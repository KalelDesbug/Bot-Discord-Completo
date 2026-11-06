from __future__ import annotations

import logging
from copy import deepcopy

import discord

from src.components.modal.welcome import WelcomeAccentColorModal, WelcomeMessageModal
from src.helpers.welcome.service import WelcomeService
from src.utils.functions import SafeLayoutView, build_notice
from src.utils.appearance import discord_colour, normalize_image_position

logger = logging.getLogger("discord.welcome.setup")
_EDITABLE_FIELDS = (
    "welcome_channel_id",
    "welcome_message",
    "welcome_image_url",
    "welcome_accent_color",
    "welcome_image_position",
)


class WelcomeSetupView(SafeLayoutView):
    """Editor de boas-vindas com rascunho e salvamento explícito."""

    def __init__(
        self,
        bot,
        guild: discord.Guild,
        owner_id: int,
        settings: dict,
    ) -> None:
        super().__init__(timeout=900)
        self.bot = bot
        self.guild = guild
        self.owner_id = owner_id
        self.settings = {
            "welcome_channel_id": None,
            "welcome_message": "",
            "welcome_image_url": None,
            "welcome_accent_color": None,
            "welcome_image_position": "outside",
            "welcome_enabled": False,
            **settings,
        }
        self.saved_settings = deepcopy(self.settings)
        self.message: discord.InteractionMessage | None = None
        self.appearance_view: WelcomeAppearanceView | None = None
        self.render()

    @property
    def has_unsaved_changes(self) -> bool:
        return any(
            self.settings.get(field) != self.saved_settings.get(field)
            for field in _EDITABLE_FIELDS
        )

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.owner_id:
            await interaction.response.send_message(
                view=build_notice(
                    "Somente quem abriu `/welcome-setup` pode utilizar este painel.",
                    discord.Colour.red(),
                ),
                ephemeral=True,
            )
            return False

        if not isinstance(interaction.user, discord.Member) or not (
            interaction.user.guild_permissions.manage_guild
            or interaction.user.guild_permissions.administrator
        ):
            await interaction.response.send_message(
                view=build_notice(
                    "Você precisa da permissão **Gerenciar servidor** para configurar boas-vindas.",
                    discord.Colour.red(),
                ),
                ephemeral=True,
            )
            return False
        return True

    def render(self) -> None:
        self.clear_items()
        channel_id = self.settings.get("welcome_channel_id")
        channel = self.guild.get_channel(channel_id) if type(channel_id) is int else None
        enabled = bool(self.settings.get("welcome_enabled", False))
        message = str(self.settings.get("welcome_message") or "")
        image_url = self.settings.get("welcome_image_url")
        dirty = self.has_unsaved_changes

        channel_label = (
            channel.mention if isinstance(channel, discord.TextChannel) else "Não configurado"
        )
        message_label = message[:700] if message else "Não configurada"
        image_label = "Configurada" if image_url else "Não configurada"
        accent_color = self.settings.get("welcome_accent_color")
        image_position = self.settings.get("welcome_image_position", "outside")
        image_position_label = "Dentro do Container" if image_position == "inside" else "Fora do Container"
        status = "🟢 Ativado" if enabled else "🔴 Desativado"
        changes = "🟠 Existem alterações não salvas." if dirty else "🟢 Configuração salva."

        content = (
            "# 🦢 Configuração de Boas-vindas\n"
            "Crie sua mensagem do zero. Nada é preenchido automaticamente.\n\n"
            f"**Status:** {status}\n"
            f"**Canal:** {channel_label}\n"
            f"**Mensagem:**\n{message_label}\n"
            f"**Imagem:** {image_label}\n"
            f"**Cor do Container:** {accent_color or 'Padrão do Discord'}\n"
            f"**Posição da imagem:** {image_position_label}\n"
            f"**Estado:** {changes}\n\n"
            "**Variáveis disponíveis:** `{member}`, `{member_name}`, `{server}` e `{member_count}`.\n"
            "Use `{member}` para mencionar quem entrou."
        )

        try:
            setup_accent = discord_colour(accent_color)
        except ValueError:
            setup_accent = None
        container = discord.ui.Container(accent_colour=setup_accent)
        container.add_item(discord.ui.TextDisplay(content))
        container.add_item(discord.ui.Separator())
        container.add_item(
            discord.ui.TextDisplay(
                "**1. Canal de envio**\nSelecione onde a mensagem será publicada. A escolha fica como rascunho até salvar."
            )
        )
        container.add_item(discord.ui.ActionRow(WelcomeChannelSelect(self)))
        container.add_item(
            discord.ui.TextDisplay(
                "**2. Conteúdo**\nEdite o texto e a imagem. A prévia utiliza o rascunho atual."
            )
        )
        container.add_item(
            discord.ui.ActionRow(
                WelcomeActionButton(
                    self, "edit", "Editar mensagem e imagem", discord.ButtonStyle.primary, "📝"
                ),
                WelcomeActionButton(
                    self,
                    "preview",
                    "Pré-visualizar",
                    discord.ButtonStyle.secondary,
                    "👁️",
                    disabled=not bool(message.strip()),
                ),
                WelcomeAppearanceButton(self),
            )
        )
        container.add_item(
            discord.ui.ActionRow(
                WelcomeActionButton(
                    self,
                    "save",
                    "Salvar configuração",
                    discord.ButtonStyle.success,
                    "💾",
                    disabled=not dirty,
                )
            )
        )
        container.add_item(discord.ui.Separator())
        container.add_item(
            discord.ui.TextDisplay(
                "**4. Ativação**\nSó é possível ativar depois de salvar um canal e uma mensagem."
            )
        )
        container.add_item(
            discord.ui.ActionRow(
                WelcomeActionButton(
                    self,
                    "enable",
                    "Ativar",
                    discord.ButtonStyle.success,
                    "✅",
                    disabled=enabled or dirty or not self._can_enable_saved_config(),
                ),
                WelcomeActionButton(
                    self,
                    "disable",
                    "Desativar",
                    discord.ButtonStyle.danger,
                    "⏸️",
                    disabled=not enabled,
                ),
            )
        )
        self.add_item(container)

    def _can_enable_saved_config(self) -> bool:
        channel_id = self.saved_settings.get("welcome_channel_id")
        message = self.saved_settings.get("welcome_message")
        return (
            type(channel_id) is int
            and channel_id > 0
            and isinstance(message, str)
            and bool(message.strip())
        )

    async def refresh_message(self) -> None:
        self.render()
        if self.message is None:
            return
        try:
            await self.message.edit(view=self)
        except (discord.NotFound, discord.HTTPException):
            logger.debug("Painel de boas-vindas expirou antes de ser atualizado.")

    async def handle_action(self, interaction: discord.Interaction, action: str) -> None:
        if action == "edit":
            await interaction.response.send_modal(WelcomeMessageModal(self))
            return

        if action == "preview":
            if not isinstance(interaction.user, discord.Member):
                await interaction.response.send_message(
                    view=build_notice(
                        "A pré-visualização só está disponível dentro do servidor.",
                        discord.Colour.red(),
                    ),
                    ephemeral=True,
                )
                return
            template = str(self.settings.get("welcome_message") or "").strip()
            if not template:
                await interaction.response.send_message(
                    view=build_notice("Escreva uma mensagem antes de pré-visualizar.", discord.Colour.orange()),
                    ephemeral=True,
                )
                return
            await interaction.response.send_message(
                view=WelcomeService.build_view(
                    template,
                    interaction.user,
                    self.settings.get("welcome_image_url"),
                    self.settings.get("welcome_accent_color"),
                    self.settings.get("welcome_image_position", "outside"),
                ),
                ephemeral=True,
                allowed_mentions=discord.AllowedMentions.none(),
            )
            return

        if action == "save":
            payload = {field: self.settings.get(field) for field in _EDITABLE_FIELDS}
            if not payload.get("welcome_channel_id") or not str(payload.get("welcome_message") or "").strip():
                payload["welcome_enabled"] = False
            try:
                await self.bot.db.update_welcome_settings(self.guild.id, payload)
            except Exception:
                logger.exception("Falha ao salvar boas-vindas no servidor %s.", self.guild.id)
                await interaction.response.send_message(
                    view=build_notice("Não consegui salvar a configuração de boas-vindas.", discord.Colour.red()),
                    ephemeral=True,
                )
                return
            self.settings.update(deepcopy(payload))
            self.saved_settings.update(deepcopy(payload))
            self.render()
            await interaction.response.edit_message(view=self)
            return

        if action == "enable":
            if self.has_unsaved_changes:
                await interaction.response.send_message(
                    view=build_notice("Salve as alterações pendentes antes de ativar.", discord.Colour.orange()),
                    ephemeral=True,
                )
                return
            if not self._can_enable_saved_config():
                await interaction.response.send_message(
                    view=build_notice(
                        "Configure e salve um canal e uma mensagem antes de ativar.",
                        discord.Colour.orange(),
                    ),
                    ephemeral=True,
                )
                return

        enabled = action == "enable"
        try:
            await self.bot.db.update_welcome_settings(
                self.guild.id, {"welcome_enabled": enabled}
            )
        except Exception:
            logger.exception("Falha ao alterar boas-vindas no servidor %s.", self.guild.id)
            await interaction.response.send_message(
                view=build_notice("Não consegui atualizar o estado das boas-vindas.", discord.Colour.red()),
                ephemeral=True,
            )
            return

        self.settings["welcome_enabled"] = enabled
        self.saved_settings["welcome_enabled"] = enabled
        self.render()
        await interaction.response.edit_message(view=self)


