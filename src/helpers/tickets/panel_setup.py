from __future__ import annotations

from urllib.parse import urlparse

import discord

from src.components.buttons.ticket_panels import BUTTON_STYLES, DEFAULT_BUTTON_STYLE
from src.helpers.tickets.panel_config import build_empty_panel, make_panel_key
from src.utils.database_defaults import MAX_PANEL_CATEGORIES, MAX_TICKET_PANELS
from src.utils.appearance import discord_colour, normalize_hex_color, normalize_image_position
from src.utils.functions import SafeLayoutView, SafeModal, build_notice, wrap_selects


class CreatePanelModal(SafeModal, title="Criar painel de tickets"):
    name = discord.ui.TextInput(
        label="Nome do painel",
        placeholder="Ex.: Atendimento, Financeiro, Aplicações...",
        min_length=1,
        max_length=80,
    )

    def __init__(self, config_view=None) -> None:
        super().__init__()
        self.config_view = config_view

    async def on_submit(self, interaction: discord.Interaction) -> None:
        if interaction.guild is None:
            await interaction.response.send_message(
                view=build_notice("Este recurso só pode ser usado em um servidor.", discord.Colour.red()),
                ephemeral=True,
            )
            return

        config = await interaction.client.db.get_config(interaction.guild.id)
        panels = dict(config.get("ticket_panels", {}))
        if len(panels) >= MAX_TICKET_PANELS:
            await interaction.response.send_message(
                view=build_notice(
                    f"Este servidor já atingiu o limite de {MAX_TICKET_PANELS} painéis.",
                    discord.Colour.orange(),
                ),
                ephemeral=True,
            )
            return

        try:
            panel = build_empty_panel(self.name.value)
            panel_key = make_panel_key(self.name.value, panels)
            panels[panel_key] = panel
            await interaction.client.db.update_config(
                interaction.guild.id,
                {"ticket_panels": panels},
            )
        except ValueError as exc:
            await interaction.response.send_message(
                view=build_notice(str(exc), discord.Colour.red()), ephemeral=True
            )
            return

        await interaction.response.send_message(
            view=build_notice(
                f"Painel **{panel['name']}** criado vazio. Agora edite os textos, adicione os botões e escolha os canais de publicação.",
                discord.Colour.green(),
            ),
            ephemeral=True,
        )
        if self.config_view is not None:
            await self.config_view.refresh_from_database()


class CreatePanelButton(discord.ui.Button):
    def __init__(self, config_view=None, *, disabled: bool = False) -> None:
        super().__init__(
            label="Criar painel",
            emoji="➕",
            style=discord.ButtonStyle.success,
            disabled=disabled,
        )
        self.config_view = config_view

    async def callback(self, interaction: discord.Interaction) -> None:
        await interaction.response.send_modal(CreatePanelModal(self.config_view))


class PanelChannelsSelect(discord.ui.ChannelSelect):
    def __init__(self, panel_key: str) -> None:
        super().__init__(
            placeholder="Canais onde este painel será publicado",
            channel_types=[discord.ChannelType.text],
            min_values=0,
            max_values=25,
        )
        self.panel_key = panel_key

    async def callback(self, interaction: discord.Interaction) -> None:
        config = await interaction.client.db.get_config(interaction.guild.id)
        panels = dict(config.get("ticket_panels", {}))
        panel = panels.get(self.panel_key)
        if panel is None:
            await interaction.response.send_message(
                view=build_notice("Este painel não existe mais.", discord.Colour.red()), ephemeral=True
            )
            return

        panel = dict(panel)
        panel["channel_ids"] = [channel.id for channel in self.values]
        panels[self.panel_key] = panel
        await interaction.client.db.update_config(
            interaction.guild.id, {"ticket_panels": panels}
        )
        await interaction.response.send_message(
            view=build_notice(
                f"{len(self.values)} canal(is) definido(s) para **{panel['name']}**.",
                discord.Colour.green(),
            ),
            ephemeral=True,
        )


