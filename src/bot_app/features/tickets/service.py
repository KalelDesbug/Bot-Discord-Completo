import re

import discord


class TicketService:
    @staticmethod
    def channel_name(username: str, user_id: int) -> str:
        slug = re.sub(r"[^a-z0-9-]+", "-", username.lower())
        slug = re.sub(r"-+", "-", slug).strip("-")[:40]
        return f"ticket-{slug or user_id}"

    @staticmethod
    def can_close(member: discord.Member, owner_id: int, support_role_id: int | None) -> bool:
        return member.id == owner_id or (
            support_role_id is not None
            and any(role.id == support_role_id for role in member.roles)
        )
