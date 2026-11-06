from __future__ import annotations

import discord

from src.utils.functions import build_notice, build_container, send_ticket_log
from src.helpers.tickets.ticket_core import get_config, _ticket_doc, _require_staff
from src.helpers.tickets.transcript import generate_transcript_artifact


async def action_transcript(interaction: discord.Interaction):
    config = await get_config(interaction.client, interaction.guild.id)
    if not await _require_staff(interaction, config):
        return

    await interaction.response.defer(ephemeral=True, thinking=True)
    artifact = await generate_transcript_artifact(
        interaction.channel,
        interaction.client.db,
        output_format="html",
    )
    try:
        file = artifact.discord_file()
        try:
            await interaction.followup.send(
                view=build_notice("📧 Transcript gerado.", discord.Colour.blurple(), file=file),
                file=file,
                ephemeral=True,
            )
        finally:
            file.close()

        log_file = artifact.discord_file()
        try:
            await send_ticket_log(
                interaction.client,
                interaction.guild,
                config,
                "📧 TRANSCRIPT DE TICKET",
                [f"Canal: {interaction.channel.mention}", f"Solicitado por: {interaction.user.mention}"],
                file=log_file,
            )
        finally:
            log_file.close()
    finally:
        artifact.cleanup()


async def action_history(interaction: discord.Interaction):
    config = await get_config(interaction.client, interaction.guild.id)
    if not await _require_staff(interaction, config):
        return

    ticket = await _ticket_doc(interaction)
    if not ticket:
        await interaction.response.send_message(view=build_notice("❌ Ticket não encontrado.", discord.Colour.red()), ephemeral=True)
        return

    cursor = interaction.client.db.tickets.find(
        {"guild_id": interaction.guild.id, "owner_id": ticket["owner_id"]}
    ).sort("number", -1).limit(10)
    docs = [d async for d in cursor]
    lines = [f"🎫 #{d['number']:04d} — {d['status']}" for d in docs] or ["Nenhum ticket encontrado."]

    view = build_container("🕐 HISTÓRICO DE TICKETS", lines, discord.Colour.blurple())
    await interaction.response.send_message(view=view, ephemeral=True)


async def action_recent(interaction: discord.Interaction):
    config = await get_config(interaction.client, interaction.guild.id)
    if not await _require_staff(interaction, config):
        return

    cursor = interaction.client.db.tickets.find({"guild_id": interaction.guild.id}).sort("number", -1).limit(10)
    docs = [d async for d in cursor]
    lines = [f"🎫 #{d['number']:04d} — <@{d['owner_id']}> — {d['status']}" for d in docs] or ["Nenhum ticket encontrado."]

    view = build_container("🕐 TICKETS RECENTES", lines, discord.Colour.blurple())
    await interaction.response.send_message(view=view, ephemeral=True)


async def action_call(interaction: discord.Interaction):
    config = await get_config(interaction.client, interaction.guild.id)
    if not await _require_staff(interaction, config):
        return

    ticket = await _ticket_doc(interaction)
    guild = interaction.guild
    if not ticket:
        await interaction.response.send_message(view=build_notice("❌ Ticket não encontrado.", discord.Colour.red()), ephemeral=True)
        return

    existing_id = ticket.get("call_channel_id")
    if existing_id:
        existing_channel = guild.get_channel(existing_id)
        if existing_channel:
            await interaction.response.send_message(
                view=build_notice(f"🔊 Já existe uma call para este ticket: {existing_channel.mention}", discord.Colour.orange()),
                ephemeral=True,
            )
            return

    await interaction.response.defer()
    category = interaction.channel.category
    overwrites = {
        guild.default_role: discord.PermissionOverwrite(view_channel=False),
        interaction.user: discord.PermissionOverwrite(view_channel=True, connect=True),
    }
    for role_id in config.get("ticket_staff_role_ids", []):
        role = guild.get_role(role_id)
        if role is not None:
            overwrites[role] = discord.PermissionOverwrite(view_channel=True, connect=True)
    owner = guild.get_member(ticket["owner_id"])
    if owner:
        overwrites[owner] = discord.PermissionOverwrite(view_channel=True, connect=True)

    voice = await guild.create_voice_channel(name=f"call-ticket-{ticket['number']:04d}", category=category, overwrites=overwrites)
    await interaction.client.db.tickets.update_one({"_id": ticket["_id"]}, {"$set": {"call_channel_id": voice.id}})
    await interaction.followup.send(view=build_notice(f"🔊 Canal de call criado: {voice.mention}", discord.Colour.green()))
