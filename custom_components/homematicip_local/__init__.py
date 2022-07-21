"""HaHomematic is a Python 3 module for Home Assistant and Homemaatic(IP) devices."""
from __future__ import annotations

import logging

from awesomeversion import AwesomeVersion
from hahomematic.central_unit import cleanup_cache_dirs

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EVENT_HOMEASSISTANT_STOP, __version__ as HA_VERSION
from homeassistant.core import HomeAssistant

from .const import DOMAIN, HMIP_LOCAL_MIN_VERSION, HMIP_LOCAL_PLATFORMS
from .control_unit import ControlConfig, get_storage_folder
from .services import async_setup_services, async_unload_services

HA_VERSION_OBJ = AwesomeVersion(HA_VERSION)
_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    """Set up HA-Homematic from a config entry."""
    if HA_VERSION_OBJ < HMIP_LOCAL_MIN_VERSION:
        _LOGGER.warning("---")
        _LOGGER.warning(
            "This release of HomematicIP Local requires HA version %s and above",
            HMIP_LOCAL_MIN_VERSION,
        )
        _LOGGER.warning("HomematicIP Local setup blocked")
        _LOGGER.warning("---")
        return False
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
    config_entry.async_on_unload(config_entry.add_update_listener(update_listener))
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


async def async_remove_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> None:
    """Handle removal of an entry."""
    storage_folder = get_storage_folder(hass=hass)
    cleanup_cache_dirs(
        instance_name=config_entry.data["instance_name"], storage_folder=storage_folder
    )


async def update_listener(hass: HomeAssistant, config_entry: ConfigEntry) -> None:
    """Handle options update."""
    await hass.config_entries.async_reload(config_entry.entry_id)
