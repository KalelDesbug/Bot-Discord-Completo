from __future__ import annotations

from datetime import datetime, timezone
import discord

from src.utils.functions import build_notice, SafeView, send_ticket_log, is_ticket_staff
from src.helpers.tickets.ticket_core import get_config, _ticket_doc, _require_staff


class MemberSelect(discord.ui.UserSelect):
    def __init__(self, mode: str):
        super().__init__(placeholder=f"Selecione o membro para {mode}")
        self.mode = mode

    async def callback(self, interaction: discord.Interaction):
        member = self.values[0]

        if self.mode == "adicionar":
            await interaction.channel.set_permissions(member, view_channel=True, send_messages=True, read_message_history=True)
            await interaction.client.db.tickets.update_one({"_id": str(interaction.channel.id)}, {"$addToSet": {"added_members": member.id}})
            msg = f"➕ {member.mention} adicionado ao ticket."
        elif self.mode == "remover":
            await interaction.channel.set_permissions(member, overwrite=None)
            await interaction.client.db.tickets.update_one({"_id": str(interaction.channel.id)}, {"$pull": {"added_members": member.id}})
            msg = f"➖ {member.mention} removido do ticket."
        else:
            config = await interaction.client.db.get_config(interaction.guild.id)
            if not is_ticket_staff(member, config):
                await interaction.response.send_message(
                    view=build_notice("❌ Só é possível transferir para alguém da equipe de tickets.", discord.Colour.red()),
                    ephemeral=True,
                )
                return
            await interaction.client.db.tickets.update_one(
                {"_id": str(interaction.channel.id)},
                {"$set": {"claimed_by": member.id, "atendimento": "Em Atendimento"}},
            )
            msg = f"🚩 Ticket transferido para {member.mention}."

        await interaction.response.edit_message(view=build_notice(msg, discord.Colour.green()))

        ticket = await interaction.client.db.tickets.find_one(
            {"_id": str(interaction.channel.id)}, {"number": 1, "owner_id": 1}
        )
        number = ticket["number"] if ticket else 0
        action = {"adicionar": "➕ Adicionado", "remover": "➖ Removido"}.get(self.mode, "🚩 Transferido para")
        lines = [
            f"🎫 Ticket: #{number:04d} — {interaction.channel.name}",
            f"{action}: {member.mention} ({member.id})",
            f"🛡️ Por: {interaction.user.mention}",
        ]
        if ticket:
            lines.insert(2, f"👤 Dono do ticket: <@{ticket['owner_id']}>")
        await send_ticket_log(
            interaction.client, interaction.guild, await interaction.client.db.get_config(interaction.guild.id),
            "🎫 LOG DE TICKET — MEMBROS", lines,
            footer=f"🕐 Data: {datetime.now(timezone.utc).strftime('%d/%m/%Y %H:%M')} UTC",
        )


class MemberSelectView(SafeView):
    def __init__(self, mode: str):
        super().__init__(timeout=60)
        self.add_item(MemberSelect(mode))


async def action_add(interaction: discord.Interaction):
    config = await get_config(interaction.client, interaction.guild.id)
    if not await _require_staff(interaction, config):
        return
    await interaction.response.send_message(view=MemberSelectView("adicionar"), ephemeral=True)


async def action_remove(interaction: discord.Interaction):
    config = await get_config(interaction.client, interaction.guild.id)
    if not await _require_staff(interaction, config):
        return
    await interaction.response.send_message(view=MemberSelectView("remover"), ephemeral=True)


async def action_transfer(interaction: discord.Interaction):
    config = await get_config(interaction.client, interaction.guild.id)
    if not await _require_staff(interaction, config):
        return
    await interaction.response.send_message(view=MemberSelectView("transferir"), ephemeral=True)


async def action_block(interaction: discord.Interaction):
    config = await get_config(interaction.client, interaction.guild.id)
    if not await _require_staff(interaction, config):
        return

    ticket = await _ticket_doc(interaction)
    if not ticket:
        return

    await interaction.response.defer()
    owner = interaction.guild.get_member(ticket["owner_id"])
    blocked = not ticket.get("blocked", False)

    if owner:
        await interaction.channel.set_permissions(owner, send_messages=not blocked)

    await interaction.client.db.tickets.update_one({"_id": ticket["_id"]}, {"$set": {"blocked": blocked}})

    text = "🔐 Usuário bloqueado." if blocked else "🔓 Usuário desbloqueado."
    await interaction.followup.send(view=build_notice(text, discord.Colour.orange() if blocked else discord.Colour.green()), ephemeral=True)

    await send_ticket_log(
        interaction.client, interaction.guild, config, "🔐 LOG DE TICKET — BLOQUEIO",
        [
            f"🎫 Ticket: #{ticket['number']:04d} — {interaction.channel.name}",
            f"👤 Dono: <@{ticket['owner_id']}>",
            f"{'🔐 Bloqueado' if blocked else '🔓 Desbloqueado'} por: {interaction.user.mention}",
        ],
        footer=f"🕐 Data: {datetime.now(timezone.utc).strftime('%d/%m/%Y %H:%M')} UTC",
    )
