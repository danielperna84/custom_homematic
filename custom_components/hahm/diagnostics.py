"""Diagnostics support for Homematic(IP) Cloud."""
from __future__ import annotations

from typing import Any

from hahomematic.const import ATTR_PASSWORD, ATTR_USERNAME

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import DOMAIN
from .control_unit import ControlUnit

REDACT_CONFIG = {ATTR_USERNAME, ATTR_PASSWORD}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, config_entry: ConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    control_unit: ControlUnit = hass.data[DOMAIN][config_entry.entry_id]
    diag: dict[str, Any] = {
        "config": async_redact_data(config_entry.as_dict(), REDACT_CONFIG)
    }

    platform_stats, device_types = control_unit.async_get_entity_stats()

    diag["platform_stats"] = platform_stats
    diag["devices"] = device_types

    return diag
