from src.bot_app.core.database import Database


class WelcomeRepository:
    _columns = {"welcome_channel_id", "welcome_message"}

    def __init__(self, database: Database) -> None:
        self.database = database

    async def get(self, guild_id: int) -> dict:
        connection = self.database.require_connection()
        async with connection.execute(
            "SELECT welcome_channel_id, welcome_message FROM guild_settings WHERE guild_id = ?",
            (guild_id,),
        ) as cursor:
            row = await cursor.fetchone()
        return dict(row) if row else {}

    async def set(self, guild_id: int, key: str, value: int | str) -> None:
        if key not in self._columns:
            raise ValueError("Configuração de boas-vindas inválida.")

        async with self.database.transaction() as connection:
            await connection.execute(
                f"""
                INSERT INTO guild_settings (guild_id, {key}) VALUES (?, ?)
                ON CONFLICT(guild_id) DO UPDATE SET {key} = excluded.{key}
                """,
                (guild_id, value),
            )

    async def set_welcome(
        self, guild_id: int, channel_id: int, message: str
    ) -> None:
        async with self.database.transaction() as connection:
            await connection.execute(
                """INSERT INTO guild_settings
                       (guild_id, welcome_channel_id, welcome_message)
                   VALUES (?, ?, ?)
                   ON CONFLICT(guild_id) DO UPDATE SET
                       welcome_channel_id = excluded.welcome_channel_id,
                       welcome_message = excluded.welcome_message""",
                (guild_id, channel_id, message),
            )
