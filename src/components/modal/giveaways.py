from __future__ import annotations

import re

import discord

from src.utils.functions import build_notice
from src.helpers.giveaways.formatting import _valid_url, format_duration, parse_duration


class SingleFieldModal(discord.ui.Modal):

    def __init__(self, setup_view: GiveawaySetupView, field: str, label: str, placeholder: str, max_length: int, paragraph: bool):
        super().__init__(title=label[:45])
        self.setup_view = setup_view
        self.field = field
        current = setup_view.draft.get(field)
        self.value_input = discord.ui.TextInput(label=label[:45], placeholder=placeholder[:100], default=str(current) if current is not None else None, required=field not in {'image_url', 'thumbnail_url', 'bonus_description'}, max_length=max_length, style=discord.TextStyle.paragraph if paragraph else discord.TextStyle.short)
        self.add_item(self.value_input)

    async def on_submit(self, interaction: discord.Interaction):
        if interaction.user.id != self.setup_view.owner_id:
            await interaction.response.send_message(view=build_notice('❌ Somente quem abriu o painel pode alterá-lo.', discord.Colour.red()), ephemeral=True)
            return
        value = self.value_input.value.strip()
        if self.field in {'title', 'description', 'prize', 'requirement_text'} and (not value):
            await interaction.response.send_message(view=build_notice('❌ Este campo não pode ficar vazio.', discord.Colour.red()), ephemeral=True)
            return
        if self.field in {'image_url', 'thumbnail_url'} and (not _valid_url(value)):
            await interaction.response.send_message(view=build_notice('❌ Informe uma URL válida começando com `https://` ou `http://`, ou deixe o campo vazio.', discord.Colour.red()), ephemeral=True)
            return
        if self.field == 'color':
            raw = value.lstrip('#')
            if not re.fullmatch('[0-9a-fA-F]{6}', raw):
                await interaction.response.send_message(view=build_notice('❌ A cor deve estar no formato hexadecimal, como `#5865F2`.', discord.Colour.red()), ephemeral=True)
                return
            value = f'#{raw.upper()}'
        if self.field in {'image_url', 'thumbnail_url'} and (not value):
            value = None
        self.setup_view.draft[self.field] = value
        self.setup_view.render()
        await interaction.response.defer(ephemeral=True)
        await self.setup_view.sync_after_modal(interaction)

class GeneralSettingsModal(discord.ui.Modal, title='Configurações gerais'):
    prize = discord.ui.TextInput(label='Prêmio', max_length=200, required=True, placeholder='Ex.: R$ 25 via Pix')
    duration = discord.ui.TextInput(label='Duração', max_length=30, required=True, placeholder='Ex.: 30m, 2h ou 1d 4h')
    winners_count = discord.ui.TextInput(label='Quantidade de ganhadores', max_length=2, required=True, placeholder='1')

    def __init__(self, setup_view: GiveawaySetupView):
        super().__init__()
        self.setup_view = setup_view
        self.prize.default = str(setup_view.draft.get('prize', 'Prêmio do sorteio'))
        self.duration.default = format_duration(setup_view.draft.get('duration_seconds', 3600))
        self.winners_count.default = str(setup_view.draft.get('winners_count', 1))

    async def on_submit(self, interaction: discord.Interaction):
        if interaction.user.id != self.setup_view.owner_id:
            await interaction.response.send_message(view=build_notice('❌ Somente quem abriu o painel pode alterá-lo.', discord.Colour.red()), ephemeral=True)
            return
        try:
            seconds = parse_duration(self.duration.value)
            winners = int(self.winners_count.value)
            if not 1 <= winners <= 20:
                raise ValueError('A quantidade de ganhadores deve ficar entre 1 e 20.')
        except ValueError as error:
            await interaction.response.send_message(view=build_notice(f'❌ {error}', discord.Colour.red()), ephemeral=True)
            return
        prize = self.prize.value.strip()
        if not prize:
            await interaction.response.send_message(view=build_notice('❌ Informe o prêmio do sorteio.', discord.Colour.red()), ephemeral=True)
            return
        self.setup_view.draft.update({'prize': prize, 'duration_seconds': seconds, 'winners_count': winners})
        self.setup_view.render()
        await interaction.response.defer(ephemeral=True)
        await self.setup_view.sync_after_modal(interaction)

class BonusAmountModal(discord.ui.Modal, title='Entradas extras por cargo'):
    amount = discord.ui.TextInput(label='Quantidade de entradas extras', max_length=3, required=True, placeholder='Ex.: 5')

    def __init__(self, setup_view: GiveawaySetupView, role_id: int):
        super().__init__()
        self.setup_view = setup_view
        self.role_id = role_id
        current = setup_view.draft.get('role_bonus', {}).get(str(role_id), setup_view.draft.get('role_bonus', {}).get(role_id, 1))
        self.amount.default = str(current)

    async def on_submit(self, interaction: discord.Interaction):
        if interaction.user.id != self.setup_view.owner_id:
            await interaction.response.send_message(view=build_notice('❌ Somente quem abriu o painel pode alterá-lo.', discord.Colour.red()), ephemeral=True)
            return
        try:
            value = int(self.amount.value)
            if not 0 <= value <= 100:
                raise ValueError('O bônus deve ficar entre 0 e 100 entradas extras.')
        except ValueError as error:
            await interaction.response.send_message(view=build_notice(f'❌ {error}', discord.Colour.red()), ephemeral=True)
            return
        key = str(self.role_id)
        if value:
            self.setup_view.draft['role_bonus'][key] = value
        else:
            self.setup_view.draft['role_bonus'].pop(key, None)
            self.setup_view.draft['role_bonus'].pop(self.role_id, None)
        self.setup_view.render()
        await interaction.response.defer(ephemeral=True)
        await self.setup_view.sync_after_modal(interaction)

__all__ = ["SingleFieldModal", "GeneralSettingsModal", "BonusAmountModal"]
