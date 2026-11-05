import pytest

from src.bot_app.config import (
    BotPreferences,
    PROJECT_ROOT,
    Settings,
    load_bot_preferences,
)


def test_settings_resolve_relative_database_path_from_project_root(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("DISCORD_TOKEN", "test-token")
    monkeypatch.setenv("DATABASE_PATH", "data/test.sqlite3")
    monkeypatch.delenv("TEST_GUILD_ID", raising=False)

    settings = Settings.from_environment(tmp_path / "missing.json")

    assert settings.database_path == (PROJECT_ROOT / "data" / "test.sqlite3").resolve()
    assert settings.preferences == BotPreferences()


def test_settings_reject_placeholder_token(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("DISCORD_TOKEN", "coloque_seu_token_aqui")
    monkeypatch.delenv("DATABASE_PATH", raising=False)
    monkeypatch.delenv("TEST_GUILD_ID", raising=False)

    with pytest.raises(RuntimeError, match="DISCORD_TOKEN"):
        Settings.from_environment(tmp_path / "missing.json")


def test_settings_reject_non_numeric_test_guild(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("DISCORD_TOKEN", "test-token")
    monkeypatch.setenv("TEST_GUILD_ID", "not-a-number")

    with pytest.raises(RuntimeError, match="TEST_GUILD_ID"):
        Settings.from_environment(tmp_path / "missing.json")


def test_load_bot_preferences_reads_easy_restart_and_log_options(tmp_path) -> None:
    config_path = tmp_path / "config-bot.json"
    config_path.write_text(
        '{"restart":{"enabled":false,"interval_hours":12,"retry_seconds":20},'
        '"logs":{"discord_enabled":false,"console_level":"DEBUG"}}',
        encoding="utf-8",
    )

    preferences = load_bot_preferences(config_path)

    assert preferences.restart_enabled is False
    assert preferences.restart_interval_hours == 12
    assert preferences.restart_retry_seconds == 20
    assert preferences.discord_logs_enabled is False
    assert preferences.console_log_level == "DEBUG"


def test_load_bot_preferences_rejects_invalid_interval(tmp_path) -> None:
    config_path = tmp_path / "config-bot.json"
    config_path.write_text('{"restart":{"interval_hours":0}}', encoding="utf-8")

    with pytest.raises(RuntimeError, match="interval_hours"):
        load_bot_preferences(config_path)
