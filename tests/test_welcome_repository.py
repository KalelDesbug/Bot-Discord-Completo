from __future__ import annotations

import pytest

from src.utils.db.welcome import WelcomeRepository


class FakeCollection:
    def __init__(self) -> None:
        self.document: dict | None = None

    async def find_one(self, query: dict) -> dict | None:
        assert query == {"_id": query["_id"]}
        return dict(self.document) if self.document else None

    async def update_one(self, query: dict, update: dict, upsert: bool = False) -> None:
        assert upsert is True
        if self.document is None:
            self.document = {"_id": query["_id"]}
        self.document.update(update["$set"])


@pytest.mark.asyncio
async def test_welcome_defaults_have_no_channel_until_configured() -> None:
    repo = WelcomeRepository()
    repo.welcome_settings = FakeCollection()

    settings = await repo.get_welcome_settings(123)

    assert settings == {
        "welcome_channel_id": None,
        "welcome_message": "",
        "welcome_image_url": None,
        "welcome_accent_color": None,
        "welcome_image_position": "outside",
        "welcome_enabled": False,
    }


@pytest.mark.asyncio
async def test_welcome_update_persists_only_allowed_fields() -> None:
    repo = WelcomeRepository()
    repo.welcome_settings = FakeCollection()

    await repo.update_welcome_settings(
        123,
        {
            "welcome_channel_id": 456,
            "welcome_message": "Olá, {member}!",
            "welcome_accent_color": "#a1b",
            "welcome_image_position": "inside",
            "welcome_enabled": True,
        },
    )
    settings = await repo.get_welcome_settings(123)

    assert settings["welcome_channel_id"] == 456
    assert settings["welcome_message"] == "Olá, {member}!"
    assert settings["welcome_accent_color"] == "#AA11BB"
    assert settings["welcome_image_position"] == "inside"
    assert settings["welcome_enabled"] is True


@pytest.mark.asyncio
async def test_welcome_rejects_invalid_channel_and_image_urls() -> None:
    repo = WelcomeRepository()
    repo.welcome_settings = FakeCollection()

    with pytest.raises(ValueError):
        await repo.update_welcome_settings(123, {"welcome_channel_id": "456"})
    with pytest.raises(ValueError):
        await repo.update_welcome_settings(
            123,
            {"welcome_image_url": "http://example.com/image.png"},
        )
    with pytest.raises(ValueError):
        await repo.update_welcome_settings(123, {"unexpected": True})
    with pytest.raises(ValueError):
        await repo.update_welcome_settings(123, {"welcome_accent_color": "red"})
    with pytest.raises(ValueError):
        await repo.update_welcome_settings(123, {"welcome_image_position": "center"})


@pytest.mark.asyncio
async def test_welcome_message_supports_eros_length_limit() -> None:
    repo = WelcomeRepository()
    repo.welcome_settings = FakeCollection()
    message = "x" * (1000 - len("{member}")) + "{member}"

    await repo.update_welcome_settings(123, {"welcome_message": message})
    settings = await repo.get_welcome_settings(123)

    assert settings["welcome_message"] == message

    with pytest.raises(ValueError):
        await repo.update_welcome_settings(123, {"welcome_message": "x" * 1001})


@pytest.mark.asyncio
async def test_welcome_accepts_empty_draft_without_enabling_automation() -> None:
    repo = WelcomeRepository()
    repo.welcome_settings = FakeCollection()

    await repo.update_welcome_settings(123, {
        "welcome_channel_id": None,
        "welcome_message": "",
        "welcome_image_url": None,
    })
    settings = await repo.get_welcome_settings(123)

    assert settings["welcome_channel_id"] is None
    assert settings["welcome_message"] == ""
    assert settings["welcome_enabled"] is False


@pytest.mark.asyncio
async def test_legacy_eros_welcome_default_is_cleared() -> None:
    repo = WelcomeRepository()
    repo.welcome_settings = FakeCollection()
    repo.welcome_settings.document = {
        "_id": 321,
        "welcome_channel_id": 654,
        "welcome_message": "Boas-vindas, {member}!",
        "welcome_image_url": None,
        "welcome_enabled": True,
    }

    settings = await repo.get_welcome_settings(321)

    assert settings["welcome_message"] == ""
    assert settings["welcome_enabled"] is False
