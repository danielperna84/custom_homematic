"""
hahomematic is a Python 3 module for Home Assistant to interact with
Homematic and Homematic IP devices.
https://github.com/danielperna84/hahomematic
"""
from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import (
    CONF_ENABLE_SENSORS_FOR_SYSTEM_VARIABLES,
    CONF_ENABLE_VIRTUAL_CHANNELS,
    DOMAIN,
    HAHM_PLATFORMS,
)
from .control_unit import ControlConfig, ControlUnit
from .services import async_setup_services

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    """Set up HA-Homematic from a config entry."""
    control = ControlConfig(
        hass=hass,
        entry_id=config_entry.entry_id,
        data=config_entry.data,
        enable_virtual_channels=config_entry.options.get(
            CONF_ENABLE_VIRTUAL_CHANNELS, False
        ),
        enable_sensors_for_system_variables=config_entry.options.get(
            CONF_ENABLE_SENSORS_FOR_SYSTEM_VARIABLES, False
        ),
    ).get_control_unit()
    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][config_entry.entry_id] = control
    hass.config_entries.async_setup_platforms(config_entry, HAHM_PLATFORMS)
    await control.start()
    await async_setup_services(hass)
    return True


async def async_unload_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    control = hass.data[DOMAIN][config_entry.entry_id]
    await control.stop()
    control.central.clear_all()
    if unload_ok := await hass.config_entries.async_unload_platforms(
        config_entry, HAHM_PLATFORMS
    ):
        hass.data[DOMAIN].pop(config_entry.entry_id)

    return unload_ok
