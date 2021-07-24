"""
hahomematic is a Python 3 (>= 3.6) module for Home Assistant to interact with
HomeMatic and homematic IP devices.
Some other devices (f.ex. Bosch, Intertechno) might be supported as well.
https://github.com/danielperna84/hahomematic
"""

from __future__ import annotations
import functools

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import DOMAIN, ATTR_INSTANCENAME, HAHM_CLIENT, HAHM_SERVER, HAHM_NAME

import hahomematic.config
from hahomematic.server import Server
from hahomematic.client import Client
from hahomematic.const import (
    ATTR_HOSTNAME,
    ATTR_PORT,
    ATTR_PATH,
    ATTR_USERNAME,
    ATTR_PASSWORD,
    ATTR_SSL,
    ATTR_VERIFY_SSL,
    ATTR_CALLBACK_IP,
    ATTR_CALLBACK_PORT,
    ATTR_JSONPORT,
    PORT_HMIP,
    PORT_JSONRPC,
)

# TODO List the platforms that you want to support.
# For your initial PR, limit it to 1 platform.
PLATFORMS = ["binary_sensor"]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up xx from a config entry."""
    # TODO Store an API object for your platforms to access
    # hass.data[DOMAIN][entry.entry_id] = MyApi(...)

    hahomematic.config.INTERFACE_ID = "homeassistant_homematic"
    hahomematic.config.INIT_TIMEOUT = 10
    hahomematic.config.CACHE_DIR = "cache"

    hahm_server = Server(
        local_ip=entry.options[ATTR_CALLBACK_IP],
        local_port=entry.options[ATTR_CALLBACK_PORT],
    )
    hahm_client = await hass.async_add_executor_job(
        functools.partial(
            Client,
            name=entry.data[ATTR_INSTANCENAME],
            host=entry.options[ATTR_HOSTNAME],
            port=entry.options[ATTR_PORT],
            username=entry.options[ATTR_USERNAME],
            password=entry.options[ATTR_PASSWORD],
            local_port=hahm_server.local_port,
        )
    )
    hahm_server.start()
    await hass.async_add_executor_job(hahm_client.proxy_init)

    hahm_data = hass.data.setdefault(DOMAIN, {})
    hahm_data[entry.entry_id] = {
        HAHM_CLIENT: hahm_client,
        HAHM_SERVER: hahm_server,
        HAHM_NAME: ATTR_INSTANCENAME,
    }

    hass.config_entries.async_setup_platforms(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok
