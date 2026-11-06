"""Empty defaults for per-guild ticket configuration."""

from __future__ import annotations

CONFIG_CACHE_TTL = 30
MAX_TICKET_PANELS = 25
MAX_PANEL_CATEGORIES = 4

# Old Eros panel identifiers are removed once when an older SQLite database is read.
# Panels created through the current UI carry ``created_by_user=True`` and are preserved.
LEGACY_PRESET_PANEL_KEYS = frozenset(
    {"suporte", "comprar_cargo", "registro", "conselheiros", "seja_staff"}
)


def default_ticket_panels() -> dict:
    """New guilds start with no panels, categories, sample text or banners."""
    return {}


def default_config(guild_id: int) -> dict:
    return {
        "_id": guild_id,
        "ticket_category_id": None,
        "ticket_staff_role_ids": [],
        "ticket_log_channel_id": None,
        "ticket_panels": {},
    }
