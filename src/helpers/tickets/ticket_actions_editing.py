from __future__ import annotations

import discord

from src.utils.functions import build_notice, SafeView, SafeModal
from src.helpers.tickets.ticket_core import get_config, _require_staff


class RenameModal(SafeModal, title="Renomear Ticket"):
    novo_nome = discord.ui.TextInput(label="Novo nome do canal", max_length=90)

    async def on_submit(self, interaction: discord.Interaction):
        name = self.novo_nome.value.strip().replace(" ", "-").lower()
        await interaction.channel.edit(name=name)
        await interaction.response.send_message(view=build_notice(f"✏️ Canal renomeado para **{name}**.", discord.Colour.green()), ephemeral=True)


async def action_rename(interaction: discord.Interaction):
    config = await get_config(interaction.client, interaction.guild.id)
    if not await _require_staff(interaction, config):
        return
    await interaction.response.send_modal(RenameModal())


class PrioritySelect(discord.ui.Select):
    def __init__(self):
        options = [
            discord.SelectOption(label="Baixa", emoji="🟢"),
            discord.SelectOption(label="Média", emoji="🟡"),
            discord.SelectOption(label="Alta", emoji="🔴"),
        ]
        super().__init__(placeholder="Selecione a prioridade", options=options)

    async def callback(self, interaction: discord.Interaction):
        value = self.values[0]
        await interaction.client.db.tickets.update_one({"_id": str(interaction.channel.id)}, {"$set": {"priority": value}})
        await interaction.response.edit_message(view=build_notice(f"⚔️ Prioridade definida como **{value}**.", discord.Colour.green()))


class PriorityView(SafeView):
    def __init__(self):
        super().__init__(timeout=60)
        self.add_item(PrioritySelect())


async def action_priority(interaction: discord.Interaction):
    config = await get_config(interaction.client, interaction.guild.id)
    if not await _require_staff(interaction, config):
        return
    await interaction.response.send_message(view=PriorityView(), ephemeral=True)


class StatusSelect(discord.ui.Select):
    def __init__(self):
        options = [
            discord.SelectOption(label="Aguardando", emoji="⏳"),
            discord.SelectOption(label="Em Atendimento", emoji="💬"),
            discord.SelectOption(label="Resolvido", emoji="✅"),
        ]
        super().__init__(placeholder="Selecione o status", options=options)

    async def callback(self, interaction: discord.Interaction):
        value = self.values[0]
        await interaction.client.db.tickets.update_one({"_id": str(interaction.channel.id)}, {"$set": {"atendimento": value}})
        await interaction.response.edit_message(view=build_notice(f"📌 Status definido como **{value}**.", discord.Colour.green()))


class StatusView(SafeView):
    def __init__(self):
        super().__init__(timeout=60)
        self.add_item(StatusSelect())


async def action_status(interaction: discord.Interaction):
    config = await get_config(interaction.client, interaction.guild.id)
    if not await _require_staff(interaction, config):
        return
    await interaction.response.send_message(view=StatusView(), ephemeral=True)
