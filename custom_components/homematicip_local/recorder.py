"""Integration platform for recorder."""
from __future__ import annotations

from hahomematic.const import (
    ATTR_ADDRESS,
    ATTR_ENTITY_TYPE,
    ATTR_FUNCTION,
    ATTR_INTERFACE_ID,
    ATTR_MODEL,
    ATTR_NAME,
    ATTR_PARAMETER,
)

from homeassistant.core import HomeAssistant, callback


@callback
def exclude_attributes(hass: HomeAssistant) -> set[str]:
    """Exclude static attributes from being recorded in the database."""
    return {
        ATTR_ADDRESS,
        ATTR_ENTITY_TYPE,
        ATTR_FUNCTION,
        ATTR_INTERFACE_ID,
        ATTR_MODEL,
        ATTR_NAME,
        ATTR_PARAMETER,
    }
