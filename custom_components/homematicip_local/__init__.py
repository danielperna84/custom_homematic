"""HaHomematic is a Python 3 module for Home Assistant and Homematic(IP) devices."""
from __future__ import annotations

import logging

from awesomeversion import AwesomeVersion
from hahomematic.support import cleanup_cache_dirs, find_free_port
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EVENT_HOMEASSISTANT_STOP, __version__ as HA_VERSION_STR
from homeassistant.core import HomeAssistant

from .const import (
    ATTR_ENABLE_SYSTEM_NOTIFICATIONS,
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


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Homematic(IP) Local from a config entry."""
    min_version = AwesomeVersion(HMIP_LOCAL_MIN_VERSION)
    if min_version > HA_VERSION:
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
        entry_id=entry.entry_id,
        data=entry.data,
        default_port=default_callback_port,
    ).async_get_control_unit()
    hass.data[DOMAIN][CONTROL_UNITS][entry.entry_id] = control
    await hass.config_entries.async_forward_entry_setups(entry, HMIP_LOCAL_PLATFORMS)
    await control.async_start_central()
    await async_setup_services(hass)

    # Register on HA stop event to gracefully shutdown Homematic(IP) Local connection
    hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, control.stop_central)
    entry.async_on_unload(entry.add_update_listener(update_listener))
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if DOMAIN not in hass.data:
        return False

    if control := hass.data[DOMAIN][CONTROL_UNITS].pop(entry.entry_id):
        await async_unload_services(hass)
        await control.async_stop_central()
        return await hass.config_entries.async_unload_platforms(
            entry, HMIP_LOCAL_PLATFORMS
        )

    return False


async def async_remove_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Handle removal of an entry."""
    storage_folder = get_storage_folder(hass=hass)
    cleanup_cache_dirs(
        instance_name=entry.data["instance_name"], storage_folder=storage_folder
    )


async def update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Handle options update."""
    await hass.config_entries.async_reload(entry.entry_id)


async def async_migrate_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Migrate old entry."""
    _LOGGER.debug("Migrating from version %s", entry.version)

    if entry.version == 1:
        data = dict(entry.data)
        data.update({ATTR_ENABLE_SYSTEM_NOTIFICATIONS: True})

        entry.version = 2
        hass.config_entries.async_update_entry(entry, data=data)

    _LOGGER.info("Migration to version %s successful", entry.version)
    return True
