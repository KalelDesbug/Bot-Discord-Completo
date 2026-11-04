from datetime import timedelta

import discord
from discord import app_commands
from discord.ext import commands

from src.bot_app.features.moderation.confirmation import ConfirmationLayout


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
    def clean_reason(reason: str) -> str:
        return reason.strip()[:400] or "Sem motivo informado"

    async def confirm_action(
        self, interaction: discord.Interaction, description: str, action
    ) -> None:
        await interaction.response.send_message(
            view=ConfirmationLayout(interaction.user.id, description, action),
            ephemeral=True,
        )

    @app_commands.command(name="ban", description="Bane uma pessoa do servidor.")
    @app_commands.checks.has_permissions(ban_members=True)
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

        async def action() -> str:
            await interaction.guild.ban(membro, reason=reason, delete_message_seconds=0)
            return f"{membro} foi banido. Motivo: {reason}"

        await self.confirm_action(interaction, f"Banir **{membro}**?\nMotivo: {reason}", action)

    @app_commands.command(name="kick", description="Expulsa uma pessoa do servidor.")
    @app_commands.checks.has_permissions(kick_members=True)
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

        async def action() -> str:
            await membro.kick(reason=reason)
            return f"{membro} foi expulso. Motivo: {reason}"

        await self.confirm_action(interaction, f"Expulsar **{membro}**?\nMotivo: {reason}", action)

    @app_commands.command(name="timeout", description="Aplica timeout em uma pessoa.")
    @app_commands.checks.has_permissions(moderate_members=True)
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

        async def action() -> str:
            await membro.timeout(timedelta(minutes=minutos), reason=reason)
            return f"{membro} recebeu timeout por {minutos} minuto(s). Motivo: {reason}"

        await self.confirm_action(
            interaction,
            f"Aplicar timeout em **{membro}** por **{minutos} minuto(s)**?\nMotivo: {reason}",
            action,
        )


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Moderation(bot))
