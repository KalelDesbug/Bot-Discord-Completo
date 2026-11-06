from __future__ import annotations
import discord
from src.utils.functions import SafeLayoutView, build_notice
from src.utils.appearance import discord_colour, normalize_image_position

MAX_CATEGORIES = 4
CUSTOM_ID_TEMPLATE = r"ticket_panel:open:(?P<panel>[a-z0-9_]+):(?P<index>[0-9]+)"


BUTTON_STYLES = {
    "secondary": discord.ButtonStyle.secondary,
    "primary": discord.ButtonStyle.primary,
    "success": discord.ButtonStyle.success,
    "danger": discord.ButtonStyle.danger,
}
DEFAULT_BUTTON_STYLE = "secondary"


def resolve_button_style(style: str | discord.ButtonStyle | None) -> discord.ButtonStyle:
    if isinstance(style, discord.ButtonStyle):
        return style
    return BUTTON_STYLES.get(style or DEFAULT_BUTTON_STYLE, discord.ButtonStyle.secondary)


class TicketPanelButton(discord.ui.DynamicItem[discord.ui.Button], template=CUSTOM_ID_TEMPLATE):
    def __init__(
        self,
        panel_key: str,
        index: int,
        label: str = "Categoria",
        emoji: str | None = None,
        style: str | discord.ButtonStyle | None = DEFAULT_BUTTON_STYLE,
    ):
        super().__init__(
            discord.ui.Button(
                label=label,
                emoji=emoji,
                style=resolve_button_style(style),
                custom_id=f"ticket_panel:open:{panel_key}:{index}",
            )
        )
        self.panel_key = panel_key
        self.index = index

    @classmethod
    async def from_custom_id(cls, interaction: discord.Interaction, item: discord.ui.Item, match, /):
        return cls(match["panel"], int(match["index"]), label=item.label or "Categoria", emoji=item.emoji, style=item.style)

    async def callback(self, interaction: discord.Interaction):
        from src.helpers.tickets.ticket_core import create_ticket

        if interaction.guild is None or not isinstance(interaction.user, discord.Member):
            await interaction.response.send_message(
                view=build_notice("❌ Este painel só pode ser usado dentro de um servidor.", discord.Colour.red()),
                ephemeral=True,
            )
            return

        await interaction.response.defer(ephemeral=True, thinking=True)
        config = await interaction.client.db.get_config(interaction.guild.id)
        panel = config.get("ticket_panels", {}).get(self.panel_key, {})
        categories = panel.get("categories", [])
        if self.index >= len(categories):
            await interaction.followup.send(
                view=build_notice("Este botão pertence a um painel desatualizado. Peça à equipe para publicar o painel novamente.", discord.Colour.orange()),
                ephemeral=True,
            )
            return

        category = categories[self.index]
        category_label = category.get("label", "Geral")
        category_message = category.get("ticket_message", "")

        channel = await create_ticket(
            interaction.client, interaction.guild, interaction.user, category_label, self.panel_key,
            category_ticket_message=category_message,
        )
        if channel is None:
            await interaction.followup.send(view=build_notice("❌ Você já possui um ticket aberto.", discord.Colour.red()), ephemeral=True)
            return
        await interaction.followup.send(view=build_notice(f"✅ Ticket criado: {channel.mention}", discord.Colour.green()), ephemeral=True)


class TicketPanelView(SafeLayoutView):
    def __init__(self, panel_key: str, panel: dict):
        super().__init__(timeout=None)
        categories = panel.get("categories") or []

        try:
            accent_colour = discord_colour(panel.get("accent_color"))
        except ValueError:
            accent_colour = None
        try:
            image_position = normalize_image_position(
                panel.get("image_position"), default="inside"
            )
        except ValueError:
            image_position = "inside"

        container = discord.ui.Container(accent_colour=accent_colour)

        title = str(panel.get("title") or panel.get("name") or "Atendimento")
        intro_lines = [f"# {title}"]
        subtitle = str(panel.get("subtitle") or "").strip()
        if subtitle:
            intro_lines.append(f"*{subtitle}*")
        welcome = panel.get("welcome")
        if welcome:
            intro_lines += ["", welcome]

        show_atendemos = len(categories) > 1 or any(c.get("description") for c in categories)
        if categories and show_atendemos:
            intro_lines += ["", "📌 **ATENDEMOS:**"]
            for category in categories[:MAX_CATEGORIES]:
                intro_lines.append(f"\n{category.get('emoji', '📁')}・**{category.get('label', 'Categoria')}**")
                if category.get("description"):
                    intro_lines.append(f"«{category['description']}»")
        container.add_item(discord.ui.TextDisplay("\n".join(intro_lines)))

        rules = panel.get("rules") or []
        if rules:
            container.add_item(discord.ui.Separator())
            rules_lines = ["🔒 **ATENÇÃO**"] + [f"• {rule}" for rule in rules]
            container.add_item(discord.ui.TextDisplay("\n".join(rules_lines)))

        footer = panel.get("footer")
        if footer:
            container.add_item(discord.ui.Separator())
            container.add_item(discord.ui.TextDisplay(footer))

        image_url = panel.get("image_url")
        if isinstance(image_url, str) and image_url:
            image_gallery = discord.ui.MediaGallery(
                discord.MediaGalleryItem(media=image_url)
            )
            if image_position == "outside":
                self.add_item(image_gallery)
            else:
                container.add_item(image_gallery)

        if categories:
            row = discord.ui.ActionRow()
            for index, category in enumerate(categories[:MAX_CATEGORIES]):
                row.add_item(TicketPanelButton(
                    panel_key,
                    index,
                    label=category.get("label", "Categoria"),
                    emoji=category.get("emoji"),
                    style=category.get("style", DEFAULT_BUTTON_STYLE),
                ))
            container.add_item(row)

        self.add_item(container)
