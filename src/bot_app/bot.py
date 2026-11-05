import logging
from typing import TYPE_CHECKING

import discord
from discord import app_commands
from discord.ext import commands

from src.bot_app.core.components import TextLayout
from src.bot_app.core.database import Database
from src.bot_app.core.settings import GuildSettingsRepository

if TYPE_CHECKING:
    from src.bot_app.config import Settings

logger = logging.getLogger(__name__)


class CommunityBot(commands.Bot):
    def __init__(self, settings: "Settings") -> None:
        intents = discord.Intents.default()
        intents.members = True
        super().__init__(command_prefix=commands.when_mentioned, intents=intents)
        self.settings = settings
        self.database = Database(settings.database_path)
        self.guild_settings = GuildSettingsRepository(self.database)
        self.tickets = None
        self.welcome_settings = None

    async def setup_hook(self) -> None:
        await self.database.open()
        for extension in (
            "src.bot_app.features.welcome.cog",
            "src.bot_app.features.tickets.cog",
            "src.bot_app.features.moderation.cog",
            "src.bot_app.features.utility.cog",
            "src.bot_app.features.logs.cog",
        ):
            await self.load_extension(extension)

        tickets = self.get_cog("Tickets")
        if tickets is not None:
            self.add_view(tickets.panel_view_class())
            self.add_view(tickets.controls_view_class())

        if self.settings.test_guild_id:
            guild = discord.Object(id=self.settings.test_guild_id)
            self.tree.copy_global_to(guild=guild)
            await self.tree.sync(guild=guild)
        else:
            await self.tree.sync()

    async def log_event(self, guild_id: int, text: str) -> None:
        channel_id = await self.guild_settings.get_log_channel(guild_id)
        if channel_id is None:
            return
        channel = self.get_channel(channel_id)
        if not isinstance(channel, discord.TextChannel):
            logger.warning("Canal de logs %s indisponível na guild %s", channel_id, guild_id)
            return
        try:
            await channel.send(
                view=TextLayout(text),
                allowed_mentions=discord.AllowedMentions.none(),
            )
        except discord.HTTPException:
            logger.exception("Falha ao enviar log para o canal %s", channel_id)

    async def on_app_command_error(
        self,
        interaction: discord.Interaction,
        error: app_commands.AppCommandError,
    ) -> None:
        if isinstance(error, app_commands.MissingPermissions):
            message = "Você não tem permissão para usar este comando."
        elif isinstance(error, app_commands.BotMissingPermissions):
            message = "Está faltando uma permissão necessária para o bot executar isso."
        else:
            logger.error(
                "Erro no comando %s",
                interaction.command.name if interaction.command else "desconhecido",
                exc_info=(type(error), error, error.__traceback__),
            )
            message = "Ocorreu um erro ao executar o comando."
        try:
            if interaction.response.is_done():
                await interaction.followup.send(view=TextLayout(message), ephemeral=True)
            else:
                await interaction.response.send_message(view=TextLayout(message), ephemeral=True)
        except discord.HTTPException:
            logger.warning("Não foi possível responder à interação com erro.")

    async def close(self) -> None:
        await self.database.close()
        await super().close()
