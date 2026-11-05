import logging
from collections.abc import Awaitable, Callable

import discord

logger = logging.getLogger(__name__)


class ConfirmationError(Exception):
    pass


class ConfirmationLayout(discord.ui.LayoutView):
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

        confirm = discord.ui.Button(label="Confirmar", style=discord.ButtonStyle.danger)
        cancel = discord.ui.Button(label="Cancelar", style=discord.ButtonStyle.secondary)
        self._buttons = (confirm, cancel)
        confirm.callback = self.confirm
        cancel.callback = self.cancel

        container = discord.ui.Container()
        container.add_item(discord.ui.TextDisplay(f"## Confirmar ação\n{description}"))
        container.add_item(discord.ui.ActionRow(confirm, cancel))
        self.add_item(container)

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id == self.owner_id:
            if not self._completed:
                return True
            message = "Esta confirmação já foi utilizada ou expirou."
        else:
            message = "Só quem iniciou esta ação pode confirmar."
        await interaction.response.send_message(
            message,
            ephemeral=True,
            allowed_mentions=discord.AllowedMentions.none(),
        )
        return False

    async def on_timeout(self) -> None:
        self._completed = True
        for item in self._buttons:
            item.disabled = True
        try:
            await self.source_interaction.edit_original_response(view=self)
        except discord.HTTPException:
            logger.exception("Não foi possível atualizar a confirmação expirada.")

    async def _remove_components(self, interaction: discord.Interaction) -> None:
        if interaction.message is None:
            return
        try:
            await interaction.message.edit(view=None)
        except discord.HTTPException:
            logger.exception("Não foi possível remover os botões da confirmação.")

    async def confirm(self, interaction: discord.Interaction) -> None:
        if self._completed:
            await interaction.response.send_message(
                "Esta confirmação já foi utilizada ou expirou.",
                ephemeral=True,
                allowed_mentions=discord.AllowedMentions.none(),
            )
            return
        self._completed = True
        await interaction.response.defer()
        try:
            result = await self.action(interaction)
        except ConfirmationError as error:
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
                "Ação recusada pelo Discord. Confira as permissões e a hierarquia de cargos.",
                ephemeral=True,
                allowed_mentions=discord.AllowedMentions.none(),
            )
            return
        except discord.HTTPException:
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
        self._completed = True
        await interaction.response.edit_message(view=None)
