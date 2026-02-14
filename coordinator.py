
from __future__ import annotations
from typing import Any, Dict, List
import logging
from datetime import timedelta

from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import CONF_SPOOLMAN_URL, CONF_SPOOLMAN_API_KEY, DOMAIN

_LOGGER = logging.getLogger(__name__)

class FilmanCoordinator(DataUpdateCoordinator[Dict[int, dict]]):
    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        self.entry = entry
        super().__init__(
            hass,
            _LOGGER,
            name=f"{DOMAIN} coordinator",
            update_interval=timedelta(minutes=5),
        )

    async def _async_fetch(self, path: str):
        url = (self.entry.options or {}).get(CONF_SPOOLMAN_URL) or self.entry.data.get(CONF_SPOOLMAN_URL)
        if not url:
            return None
        api = f"{url.rstrip('/')}{path}"
        session = async_get_clientsession(self.hass)
        headers = {}
        key = (self.entry.options or {}).get(CONF_SPOOLMAN_API_KEY) or self.entry.data.get(CONF_SPOOLMAN_API_KEY)
        if key:
            headers["Authorization"] = f"Bearer {key}"
        async with session.get(api, timeout=20, headers=headers) as resp:
            if resp.status != 200:
                _LOGGER.warning("Spoolman HTTP %s for %s", resp.status, api)
                return None
            return await resp.json()

    async def _async_update_data(self) -> Dict[int, dict]:
        try:
            data = await self._async_fetch("/api/v1/spool?archived=false")
        except Exception as e:
            raise UpdateFailed(str(e)) from e

        items: List[dict] = []
        if isinstance(data, dict) and isinstance(data.get("items"), list):
            items = data["items"]
        elif isinstance(data, list):
            items = data

        by_id: Dict[int, dict] = {}
        for sp in items:
            sid = sp.get("id")
            if sid is None:
                continue
            fil = sp.get("filament") or {}
            vendor = (fil.get("vendor") or {}).get("name")
            color = fil.get("name") or fil.get("color_name")
            ftype = fil.get("material") or fil.get("name")
            by_id[sid] = {
                "id": sid,
                "location": sp.get("location"),
                "archived": sp.get("archived", False),
                "manufacturer": vendor,
                "color": color,
                "filament_type": ftype,
            }
        return by_id
