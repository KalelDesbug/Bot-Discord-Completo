from __future__ import annotations

import logging
import discord


NO_PERMISSION_TEXT = "❌ Você não possui permissão para utilizar esta função."


def is_ticket_staff(member: discord.Member, config: dict) -> bool:
    if member.guild_permissions.administrator:
        return True
    role_ids = {int(role_id) for role_id in config.get("ticket_staff_role_ids", [])}
    return any(role.id in role_ids for role in member.roles)


def is_ticket_manager(member: discord.Member) -> bool:
    permissions = member.guild_permissions
    return permissions.administrator or permissions.manage_guild


def is_giveaway_manager(member: discord.Member) -> bool:
    permissions = member.guild_permissions
    return permissions.administrator or permissions.manage_guild


def build_container(
    title: str,
    description_lines: list[str],
    colour: discord.Colour,
    footer: str | None = None,
) -> discord.ui.LayoutView:
    view = SafeLayoutView(timeout=None)
    container = discord.ui.Container(accent_colour=colour)
    container.add_item(discord.ui.TextDisplay(f"## {title}\n" + "\n".join(description_lines)))
    if footer:
        container.add_item(discord.ui.Separator())
        container.add_item(discord.ui.TextDisplay(f"-# {footer}"))
    view.add_item(container)
    return view


def build_notice(
    text: str,
    colour: discord.Colour | None = None,
    file: discord.File | None = None,
) -> discord.ui.LayoutView:
    view = SafeLayoutView(timeout=None)
    container = discord.ui.Container(accent_colour=colour or discord.Colour.blurple())
    container.add_item(discord.ui.TextDisplay(text))
    if file:
        container.add_item(discord.ui.File(media=file))
    view.add_item(container)
    return view


def wrap_selects(
    colour: discord.Colour,
    *items,
    timeout: float = 120,
    title: str | None = None,
) -> discord.ui.LayoutView:
    view = SafeLayoutView(timeout=timeout)
    container = discord.ui.Container(accent_colour=colour)
    if title:
        container.add_item(discord.ui.TextDisplay(title))
        container.add_item(discord.ui.Separator())
    for item in items:
        row = discord.ui.ActionRow()
        row.add_item(item)
        container.add_item(row)
    view.add_item(container)
    return view


def permission_denied_view() -> discord.ui.LayoutView:
    return build_notice(NO_PERMISSION_TEXT, discord.Colour.red())


async def send_ticket_log(
    bot,
    guild: discord.Guild,
    config: dict,
    title: str,
    lines: list[str],
    footer: str | None = None,
    file: discord.File | None = None,
) -> bool:
    channel_id = config.get("ticket_log_channel_id")
    if not channel_id:
        return False

    channel = guild.get_channel(channel_id)
    if channel is None:
        try:
            channel = await guild.fetch_channel(channel_id)
        except (discord.NotFound, discord.Forbidden, discord.HTTPException):
            return False
    if not isinstance(channel, (discord.TextChannel, discord.Thread)):
        return False

    view = build_container(title, lines, discord.Colour.blurple(), footer=footer)
    if file:
        view.children[0].add_item(discord.ui.File(media=file))
    try:
        await channel.send(
            view=view,
            file=file,
            allowed_mentions=discord.AllowedMentions.none(),
        )
        return True
    except (discord.Forbidden, discord.HTTPException):
        logging.getLogger("discord.ticket_logs").exception(
            "Falha ao enviar log de ticket no servidor %s.", guild.id
        )
        return False


async def _report_component_error(
    interaction: discord.Interaction,
    error: Exception,
    item,
) -> None:
    logging.getLogger("discord.components").exception(
        "Falha no componente %s (user=%s, guild=%s)",
        item,
        interaction.user.id,
        interaction.guild_id,
        exc_info=(type(error), error, error.__traceback__),
    )
    notice = build_notice(
        "❌ Ocorreu um erro ao processar esta ação. Tente novamente.",
        discord.Colour.red(),
    )
    try:
        if interaction.response.is_done():
            await interaction.followup.send(view=notice, ephemeral=True)
        else:
            await interaction.response.send_message(view=notice, ephemeral=True)
    except discord.HTTPException:
        pass


class SafeView(discord.ui.View):
    async def on_error(self, interaction: discord.Interaction, error: Exception, item) -> None:
        await _report_component_error(interaction, error, item)


class SafeLayoutView(discord.ui.LayoutView):
    async def on_error(self, interaction: discord.Interaction, error: Exception, item) -> None:
        await _report_component_error(interaction, error, item)


class SafeModal(discord.ui.Modal):
    async def on_error(self, interaction: discord.Interaction, error: Exception) -> None:
        await _report_component_error(interaction, error, self)
