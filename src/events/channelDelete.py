import discord
from discord.ext import commands
from src.utils.functions import send_ticket_log
from src.helpers.tickets.ticket import finalize_ticket_closure


class OnChannelDelete(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_guild_channel_delete(self, channel: discord.abc.GuildChannel):
        self.bot.active_ticket_channels.discard(channel.id)
        ticket = await self.bot.db.tickets.find_one({"_id": str(channel.id)})
        if not ticket or ticket["status"] == "fechado":
            return

        config = await self.bot.db.get_config(channel.guild.id)
        now = await finalize_ticket_closure(self.bot, channel.guild, ticket, config)
        call_channel_id = ticket.get("call_channel_id")
        call_channel = channel.guild.get_channel(call_channel_id) if call_channel_id else None
        if call_channel is not None:
            try:
                await call_channel.delete(reason=f"Call do ticket #{ticket['number']:04d} encerrada")
            except discord.HTTPException:
                pass
        claimed_mention = f"<@{ticket['claimed_by']}>" if ticket.get("claimed_by") else "ninguém"

        await send_ticket_log(
            self.bot, channel.guild, config, "🗑️ LOG DE TICKET — CANAL APAGADO",
            [
                f"🎫 Ticket: #{ticket['number']:04d} — {getattr(channel, 'name', channel.id)}",
                f"🏷️ Categoria: {ticket.get('category', '—')} · Painel: {ticket.get('panel', '—')}",
                f"👤 Aberto por: <@{ticket['owner_id']}>",
                f"🙋 Atendido por: {claimed_mention}",
                "🗑️ Canal apagado manualmente — marcado como fechado no sistema.",
            ],
            footer=f"🕐 Data: {now.strftime('%d/%m/%Y %H:%M')} UTC",
        )


async def setup(bot: commands.Bot):
    await bot.add_cog(OnChannelDelete(bot))
