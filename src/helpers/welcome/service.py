from __future__ import annotations

from urllib.parse import urlparse

import discord

from src.utils.appearance import discord_colour, normalize_image_position


class WelcomeService:
    @staticmethod
    def render_message(template: str, member: discord.Member) -> str:
        guild = member.guild
        replacements = {
            "{member}": member.mention,
            "{member_name}": discord.utils.escape_markdown(member.display_name),
            "{server}": discord.utils.escape_markdown(guild.name),
            "{member_count}": str(guild.member_count or 0),
        }
        rendered = template
        for placeholder, value in replacements.items():
            rendered = rendered.replace(placeholder, value)
        return rendered[:4000]

    @staticmethod
    def build_view(
        template: str,
        member: discord.Member,
        image_url: str | None = None,
        accent_color: str | None = None,
        image_position: str = "outside",
    ) -> discord.ui.LayoutView:
        view = discord.ui.LayoutView(timeout=None)
        image_gallery = None
        if isinstance(image_url, str) and image_url:
            parsed = urlparse(image_url)
            if parsed.scheme == "https" and parsed.netloc:
                image_gallery = discord.ui.MediaGallery(
                    discord.MediaGalleryItem(media=image_url)
                )

        try:
            accent_colour = discord_colour(accent_color)
        except ValueError:
            accent_colour = None
        try:
            position = normalize_image_position(image_position, default="outside")
        except ValueError:
            position = "outside"

        if image_gallery is not None and position == "outside":
            view.add_item(image_gallery)

        container = discord.ui.Container(
            discord.ui.TextDisplay(WelcomeService.render_message(template, member)),
            accent_colour=accent_colour,
        )
        if image_gallery is not None and position == "inside":
            container.add_item(image_gallery)
        view.add_item(container)
        return view
