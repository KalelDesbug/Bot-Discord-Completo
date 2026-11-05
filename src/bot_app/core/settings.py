from src.bot_app.core.database import Database


class GuildSettingsRepository:
    def __init__(self, database: Database) -> None:
        self.database = database

    async def get_log_channel(self, guild_id: int) -> int | None:
        connection = self.database.require_connection()
        async with connection.execute(
            "SELECT log_channel_id FROM guild_settings WHERE guild_id = ?",
            (guild_id,),
        ) as cursor:
            row = await cursor.fetchone()
        return row["log_channel_id"] if row else None

    async def set_log_channel(self, guild_id: int, channel_id: int | None) -> None:
        connection = self.database.require_connection()
        async with self.database.write_lock:
            await connection.execute(
                """INSERT INTO guild_settings (guild_id, log_channel_id) VALUES (?, ?)
                   ON CONFLICT(guild_id) DO UPDATE SET log_channel_id = excluded.log_channel_id""",
                (guild_id, channel_id),
            )
            await connection.commit()
