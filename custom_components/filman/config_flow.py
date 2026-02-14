from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import DOMAIN, CONF_SPOOLMAN_URL, CONF_SPOOLMAN_API_KEY

DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_SPOOLMAN_URL): str,
        vol.Optional(CONF_SPOOLMAN_API_KEY, default=""): str,
    }
)


async def _validate_spoolman_connection(
    hass,
    base_url: str,
    api_key: str | None,
) -> str | None:
    """Return an error key (cannot_connect/invalid_auth) or None if OK."""
    if not base_url:
        return "cannot_connect"

    session = async_get_clientsession(hass)
    url = base_url.rstrip("/") + "/api/v1/spool?archived=false"

    headers: dict[str, str] = {}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"

    try:
        resp = await session.get(url, timeout=20, headers=headers)
    except Exception:
        return "cannot_connect"

    try:
        # Some servers keep connections open; ensure we close properly.
        async with resp:
            if resp.status in (401, 403):
                return "invalid_auth"
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
            api_key = user_input.get(CONF_SPOOLMAN_API_KEY, "")

            err = await _validate_spoolman_connection(self.hass, spoolman_url, api_key)
            if err:
                errors["base"] = err
            else:
                return self.async_create_entry(title="Filman", data=user_input)

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
            api_key = user_input.get(CONF_SPOOLMAN_API_KEY, "")

            err = await _validate_spoolman_connection(self.hass, spoolman_url, api_key)
            if err:
                errors["base"] = err
            else:
                return self.async_create_entry(title="", data=user_input)

        opts = self._entry.options or self._entry.data
        schema = vol.Schema(
            {
                vol.Required(CONF_SPOOLMAN_URL, default=opts.get(CONF_SPOOLMAN_URL, "")): str,
                vol.Optional(CONF_SPOOLMAN_API_KEY, default=opts.get(CONF_SPOOLMAN_API_KEY, "")): str,
            }
        )

        return self.async_show_form(step_id="init", data_schema=schema, errors=errors)
