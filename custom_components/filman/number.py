from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up Filman number entities.

    Count control has been removed. This platform is kept as a no-op to avoid
    breaking existing installs that still include 'number' in PLATFORMS.
    """
    _LOGGER.debug("Filman number platform loaded; no number entities are created.")
    return
