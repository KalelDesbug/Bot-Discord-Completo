import logging

import aiosqlite
import discord
from discord import app_commands
from discord.ext import commands

from src.bot_app.features.tickets.components import TicketControls, TicketPanel
from src.bot_app.features.tickets.service import TicketService

logger = logging.getLogger(__name__)


class Tickets(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self.panel_view_class = TicketPanel
        self.controls_view_class = TicketControls

    @app_commands.command(
        name="configurar_tickets",
        description="Define a categoria de tickets e o cargo de suporte.",
    )
    @app_commands.checks.has_permissions(manage_guild=True)
    @app_commands.guild_only()
    async def configure_tickets(
        self,
        interaction: discord.Interaction,
        categoria: discord.CategoryChannel,
        cargo_suporte: discord.Role,
    ) -> None:
        await interaction.response.defer(ephemeral=True, thinking=True)
        await self.bot.tickets.set_settings(
            interaction.guild_id, categoria.id, cargo_suporte.id
        )
        await interaction.followup.send(
            f"Categoria: {categoria.mention}\nCargo de suporte: {cargo_suporte.mention}",
            ephemeral=True,
            allowed_mentions=discord.AllowedMentions.none(),
        )

    @app_commands.command(
        name="publicar_painel_tickets",
        description="Publica o painel de abertura de tickets neste canal.",
    )
    @app_commands.checks.has_permissions(manage_guild=True)
    @app_commands.guild_only()
    async def publish_panel(self, interaction: discord.Interaction) -> None:
        if not isinstance(interaction.channel, discord.TextChannel):
            await interaction.response.send_message(
                "Use este comando em um canal de texto.", ephemeral=True
            )
            return
        await interaction.response.defer(ephemeral=True, thinking=True)
        await interaction.channel.send(view=TicketPanel())
        await interaction.followup.send(
            "Painel publicado.",
            ephemeral=True,
            allowed_mentions=discord.AllowedMentions.none(),
        )

    async def create_ticket(self, interaction: discord.Interaction) -> None:
        guild = interaction.guild
        if guild is None or not isinstance(interaction.user, discord.Member):
            await interaction.response.send_message(
                "Este botão só pode ser usado em um servidor.", ephemeral=True
            )
            return

        await interaction.response.defer(ephemeral=True, thinking=True)
        try:
            settings = await self.bot.tickets.get_settings(guild.id)
            existing_id = await self.bot.tickets.get_open_for_owner(
                guild.id, interaction.user.id
            )
            if existing_id and guild.get_channel(existing_id) is None:
                await self.bot.tickets.close_ticket(existing_id)
        except aiosqlite.Error:
            logger.exception("Falha ao consultar tickets do servidor %s", guild.id)
            await interaction.followup.send(
                "O sistema de tickets está temporariamente indisponível. Tente novamente.",
                ephemeral=True,
                allowed_mentions=discord.AllowedMentions.none(),
            )
            return

        category_id = settings.get("ticket_category_id")
        support_role_id = settings.get("support_role_id")
        if not category_id or not support_role_id:
            await interaction.followup.send(
                "Um administrador ainda precisa configurar o sistema de tickets.",
                ephemeral=True,
                allowed_mentions=discord.AllowedMentions.none(),
            )
            return

        if existing_id:
            existing = guild.get_channel(existing_id)
            if existing:
                await interaction.followup.send(
                    f"Você já tem um ticket aberto: {existing.mention}",
                    ephemeral=True,
                    allowed_mentions=discord.AllowedMentions.none(),
                )
                return

        category = guild.get_channel(category_id)
        bot_member = guild.me
        support_role = guild.get_role(support_role_id)
        if (
            not isinstance(category, discord.CategoryChannel)
            or bot_member is None
            or support_role is None
        ):
            await interaction.followup.send(
                "A categoria, o cargo de suporte ou o acesso do bot está inválido. "
                "Peça a um administrador para revisar.",
                ephemeral=True,
                allowed_mentions=discord.AllowedMentions.none(),
            )
            return

        overwrites = {
            guild.default_role: discord.PermissionOverwrite(view_channel=False),
            interaction.user: discord.PermissionOverwrite(
                view_channel=True,
                send_messages=True,
                read_message_history=True,
            ),
            bot_member: discord.PermissionOverwrite(
                view_channel=True,
                send_messages=True,
                manage_channels=True,
                read_message_history=True,
            ),
        }
        overwrites[support_role] = discord.PermissionOverwrite(
            view_channel=True,
            send_messages=True,
            read_message_history=True,
        )

        channel = None
        try:
            channel = await guild.create_text_channel(
                name=TicketService.channel_name(interaction.user.name, interaction.user.id),
                category=category,
                overwrites=overwrites,
                reason=f"Ticket aberto por {interaction.user} ({interaction.user.id})",
            )
            await self.bot.tickets.create(channel.id, guild.id, interaction.user.id)
            await channel.send(
                f"{interaction.user.mention}, descreva sua solicitação.",
                view=TicketControls(),
                allowed_mentions=discord.AllowedMentions(
                    users=[interaction.user], roles=False, everyone=False
                ),
            )
        except aiosqlite.IntegrityError:
            await self._cleanup_failed_ticket(
                channel, "Ticket duplicado criado em concorrência"
            )
            try:
                existing_id = await self.bot.tickets.get_open_for_owner(
                    guild.id, interaction.user.id
                )
            except aiosqlite.Error:
                logger.exception(
                    "Falha ao consultar ticket existente do usuário %s",
                    interaction.user.id,
                )
                existing_id = None
            existing = guild.get_channel(existing_id) if existing_id else None
            await interaction.followup.send(
                f"Você já tem um ticket aberto: {existing.mention}"
                if existing
                else "Já existe um ticket aberto para você.",
                ephemeral=True,
                allowed_mentions=discord.AllowedMentions.none(),
            )
            return
        except (discord.HTTPException, aiosqlite.Error):
            logger.exception("Falha ao criar ticket para usuário %s", interaction.user.id)
            await self._cleanup_failed_ticket(
                channel, "Falha durante a criação do ticket"
            )
            await interaction.followup.send(
                "Não foi possível abrir o ticket. Verifique as permissões do bot e tente novamente.",
                ephemeral=True,
                allowed_mentions=discord.AllowedMentions.none(),
            )
            return

        await interaction.followup.send(
            f"Ticket aberto: {channel.mention}",
            ephemeral=True,
            allowed_mentions=discord.AllowedMentions.none(),
        )

    async def _cleanup_failed_ticket(
        self, channel: discord.TextChannel | None, reason: str
    ) -> None:
        if channel is None:
            return
        try:
            await self.bot.tickets.close_ticket(channel.id)
        except aiosqlite.Error:
            logger.exception("Não foi possível marcar o ticket %s como fechado", channel.id)
        try:
            await channel.delete(reason=reason)
        except discord.HTTPException:
            logger.exception("Não foi possível remover o canal de ticket %s", channel.id)
            return
        try:
            await self.bot.tickets.delete_by_channel(channel.id)
        except aiosqlite.Error:
            logger.exception("Não foi possível remover o ticket %s do banco", channel.id)

    async def close_ticket(self, interaction: discord.Interaction) -> None:
        guild = interaction.guild
        channel = interaction.channel
        if guild is None or not isinstance(channel, discord.TextChannel):
            await interaction.response.send_message(
                "Este botão só pode ser usado dentro de um ticket.", ephemeral=True
            )
            return

        await interaction.response.defer(ephemeral=True, thinking=True)
        try:
            ticket = await self.bot.tickets.get_by_channel(channel.id)
        except aiosqlite.Error:
            logger.exception("Falha ao consultar ticket %s", channel.id)
            await interaction.followup.send(
                "O sistema de tickets está temporariamente indisponível. Tente novamente.",
                ephemeral=True,
                allowed_mentions=discord.AllowedMentions.none(),
            )
            return
        if not ticket or ticket["status"] != "open":
            await interaction.followup.send(
                "Este ticket já foi fechado ou não foi encontrado.",
                ephemeral=True,
                allowed_mentions=discord.AllowedMentions.none(),
            )
            return

        try:
            settings = await self.bot.tickets.get_settings(guild.id)
        except aiosqlite.Error:
            logger.exception(
                "Falha ao consultar configuração de tickets do servidor %s", guild.id
            )
            await interaction.followup.send(
                "O sistema de tickets está temporariamente indisponível. Tente novamente.",
                ephemeral=True,
                allowed_mentions=discord.AllowedMentions.none(),
            )
            return
        if not isinstance(interaction.user, discord.Member) or not TicketService.can_close(
            interaction.user, ticket["owner_id"], settings.get("support_role_id")
        ):
            await interaction.followup.send(
                "Só quem abriu o ticket ou a equipe de suporte pode fechá-lo.",
                ephemeral=True,
                allowed_mentions=discord.AllowedMentions.none(),
            )
            return

        try:
            await self.bot.tickets.close_ticket(channel.id)
        except aiosqlite.Error:
            logger.exception("Falha ao fechar ticket %s no banco de dados", channel.id)
            await interaction.followup.send(
                "Não foi possível fechar o ticket. Tente novamente.",
                ephemeral=True,
                allowed_mentions=discord.AllowedMentions.none(),
            )
            return
        try:
            await channel.edit(
                name=f"fechado-{channel.name}"[:100],
                reason=f"Ticket fechado por {interaction.user}",
            )
        except discord.HTTPException:
            logger.exception("Ticket %s fechado no banco, mas não renomeado", channel.id)
        await interaction.followup.send(
            "Ticket fechado. O canal foi mantido para histórico.",
            ephemeral=True,
            allowed_mentions=discord.AllowedMentions.none(),
        )


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Tickets(bot))
