import discord


class TextLayout(discord.ui.LayoutView):
    def __init__(self, text: str) -> None:
        super().__init__(timeout=None)
        container = discord.ui.Container()
        container.add_item(discord.ui.TextDisplay((text or " ")[:4000]))
        self.add_item(container)


async def respond(
    interaction: discord.Interaction,
    text: str,
    *,
    ephemeral: bool = True,
) -> None:
    await interaction.response.send_message(view=TextLayout(text), ephemeral=ephemeral)


async def followup(
    interaction: discord.Interaction,
    text: str,
    *,
    ephemeral: bool = True,
) -> None:
    await interaction.followup.send(view=TextLayout(text), ephemeral=ephemeral)
