import logging

import aiosqlite
import discord
from discord import app_commands
from discord.ext import commands

from src.bot_app.core.components import followup, respond
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
        if cargo_suporte.is_default():
            await respond(interaction, "O cargo de suporte não pode ser @everyone.")
            return

        await self.bot.tickets.set_settings(
            interaction.guild_id,
            categoria.id,
            cargo_suporte.id,
        )
        await respond(
            interaction,
            f"Categoria: {categoria.mention}\nCargo de suporte: {cargo_suporte.mention}",
        )

    @app_commands.command(
        name="publicar_painel_tickets",
        description="Publica o painel de abertura de tickets neste canal.",
    )
    @app_commands.checks.has_permissions(manage_guild=True)
    @app_commands.guild_only()
    async def publish_panel(self, interaction: discord.Interaction) -> None:
        if not isinstance(interaction.channel, discord.TextChannel):
            await respond(interaction, "Use este comando em um canal de texto.")
            return
        try:
            await interaction.channel.send(view=TicketPanel())
        except discord.HTTPException:
            logger.exception("Falha ao publicar painel de tickets na guild %s", interaction.guild_id)
            await respond(interaction, "Não consegui publicar o painel neste canal.")
            return
        await respond(interaction, "Painel publicado.")

    async def create_ticket(self, interaction: discord.Interaction) -> None:
        guild = interaction.guild
        user = interaction.user
        if guild is None or not isinstance(user, discord.Member):
            await respond(interaction, "Este botão só pode ser usado em um servidor.")
            return

        settings = await self.bot.tickets.get_settings(guild.id)
        category_id = settings.get("ticket_category_id")
        support_role_id = settings.get("support_role_id")
        category = guild.get_channel(category_id) if category_id else None
        support_role = guild.get_role(support_role_id) if support_role_id else None
        bot_member = guild.me

        if not isinstance(category, discord.CategoryChannel) or bot_member is None:
            await respond(interaction, "A configuração de tickets está inválida. Peça a um administrador para revisá-la.")
            return
        if support_role is None or support_role.is_default():
            await respond(interaction, "O cargo de suporte configurado não existe ou é inválido. Peça a um administrador para revisá-lo.")
            return

        existing_id = await self.bot.tickets.get_open_for_owner(guild.id, user.id)
        if existing_id:
            existing = guild.get_channel(existing_id)
            if existing:
                await respond(interaction, f"Você já tem um ticket aberto: {existing.mention}")
                return
            await self.bot.tickets.delete_by_channel(existing_id)

        overwrites = {
            guild.default_role: discord.PermissionOverwrite(view_channel=False),
            user: discord.PermissionOverwrite(
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
            support_role: discord.PermissionOverwrite(
                view_channel=True,
                send_messages=True,
                read_message_history=True,
            ),
        }

        await interaction.response.defer(ephemeral=True, thinking=True)
        channel = None
        try:
            channel = await guild.create_text_channel(
                name=TicketService.channel_name(user.name, user.id),
                category=category,
                overwrites=overwrites,
                reason=f"Ticket aberto por {user} ({user.id})",
            )
            await self.bot.tickets.create(channel.id, guild.id, user.id)
            await channel.send(
                f"{user.mention}, descreva sua solicitação.",
                view=TicketControls(),
                allowed_mentions=discord.AllowedMentions(users=True),
            )
        except aiosqlite.IntegrityError:
            if channel:
                try:
                    await channel.delete(reason="Ticket duplicado criado em concorrência")
                except discord.HTTPException:
                    logger.warning("Não foi possível remover canal de ticket duplicado")
            existing_id = await self.bot.tickets.get_open_for_owner(guild.id, user.id)
            existing = guild.get_channel(existing_id) if existing_id else None
            await followup(
                interaction,
                f"Você já tem um ticket aberto: {existing.mention}" if existing else "Você já tem um ticket aberto.",
            )
            return
        except (discord.HTTPException, aiosqlite.Error):
            logger.exception("Falha ao criar ticket para usuário %s", user.id)
            if channel:
                try:
                    await channel.delete(reason="Falha durante a criação do ticket")
                except discord.HTTPException:
                    logger.warning("Não foi possível remover canal de ticket incompleto")
            await followup(interaction, "Não foi possível abrir o ticket. Verifique as permissões do bot e tente novamente.")
            return

        await followup(interaction, f"Ticket aberto: {channel.mention}")
        await self.bot.log_event(guild.id, f"🎫 Ticket aberto\nPessoa: {user} (`{user.id}`)\nCanal: {channel.mention}")

    async def close_ticket(self, interaction: discord.Interaction) -> None:
        guild = interaction.guild
        channel = interaction.channel
        member = interaction.user
        if guild is None or not isinstance(channel, discord.TextChannel):
            await respond(interaction, "Este botão só pode ser usado dentro de um ticket.")
            return

        ticket = await self.bot.tickets.get_by_channel(channel.id)
        if not ticket or ticket["status"] != "open":
            await respond(interaction, "Este ticket já foi fechado ou não foi encontrado.")
            return

        settings = await self.bot.tickets.get_settings(guild.id)
        if not isinstance(member, discord.Member) or not TicketService.can_close(
            member,
            ticket["owner_id"],
            settings.get("support_role_id"),
        ):
            await respond(interaction, "Só quem abriu o ticket ou a equipe de suporte pode fechá-lo.")
            return

        await interaction.response.defer(ephemeral=True, thinking=True)
        original_name = channel.name
        try:
            await channel.edit(
                name=f"fechado-{original_name}"[:100],
                reason=f"Ticket fechado por {member}",
            )
        except discord.HTTPException:
            logger.exception("Falha ao renomear ticket %s antes do fechamento", channel.id)
            await followup(interaction, "Não consegui fechar o canal. Confira as permissões do bot e tente novamente.")
            return

        closed = await self.bot.tickets.close_ticket(channel.id)
        if not closed:
            await followup(interaction, "Este ticket já foi fechado.")
            return

        await followup(interaction, "Ticket fechado. O canal foi mantido para histórico.")
        await self.bot.log_event(guild.id, f"🔒 Ticket fechado\nPessoa: {member} (`{member.id}`)\nCanal: {channel.mention}")


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Tickets(bot))
