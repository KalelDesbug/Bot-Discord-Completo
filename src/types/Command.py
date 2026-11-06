from __future__ import annotations

from typing import Protocol

from discord.ext import commands


class ExtensionSetup(Protocol):
    async def __call__(self, bot: commands.Bot) -> None: ...
