from __future__ import annotations

import logging

from discord.ext import commands


class ReadyEvent(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self.logger = logging.getLogger("discord.ready")

    @commands.Cog.listener()
    async def on_ready(self) -> None:
        self.logger.info("Bot conectado como %s (%s)", self.bot.user, self.bot.user.id if self.bot.user else "-")


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(ReadyEvent(bot))
