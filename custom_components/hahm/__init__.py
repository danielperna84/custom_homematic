"""
hahomematic is a Python 3 (>= 3.6) module for Home Assistant to interact with
HomeMatic and homematic IP devices.
Some other devices (f.ex. Bosch, Intertechno) might be supported as well.
https://github.com/danielperna84/hahomematic
"""

from __future__ import annotations

from hahomematic.const import HA_PLATFORMS
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import (
    ATTR_INSTANCENAME,
    ATTR_INTERFACE,
    ATTR_JSONTLS,
    DOMAIN,
    HAHM_CLIENT,
    HAHM_NAME,
    HAHM_SERVER,
)
from .control_unit import Control_Unit


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up HA-Homematic from a config entry."""

    cu = Control_Unit(hass, entry)
    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = cu
    await cu.async_start()

    # hass.config_entries.async_setup_platforms(entry, HA_PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, HA_PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok
