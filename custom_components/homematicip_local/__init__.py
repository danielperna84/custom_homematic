"""HaHomematic is a Python 3 module for Home Assistant and Homematic(IP) devices."""

from __future__ import annotations

from dataclasses import dataclass
import logging

from awesomeversion import AwesomeVersion
from hahomematic.support import cleanup_cache_dirs, find_free_port

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EVENT_HOMEASSISTANT_STOP, __version__ as HA_VERSION_STR
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.entity_registry import async_migrate_entries
from homeassistant.util.hass_dict import HassKey

from .const import (
    CONF_ENABLE_SYSTEM_NOTIFICATIONS,
    DOMAIN,
    HMIP_LOCAL_MIN_VERSION,
    HMIP_LOCAL_PLATFORMS,
)
from .control_unit import ControlConfig, ControlUnit, get_storage_folder
from .services import async_get_config_entries, async_setup_services, async_unload_services

HA_VERSION = AwesomeVersion(HA_VERSION_STR)
type HomematicConfigEntry = ConfigEntry[ControlUnit]


@dataclass
class HomematicData:
    """Common data for shared homematic ip local data."""

    default_callback_port: int | None = None


HM_KEY: HassKey[HomematicData] = HassKey(DOMAIN)
_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: HomematicConfigEntry) -> bool:
    """Set up Homematic(IP) Local from a config entry."""
    min_version = AwesomeVersion(HMIP_LOCAL_MIN_VERSION)
    if min_version > HA_VERSION:
        _LOGGER.warning(
            "This release of Homematic(IP) Local requires HA version %s and above",
            HMIP_LOCAL_MIN_VERSION,
        )
        _LOGGER.warning("Homematic(IP) Local setup blocked")
        return False

    hass.data.setdefault(HM_KEY, HomematicData())
    if (default_callback_port := hass.data[HM_KEY].default_callback_port) is None:
        default_callback_port = find_free_port()
        hass.data[HM_KEY].default_callback_port = default_callback_port

    control = ControlConfig(
        hass=hass,
        entry_id=entry.entry_id,
        data=entry.data,
        default_port=default_callback_port,
    ).create_control_unit()
    entry.runtime_data = control
    await hass.config_entries.async_forward_entry_setups(entry, HMIP_LOCAL_PLATFORMS)
    await control.start_central()
    await async_setup_services(hass)

    # Register on HA stop event to gracefully shutdown Homematic(IP) Local connection
    hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, control.stop_central)
    entry.async_on_unload(entry.add_update_listener(update_listener))
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if control := entry.runtime_data:
        await async_unload_services(hass)
        await control.stop_central()
        unload_ok = await hass.config_entries.async_unload_platforms(entry, HMIP_LOCAL_PLATFORMS)
        if len(async_get_config_entries(hass=hass)) == 0:
            del hass.data[HM_KEY]
        return unload_ok

    return False


async def async_remove_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Handle removal of an entry."""
    storage_folder = get_storage_folder(hass=hass)
    cleanup_cache_dirs(instance_name=entry.data["instance_name"], storage_folder=storage_folder)


async def update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Handle options update."""
    await hass.config_entries.async_reload(entry.entry_id)


async def async_migrate_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Migrate old entry."""
    _LOGGER.debug("Migrating from version %s", entry.version)

    if entry.version == 1:
        data = dict(entry.data)
        data.update({CONF_ENABLE_SYSTEM_NOTIFICATIONS: True})
        hass.config_entries.async_update_entry(entry, version=2, data=data)
    if entry.version == 2:

        @callback
        def update_entity_unique_id(entity_entry: er.RegistryEntry) -> dict[str, str] | None:
            """Update unique ID of entity entry."""
            if entity_entry.unique_id.startswith(f"{DOMAIN}_bidcos_wir"):
                return {
                    "new_unique_id": entity_entry.unique_id.replace(
                        f"{DOMAIN}_bidcos_wir",
                        f"{DOMAIN}_{entry.unique_id}_bidcos_wir",
                    )
                }
            return None

        await async_migrate_entries(hass, entry.entry_id, update_entity_unique_id)

        hass.config_entries.async_update_entry(entry, version=3)
    _LOGGER.info("Migration to version %s successful", entry.version)
    return True
