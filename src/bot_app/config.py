import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class Settings:
    discord_token: str
    database_path: Path
    test_guild_id: int | None = None

    @classmethod
    def from_environment(cls) -> "Settings":
        token = os.getenv("DISCORD_TOKEN", "").strip()
        if not token:
            raise RuntimeError("DISCORD_TOKEN não foi definido no arquivo .env ou ambiente.")

        raw_guild_id = os.getenv("TEST_GUILD_ID", "").strip()
        try:
            guild_id = int(raw_guild_id) if raw_guild_id else None
        except ValueError as error:
            raise RuntimeError("TEST_GUILD_ID precisa ser um ID numérico do Discord.") from error

        raw_database_path = os.getenv("DATABASE_PATH", "data/bot.sqlite3").strip()
        if not raw_database_path:
            raise RuntimeError("DATABASE_PATH não pode estar vazio.")

        return cls(
            discord_token=token,
            database_path=Path(raw_database_path),
            test_guild_id=guild_id,
        )
