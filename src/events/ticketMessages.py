from __future__ import annotations

import logging

import discord
from discord.ext import commands

from src.helpers.tickets.transcript import message_record


logger = logging.getLogger("discord.ticket_messages")


class TicketMessageEvents(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    def _is_ticket_message(self, message: discord.Message) -> bool:
        active_channels = getattr(self.bot, "active_ticket_channels", set())
        return message.guild is not None and message.channel.id in active_channels

    async def _save(self, message: discord.Message) -> None:
        if not self._is_ticket_message(message):
            return
        try:
            await self.bot.db.save_ticket_messages([message_record(message)])
        except Exception:
            logger.exception(
                "Falha ao salvar mensagem %s do ticket %s.",
                message.id,
                message.channel.id,
            )

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message) -> None:
        await self._save(message)

    @commands.Cog.listener()
    async def on_message_edit(
        self, before: discord.Message, after: discord.Message
    ) -> None:
        await self._save(after)

    @commands.Cog.listener()
    async def on_message_delete(self, message: discord.Message) -> None:
        if not self._is_ticket_message(message):
            return
        try:
            await self.bot.db.delete_ticket_messages(
                message.channel.id,
                [message.id],
            )
        except Exception:
            logger.exception(
                "Falha ao remover mensagem apagada %s do ticket %s.",
                message.id,
                message.channel.id,
            )

    @commands.Cog.listener()
    async def on_bulk_message_delete(self, messages: list[discord.Message]) -> None:
        if not messages:
            return
        channel = messages[0].channel
        if channel.id not in getattr(self.bot, "active_ticket_channels", set()):
            return
        try:
            await self.bot.db.delete_ticket_messages(
                channel.id,
                [message.id for message in messages],
            )
        except Exception:
            logger.exception(
                "Falha ao remover mensagens em lote do ticket %s.",
                channel.id,
            )


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(TicketMessageEvents(bot))
