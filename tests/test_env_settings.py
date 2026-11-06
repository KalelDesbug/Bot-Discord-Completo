from __future__ import annotations

from pathlib import Path

import pytest

from src.config.env import PROJECT_ROOT, Settings, _optional_int


def test_settings_only_require_discord_token(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("DISCORD_TOKEN", raising=False)
    monkeypatch.delenv("DATABASE_PATH", raising=False)

    with pytest.raises(ValueError, match="DISCORD_TOKEN"):
        Settings.from_environment()

    monkeypatch.setenv("DISCORD_TOKEN", "test-token")
    settings = Settings.from_environment()
    assert settings.discord_token == "test-token"
    assert settings.database_path == (PROJECT_ROOT / "data/community_bot.sqlite3").resolve()


def test_settings_parse_database_and_optional_values(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DISCORD_TOKEN", "test-token")
    monkeypatch.setenv("DATABASE_PATH", "data/test.sqlite3")
    monkeypatch.setenv("GUILD_ID", "12345")
    monkeypatch.setenv("TICKET_CATEGORY_ID", "67890")

    settings = Settings.from_environment()

    assert settings.database_path == (PROJECT_ROOT / "data/test.sqlite3").resolve()
    assert settings.guild_id == 12345
    assert settings.ticket_category_id == 67890


def test_settings_support_absolute_database_path(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    target = tmp_path / "bot.sqlite3"
    monkeypatch.setenv("DISCORD_TOKEN", "test-token")
    monkeypatch.setenv("DATABASE_PATH", str(target))
    assert Settings.from_environment().database_path == target.resolve()


def test_optional_int_rejects_non_integer(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GUILD_ID", "not-an-id")
    with pytest.raises(ValueError, match="GUILD_ID"):
        _optional_int("GUILD_ID")
