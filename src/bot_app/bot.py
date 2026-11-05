import logging
import subprocess
import sys
from pathlib import Path
from typing import TYPE_CHECKING

if __package__ in (None, ""):
    project_root = Path(__file__).resolve().parents[2]
    venv_python = project_root / ".venv" / "Scripts" / "python.exe"
    if venv_python.is_file() and Path(sys.executable).resolve() != venv_python.resolve():
        result = subprocess.run(
            [str(venv_python), str(Path(__file__).resolve()), *sys.argv[1:]],
            cwd=project_root,
            check=False,
        )
        raise SystemExit(result.returncode)

    project_root_string = str(project_root)
    if project_root_string not in sys.path:
        sys.path.insert(0, project_root_string)

    from src.bot_app.__main__ import main

    main()
    raise SystemExit(0)

import discord
from discord import app_commands
from discord.ext import commands

from src.bot_app.core.components import TextLayout
from src.bot_app.core.database import Database
from src.bot_app.core.settings import GuildSettingsRepository
from src.bot_app.features.tickets.repository import TicketRepository
from src.bot_app.features.welcome.repository import WelcomeRepository

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
        self.tickets = TicketRepository(self.database)
        self.welcome_settings = WelcomeRepository(self.database)

    async def setup_hook(self) -> None:
        await self.database.open()
        for extension in (
            "src.bot_app.features.welcome.cog",
            "src.bot_app.features.tickets.cog",
            "src.bot_app.features.moderation.cog",
            "src.bot_app.features.utility.cog",
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
                await interaction.followup.send(
                    view=TextLayout(message),
                    ephemeral=True,
                    allowed_mentions=discord.AllowedMentions.none(),
                )
            else:
                await interaction.response.send_message(
                    view=TextLayout(message),
                    ephemeral=True,
                    allowed_mentions=discord.AllowedMentions.none(),
                )
        except discord.HTTPException:
            logger.warning("Não foi possível responder à interação com erro.")

    async def close(self) -> None:
        await self.database.close()
        await super().close()
