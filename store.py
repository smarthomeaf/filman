
from __future__ import annotations
from typing import Any, Dict
from homeassistant.core import HomeAssistant
from homeassistant.helpers.storage import Store
from homeassistant.config_entries import ConfigEntry
from .const import DOMAIN

class FilmanStore:
    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        self.hass = hass
        self.entry = entry
        self._store = Store(hass, 1, f"{DOMAIN}_{entry.entry_id}.json")
        self._data: Dict[str, Dict[str, Any]] = {}

    async def async_load(self) -> None:
        data = await self._store.async_load()
        self._data = data or {}

    async def async_save(self) -> None:
        await self._store.async_save(self._data)

    def all(self) -> Dict[str, Dict[str, Any]]:
        return self._data

    async def update(self, spool_id: str, **kwargs: Any) -> None:
        cur = dict(self._data.get(spool_id) or {})
        cur.update(kwargs)
        self._data[spool_id] = cur
        await self.async_save()
