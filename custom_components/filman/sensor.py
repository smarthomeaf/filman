from __future__ import annotations

from typing import Any, List
import logging

from homeassistant.components.sensor import SensorEntity, SensorDeviceClass
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.dispatcher import async_dispatcher_connect

from .const import DOMAIN, UPDATE_SIGNAL
from .coordinator import FilmanCoordinator

_LOGGER = logging.getLogger(__name__)

# Unit fallback for older HA versions
try:
    from homeassistant.const import UnitOfDensity

    DENSITY_UNIT = UnitOfDensity.GRAMS_PER_CUBIC_CENTIMETER
except Exception:
    DENSITY_UNIT = "g/cm³"

# Device class fallback for older HA versions
try:
    DENSITY_DEVICE_CLASS = SensorDeviceClass.DENSITY
except Exception:
    DENSITY_DEVICE_CLASS = None


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    data = hass.data[DOMAIN][entry.entry_id]
    coord: FilmanCoordinator = data["coordinator"]

    # Ensure we have data before creating entities
    await coord.async_config_entry_first_refresh()

    entities: List[SensorEntity] = []
    for _, sp in (coord.data or {}).items():
        entities.extend(
            [
                FilmanManufacturerSensor(hass, entry, coord, sp),
                FilmanColorSensor(hass, entry, coord, sp),
                FilmanTypeSensor(hass, entry, coord, sp),
                FilmanDensitySensor(hass, entry, coord, sp),
                FilmanCountSensor(hass, entry, coord, sp),  # NEW
                FilmanHumiditySensor(hass, entry, coord, sp),
                FilmanTemperatureSensor(hass, entry, coord, sp),
            ]
        )

    if not entities:
        _LOGGER.warning(
            "No spools returned from coordinator; no entities created. "
            "Check Spoolman URL and that /api/v1/spool?archived=false returns data."
        )
        return

    async_add_entities(entities, update_before_add=True)


class _BaseFilmanSensor(SensorEntity):
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

    @property
    def available(self) -> bool:
        # Keep as-is (you can optionally tie this to coord.last_update_success later)
        return True

    @callback
    def _on_update(self, spool_id: str | None = None) -> None:
        # Dispatcher may fire with no args; don't crash
        if spool_id is not None and spool_id != self.spool_id:
            return
        self.async_write_ha_state()


class FilmanManufacturerSensor(_BaseFilmanSensor):
    _attr_name = "Manufacturer"
    _attr_icon = "mdi:factory"

    def __init__(self, hass, entry, coord, spool) -> None:
        super().__init__(hass, entry, coord, spool)
        self._attr_unique_id = f"{DOMAIN}_{self.spool_id}_manufacturer"

    @property
    def native_value(self):
        d = (self.coord.data or {}).get(int(self.spool_id)) or {}
        return d.get("manufacturer")


class FilmanColorSensor(_BaseFilmanSensor):
    _attr_name = "Color"
    _attr_icon = "mdi:palette"

    def __init__(self, hass, entry, coord, spool) -> None:
        super().__init__(hass, entry, coord, spool)
        self._attr_unique_id = f"{DOMAIN}_{self.spool_id}_color"

    @property
    def native_value(self):
        d = (self.coord.data or {}).get(int(self.spool_id)) or {}
        return d.get("color")


class FilmanTypeSensor(_BaseFilmanSensor):
    _attr_name = "Filament Type"
    _attr_icon = "mdi:alpha-t-box-outline"

    def __init__(self, hass, entry, coord, spool) -> None:
        super().__init__(hass, entry, coord, spool)
        self._attr_unique_id = f"{DOMAIN}_{self.spool_id}_type"

    @property
    def native_value(self):
        d = (self.coord.data or {}).get(int(self.spool_id)) or {}
        return d.get("filament_type")


class FilmanDensitySensor(_BaseFilmanSensor):
    """Density sourced from filament.density (g/cm³)."""

    _attr_name = "Density"
    _attr_icon = "mdi:weight"
    _attr_native_unit_of_measurement = DENSITY_UNIT
    _attr_device_class = DENSITY_DEVICE_CLASS  # None is OK on older HA versions

    def __init__(self, hass, entry, coord, spool) -> None:
        super().__init__(hass, entry, coord, spool)
        self._attr_unique_id = f"{DOMAIN}_{self.spool_id}_density"
        self.async_on_remove(
            async_dispatcher_connect(self.hass, UPDATE_SIGNAL, self._on_update)
        )

    @property
    def native_value(self):
        d = (self.coord.data or {}).get(int(self.spool_id)) or {}
        filament = d.get("filament") or {}
        val = filament.get("density")

        if val is None or val == "":
            return None

        try:
            return float(val)
        except (ValueError, TypeError):
            return None


class FilmanCountSensor(_BaseFilmanSensor):
    """Count sourced from filament.count (unitless)."""

    _attr_name = "Count"
    _attr_icon = "mdi:counter"

    def __init__(self, hass, entry, coord, spool) -> None:
        super().__init__(hass, entry, coord, spool)
        self._attr_unique_id = f"{DOMAIN}_{self.spool_id}_count"
        self.async_on_remove(
            async_dispatcher_connect(self.hass, UPDATE_SIGNAL, self._on_update)
        )

    @property
    def native_value(self):
        d = (self.coord.data or {}).get(int(self.spool_id)) or {}
        filament = d.get("filament") or {}
        val = filament.get("count")

        if val is None or val == "":
            return None

        try:
            return int(val)
        except (ValueError, TypeError):
            # Sometimes APIs send floats/strings; try float->int as a last resort
            try:
                return int(float(val))
            except (ValueError, TypeError):
                return None


class FilmanHumiditySensor(_BaseFilmanSensor):
    _attr_name = "Humidity"
    _attr_icon = "mdi:water-percent"
    _attr_device_class = SensorDeviceClass.HUMIDITY

    def __init__(self, hass, entry, coord, spool) -> None:
        super().__init__(hass, entry, coord, spool)
        self._attr_unique_id = f"{DOMAIN}_{self.spool_id}_humidity"
        self._store = hass.data[DOMAIN][entry.entry_id]["store"]
        self.async_on_remove(
            async_dispatcher_connect(self.hass, UPDATE_SIGNAL, self._on_update)
        )

    @property
    def native_unit_of_measurement(self):
        return "%"

    @property
    def native_value(self):
        rec = (self._store.all().get(self.spool_id) or {})
        eid = rec.get("humidity_entity_id")
        if not eid:
            return 0
        st = self.hass.states.get(eid)
        if st is None:
            return 0
        try:
            return float(st.state)
        except (ValueError, TypeError):
            return 0


class FilmanTemperatureSensor(_BaseFilmanSensor):
    _attr_name = "Temperature"
    _attr_icon = "mdi:thermometer"
    _attr_device_class = SensorDeviceClass.TEMPERATURE

    def __init__(self, hass, entry, coord, spool) -> None:
        super().__init__(hass, entry, coord, spool)
        self._attr_unique_id = f"{DOMAIN}_{self.spool_id}_temperature"
        self._store = hass.data[DOMAIN][entry.entry_id]["store"]
        self.async_on_remove(
            async_dispatcher_connect(self.hass, UPDATE_SIGNAL, self._on_update)
        )

    @property
    def native_unit_of_measurement(self):
        return "°F"

    @property
    def native_value(self):
        rec = (self._store.all().get(self.spool_id) or {})
        eid = rec.get("temperature_entity_id")
        if not eid:
            return 0
        st = self.hass.states.get(eid)
        if st is None:
            return 0
        try:
            return float(st.state)
        except (ValueError, TypeError):
            return 0
