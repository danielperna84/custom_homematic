"""
hahomematic is a Python 3 (>= 3.6) module for Home Assistant to interact with
HomeMatic and homematic IP devices.
Some other devices (f.ex. Bosch, Intertechno) might be supported as well.
https://github.com/danielperna84/hahomematic
"""

from __future__ import annotations

import functools
from typing import Any

import hahomematic.config
from hahomematic.client import Client
from hahomematic.const import (ATTR_CALLBACK_IP, ATTR_CALLBACK_PORT,
                               ATTR_HOSTNAME, ATTR_JSONPORT, ATTR_PASSWORD,
                               ATTR_PATH, ATTR_PORT, ATTR_SSL, ATTR_USERNAME,
                               ATTR_VERIFY_SSL, IP_ANY_V4, PORT_HMIP,
                               PORT_JSONRPC)
from hahomematic.server import Server
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import (ATTR_INSTANCENAME, ATTR_INTERFACE, ATTR_JSONSSL, DOMAIN,
                    HAHM_CLIENT, HAHM_NAME, HAHM_SERVER)

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

    hahm_server = await create_server(entry.data)
    hahm_clients = []

    for interface_name in entry.data[ATTR_INTERFACE]:
        hahm_client = await create_client(hass, hahm_server, entry.data, interface_name)
        await hass.async_add_executor_job(hahm_client.proxy_init)
        hahm_clients.append(hahm_client)

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = {
        HAHM_CLIENT: hahm_clients,
        HAHM_SERVER: hahm_server,
        HAHM_NAME: entry.data[ATTR_INSTANCENAME],
    }

    hahm_server.start()
    hass.config_entries.async_setup_platforms(entry, PLATFORMS)

    return True


async def create_server(data: dict[str, Any]):
    hahm_server = Server(
        local_ip=data.get(ATTR_CALLBACK_IP),
        local_port=data.get(ATTR_CALLBACK_PORT),
    )
    return hahm_server

async def create_client(hass: HomeAssistant, hahm_server, data: dict[str, Any], interface_name: str):
    interface = data[ATTR_INTERFACE][interface_name]
    hahm_client = await hass.async_add_executor_job(
        functools.partial(
            Client,
            name=f"{data[ATTR_INSTANCENAME]}-{interface_name}",
            host=data[ATTR_HOSTNAME],
            port=interface[ATTR_PORT],
            path=interface[ATTR_PATH],
            username=data[ATTR_USERNAME],
            password=data[ATTR_PASSWORD],
            tls=interface[ATTR_SSL],
            verify_tls=interface[ATTR_VERIFY_SSL],
            callback_hostname=data.get(ATTR_CALLBACK_IP) if not data.get(
                ATTR_CALLBACK_IP) == IP_ANY_V4 else None,
            callback_port=data.get(ATTR_CALLBACK_PORT),
            local_port=hahm_server.local_port,
            json_port=data[ATTR_JSONPORT],
            json_tls=data[ATTR_JSONSSL],
        )
    )
    return hahm_client


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok
