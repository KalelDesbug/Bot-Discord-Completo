import discord


class ConfirmationLayout(discord.ui.LayoutView):
    def __init__(self, owner_id: int, description: str, action) -> None:
        super().__init__(timeout=120)
        self.owner_id = owner_id
        self.action = action

        confirm = discord.ui.Button(label="Confirmar", style=discord.ButtonStyle.danger)
        cancel = discord.ui.Button(label="Cancelar", style=discord.ButtonStyle.secondary)
        confirm.callback = self.confirm
        cancel.callback = self.cancel

        container = discord.ui.Container()
        container.add_item(discord.ui.TextDisplay(f"## Confirmar ação\n{description}"))
        container.add_item(discord.ui.ActionRow(confirm, cancel))
        self.add_item(container)

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id == self.owner_id:
            return True
        await interaction.response.send_message(
            "Só quem iniciou esta ação pode confirmar.", ephemeral=True
        )
        return False

    async def confirm(self, interaction: discord.Interaction) -> None:
        try:
            result = await self.action()
        except discord.Forbidden:
            await interaction.response.edit_message(view=None)
            await interaction.followup.send(
                "Ação recusada pelo Discord. Confira as permissões e a hierarquia de cargos.",
                ephemeral=True,
            )
            return
        except discord.HTTPException:
            await interaction.response.edit_message(view=None)
            await interaction.followup.send(
                "O Discord não conseguiu concluir a ação. Tente novamente.",
                ephemeral=True,
            )
            return

        await interaction.response.edit_message(view=None)
        await interaction.followup.send(result, ephemeral=True)

    async def cancel(self, interaction: discord.Interaction) -> None:
        await interaction.response.edit_message(view=None)
