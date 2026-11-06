from __future__ import annotations

import logging
from typing import TYPE_CHECKING
from urllib.parse import urlparse

import discord

from src.utils.functions import SafeModal, build_notice
from src.utils.appearance import normalize_hex_color

if TYPE_CHECKING:
    from src.helpers.welcome.setup_ui import WelcomeSetupView

logger = logging.getLogger("discord.welcome.setup")


class WelcomeMessageModal(SafeModal):
    mensagem = discord.ui.TextInput(
        label="Mensagem (use {member} para mencionar)",
        style=discord.TextStyle.paragraph,
        max_length=1000,
        required=False,
    )
    imagem_url = discord.ui.TextInput(
        label="URL HTTPS da imagem (vazio remove)",
        max_length=2048,
        required=False,
    )

    def __init__(self, setup_view: WelcomeSetupView) -> None:
        super().__init__(title="Mensagem e imagem de boas-vindas")
        self.setup_view = setup_view
        self.mensagem.default = str(setup_view.settings.get("welcome_message") or "")[:1000]
        self.imagem_url.default = str(setup_view.settings.get("welcome_image_url") or "")[:2048]

    async def on_submit(self, interaction: discord.Interaction) -> None:
        if interaction.user.id != self.setup_view.owner_id:
            await interaction.response.send_message(
                view=build_notice("Somente quem abriu o painel pode alterar esta configuração.", discord.Colour.red()),
                ephemeral=True,
            )
            return
        if not isinstance(interaction.user, discord.Member) or not (
            interaction.user.guild_permissions.manage_guild
            or interaction.user.guild_permissions.administrator
        ):
            await interaction.response.send_message(
                view=build_notice("Você precisa de **Gerenciar servidor** para alterar boas-vindas.", discord.Colour.red()),
                ephemeral=True,
            )
            return

        message = self.mensagem.value.strip()
        if message and "{member}" not in message:
            await interaction.response.send_message(
                view=build_notice("Inclua `{member}` para mencionar a pessoa que entrou.", discord.Colour.orange()),
                ephemeral=True,
            )
            return

        image_url = self.imagem_url.value.strip() or None
        if image_url is not None:
            parsed = urlparse(image_url)
            if parsed.scheme != "https" or not parsed.netloc:
                await interaction.response.send_message(
                    view=build_notice("A imagem precisa usar uma URL HTTPS válida.", discord.Colour.red()),
                    ephemeral=True,
                )
                return

        self.setup_view.settings.update(
            {"welcome_message": message, "welcome_image_url": image_url}
        )
        await interaction.response.send_message(
            view=build_notice(
                "Rascunho atualizado. Clique em **Salvar configuração** no painel para persistir as alterações.",
                discord.Colour.orange(),
            ),
            ephemeral=True,
        )
        await self.setup_view.refresh_message()


class WelcomeAccentColorModal(SafeModal):
    color = discord.ui.TextInput(
        label="Cor HEX do Container (ex.: #5865F2)",
        placeholder="#5865F2 — vazio remove a cor personalizada",
        max_length=7,
        required=False,
    )

    def __init__(self, setup_view: WelcomeSetupView, appearance_view=None) -> None:
        super().__init__(title="Cor do Container de boas-vindas")
        self.setup_view = setup_view
        self.appearance_view = appearance_view
        self.color.default = str(setup_view.settings.get("welcome_accent_color") or "")[:7]

    async def on_submit(self, interaction: discord.Interaction) -> None:
        if interaction.user.id != self.setup_view.owner_id:
            await interaction.response.send_message(
                view=build_notice("Somente quem abriu o painel pode alterar esta configuração.", discord.Colour.red()),
                ephemeral=True,
            )
            return
        if not isinstance(interaction.user, discord.Member) or not (
            interaction.user.guild_permissions.manage_guild
            or interaction.user.guild_permissions.administrator
        ):
            await interaction.response.send_message(
                view=build_notice("Você precisa de **Gerenciar servidor** para alterar boas-vindas.", discord.Colour.red()),
                ephemeral=True,
            )
            return

        try:
            color = normalize_hex_color(self.color.value)
        except ValueError as exc:
            await interaction.response.send_message(
                view=build_notice(str(exc), discord.Colour.red()), ephemeral=True
            )
            return

        self.setup_view.settings["welcome_accent_color"] = color
        await interaction.response.send_message(
            view=build_notice(
                "Cor personalizada removida do rascunho." if color is None else f"Cor **{color}** definida no rascunho. Clique em **Salvar configuração** para persistir.",
                discord.Colour.orange(),
            ),
            ephemeral=True,
        )
        await self.setup_view.refresh_message()
        if self.appearance_view is not None:
            await self.appearance_view.refresh_message()

