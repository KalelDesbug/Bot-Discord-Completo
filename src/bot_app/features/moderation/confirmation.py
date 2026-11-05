import logging

import discord
from discord import app_commands
from discord.ext import commands

from src.bot_app.features.welcome.service import WelcomeService

logger = logging.getLogger(__name__)


class Welcome(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @app_commands.command(
        name="configurar_boas_vindas",
        description="Define o canal e a mensagem de boas-vindas.",
    )
    @app_commands.checks.has_permissions(manage_guild=True)
    @app_commands.guild_only()
    async def configure_welcome(
        self,
        interaction: discord.Interaction,
        canal: discord.TextChannel,
        mensagem: app_commands.Range[str, 1, 500],
    ) -> None:
        await self.bot.welcome_settings.set(
            interaction.guild_id, "welcome_channel_id", canal.id
        )
        await self.bot.welcome_settings.set(
            interaction.guild_id, "welcome_message", mensagem
        )
        await interaction.response.send_message(
            f"Boas-vindas configuradas em {canal.mention}. Use `{{member}}` para mencionar "
            "a pessoa e `{{server}}` para o nome do servidor.",
            ephemeral=True,
        )

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member) -> None:
        settings = await self.bot.welcome_settings.get(member.guild.id)
        channel_id = settings.get("welcome_channel_id")
        if not channel_id:
            return

        channel = member.guild.get_channel(channel_id)
        if not isinstance(channel, discord.TextChannel):
            return

        template = settings.get("welcome_message") or "Boas-vindas, {member}!"
        message = WelcomeService.render(template, member)
        try:
            await channel.send(
                message,
                allowed_mentions=discord.AllowedMentions(
                    users=True, roles=False, everyone=False
                ),
            )
        except discord.HTTPException:
            logger.warning(
                "Não foi possível enviar mensagem de boas-vindas para %s em %s.",
                member.id,
                member.guild.id,
            )
            return


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Welcome(bot))
