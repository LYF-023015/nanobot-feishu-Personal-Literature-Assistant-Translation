from nanobot.agent.loop import AgentLoop
import json


def test_build_token_monitor_clamps_negative_residue() -> None:
    monitor = AgentLoop._build_token_monitor(
        {
            "prompt_tokens": 90,
            "completion_tokens": 40,
            "total_tokens": 130,
            "cache_tokens": 12,
        },
        output_budget_tokens=30,
        context_window_tokens=100,
        token_budget_mode="output",
    )

    assert monitor["input_tokens"] == 90
    assert monitor["output_budget_total_tokens"] == 30
    assert monitor["output_budget_used_tokens"] == 40
    assert monitor["output_budget_residue_tokens"] == 0
    assert monitor["output_budget_exceeded"] is True
    assert monitor["selected_budget_mode"] == "output"
    assert monitor["selected_budget_usage_percent"] == 100.0


def test_build_token_monitor_input_tokens_merge_prompt_and_cached_semantics() -> None:
    # Simulate provider semantics where prompt_tokens may be uncached-only,
    # while total_tokens still includes full input + output.
    monitor = AgentLoop._build_token_monitor(
        {
            "prompt_tokens": 80,
            "completion_tokens": 20,
            "total_tokens": 130,
            "cache_tokens": 30,
        },
        output_budget_tokens=200,
        context_window_tokens=0,
        token_budget_mode="output",
    )

    # merged input = max(prompt_tokens, total_tokens - completion_tokens)
    assert monitor["input_tokens"] == 110
    values = monitor["chart"]["data"]["values"]
    assert values[0] == {"category": "token用量", "item": "input", "value": 110}


def test_build_token_monitor_chart_values_match_usage() -> None:
    monitor = AgentLoop._build_token_monitor(
        {
            "prompt_tokens": 50,
            "completion_tokens": 30,
            "total_tokens": 80,
            "cache_tokens": 5,
        },
        output_budget_tokens=120,
        context_window_tokens=0,
        token_budget_mode="output",
    )

    values = monitor["chart"]["data"]["values"]
    assert values[0] == {"category": "token用量", "item": "input", "value": 50}
    assert values[1] == {"category": "token用量", "item": "output", "value": 30}


def test_build_token_monitor_chart_includes_tool_calls_when_provided() -> None:
    monitor = AgentLoop._build_token_monitor(
        {
            "prompt_tokens": 10,
            "completion_tokens": 5,
            "total_tokens": 15,
            "cache_tokens": 0,
        },
        output_budget_tokens=100,
        context_window_tokens=0,
        token_budget_mode="output",
        tool_calls_completed=3,
    )

    values = monitor["chart"]["data"]["values"]
    assert {"category": "token用量", "item": "tool_calls", "value": 3} in values


def test_format_tool_arguments_for_panel_truncates_only_long_values() -> None:
    long_text = "a" * 1500
    args = {
        "short": "ok",
        "long": long_text,
        "count": 3,
    }

    formatted = AgentLoop._format_tool_arguments_for_panel(args, max_value_chars=1000)
    parsed = json.loads(formatted)

    assert parsed["short"] == "ok"
    assert parsed["count"] == 3
    assert "内容已截断" in parsed["long"]
    assert len(parsed["long"]) > 1000


def test_format_tool_arguments_for_panel_preserves_nested_structure() -> None:
    long_text = "b" * 1200
    args = {
        "nested": {
            "message": long_text,
            "items": ["x", long_text],
        },
        "another": "keep",
    }

    formatted = AgentLoop._format_tool_arguments_for_panel(args, max_value_chars=1000)
    parsed = json.loads(formatted)

    assert set(parsed.keys()) == {"nested", "another"}
    assert parsed["another"] == "keep"
    assert "内容已截断" in parsed["nested"]["message"]
    assert "内容已截断" in parsed["nested"]["items"][1]
