from __future__ import annotations

from typing import Protocol

import discord

from src.utils.keyed_locks import KeyedLockPool


class DatabaseProtocol(Protocol):
    async def get_config(self, guild_id: int) -> dict: ...
    async def update_config(self, guild_id: int, data: dict) -> None: ...


class BotProtocol(Protocol):
    db: DatabaseProtocol
    ticket_locks: KeyedLockPool
    user: discord.ClientUser | None
