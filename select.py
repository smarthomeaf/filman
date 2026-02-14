
from __future__ import annotations
from typing import Any, Dict, Iterable, List, Optional, Set
import re, logging

from homeassistant.components.select import SelectEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.dispatcher import async_dispatcher_connect, async_dispatcher_send

from .const import DOMAIN, ADD_SIGNAL, REMOVE_SIGNAL, UPDATE_SIGNAL
from .store import FilmanStore
from .coordinator import FilmanCoordinator

_LOGGER = logging.getLogger(__name__)

ZB_DOMAINS: Set[str] = {"zha", "zigbee2mqtt", "deconz"}

def _is_filamenty(text: str) -> bool:
    return re.search(r"filament|filman", text, re.IGNORECASE) is not None

def _domains_from_identifiers(identifiers: Iterable[tuple]) -> Set[str]:
    domains: Set[str] = set()
    for ident in identifiers or []:
        if not isinstance(ident, (list, tuple)) or not ident:
            continue
        dom = ident[0]
        if isinstance(dom, str):
            domains.add(dom)
    return domains

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback) -> None:
    data = hass.data[DOMAIN][entry.entry_id]
    coord: FilmanCoordinator = data["coordinator"]
    store: FilmanStore = data["store"]

    entities: List[SelectEntity] = []
    for sid, spool in coord.data.items():
        store.all().setdefault(str(sid), {})
        entities.append(FilmanLinkSelect(entry, store, spool))

    if entities:
        async_add_entities(entities)

    async def _on_add(spool_id: str) -> None:
        sp = coord.data.get(int(spool_id))
        if sp:
            async_add_entities([FilmanLinkSelect(entry, store, sp)])

    async def _on_update(spool_id: str) -> None:
        return

    entry.async_on_unload(async_dispatcher_connect(hass, ADD_SIGNAL, _on_add))
    entry.async_on_unload(async_dispatcher_connect(hass, UPDATE_SIGNAL, _on_update))

class FilmanLinkSelect(SelectEntity):
    _attr_has_entity_name = True
    _attr_name = "Linked Zigbee Device"
    _attr_icon = "mdi:zigbee"

    def __init__(self, entry: ConfigEntry, store: FilmanStore, spool: dict[str, Any]) -> None:
        self._entry = entry
        self._store = store
        self.spool_id = str(spool["id"])
        self.spool = spool
        self._options_map: Dict[str, str] = {"None": ""}
        self._attr_options = ["None"]
        self._attr_unique_id = f"{DOMAIN}_{self.spool_id}_link"

    @property
    def device_info(self) -> DeviceInfo:
        return DeviceInfo(
            identifiers={(DOMAIN, self.spool_id)},
            name=f"Spool {self.spool_id}",
            manufacturer=self.spool.get("manufacturer") or "Unknown",
            model=str(self.spool.get("filament_type") or "Filament"),
            suggested_area=self.spool.get("location") or None,
        )

    async def async_added_to_hass(self) -> None:
        self._rebuild_options()
        self.async_write_ha_state()

    def _rebuild_options(self) -> None:
        dev_reg = dr.async_get(self.hass)
        filtered: Dict[str, str] = {}
        for device in dev_reg.devices.values():
            domains = _domains_from_identifiers(device.identifiers)
            if not (domains & ZB_DOMAINS):
                continue
            label = device.name_by_user or device.name or ""
            if _is_filamenty(label or ""):
                filtered[label] = device.id
        self._options_map = {"None": ""}
        for label in sorted(filtered.keys(), key=str.lower):
            self._options_map[label] = filtered[label]
        self._attr_options = list(self._options_map.keys())

    @property
    def current_option(self) -> str | None:
        cur = (self._store.all().get(self.spool_id) or {}).get("zigbee_device_id") or ""
        for label, dev_id in self._options_map.items():
            if dev_id == cur:
                return label
        return "None"

    async def async_select_option(self, option: str) -> None:
        dev_id = self._options_map.get(option, "")
        hum_eid = None
        tmp_eid = None
        if dev_id:
            ent_reg = er.async_get(self.hass)
            for ent in ent_reg.entities.values():
                if ent.device_id != dev_id or ent.domain != "sensor":
                    continue
                nm = (ent.original_name or "").lower()
                eid = ent.entity_id
                if hum_eid is None and ("humidity" in eid or "humidity" in nm):
                    hum_eid = eid
                if tmp_eid is None and ("temperature" in eid or "temperature" in nm or "temp" in nm):
                    tmp_eid = eid
        await self._store.update(self.spool_id, zigbee_device_id=(dev_id or None), humidity_entity_id=hum_eid, temperature_entity_id=tmp_eid)
        async_dispatcher_send(self.hass, UPDATE_SIGNAL, self.spool_id)
        self.async_write_ha_state()
