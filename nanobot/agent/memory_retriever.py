"""Retrieve relevant personal memories for prompt injection."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from nanobot.agent.personal_memory_store import PersonalMemoryStore
from nanobot.config.schema import MemorySystemConfig


class MemoryRetriever:
    """Build retrieval query and render prompt blocks for personal memory."""

    def __init__(self, workspace: Path, config: MemorySystemConfig):
        self.workspace = workspace
        self.config = config
        self.store = PersonalMemoryStore(workspace, config)

    def build_query(
        self,
        user_text: str,
        session_state: str | None,
        recent_messages: list[dict[str, Any]],
    ) -> str:
        parts: list[str] = []
        if session_state:
            parts.append(str(session_state).strip())
        for msg in recent_messages[-4:]:
            role = msg.get("role")
            content = str(msg.get("content") or "").strip()
            if role in {"user", "assistant"} and content:
                parts.append(content)
        if user_text.strip():
            parts.append(user_text.strip())
        return "\n".join(parts).strip()

    def _infer_scope_hints(self, query: str) -> dict[str, Any]:
        q = (query or "").lower()
        if "nanobot" in q or "memory" in q or "记忆" in q:
            return {"scope": "topic", "scope_key": "nanobot-memory"}
        return {}

    def retrieve_for_prompt(
        self,
        user_text: str,
        session_state: str | None,
        recent_messages: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        query = self.build_query(user_text, session_state, recent_messages)
        scope_hints = self._infer_scope_hints(query)
        results = self.store.retrieve(query=query, scope_hints=scope_hints, top_k=self.config.retrieval_top_k)
        self.store.mark_used([item["id"] for item in results if item.get("id")])
        return results

    def render_memory_block(self, retrieved: list[dict[str, Any]]) -> str:
        if not retrieved:
            return ""
        lines = ["## Retrieved Personal Memory", ""]
        for item in retrieved:
            slot = item.get("slot") or item.get("kind") or "memory"
            summary = item.get("summary") or item.get("content") or ""
            lines.append(f"- [{slot}] {summary}")
        return "\n".join(lines)
