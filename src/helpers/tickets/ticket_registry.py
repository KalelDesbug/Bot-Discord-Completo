from __future__ import annotations

from src.helpers.tickets.ticket_actions_lifecycle import action_close, action_claim, action_admin, action_notify
from src.helpers.tickets.ticket_actions_editing import action_rename, action_priority, action_status
from src.helpers.tickets.ticket_actions_members import action_add, action_remove, action_transfer, action_block
from src.helpers.tickets.ticket_actions_info import action_transcript, action_history, action_recent, action_call

MAIN_ACTIONS = {
    "close": action_close,
    "claim": action_claim,
    "admin": action_admin,
}

ACTIONS = {
    "close": action_close,
    "claim": action_claim,
    "notify": action_notify,
    "rename": action_rename,
    "priority": action_priority,
    "status": action_status,
    "add": action_add,
    "remove": action_remove,
    "block": action_block,
    "transcript": action_transcript,
    "history": action_history,
    "recent": action_recent,
    "call": action_call,
    "transfer": action_transfer,
}
