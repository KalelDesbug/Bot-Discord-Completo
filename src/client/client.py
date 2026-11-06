from __future__ import annotations

import logging

import discord
from discord.ext import commands

from src.config.bot import build_intents
from src.config.env import Settings
from src.handlers.commandHandler import register_command_error_handler
from src.handlers.commandLoader import load_command_extensions
from src.handlers.componentHandler import register_persistent_components
from src.handlers.eventHandler import load_event_extensions
from src.utils.database import Database
from src.utils.keyed_locks import KeyedLockPool


class DiscordBot(commands.Bot):
    def __init__(self, settings: Settings) -> None:
        super().__init__(
            command_prefix=commands.when_mentioned_or("!"),
            intents=build_intents(),
            help_command=None,
            allowed_mentions=discord.AllowedMentions.none(),
        )
        self.settings = settings
        self.logger = logging.getLogger("discord.bot")
        self.db = Database(settings.database_path)
        self.ticket_locks = KeyedLockPool()
        self.active_ticket_channels: set[int] = set()
        self._database_closed = False

    async def setup_hook(self) -> None:
        await self.db.create_indexes()
        self.active_ticket_channels = await self.db.get_open_ticket_channel_ids()
        register_command_error_handler(self)
        await load_command_extensions(self)
        await load_event_extensions(self)
        register_persistent_components(self)

        if self.settings.guild_id:
            # Remove comandos globais antigos e mantém esta instalação limitada ao servidor de teste.
            current_commands = self.tree.get_commands()
            self.tree.clear_commands(guild=None)
            await self.tree.sync()
            for command in current_commands:
                self.tree.add_command(command)

            guild = discord.Object(id=self.settings.guild_id)
            self.tree.copy_global_to(guild=guild)
            synced = await self.tree.sync(guild=guild)
            self.logger.info("%s comandos sincronizados no servidor %s; comandos globais antigos removidos.", len(synced), self.settings.guild_id)
        else:
            synced = await self.tree.sync()
            self.logger.info("%s comandos globais sincronizados.", len(synced))

    async def close(self) -> None:
        try:
            await super().close()
        finally:
            if not self._database_closed:
                await self.db.close()
                self._database_closed = True
                self.logger.info("Banco SQLite local encerrado.")
