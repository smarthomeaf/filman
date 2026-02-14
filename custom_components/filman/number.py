from __future__ import annotations

from typing import Any, List
import logging

from homeassistant.components.number import NumberEntity, NumberMode
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.dispatcher import async_dispatcher_connect

from .const import DOMAIN, UPDATE_SIGNAL
from .coordinator import FilmanCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    data = hass.data[DOMAIN][entry.entry_id]
    coord: FilmanCoordinator = data["coordinator"]

    await coord.async_config_entry_first_refresh()

    entities: List[NumberEntity] = []
    for _, sp in (coord.data or {}).items():
        filament = sp.get("filament") or {}
        if filament.get("id") is None:
            continue
        entities.append(FilmanCountControl(hass, entry, coord, sp))

    if entities:
        async_add_entities(entities, update_before_add=True)


class _BaseFilmanNumber(NumberEntity):
    _attr_has_entity_name = True

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        coord: FilmanCoordinator,
        spool: dict[str, Any],
    ) -> None:
        self.hass = hass
        self.entry = entry
        self.coord = coord
        self.spool = spool
        self.spool_id = str(spool["id"])

    @property
    def device_info(self) -> DeviceInfo:
        return DeviceInfo(
            identifiers={(DOMAIN, self.spool_id)},
            name=f"Spool {self.spool_id}",
            manufacturer=self.spool.get("manufacturer") or "Unknown",
            model=str(self.spool.get("filament_type") or "Filament"),
            suggested_area=self.spool.get("location") or None,
        )

    @callback
    def _on_update(self, spool_id: str | None = None) -> None:
        if spool_id is not None and spool_id != self.spool_id:
            return
        self.async_write_ha_state()


class FilmanCountControl(_BaseFilmanNumber):
    """Writable control for filament.extra.count (stored on the filament object)."""

    _attr_name = "Count Control"
    _attr_icon = "mdi:counter"
    _attr_mode = NumberMode.BOX

    _attr_native_min_value = 0
    _attr_native_max_value = 999
    _attr_native_step = 1

    def __init__(self, hass, entry, coord, spool) -> None:
        super().__init__(hass, entry, coord, spool)
        self._attr_unique_id = f"{DOMAIN}_{self.spool_id}_count_control"
        self.async_on_remove(
            async_dispatcher_connect(self.hass, UPDATE_SIGNAL, self._on_update)
        )

    @property
    def native_value(self) -> float | None:
        d = (self.coord.data or {}).get(int(self.spool_id)) or {}
        filament = d.get("filament") or {}
        val = filament.get("count")

        if val is None or val == "":
            return None

        try:
            return float(int(val))
        except (ValueError, TypeError):
            return None

    async def async_set_native_value(self, value: float) -> None:
        d = (self.coord.data or {}).get(int(self.spool_id)) or {}
        filament = d.get("filament") or {}
        filament_id = filament.get("id")
        if filament_id is None:
            _LOGGER.warning("Cannot set count: missing filament.id for spool %s", self.spool_id)
            return

        ok = await self.coord.async_set_filament_count(int(filament_id), int(value))
        if not ok:
            _LOGGER.warning("Failed to set filament count for filament_id=%s", filament_id)
