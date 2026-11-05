import asyncio
import logging

from dotenv import load_dotenv

from src.bot_app.bot import CommunityBot
from src.bot_app.config import PROJECT_ROOT, Settings


async def run() -> None:
    load_dotenv(PROJECT_ROOT / ".env")
    settings = Settings.from_environment()
    async with CommunityBot(settings) as bot:
        await bot.start(settings.discord_token)


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    asyncio.run(run())


if __name__ == "__main__":
    main()
