import random

import discord
from discord import app_commands
from discord.ext import commands


class Utility(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @app_commands.command(name="ping", description="Mostra a latência do bot.")
    async def ping(self, interaction: discord.Interaction) -> None:
        await interaction.response.send_message(
            f"Pong! Latência: **{round(self.bot.latency * 1000)} ms**",
            ephemeral=True,
        )

    @app_commands.command(name="avatar", description="Mostra o avatar de uma pessoa.")
    async def avatar(
        self, interaction: discord.Interaction, membro: discord.User | None = None
    ) -> None:
        user = membro or interaction.user
        await interaction.response.send_message(
            f"Avatar de **{user}**: {user.display_avatar.url}",
            ephemeral=True,
            allowed_mentions=discord.AllowedMentions.none(),
        )

    @app_commands.command(name="userinfo", description="Mostra informações de uma pessoa.")
    @app_commands.guild_only()
    async def userinfo(
        self, interaction: discord.Interaction, membro: discord.Member | None = None
    ) -> None:
        user = membro or interaction.user
        if not isinstance(user, discord.Member):
            await interaction.response.send_message(
                "Não foi possível obter os dados do membro.", ephemeral=True
            )
            return
        joined = (
            discord.utils.format_dt(user.joined_at, style="R")
            if user.joined_at
            else "desconhecido"
        )
        await interaction.response.send_message(
            f"**{user}**\nID: `{user.id}`\nEntrou: {joined}\n"
            f"Cargo mais alto: {user.top_role.mention}",
            ephemeral=True,
            allowed_mentions=discord.AllowedMentions.none(),
        )

    @app_commands.command(name="moeda", description="Joga cara ou coroa.")
    async def moeda(self, interaction: discord.Interaction) -> None:
        await interaction.response.send_message(
            f"🪙 Deu **{random.choice(('cara', 'coroa'))}**!"
        )

    @app_commands.command(name="bola8", description="Responde uma pergunta de forma divertida.")
    async def bola8(
        self, interaction: discord.Interaction, pergunta: app_commands.Range[str, 1, 300]
    ) -> None:
        respostas = (
            "Com certeza!",
            "Parece que sim.",
            "Melhor não contar com isso.",
            "Não consigo prever agora.",
            "As chances são boas.",
        )
        await interaction.response.send_message(
            f"🎱 **Pergunta:** {pergunta}\n**Resposta:** {random.choice(respostas)}",
            allowed_mentions=discord.AllowedMentions.none(),
        )


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Utility(bot))