class WelcomeAppearanceButton(discord.ui.Button):
    def __init__(self, setup_view: WelcomeSetupView) -> None:
        super().__init__(
            label="Aparência",
            emoji="🎨",
            style=discord.ButtonStyle.secondary,
        )
        self.setup_view = setup_view

    async def callback(self, interaction: discord.Interaction) -> None:
        appearance = WelcomeAppearanceView(self.setup_view)
        self.setup_view.appearance_view = appearance
        await interaction.response.send_message(view=appearance, ephemeral=True)
        appearance.message = await interaction.original_response()


class WelcomeAppearanceView(SafeLayoutView):
    """Subpainel de aparência para manter o painel principal dentro dos limites V2."""

    def __init__(self, setup_view: WelcomeSetupView) -> None:
        super().__init__(timeout=600)
        self.setup_view = setup_view
        self.message: discord.InteractionMessage | None = None
        self.render()

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.setup_view.owner_id:
            await interaction.response.send_message(
                view=build_notice("Somente quem abriu o painel principal pode alterar a aparência.", discord.Colour.red()),
                ephemeral=True,
            )
            return False
        return True

    def render(self) -> None:
        self.clear_items()
        color = self.setup_view.settings.get("welcome_accent_color")
        position = self.setup_view.settings.get("welcome_image_position", "outside")
        position_label = "Dentro do Container" if position == "inside" else "Fora do Container"
        try:
            accent = discord_colour(color)
        except ValueError:
            accent = None
        container = discord.ui.Container(
            discord.ui.TextDisplay(
                "## Aparência das boas-vindas\n"
                f"**Cor atual:** {color or 'Padrão do Discord'}\n"
                f"**Posição da imagem:** {position_label}\n\n"
                "A cor e a posição ficam como rascunho até você salvar no painel principal."
            ),
            discord.ui.ActionRow(WelcomeAppearanceColorButton(self)),
            discord.ui.ActionRow(WelcomeImagePositionSelect(self)),
            accent_colour=accent,
        )
        self.add_item(container)

    async def refresh_message(self) -> None:
        self.render()
        if self.message is not None:
            try:
                await self.message.edit(view=self)
            except (discord.NotFound, discord.HTTPException):
                logger.debug("Subpainel de aparência expirou antes de ser atualizado.")


