from __future__ import annotations

from typing import Any, List
import logging

from homeassistant.components.sensor import SensorEntity, SensorDeviceClass
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
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

    await coord.async_config_entry_first_refresh()

    entities: List[SensorEntity] = []
    for sid in (coord.data or {}).keys():
        entities.extend(
            [
                FilmanManufacturerSensor(entry, coord, sid),
                FilmanColorSensor(entry, coord, sid),
                FilmanTypeSensor(entry, coord, sid),
                FilmanDensitySensor(entry, coord, sid),
                FilmanQtySensor(entry, coord, sid),
                FilmanHumiditySensor(hass, entry, coord, sid),
                FilmanTemperatureSensor(hass, entry, coord, sid),
            ]
        )

    if not entities:
        _LOGGER.warning(
            "No spools returned from coordinator; no entities created. "
            "Check Spoolman URL and that /api/v1/spool?archived=false returns data."
        )
        return

    async_add_entities(entities, update_before_add=True)


class _BaseFilmanCoordinatorSensor(CoordinatorEntity[FilmanCoordinator], SensorEntity):
    """Base sensor that updates automatically when the coordinator refreshes."""
    _attr_has_entity_name = True

    def __init__(self, entry: ConfigEntry, coord: FilmanCoordinator, spool_id: int) -> None:
        super().__init__(coord)
        self.entry = entry
        self.spool_id = str(spool_id)

    def _spool(self) -> dict[str, Any]:
        return (self.coordinator.data or {}).get(int(self.spool_id), {}) or {}

    @property
    def device_info(self) -> DeviceInfo:
        d = self._spool()
        return DeviceInfo(
            identifiers={(DOMAIN, self.spool_id)},
            name=f"Spool {self.spool_id}",
            manufacturer=d.get("manufacturer") or "Unknown",
            model=str(d.get("filament_type") or "Filament"),
            suggested_area=d.get("location") or None,
        )


class FilmanManufacturerSensor(_BaseFilmanCoordinatorSensor):
    _attr_name = "Manufacturer"
    _attr_icon = "mdi:factory"

    def __init__(self, entry, coord, spool_id: int) -> None:
        super().__init__(entry, coord, spool_id)
        self._attr_unique_id = f"{DOMAIN}_{self.spool_id}_manufacturer"

    @property
    def native_value(self):
        return self._spool().get("manufacturer")


class FilmanColorSensor(_BaseFilmanCoordinatorSensor):
    _attr_name = "Color"
    _attr_icon = "mdi:palette"

    def __init__(self, entry, coord, spool_id: int) -> None:
        super().__init__(entry, coord, spool_id)
        self._attr_unique_id = f"{DOMAIN}_{self.spool_id}_color"

    @property
    def native_value(self):
        return self._spool().get("color")


class FilmanTypeSensor(_BaseFilmanCoordinatorSensor):
    _attr_name = "Filament Type"
    _attr_icon = "mdi:alpha-t-box-outline"

    def __init__(self, entry, coord, spool_id: int) -> None:
        super().__init__(entry, coord, spool_id)
        self._attr_unique_id = f"{DOMAIN}_{self.spool_id}_type"

    @property
    def native_value(self):
        return self._spool().get("filament_type")


class FilmanDensitySensor(_BaseFilmanCoordinatorSensor):
    """Density sourced from filament.density (g/cm³)."""
    _attr_name = "Density"
    _attr_icon = "mdi:weight"
    _attr_native_unit_of_measurement = DENSITY_UNIT
    _attr_device_class = DENSITY_DEVICE_CLASS  # None is OK on older HA versions

    def __init__(self, entry, coord, spool_id: int) -> None:
        super().__init__(entry, coord, spool_id)
        self._attr_unique_id = f"{DOMAIN}_{self.spool_id}_density"

    @property
    def native_value(self):
        filament = self._spool().get("filament") or {}
        val = filament.get("density")
        if val is None or val == "":
            return None
        try:
            return float(val)
        except (ValueError, TypeError):
            return None


class FilmanQtySensor(_BaseFilmanCoordinatorSensor):
    """Qty sourced from spool.extra.qty (unitless)."""
    _attr_name = "Qty"
    _attr_icon = "mdi:counter"

    def __init__(self, entry, coord, spool_id: int) -> None:
        super().__init__(entry, coord, spool_id)
        self._attr_unique_id = f"{DOMAIN}_{self.spool_id}_qty"

    @property
    def native_value(self):
        val = self._spool().get("qty")
        if val is None or val == "":
            return None
        try:
            return int(val)
        except (ValueError, TypeError):
            try:
                return int(float(val))
            except (ValueError, TypeError):
                return None


class FilmanHumiditySensor(_BaseFilmanCoordinatorSensor):
    _attr_name = "Humidity"
    _attr_icon = "mdi:water-percent"
    _attr_device_class = SensorDeviceClass.HUMIDITY

    def __init__(self, hass: HomeAssistant, entry, coord, spool_id: int) -> None:
        super().__init__(entry, coord, spool_id)
        self.hass = hass
        self._attr_unique_id = f"{DOMAIN}_{self.spool_id}_humidity"
        self._store = hass.data[DOMAIN][entry.entry_id]["store"]

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


class FilmanTemperatureSensor(_BaseFilmanCoordinatorSensor):
    _attr_name = "Temperature"
    _attr_icon = "mdi:thermometer"
    _attr_device_class = SensorDeviceClass.TEMPERATURE

    def __init__(self, hass: HomeAssistant, entry, coord, spool_id: int) -> None:
        super().__init__(entry, coord, spool_id)
        self.hass = hass
        self._attr_unique_id = f"{DOMAIN}_{self.spool_id}_temperature"
        self._store = hass.data[DOMAIN][entry.entry_id]["store"]

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
