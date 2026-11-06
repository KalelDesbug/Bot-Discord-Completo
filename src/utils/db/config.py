from __future__ import annotations

import time
from typing import Any

from src.helpers.tickets.panel_config import normalize_panels
from src.utils.database_defaults import CONFIG_CACHE_TTL, MAX_TICKET_PANELS, default_config


class ConfigRepository:
    async def get_config(self, guild_id: int) -> dict:
        cached = self._config_cache.get(guild_id)
        if cached and time.monotonic() - cached[1] < CONFIG_CACHE_TTL:
            return cached[0]

        document = await self.config.find_one({"_id": guild_id})
        if document is None:
            defaults = default_config(guild_id)
            try:
                await self.config.insert_one(defaults)
                document = defaults
            except ValueError:
                document = await self.config.find_one({"_id": guild_id})
                if document is None:
                    raise

        config = default_config(guild_id)
        for key in ("ticket_category_id", "ticket_staff_role_ids", "ticket_log_channel_id"):
            if key in document:
                config[key] = document[key]

        panels, changed = normalize_panels(document.get("ticket_panels", {}))
        config["ticket_panels"] = panels
        if changed:
            await self.config.update_one(
                {"_id": guild_id},
                {"$set": {"ticket_panels": panels}},
                upsert=True,
            )

        self._config_cache[guild_id] = (config, time.monotonic())
        if len(self._config_cache) > 512:
            oldest_guild_id = next(iter(self._config_cache))
            if oldest_guild_id != guild_id:
                self._config_cache.pop(oldest_guild_id, None)
        return config

    async def update_config(self, guild_id: int, data: dict[str, Any]) -> None:
        allowed = {
            "ticket_category_id",
            "ticket_staff_role_ids",
            "ticket_log_channel_id",
            "ticket_panels",
        }
        unknown = set(data) - allowed
        if unknown:
            raise ValueError(
                f"Campos de configuração desconhecidos: {', '.join(sorted(unknown))}"
            )
        if not data:
            return

        if "ticket_panels" in data:
            panels, changed = normalize_panels(data["ticket_panels"])
            if changed and panels != data["ticket_panels"]:
                raise ValueError("A lista de painéis contém dados inválidos ou excede os limites.")
            if len(panels) > MAX_TICKET_PANELS:
                raise ValueError(f"O servidor pode ter até {MAX_TICKET_PANELS} painéis.")
            data = {**data, "ticket_panels": panels}

        await self.config.update_one({"_id": guild_id}, {"$set": data}, upsert=True)
        self._config_cache.pop(guild_id, None)