class PanelTextsModal(SafeModal, title="Textos do painel"):
    titulo = discord.ui.TextInput(label="Título", max_length=100, required=False)
    subtitulo = discord.ui.TextInput(label="Subtítulo", max_length=150, required=False)
    mensagem_inicial = discord.ui.TextInput(
        label="Mensagem inicial",
        style=discord.TextStyle.paragraph,
        max_length=800,
        required=False,
    )
    rodape = discord.ui.TextInput(
        label="Rodapé", style=discord.TextStyle.paragraph, max_length=250, required=False
    )
    imagem_url = discord.ui.TextInput(
        label="URL HTTPS do banner (vazio remove)", max_length=2048, required=False
    )

    def __init__(self, panel_key: str, current: dict) -> None:
        super().__init__()
        self.panel_key = panel_key
        self.titulo.default = str(current.get("title") or "")[:100]
        self.subtitulo.default = str(current.get("subtitle") or "")[:150]
        self.mensagem_inicial.default = str(current.get("welcome") or "")[:800]
        self.rodape.default = str(current.get("footer") or "")[:250]
        self.imagem_url.default = str(current.get("image_url") or "")[:2048]

    async def on_submit(self, interaction: discord.Interaction) -> None:
        config = await interaction.client.db.get_config(interaction.guild.id)
        panels = dict(config.get("ticket_panels", {}))
        panel = panels.get(self.panel_key)
        if panel is None:
            await interaction.response.send_message(
                view=build_notice("Este painel não existe mais.", discord.Colour.red()), ephemeral=True
            )
            return

        image_url = self.imagem_url.value.strip() or None
        parsed_image = urlparse(image_url) if image_url else None
        if image_url is not None and (parsed_image.scheme != "https" or not parsed_image.netloc):
            await interaction.response.send_message(
                view=build_notice("O banner precisa usar uma URL HTTPS.", discord.Colour.red()),
                ephemeral=True,
            )
            return

        panel = dict(panel)
        panel.update(
            {
                "title": self.titulo.value.strip(),
                "subtitle": self.subtitulo.value.strip(),
                "welcome": self.mensagem_inicial.value.strip(),
                "footer": self.rodape.value.strip() or None,
                "image_url": image_url,
            }
        )
        panels[self.panel_key] = panel
        await interaction.client.db.update_config(
            interaction.guild.id, {"ticket_panels": panels}
        )
        await interaction.response.send_message(
            view=build_notice("Textos e banner do painel salvos.", discord.Colour.green()),
            ephemeral=True,
        )


class PanelCategoryModal(SafeModal, title="Configurar botão do painel"):
    emoji = discord.ui.TextInput(label="Emoji", max_length=10, required=False)
    name = discord.ui.TextInput(label="Nome do botão", min_length=1, max_length=40)
    description = discord.ui.TextInput(
        label="Descrição no painel",
        style=discord.TextStyle.paragraph,
        max_length=300,
        required=False,
    )
    ticket_message = discord.ui.TextInput(
        label="Mensagem inicial dentro do ticket",
        style=discord.TextStyle.paragraph,
        max_length=800,
        required=False,
    )
    style = discord.ui.TextInput(
        label="Cor: secondary/primary/success/danger", max_length=10, required=False
    )

    def __init__(
        self,
        panel_key: str,
        index: int,
        current: dict | None = None,
        manager_view=None,
    ) -> None:
        super().__init__()
        current = current or {}
        self.panel_key = panel_key
        self.index = index
        self.manager_view = manager_view
        self.emoji.default = str(current.get("emoji") or "")[:10]
        self.name.default = str(current.get("label") or "")[:40]
        self.description.default = str(current.get("description") or "")[:300]
        self.ticket_message.default = str(current.get("ticket_message") or "")[:800]
        self.style.default = str(current.get("style") or DEFAULT_BUTTON_STYLE)

    async def on_submit(self, interaction: discord.Interaction) -> None:
        config = await interaction.client.db.get_config(interaction.guild.id)
        panels = dict(config.get("ticket_panels", {}))
        panel = panels.get(self.panel_key)
        if panel is None:
            await interaction.response.send_message(
                view=build_notice("Este painel não existe mais.", discord.Colour.red()), ephemeral=True
            )
            return

        categories = list(panel.get("categories", []))
        if self.index > len(categories) or self.index >= MAX_PANEL_CATEGORIES:
            await interaction.response.send_message(
                view=build_notice("A posição deste botão não está mais disponível.", discord.Colour.red()),
                ephemeral=True,
            )
            return

        style = self.style.value.strip().lower() or DEFAULT_BUTTON_STYLE
        if style not in BUTTON_STYLES:
            await interaction.response.send_message(
                view=build_notice(
                    "Cor inválida. Use secondary, primary, success ou danger.",
                    discord.Colour.red(),
                ),
                ephemeral=True,
            )
            return

        category = {
            "emoji": self.emoji.value.strip() or None,
            "label": self.name.value.strip(),
            "description": self.description.value.strip(),
            "ticket_message": self.ticket_message.value.strip(),
            "style": style,
        }
        if not category["label"]:
            await interaction.response.send_message(
                view=build_notice("O nome do botão é obrigatório.", discord.Colour.red()),
                ephemeral=True,
            )
            return

        if self.index == len(categories):
            categories.append(category)
            result_text = f"Botão **{category['label']}** adicionado."
        else:
            categories[self.index] = category
            result_text = f"Botão **{category['label']}** atualizado."
        panel = dict(panel)
        panel["categories"] = categories
        panels[self.panel_key] = panel
        await interaction.client.db.update_config(
            interaction.guild.id, {"ticket_panels": panels}
        )
        await interaction.response.send_message(
            view=build_notice(result_text, discord.Colour.green()), ephemeral=True
        )
        if self.manager_view is not None:
            self.manager_view.panel = panel
            await self.manager_view.refresh_message()


