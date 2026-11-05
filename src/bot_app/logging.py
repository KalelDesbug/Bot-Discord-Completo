from __future__ import annotations

from enum import Enum
import logging as std_logging
from typing import Protocol

import discord


class LogLevel(Enum):
    STARTUP = ("⚪", discord.Colour.from_rgb(255, 255, 255))
    INFO = ("🔵", discord.Colour.blue())
    SUCCESS = ("🟢", discord.Colour.green())
    WARNING = ("🟡", discord.Colour.gold())
    ERROR = ("🔴", discord.Colour.red())
    RESTART = ("🟣", discord.Colour.purple())

    @property
    def icon(self) -> str:
        return self.value[0]

    @property
    def colour(self) -> discord.Colour:
        return self.value[1]


class GuildSettingsReader(Protocol):
    async def get_log_channel(self, guild_id: int) -> int | None: ...


def get_logger(name: str) -> std_logging.Logger:
    return std_logging.getLogger(name)


def configure_logging(level: str = "INFO") -> None:
    std_logging.basicConfig(
        level=getattr(std_logging, level.upper()),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )


def build_log_embed(
    title: str,
    message: str,
    level: LogLevel = LogLevel.INFO,
) -> discord.Embed:
    safe_title = (title.strip() or "Registro do bot")[:250]
    safe_message = (message.strip() or "Sem detalhes adicionais.")[:3500]
    return discord.Embed(
        title=f"{level.icon} {safe_title}"[:256],
        description=safe_message,
        colour=level.colour,
        timestamp=discord.utils.utcnow(),
    )


def friendly_error(error: BaseException) -> str:
    if isinstance(error, discord.Forbidden):
        return "O Discord recusou a ação por falta de permissão. Confira as permissões e os cargos do bot."
    if isinstance(error, discord.NotFound):
        return "O item solicitado não existe mais ou foi removido."
    if isinstance(error, discord.HTTPException):
        return "O Discord não conseguiu concluir a solicitação. Aguarde um pouco e tente novamente."
    return "Ocorreu uma falha inesperada. Tente novamente; os detalhes técnicos foram registrados no console do bot."


async def send_guild_log(
    client: discord.Client,
    settings: GuildSettingsReader,
    guild_id: int,
    message: str,
    *,
    title: str = "Registro do bot",
    level: LogLevel = LogLevel.INFO,
) -> None:
    """Tenta enviar um log ao Discord sem propagar falhas para a aplicação."""
    logger = get_logger(__name__)
    try:
        channel_id = await settings.get_log_channel(guild_id)
        if channel_id is None:
            return
        channel = client.get_channel(channel_id)
        if channel is None:
            channel = await client.fetch_channel(channel_id)
        if not isinstance(channel, discord.TextChannel):
            logger.warning("Canal de logs %s inválido no servidor %s.", channel_id, guild_id)
            return
        await channel.send(
            embed=build_log_embed(title, message, level),
            allowed_mentions=discord.AllowedMentions.none(),
        )
    except discord.NotFound:
        logger.warning("Canal de logs não encontrado no servidor %s.", guild_id)
    except discord.Forbidden:
        logger.warning("Sem permissão para enviar logs no servidor %s.", guild_id)
    except Exception:
        logger.exception("Falha interna ao enviar log para o servidor %s.", guild_id)
