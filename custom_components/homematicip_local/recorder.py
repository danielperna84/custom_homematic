"""Integration platform for recorder."""
from __future__ import annotations

from homeassistant.core import HomeAssistant, callback


@callback
def exclude_attributes(hass: HomeAssistant) -> set[str]:
    """Exclude static attributes from being recorded in the database."""
    return {
        "address"
        "entity_type",
        "function",
        "interface_id",
        "model",
        "name",
        "parameter",
        "value_state",
    }
