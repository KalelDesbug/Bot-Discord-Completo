import discord


class TicketPanel(discord.ui.LayoutView):
    def __init__(self) -> None:
        super().__init__(timeout=None)
        button = discord.ui.Button(
            label="Abrir ticket",
            style=discord.ButtonStyle.primary,
            custom_id="tickets:open",
        )
        button.callback = self.open_ticket

        container = discord.ui.Container()
        container.add_item(
            discord.ui.TextDisplay(
                "## Atendimento\nPrecisa de ajuda? Abra um ticket e explique sua solicitação."
            )
        )
        container.add_item(discord.ui.ActionRow(button))
        self.add_item(container)

    async def open_ticket(self, interaction: discord.Interaction) -> None:
        cog = interaction.client.get_cog("Tickets")
        if cog is None:
            await interaction.response.send_message(
                "O sistema de tickets não está disponível.", ephemeral=True
            )
            return
        await cog.create_ticket(interaction)


class TicketControls(discord.ui.LayoutView):
    def __init__(self) -> None:
        super().__init__(timeout=None)
        button = discord.ui.Button(
            label="Fechar ticket",
            style=discord.ButtonStyle.danger,
            custom_id="tickets:close",
        )
        button.callback = self.close_ticket

        container = discord.ui.Container()
        container.add_item(
            discord.ui.TextDisplay("Quando o atendimento terminar, feche o ticket aqui.")
        )
        container.add_item(discord.ui.ActionRow(button))
        self.add_item(container)

    async def close_ticket(self, interaction: discord.Interaction) -> None:
        cog = interaction.client.get_cog("Tickets")
        if cog is None:
            await interaction.response.send_message(
                "O sistema de tickets não está disponível.", ephemeral=True
            )
            return
        await cog.close_ticket(interaction)
