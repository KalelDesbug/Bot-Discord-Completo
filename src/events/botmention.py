from __future__ import annotations

import discord
from discord.ext import commands


class BotMentionEvents(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message) -> None:
        if message.author.bot or self.bot.user is None:
            return
        if self.bot.user not in message.mentions:
            return
        if message.content.strip() not in {f"<@{self.bot.user.id}>", f"<@!{self.bot.user.id}>"}:
            return
        await message.reply(
            "Olá! Gerencio tickets e sorteios. Use `/ticket-config`, `/enviar-painel` "
            "ou `/giveaway setup`.",
            mention_author=False,
            allowed_mentions=discord.AllowedMentions.none(),
        )


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(BotMentionEvents(bot))
