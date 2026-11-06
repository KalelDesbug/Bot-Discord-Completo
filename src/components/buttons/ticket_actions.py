from __future__ import annotations

import discord

from src.utils.functions import SafeLayoutView
from src.utils.appearance import discord_colour

TICKET_ACCENT = discord.Colour(9078502)


class TicketMainButton(discord.ui.Button):
    def __init__(self, label, emoji, style, action):
        super().__init__(label=label, emoji=emoji, style=style, custom_id=f"ticket_main:{action}")
        self.action = action

    async def callback(self, interaction: discord.Interaction):
        from src.helpers.tickets.ticket_registry import MAIN_ACTIONS
        handler = MAIN_ACTIONS.get(self.action)
        if handler:
            await handler(interaction)


class TicketButton(discord.ui.Button):
    def __init__(self, label, emoji, style, action):
        super().__init__(label=label, emoji=emoji, style=style, custom_id=f"ticket_staff:{action}")
        self.action = action

    async def callback(self, interaction: discord.Interaction):
        from src.helpers.tickets.ticket_registry import ACTIONS
        handler = ACTIONS.get(self.action)
        if handler:
            await handler(interaction)


class StaffPanelView(SafeLayoutView):
    def __init__(self, accent_color: str | None = None):
        super().__init__(timeout=None)

        container = discord.ui.Container(
            discord.ui.TextDisplay(content="## ⚙️ Painel Admin"),
            discord.ui.TextDisplay(content="Gerencie este ticket através das opções abaixo."),
            discord.ui.Separator(),
            discord.ui.ActionRow(
                TicketButton("Fechar", "🔒", discord.ButtonStyle.danger, "close"),
                TicketButton("Assumir", "🙋", discord.ButtonStyle.secondary, "claim"),
            ),
            discord.ui.ActionRow(
                TicketButton("Notificar", "🔔", discord.ButtonStyle.secondary, "notify"),
                TicketButton("Renomear", "✏️", discord.ButtonStyle.secondary, "rename"),
            ),
            discord.ui.ActionRow(
                TicketButton("Prioridade", "⚔️", discord.ButtonStyle.secondary, "priority"),
                TicketButton("Status", "📌", discord.ButtonStyle.secondary, "status"),
            ),
            discord.ui.ActionRow(
                TicketButton("Adicionar", "➕", discord.ButtonStyle.secondary, "add"),
                TicketButton("Remover", "➖", discord.ButtonStyle.secondary, "remove"),
            ),
            discord.ui.ActionRow(
                TicketButton("Bloquear", "🔐", discord.ButtonStyle.secondary, "block"),
                TicketButton("Transcript", "📧", discord.ButtonStyle.secondary, "transcript"),
            ),
            discord.ui.ActionRow(
                TicketButton("Histórico", "🕐", discord.ButtonStyle.secondary, "history"),
                TicketButton("Recentes", "🕐", discord.ButtonStyle.secondary, "recent"),
            ),
            discord.ui.ActionRow(
                TicketButton("Call", "🔊", discord.ButtonStyle.secondary, "call"),
                TicketButton("Transferir", "🚩", discord.ButtonStyle.secondary, "transfer"),
            ),
            accent_colour=discord_colour(accent_color),
        )
        self.add_item(container)
