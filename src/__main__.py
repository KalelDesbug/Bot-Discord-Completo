from __future__ import annotations

import asyncio
import logging

from src.client.client import DiscordBot
from src.config.env import PROJECT_ROOT, Settings
from src.utils.logging_config import configure_logging


async def run() -> None:
    settings = Settings.from_environment()
    bot = DiscordBot(settings)
    try:
        await bot.start(settings.discord_token)
    finally:
        await bot.close()


def main() -> None:
    configure_logging(PROJECT_ROOT)
    try:
        asyncio.run(run())
    except KeyboardInterrupt:
        logging.getLogger("discord.bot").info("Encerramento solicitado pelo usuário.")
    except Exception:
        logging.getLogger("discord.bot").exception("Falha fatal durante a inicialização ou execução.")
        raise


if __name__ == "__main__":
    main()
