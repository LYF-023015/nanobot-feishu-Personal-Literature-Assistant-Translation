from pathlib import Path

from nanobot.agent.personal_memory_store import PersonalMemoryStore
from nanobot.config.schema import MemorySystemConfig


def _make_store(tmp_path: Path) -> PersonalMemoryStore:
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
        update_memory_md=True,
    )
    return PersonalMemoryStore(workspace, cfg)


def test_memory_store_create_retrieve_and_stats(tmp_path: Path) -> None:
    store = _make_store(tmp_path)
    store.create_memory(
        {
            "kind": "preference",
            "scope": "global",
            "slot": "preference.reply.language",
            "content": "默认回复语言为中文。",
            "summary": "默认回复语言为中文",
            "tags": ["语言", "中文"],
            "keywords": ["中文", "reply", "language"],
            "priority": 8,
            "source_refs": ["test:a"],
        }
    )
    store.create_memory(
        {
            "kind": "decision",
            "scope": "topic",
            "scope_key": "nanobot-memory",
            "slot": "decision.memory.architecture",
            "content": "采用数据库+检索召回的长期记忆方案。",
            "summary": "采用数据库+检索召回的长期记忆方案",
            "tags": ["memory", "architecture"],
            "keywords": ["memory", "检索", "数据库"],
            "priority": 6,
            "source_refs": ["test:b"],
        }
    )

    hits = store.retrieve("请用中文回答", top_k=3)
    assert hits
    assert hits[0]["slot"] == "preference.reply.language"

    stats = store.get_stats()
    assert stats["active"] == 2
    assert stats["candidates_total"] == 0
    assert Path(stats["db_path"]).exists()


def test_memory_store_fallback_returns_core_memory(tmp_path: Path) -> None:
    store = _make_store(tmp_path)
    store.create_memory(
        {
            "kind": "reference",
            "scope": "global",
            "slot": "reference.user.school",
            "content": "Wuu大王来自上海交通大学。",
            "summary": "Wuu大王来自上海交通大学",
            "tags": ["SJTU"],
            "keywords": ["上海交通大学", "SJTU"],
            "priority": 9,
            "source_refs": ["test:c"],
        }
    )

    hits = store.retrieve("一个完全无关的查询词zxqv", top_k=3)
    assert len(hits) == 1
    assert hits[0]["slot"] == "reference.user.school"


def test_sync_memory_md_writes_auto_sections(tmp_path: Path) -> None:
    store = _make_store(tmp_path)
    store.create_memory(
        {
            "kind": "preference",
            "scope": "global",
            "slot": "preference.reply.style",
            "content": "回复要简洁、结构化。",
            "summary": "回复要简洁、结构化",
            "tags": ["style"],
            "keywords": ["简洁", "结构化"],
            "priority": 7,
            "source_refs": ["test:d"],
        }
    )

    store.sync_memory_md(extra_notes=["personal_memory.db: test.db", "检索 top-k: 5"])
    text = (tmp_path / "workspace" / "memory" / "MEMORY.md").read_text(encoding="utf-8")
    assert "## Auto Core Memory" in text
    assert "[preference.reply.style] 回复要简洁、结构化" in text
    assert "## Auto Memory System" in text
    assert "personal_memory.db: test.db" in text
