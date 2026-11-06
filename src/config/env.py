from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parents[2]
load_dotenv(PROJECT_ROOT / ".env", override=False)


def _optional_int(name: str) -> int | None:
    raw = os.getenv(name, "").strip()
    if not raw:
        return None
    try:
        value = int(raw)
    except ValueError as exc:
        raise ValueError(f"{name} precisa ser um número inteiro.") from exc
    if value <= 0:
        raise ValueError(f"{name} precisa ser maior que zero.")
    return value


def _database_path() -> Path:
    raw = os.getenv("DATABASE_PATH", "data/community_bot.sqlite3").strip()
    if not raw:
        raw = "data/community_bot.sqlite3"
    path = Path(raw).expanduser()
    return (PROJECT_ROOT / path).resolve() if not path.is_absolute() else path.resolve()


@dataclass(frozen=True, slots=True)
class Settings:
    discord_token: str
    database_path: Path
    guild_id: int | None
    ticket_category_id: int | None

    @classmethod
    def from_environment(cls) -> "Settings":
        token = os.getenv("DISCORD_TOKEN", "").strip()
        if not token:
            raise ValueError("DISCORD_TOKEN não foi configurado no arquivo .env.")
        return cls(
            discord_token=token,
            database_path=_database_path(),
            guild_id=_optional_int("GUILD_ID"),
            ticket_category_id=_optional_int("TICKET_CATEGORY_ID"),
        )
