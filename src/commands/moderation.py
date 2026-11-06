from __future__ import annotations

import logging
from datetime import timedelta
from collections.abc import Awaitable, Callable

import discord
from discord import app_commands
from discord.ext import commands

from src.components.views.confirmation import ConfirmationLayout

logger = logging.getLogger("discord.moderation")


class ModerationCog(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @staticmethod
    def _has_permission(interaction: discord.Interaction, permission: str) -> bool:
        actor = interaction.user
        if not isinstance(actor, discord.Member):
            return False
        permissions = actor.guild_permissions
        return permissions.administrator or bool(getattr(permissions, permission, False))

    @staticmethod
    def _validate_target(
        interaction: discord.Interaction,
        target: discord.Member,
    ) -> str | None:
        guild = interaction.guild
        actor = interaction.user
        if guild is None or not isinstance(actor, discord.Member):
            return "Este comando só pode ser usado em um servidor."
        if target.id in {actor.id, guild.owner_id}:
            return "Você não pode aplicar esta ação em si mesmo ou no dono do servidor."
        bot_user = interaction.client.user
        if target.bot and bot_user is not None and target.id == bot_user.id:
            return "Não posso aplicar esta ação em mim mesmo."

        bot_member = guild.me
        if bot_member is None or target.top_role >= bot_member.top_role:
            return "O cargo do bot precisa estar acima do cargo da pessoa."
        if actor.id != guild.owner_id and target.top_role >= actor.top_role:
            return "Seu cargo precisa estar acima do cargo da pessoa."
        return None

    @staticmethod
    def _clean_reason(reason: str) -> str:
        return reason.strip()[:400] or "Sem motivo informado"

    async def _confirm_action(
        self,
        interaction: discord.Interaction,
        target: discord.Member,
        permission: str,
        title: str,
        description: str,
        action: Callable[[discord.Member], Awaitable[str]],
    ) -> None:
        async def validate_and_run(confirmation: discord.Interaction) -> str:
            if not self._has_permission(confirmation, permission):
                raise PermissionError(
                    "Sua permissão para esta ação não está mais disponível. Ação cancelada."
                )

            guild = confirmation.guild
            if guild is None:
                raise PermissionError("Esta ação só pode ser usada em um servidor.")

            try:
                current_target = await guild.fetch_member(target.id)
            except discord.NotFound as error:
                raise PermissionError(
                    "A pessoa não está mais neste servidor. Ação cancelada."
                ) from error

            validation_error = self._validate_target(confirmation, current_target)
            if validation_error:
                raise PermissionError(f"{validation_error} Ação cancelada.")

            bot_member = guild.me
            if bot_member is None:
                raise PermissionError("Não consegui validar o cargo do bot. Ação cancelada.")
            bot_permissions = bot_member.guild_permissions
            if not (
                bot_permissions.administrator
                or bool(getattr(bot_permissions, permission, False))
            ):
                raise PermissionError(
                    "O bot não possui mais a permissão necessária. Ação cancelada."
                )

            result = await action(current_target)
            logger.info(
                "Moderação concluída: action=%s actor=%s target=%s guild=%s",
                title,
                confirmation.user.id,
                current_target.id,
                guild.id,
            )
            return result

        await interaction.response.send_message(
            view=ConfirmationLayout(interaction, description, validate_and_run),
            ephemeral=True,
            allowed_mentions=discord.AllowedMentions.none(),
        )

    @app_commands.command(name="ban", description="Bane uma pessoa do servidor.")
    @app_commands.guild_only()
    @app_commands.checks.has_permissions(ban_members=True)
    @app_commands.checks.bot_has_permissions(ban_members=True)
    async def ban(
        self,
        interaction: discord.Interaction,
        membro: discord.Member,
        motivo: app_commands.Range[str, 1, 400] = "Sem motivo informado",
    ) -> None:
        validation_error = self._validate_target(interaction, membro)
        if validation_error:
            await interaction.response.send_message(
                validation_error,
                ephemeral=True,
                allowed_mentions=discord.AllowedMentions.none(),
            )
            return

        reason = self._clean_reason(motivo)
        safe_name = discord.utils.escape_markdown(str(membro))
        safe_reason = discord.utils.escape_markdown(reason)

        async def action(target: discord.Member) -> str:
            await target.guild.ban(target, reason=reason, delete_message_seconds=0)
            return f"{safe_name} foi banido. Motivo: {safe_reason}"

        await self._confirm_action(
            interaction,
            membro,
            "ban_members",
            "ban",
            f"Banir **{safe_name}**?\nMotivo: {safe_reason}",
            action,
        )

    @app_commands.command(name="kick", description="Expulsa uma pessoa do servidor.")
    @app_commands.guild_only()
    @app_commands.checks.has_permissions(kick_members=True)
    @app_commands.checks.bot_has_permissions(kick_members=True)
    async def kick(
        self,
        interaction: discord.Interaction,
        membro: discord.Member,
        motivo: app_commands.Range[str, 1, 400] = "Sem motivo informado",
    ) -> None:
        validation_error = self._validate_target(interaction, membro)
        if validation_error:
            await interaction.response.send_message(
                validation_error,
                ephemeral=True,
                allowed_mentions=discord.AllowedMentions.none(),
            )
            return

        reason = self._clean_reason(motivo)
        safe_name = discord.utils.escape_markdown(str(membro))
        safe_reason = discord.utils.escape_markdown(reason)

        async def action(target: discord.Member) -> str:
            await target.kick(reason=reason)
            return f"{safe_name} foi expulso. Motivo: {safe_reason}"

        await self._confirm_action(
            interaction,
            membro,
            "kick_members",
            "kick",
            f"Expulsar **{safe_name}**?\nMotivo: {safe_reason}",
            action,
        )

    @app_commands.command(name="mute", description="Aplica silenciamento temporário (timeout).")
    @app_commands.guild_only()
    @app_commands.checks.has_permissions(moderate_members=True)
    @app_commands.checks.bot_has_permissions(moderate_members=True)
    async def mute(
        self,
        interaction: discord.Interaction,
        membro: discord.Member,
        minutos: app_commands.Range[int, 1, 40320],
        motivo: app_commands.Range[str, 1, 400] = "Sem motivo informado",
    ) -> None:
        validation_error = self._validate_target(interaction, membro)
        if validation_error:
            await interaction.response.send_message(
                validation_error,
                ephemeral=True,
                allowed_mentions=discord.AllowedMentions.none(),
            )
            return

        reason = self._clean_reason(motivo)
        safe_name = discord.utils.escape_markdown(str(membro))
        safe_reason = discord.utils.escape_markdown(reason)

        async def action(target: discord.Member) -> str:
            await target.timeout(timedelta(minutes=minutos), reason=reason)
            return (
                f"{safe_name} recebeu mute por {minutos} minuto(s). "
                f"Motivo: {safe_reason}"
            )

        await self._confirm_action(
            interaction,
            membro,
            "moderate_members",
            "mute",
            f"Aplicar mute em **{safe_name}** por **{minutos} minuto(s)**?\n"
            f"Motivo: {safe_reason}",
            action,
        )


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(ModerationCog(bot))
