from datetime import timedelta
from collections.abc import Awaitable, Callable

import discord
from discord import app_commands
from discord.ext import commands

from src.bot_app.features.moderation.confirmation import (
    ConfirmationError,
    ConfirmationLayout,
)


class Moderation(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @staticmethod
    def validate_target(
        interaction: discord.Interaction, target: discord.Member
    ) -> str | None:
        guild = interaction.guild
        actor = interaction.user
        if guild is None or not isinstance(actor, discord.Member):
            return "Este comando só pode ser usado em um servidor."
        if target.id in (actor.id, guild.owner_id):
            return "Você não pode aplicar esta ação em si ou no dono do servidor."
        bot_member = guild.me
        if bot_member is None or target.top_role >= bot_member.top_role:
            return "O cargo do bot precisa estar acima do cargo da pessoa."
        if actor.id != guild.owner_id and target.top_role >= actor.top_role:
            return "Seu cargo precisa estar acima do cargo da pessoa."
        return None

    @staticmethod
    def has_permission(interaction: discord.Interaction, permission: str) -> bool:
        actor = interaction.user
        if not isinstance(actor, discord.Member):
            return False
        permissions = actor.guild_permissions
        return permissions.administrator or getattr(permissions, permission, False)

    @staticmethod
    def clean_reason(reason: str) -> str:
        return reason.strip()[:400] or "Sem motivo informado"

    async def confirm_action(
        self,
        interaction: discord.Interaction,
        target: discord.Member,
        permission: str,
        description: str,
        action: Callable[[discord.Member], Awaitable[str]],
    ) -> None:
        async def validate_and_run(
            confirmation: discord.Interaction,
        ) -> str:
            if not self.has_permission(confirmation, permission):
                raise ConfirmationError(
                    "Sua permissão para esta ação mudou. Ela foi cancelada."
                )
            guild = confirmation.guild
            if guild is None:
                raise ConfirmationError("Esta ação só pode ser usada em um servidor.")
            try:
                current_target = await guild.fetch_member(target.id)
            except discord.NotFound as error:
                raise ConfirmationError(
                    "A pessoa não está mais neste servidor. Ação cancelada."
                ) from error
            error = self.validate_target(confirmation, current_target)
            if error:
                raise ConfirmationError(f"{error} Ação cancelada.")
            return await action(current_target)

        await interaction.response.send_message(
            view=ConfirmationLayout(
                interaction, description, validate_and_run
            ),
            ephemeral=True,
            allowed_mentions=discord.AllowedMentions.none(),
        )

    @app_commands.command(name="ban", description="Bane uma pessoa do servidor.")
    @app_commands.checks.has_permissions(ban_members=True)
    @app_commands.checks.bot_has_permissions(ban_members=True)
    @app_commands.guild_only()
    async def ban(
        self,
        interaction: discord.Interaction,
        membro: discord.Member,
        motivo: app_commands.Range[str, 1, 400] = "Sem motivo informado",
    ) -> None:
        error = self.validate_target(interaction, membro)
        if error:
            await interaction.response.send_message(error, ephemeral=True)
            return
        reason = self.clean_reason(motivo)

        async def action(target: discord.Member) -> str:
            await target.guild.ban(
                target, reason=reason, delete_message_seconds=0
            )
            return f"{target} foi banido. Motivo: {reason}"

        await self.confirm_action(
            interaction,
            membro,
            "ban_members",
            f"Banir **{membro}**?\nMotivo: {reason}",
            action,
        )

    @app_commands.command(name="kick", description="Expulsa uma pessoa do servidor.")
    @app_commands.checks.has_permissions(kick_members=True)
    @app_commands.checks.bot_has_permissions(kick_members=True)
    @app_commands.guild_only()
    async def kick(
        self,
        interaction: discord.Interaction,
        membro: discord.Member,
        motivo: app_commands.Range[str, 1, 400] = "Sem motivo informado",
    ) -> None:
        error = self.validate_target(interaction, membro)
        if error:
            await interaction.response.send_message(error, ephemeral=True)
            return
        reason = self.clean_reason(motivo)

        async def action(target: discord.Member) -> str:
            await target.kick(reason=reason)
            return f"{target} foi expulso. Motivo: {reason}"

        await self.confirm_action(
            interaction,
            membro,
            "kick_members",
            f"Expulsar **{membro}**?\nMotivo: {reason}",
            action,
        )

    @app_commands.command(name="timeout", description="Aplica timeout em uma pessoa.")
    @app_commands.checks.has_permissions(moderate_members=True)
    @app_commands.checks.bot_has_permissions(moderate_members=True)
    @app_commands.guild_only()
    async def timeout(
        self,
        interaction: discord.Interaction,
        membro: discord.Member,
        minutos: app_commands.Range[int, 1, 40320],
        motivo: app_commands.Range[str, 1, 400] = "Sem motivo informado",
    ) -> None:
        error = self.validate_target(interaction, membro)
        if error:
            await interaction.response.send_message(error, ephemeral=True)
            return
        reason = self.clean_reason(motivo)

        async def action(target: discord.Member) -> str:
            await target.timeout(timedelta(minutes=minutos), reason=reason)
            return f"{target} recebeu timeout por {minutos} minuto(s). Motivo: {reason}"

        await self.confirm_action(
            interaction,
            membro,
            "moderate_members",
            f"Aplicar timeout em **{membro}** por **{minutos} minuto(s)**?\nMotivo: {reason}",
            action,
        )


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Moderation(bot))
