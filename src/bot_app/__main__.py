import asyncio

from dotenv import load_dotenv

from src.bot_app.bot import CommunityBot
from src.bot_app.config import PROJECT_ROOT, Settings
from src.bot_app.logging import configure_logging, get_logger

logger = get_logger(__name__)


async def _restart_after_interval(bot: CommunityBot, interval_hours: int) -> None:
    await asyncio.sleep(interval_hours * 60 * 60)
    logger.info("Intervalo de %d hora(s) atingido; reiniciando a sessão do bot.", interval_hours)
    await bot.close()


async def run() -> None:
    load_dotenv(PROJECT_ROOT / ".env")
    settings = Settings.from_environment()
    preferences = settings.preferences

    while True:
        try:
            async with CommunityBot(settings) as bot:
                restart_task = None
                if preferences.restart_enabled:
                    restart_task = asyncio.create_task(
                        _restart_after_interval(bot, preferences.restart_interval_hours)
                    )
                    logger.info(
                        "Reinício automático ativado: a cada %d hora(s).",
                        preferences.restart_interval_hours,
                    )
                else:
                    logger.info("Reinício automático por horário desativado na config-bot.json.")

                try:
                    await bot.start(settings.discord_token)
                finally:
                    if restart_task is not None:
                        restart_task.cancel()
                        await asyncio.gather(restart_task, return_exceptions=True)
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception(
                "A sessão do bot terminou com erro; nova tentativa em %d segundos.",
                preferences.restart_retry_seconds,
            )
        else:
            logger.warning(
                "A sessão do bot terminou; iniciando novamente em %d segundos.",
                preferences.restart_retry_seconds,
            )
        await asyncio.sleep(preferences.restart_retry_seconds)


def main() -> None:
    configure_logging()
    asyncio.run(run())


if __name__ == "__main__":
    main()
