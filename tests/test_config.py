import pytest

from src.bot_app.config import PROJECT_ROOT, Settings


def test_settings_resolve_relative_database_path_from_project_root(monkeypatch) -> None:
    monkeypatch.setenv("DISCORD_TOKEN", "test-token")
    monkeypatch.setenv("DATABASE_PATH", "data/test.sqlite3")
    monkeypatch.delenv("TEST_GUILD_ID", raising=False)

    settings = Settings.from_environment()

    assert settings.database_path == (PROJECT_ROOT / "data" / "test.sqlite3").resolve()


def test_settings_reject_placeholder_token(monkeypatch) -> None:
    monkeypatch.setenv("DISCORD_TOKEN", "coloque_seu_token_aqui")
    monkeypatch.delenv("DATABASE_PATH", raising=False)
    monkeypatch.delenv("TEST_GUILD_ID", raising=False)

    with pytest.raises(RuntimeError, match="DISCORD_TOKEN"):
        Settings.from_environment()


def test_settings_reject_non_numeric_test_guild(monkeypatch) -> None:
    monkeypatch.setenv("DISCORD_TOKEN", "test-token")
    monkeypatch.setenv("TEST_GUILD_ID", "not-a-number")

    with pytest.raises(RuntimeError, match="TEST_GUILD_ID"):
        Settings.from_environment()
