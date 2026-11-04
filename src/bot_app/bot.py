import logging

import discord
from discord import app_commands
from discord.ext import commands

from src.bot_app.config import Settings
from src.bot_app.core.database import Database
from src.bot_app.features.tickets.repository import TicketRepository
from src.bot_app.features.welcome.repository import WelcomeRepository

logger = logging.getLogger(__name__)


class CommunityBot(commands.Bot):
    def __init__(self, settings: Settings) -> None:
        intents = discord.Intents.default()
        intents.members = True
        super().__init__(command_prefix="!", intents=intents, help_command=None)
        self.settings = settings
        self.database = Database(settings.database_path)
        self.tickets = TicketRepository(self.database)
        self.welcome_settings = WelcomeRepository(self.database)

    async def setup_hook(self) -> None:
        await self.database.open()

        extensions = (
            "src.bot_app.features.welcome.cog",
            "src.bot_app.features.tickets.cog",
            "src.bot_app.features.moderation.cog",
            "src.bot_app.features.utility.cog",
        )
        for extension in extensions:
            await self.load_extension(extension)

        tickets_cog = self.get_cog("Tickets")
        if tickets_cog is not None:
            self.add_view(tickets_cog.panel_view_class())
            self.add_view(tickets_cog.controls_view_class())

        if self.settings.test_guild_id:
            guild = discord.Object(id=self.settings.test_guild_id)
            self.tree.copy_global_to(guild=guild)
            await self.tree.sync(guild=guild)
            logger.info("Slash commands sincronizados na guild %s", guild.id)
        else:
            await self.tree.sync()
            logger.info("Slash commands globais sincronizados")

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
                "Erro em slash command %s",
                interaction.command.name if interaction.command else "desconhecido",
                exc_info=(type(error), error, error.__traceback__),
            )
            message = "Ocorreu um erro ao executar o comando. Tente novamente mais tarde."

        try:
            if interaction.response.is_done():
                await interaction.followup.send(message, ephemeral=True)
            else:
                await interaction.response.send_message(message, ephemeral=True)
        except discord.HTTPException:
            logger.warning("Não foi possível responder à interação com erro.")

    async def close(self) -> None:
        await self.database.close()
        await super().close()