class PanelCategorySelect(discord.ui.Select):
    def __init__(
        self,
        panel_key: str,
        categories: list[dict],
        manager_view: PanelCategoryManagerView,
    ) -> None:
        options = [
            discord.SelectOption(
                label=str(category.get("label") or f"Botão {index + 1}")[:100],
                value=str(index),
                description=(str(category.get("description") or "")[:100] or None),
                emoji=category.get("emoji"),
            )
            for index, category in enumerate(categories[:MAX_PANEL_CATEGORIES])
        ]
        super().__init__(
            placeholder="Selecione um botão para editar",
            min_values=1,
            max_values=1,
            options=options,
        )
        self.panel_key = panel_key
        self.categories = categories
        self.manager_view = manager_view

    async def callback(self, interaction: discord.Interaction) -> None:
        index = int(self.values[0])
        current = self.categories[index] if index < len(self.categories) else {}
        await interaction.response.send_modal(
            PanelCategoryModal(self.panel_key, index, current, self.manager_view)
        )


class AddPanelCategoryButton(discord.ui.Button):
    def __init__(self, panel_key: str, categories: list[dict], manager_view: PanelCategoryManagerView) -> None:
        super().__init__(
            label="Adicionar botão",
            emoji="➕",
            style=discord.ButtonStyle.success,
            disabled=len(categories) >= MAX_PANEL_CATEGORIES,
        )
        self.panel_key = panel_key
        self.index = len(categories)
        self.manager_view = manager_view

    async def callback(self, interaction: discord.Interaction) -> None:
        await interaction.response.send_modal(
            PanelCategoryModal(self.panel_key, self.index, manager_view=self.manager_view)
        )


class PanelCategoryManagerView(SafeLayoutView):
    def __init__(self, panel_key: str, panel: dict) -> None:
        super().__init__(timeout=180)
        self.panel_key = panel_key
        self.panel = dict(panel)
        self.message: discord.InteractionMessage | None = None
        self.render()

    def render(self) -> None:
        self.clear_items()
        categories = list(self.panel.get("categories", []))
        container = discord.ui.Container(
            discord.ui.TextDisplay(
                f"## Botões de {self.panel.get('name', self.panel_key)}\n"
                f"{len(categories)}/{MAX_PANEL_CATEGORIES} botões configurados."
            ),
            accent_colour=discord.Colour.blurple(),
        )
        if categories:
            container.add_item(
                discord.ui.ActionRow(PanelCategorySelect(self.panel_key, categories, self))
            )
        else:
            container.add_item(
                discord.ui.TextDisplay("Nenhum botão criado. Adicione o primeiro botão abaixo.")
            )
        container.add_item(
            discord.ui.ActionRow(AddPanelCategoryButton(self.panel_key, categories, self))
        )
        self.add_item(container)

    async def refresh_message(self) -> None:
        self.render()
        if self.message is not None:
            try:
                await self.message.edit(view=self)
            except (discord.NotFound, discord.HTTPException):
                pass


