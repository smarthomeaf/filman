
from __future__ import annotations
from typing import Any
import voluptuous as vol
from homeassistant import config_entries
from .const import DOMAIN, CONF_SPOOLMAN_URL, CONF_SPOOLMAN_API_KEY

DATA_SCHEMA = vol.Schema({
    vol.Required(CONF_SPOOLMAN_URL): str,
    vol.Optional(CONF_SPOOLMAN_API_KEY, default=""): str,
})

class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1

    async def async_step_user(self, user_input: dict[str, Any] | None = None):
        if user_input is not None:
            return self.async_create_entry(title="Filman", data=user_input)
        return self.async_show_form(step_id="user", data_schema=DATA_SCHEMA)

    async def async_step_import(self, user_input):
        return await self.async_step_user(user_input)

    async def async_step_reauth(self, data):
        return await self.async_step_user(data)

    async def async_get_options_flow(self, entry):
        return OptionsFlowHandler(entry)

class OptionsFlowHandler(config_entries.OptionsFlow):
    def __init__(self, entry: config_entries.ConfigEntry) -> None:
        self._entry = entry

    async def async_step_init(self, user_input: dict[str, Any] | None = None):
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        opts = self._entry.options or self._entry.data
        schema = vol.Schema({
            vol.Required(CONF_SPOOLMAN_URL, default=opts.get(CONF_SPOOLMAN_URL, "")): str,
            vol.Optional(CONF_SPOOLMAN_API_KEY, default=opts.get(CONF_SPOOLMAN_API_KEY, "")): str,
        })
        return self.async_show_form(step_id="init", data_schema=schema)
