import asyncio
from pathlib import Path

import aiosqlite


class Database:
    def __init__(self, path: Path) -> None:
        self.path = path
        self.connection: aiosqlite.Connection | None = None
        self.write_lock = asyncio.Lock()

    async def open(self) -> None:
        if self.connection is not None:
            return
        self.path.parent.mkdir(parents=True, exist_ok=True)
        connection = await aiosqlite.connect(self.path)
        try:
            connection.row_factory = aiosqlite.Row
            await connection.execute("PRAGMA foreign_keys = ON")
            await connection.execute("PRAGMA busy_timeout = 5000")
            await connection.execute("PRAGMA journal_mode = WAL")
            await connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS guild_settings (
                    guild_id INTEGER PRIMARY KEY,
                    welcome_channel_id INTEGER,
                    welcome_message TEXT NOT NULL DEFAULT 'Boas-vindas, {member}!',
                    ticket_category_id INTEGER,
                    support_role_id INTEGER,
                    log_channel_id INTEGER
                );
                CREATE TABLE IF NOT EXISTS tickets (
                    channel_id INTEGER PRIMARY KEY,
                    guild_id INTEGER NOT NULL,
                    owner_id INTEGER NOT NULL,
                    status TEXT NOT NULL DEFAULT 'open',
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    closed_at TEXT
                );
                CREATE UNIQUE INDEX IF NOT EXISTS one_open_ticket_per_user
                ON tickets(guild_id, owner_id) WHERE status = 'open';
                """
            )
            async with connection.execute("PRAGMA table_info(guild_settings)") as cursor:
                columns = {row["name"] for row in await cursor.fetchall()}
            if "log_channel_id" not in columns:
                await connection.execute(
                    "ALTER TABLE guild_settings ADD COLUMN log_channel_id INTEGER"
                )
            await connection.commit()
        except Exception:
            await connection.close()
            raise
        self.connection = connection

    def require_connection(self) -> aiosqlite.Connection:
        if self.connection is None:
            raise RuntimeError("Banco de dados ainda não foi inicializado.")
        return self.connection

    async def close(self) -> None:
        if self.connection is not None:
            await self.connection.close()
            self.connection = None
