from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable

import discord

logger = logging.getLogger("discord.confirmation")


class ConfirmationLayout(discord.ui.LayoutView):
    """Confirmação privada e limitada ao usuário que iniciou a ação."""

    def __init__(
        self,
        source_interaction: discord.Interaction,
        description: str,
        action: Callable[[discord.Interaction], Awaitable[str]],
    ) -> None:
        super().__init__(timeout=120)
        self.source_interaction = source_interaction
        self.owner_id = source_interaction.user.id
        self.action = action
        self._completed = False

        confirm = discord.ui.Button(
            label="Confirmar",
            style=discord.ButtonStyle.danger,
        )
        cancel = discord.ui.Button(
            label="Cancelar",
            style=discord.ButtonStyle.secondary,
        )
        self._buttons = (confirm, cancel)
        confirm.callback = self.confirm
        cancel.callback = self.cancel

        container = discord.ui.Container()
        container.add_item(discord.ui.TextDisplay(f"## Confirmar ação\n{description}"))
        container.add_item(discord.ui.ActionRow(confirm, cancel))
        self.add_item(container)

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.owner_id:
            await interaction.response.send_message(
                "Só quem iniciou esta ação pode confirmar.",
                ephemeral=True,
                allowed_mentions=discord.AllowedMentions.none(),
            )
            return False
        if self._completed:
            await interaction.response.send_message(
                "Esta confirmação já foi utilizada ou expirou.",
                ephemeral=True,
                allowed_mentions=discord.AllowedMentions.none(),
            )
            return False
        return True

    def _disable_components(self) -> None:
        self._completed = True
        for item in self._buttons:
            item.disabled = True

    async def _remove_components(self, interaction: discord.Interaction) -> None:
        self._disable_components()
        if interaction.message is None:
            return
        try:
            await interaction.message.edit(view=None)
        except discord.HTTPException:
            logger.exception("Não foi possível remover os botões da confirmação.")

    async def on_timeout(self) -> None:
        self._disable_components()
        try:
            await self.source_interaction.edit_original_response(view=self)
        except discord.HTTPException:
            logger.debug("Não foi possível atualizar a confirmação expirada.")

    async def confirm(self, interaction: discord.Interaction) -> None:
        if self._completed:
            await interaction.response.send_message(
                "Esta confirmação já foi utilizada ou expirou.",
                ephemeral=True,
                allowed_mentions=discord.AllowedMentions.none(),
            )
            return

        self._completed = True
        for item in self._buttons:
            item.disabled = True
        await interaction.response.defer(ephemeral=True)

        try:
            result = await self.action(interaction)
        except PermissionError as error:
            await self._remove_components(interaction)
            await interaction.followup.send(
                str(error),
                ephemeral=True,
                allowed_mentions=discord.AllowedMentions.none(),
            )
            return
        except discord.Forbidden:
            await self._remove_components(interaction)
            await interaction.followup.send(
                "Ação recusada pelo Discord. Confira as permissões e a hierarquia dos cargos.",
                ephemeral=True,
                allowed_mentions=discord.AllowedMentions.none(),
            )
            return
        except discord.HTTPException:
            logger.exception("O Discord recusou a ação confirmada.")
            await self._remove_components(interaction)
            await interaction.followup.send(
                "O Discord não conseguiu concluir a ação. Tente novamente.",
                ephemeral=True,
                allowed_mentions=discord.AllowedMentions.none(),
            )
            return
        except Exception:
            logger.exception("Falha inesperada ao executar ação confirmada.")
            await self._remove_components(interaction)
            await interaction.followup.send(
                "Ocorreu um erro ao executar a ação. Consulte os logs do bot.",
                ephemeral=True,
                allowed_mentions=discord.AllowedMentions.none(),
            )
            return

        await self._remove_components(interaction)
        await interaction.followup.send(
            result,
            ephemeral=True,
            allowed_mentions=discord.AllowedMentions.none(),
        )

    async def cancel(self, interaction: discord.Interaction) -> None:
        self._disable_components()
        await interaction.response.edit_message(view=None)

    async def on_error(
        self,
        interaction: discord.Interaction,
        error: Exception,
        item: discord.ui.Item,
    ) -> None:
        logger.error(
            "Falha no componente de confirmação %s (user=%s, guild=%s).",
            item,
            interaction.user.id,
            interaction.guild_id,
            exc_info=(type(error), error, error.__traceback__),
        )
        try:
            if interaction.response.is_done():
                await interaction.followup.send(
                    "Não consegui processar esta confirmação.",
                    ephemeral=True,
                    allowed_mentions=discord.AllowedMentions.none(),
                )
            else:
                await interaction.response.send_message(
                    "Não consegui processar esta confirmação.",
                    ephemeral=True,
                    allowed_mentions=discord.AllowedMentions.none(),
                )
        except discord.HTTPException:
            logger.debug("Não foi possível responder ao erro da confirmação.")
