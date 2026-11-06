from __future__ import annotations

import discord

from src.utils.functions import build_notice


class GiveawayJoinButton(discord.ui.DynamicItem[discord.ui.Button], template=r"giveaway:join:(?P<giveaway_id>[a-f0-9]{32})"):
    def __init__(self, giveaway_id: str, label: str = "Participar", emoji: str = "🎉"):
        super().__init__(discord.ui.Button(
            label=label,
            emoji=emoji,
            style=discord.ButtonStyle.primary,
            custom_id=f"giveaway:join:{giveaway_id}",
        ))
        self.giveaway_id = giveaway_id

    @classmethod
    async def from_custom_id(cls, interaction: discord.Interaction, item: discord.ui.Item, match, /):
        label = getattr(item, "label", None) or "Participar"
        emoji = str(item.emoji) if getattr(item, "emoji", None) else "🎉"
        return cls(match["giveaway_id"], label=label, emoji=emoji)

    async def callback(self, interaction: discord.Interaction) -> None:
        cog = interaction.client.get_cog("GiveawayCog")
        if cog is None:
            await interaction.response.send_message(view=build_notice("❌ O sistema de sorteios está indisponível no momento.", discord.Colour.red()), ephemeral=True)
            return
        await cog.handle_join(interaction, self.giveaway_id)


class GiveawayParticipantsButton(discord.ui.DynamicItem[discord.ui.Button], template=r"giveaway:participants:(?P<giveaway_id>[a-f0-9]{32})"):
    def __init__(self, giveaway_id: str):
        super().__init__(discord.ui.Button(
            label="Participantes",
            emoji="👥",
            style=discord.ButtonStyle.secondary,
            custom_id=f"giveaway:participants:{giveaway_id}",
        ))
        self.giveaway_id = giveaway_id

    @classmethod
    async def from_custom_id(cls, interaction: discord.Interaction, item: discord.ui.Item, match, /):
        return cls(match["giveaway_id"])

    async def callback(self, interaction: discord.Interaction) -> None:
        cog = interaction.client.get_cog("GiveawayCog")
        if cog is None:
            await interaction.response.send_message(view=build_notice("❌ O sistema de sorteios está indisponível no momento.", discord.Colour.red()), ephemeral=True)
            return
        await cog.handle_participants(interaction, self.giveaway_id)
