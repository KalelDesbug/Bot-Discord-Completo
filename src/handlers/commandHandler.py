from __future__ import annotations

import logging
import traceback

import discord
from discord import app_commands

from src.utils.functions import build_notice

logger = logging.getLogger("discord.commands")


def register_command_error_handler(bot) -> None:
    @bot.tree.error
    async def on_app_command_error(
        interaction: discord.Interaction,
        error: app_commands.AppCommandError,
    ) -> None:
        command_name = interaction.command.qualified_name if interaction.command else "desconhecido"
        original = error.original if isinstance(error, app_commands.CommandInvokeError) else error

        if isinstance(error, app_commands.CommandOnCooldown):
            message = f"⏳ Aguarde {error.retry_after:.1f}s antes de usar este comando novamente."
            colour = discord.Colour.orange()
            logger.info("Cooldown em /%s para usuário %s", command_name, interaction.user.id)
        elif isinstance(error, app_commands.MissingPermissions):
            message = "❌ Você não possui as permissões necessárias para executar este comando."
            colour = discord.Colour.red()
            logger.warning("Permissão ausente em /%s para usuário %s", command_name, interaction.user.id)
        elif isinstance(error, app_commands.CheckFailure):
            message = "❌ Você não está autorizado a executar este comando."
            colour = discord.Colour.red()
            logger.warning("Check recusado em /%s para usuário %s: %r", command_name, interaction.user.id, error)
        else:
            logger.error(
                "Falha em /%s (usuário=%s, servidor=%s): %r",
                command_name,
                interaction.user.id,
                interaction.guild_id,
                original,
                exc_info=(type(original), original, original.__traceback__)
                if original.__traceback__
                else None,
            )
            message = "❌ Ocorreu um erro ao executar este comando. Tente novamente em instantes."
            colour = discord.Colour.red()

        view = build_notice(message, colour)
        try:
            if interaction.response.is_done():
                await interaction.followup.send(view=view, ephemeral=True)
            else:
                await interaction.response.send_message(view=view, ephemeral=True)
        except (discord.NotFound, discord.Forbidden, discord.HTTPException):
            logger.debug("Não foi possível responder à interação %s", interaction.id)
