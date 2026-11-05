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
        if cargo_suporte.is_default():
            await interaction.response.send_message(
                "O cargo de suporte não pode ser `@everyone`.",
                ephemeral=True,
            )
            return

        await self.bot.tickets.set_settings(
            interaction.guild_id, categoria.id, cargo_suporte.id
        )
        await interaction.response.send_message(
            f"Categoria: {categoria.mention}\nCargo de suporte: {cargo_suporte.mention}",
            ephemeral=True,
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
        await interaction.channel.send(view=TicketPanel())
        await interaction.response.send_message("Painel publicado.", ephemeral=True)

    async def create_ticket(self, interaction: discord.Interaction) -> None:
        guild = interaction.guild
        if guild is None or not isinstance(interaction.user, discord.Member):
            await interaction.response.send_message(
                "Este botão só pode ser usado em um servidor.", ephemeral=True
            )
            return

        settings = await self.bot.tickets.get_settings(guild.id)
        category_id = settings.get("ticket_category_id")
        if not category_id:
            await interaction.response.send_message(
                "Um administrador ainda precisa configurar o sistema de tickets.",
                ephemeral=True,
            )
            return

        existing_id = await self.bot.tickets.get_open_for_owner(guild.id, interaction.user.id)
        if existing_id:
            existing = guild.get_channel(existing_id)
            if existing:
                await interaction.response.send_message(
                    f"Você já tem um ticket aberto: {existing.mention}", ephemeral=True
                )
                return
            await self.bot.tickets.delete_by_channel(existing_id)

        category = guild.get_channel(category_id)
        bot_member = guild.me
        if not isinstance(category, discord.CategoryChannel) or bot_member is None:
            await interaction.response.send_message(
                "A categoria ou o acesso do bot está inválido. Peça a um administrador para revisar.",
                ephemeral=True,
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
        support_role_id = settings.get("support_role_id")
        support_role = guild.get_role(support_role_id) if support_role_id else None
        if support_role is not None and support_role.is_default():
            await interaction.response.send_message(
                "O cargo de suporte não pode ser `@everyone`.",
                ephemeral=True,
            )
            return
        if support_role:
            overwrites[support_role] = discord.PermissionOverwrite(
                view_channel=True,
                send_messages=True,
                read_message_history=True,
            )

        await interaction.response.defer(ephemeral=True, thinking=True)
        channel = None
        try:
            channel = await guild.create_text_channel(
                name=TicketService.channel_name(interaction.user.name, interaction.user.id),
                category=category,
                overwrites=overwrites,
                reason=f"Ticket aberto por {interaction.user} ({interaction.user.id})",
            )
            await self.bot.tickets.create(channel.id, guild.id, interaction.user.id)
            try:
                await channel.send(
                    f"{interaction.user.mention}, descreva sua solicitação.",
                    view=TicketControls(),
                    allowed_mentions=discord.AllowedMentions(users=True),
                )
            except discord.HTTPException:
                logger.warning(
                    "Falha ao enviar mensagem inicial do ticket %s para %s.",
                    channel.id,
                    interaction.user.id,
                )
                await self.bot.tickets.delete_by_channel(channel.id)
                try:
                    await channel.delete(reason="Falha ao enviar mensagem inicial do ticket")
                except discord.HTTPException:
                    logger.warning("Não foi possível remover canal de ticket com mensagem inicial falha.")
                await interaction.followup.send(
                    "Não foi possível abrir o ticket. Verifique as permissões do bot e tente novamente.",
                    ephemeral=True,
                )
                return
        except aiosqlite.IntegrityError:
            if channel:
                try:
                    await channel.delete(reason="Ticket duplicado criado em concorrência")
                except discord.HTTPException:
                    logger.warning("Não foi possível remover canal de ticket duplicado")
            existing_id = await self.bot.tickets.get_open_for_owner(guild.id, interaction.user.id)
            existing = guild.get_channel(existing_id) if existing_id else None
            await interaction.followup.send(
                f"Você já tem um ticket aberto: {existing.mention}"
                if existing
                else "Já existe um ticket aberto para você.",
                ephemeral=True,
            )
            return
        except (discord.HTTPException, aiosqlite.Error):
            logger.exception("Falha ao criar ticket para usuário %s", interaction.user.id)
            if channel:
                try:
                    await channel.delete(reason="Falha durante a criação do ticket")
                except discord.HTTPException:
                    logger.warning("Não foi possível remover canal de ticket incompleto")
            await interaction.followup.send(
                "Não foi possível abrir o ticket. Verifique as permissões do bot e tente novamente.",
                ephemeral=True,
            )
            return

        await interaction.followup.send(f"Ticket aberto: {channel.mention}", ephemeral=True)

    async def close_ticket(self, interaction: discord.Interaction) -> None:
        guild = interaction.guild
        channel = interaction.channel
        if guild is None or not isinstance(channel, discord.TextChannel):
            await interaction.response.send_message(
                "Este botão só pode ser usado dentro de um ticket.", ephemeral=True
            )
            return

        ticket = await self.bot.tickets.get_by_channel(channel.id)
        if not ticket or ticket["status"] != "open":
            await interaction.response.send_message(
                "Este ticket já foi fechado ou não foi encontrado.", ephemeral=True
            )
            return

        settings = await self.bot.tickets.get_settings(guild.id)
        if not isinstance(interaction.user, discord.Member) or not TicketService.can_close(
            interaction.user, ticket["owner_id"], settings.get("support_role_id")
        ):
            await interaction.response.send_message(
                "Só quem abriu o ticket ou a equipe de suporte pode fechá-lo.",
                ephemeral=True,
            )
            return

        await self.bot.tickets.close_ticket(channel.id)
        try:
            await channel.edit(
                name=f"fechado-{channel.name}"[:100],
                reason=f"Ticket fechado por {interaction.user}",
            )
        except discord.HTTPException:
            logger.exception("Ticket %s fechado no banco, mas não renomeado", channel.id)
        await interaction.response.send_message(
            "Ticket fechado. O canal foi mantido para histórico.", ephemeral=True
        )


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Tickets(bot))
