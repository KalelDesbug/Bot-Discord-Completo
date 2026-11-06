from __future__ import annotations

import logging

from src.config.bot import COMMAND_EXTENSIONS


async def load_command_extensions(bot) -> None:
    logger = logging.getLogger("discord.commands.loader")
    for extension in COMMAND_EXTENSIONS:
        await bot.load_extension(extension)
        logger.debug("Comando carregado: %s", extension)
