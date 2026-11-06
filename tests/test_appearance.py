from __future__ import annotations

import pytest

from src.utils.appearance import normalize_hex_color, normalize_image_position


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("#5865f2", "#5865F2"),
        ("5865F2", "#5865F2"),
        ("#abc", "#AABBCC"),
        ("", None),
        (None, None),
    ],
)
def test_hex_color_normalization(raw, expected) -> None:
    assert normalize_hex_color(raw) == expected


@pytest.mark.parametrize("raw", ["red", "#12", "#12345G", 123456])
def test_invalid_hex_color_is_rejected(raw) -> None:
    with pytest.raises(ValueError):
        normalize_hex_color(raw)


@pytest.mark.parametrize("position", ["inside", "outside"])
def test_image_position_values(position) -> None:
    assert normalize_image_position(position) == position


def test_image_position_rejects_unknown_values() -> None:
    with pytest.raises(ValueError):
        normalize_image_position("center")
