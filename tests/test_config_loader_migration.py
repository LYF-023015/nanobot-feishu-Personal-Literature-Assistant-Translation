from nanobot.config.loader import _migrate_config


def test_migrate_keep_recent_tool_messages_to_tool_history() -> None:
    data = {
        "tools": {
            "toolHistory": {
                "maxEvents": 5,
            },
            "contextCompression": {
                "keepRecentToolMessages": 12,
            },
        }
    }

    migrated = _migrate_config(data)

    assert migrated["tools"]["toolHistory"]["keepRecentMessages"] == 12
    assert "keepRecentToolMessages" not in migrated["tools"]["contextCompression"]


def test_migrate_keep_recent_tool_messages_does_not_override_existing_tool_history() -> None:
    data = {
        "tools": {
            "toolHistory": {
                "keepRecentMessages": 7,
            },
            "contextCompression": {
                "keepRecentToolMessages": 12,
            },
        }
    }

    migrated = _migrate_config(data)

    assert migrated["tools"]["toolHistory"]["keepRecentMessages"] == 7
    assert migrated["tools"]["contextCompression"]["keepRecentToolMessages"] == 12
