import asyncio

import aiosqlite
import pytest

from src.bot_app.core.database import Database
from src.bot_app.core.settings import GuildSettingsRepository
from src.bot_app.features.tickets.repository import TicketRepository
from src.bot_app.features.welcome.repository import WelcomeRepository


def test_transaction_rolls_back_on_error(tmp_path) -> None:
    async def run() -> None:
        database = Database(tmp_path / "bot.sqlite3")
        await database.open()
        try:
            with pytest.raises(ValueError):
                async with database.transaction() as connection:
                    await connection.execute(
                        "INSERT INTO guild_settings (guild_id) VALUES (?)", (123,)
                    )
                    raise ValueError("rollback")

            async with database.require_connection().execute(
                "SELECT guild_id FROM guild_settings WHERE guild_id = ?", (123,)
            ) as cursor:
                assert await cursor.fetchone() is None
        finally:
            await database.close()

    asyncio.run(run())


def test_concurrent_repository_writes_are_serialized(tmp_path) -> None:
    async def run() -> None:
        database = Database(tmp_path / "bot.sqlite3")
        await database.open()
        welcome = WelcomeRepository(database)
        tickets = TicketRepository(database)
        settings = GuildSettingsRepository(database)
        try:
            await asyncio.gather(
                *(
                    welcome.set_welcome(guild_id, guild_id + 100, f"Bem-vindo {guild_id}")
                    for guild_id in range(1, 21)
                ),
                *(
                    tickets.set_settings(guild_id, guild_id + 200, guild_id + 300)
                    for guild_id in range(21, 41)
                ),
                *(
                    settings.set_log_channel(guild_id, guild_id + 400)
                    for guild_id in range(41, 61)
                ),
            )
            for guild_id in range(1, 21):
                saved = await welcome.get(guild_id)
                assert saved == {
                    "welcome_channel_id": guild_id + 100,
                    "welcome_message": f"Bem-vindo {guild_id}",
                }
            for guild_id in range(21, 41):
                saved = await tickets.get_settings(guild_id)
                assert saved == {
                    "ticket_category_id": guild_id + 200,
                    "support_role_id": guild_id + 300,
                }
            for guild_id in range(41, 61):
                assert await settings.get_log_channel(guild_id) == guild_id + 400
        finally:
            await database.close()

    asyncio.run(run())


def test_welcome_update_preserves_other_guild_settings(tmp_path) -> None:
    async def run() -> None:
        database = Database(tmp_path / "bot.sqlite3")
        await database.open()
        welcome = WelcomeRepository(database)
        tickets = TicketRepository(database)
        try:
            await tickets.set_settings(123, 456, 789)
            await welcome.set_welcome(123, 321, "Olá, {member}!")
            assert await tickets.get_settings(123) == {
                "ticket_category_id": 456,
                "support_role_id": 789,
            }
            assert await welcome.get(123) == {
                "welcome_channel_id": 321,
                "welcome_message": "Olá, {member}!",
            }
        finally:
            await database.close()

    asyncio.run(run())


def test_open_migrates_database_without_log_channel(tmp_path) -> None:
    async def run() -> None:
        path = tmp_path / "legacy.sqlite3"
        async with aiosqlite.connect(path) as connection:
            await connection.execute(
                """CREATE TABLE guild_settings (
                       guild_id INTEGER PRIMARY KEY,
                       welcome_channel_id INTEGER,
                       welcome_message TEXT NOT NULL DEFAULT 'Boas-vindas, {member}!',
                       ticket_category_id INTEGER,
                       support_role_id INTEGER
                   )"""
            )
            await connection.commit()

        database = Database(path)
        await database.open()
        try:
            async with database.require_connection().execute(
                "PRAGMA table_info(guild_settings)"
            ) as cursor:
                columns = {row["name"] for row in await cursor.fetchall()}
            assert "log_channel_id" in columns
        finally:
            await database.close()

    asyncio.run(run())
