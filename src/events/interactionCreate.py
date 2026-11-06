from __future__ import annotations

import logging

import discord
from discord.ext import commands

logger = logging.getLogger("discord.interactions")


class InteractionEvents(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @commands.Cog.listener()
    async def on_interaction(self, interaction: discord.Interaction) -> None:
        if interaction.type is discord.InteractionType.application_command:
            command = interaction.command.qualified_name if interaction.command else "unknown"
            logger.debug("Comando /%s | user=%s | guild=%s", command, interaction.user.id, interaction.guild_id)
        elif interaction.type is discord.InteractionType.component:
            custom_id = (interaction.data or {}).get("custom_id")
            logger.debug("Componente %s | user=%s | guild=%s", custom_id, interaction.user.id, interaction.guild_id)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(InteractionEvents(bot))
