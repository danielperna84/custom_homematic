"""Diagnostics support for Homematic(IP) Local."""
from __future__ import annotations

from dataclasses import asdict
from typing import Any

from hahomematic.const import CONF_PASSWORD, CONF_USERNAME

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import CONTROL_UNITS, DOMAIN
from .control_unit import ControlUnit

REDACT_CONFIG = {CONF_USERNAME, CONF_PASSWORD}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: ConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    control_unit: ControlUnit = hass.data[DOMAIN][CONTROL_UNITS][entry.entry_id]
    diag: dict[str, Any] = {"config": async_redact_data(entry.as_dict(), REDACT_CONFIG)}

    platform_stats, device_types = control_unit.get_entity_stats()

    diag["platform_stats"] = platform_stats
    diag["devices"] = device_types
    diag["system_information"] = async_redact_data(
        asdict(control_unit.central.system_information), "serial"
    )

    return diag
