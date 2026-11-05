import discord
from discord import app_commands
from discord.ext import commands

from src.bot_app.core.components import TextLayout, respond


class Logs(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @app_commands.command(
        name="configurar_logs",
        description="Define o canal para os registros do bot.",
    )
    @app_commands.checks.has_permissions(manage_guild=True)
    @app_commands.guild_only()
    async def configure_logs(
        self,
        interaction: discord.Interaction,
        canal: discord.TextChannel,
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

        try:
            await canal.send(
                view=TextLayout("✅ Este canal foi configurado para os logs do bot."),
                allowed_mentions=discord.AllowedMentions.none(),
            )
            await self.bot.guild_settings.set_log_channel(guild.id, canal.id)
        except discord.HTTPException:
            await respond(interaction, "Não consegui enviar uma mensagem de teste neste canal.")
            return

        await respond(interaction, f"Canal de logs configurado: {canal.mention}")

    @app_commands.command(
        name="remover_logs",
        description="Desativa os registros enviados pelo bot.",
    )
    @app_commands.checks.has_permissions(manage_guild=True)
    @app_commands.guild_only()
    async def remove_logs(self, interaction: discord.Interaction) -> None:
        await self.bot.guild_settings.set_log_channel(interaction.guild_id, None)
        await respond(interaction, "O envio de logs foi desativado neste servidor.")

    @app_commands.command(
        name="testar_logs",
        description="Envia uma mensagem de teste ao canal de logs configurado.",
    )
    @app_commands.checks.has_permissions(manage_guild=True)
    @app_commands.guild_only()
    async def test_logs(self, interaction: discord.Interaction) -> None:
        channel_id = await self.bot.guild_settings.get_log_channel(interaction.guild_id)
        channel = interaction.guild.get_channel(channel_id) if channel_id else None
        if not isinstance(channel, discord.TextChannel):
            await respond(
                interaction,
                "Nenhum canal de logs válido está configurado. Use /configurar_logs.",
            )
            return

        try:
            await channel.send(
                view=TextLayout(f"✅ Teste de logs solicitado por {interaction.user} (`{interaction.user.id}`)."),
                allowed_mentions=discord.AllowedMentions.none(),
            )
        except discord.HTTPException:
            await respond(interaction, "Não consegui enviar a mensagem de teste. Confira as permissões do bot.")
            return

        await respond(interaction, "Mensagem de teste enviada ao canal de logs.")


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Logs(bot))
