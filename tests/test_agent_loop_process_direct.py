import asyncio

from nanobot.agent.loop import AgentLoop
from nanobot.bus.events import OutboundMessage


class _DummyLoop:
    def __init__(self):
        self.captured = None

    async def _process_message(self, msg):
        self.captured = msg
        return OutboundMessage(channel=msg.channel, chat_id=msg.chat_id, content="ok")


def test_process_direct_injects_session_key_override():
    dummy = _DummyLoop()
    result = asyncio.run(
        AgentLoop.process_direct(
            dummy,
            content="hello",
            session_key="cli:test-session",
            channel="cli",
            chat_id="direct-chat",
        )
    )

    assert result == "ok"
    assert dummy.captured is not None
    assert dummy.captured.metadata["session_key_override"] == "cli:test-session"
    assert dummy.captured.channel == "cli"
    assert dummy.captured.chat_id == "direct-chat"
    assert dummy.captured.content == "hello"
