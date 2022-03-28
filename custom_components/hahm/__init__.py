"""HaHomematic is a Python 3 module for Home Assistant and Homemaatic(IP) devices."""
from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EVENT_HOMEASSISTANT_STOP
from homeassistant.core import HomeAssistant

from .const import DOMAIN, HMIP_LOCAL_PLATFORMS
from .control_unit import ControlConfig
from .services import async_setup_services, async_unload_services

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    """Set up HA-Homematic from a config entry."""
    control = await ControlConfig(
        hass=hass,
        entry_id=config_entry.entry_id,
        data=config_entry.data,
    ).async_get_control_unit()
    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][config_entry.entry_id] = control
    hass.config_entries.async_setup_platforms(config_entry, HMIP_LOCAL_PLATFORMS)
    await control.async_start()
    await async_setup_services(hass)

    # Register on HA stop event to gracefully shutdown Homematic(IP) Local connection
    hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, control.stop)
    return True


async def async_unload_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    control = hass.data[DOMAIN][config_entry.entry_id]
    await async_unload_services(hass)
    await control.async_stop()
    if unload_ok := await hass.config_entries.async_unload_platforms(
        config_entry, HMIP_LOCAL_PLATFORMS
    ):
        hass.data[DOMAIN].pop(config_entry.entry_id)

    return unload_ok
