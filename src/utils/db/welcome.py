from __future__ import annotations

from urllib.parse import urlparse

from src.utils.appearance import normalize_hex_color, normalize_image_position


LEGACY_WELCOME_MESSAGE = "Boas-vindas, {member}!"


class WelcomeRepository:
    """Persistência das configurações de boas-vindas por servidor."""

    _ALLOWED_FIELDS = {
        "welcome_channel_id",
        "welcome_message",
        "welcome_image_url",
        "welcome_accent_color",
        "welcome_image_position",
        "welcome_enabled",
    }

    @staticmethod
    def _defaults() -> dict:
        return {
            "welcome_channel_id": None,
            "welcome_message": "",
            "welcome_image_url": None,
            "welcome_accent_color": None,
            "welcome_image_position": "outside",
            "welcome_enabled": False,
        }

    async def get_welcome_settings(self, guild_id: int) -> dict:
        if type(guild_id) is not int or guild_id <= 0:
            raise ValueError("ID do servidor inválido.")

        document = await self.welcome_settings.find_one({"_id": guild_id})
        settings = self._defaults()
        if document:
            for key in self._ALLOWED_FIELDS:
                if key in document:
                    settings[key] = document[key]

            try:
                settings["welcome_accent_color"] = normalize_hex_color(
                    settings.get("welcome_accent_color")
                )
            except ValueError:
                settings["welcome_accent_color"] = None

            try:
                settings["welcome_image_position"] = normalize_image_position(
                    settings.get("welcome_image_position"), default="outside"
                )
            except ValueError:
                settings["welcome_image_position"] = "outside"

            # Remove the old automatic Eros greeting instead of treating it as user content.
            stored_message = settings.get("welcome_message")
            legacy_default = (
                isinstance(stored_message, str)
                and stored_message.strip() == LEGACY_WELCOME_MESSAGE
            )
            if not isinstance(stored_message, str) or legacy_default:
                settings["welcome_message"] = ""
            if not settings["welcome_message"].strip() and settings["welcome_enabled"]:
                settings["welcome_enabled"] = False
            if legacy_default or not isinstance(stored_message, str) or (
                not settings["welcome_message"].strip()
                and bool(document.get("welcome_enabled", False))
            ):
                await self.welcome_settings.update_one(
                    {"_id": guild_id},
                    {"$set": {
                        "welcome_message": settings["welcome_message"],
                        "welcome_enabled": settings["welcome_enabled"],
                    }},
                    upsert=True,
                )

        settings["welcome_enabled"] = bool(settings["welcome_enabled"])
        return settings

    async def update_welcome_settings(self, guild_id: int, data: dict) -> None:
        if type(guild_id) is not int or guild_id <= 0:
            raise ValueError("ID do servidor inválido.")
        if not isinstance(data, dict) or not data:
            raise ValueError("Informe ao menos uma configuração.")

        unknown = set(data) - self._ALLOWED_FIELDS
        if unknown:
            raise ValueError(
                "Campos de boas-vindas desconhecidos: " + ", ".join(sorted(unknown))
            )

        validated = dict(data)
        channel_id = validated.get("welcome_channel_id")
        if "welcome_channel_id" in validated and channel_id is not None:
            if type(channel_id) is not int or channel_id <= 0:
                raise ValueError("ID do canal de boas-vindas inválido.")

        if "welcome_message" in validated:
            message = validated["welcome_message"]
            if not isinstance(message, str) or len(message) > 1000:
                raise ValueError("A mensagem precisa ter no máximo 1.000 caracteres.")
            validated["welcome_message"] = message.strip()

        image_url = validated.get("welcome_image_url")
        if "welcome_image_url" in validated and image_url is not None:
            if not isinstance(image_url, str) or len(image_url) > 2048:
                raise ValueError("URL da imagem inválida.")
            parsed = urlparse(image_url)
            if parsed.scheme != "https" or not parsed.netloc:
                raise ValueError("A imagem precisa ser uma URL HTTPS válida.")

        if "welcome_accent_color" in validated:
            validated["welcome_accent_color"] = normalize_hex_color(
                validated["welcome_accent_color"]
            )

        if "welcome_image_position" in validated:
            validated["welcome_image_position"] = normalize_image_position(
                validated["welcome_image_position"], default="outside"
            )

        enabled = validated.get("welcome_enabled")
        if "welcome_enabled" in validated and type(enabled) is not bool:
            raise ValueError("O estado de boas-vindas precisa ser booleano.")
        current = await self.get_welcome_settings(guild_id)
        channel = validated.get("welcome_channel_id", current["welcome_channel_id"])
        message = validated.get("welcome_message", current["welcome_message"])
        if validated.get("welcome_enabled") is True:
            if not channel or not isinstance(message, str) or not message.strip():
                raise ValueError("Configure e salve o canal e a mensagem antes de ativar.")
        elif any(field in validated for field in ("welcome_channel_id", "welcome_message")):
            if not channel or not isinstance(message, str) or not message.strip():
                if current.get("welcome_enabled"):
                    validated["welcome_enabled"] = False

        await self.welcome_settings.update_one(
            {"_id": guild_id},
            {"$set": validated},
            upsert=True,
        )
