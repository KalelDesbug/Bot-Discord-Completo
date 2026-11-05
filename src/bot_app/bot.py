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
from src.bot_app.features.logs.service import LogLevel, build_log_embed, friendly_error
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
        self._startup_logged = False

    async def setup_hook(self) -> None:
        await self.database.open()
        for extension in (
            "src.bot_app.features.welcome.cog",
            "src.bot_app.features.tickets.cog",
            "src.bot_app.features.logs.cog",
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

    async def on_ready(self) -> None:
        if self._startup_logged:
            return
        self._startup_logged = True
        for guild in self.guilds:
            await self.log_event(
                guild.id,
                f"O bot está online e pronto para uso no servidor **{guild.name[:100]}**.",
                title="Bot ligado",
                level=LogLevel.STARTUP,
            )
        logger.info("Bot conectado como %s; conectado a %d servidor(es).", self.user, len(self.guilds))

    async def log_event(
        self,
        guild_id: int,
        text: str,
        *,
        title: str = "Registro do bot",
        level: LogLevel = LogLevel.INFO,
    ) -> None:
        """Best-effort log delivery: log failures never interrupt bot features."""
        try:
            channel_id = await self.guild_settings.get_log_channel(guild_id)
            if channel_id is None:
                return
            channel = self.get_channel(channel_id)
            if channel is None:
                channel = await self.fetch_channel(channel_id)
            if not isinstance(channel, discord.TextChannel):
                logger.warning("Canal de logs %s inválido no servidor %s.", channel_id, guild_id)
                return
            await channel.send(
                embed=build_log_embed(title, text, level),
                allowed_mentions=discord.AllowedMentions.none(),
            )
        except discord.NotFound:
            logger.warning("Canal de logs não encontrado no servidor %s.", guild_id)
        except discord.Forbidden:
            logger.warning("Sem permissão para enviar logs no servidor %s.", guild_id)
        except Exception:
            logger.exception("Falha interna ao enviar log para o servidor %s.", guild_id)

    async def on_app_command_error(
        self,
        interaction: discord.Interaction,
        error: app_commands.AppCommandError,
    ) -> None:
        if isinstance(error, app_commands.MissingPermissions):
            message = "Você não tem permissão para usar este comando."
        elif isinstance(error, app_commands.BotMissingPermissions):
            message = "Está faltando uma permissão necessária para o bot executar isso."
        elif isinstance(error, app_commands.CommandOnCooldown):
            message = "Este comando foi usado muitas vezes. Aguarde um pouco e tente novamente."
        else:
            message = friendly_error(getattr(error, "original", error))
            logger.error(
                "Erro no comando %s: %s",
                interaction.command.name if interaction.command else "desconhecido",
                type(getattr(error, "original", error)).__name__,
                exc_info=(type(error), error, error.__traceback__),
            )
            if interaction.guild_id is not None:
                command_name = interaction.command.name if interaction.command else "desconhecido"
                await self.log_event(
                    interaction.guild_id,
                    f"Comando: `/{command_name}`\nResumo: {message}",
                    title="Falha em comando",
                    level=LogLevel.ERROR,
                )

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
        except Exception:
            logger.exception("Falha ao tratar erro de comando.")

    async def on_error(self, event_method: str, *args: object, **kwargs: object) -> None:
        logger.exception("Erro não tratado no evento Discord %s.", event_method)
        if not args:
            return
        guild = getattr(args[0], "guild", None)
        guild_id = getattr(guild, "id", None)
        if isinstance(guild_id, int):
            await self.log_event(
                guild_id,
                f"O evento `{event_method}` encontrou uma falha inesperada. O bot continua ativo; consulte o log técnico para detalhes.",
                title="Falha em evento",
                level=LogLevel.ERROR,
            )

    async def close(self) -> None:
        if self.is_ready():
            for guild in self.guilds:
                await self.log_event(
                    guild.id,
                    "O bot está encerrando esta sessão. Ele será iniciado novamente em seguida.",
                    title="Bot reiniciando",
                    level=LogLevel.RESTART,
                )
        await self.database.close()
        await super().close()
