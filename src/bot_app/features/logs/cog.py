import discord
from discord import app_commands
from discord.ext import commands

from src.bot_app.core.components import respond
from src.bot_app.logging import LogLevel, build_log_embed, get_logger

logger = get_logger(__name__)


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
                embed=build_log_embed(
                    "Canal de logs configurado",
                    "Este canal receberá registros importantes do bot.",
                    LogLevel.SUCCESS,
                ),
                allowed_mentions=discord.AllowedMentions.none(),
            )
            await self.bot.guild_settings.set_log_channel(guild.id, canal.id)
        except discord.Forbidden:
            await respond(interaction, "O Discord negou o envio. Confira as permissões do canal.")
            return
        except Exception:
            logger.exception("Falha ao configurar o canal de logs no servidor %s.", guild.id)
            await respond(interaction, "Não consegui configurar os logs. Tente novamente mais tarde.")
            return

        await respond(interaction, f"Canal de logs configurado: {canal.mention}")

    @app_commands.command(
        name="remover_logs",
        description="Desativa os registros enviados pelo bot.",
    )
    @app_commands.checks.has_permissions(manage_guild=True)
    @app_commands.guild_only()
    async def remove_logs(self, interaction: discord.Interaction) -> None:
        try:
            await self.bot.guild_settings.set_log_channel(interaction.guild_id, None)
        except Exception:
            logger.exception("Falha ao remover canal de logs do servidor %s.", interaction.guild_id)
            await respond(interaction, "Não consegui remover os logs. Tente novamente mais tarde.")
            return
        await respond(interaction, "O envio de logs foi desativado neste servidor.")

    @app_commands.command(
        name="testar_logs",
        description="Envia uma mensagem de teste ao canal de logs configurado.",
    )
    @app_commands.checks.has_permissions(manage_guild=True)
    @app_commands.guild_only()
    async def test_logs(self, interaction: discord.Interaction) -> None:
        try:
            channel_id = await self.bot.guild_settings.get_log_channel(interaction.guild_id)
            channel = interaction.guild.get_channel(channel_id) if channel_id else None
            if not isinstance(channel, discord.TextChannel):
                await respond(
                    interaction,
                    "Nenhum canal de logs válido está configurado. Use /configurar_logs.",
                )
                return
            await channel.send(
                embed=build_log_embed(
                    "Teste de logs",
                    f"Solicitado por {interaction.user} (`{interaction.user.id}`).",
                    LogLevel.INFO,
                ),
                allowed_mentions=discord.AllowedMentions.none(),
            )
        except discord.Forbidden:
            await respond(interaction, "O Discord negou o envio. Confira as permissões do canal.")
            return
        except Exception:
            logger.exception("Falha ao testar logs no servidor %s.", interaction.guild_id)
            await respond(interaction, "Não consegui enviar o teste de logs. Tente novamente mais tarde.")
            return

        await respond(interaction, "Mensagem de teste enviada ao canal de logs.")


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Logs(bot))
