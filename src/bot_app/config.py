import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[2]
BOT_CONFIG_PATH = PROJECT_ROOT / "config-bot.json"
DEFAULT_RESTART_HOURS = 24
DEFAULT_RESTART_RETRY_SECONDS = 10
DEFAULT_CONSOLE_LOG_LEVEL = "INFO"
ALLOWED_LOG_LEVELS = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}


@dataclass(frozen=True, slots=True)
class BotPreferences:
    restart_enabled: bool = True
    restart_interval_hours: int = DEFAULT_RESTART_HOURS
    restart_retry_seconds: int = DEFAULT_RESTART_RETRY_SECONDS
    discord_logs_enabled: bool = True
    console_log_level: str = DEFAULT_CONSOLE_LOG_LEVEL


def load_bot_preferences(path: Path = BOT_CONFIG_PATH) -> BotPreferences:
    if not path.exists():
        return BotPreferences()

    try:
        data: Any = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"Não foi possível ler {path.name}: confira se o JSON está válido.") from exc

    if not isinstance(data, dict):
        raise RuntimeError(f"{path.name} precisa conter um objeto JSON na raiz.")

    restart = data.get("restart", {})
    logs = data.get("logs", {})
    if not isinstance(restart, dict) or not isinstance(logs, dict):
        raise RuntimeError("As seções 'restart' e 'logs' precisam ser objetos JSON.")

    enabled = restart.get("enabled", True)
    if not isinstance(enabled, bool):
        raise RuntimeError("restart.enabled precisa ser true ou false.")

    interval_hours = restart.get("interval_hours", DEFAULT_RESTART_HOURS)
    if type(interval_hours) is not int or not 1 <= interval_hours <= 720:
        raise RuntimeError("restart.interval_hours precisa ser um número inteiro entre 1 e 720.")

    retry_seconds = restart.get("retry_seconds", DEFAULT_RESTART_RETRY_SECONDS)
    if type(retry_seconds) is not int or not 1 <= retry_seconds <= 3600:
        raise RuntimeError("restart.retry_seconds precisa ser um número inteiro entre 1 e 3600.")

    discord_logs_enabled = logs.get("discord_enabled", True)
    if not isinstance(discord_logs_enabled, bool):
        raise RuntimeError("logs.discord_enabled precisa ser true ou false.")

    console_log_level = logs.get("console_level", DEFAULT_CONSOLE_LOG_LEVEL)
    if not isinstance(console_log_level, str) or console_log_level.upper() not in ALLOWED_LOG_LEVELS:
        allowed = ", ".join(sorted(ALLOWED_LOG_LEVELS))
        raise RuntimeError(f"logs.console_level precisa ser um destes níveis: {allowed}.")

    return BotPreferences(
        restart_enabled=enabled,
        restart_interval_hours=interval_hours,
        restart_retry_seconds=retry_seconds,
        discord_logs_enabled=discord_logs_enabled,
        console_log_level=console_log_level.upper(),
    )


@dataclass(frozen=True, slots=True)
class Settings:
    discord_token: str
    database_path: Path
    test_guild_id: int | None = None
    preferences: BotPreferences = BotPreferences()

    @classmethod
    def from_environment(cls, config_path: Path = BOT_CONFIG_PATH) -> "Settings":
        token = os.getenv("DISCORD_TOKEN", "").strip()
        if not token or token.casefold() == "coloque_seu_token_aqui":
            raise RuntimeError(
                "DISCORD_TOKEN não foi definido ou ainda contém o valor de exemplo."
            )

        raw_guild = os.getenv("TEST_GUILD_ID", "").strip()
        try:
            guild_id = int(raw_guild) if raw_guild else None
        except ValueError as exc:
            raise RuntimeError("TEST_GUILD_ID precisa ser um ID numérico do Discord.") from exc
        if guild_id is not None and guild_id <= 0:
            raise RuntimeError("TEST_GUILD_ID precisa ser maior que zero.")

        raw_path = os.getenv("DATABASE_PATH", "data/bot.sqlite3").strip()
        if not raw_path:
            raise RuntimeError("DATABASE_PATH não pode estar vazio.")
        database_path = Path(raw_path)
        if not database_path.is_absolute():
            database_path = PROJECT_ROOT / database_path

        return cls(
            token,
            database_path.resolve(),
            guild_id,
            load_bot_preferences(config_path),
        )
