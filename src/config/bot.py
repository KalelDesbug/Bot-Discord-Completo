from __future__ import annotations

import discord

COMMAND_EXTENSIONS = (
    "src.commands.ticket_setup",
    "src.commands.ticket_painel",
    "src.commands.giveaways",
    "src.commands.welcome",
    "src.commands.userinfo",
    "src.commands.moderation",
)

EVENT_EXTENSIONS = (
    "src.events.ready",
    "src.events.channelDelete",
    "src.events.botmention",
    "src.events.interactionCreate",
    "src.events.ticketMessages",
)


def build_intents() -> discord.Intents:
    intents = discord.Intents.none()
    intents.guilds = True
    intents.members = True
    intents.messages = True
    intents.message_content = True
    return intents
