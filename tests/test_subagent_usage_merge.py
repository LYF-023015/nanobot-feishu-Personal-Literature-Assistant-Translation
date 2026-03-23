from nanobot.agent.loop import AgentLoop


def test_build_token_monitor_context_mode_with_budget() -> None:
    monitor = AgentLoop._build_token_monitor(
        {
            "prompt_tokens": 70,
            "completion_tokens": 20,
            "total_tokens": 90,
            "cache_tokens": 30,
        },
        output_budget_tokens=40,
        context_window_tokens=200,
        token_budget_mode="context",
    )

    assert monitor["selected_budget_mode"] == "context"
    assert monitor["selected_budget_total_tokens"] == 200
    assert monitor["selected_budget_used_tokens"] == 90
    assert monitor["selected_budget_residue_tokens"] == 110
    values = monitor["chart"]["data"]["values"]
    assert values[0]["item"] == "input_cached"
    assert values[0]["value"] == 30
    assert values[1]["item"] == "input_uncached"
    assert values[1]["value"] == 40
    assert values[2]["item"] == "output"
    assert values[2]["value"] == 20
    assert values[3]["item"] == "sum_tokens"
    assert values[3]["value"] == 90
