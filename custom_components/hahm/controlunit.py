"""
hahomematic is a Python 3 (>= 3.6) module for Home Assistant to interact with
HomeMatic and homematic IP devices.
Some other devices (f.ex. Bosch, Intertechno) might be supported as well.
https://github.com/danielperna84/hahomematic
"""

import logging
from functools import partial

from hahomematic import config
from hahomematic.client import Client
from hahomematic.const import (
    ATTR_CALLBACK_HOST,
    ATTR_CALLBACK_PORT,
    ATTR_HOST,
    ATTR_JSON_PORT,
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
    HH_EVENT_RE_ADDED_DEVICE,
    HH_EVENT_REPLACE_DEVICE,
    HH_EVENT_UPDATE_DEVICE,
    IP_ANY_V4,
    PORT_ANY,
)
from hahomematic.entity import BaseEntity
from hahomematic.server import Server

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_send

from .const import ATTR_INSTANCE_NAME, ATTR_INTERFACE, ATTR_JSON_TLS

LOG = logging.getLogger(__name__)


class ControlUnit:
    """
    Central point to control a Homematic CCU.
    """

    def __init__(self, hass: HomeAssistant, data=None, entry: ConfigEntry = None):
        if data is None:
            data = {}
        self._hass = hass
        self._data = data
        if entry:
            self._entry = entry
            self._entry_id = entry.entry_id
            self._data = self._entry.data
        else:
            self._entry_id = "solo"
        self._server: Server = None
        self._active_hm_entities: dict[str, BaseEntity] = {}

    async def start(self):
        """Start the server."""
        LOG.debug("Starting HAHM ControlUnit %s", self._data[ATTR_INSTANCE_NAME])
        config.CACHE_DIR = "cache"

        self.create_server()

        await self.create_clients()
        self._server.start()
        await self.init_clients()

    async def stop(self):
        """Stop the server."""
        LOG.debug("Stopping HAHM ControlUnit %s", self._data[ATTR_INSTANCE_NAME])
        for client in self._server.clients.values():
            await self._hass.async_add_executor_job(client.proxy_de_init)
        self._server.stop()

    async def init_clients(self):
        """Init clients related to server."""
        for client in self._server.clients.values():
            await self._hass.async_add_executor_job(client.proxy_init)

    @property
    def server(self):
        """return the HAHM server instance."""
        return self._server

    def reconnect(self):
        """Reinit all Clients."""
        if self._server:
            self._server.reconnect()

    def get_all_system_variables(self):
        """Get all system variables from CCU / Homegear"""
        if self._server:
            return self._server.get_all_system_variables()

    def get_system_variable(self, name):
        """Get single system variable from CCU / Homegear"""
        if self._server:
            return self._server.get_system_variable(name)

    def set_system_variable(self, name, value):
        """Set a system variable on CCU / Homegear"""
        if self._server:
            return self._server.set_system_variable(name, value)

    def get_service_messages(self):
        """Get service messages from CCU / Homegear"""
        if self._server:
            return self._server.get_service_messages()

    def get_install_mode(self, interface_id):
        """Get remaining time in seconds install mode is active from CCU / Homegear"""
        if self._server:
            return self._server.get_install_mode(interface_id)

    def set_install_mode(self, interface_id, on=True, t=60, mode=1, address=None):
        """Activate or deactivate installmode on CCU / Homegear"""
        if self._server:
            return self._server.set_install_mode(interface_id, on, t, mode, address)

    def put_paramset(self, interface_id, address, paramset, value, rx_mode=None):
        """Set paramsets manually"""
        if self._server:
            return self._server.put_paramset(
                interface_id, address, paramset, value, rx_mode
            )

    def get_new_hm_entities(self, new_entities):
        """
        Return all hm-entities by requested unique_ids
        """
        # init dict
        hm_entities = {}
        for platform in HA_PLATFORMS:
            hm_entities[platform] = []

        for entity in new_entities:
            if (
                entity.unique_id not in self._active_hm_entities
                and entity.create_in_ha
                and entity.platform in HA_PLATFORMS
            ):
                hm_entities[entity.platform].append(entity)

        return hm_entities

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
    def _callback_system_event(self, src, *args):
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
            """Handle event of device removed in HAHM."""
            for address in args[1]:
                entity = self._get_active_entity_by_address(address)
                if entity:
                    entity.remove_entity()
            return
        elif src == HH_EVENT_ERROR:
            return
        elif src == HH_EVENT_LIST_DEVICES:
            return
        elif src == HH_EVENT_RE_ADDED_DEVICE:
            return
        elif src == HH_EVENT_REPLACE_DEVICE:
            return
        elif src == HH_EVENT_UPDATE_DEVICE:
            return

    @callback
    def _callback_device_event(self, address, interface_id):
        return

    @callback
    def _callback_click_event(self, event_type, event_data):
        self._hass.bus.fire(
            event_type,
            event_data,
        )
        return

    def create_server(self):
        """create the server for ccu callbacks."""
        self._server = Server(
            instance_name=self._data[ATTR_INSTANCE_NAME],
            entry_id=self._entry_id,
            local_ip=self._data.get(ATTR_CALLBACK_HOST),
            local_port=self._data.get(ATTR_CALLBACK_PORT),
        )
        # register callback
        self._server.callback_system_event = self._callback_system_event
        self._server.callback_click_event = self._callback_click_event

    async def create_clients(self):
        """create clients for the server."""
        clients: set[Client] = set()
        for interface_name in self._data[ATTR_INTERFACE]:
            interface = self._data[ATTR_INTERFACE][interface_name]
            clients.add(
                await self._hass.async_add_executor_job(
                    partial(
                        Client,
                        server=self.server,
                        name=interface_name,
                        host=self._data[ATTR_HOST],
                        port=interface[ATTR_PORT],
                        path=interface[ATTR_PATH],
                        username=self._data[ATTR_USERNAME],
                        password=self._data[ATTR_PASSWORD],
                        tls=self._data[ATTR_TLS],
                        verify_tls=self._data[ATTR_VERIFY_TLS],
                        callback_host=self._data.get(ATTR_CALLBACK_HOST)
                        if not self._data.get(ATTR_CALLBACK_HOST) == IP_ANY_V4
                        else None,
                        callback_port=self._data.get(ATTR_CALLBACK_PORT)
                        if not self._data.get(ATTR_CALLBACK_PORT) == PORT_ANY
                        else None,
                        json_port=self._data[ATTR_JSON_PORT],
                        json_tls=self._data[ATTR_JSON_TLS],
                    )
                )
            )
        return clients

    def _get_active_entity_by_address(self, address):
        for entity in self._active_hm_entities.values():
            if entity.address == address:
                return entity
