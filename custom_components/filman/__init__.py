from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.typing import ConfigType

from .const import DOMAIN, PLATFORMS
from .coordinator import FilmanCoordinator
from .store import FilmanStore
from .schema_helper import SchemaHelper


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    store = FilmanStore(hass, entry)
    await store.async_load()

    coord = FilmanCoordinator(hass, entry)
    await coord.async_config_entry_first_refresh()

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = {"coordinator": coord, "store": store}

    # ---------------------------
    # Services (Filman)
    # ---------------------------

    async def _svc_patch_spool(call: ServiceCall) -> None:
        spool_id: int = call.data["id"]
        data = {key: call.data[key] for key in call.data if key != "id"}

        if not data:
            raise HomeAssistantError("No fields provided to patch (ex: extra: {qty: 5})")

        try:
            await coord.async_patch_spool(spool_id, data)
        except Exception as e:
            raise HomeAssistantError(f"filman.patch_spool failed: {e}") from e

    async def _svc_use_spool_filament(call: ServiceCall) -> None:
        spool_id: int = call.data["id"]
        use_length = call.data.get("use_length")
        use_weight = call.data.get("use_weight")

        if use_length is not None and use_weight is not None:
            raise HomeAssistantError("Provide only one of use_length or use_weight")

        try:
            await coord.async_use_spool_filament(
                spool_id,
                use_length=use_length,
                use_weight=use_weight,
            )
        except Exception as e:
            raise HomeAssistantError(f"filman.use_spool_filament failed: {e}") from e

    # Register once per entry load (safe; HA service registry is global)
    # We keep it simple: services always act on the currently loaded entry.
    hass.services.async_register(
        DOMAIN,
        "patch_spool",
        _svc_patch_spool,
        schema=SchemaHelper.patch_spool_schema(),
    )
    hass.services.async_register(
        DOMAIN,
        "use_spool_filament",
        _svc_use_spool_filament,
        schema=SchemaHelper.use_spool_filament_schema(),
    )

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    unloaded = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unloaded:
        hass.data[DOMAIN].pop(entry.entry_id, None)

        # Remove services on unload (prevents stale handlers)
        hass.services.async_remove(DOMAIN, "patch_spool")
        hass.services.async_remove(DOMAIN, "use_spool_filament")

    return unloaded
