from __future__ import annotations

from datetime import datetime, timezone

import discord

from src.utils.functions import is_ticket_staff, permission_denied_view, build_notice, SafeLayoutView, send_ticket_log
from src.components.buttons.ticket_actions import TicketMainButton, TICKET_ACCENT
from src.utils.appearance import discord_colour


async def get_config(bot, guild_id):
    return await bot.db.get_config(guild_id)


async def create_ticket(
    bot, guild: discord.Guild, owner: discord.Member, category_label: str = "Geral", panel_key: str = "suporte",
    category_ticket_message: str | None = None,
) -> discord.TextChannel | None:
    lock_key = f"{guild.id}_{owner.id}_{panel_key}"
    async with bot.ticket_locks.hold(lock_key):
        existing = await bot.db.tickets.find_one(
            {"guild_id": guild.id, "owner_id": owner.id, "panel": panel_key, "status": "aberto"}
        )
        if existing:
            return None

        config = await get_config(bot, guild.id)
        panel_settings = config.get("ticket_panels", {}).get(panel_key, {})
        accent_color = panel_settings.get("accent_color")
        number = await bot.db.next_ticket_number(guild.id)

        category_id = config.get("ticket_category_id") or bot.settings.ticket_category_id
        channel_category = guild.get_channel(category_id) if category_id else None

        overwrites = {
            guild.default_role: discord.PermissionOverwrite(view_channel=False),
            owner: discord.PermissionOverwrite(view_channel=True, send_messages=True, read_message_history=True),
            guild.me: discord.PermissionOverwrite(view_channel=True, send_messages=True, manage_channels=True),
        }
        for role_id in config.get("ticket_staff_role_ids", []):
            role = guild.get_role(role_id)
            if role:
                overwrites[role] = discord.PermissionOverwrite(view_channel=True, send_messages=True, read_message_history=True)

        prefix = panel_key.replace("_", "-")
        channel = await guild.create_text_channel(
            name=f"{prefix}-{number:04d}",
            category=channel_category,
            overwrites=overwrites,
            reason=f"Ticket aberto por {owner}",
        )

        now = datetime.now(timezone.utc)
        ticket_data = {
            "_id": str(channel.id),
            "guild_id": guild.id,
            "channel_id": channel.id,
            "number": number,
            "owner_id": owner.id,
            "panel": panel_key,
            "category": category_label,
            "claimed_by": None,
            "status": "aberto",
            "atendimento": "Aguardando",
            "priority": "Média",
            "opened_at": now.isoformat(),
            "closed_at": None,
            "blocked": False,
            "call_channel_id": None,
            "added_members": [],
            "ticket_message_id": None,
            "accent_color": accent_color,
        }
        try:
            await bot.db.tickets.insert_one(ticket_data)
            bot.active_ticket_channels.add(channel.id)
            ticket_message = await channel.send(
                view=build_ticket_info_view(
                    owner=owner,
                    number=number,
                    category_label=category_label,
                    opened_at=now,
                    claimed_by=None,
                    accent_color=accent_color,
                )
            )
            await bot.db.tickets.update_one(
                {"_id": str(channel.id)},
                {"$set": {"ticket_message_id": ticket_message.id}},
            )

            if ticket_message_text := (category_ticket_message or "").strip():
                try:
                    text = ticket_message_text.format(member=owner.mention)
                except (KeyError, IndexError, ValueError):
                    text = ticket_message_text
                intro_view = SafeLayoutView(timeout=None)
                intro_view.add_item(
                    discord.ui.Container(
                        discord.ui.TextDisplay(content=text),
                        accent_colour=discord_colour(accent_color),
                    )
                )
                await channel.send(view=intro_view)
        except Exception:
            bot.active_ticket_channels.discard(channel.id)
            try:
                await bot.db.tickets.delete_one({"_id": str(channel.id)})
            finally:
                try:
                    await channel.delete(reason="Rollback de ticket: falha durante a inicialização")
                except discord.HTTPException:
                    pass
            raise

        await send_ticket_log(
            bot,
            guild,
            config,
            "🎫 TICKET ABERTO",
            [
                f"🎫 Ticket: #{number:04d} — {channel.name}",
                f"🏷️ Categoria: {category_label} · Painel: {panel_key}",
                f"👤 Aberto por: {owner.mention} (`{owner.id}`)",
            ],
        )
        return channel


