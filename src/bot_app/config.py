import os
from dataclasses import dataclass
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]


@dataclass(frozen=True, slots=True)
class Settings:
    discord_token: str
    database_path: Path
    test_guild_id: int | None = None

    @classmethod
    def from_environment(cls) -> "Settings":
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
        return cls(token, database_path.resolve(), guild_id)
