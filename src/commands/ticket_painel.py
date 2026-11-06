from __future__ import annotations

import discord
from discord import app_commands
from discord.ext import commands

from src.components.buttons.ticket_panels import TicketPanelView
from src.utils.database_defaults import MAX_PANEL_CATEGORIES
from src.utils.functions import build_notice, is_ticket_manager, permission_denied_view


async def panel_autocomplete(
    interaction: discord.Interaction,
    current: str,
) -> list[app_commands.Choice[str]]:
    if interaction.guild is None:
        return []
    config = await interaction.client.db.get_config(interaction.guild.id)
    query = current.casefold().strip()
    choices = []
    for key, panel in config.get("ticket_panels", {}).items():
        name = str(panel.get("name") or key)
        if query and query not in name.casefold():
            continue
        choices.append(app_commands.Choice(name=name[:100], value=key))
        if len(choices) >= 25:
            break
    return choices


class TicketPainelCommand(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot


    @app_commands.command(
        name="enviar-painel",
        description="Publica ou atualiza um painel de tickets criado em /ticket-config.",
    )
    @app_commands.guild_only()
    @app_commands.describe(painel="Painel personalizado que deseja publicar")
    @app_commands.autocomplete(painel=panel_autocomplete)
    async def enviar_painel(self, interaction: discord.Interaction, painel: str) -> None:
        if interaction.guild is None:
            await interaction.response.send_message(
                view=build_notice("Este comando só pode ser usado em um servidor.", discord.Colour.red()),
                ephemeral=True,
            )
            return
        if not is_ticket_manager(interaction.user):
            await interaction.response.send_message(
                view=permission_denied_view(), ephemeral=True
            )
            return

        config = await self.bot.db.get_config(interaction.guild.id)
        panel = config.get("ticket_panels", {}).get(painel)
        if panel is None:
            await interaction.response.send_message(
                view=build_notice("Painel não encontrado. Crie-o em `/ticket-config`.", discord.Colour.red()),
                ephemeral=True,
            )
            return

        categories = panel.get("categories") or []
        if not 1 <= len(categories) <= MAX_PANEL_CATEGORIES:
            await interaction.response.send_message(
                view=build_notice(
                    f"Configure pelo menos um botão (máximo {MAX_PANEL_CATEGORIES}) antes de publicar.",
                    discord.Colour.orange(),
                ),
                ephemeral=True,
            )
            return

        if any(not str(category.get("label") or "").strip() for category in categories):
            await interaction.response.send_message(
                view=build_notice("Todos os botões precisam ter um nome.", discord.Colour.orange()),
                ephemeral=True,
            )
            return

        channel_ids = panel.get("channel_ids") or []
        if not channel_ids:
            await interaction.response.send_message(
                view=build_notice(
                    f"Nenhum canal configurado para **{panel.get('name', painel)}**. Defina em `/ticket-config`.",
                    discord.Colour.orange(),
                ),
                ephemeral=True,
            )
            return

        await interaction.response.defer(ephemeral=True)
        message_ids = dict(panel.get("message_ids") or {})
        sent_channels: list[str] = []

        for channel_id in channel_ids:
            channel = interaction.guild.get_channel(channel_id)
            if channel is None:
                try:
                    channel = await interaction.guild.fetch_channel(channel_id)
                except (discord.NotFound, discord.Forbidden, discord.HTTPException):
                    continue
            if not isinstance(channel, discord.TextChannel):
                continue

            existing_id = message_ids.get(str(channel_id))
            if existing_id:
                try:
                    message = await channel.fetch_message(existing_id)
                    await message.edit(view=TicketPanelView(painel, panel))
                    sent_channels.append(channel.mention)
                    continue
                except (discord.NotFound, discord.Forbidden, discord.HTTPException):
                    message_ids.pop(str(channel_id), None)

            try:
                message = await channel.send(view=TicketPanelView(painel, panel))
            except (discord.Forbidden, discord.HTTPException):
                continue
            message_ids[str(channel_id)] = message.id
            sent_channels.append(channel.mention)

        panel = {**panel, "message_ids": message_ids}
        panels = dict(config.get("ticket_panels", {}))
        panels[painel] = panel
        await self.bot.db.update_config(
            interaction.guild.id, {"ticket_panels": panels}
        )

        if not sent_channels:
            await interaction.followup.send(
                view=build_notice(
                    "Não consegui publicar em nenhum dos canais configurados. Verifique as permissões do bot.",
                    discord.Colour.red(),
                ),
                ephemeral=True,
            )
            return

        await interaction.followup.send(
            view=build_notice(
                f"Painel **{panel.get('name', painel)}** publicado/atualizado em: {', '.join(sent_channels)}.",
                discord.Colour.green(),
            ),
            ephemeral=True,
        )


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(TicketPainelCommand(bot))