class WelcomeAppearanceColorButton(discord.ui.Button):
    def __init__(self, appearance_view: WelcomeAppearanceView) -> None:
        super().__init__(
            label="Personalizar cor do Container",
            emoji="🎨",
            style=discord.ButtonStyle.primary,
        )
        self.appearance_view = appearance_view

    async def callback(self, interaction: discord.Interaction) -> None:
        await interaction.response.send_modal(
            WelcomeAccentColorModal(self.appearance_view.setup_view, self.appearance_view)
        )


class WelcomeImagePositionSelect(discord.ui.Select):
    def __init__(self, appearance_view: WelcomeAppearanceView) -> None:
        current = appearance_view.setup_view.settings.get("welcome_image_position", "outside")
        options = [
            discord.SelectOption(
                label="Dentro do Container",
                value="inside",
                description="A imagem fica dentro da moldura colorida.",
                default=current == "inside",
            ),
            discord.SelectOption(
                label="Fora do Container",
                value="outside",
                description="A imagem fica separada, acima do texto.",
                default=current == "outside",
            ),
        ]
        super().__init__(
            placeholder="Posição da imagem de boas-vindas",
            min_values=1,
            max_values=1,
            options=options,
        )
        self.appearance_view = appearance_view

    async def callback(self, interaction: discord.Interaction) -> None:
        try:
            position = normalize_image_position(self.values[0])
        except ValueError as exc:
            await interaction.response.send_message(
                view=build_notice(str(exc), discord.Colour.red()), ephemeral=True
            )
            return
        self.appearance_view.setup_view.settings["welcome_image_position"] = position
        await self.appearance_view.setup_view.refresh_message()
        self.appearance_view.render()
        await interaction.response.edit_message(view=self.appearance_view)


