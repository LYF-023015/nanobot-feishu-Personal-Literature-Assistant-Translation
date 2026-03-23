import asyncio

from nanobot.agent.tools.message import MessageTool


class _Capture:
    def __init__(self) -> None:
        self.last_msg = None

    async def send(self, msg):
        self.last_msg = msg


def test_message_tool_injects_token_monitor_metadata() -> None:
    capture = _Capture()
    tool = MessageTool(send_callback=capture.send)
    tool.set_context("feishu", "ou_test")
    tool.set_token_monitor_factory(
        lambda: {
            "input_tokens": 12,
            "output_tokens": 7,
            "context_budget_residue_tokens": 81,
            "chart": {
                "type": "bar",
                "data": {
                    "values": [
                        {"category": "token用量", "item": "input", "value": 12},
                        {"category": "token用量", "item": "output", "value": 7},
                        {"category": "token用量", "item": "residue", "value": 81},
                    ]
                },
            },
        }
    )

    result = asyncio.run(tool.execute(content="hello"))

    assert result == "Message sent to feishu:ou_test"
    assert capture.last_msg is not None
    assert capture.last_msg.metadata["token_monitor"]["output_tokens"] == 7
