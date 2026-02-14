from __future__ import annotations
from typing import Any, Dict
import voluptuous as vol

from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.typing import ConfigType
from homeassistant.config_entries import SOURCE_IMPORT

from .const import DOMAIN, ADD_SIGNAL, UPDATE_SIGNAL, REMOVE_SIGNAL
from .store import SpoolStore

PLATFORMS = ["sensor", "select"]

# Service schemas
import homeassistant.helpers.config_validation as cv

SVC_ADD = vol.Schema({
    vol.Required("name"): cv.string,
    vol.Optional("brand", default=""): cv.string,
    vol.Optional("type", default=""): cv.string,
    vol.Optional("color", default=""): cv.string,
    vol.Optional("location", default=""): cv.string,
})

SVC_UPDATE = vol.Schema({
    vol.Required("id"): cv.string,
    vol.Optional("name"): cv.string,
    vol.Optional("brand"): cv.string,
    vol.Optional("type"): cv.string,
    vol.Optional("color"): cv.string,
    vol.Optional("location"): cv.string,
    vol.Optional("zigbee_device_id"): cv.string,
})

SVC_REMOVE = vol.Schema({
    vol.Required("id"): cv.string,
})

async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    return True

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    hass.data.setdefault(DOMAIN, {})
    store = SpoolStore(hass, entry.entry_id)
    await store.async_load()
    hass.data[DOMAIN][entry.entry_id] = store

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    # Register services under this domain
    async def _add(call: ServiceCall):
        data = dict(call.data)
        spool_id = await store.add(**data)
        async_dispatcher_send(hass, ADD_SIGNAL, spool_id)

    async def _update(call: ServiceCall):
        data = dict(call.data)
        spool_id = data.pop("id")
        await store.update(spool_id, **data)
        async_dispatcher_send(hass, UPDATE_SIGNAL, spool_id)

    async def _remove(call: ServiceCall):
        data = dict(call.data)
        spool_id = data["id"]
        await store.remove(spool_id)
        async_dispatcher_send(hass, REMOVE_SIGNAL, spool_id)

    hass.services.async_register(DOMAIN, "add_spool", _add, schema=SVC_ADD)
    hass.services.async_register(DOMAIN, "update_spool", _update, schema=SVC_UPDATE)
    hass.services.async_register(DOMAIN, "remove_spool", _remove, schema=SVC_REMOVE)

    return True

async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    hass.data.get(DOMAIN, {}).pop(entry.entry_id, None)
    # Unregister services when unloading the last entry
    if not hass.data.get(DOMAIN):
        hass.services.async_remove(DOMAIN, "add_spool")
        hass.services.async_remove(DOMAIN, "update_spool")
        hass.services.async_remove(DOMAIN, "remove_spool")
    return unload_ok
