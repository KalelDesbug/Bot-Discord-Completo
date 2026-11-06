from __future__ import annotations

import discord
from discord import app_commands


async def _is_owner(interaction: discord.Interaction) -> bool:
    return await interaction.client.is_owner(interaction.user)


def owner_guard() -> app_commands.check:
    """Check reutilizável para comandos restritos ao dono da aplicação."""
    return app_commands.check(_is_owner)
