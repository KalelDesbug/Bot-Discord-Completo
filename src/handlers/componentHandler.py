from __future__ import annotations

from datetime import datetime, timezone

from src.components.buttons.giveaways import GiveawayJoinButton, GiveawayParticipantsButton
from src.components.buttons.ticket_panels import TicketPanelButton
from src.components.buttons.ticket_actions import StaffPanelView
from src.helpers.tickets.ticket_core import build_ticket_info_view


def register_persistent_components(bot) -> None:
    bot.add_dynamic_items(
        TicketPanelButton,
        GiveawayJoinButton,
        GiveawayParticipantsButton,
    )
    bot.add_view(StaffPanelView())
    bot.add_view(
        build_ticket_info_view(
            owner=None,
            number=0,
            category_label="",
            opened_at=datetime.now(timezone.utc),
            claimed_by=None,
        )
    )
