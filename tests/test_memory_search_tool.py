"""Tests for MemorySearchTool."""

import asyncio
from pathlib import Path

from nanobot.agent.tools.memory_search import MemorySearchTool
from nanobot.config.schema import MemorySystemConfig


def _make_tool(tmp_path: Path) -> MemorySearchTool:
    workspace = tmp_path / "workspace"
    (workspace / "memory").mkdir(parents=True, exist_ok=True)
    (workspace / "memory" / "MEMORY.md").write_text("# MEMORY\n", encoding="utf-8")
    cfg = MemorySystemConfig(
        enabled=True,
        db_path=str(workspace / "memory" / "personal_memory.db"),
        default_user_id="test-user",
        retrieval_top_k=5,
        fallback_top_k=2,
        update_memory_md=False,
    )
    tool = MemorySearchTool(workspace=workspace, config=cfg)
    tool._store.create_memory({
        "kind": "decision",
        "scope": "topic",
        "scope_key": "coa",
        "slot": "decision.coa.schema.layers",
        "content": "CoA Schema 从五层精简为三层：L1任务层、L2轨迹层、L3通信层。",
        "summary": "CoA Schema 从五层精简为三层",
        "tags": ["CoA", "schema"],
        "keywords": ["CoA", "schema", "L1", "L2", "L3"],
        "priority": 8,
    })
    tool._store.create_memory({
        "kind": "preference",
        "scope": "global",
        "slot": "preference.reply.language",
        "content": "默认回复语言为中文。",
        "summary": "默认回复语言为中文",
        "tags": ["语言", "中文"],
        "keywords": ["中文", "language"],
        "priority": 7,
    })
    tool._store.create_memory({
        "kind": "reference",
        "scope": "topic",
        "scope_key": "plm-sol",
        "slot": "project.plm_sol.training.lora_rank",
        "content": "PLM_Sol E2 最佳 LoRA rank=8。",
        "summary": "PLM_Sol 最佳 LoRA rank=8",
        "tags": ["PLM_Sol", "LoRA"],
        "keywords": ["PLM_Sol", "LoRA", "rank"],
        "priority": 6,
    })
    return tool


def test_basic_query_returns_results(tmp_path: Path) -> None:
    tool = _make_tool(tmp_path)
    result = asyncio.run(tool.execute(query="CoA schema layers"))
    assert "decision.coa.schema.layers" in result
    assert "三层" in result


def test_top_k_limits_results(tmp_path: Path) -> None:
    tool = _make_tool(tmp_path)
    result = asyncio.run(tool.execute(query="memory language coa plm", top_k=1))
    assert result.count("### [") == 1


def test_kind_filter(tmp_path: Path) -> None:
    tool = _make_tool(tmp_path)
    result = asyncio.run(tool.execute(query="schema", kind="preference"))
    assert "decision.coa" not in result


def test_slot_prefix_filter(tmp_path: Path) -> None:
    tool = _make_tool(tmp_path)
    result = asyncio.run(tool.execute(query="lora rank training", slot_prefix="project.plm_sol"))
    assert "project.plm_sol" in result
    assert "decision.coa" not in result


def test_scope_filter(tmp_path: Path) -> None:
    tool = _make_tool(tmp_path)
    result = asyncio.run(tool.execute(query="language default", scope="global"))
    assert "preference.reply.language" in result


def test_no_results_message(tmp_path: Path) -> None:
    """When the store is completely empty, the tool should return a 'No memories found' message."""
    workspace = tmp_path / "empty_workspace"
    (workspace / "memory").mkdir(parents=True, exist_ok=True)
    (workspace / "memory" / "MEMORY.md").write_text("# MEMORY\n", encoding="utf-8")
    cfg = MemorySystemConfig(
        enabled=True,
        db_path=str(workspace / "memory" / "personal_memory.db"),
        default_user_id="test-user",
        retrieval_top_k=5,
        fallback_top_k=0,          # disable fallback so empty query returns nothing
        update_memory_md=False,
    )
    empty_tool = MemorySearchTool(workspace=workspace, config=cfg)
    result = asyncio.run(empty_tool.execute(query="xyzzy_nonexistent_query_9999"))
    assert "No memories found" in result


def test_tool_schema_valid(tmp_path: Path) -> None:
    tool = _make_tool(tmp_path)
    schema = tool.to_schema()
    assert schema["function"]["name"] == "memory_search"
    assert "query" in schema["function"]["parameters"]["properties"]
    assert "query" in schema["function"]["parameters"]["required"]
