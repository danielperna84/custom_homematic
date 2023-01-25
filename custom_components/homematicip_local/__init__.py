"""HaHomematic is a Python 3 module for Home Assistant and Homemaatic(IP) devices."""
from __future__ import annotations

import logging

from awesomeversion import AwesomeVersion
from hahomematic.central_unit import cleanup_cache_dirs
from hahomematic.helpers import find_free_port

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EVENT_HOMEASSISTANT_STOP, __version__ as HA_VERSION_STR
from homeassistant.core import HomeAssistant

from .const import (
    CONTROL_UNITS,
    DEFAULT_CALLBACK_PORT,
    DOMAIN,
    HMIP_LOCAL_MIN_VERSION,
    HMIP_LOCAL_PLATFORMS,
)
from .control_unit import ControlConfig, get_storage_folder
from .services import async_setup_services, async_unload_services

HA_VERSION = AwesomeVersion(HA_VERSION_STR)
_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    """Set up Homematic(IP) Local from a config entry."""
    min_version = AwesomeVersion(HMIP_LOCAL_MIN_VERSION)
    if HA_VERSION < min_version:
        _LOGGER.warning(
            "This release of Homematic(IP) Local requires HA version %s and above",
            HMIP_LOCAL_MIN_VERSION,
        )
        _LOGGER.warning("Homematic(IP) Local setup blocked")
        return False

    hass.data.setdefault(DOMAIN, {})
    if (default_callback_port := hass.data[DOMAIN].get(DEFAULT_CALLBACK_PORT)) is None:
        default_callback_port = find_free_port()
        hass.data[DOMAIN][DEFAULT_CALLBACK_PORT] = default_callback_port

    if CONTROL_UNITS not in hass.data[DOMAIN]:
        hass.data[DOMAIN][CONTROL_UNITS] = {}

    control = await ControlConfig(
        hass=hass,
        entry_id=config_entry.entry_id,
        data=config_entry.data,
        default_port=default_callback_port,
    ).async_get_control_unit()
    hass.data[DOMAIN][CONTROL_UNITS][config_entry.entry_id] = control
    await hass.config_entries.async_forward_entry_setups(config_entry, HMIP_LOCAL_PLATFORMS)
    await control.async_start_central()
    await async_setup_services(hass)

    # Register on HA stop event to gracefully shutdown Homematic(IP) Local connection
    hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, control.stop_central)
    config_entry.async_on_unload(config_entry.add_update_listener(update_listener))
    return True


async def async_unload_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    control = hass.data[DOMAIN][CONTROL_UNITS][config_entry.entry_id]
    await async_unload_services(hass)
    await control.async_stop_central()
    if unload_ok := await hass.config_entries.async_unload_platforms(
        config_entry, HMIP_LOCAL_PLATFORMS
    ):
        hass.data[DOMAIN][CONTROL_UNITS].pop(config_entry.entry_id)

    return unload_ok


async def async_remove_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> None:
    """Handle removal of an entry."""
    storage_folder = get_storage_folder(hass=hass)
    cleanup_cache_dirs(
        instance_name=config_entry.data["instance_name"], storage_folder=storage_folder
    )


async def update_listener(hass: HomeAssistant, config_entry: ConfigEntry) -> None:
    """Handle options update."""
    await hass.config_entries.async_reload(config_entry.entry_id)
