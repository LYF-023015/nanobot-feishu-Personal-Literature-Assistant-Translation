"""LLM-assisted personal memory compiler."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from loguru import logger

from nanobot.agent.personal_memory_store import PersonalMemoryStore
from nanobot.config.schema import MemorySystemConfig
from nanobot.providers.base import LLMProvider


class MemoryCompiler:
    """Extract, merge, and refresh personal long-term memory."""

    def __init__(
        self,
        workspace: Path,
        provider: LLMProvider,
        config: MemorySystemConfig,
        default_model: str,
    ) -> None:
        self.workspace = workspace
        self.provider = provider
        self.config = config
        self.default_model = default_model
        self.store = PersonalMemoryStore(workspace, config)

    async def extract_candidates_from_text(self, text: str, extracted_from: str) -> list[dict[str, Any]]:
        if not self.config.enabled:
            return []
        if not text or len(text.strip()) < 80:
            return []
        prompt = self._extractor_prompt(text)
        response = await self.provider.chat(
            messages=[
                {"role": "system", "content": "You are a precise memory extractor. Output JSON only."},
                {"role": "user", "content": prompt},
            ],
            tools=None,
            model=self.config.llm_model or self.default_model,
            max_tokens=1800,
            temperature=0.1,
        )
        data = self._parse_json_response(response.content or "")
        if not isinstance(data, dict):
            return []
        memories = data.get("memories") or []
        cleaned = [self._normalize_candidate(item) for item in memories if isinstance(item, dict)]
        cleaned = [item for item in cleaned if item.get("content") and item.get("summary")]
        if cleaned:
            self.store.add_candidates(cleaned, extracted_from=extracted_from)
        return cleaned

    async def merge_candidates(self, limit: int = 100) -> dict[str, int]:
        if not self.config.enabled:
            return {"create": 0, "update": 0, "supersede": 0, "noop": 0}
        counters = {"create": 0, "update": 0, "supersede": 0, "noop": 0}
        candidates = self.store.get_unmerged_candidates(limit=limit)
        for candidate in candidates:
            related = self.store.find_related_memories(candidate, limit=self.config.max_related_memories)
            decision = await self._merge_one_candidate(candidate, related)
            action = str(decision.get("action") or "noop")
            if action not in counters:
                action = "noop"
            before = None
            after = decision.get("memory") if isinstance(decision.get("memory"), dict) else None
            target_memory_id = decision.get("target_memory_id")
            if action == "create" and after:
                memory_id = self.store.create_memory(after)
                target_memory_id = memory_id
            elif action == "update" and after and target_memory_id:
                before = self.store.get_memory(target_memory_id)
                self.store.update_memory(target_memory_id, after)
            elif action == "supersede" and after and target_memory_id:
                before = self.store.get_memory(target_memory_id)
                memory_id = self.store.supersede_memory(target_memory_id, after)
                target_memory_id = memory_id
            self.store.mark_candidate_merged(candidate["id"])
            self.store.log_event(
                {
                    "memory_id": target_memory_id,
                    "candidate_id": candidate.get("id"),
                    "action": action,
                    "reason": decision.get("reason", ""),
                    "before": before,
                    "after": after,
                }
            )
            counters[action] += 1
        self.store.sync_memory_md(
            extra_notes=[
                f"personal_memory.db: {self.store.db_path}",
                f"每日自动更新已启用: {'是' if self.config.enabled else '否'}",
                f"检索 top-k: {self.config.retrieval_top_k}",
            ]
        )
        return counters

    async def daily_update_from_file(self, path: Path, extracted_from: str) -> dict[str, int]:
        text = path.read_text(encoding="utf-8") if path.exists() else ""
        await self.extract_candidates_from_text(text=text, extracted_from=extracted_from)
        return await self.merge_candidates(limit=self.config.max_candidates_per_run)

    def rebuild_memory_md(self) -> None:
        self.store.sync_memory_md(
            extra_notes=[
                f"personal_memory.db: {self.store.db_path}",
                f"retrieval_top_k={self.config.retrieval_top_k}",
                f"core_memory_max_items={self.config.core_memory_max_items}",
            ]
        )

    async def _merge_one_candidate(self, candidate: dict[str, Any], related: list[dict[str, Any]]) -> dict[str, Any]:
        prompt = self._merger_prompt(candidate, related)
        response = await self.provider.chat(
            messages=[
                {"role": "system", "content": "You are a precise memory merger. Output JSON only."},
                {"role": "user", "content": prompt},
            ],
            tools=None,
            model=self.config.llm_model or self.default_model,
            max_tokens=1600,
            temperature=0.1,
        )
        data = self._parse_json_response(response.content or "")
        if not isinstance(data, dict):
            return {"action": "noop", "reason": "invalid_json"}
        if isinstance(data.get("memory"), dict):
            data["memory"] = self._normalize_candidate(data["memory"])
        return data

    def _extractor_prompt(self, text: str) -> str:
        return (
            "你是一个长期记忆提炼器。你的任务是从给定内容中，只提取未来可复用的长期记忆。\n\n"
            "允许提取：用户长期偏好、长期约束/规则、已确定方案/稳定决策、长期稳定参考信息、稳定身份背景。\n"
            "禁止提取：一次性任务进度、普通问答、工具输出本身、临时调试过程、未确认推测、短期待办。\n\n"
            "输出要求：\n"
            "1. 若没有值得保留的长期记忆，输出 {\"action\":\"noop\",\"memories\":[]}\n"
            "2. 每条记忆必须原子化，只表达一个稳定结论\n"
            "3. 每条记忆必须高信息密度，content 1-3 句，summary 更短\n"
            "4. slot 格式尽量规范为 <kind>.<namespace>.<key>\n"
            f"5. 最多输出 {self.config.max_candidates_per_run} 条\n\n"
            "只输出 JSON，不要输出解释。\n\n"
            "内容如下：\n"
            f"{text}"
        )

    def _merger_prompt(self, candidate: dict[str, Any], related: list[dict[str, Any]]) -> str:
        return (
            "你是一个长期记忆合并器。根据新候选记忆与已有记忆，判断应 create / update / supersede / noop。\n"
            "原则：优先合并而不是制造重复；同 slot 优先视为同一记忆位；补充信息用 update；明确冲突用 supersede。\n"
            "只输出 JSON。\n\n"
            f"候选记忆:\n{json.dumps(candidate, ensure_ascii=False, indent=2)}\n\n"
            f"已有相关记忆:\n{json.dumps(related, ensure_ascii=False, indent=2)}\n"
        )

    @staticmethod
    def _parse_json_response(text: str) -> Any:
        text = (text or "").strip()
        if not text:
            return {}
        if text.startswith("```"):
            lines = text.splitlines()
            if len(lines) >= 3:
                text = "\n".join(lines[1:-1]).strip()
        try:
            return json.loads(text)
        except Exception:
            start = text.find("{")
            end = text.rfind("}")
            if start != -1 and end != -1 and end > start:
                try:
                    return json.loads(text[start : end + 1])
                except Exception:
                    logger.warning("Failed to parse memory compiler JSON response")
        return {}

    def _normalize_candidate(self, item: dict[str, Any]) -> dict[str, Any]:
        summary = str(item.get("summary") or item.get("content") or "").strip()
        summary = summary[: self.config.summary_max_chars]
        priority = int(item.get("priority", 0) or 0)
        kind = str(item.get("kind") or "reference").strip()
        scope = str(item.get("scope") or "global").strip()
        scope_key = str(item.get("scope_key") or "").strip()
        slot = str(item.get("slot") or "").strip()
        tags = [str(x).strip() for x in item.get("tags", []) if str(x).strip()]
        keywords = [str(x).strip() for x in item.get("keywords", []) if str(x).strip()]
        source_refs = [str(x).strip() for x in item.get("source_refs", []) if str(x).strip()]
        if not slot:
            namespace = scope_key or "general"
            key = (summary or kind).lower().replace(" ", "_")[:40]
            slot = f"{kind}.{namespace}.{key}"
        return {
            "kind": kind,
            "scope": scope,
            "scope_key": scope_key,
            "slot": slot,
            "content": str(item.get("content") or "").strip(),
            "summary": summary,
            "tags": list(dict.fromkeys(tags)),
            "keywords": list(dict.fromkeys(keywords or tags)),
            "source_refs": list(dict.fromkeys(source_refs)),
            "priority": priority,
        }
