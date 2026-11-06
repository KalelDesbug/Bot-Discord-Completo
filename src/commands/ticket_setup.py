from __future__ import annotations

import discord
from discord import app_commands
from discord.ext import commands

from src.helpers.tickets.panel_setup import CreatePanelButton, PanelChooserSelect
from src.utils.database_defaults import MAX_TICKET_PANELS
from src.utils.functions import SafeLayoutView, build_notice, is_ticket_manager


class TicketStaffRolesSelect(discord.ui.RoleSelect):
    def __init__(self) -> None:
        super().__init__(
            placeholder="Cargos que podem atender e administrar tickets",
            min_values=0,
            max_values=25,
        )

    async def callback(self, interaction: discord.Interaction) -> None:
        roles = [role.id for role in self.values]
        await interaction.client.db.update_config(
            interaction.guild_id,
            {"ticket_staff_role_ids": roles},
        )
        await interaction.response.send_message(
            view=build_notice(f"✅ {len(roles)} cargo(s) autorizado(s) para tickets.", discord.Colour.green()),
            ephemeral=True,
        )


class TicketCategorySelect(discord.ui.ChannelSelect):
    def __init__(self) -> None:
        super().__init__(
            placeholder="Categoria onde os canais de ticket serão criados",
            channel_types=[discord.ChannelType.category],
            min_values=1,
            max_values=1,
        )

    async def callback(self, interaction: discord.Interaction) -> None:
        category = self.values[0]
        await interaction.client.db.update_config(
            interaction.guild_id,
            {"ticket_category_id": category.id},
        )
        await interaction.response.send_message(
            view=build_notice(f"✅ Categoria dos tickets: **{category.name}**.", discord.Colour.green()),
            ephemeral=True,
        )


class TicketLogChannelSelect(discord.ui.ChannelSelect):
    def __init__(self) -> None:
        super().__init__(
            placeholder="Canal para logs e transcripts dos tickets",
            channel_types=[discord.ChannelType.text],
            min_values=1,
            max_values=1,
        )

    async def callback(self, interaction: discord.Interaction) -> None:
        channel = self.values[0]
        bot_member = interaction.guild.get_member(interaction.client.user.id)
        permissions = channel.permissions_for(bot_member) if bot_member else None
        if permissions is None or not (permissions.view_channel and permissions.send_messages and permissions.attach_files):
            await interaction.response.send_message(
                view=build_notice(
                    "❌ Preciso de Ver canal, Enviar mensagens e Anexar arquivos no canal escolhido.",
                    discord.Colour.red(),
                ),
                ephemeral=True,
            )
            return
        await interaction.client.db.update_config(
            interaction.guild_id,
            {"ticket_log_channel_id": channel.id},
        )
        await interaction.response.send_message(
            view=build_notice(f"✅ Canal de logs dos tickets: {channel.mention}.", discord.Colour.green()),
            ephemeral=True,
        )


class TicketConfigView(SafeLayoutView):
    def __init__(self, bot: commands.Bot, guild_id: int, config: dict) -> None:
        super().__init__(timeout=180)
        self.bot = bot
        self.guild_id = guild_id
        self.config = config
        self.message: discord.InteractionMessage | None = None
        self.render()

    def render(self) -> None:
        self.clear_items()
        panels = self.config.get("ticket_panels", {})
        container = discord.ui.Container(
            discord.ui.TextDisplay(
                "## 🎫 Configuração de Tickets\n"
                "Configure os cargos da equipe, a categoria de criação e o canal de logs.\n"
                f"**Seus painéis ({len(panels)}/{MAX_TICKET_PANELS}):** "
                + ("selecione um painel para editar." if panels else "nenhum criado; crie o primeiro abaixo.")
            ),
            discord.ui.Separator(),
            discord.ui.TextDisplay("**Cargos da equipe**"),
            discord.ui.ActionRow(TicketStaffRolesSelect()),
            discord.ui.TextDisplay("**Categoria dos tickets**"),
            discord.ui.ActionRow(TicketCategorySelect()),
            discord.ui.TextDisplay("**Logs e transcripts**"),
            discord.ui.ActionRow(TicketLogChannelSelect()),
            discord.ui.ActionRow(CreatePanelButton(self, disabled=len(panels) >= MAX_TICKET_PANELS)),
            *([discord.ui.ActionRow(PanelChooserSelect(panels))] if panels else []),
            accent_colour=discord.Colour.blurple(),
        )
        self.add_item(container)

    async def refresh_from_database(self) -> None:
        self.config = await self.bot.db.get_config(self.guild_id)
        self.render()
        if self.message is not None:
            try:
                await self.message.edit(view=self)
            except (discord.NotFound, discord.HTTPException):
                pass


class TicketSetupCog(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @app_commands.command(name="ticket-config", description="Configura somente o sistema de tickets.")
    @app_commands.guild_only()
    @app_commands.checks.has_permissions(manage_guild=True)
    async def ticket_config(self, interaction: discord.Interaction) -> None:
        if not is_ticket_manager(interaction.user):
            await interaction.response.send_message(
                view=build_notice("❌ Você precisa de Gerenciar servidor para configurar tickets.", discord.Colour.red()),
                ephemeral=True,
            )
            return
        config = await self.bot.db.get_config(interaction.guild.id)
        view = TicketConfigView(self.bot, interaction.guild.id, config)
        await interaction.response.send_message(view=view, ephemeral=True)
        view.message = await interaction.original_response()


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(TicketSetupCog(bot))
