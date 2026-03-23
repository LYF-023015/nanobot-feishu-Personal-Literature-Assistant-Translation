from nanobot.agent.loop import AgentLoop


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

    assert monitor["input_cached_tokens"] == 12
    assert monitor["input_uncached_tokens"] == 78
    assert monitor["output_budget_total_tokens"] == 30
    assert monitor["output_budget_used_tokens"] == 40
    assert monitor["output_budget_residue_tokens"] == 0
    assert monitor["output_budget_exceeded"] is True
    assert monitor["selected_budget_mode"] == "output"
    assert monitor["selected_budget_usage_percent"] == 100.0


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
    assert values[0] == {"category": "token用量", "item": "input_cached", "value": 5}
    assert values[1] == {"category": "token用量", "item": "input_uncached", "value": 45}
    assert values[2] == {"category": "token用量", "item": "output", "value": 30}
    assert values[3] == {"category": "token用量", "item": "sum_tokens", "value": 80}
