import discord
from discord import app_commands
from discord.ext import commands

from src.bot_app.core.components import respond
from src.bot_app.features.welcome.service import WelcomeService


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
        guild = interaction.guild
        bot_member = guild.me if guild else None
        if guild is None or bot_member is None:
            await respond(interaction, "Não consegui validar o servidor.")
            return

        permissions = canal.permissions_for(bot_member)
        if not permissions.view_channel or not permissions.send_messages:
            await respond(
                interaction,
                "O bot precisa de Ver canal e Enviar mensagens no canal escolhido.",
            )
            return

        await self.bot.welcome_settings.configure(guild.id, canal.id, mensagem)
        await respond(
            interaction,
            f"Boas-vindas configuradas em {canal.mention}. Use `{{member}}` para mencionar a pessoa e `{{server}}` para o nome do servidor.",
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
        await channel.send(
            view=TextLayout(message),
            allowed_mentions=discord.AllowedMentions(users=True, roles=False, everyone=False),
        )
        await self.bot.log_event(member.guild.id, f"👋 Novo membro\nPessoa: {member} (`{member.id}`)")


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Welcome(bot))
