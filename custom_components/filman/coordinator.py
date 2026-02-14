from __future__ import annotations

from typing import Dict, List, Any
import logging
from datetime import timedelta

from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.dispatcher import async_dispatcher_send

from .const import CONF_SPOOLMAN_URL, CONF_SPOOLMAN_API_KEY, DOMAIN, UPDATE_SIGNAL

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

    def _base_url(self) -> str | None:
        return (self.entry.options or {}).get(CONF_SPOOLMAN_URL) or self.entry.data.get(
            CONF_SPOOLMAN_URL
        )

    def _headers(self) -> dict[str, str]:
        headers: dict[str, str] = {}
        key = (self.entry.options or {}).get(CONF_SPOOLMAN_API_KEY) or self.entry.data.get(
            CONF_SPOOLMAN_API_KEY
        )
        if key:
            headers["Authorization"] = f"Bearer {key}"
        return headers

    async def _async_request(self, method: str, path: str, json_body: dict | None = None):
        """Low-level request helper. Returns parsed JSON or None."""
        url = self._base_url()
        if not url:
            return None

        api = f"{url.rstrip('/')}{path}"
        session = async_get_clientsession(self.hass)
        headers = self._headers()

        async with session.request(
            method,
            api,
            timeout=20,
            headers=headers,
            json=json_body,
        ) as resp:
            if resp.status < 200 or resp.status >= 300:
                _LOGGER.warning("Spoolman HTTP %s for %s %s", resp.status, method, api)
                return None
            try:
                return await resp.json()
            except Exception:
                return None

    async def _async_fetch(self, path: str):
        return await self._async_request("GET", path)

    async def _async_patch(self, path: str, payload: dict):
        return await self._async_request("PATCH", path, json_body=payload)

    async def async_set_filament_count(self, filament_id: int, count: int) -> bool:
        """Update filament.extra.count in Spoolman.

        Note: Spoolman treats `extra` as replace-on-write. If you send `extra`, any existing
        extra fields are replaced with what you send (so we GET first, mutate, then PATCH).
        """
        filament = await self._async_fetch(f"/api/v1/filament/{filament_id}")
        if not isinstance(filament, dict):
            return False

        extra = filament.get("extra") or {}
        if not isinstance(extra, dict):
            extra = {}

        extra["count"] = int(count)

        updated = await self._async_patch(
            f"/api/v1/filament/{filament_id}",
            {"extra": extra},
        )
        if not isinstance(updated, dict):
            return False

        # Update local coordinator cache for any spools that reference this filament_id
        data = dict(self.data or {})
        changed = False
        for sid, sp in data.items():
            fil = sp.get("filament") or {}
            if fil.get("id") != filament_id:
                continue

            fil = dict(fil)
            fil["count"] = int(count)
            fil["extra"] = extra
            sp = dict(sp)
            sp["filament"] = fil
            data[sid] = sp
            changed = True

        if changed:
            self.async_set_updated_data(data)
            async_dispatcher_send(self.hass, UPDATE_SIGNAL, None)

        return True

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

            fil: dict[str, Any] = sp.get("filament") or {}
            filament_id = fil.get("id")

            vendor = (fil.get("vendor") or {}).get("name")
            color = fil.get("name") or fil.get("color_name")
            ftype = fil.get("material") or fil.get("name")

            density = fil.get("density")  # g/cm³

            extra = fil.get("extra") or {}
            if not isinstance(extra, dict):
                extra = {}

            count = extra.get("count")

            by_id[sid] = {
                "id": sid,
                "location": sp.get("location"),
                "archived": sp.get("archived", False),
                "manufacturer": vendor,
                "color": color,
                "filament_type": ftype,
                "filament": {
                    "id": filament_id,
                    "density": density,
                    "count": count,
                    "extra": extra,
                },
            }

        return by_id
