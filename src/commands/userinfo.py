from __future__ import annotations

import discord
from discord import app_commands
from discord.ext import commands


class UserInfoCog(commands.Cog):
    @app_commands.command(
        name="userinfo",
        description="Mostra informações de uma pessoa no servidor.",
    )
    @app_commands.guild_only()
    async def userinfo(
        self,
        interaction: discord.Interaction,
        membro: discord.Member | None = None,
    ) -> None:
        member = membro or interaction.user
        if not isinstance(member, discord.Member):
            await interaction.response.send_message(
                "Não foi possível obter os dados do membro.",
                ephemeral=True,
                allowed_mentions=discord.AllowedMentions.none(),
            )
            return

        joined = (
            discord.utils.format_dt(member.joined_at, style="R")
            if member.joined_at
            else "Desconhecido"
        )
        created = discord.utils.format_dt(member.created_at, style="R")
        colour = member.colour if member.colour.value else discord.Colour.blurple()
        embed = discord.Embed(
            title=discord.utils.escape_markdown(str(member)),
            colour=colour,
        )
        embed.set_thumbnail(url=member.display_avatar.url)
        embed.add_field(name="ID", value=f"`{member.id}`", inline=True)
        embed.add_field(name="Entrou no servidor", value=joined, inline=True)
        embed.add_field(name="Conta criada", value=created, inline=True)
        embed.add_field(
            name="Cargo mais alto",
            value=discord.utils.escape_markdown(member.top_role.name),
            inline=False,
        )
        embed.add_field(
            name="Quantidade de cargos",
            value=str(max(0, len(member.roles) - 1)),
            inline=True,
        )
        embed.set_footer(text=f"Servidor: {discord.utils.escape_markdown(member.guild.name)}")

        await interaction.response.send_message(
            embed=embed,
            ephemeral=True,
            allowed_mentions=discord.AllowedMentions.none(),
        )


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(UserInfoCog())
