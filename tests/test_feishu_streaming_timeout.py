import asyncio

from nanobot.agent.loop import AgentLoop
from nanobot.bus.events import InboundMessage
from nanobot.bus.queue import MessageBus
from nanobot.config.schema import FeishuConfig


def _make_loop() -> AgentLoop:
    loop = AgentLoop.__new__(AgentLoop)
    loop.bus = MessageBus()
    loop.feishu_config = FeishuConfig(
        streaming_enabled=True,
        streaming_print_frequency_ms_default=20,
        streaming_print_step_default=1,
    )
    loop._build_stream_id = lambda _msg: "test-stream-id"
    return loop


def _collect_outbound(bus: MessageBus) -> list:
    items = []
    while not bus.outbound.empty():
        items.append(bus.outbound.get_nowait())
    return items


def test_streaming_timeout_fallback_to_regular_message(monkeypatch) -> None:
    loop = _make_loop()
    msg = InboundMessage(channel="feishu", sender_id="u1", chat_id="c1", content="hello")
    final_content = "A" * 100
    token_monitor = {"chart": {"type": "bar", "data": {"values": []}}}

    # First call for stream start, second call in loop triggers timeout.
    times = iter([0.0, 481.0, 482.0])
    monkeypatch.setattr("nanobot.agent.loop.time.time", lambda: next(times))

    asyncio.run(
        loop._publish_feishu_streaming_response(
            msg=msg,
            final_content=final_content,
            token_monitor=token_monitor,
            stream_id="s1",
            send_init=False,
        )
    )

    outbound = _collect_outbound(loop.bus)
    assert len(outbound) == 3

    finalize = outbound[0]
    assert finalize.metadata["feishu_stream"]["action"] == "finalize"
    assert finalize.metadata["feishu_stream"]["full_text"] == "A" * 20

    notice = outbound[1]
    assert "feishu_stream" not in notice.metadata
    assert "超出流式窗口限制" in notice.content

    remaining = outbound[2]
    assert "feishu_stream" not in remaining.metadata
    assert remaining.content == "A" * 80


def test_streaming_within_window_keeps_finalize_flow(monkeypatch) -> None:
    loop = _make_loop()
    msg = InboundMessage(channel="feishu", sender_id="u1", chat_id="c1", content="hello")
    final_content = "B" * 45
    token_monitor = {"chart": {"type": "bar", "data": {"values": []}}}

    times = iter([0.0, 1.0, 2.0, 3.0])
    monkeypatch.setattr("nanobot.agent.loop.time.time", lambda: next(times))

    asyncio.run(
        loop._publish_feishu_streaming_response(
            msg=msg,
            final_content=final_content,
            token_monitor=token_monitor,
            stream_id="s2",
            send_init=False,
        )
    )

    outbound = _collect_outbound(loop.bus)
    assert len(outbound) == 4
    assert outbound[0].metadata["feishu_stream"]["action"] == "append"
    assert outbound[1].metadata["feishu_stream"]["action"] == "append"
    assert outbound[2].metadata["feishu_stream"]["action"] == "append"
    assert outbound[3].metadata["feishu_stream"]["action"] == "finalize"
    assert outbound[3].metadata["feishu_stream"]["full_text"] == final_content
