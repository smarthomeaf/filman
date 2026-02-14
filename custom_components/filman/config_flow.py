from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import DOMAIN, CONF_SPOOLMAN_URL

DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_SPOOLMAN_URL): str,
    }
)


async def _validate_spoolman_connection(
    hass,
    base_url: str,
) -> str | None:
    """Return an error key (cannot_connect) or None if OK."""
    if not base_url:
        return "cannot_connect"

    session = async_get_clientsession(hass)
    url = base_url.rstrip("/") + "/api/v1/spool?archived=false"

    try:
        resp = await session.get(url, timeout=20)
    except Exception:
        return "cannot_connect"

    try:
        # Some servers keep connections open; ensure we close properly.
        async with resp:
            if resp.status != 200:
                return "cannot_connect"
            # Confirm JSON is parseable (doesn't need strict shape here).
            await resp.json()
    except Exception:
        return "cannot_connect"

    return None


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1

    async def async_step_user(self, user_input: dict[str, Any] | None = None):
        errors: dict[str, str] = {}

        if user_input is not None:
            spoolman_url = user_input.get(CONF_SPOOLMAN_URL, "")

            err = await _validate_spoolman_connection(self.hass, spoolman_url)
            if err:
                errors["base"] = err
            else:
                # Store only what we need
                return self.async_create_entry(
                    title="Filman",
                    data={CONF_SPOOLMAN_URL: spoolman_url},
                )

        return self.async_show_form(
            step_id="user",
            data_schema=DATA_SCHEMA,
            errors=errors,
        )

    async def async_step_import(self, user_input):
        return await self.async_step_user(user_input)

    async def async_step_reauth(self, data):
        # Simple reauth path: prompt the user again (same form/validation).
        return await self.async_step_user(data)

    @staticmethod
    def async_get_options_flow(config_entry: config_entries.ConfigEntry):
        return OptionsFlowHandler(config_entry)


class OptionsFlowHandler(config_entries.OptionsFlow):
    def __init__(self, entry: config_entries.ConfigEntry) -> None:
        self._entry = entry

    async def async_step_init(self, user_input: dict[str, Any] | None = None):
        errors: dict[str, str] = {}

        if user_input is not None:
            spoolman_url = user_input.get(CONF_SPOOLMAN_URL, "")

            err = await _validate_spoolman_connection(self.hass, spoolman_url)
            if err:
                errors["base"] = err
            else:
                return self.async_create_entry(
                    title="",
                    data={CONF_SPOOLMAN_URL: spoolman_url},
                )

        opts = self._entry.options or self._entry.data
        schema = vol.Schema(
            {
                vol.Required(
                    CONF_SPOOLMAN_URL,
                    default=opts.get(CONF_SPOOLMAN_URL, ""),
                ): str,
            }
        )

        return self.async_show_form(step_id="init", data_schema=schema, errors=errors)
