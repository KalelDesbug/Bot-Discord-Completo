from __future__ import annotations


class TicketRepository:
    async def next_ticket_number(self, guild_id: int) -> int:
        return await self._next_ticket_sequence(guild_id)