def build_ticket_info_view(
    owner,
    number,
    category_label,
    opened_at,
    claimed_by=None,
    accent_color: str | None = None,
):
    view = SafeLayoutView(timeout=None)
    owner_mention = getattr(owner, "mention", f"<@{getattr(owner, 'id', owner)}>")
    staff_mention = f"<@{claimed_by}>" if claimed_by else "Ninguém"
    opened_txt = opened_at.strftime("%d/%m/%Y %H:%M") if opened_at else "—"

    container = discord.ui.Container(
        discord.ui.TextDisplay(content="## 🎫 Ticket Aberto"),
        discord.ui.TextDisplay(content=f"{owner_mention}\nAcabou de criar um ticket na categoria **{category_label}**."),
        discord.ui.Separator(),
        discord.ui.TextDisplay(content=f"**Staff que assumiu:** {staff_mention}\n**Aberto em:** {opened_txt} (UTC)"),
        discord.ui.Separator(),
        discord.ui.ActionRow(
            TicketMainButton(label="Fechar ticket", emoji="🔒", style=discord.ButtonStyle.danger, action="close"),
            TicketMainButton(label="Assumir ticket", emoji="🙋", style=discord.ButtonStyle.secondary, action="claim"),
            TicketMainButton(label="Painel Admin", emoji="⚙️", style=discord.ButtonStyle.secondary, action="admin"),
        ),
        accent_colour=discord_colour(accent_color),
    )
    view.add_item(container)
    return view


async def _refresh_ticket_message(interaction: discord.Interaction, ticket: dict):
    channel = interaction.channel
    if not isinstance(channel, discord.TextChannel):
        return

    message = None
    message_id = ticket.get("ticket_message_id")
    if message_id:
        try:
            message = await channel.fetch_message(message_id)
        except (discord.NotFound, discord.Forbidden, discord.HTTPException):
            message = None

    if message is None:
        try:
            async for candidate in channel.history(limit=20, oldest_first=True):
                if candidate.author.id != interaction.client.user.id:
                    continue
                if candidate.components:
                    message = candidate
                    break
        except (discord.Forbidden, discord.HTTPException):
            return

    if message is None:
        return

    owner = interaction.guild.get_member(ticket["owner_id"]) or await interaction.client.fetch_user(ticket["owner_id"])
    opened_at = datetime.fromisoformat(ticket["opened_at"])

    await message.edit(
        view=build_ticket_info_view(
            owner=owner,
            number=ticket["number"],
            category_label=ticket["category"],
            opened_at=opened_at,
            claimed_by=ticket.get("claimed_by"),
            accent_color=ticket.get("accent_color"),
        )
    )


async def _ticket_doc(interaction: discord.Interaction):
    return await interaction.client.db.tickets.find_one({"_id": str(interaction.channel.id)})


async def _require_staff(interaction: discord.Interaction, config) -> bool:
    if not is_ticket_staff(interaction.user, config):
        await interaction.response.send_message(view=permission_denied_view(), ephemeral=True)
        return False
    return True


async def finalize_ticket_closure(bot, guild: discord.Guild, ticket: dict, config: dict) -> datetime:
    now = datetime.now(timezone.utc)
    await bot.db.tickets.update_one(
        {"_id": ticket["_id"], "status": {"$ne": "fechado"}},
        {"$set": {"status": "fechado", "closed_at": now.isoformat()}},
    )
    return now


async def _dm_transcript(bot, guild, user_id, artifact, number) -> None:
    try:
        member = guild.get_member(user_id) or await bot.fetch_user(user_id)
        file = artifact.discord_file()
        try:
            await member.send(
                view=build_notice(f"📧 Transcript do seu ticket #{number:04d} em {guild.name}.", discord.Colour.blurple(), file=file),
                file=file,
            )
        finally:
            file.close()
    except (discord.Forbidden, discord.HTTPException, discord.NotFound):
        pass
