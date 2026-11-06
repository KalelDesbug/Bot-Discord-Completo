from __future__ import annotations

import re
from typing import Any


_HEX_COLOR_PATTERN = re.compile(r"^[0-9a-fA-F]{6}$")
_IMAGE_POSITIONS = frozenset({"inside", "outside"})


def normalize_hex_color(value: Any) -> str | None:
    """Normalize an optional HEX RGB color to #RRGGBB."""
    if value is None:
        return None
    if not isinstance(value, str):
        raise ValueError("A cor precisa estar no formato HEX, como #5865F2.")

    cleaned = value.strip()
    if not cleaned:
        return None
    if cleaned.startswith("#"):
        cleaned = cleaned[1:]
    if len(cleaned) == 3 and re.fullmatch(r"[0-9a-fA-F]{3}", cleaned):
        cleaned = "".join(character * 2 for character in cleaned)
    if not _HEX_COLOR_PATTERN.fullmatch(cleaned):
        raise ValueError("A cor precisa estar no formato HEX, como #5865F2.")
    return f"#{cleaned.upper()}"


def normalize_image_position(value: Any, *, default: str = "outside") -> str:
    if value is None:
        return default
    if isinstance(value, str) and value in _IMAGE_POSITIONS:
        return value
    raise ValueError("A posição da imagem precisa ser 'inside' ou 'outside'.")


def discord_colour(value: Any):
    """Convert a stored HEX value to discord.Colour without requiring it here."""
    normalized = normalize_hex_color(value)
    if normalized is None:
        return None

    import discord

    return discord.Colour(int(normalized[1:], 16))
