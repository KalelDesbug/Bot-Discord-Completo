import logging
from collections.abc import Awaitable, Callable

import discord

from src.bot_app.core.components import TextLayout

logger = logging.getLogger(__name__)


class ConfirmationLayout(discord.ui.LayoutView):
    def __init__(
        self,
        owner_id: int,
        description: str,
        action: Callable[[], Awaitable[str]],
    ) -> None:
        super().__init__(timeout=120)
        self.owner_id = owner_id
        self.action = action

        self.confirm_button = discord.ui.Button(
            label="Confirmar",
            style=discord.ButtonStyle.danger,
        )
        self.cancel_button = discord.ui.Button(
            label="Cancelar",
            style=discord.ButtonStyle.secondary,
        )

        self.confirm_button.callback = self.confirm
        self.cancel_button.callback = self.cancel

        container = discord.ui.Container()
        container.add_item(discord.ui.TextDisplay(f"## Confirmar ação\n{description[:3000]}"))
        container.add_item(discord.ui.ActionRow(self.confirm_button, self.cancel_button))
        self.add_item(container)

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id == self.owner_id:
            return True

        await interaction.response.send_message(
            "Só quem iniciou esta ação pode confirmar.",
            ephemeral=True,
        )
        return False

    async def confirm(self, interaction: discord.Interaction) -> None:
        self.confirm_button.disabled = True
        self.cancel_button.disabled = True

        try:
            result = await self.action()
        except discord.Forbidden:
            await interaction.response.edit_message(view=self)
            await interaction.followup.send(
                view=TextLayout("Ação recusada pelo Discord. Confira permissões e hierarquia de cargos."),
                ephemeral=True,
                allowed_mentions=discord.AllowedMentions.none(),
            )
            return
        except discord.HTTPException:
            logger.exception("Falha HTTP ao executar ação confirmada")
            await interaction.response.edit_message(view=self)
            await interaction.followup.send(
                view=TextLayout("O Discord não conseguiu concluir a ação. Tente novamente."),
                ephemeral=True,
                allowed_mentions=discord.AllowedMentions.none(),
            )
            return
        except Exception:
            logger.exception("Erro inesperado ao executar ação confirmada")
            await interaction.response.edit_message(view=self)
            await interaction.followup.send(
                view=TextLayout("Ocorreu um erro ao executar a ação."),
                ephemeral=True,
                allowed_mentions=discord.AllowedMentions.none(),
            )
            return

        await interaction.response.edit_message(view=self)
        await interaction.followup.send(
            view=TextLayout(result),
            ephemeral=True,
            allowed_mentions=discord.AllowedMentions.none(),
        )

    async def cancel(self, interaction: discord.Interaction) -> None:
        self.confirm_button.disabled = True
        self.cancel_button.disabled = True
        await interaction.response.edit_message(view=self)
