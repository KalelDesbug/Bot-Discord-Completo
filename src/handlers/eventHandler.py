from __future__ import annotations

import logging

from src.config.bot import EVENT_EXTENSIONS


async def load_event_extensions(bot) -> None:
    logger = logging.getLogger("discord.events")
    for extension in EVENT_EXTENSIONS:
        await bot.load_extension(extension)
        logger.debug("Evento carregado: %s", extension)
