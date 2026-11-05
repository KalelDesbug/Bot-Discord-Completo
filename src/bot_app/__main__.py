import asyncio
import logging

from dotenv import load_dotenv

from src.bot_app.bot import CommunityBot
from src.bot_app.config import PROJECT_ROOT, Settings

logger = logging.getLogger(__name__)
RESTART_INTERVAL_SECONDS = 24 * 60 * 60
RESTART_RETRY_SECONDS = 10


async def _restart_after_interval(bot: CommunityBot) -> None:
    await asyncio.sleep(RESTART_INTERVAL_SECONDS)
    logger.info("Intervalo de 24 horas atingido; reiniciando a sessão do bot.")
    await bot.close()


async def run() -> None:
    load_dotenv(PROJECT_ROOT / ".env")
    settings = Settings.from_environment()

    while True:
        try:
            async with CommunityBot(settings) as bot:
                restart_task = asyncio.create_task(_restart_after_interval(bot))
                try:
                    await bot.start(settings.discord_token)
                finally:
                    restart_task.cancel()
                    await asyncio.gather(restart_task, return_exceptions=True)
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("A sessão do bot terminou com erro; nova tentativa em 10 segundos.")
        else:
            logger.warning("A sessão do bot terminou; reiniciando em 10 segundos.")
        await asyncio.sleep(RESTART_RETRY_SECONDS)


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    asyncio.run(run())


if __name__ == "__main__":
    main()