class WelcomeChannelSelect(discord.ui.ChannelSelect):
    def __init__(self, setup_view: WelcomeSetupView) -> None:
        super().__init__(
            placeholder="Selecione o canal de boas-vindas",
            channel_types=[discord.ChannelType.text],
            min_values=1,
            max_values=1,
        )
        self.setup_view = setup_view

    async def callback(self, interaction: discord.Interaction) -> None:
        channel = self.values[0]
        if (
            not isinstance(channel, discord.TextChannel)
            or channel.guild.id != self.setup_view.guild.id
        ):
            await interaction.response.send_message(
                view=build_notice("Selecione um canal de texto deste servidor.", discord.Colour.red()),
                ephemeral=True,
            )
            return

        bot_user = interaction.client.user
        bot_member = self.setup_view.guild.get_member(bot_user.id) if bot_user else None
        permissions = channel.permissions_for(bot_member) if bot_member else None
        if permissions is None or not permissions.view_channel or not permissions.send_messages:
            await interaction.response.send_message(
                view=build_notice(
                    "Preciso de **Ver canal** e **Enviar mensagens** no canal escolhido.",
                    discord.Colour.red(),
                ),
                ephemeral=True,
            )
            return

        self.setup_view.settings["welcome_channel_id"] = channel.id
        self.setup_view.render()
        await interaction.response.edit_message(view=self.setup_view)


class WelcomeActionButton(discord.ui.Button):
    def __init__(
        self,
        setup_view: WelcomeSetupView,
        action: str,
        label: str,
        style: discord.ButtonStyle,
        emoji: str,
        *,
        disabled: bool = False,
    ) -> None:
        super().__init__(label=label, style=style, emoji=emoji, disabled=disabled)
        self.setup_view = setup_view
        self.action = action

    async def callback(self, interaction: discord.Interaction) -> None:
        await self.setup_view.handle_action(interaction, self.action)
