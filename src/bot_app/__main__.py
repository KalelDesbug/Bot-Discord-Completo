import asyncio

from dotenv import load_dotenv

from src.bot_app.bot import CommunityBot
from src.bot_app.config import Settings


async def run() -> None:
    load_dotenv()
    settings = Settings.from_environment()
    async with CommunityBot(settings) as bot:
        await bot.start(settings.discord_token)


def main() -> None:
    asyncio.run(run())


if __name__ == "__main__":
    main()
