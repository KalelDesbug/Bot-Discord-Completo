from __future__ import annotations

from datetime import datetime, timezone
import discord

from src.utils.functions import build_notice, send_ticket_log
from src.helpers.tickets.ticket_core import get_config, _ticket_doc, _require_staff, finalize_ticket_closure, _dm_transcript, _refresh_ticket_message
from src.components.buttons.ticket_actions import StaffPanelView
from src.helpers.tickets.transcript import generate_transcript_artifact


async def action_close(interaction: discord.Interaction):
    guild = interaction.guild
    ticket = await _ticket_doc(interaction)

    if not ticket:
        await interaction.response.send_message(view=build_notice("❌ Ticket não encontrado.", discord.Colour.red()), ephemeral=True)
        return

    if ticket["status"] == "fechado":
        await interaction.response.send_message(view=build_notice("❌ Este ticket já está fechado.", discord.Colour.red()), ephemeral=True)
        return

    if interaction.user.id == ticket["owner_id"]:
        await interaction.response.send_message(view=build_notice("❌ Quem abriu o ticket não pode fechá-lo.", discord.Colour.red()), ephemeral=True)
        return

    config = await get_config(interaction.client, guild.id)
    if not await _require_staff(interaction, config):
        return

    await interaction.response.defer()
    channel = interaction.channel
    # Gere o transcript antes de marcar o registro como fechado. Se a leitura do
    # histórico falhar, o ticket permanece aberto e pode ser fechado novamente.
    artifact = await generate_transcript_artifact(
        channel,
        interaction.client.db,
        output_format="txt",
    )
    try:
        now = await finalize_ticket_closure(interaction.client, guild, ticket, config)
        recipients = {ticket["owner_id"], *ticket.get("added_members", [])}
        for user_id in recipients:
            await _dm_transcript(
                interaction.client,
                guild,
                user_id,
                artifact,
                ticket["number"],
            )

        owner_mention = f"<@{ticket['owner_id']}>"
        claimed_mention = f"<@{ticket['claimed_by']}>" if ticket.get("claimed_by") else "ninguém"
        log_file = artifact.discord_file()
        try:
            await send_ticket_log(
                interaction.client, guild, config, "🔒 LOG DE TICKET — FECHADO",
                [
                    f"🎫 Ticket: #{ticket['number']:04d} — {channel.name}",
                    f"🏷️ Categoria: {ticket.get('category', '—')} · Painel: {ticket.get('panel', '—')}",
                    f"👤 Aberto por: {owner_mention}",
                    f"🙋 Atendido por: {claimed_mention}",
                    f"🛡️ Fechado por: {interaction.user.mention}",
                    f"🕐 Aberto em: {ticket['opened_at'][:16].replace('T', ' ')} UTC",
                ],
                footer=f"🕐 Fechado em: {now.strftime('%d/%m/%Y %H:%M')} UTC",
                file=log_file,
            )
        finally:
            log_file.close()

        call_channel_id = ticket.get("call_channel_id")
        call_channel = guild.get_channel(call_channel_id) if call_channel_id else None
        if call_channel is not None:
            try:
                await call_channel.delete(reason=f"Call do ticket #{ticket['number']:04d} encerrada")
            except discord.HTTPException:
                pass
        await channel.delete(reason=f"Ticket fechado por {interaction.user}")
        interaction.client.active_ticket_channels.discard(channel.id)
    finally:
        artifact.cleanup()


async def action_claim(interaction: discord.Interaction):
    guild = interaction.guild
    config = await get_config(interaction.client, guild.id)
    if not await _require_staff(interaction, config):
        return

    ticket = await _ticket_doc(interaction)
    if not ticket:
        await interaction.response.send_message(view=build_notice("❌ Ticket não encontrado.", discord.Colour.red()), ephemeral=True)
        return

    if ticket["status"] == "fechado":
        await interaction.response.send_message(view=build_notice("❌ Este ticket já está fechado.", discord.Colour.red()), ephemeral=True)
        return

    if ticket.get("claimed_by"):
        await interaction.response.send_message(view=build_notice("❌ Este ticket já foi assumido.", discord.Colour.red()), ephemeral=True)
        return

    await interaction.response.defer()
    await interaction.client.db.tickets.update_one(
        {"_id": ticket["_id"]}, {"$set": {"claimed_by": interaction.user.id, "atendimento": "Em Atendimento"}}
    )
    ticket["claimed_by"] = interaction.user.id
    ticket["atendimento"] = "Em Atendimento"
    await _refresh_ticket_message(interaction, ticket)

    await interaction.followup.send(view=build_notice(f"🙋 Ticket assumido por {interaction.user.mention}.", discord.Colour.green()), ephemeral=True)
    await send_ticket_log(
        interaction.client, guild, config, "🙋 LOG DE TICKET — ASSUMIDO",
        [
            f"🎫 Ticket: #{ticket['number']:04d} — {interaction.channel.name}",
            f"🏷️ Categoria: {ticket.get('category', '—')}",
            f"👤 Aberto por: <@{ticket['owner_id']}>",
            f"🛡️ Assumido por: {interaction.user.mention}",
        ],
        footer=f"🕐 Data: {datetime.now(timezone.utc).strftime('%d/%m/%Y %H:%M')} UTC",
    )


async def action_admin(interaction: discord.Interaction):
    config = await get_config(interaction.client, interaction.guild.id)
    if not await _require_staff(interaction, config):
        return
    ticket = await _ticket_doc(interaction)
    if not ticket:
        await interaction.response.send_message(
            view=build_notice("❌ Ticket não encontrado.", discord.Colour.red()),
            ephemeral=True,
        )
        return
    await interaction.response.send_message(
        view=StaffPanelView(ticket.get("accent_color")), ephemeral=True
    )


async def action_notify(interaction: discord.Interaction):
    config = await get_config(interaction.client, interaction.guild.id)
    if not await _require_staff(interaction, config):
        return

    ticket = await _ticket_doc(interaction)
    if not ticket:
        return

    owner = interaction.guild.get_member(ticket["owner_id"])
    mention = owner.mention if owner else f"<@{ticket['owner_id']}>"
    await interaction.response.send_message(view=build_notice(f"🔔 {mention}, você ainda está aí?", discord.Colour.gold()))
