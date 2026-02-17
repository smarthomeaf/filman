from __future__ import annotations

import voluptuous as vol
import homeassistant.helpers.config_validation as cv


class SchemaHelper:
    @staticmethod
    def patch_spool_schema() -> vol.Schema:
        return vol.Schema(
            {
                vol.Required("id"): cv.positive_int,
                vol.Optional("extra"): vol.Schema({}, extra=vol.ALLOW_EXTRA),
            }
        )

    @staticmethod
    def use_spool_filament_schema() -> vol.Schema:
        return vol.Schema(
            {
                vol.Required("id"): cv.positive_int,
                vol.Optional("use_length"): vol.Coerce(float),
                vol.Optional("use_weight"): vol.Coerce(float),
            }
        )
