from pathlib import Path

from nanobot.agent.context import ContextBuilder


class DummyRetriever:
    def __init__(self):
        self.calls = []

    def retrieve_for_prompt(self, user_text, session_state=None, recent_messages=None):
        self.calls.append(
            {
                "user_text": user_text,
                "session_state": session_state,
                "recent_messages": recent_messages,
            }
        )
        return [{"memory_id": "m1", "summary": "memory summary", "content": "memory content"}]

    def render_memory_block(self, memories):
        return "# Retrieved Memories\n\n- memory summary"


def test_context_builder_triggers_memory_retrieval_and_records_stats(tmp_path: Path):
    (tmp_path / "AGENTS.md").write_text("agent", encoding="utf-8")
    (tmp_path / "SOUL.md").write_text("soul", encoding="utf-8")
    (tmp_path / "USER.md").write_text("user", encoding="utf-8")
    (tmp_path / "memory").mkdir()
    (tmp_path / "memory" / "MEMORY.md").write_text("index", encoding="utf-8")

    ctx = ContextBuilder(tmp_path, memory_system_config=None)
    ctx.memory_retriever = DummyRetriever()

    history = [{"role": "user", "content": "之前聊过记忆系统"}]
    messages = ctx.build_messages(
        history=history,
        current_message="继续说长期记忆",
        session_summary="summary",
        channel="feishu",
        chat_id="chat-1",
    )

    assert len(ctx.memory_retriever.calls) == 1
    call = ctx.memory_retriever.calls[0]
    assert call["user_text"] == "继续说长期记忆"
    assert call["session_state"] == "summary"
    assert call["recent_messages"] == history

    assert messages[0]["role"] == "system"
    assert "# Retrieved Memories" in messages[0]["content"]
    assert "## Current Session\nChannel: feishu\nChat ID: chat-1" in messages[0]["content"]
    assert messages[-1]["role"] == "user"
    assert ctx.last_build_stats["retrieved_count"] == 1
    assert ctx.last_build_stats["history_messages"] == 1
    assert ctx.last_build_stats["channel"] == "feishu"
    assert ctx.last_build_stats["chat_id"] == "chat-1"


def test_context_builder_bootstrap_cache_hits_and_invalidates(tmp_path: Path):
    (tmp_path / "AGENTS.md").write_text("v1", encoding="utf-8")
    ctx = ContextBuilder(tmp_path, memory_system_config=None)

    first = ctx._read_cached_text(tmp_path / "AGENTS.md")
    second = ctx._read_cached_text(tmp_path / "AGENTS.md")
    assert first == second == "v1"

    (tmp_path / "AGENTS.md").write_text("v2", encoding="utf-8")
    third = ctx._read_cached_text(tmp_path / "AGENTS.md")
    assert third == "v2"
