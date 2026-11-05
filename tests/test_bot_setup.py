import asyncio
from unittest.mock import AsyncMock

from src.bot_app.bot import CommunityBot
from src.bot_app.config import Settings
from src.bot_app.features.tickets.repository import TicketRepository
from src.bot_app.features.welcome.repository import WelcomeRepository


def test_setup_initializes_repositories_and_extensions(
    tmp_path, monkeypatch
) -> None:
    async def setup_bot() -> None:
        bot = CommunityBot(Settings("test-token", tmp_path / "bot.sqlite3"))
        monkeypatch.setattr(bot.tree, "sync", AsyncMock())
        try:
            await bot.setup_hook()
            assert isinstance(bot.tickets, TicketRepository)
            assert isinstance(bot.welcome_settings, WelcomeRepository)
            assert bot.get_cog("Tickets") is not None
            assert bot.get_cog("Welcome") is not None
            assert bot.get_cog("Moderation") is not None
            assert bot.get_cog("Utility") is not None
            assert {
                command.name for command in bot.tree.get_commands()
            } == {
                "avatar",
                "ban",
                "bola8",
                "configurar_boas_vindas",
                "configurar_tickets",
                "kick",
                "moeda",
                "ping",
                "publicar_painel_tickets",
                "timeout",
                "userinfo",
            }
            assert len(bot.persistent_views) == 2
            assert all(view.has_components_v2() for view in bot.persistent_views)
        finally:
            await bot.close()

    asyncio.run(setup_bot())
