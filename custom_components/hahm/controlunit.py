"""
hahomematic is a Python 3 (>= 3.6) module for Home Assistant to interact with
HomeMatic and homematic IP devices.
Some other devices (f.ex. Bosch, Intertechno) might be supported as well.
https://github.com/danielperna84/hahomematic
"""

import logging
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
    HA_PLATFORMS,
    HH_EVENT_DELETE_DEVICES,
    HH_EVENT_DEVICES_CREATED,
    HH_EVENT_ERROR,
    HH_EVENT_LIST_DEVICES,
    HH_EVENT_NEW_DEVICES,
    HH_EVENT_READDED_DEVICE,
    HH_EVENT_REPLACE_DEVICE,
    HH_EVENT_UPDATE_DEVICE,
    IP_ANY_V4,
    PORT_ANY,
)
from hahomematic.server import Server
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_send

from .const import ATTR_INSTANCENAME, ATTR_INTERFACE, ATTR_JSONTLS

LOG = logging.getLogger(__name__)


class ControlUnit:
    """
    Central point to control a homematic ccu.
    """

    def __init__(
        self, hass: HomeAssistant, data: dict[str, Any] = {}, entry: ConfigEntry = None
    ):
        self._hass = hass
        self._data = data
        if entry:
            self._entry = entry
            self._data = self._entry.data
        self._server: Server = None
        self._active_hm_entities = {}

    async def start(self):
        """Start the server."""
        LOG.debug("Starting HAHM ControlUnit %s", self._data[ATTR_INSTANCENAME])
        config.CACHE_DIR = "cache"
        config.CALLBACK_SYSTEM = self._system_callback
        config.CALLBACK_EVENT = self._event_callback

        self.create_server()
        await self.create_clients()
        self._server.start()
        await self.init_clients()

    async def stop(self):
        """Stop the server."""
        LOG.debug("Stopping HAHM ControlUnit %s", self._data[ATTR_INSTANCENAME])
        for client in self._server.clients.values():
            await self._hass.async_add_executor_job(client.proxy_de_init)
        self._server.stop()

    async def init_clients(self):
        """Init clients related to server."""
        for client in self._server.clients.values():
            await self._hass.async_add_executor_job(client.proxy_init)

    @property
    def server(self):
        """return the hahm server instance."""
        return self._server

    def get_new_hm_entities(self, new_unique_entity_ids=None):
        """
        Return all new hḿ-entities by unique_ids
        """
        # remove already active entity unique_ids from new_unique_entity_ids
        new_unique_entity_ids -= self._active_hm_entities.keys()

        return self._server.get_hm_entities_by_platform(new_unique_entity_ids)

    def add_hm_entity(self, hm_entity):
        """add entity to active entities"""
        self._active_hm_entities[hm_entity.unique_id] = hm_entity

    def remove_hm_entity(self, hm_entity):
        """remove entity from active entities"""
        del self._active_hm_entities[hm_entity.unique_id]

    @callback
    def async_signal_new_hm_entity(self, device_type) -> str:
        """Gateway specific event to signal new device."""
        return f"hahm-new-entity-{device_type}"

    @callback
    def _system_callback(self, src, *args):
        """Callback for ccu based events."""
        if src == HH_EVENT_DEVICES_CREATED:
            new_entity_unique_ids = args[1]
            """Handle event of new device creation in HAHM."""
            for (platform, hm_entities) in self.get_new_hm_entities(
                new_entity_unique_ids
            ).items():
                args = []
                if hm_entities and len(hm_entities) > 0:
                    args.append([hm_entities])
                    async_dispatcher_send(
                        self._hass,
                        self.async_signal_new_hm_entity(platform),
                        *args,  # Don't send device if None, it would override default value in listeners
                    )
            return
        elif src == HH_EVENT_NEW_DEVICES:
            # ignore
            return
        elif src == HH_EVENT_DELETE_DEVICES:
            return
        elif src == HH_EVENT_ERROR:
            return
        elif src == HH_EVENT_LIST_DEVICES:
            return
        elif src == HH_EVENT_READDED_DEVICE:
            return
        elif src == HH_EVENT_REPLACE_DEVICE:
            return
        elif src == HH_EVENT_UPDATE_DEVICE:
            return

    @callback
    def _event_callback(self, address, interface_id, key, value):
        return

    def create_server(self):
        """create the server for ccu callbacks."""
        self._server = Server(
            instance_name=self._data[ATTR_INSTANCENAME],
            local_ip=self._data.get(ATTR_CALLBACK_IP),
            local_port=self._data.get(ATTR_CALLBACK_PORT),
        )

    async def create_clients(self):
        """create clients for the server."""
        clients: set(Client) = []
        for interface_name in self._data[ATTR_INTERFACE]:
            interface = self._data[ATTR_INTERFACE][interface_name]
            clients.append(
                await self._hass.async_add_executor_job(
                    partial(
                        Client,
                        server=self.server,
                        name=interface_name,
                        host=self._data[ATTR_HOSTNAME],
                        port=interface[ATTR_PORT],
                        path=interface[ATTR_PATH],
                        username=self._data[ATTR_USERNAME],
                        password=self._data[ATTR_PASSWORD],
                        tls=self._data[ATTR_TLS],
                        verify_tls=self._data[ATTR_VERIFY_TLS],
                        callback_hostname=self._data.get(ATTR_CALLBACK_IP)
                        if not self._data.get(ATTR_CALLBACK_IP) == IP_ANY_V4
                        else None,
                        callback_port=self._data.get(ATTR_CALLBACK_PORT)
                        if not self._data.get(ATTR_CALLBACK_PORT) == PORT_ANY
                        else None,
                        json_port=self._data[ATTR_JSONPORT],
                        json_tls=self._data[ATTR_JSONTLS],
                    )
                )
            )
        return clients
