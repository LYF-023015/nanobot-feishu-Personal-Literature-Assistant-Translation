from pathlib import Path
import asyncio

from nanobot.agent.memory_compiler import MemoryCompiler
from nanobot.config.schema import MemorySystemConfig
from nanobot.providers.base import LLMProvider, LLMResponse


class FakeProvider(LLMProvider):
    def __init__(self, responses: list[str]):
        super().__init__(api_key=None, api_base=None)
        self.responses = responses
        self.calls: list[dict] = []

    async def chat(self, messages, tools=None, model=None, max_tokens=4096, temperature=0.7, **kwargs):
        self.calls.append(
            {
                "messages": messages,
                "tools": tools,
                "model": model,
                "max_tokens": max_tokens,
                "temperature": temperature,
                "kwargs": kwargs,
            }
        )
        content = self.responses.pop(0)
        return LLMResponse(content=content, usage={"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15})

    def get_default_model(self) -> str:
        return "fake-model"


def _make_compiler(tmp_path: Path, responses: list[str]) -> MemoryCompiler:
    workspace = tmp_path / "workspace"
    (workspace / "memory").mkdir(parents=True, exist_ok=True)
    (workspace / "memory" / "MEMORY.md").write_text("# MEMORY\n", encoding="utf-8")
    cfg = MemorySystemConfig(
        enabled=True,
        db_path=str(workspace / "memory" / "personal_memory.db"),
        default_user_id="test-user",
        retrieval_top_k=5,
        fallback_top_k=2,
        core_memory_max_items=8,
        max_candidates_per_run=3,
        max_related_memories=5,
        update_memory_md=True,
    )
    return MemoryCompiler(
        workspace=workspace,
        provider=FakeProvider(responses),
        config=cfg,
        default_model="fake-model",
    )


def test_memory_compiler_daily_update_create_and_memory_md(tmp_path: Path) -> None:
    diary = tmp_path / "diary.md"
    diary.write_text(
        "今天讨论后确认：长期记忆方案采用 SQLite 个人数据库 + query 检索召回；Core Memory 直接集成到 MEMORY.md。"
        "同时明确不采用过度工程化的 proposal queue、confidence scoring、vector DB 和每轮在线自动写库，"
        "而是改为每日批处理更新，以保证系统简单、稳定、可维护。",
        encoding="utf-8",
    )
    compiler = _make_compiler(
        tmp_path,
        responses=[
            '{"memories":[{"kind":"decision","scope":"global","slot":"decision.memory.architecture","content":"长期记忆方案采用 SQLite 个人数据库 + query 检索召回。","summary":"长期记忆方案采用 SQLite 个人数据库 + query 检索召回","tags":["memory","sqlite"],"keywords":["SQLite","检索召回"],"priority":8}]}',
            '{"action":"create","reason":"new stable decision","memory":{"kind":"decision","scope":"global","slot":"decision.memory.architecture","content":"长期记忆方案采用 SQLite 个人数据库 + query 检索召回。","summary":"长期记忆方案采用 SQLite 个人数据库 + query 检索召回","tags":["memory","sqlite"],"keywords":["SQLite","检索召回"],"priority":8}}',
        ],
    )

    result = asyncio.run(compiler.daily_update_from_file(diary, extracted_from="test:diary"))
    assert result == {"create": 1, "update": 0, "supersede": 0, "noop": 0}

    active = compiler.store.list_active_memories()
    assert len(active) == 1
    assert active[0]["slot"] == "decision.memory.architecture"

    memory_md = (tmp_path / "workspace" / "memory" / "MEMORY.md").read_text(encoding="utf-8")
    assert "## Auto Core Memory" in memory_md
    assert "decision.memory.architecture" in memory_md
    assert "personal_memory.db:" in memory_md


def test_memory_compiler_merge_updates_existing_slot(tmp_path: Path) -> None:
    compiler = _make_compiler(
        tmp_path,
        responses=[
            '{"action":"update","reason":"same slot with better summary","target_memory_id":"mem_existing","memory":{"kind":"preference","scope":"global","slot":"preference.reply.style","content":"回复要简洁、结构化，并保持专业。","summary":"回复要简洁、结构化，并保持专业","tags":["style"],"keywords":["简洁","结构化","专业"],"priority":9}}',
        ],
    )
    compiler.store.create_memory(
        {
            "id": "mem_existing",
            "kind": "preference",
            "scope": "global",
            "slot": "preference.reply.style",
            "content": "回复要简洁、结构化。",
            "summary": "回复要简洁、结构化",
            "tags": ["style"],
            "keywords": ["简洁", "结构化"],
            "priority": 7,
            "source_refs": ["old:test"],
        }
    )
    compiler.store.add_candidates(
        [
            {
                "id": "cand_1",
                "kind": "preference",
                "scope": "global",
                "slot": "preference.reply.style",
                "content": "回复要简洁、结构化，并保持专业。",
                "summary": "回复要简洁、结构化，并保持专业",
                "tags": ["style"],
                "keywords": ["简洁", "结构化", "专业"],
                "source_refs": ["new:test"],
                "priority": 9,
            }
        ],
        extracted_from="test:candidate",
    )

    result = asyncio.run(compiler.merge_candidates(limit=5))
    assert result == {"create": 0, "update": 1, "supersede": 0, "noop": 0}

    updated = compiler.store.get_memory("mem_existing")
    assert updated is not None
    assert updated["summary"] == "回复要简洁、结构化，并保持专业"
    assert "专业" in updated["keywords"]

    events = compiler.store.list_recent_events(limit=5)
    assert events
    assert events[0]["action"] == "update"