class PanelAccentColorModal(SafeModal, title="Cor do Container do painel"):
    color = discord.ui.TextInput(
        label="Cor HEX (ex.: #5865F2)",
        placeholder="#5865F2 — deixe vazio para remover a cor personalizada",
        max_length=7,
        required=False,
    )

    def __init__(self, appearance_view: PanelAppearanceView) -> None:
        super().__init__()
        self.appearance_view = appearance_view
        self.color.default = str(appearance_view.panel.get("accent_color") or "")[:7]

    async def on_submit(self, interaction: discord.Interaction) -> None:
        if interaction.user.id != self.appearance_view.owner_id:
            await interaction.response.send_message(
                view=build_notice("Somente quem abriu esta configuração pode alterá-la.", discord.Colour.red()),
                ephemeral=True,
            )
            return

        try:
            accent_color = normalize_hex_color(self.color.value)
            config = await interaction.client.db.get_config(self.appearance_view.guild_id)
            panels = dict(config.get("ticket_panels", {}))
            panel = panels.get(self.appearance_view.panel_key)
            if panel is None:
                raise ValueError("Este painel não existe mais.")
            panel = dict(panel)
            panel["accent_color"] = accent_color
            panels[self.appearance_view.panel_key] = panel
            await interaction.client.db.update_config(
                self.appearance_view.guild_id, {"ticket_panels": panels}
            )
        except ValueError as exc:
            await interaction.response.send_message(
                view=build_notice(str(exc), discord.Colour.red()), ephemeral=True
            )
            return
        except Exception:
            await interaction.response.send_message(
                view=build_notice("Não consegui salvar a cor deste painel.", discord.Colour.red()),
                ephemeral=True,
            )
            return

        self.appearance_view.panel = panel
        await interaction.response.send_message(
            view=build_notice(
                "Cor do Container removida." if accent_color is None else f"Cor **{accent_color}** salva.",
                discord.Colour.green(),
            ),
            ephemeral=True,
        )
        await self.appearance_view.refresh_message()


class PanelAppearanceColorButton(discord.ui.Button):
    def __init__(self, appearance_view: PanelAppearanceView) -> None:
        super().__init__(
            label="Personalizar cor",
            emoji="🎨",
            style=discord.ButtonStyle.primary,
        )
        self.appearance_view = appearance_view

    async def callback(self, interaction: discord.Interaction) -> None:
        await interaction.response.send_modal(PanelAccentColorModal(self.appearance_view))


class PanelImagePositionSelect(discord.ui.Select):
    def __init__(self, appearance_view: PanelAppearanceView) -> None:
        current = appearance_view.panel.get("image_position", "inside")
        options = [
            discord.SelectOption(
                label="Dentro do Container",
                value="inside",
                description="A imagem aparece junto do conteúdo e dentro da moldura.",
                default=current == "inside",
            ),
            discord.SelectOption(
                label="Fora do Container",
                value="outside",
                description="A imagem aparece separada, acima do Container.",
                default=current == "outside",
            ),
        ]
        super().__init__(
            placeholder="Onde a imagem deve aparecer?",
            min_values=1,
            max_values=1,
            options=options,
        )
        self.appearance_view = appearance_view

    async def callback(self, interaction: discord.Interaction) -> None:
        position = self.values[0]
        try:
            position = normalize_image_position(position)
            config = await interaction.client.db.get_config(self.appearance_view.guild_id)
            panels = dict(config.get("ticket_panels", {}))
            panel = panels.get(self.appearance_view.panel_key)
            if panel is None:
                raise ValueError("Este painel não existe mais.")
            panel = dict(panel)
            panel["image_position"] = position
            panels[self.appearance_view.panel_key] = panel
            await interaction.client.db.update_config(
                self.appearance_view.guild_id, {"ticket_panels": panels}
            )
        except ValueError as exc:
            await interaction.response.send_message(
                view=build_notice(str(exc), discord.Colour.red()), ephemeral=True
            )
            return
        except Exception:
            await interaction.response.send_message(
                view=build_notice("Não consegui salvar a posição da imagem.", discord.Colour.red()),
                ephemeral=True,
            )
            return

        self.appearance_view.panel = panel
        self.appearance_view.render()
        await interaction.response.edit_message(view=self.appearance_view)


