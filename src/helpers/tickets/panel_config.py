from __future__ import annotations

import re
import unicodedata
from typing import Any

from src.utils.database_defaults import LEGACY_PRESET_PANEL_KEYS, MAX_PANEL_CATEGORIES, MAX_TICKET_PANELS
from src.utils.appearance import normalize_hex_color, normalize_image_position

_PANEL_KEY_PATTERN = re.compile(r"^[a-z0-9_]{1,32}$")


def make_panel_key(name: str, existing: dict[str, Any]) -> str:
    """Create a short, Discord-custom-id-safe key unique within a guild."""
    normalized = unicodedata.normalize("NFKD", name)
    ascii_name = normalized.encode("ascii", "ignore").decode("ascii").lower()
    base = re.sub(r"[^a-z0-9]+", "_", ascii_name).strip("_")[:32] or "painel"
    candidate = base
    suffix = 2
    while candidate in existing:
        tail = f"_{suffix}"
        candidate = f"{base[:32 - len(tail)]}{tail}"
        suffix += 1
    if not _PANEL_KEY_PATTERN.fullmatch(candidate):
        raise ValueError("Não foi possível gerar um identificador válido para o painel.")
    return candidate


def build_empty_panel(name: str) -> dict[str, Any]:
    clean_name = name.strip()
    if not 1 <= len(clean_name) <= 80:
        raise ValueError("O nome do painel precisa ter entre 1 e 80 caracteres.")
    return {
        "name": clean_name,
        "title": "",
        "subtitle": "",
        "welcome": "",
        "rules": [],
        "footer": None,
        "image_url": None,
        "accent_color": None,
        "image_position": "inside",
        "channel_ids": [],
        "message_ids": {},
        "categories": [],
        "created_by_user": True,
    }


def normalize_panels(panels: Any) -> tuple[dict[str, dict[str, Any]], bool]:
    """Remove legacy Eros presets and fills only structural, content-free fields."""
    if not isinstance(panels, dict):
        return {}, bool(panels)

    normalized: dict[str, dict[str, Any]] = {}
    changed = False
    for key, raw_panel in panels.items():
        if not isinstance(key, str) or not _PANEL_KEY_PATTERN.fullmatch(key):
            changed = True
            continue
        if key in LEGACY_PRESET_PANEL_KEYS and not (
            isinstance(raw_panel, dict) and raw_panel.get("created_by_user") is True
        ):
            changed = True
            continue
        if not isinstance(raw_panel, dict):
            changed = True
            continue

        panel = dict(raw_panel)
        defaults = {
            "name": key.replace("_", " ").title(),
            "title": "",
            "subtitle": "",
            "welcome": "",
            "rules": [],
            "footer": None,
            "image_url": None,
            "accent_color": None,
            "image_position": "inside",
            "channel_ids": [],
            "message_ids": {},
            "categories": [],
            "created_by_user": True,
        }
        for field, value in defaults.items():
            if field not in panel:
                panel[field] = value
                changed = True
        try:
            normalized_color = normalize_hex_color(panel.get("accent_color"))
        except ValueError:
            normalized_color = None
        if panel.get("accent_color") != normalized_color:
            panel["accent_color"] = normalized_color
            changed = True

        try:
            normalized_position = normalize_image_position(
                panel.get("image_position"), default="inside"
            )
        except ValueError:
            normalized_position = "inside"
        if panel.get("image_position") != normalized_position:
            panel["image_position"] = normalized_position
            changed = True

        if not isinstance(panel.get("categories"), list):
            panel["categories"] = []
            changed = True
        if len(panel["categories"]) > MAX_PANEL_CATEGORIES:
            panel["categories"] = panel["categories"][:MAX_PANEL_CATEGORIES]
            changed = True
        if not isinstance(panel.get("channel_ids"), list):
            panel["channel_ids"] = []
            changed = True
        if not isinstance(panel.get("message_ids"), dict):
            panel["message_ids"] = {}
            changed = True
        normalized[key] = panel

    if len(normalized) > MAX_TICKET_PANELS:
        normalized = dict(list(normalized.items())[:MAX_TICKET_PANELS])
        changed = True
    return normalized, changed
