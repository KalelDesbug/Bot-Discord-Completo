from __future__ import annotations

import logging

import discord
from discord import app_commands
from discord.ext import commands

from src.helpers.welcome.service import WelcomeService
from src.helpers.welcome.setup_ui import WelcomeSetupView
from src.utils.functions import build_notice

logger = logging.getLogger("discord.welcome")


class WelcomeCog(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @app_commands.command(
        name="welcome-setup",
        description="Abre o painel completo de configuração de boas-vindas.",
    )
    @app_commands.guild_only()
    @app_commands.checks.has_permissions(manage_guild=True)
    async def welcome_setup(self, interaction: discord.Interaction) -> None:
        guild = interaction.guild
        if guild is None:
            await interaction.response.send_message(
                view=build_notice(
                    "Este comando só pode ser usado em um servidor.", discord.Colour.red()
                ),
                ephemeral=True,
            )
            return

        if not isinstance(interaction.user, discord.Member) or not (
            interaction.user.guild_permissions.manage_guild
            or interaction.user.guild_permissions.administrator
        ):
            await interaction.response.send_message(
                view=build_notice(
                    "Você precisa de **Gerenciar servidor** para abrir este painel.",
                    discord.Colour.red(),
                ),
                ephemeral=True,
            )
            return

        await interaction.response.defer(ephemeral=True, thinking=True)
        try:
            settings = await self.bot.db.get_welcome_settings(guild.id)
        except Exception:
            logger.exception("Falha ao carregar boas-vindas no servidor %s.", guild.id)
            await interaction.edit_original_response(
                view=build_notice(
                    "Não consegui carregar a configuração de boas-vindas.",
                    discord.Colour.red(),
                )
            )
            return

        panel = WelcomeSetupView(self.bot, guild, interaction.user.id, settings)
        panel.message = await interaction.edit_original_response(
            content=None, embeds=[], attachments=[], view=panel
        )

    async def _resolve_channel(
        self, guild: discord.Guild, channel_id: int
    ) -> discord.TextChannel | None:
        channel = guild.get_channel(channel_id)
        if isinstance(channel, discord.TextChannel):
            return channel
        if channel is not None:
            return None
        try:
            fetched = await guild.fetch_channel(channel_id)
        except (discord.NotFound, discord.Forbidden, discord.HTTPException):
            logger.warning(
                "Canal de boas-vindas indisponível (guild=%s, channel=%s).",
                guild.id,
                channel_id,
                exc_info=True,
            )
            return None
        return (
            fetched
            if isinstance(fetched, discord.TextChannel) and fetched.guild.id == guild.id
            else None
        )

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member) -> None:
        try:
            settings = await self.bot.db.get_welcome_settings(member.guild.id)
        except Exception:
            logger.exception(
                "Falha ao consultar boas-vindas no servidor %s.", member.guild.id
            )
            return

        if not settings.get("welcome_enabled", False):
            return

        channel_id = settings.get("welcome_channel_id")
        if type(channel_id) is not int or channel_id <= 0:
            return

        channel = await self._resolve_channel(member.guild, channel_id)
        if channel is None:
            logger.warning(
                "Canal de boas-vindas não encontrado (guild=%s, channel=%s).",
                member.guild.id,
                channel_id,
            )
            return

        bot_user = self.bot.user
        bot_member = member.guild.get_member(bot_user.id) if bot_user else None
        permissions = channel.permissions_for(bot_member) if bot_member else None
        if permissions is None or not permissions.view_channel or not permissions.send_messages:
            logger.warning(
                "Sem permissões para enviar boas-vindas (guild=%s, channel=%s).",
                member.guild.id,
                channel_id,
            )
            return

        template = settings.get("welcome_message")
        if not isinstance(template, str) or not template.strip():
            return

        image_url = settings.get("welcome_image_url")
        mentions = discord.AllowedMentions(
            users=[member],
            roles=False,
            everyone=False,
            replied_user=False,
        )
        try:
            await channel.send(
                view=WelcomeService.build_view(
                    template,
                    member,
                    image_url,
                    settings.get("welcome_accent_color"),
                    settings.get("welcome_image_position", "outside"),
                ),
                allowed_mentions=mentions,
            )
        except discord.HTTPException:
            if not image_url:
                logger.exception(
                    "Não foi possível enviar boas-vindas (guild=%s, member=%s).",
                    member.guild.id,
                    member.id,
                )
                return
            logger.warning(
                "Falha ao enviar boas-vindas com imagem; tentando sem imagem "
                "(guild=%s, member=%s).",
                member.guild.id,
                member.id,
                exc_info=True,
            )
            try:
                await channel.send(
                    view=WelcomeService.build_view(
                        template,
                        member,
                        accent_color=settings.get("welcome_accent_color"),
                        image_position=settings.get("welcome_image_position", "outside"),
                    ),
                    allowed_mentions=mentions,
                )
            except (discord.Forbidden, discord.HTTPException):
                logger.exception(
                    "Não foi possível enviar boas-vindas sem imagem "
                    "(guild=%s, member=%s).",
                    member.guild.id,
                    member.id,
                )


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(WelcomeCog(bot))