class PanelAppearanceView(SafeLayoutView):
    def __init__(
        self,
        guild_id: int,
        owner_id: int,
        panel_key: str,
        panel: dict,
    ) -> None:
        super().__init__(timeout=300)
        self.guild_id = guild_id
        self.owner_id = owner_id
        self.panel_key = panel_key
        self.panel = dict(panel)
        self.message: discord.InteractionMessage | None = None
        self.render()

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.owner_id:
            await interaction.response.send_message(
                view=build_notice("Somente quem abriu esta configuração pode utilizá-la.", discord.Colour.red()),
                ephemeral=True,
            )
            return False
        return True

    def render(self) -> None:
        self.clear_items()
        color = self.panel.get("accent_color")
        position = self.panel.get("image_position", "inside")
        position_label = "Dentro do Container" if position == "inside" else "Fora do Container"
        try:
            accent = discord_colour(color)
        except ValueError:
            accent = None
        container = discord.ui.Container(
            discord.ui.TextDisplay(
                f"## Aparência — {self.panel.get('name', self.panel_key)}\n"
                f"**Cor do Container:** {color or 'Padrão do Discord'}\n"
                f"**Posição da imagem:** {position_label}\n\n"
                "Escolha uma cor HEX personalizada e defina se a imagem ficará dentro ou fora do Container. "
                "Depois de alterar a aparência de um painel já publicado, execute `/enviar-painel` novamente para atualizar a mensagem."
            ),
            discord.ui.ActionRow(PanelAppearanceColorButton(self)),
            discord.ui.ActionRow(PanelImagePositionSelect(self)),
            accent_colour=accent,
        )
        self.add_item(container)

    async def refresh_message(self) -> None:
        self.render()
        if self.message is not None:
            try:
                await self.message.edit(view=self)
            except (discord.NotFound, discord.HTTPException):
                pass


class PanelSectionSelect(discord.ui.Select):
    def __init__(self, panel_key: str, panel_name: str) -> None:
        options = [
            discord.SelectOption(label="Textos e banner", value="textos", emoji="📝"),
            discord.SelectOption(label="Botões/categorias", value="categorias", emoji="🔘"),
            discord.SelectOption(label="Canais de publicação", value="canais", emoji="📺"),
            discord.SelectOption(label="Aparência", value="aparencia", emoji="🎨"),
        ]
        super().__init__(
            placeholder=f"Configurar: {panel_name[:80]}",
            options=options,
        )
        self.panel_key = panel_key
        self.panel_name = panel_name

    async def callback(self, interaction: discord.Interaction) -> None:
        config = await interaction.client.db.get_config(interaction.guild.id)
        panel = config.get("ticket_panels", {}).get(self.panel_key)
        if panel is None:
            await interaction.response.send_message(
                view=build_notice("Este painel não existe mais.", discord.Colour.red()), ephemeral=True
            )
            return

        if self.values[0] == "textos":
            await interaction.response.send_modal(PanelTextsModal(self.panel_key, panel))
        elif self.values[0] == "categorias":
            manager = PanelCategoryManagerView(self.panel_key, panel)
            await interaction.response.send_message(view=manager, ephemeral=True)
            manager.message = await interaction.original_response()
        elif self.values[0] == "aparencia":
            appearance = PanelAppearanceView(
                interaction.guild.id,
                interaction.user.id,
                self.panel_key,
                panel,
            )
            await interaction.response.send_message(view=appearance, ephemeral=True)
            appearance.message = await interaction.original_response()
        else:
            await interaction.response.send_message(
                view=wrap_selects(
                    discord.Colour.blurple(),
                    PanelChannelsSelect(self.panel_key),
                    title=f"Canais de publicação — {panel.get('name', self.panel_name)}",
                ),
                ephemeral=True,
            )


class PanelChooserSelect(discord.ui.Select):
    def __init__(self, panels: dict[str, dict]) -> None:
        options = [
            discord.SelectOption(
                label=str(panel.get("name") or key.replace("_", " ").title())[:100],
                value=key,
            )
            for key, panel in list(panels.items())[:MAX_TICKET_PANELS]
        ]
        super().__init__(
            placeholder="Selecione um painel criado por você",
            min_values=1,
            max_values=1,
            options=options,
        )

    async def callback(self, interaction: discord.Interaction) -> None:
        config = await interaction.client.db.get_config(interaction.guild.id)
        panel = config.get("ticket_panels", {}).get(self.values[0])
        if panel is None:
            await interaction.response.send_message(
                view=build_notice("Este painel não existe mais.", discord.Colour.red()), ephemeral=True
            )
            return
        panel_name = str(panel.get("name") or self.values[0])
        await interaction.response.send_message(
            view=wrap_selects(
                discord.Colour.blurple(),
                PanelSectionSelect(self.values[0], panel_name),
                title=f"Editar painel — {panel_name}",
            ),
            ephemeral=True,
        )
