from __future__ import annotations
from typing import Any, Dict
import uuid

from homeassistant.core import HomeAssistant
from homeassistant.helpers.storage import Store

from .const import STORAGE_KEY, STORAGE_VERSION

class SpoolStore:
    def __init__(self, hass: HomeAssistant, entry_id: str) -> None:
        self.hass = hass
        self.entry_id = entry_id
        self._store = Store(hass, STORAGE_VERSION, f"{STORAGE_KEY}_{entry_id}")
        self._data: Dict[str, Dict[str, Any]] = {}

    async def async_load(self) -> None:
        data = await self._store.async_load()
        if isinstance(data, dict):
            self._data = data
        else:
            self._data = {}

    async def _async_save(self) -> None:
        await self._store.async_save(self._data)

    def all(self) -> Dict[str, Dict[str, Any]]:
        return self._data

    async def add(self, **fields) -> str:
        spool_id = str(uuid.uuid4())
        record = {"id": spool_id}
        record.update({
            "name": fields.get("name", f"Spool {spool_id[:6]}"),
            "brand": fields.get("brand", ""),
            "type": fields.get("type", ""),
            "color": fields.get("color", ""),
            "location": fields.get("location", ""),
            "zigbee_device_id": fields.get("zigbee_device_id"),
        })
        self._data[spool_id] = record
        await self._async_save()
        return spool_id

    async def update(self, spool_id: str, **fields) -> None:
        if spool_id not in self._data:
            return
        self._data[spool_id].update(fields)
        await self._async_save()

    async def remove(self, spool_id: str) -> None:
        if spool_id in self._data:
            self._data.pop(spool_id)
            await self._async_save()
