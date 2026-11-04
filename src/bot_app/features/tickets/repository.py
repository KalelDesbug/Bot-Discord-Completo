import aiosqlite

from src.bot_app.core.database import Database


class TicketRepository:
    def __init__(self, database: Database) -> None:
        self.database = database

    async def get_settings(self, guild_id: int) -> dict:
        connection = self.database.require_connection()
        async with connection.execute(
            "SELECT ticket_category_id, support_role_id FROM guild_settings WHERE guild_id = ?",
            (guild_id,),
        ) as cursor:
            row = await cursor.fetchone()
        return dict(row) if row else {}

    async def set_settings(
        self, guild_id: int, category_id: int, support_role_id: int
    ) -> None:
        connection = self.database.require_connection()
        await connection.execute(
            """INSERT INTO guild_settings (guild_id, ticket_category_id, support_role_id)
               VALUES (?, ?, ?)
               ON CONFLICT(guild_id) DO UPDATE SET
                   ticket_category_id = excluded.ticket_category_id,
                   support_role_id = excluded.support_role_id""",
            (guild_id, category_id, support_role_id),
        )
        await connection.commit()

    async def get_open_for_owner(self, guild_id: int, owner_id: int) -> int | None:
        connection = self.database.require_connection()
        async with connection.execute(
            """SELECT channel_id FROM tickets
               WHERE guild_id = ? AND owner_id = ? AND status = 'open'""",
            (guild_id, owner_id),
        ) as cursor:
            row = await cursor.fetchone()
        return row["channel_id"] if row else None

    async def get_by_channel(self, channel_id: int) -> dict | None:
        connection = self.database.require_connection()
        async with connection.execute(
            "SELECT * FROM tickets WHERE channel_id = ?", (channel_id,)
        ) as cursor:
            row = await cursor.fetchone()
        return dict(row) if row else None

    async def create(self, channel_id: int, guild_id: int, owner_id: int) -> None:
        connection = self.database.require_connection()
        try:
            await connection.execute(
                "INSERT INTO tickets (channel_id, guild_id, owner_id) VALUES (?, ?, ?)",
                (channel_id, guild_id, owner_id),
            )
            await connection.commit()
        except aiosqlite.IntegrityError:
            await connection.rollback()
            raise

    async def close_ticket(self, channel_id: int) -> None:
        connection = self.database.require_connection()
        await connection.execute(
            """UPDATE tickets SET status = 'closed', closed_at = CURRENT_TIMESTAMP
               WHERE channel_id = ? AND status = 'open'""",
            (channel_id,),
        )
        await connection.commit()
