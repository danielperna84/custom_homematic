"""
hahomematic is a Python 3 (>= 3.6) module for Home Assistant to interact with
HomeMatic and homematic IP devices.
Some other devices (f.ex. Bosch, Intertechno) might be supported as well.
https://github.com/danielperna84/hahomematic
"""

from __future__ import annotations

import functools
import time
from functools import partial
from typing import Any

from hahomematic import config
from hahomematic.client import Client
from hahomematic.const import (
    ATTR_CALLBACK_IP,
    ATTR_CALLBACK_PORT,
    ATTR_HOSTNAME,
    ATTR_JSONPORT,
    ATTR_PASSWORD,
    ATTR_PATH,
    ATTR_PORT,
    ATTR_TLS,
    ATTR_USERNAME,
    ATTR_VERIFY_TLS,
    HA_DOMAIN,
    HA_PLATFORMS,
    HH_EVENT_DEVICES_CREATED,
    HH_EVENT_NEW_DEVICES,
    IP_ANY_V4,
    PORT_ANY,
)
from hahomematic.server import Server
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_send

from .const import ATTR_INSTANCENAME, ATTR_INTERFACE, ATTR_JSONTLS

GOT_DEVICES = False


class Control_Unit:
    def __init__(self, hass: HomeAssistant, entry: ConfigEntry):
        self._hass = hass
        self._entry = entry
        self._server: Server = None
        self.active_hm_entities = {}

    async def async_start(self):
        config.INIT_TIMEOUT = 10
        config.CACHE_DIR = "cache"
        config.CALLBACK_SYSTEM = self._system_callback
        config.CALLBACK_EVENT = eventcallback

        self._server = await create_server(self._entry.data)

        await create_clients(
            self._hass,
            server=self._server,
            data=self._entry.data,
        )

        self._server.start()

        for client in self._server.clients.values():
            await self._hass.async_add_executor_job(client.proxy_init)

    async def async_stop(self):
        self._server.stop()

    @property
    def server(self):
        return self._server

    def get_new_hm_entities(self, platform):
        """
        Return all new hḿ-entities by unique_ids
        """
        new_entities = []
        if platform not in HA_PLATFORMS:
            return

        for (unique_id, hm_entity) in self._server.entities.items():
            if platform == getattr(hm_entity, "platform", None):
                if unique_id not in self.active_hm_entities.keys():
                    new_entities.append(hm_entity)

        return new_entities

    def add_hm_entity(self, hm_entity):
        """add entity to active entities"""
        self.active_hm_entities[hm_entity.unique_id] = hm_entity

    def remove_hm_entity(self, hm_entity):
        """remove entity from active entities"""
        del self._active_hm_entities[hm_entity.unique_id]

    @callback
    def async_signal_new_hm_entity(self, device_type) -> str:
        """Gateway specific event to signal new device."""
        return f"hahm-new-entity-{device_type}"

    def _system_callback(self, src, *args):
        global GOT_DEVICES
        new_entity_unique_ids = args[1]
        if src == HH_EVENT_NEW_DEVICES:
            """Handle event of new device creation in HAHM."""
            for (platform, hm_entities) in self._server.get_new_entities(
                new_entity_unique_ids
            ).items():
                args = []
                if hm_entities:
                    args.append([hm_entities])
                async_dispatcher_send(
                    self._hass,
                    self.async_signal_new_hm_entity(platform),
                    *args,  # Don't send device if None, it would override default value in listeners
                )
            return

        elif src == HH_EVENT_DEVICES_CREATED:
            GOT_DEVICES = True
            # start the platforms
            self._hass.config_entries.async_setup_platforms(self._entry, HA_PLATFORMS)
            return


def eventcallback(address, interface_id, key, value):
    if 0 == 2:
        return


# print(
#     "eventcallback at %i: %s, %s, %s, %s"
#     % (int(time.time()), address, interface_id, key, value)
# )


async def create_server(data: dict[str, Any]):
    """create the server for ccu callbacks."""
    return Server(
        instance_name=data[ATTR_INSTANCENAME],
        local_ip=data.get(ATTR_CALLBACK_IP),
        local_port=data.get(ATTR_CALLBACK_PORT),
    )


async def create_clients(hass: HomeAssistant, server: Server, data: dict[str, Any]):
    """create clients for the server."""
    clients: set(Client) = []
    for interface_name in data[ATTR_INTERFACE]:
        interface = data[ATTR_INTERFACE][interface_name]
        clients.append(
            await hass.async_add_executor_job(
                functools.partial(
                    Client,
                    server=server,
                    name=interface_name,
                    host=data[ATTR_HOSTNAME],
                    port=interface[ATTR_PORT],
                    path=interface[ATTR_PATH],
                    username=data[ATTR_USERNAME],
                    password=data[ATTR_PASSWORD],
                    tls=data[ATTR_TLS],
                    verify_tls=data[ATTR_VERIFY_TLS],
                    callback_hostname=data.get(ATTR_CALLBACK_IP)
                    if not data.get(ATTR_CALLBACK_IP) == IP_ANY_V4
                    else None,
                    callback_port=data.get(ATTR_CALLBACK_PORT)
                    if not data.get(ATTR_CALLBACK_PORT) == PORT_ANY
                    else None,
                    json_port=data[ATTR_JSONPORT],
                    json_tls=data[ATTR_JSONTLS],
                )
            )
        )
    return clients
