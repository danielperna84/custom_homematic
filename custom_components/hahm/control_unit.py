"""HaHomematic is a Python 3 module for Home Assistant and Homemaatic(IP) devices."""
from __future__ import annotations

from collections.abc import Callable, Mapping
from datetime import datetime, timedelta
import logging
from typing import Any, Tuple, cast

from hahomematic.central_unit import CentralConfig, CentralUnit
from hahomematic.client import ClientConfig
from hahomematic.const import (
    ATTR_ADDRESS,
    ATTR_CALLBACK_HOST,
    ATTR_CALLBACK_PORT,
    ATTR_HOST,
    ATTR_INTERFACE_ID,
    ATTR_JSON_PORT,
    ATTR_PARAMETER,
    ATTR_PASSWORD,
    ATTR_PORT,
    ATTR_TLS,
    ATTR_USERNAME,
    ATTR_VALUE,
    ATTR_VERIFY_TLS,
    AVAILABLE_HM_PLATFORMS,
    EVENT_STICKY_UN_REACH,
    EVENT_UN_REACH,
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
    HmEntityUsage,
    HmEventType,
    HmPlatform,
)
from hahomematic.entity import BaseEntity
from hahomematic.hub import HmDummyHub, HmHub
from hahomematic.xml_rpc_server import register_xml_rpc_server

from homeassistant.const import CONF_DEVICE_ID
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import aiohttp_client, device_registry as dr
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.device_registry import DeviceEntry, DeviceEntryType
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.entity import Entity
from homeassistant.util import slugify

from .const import ATTR_INSTANCE_NAME, ATTR_INTERFACE, ATTR_PATH, DOMAIN, HAHM_PLATFORMS
from .helpers import HmBaseEntity, HmCallbackEntity

_LOGGER = logging.getLogger(__name__)
SCAN_INTERVAL = timedelta(seconds=30)


class ControlUnit:
    """Central point to control a Homematic CCU."""

    def __init__(self, control_config: ControlConfig) -> None:
        """Init the control unit."""
        self._hass = control_config.hass
        self._entry_id = control_config.entry_id
        self._data = control_config.data
        self._central: CentralUnit | None = None
        # {entity_id, entity}
        self._active_hm_entities: dict[str, HmBaseEntity] = {}
        self._hub: HaHub | None = None

    async def async_init_central(self) -> None:
        """Start the control unit."""
        self._central = await self.async_create_central()
        self._async_add_central_to_device_registry()

    async def async_start(self) -> None:
        """Start the control unit."""
        _LOGGER.debug(
            "Starting Homematic(IP) Local ControlUnit %s",
            self._data[ATTR_INSTANCE_NAME],
        )
        if self._central:
            await self.async_create_clients()
            await self._central.init_clients()
            self.async_add_virtual_remotes_to_device_registry()
            await self.async_init_hub()
        else:
            _LOGGER.exception(
                "Starting Homematic(IP) Local ControlUnit %s not possible, CentralUnit is not available",
                self._data[ATTR_INSTANCE_NAME],
            )

    def _async_add_central_to_device_registry(self) -> None:
        """Add the central to device registry."""
        info = self.central.device_info
        device_registry = dr.async_get(self._hass)
        device_registry.async_get_or_create(
            config_entry_id=self._entry_id,
            identifiers=info["identifiers"],
            manufacturer=info["manufacturer"],
            model="CU",
            name=info["name"],
            entry_type=DeviceEntryType.SERVICE,
            configuration_url=info["device_url"],
        )

    @callback
    def async_add_virtual_remotes_to_device_registry(self) -> None:
        """Add the virtual remotes to device registry."""
        if not self._central:
            _LOGGER.error(
                "Cannot create Homematic(IP) Local ControlUnit %s virtual remote devices. No central",
                self._data[ATTR_INSTANCE_NAME],
            )
            return

        if not self._central.clients:
            _LOGGER.error(
                "Cannot create Homematic(IP) Local ControlUnit %s virtual remote devices. No clients",
                self._data[ATTR_INSTANCE_NAME],
            )
            return

        device_registry = dr.async_get(self._hass)
        for client in self._central.clients.values():
            if virtual_remote := client.get_virtual_remote():
                device_registry.async_get_or_create(
                    config_entry_id=self._entry_id,
                    identifiers=virtual_remote.device_info["identifiers"],
                    manufacturer=virtual_remote.device_info["manufacturer"],
                    name=virtual_remote.device_info["name"],
                    model=virtual_remote.device_info["model"],
                    sw_version=virtual_remote.device_info["sw_version"],
                    # Link to the homematic control unit.
                    via_device=cast(
                        Tuple[str, str], virtual_remote.device_info.get("via_device")
                    ),
                )

    async def async_stop(self) -> None:
        """Stop the control unit."""
        _LOGGER.debug(
            "Stopping Homematic(IP) Local ControlUnit %s",
            self._data[ATTR_INSTANCE_NAME],
        )
        if self._hub:
            self._hub.de_init()
        self.central.stop_connection_checker()
        for client in self.central.clients.values():
            await client.proxy_de_init()
        await self.central.stop()

    async def async_init_hub(self) -> None:
        """Init the hub."""
        await self.central.init_hub()
        if not self.central.hub:
            return None
        self._hub = HaHub(self._hass, control_unit=self, hm_hub=self.central.hub)
        await self._hub.async_init()
        if hub_entities_by_platform := self.central.hub.hub_entities_by_platform:
            sensors = hub_entities_by_platform.get(HmPlatform.HUB_SENSOR)
            async_dispatcher_send(
                self._hass,
                self.async_signal_new_hm_entity(
                    entry_id=self._entry_id, platform=HmPlatform.HUB_SENSOR
                ),
                sensors,
            )
            binary_sensors = hub_entities_by_platform.get(HmPlatform.HUB_BINARY_SENSOR)
            async_dispatcher_send(
                self._hass,
                self.async_signal_new_hm_entity(
                    entry_id=self._entry_id, platform=HmPlatform.HUB_BINARY_SENSOR
                ),
                binary_sensors,
            )

    @property
    def hub(self) -> HaHub | None:
        """Return the Hub."""
        return self._hub

    @property
    def central(self) -> CentralUnit:
        """Return the Homematic(IP) Local central_unit instance."""
        if self._central is not None:
            return self._central
        raise HomeAssistantError("homematicip_local.central not initialized")

    @callback
    def async_get_hm_entity(self, entity_id: str) -> HmBaseEntity | None:
        """Return hm-entity by requested entity_id."""
        return self._active_hm_entities.get(entity_id)

    @callback
    def async_get_new_hm_entities(
        self, new_entities: list[BaseEntity]
    ) -> dict[HmPlatform, list[BaseEntity]]:
        """Return all hm-entities by requested unique_ids."""
        active_unique_ids = [
            entity.unique_id for entity in self._active_hm_entities.values()
        ]
        # init dict
        hm_entities: dict[HmPlatform, list[BaseEntity]] = {}
        for hm_platform in AVAILABLE_HM_PLATFORMS:
            hm_entities[hm_platform] = []

        for entity in new_entities:
            if (
                entity.usage != HmEntityUsage.ENTITY_NO_CREATE
                and entity.unique_id not in active_unique_ids
                and entity.platform.value in HAHM_PLATFORMS
            ):
                hm_entities[entity.platform].append(entity)

        return hm_entities

    @callback
    def async_get_new_hm_entities_by_platform(
        self, platform: HmPlatform
    ) -> list[BaseEntity]:
        """Return all new hm-entities by platform."""
        active_unique_ids = [
            entity.unique_id for entity in self._active_hm_entities.values()
        ]

        hm_entities = []
        for entity in self.central.hm_entities.values():
            if (
                entity.usage != HmEntityUsage.ENTITY_NO_CREATE
                and entity.unique_id not in active_unique_ids
                and entity.platform == platform
            ):
                hm_entities.append(entity)

        return hm_entities

    @callback
    def async_get_hm_entities_by_platform(
        self, platform: HmPlatform
    ) -> list[BaseEntity]:
        """Return all hm-entities by platform."""
        hm_entities = []
        for entity in self.central.hm_entities.values():
            if (
                entity.usage != HmEntityUsage.ENTITY_NO_CREATE
                and entity.platform == platform
            ):
                hm_entities.append(entity)

        return hm_entities

    @callback
    def async_add_hm_entity(self, entity_id: str, hm_entity: HmBaseEntity) -> None:
        """Add entity to active entities."""
        self._active_hm_entities[entity_id] = hm_entity

    @callback
    def async_remove_hm_entity(self, entity_id: str) -> None:
        """Remove entity from active entities."""
        del self._active_hm_entities[entity_id]

    # pylint: disable=no-self-use
    @callback
    def async_signal_new_hm_entity(self, entry_id: str, platform: HmPlatform) -> str:
        """Gateway specific event to signal new device."""
        return f"hahm-new-entity-{entry_id}-{platform.value}"

    @callback
    def _async_callback_system_event(self, src: str, *args: Any) -> None:
        """Execute the callback for system based events."""
        if src == HH_EVENT_DEVICES_CREATED:
            new_entity_unique_ids = args[1]
            # Handle event of new device creation in HAHM.
            for (platform, hm_entities) in self.async_get_new_hm_entities(
                new_entities=new_entity_unique_ids
            ).items():
                if hm_entities and len(hm_entities) > 0:
                    async_dispatcher_send(
                        self._hass,
                        self.async_signal_new_hm_entity(
                            entry_id=self._entry_id, platform=platform
                        ),
                        hm_entities,  # Don't send device if None, it would override default value in listeners
                    )
        elif src == HH_EVENT_NEW_DEVICES:
            # ignore
            return None
        elif src == HH_EVENT_DELETE_DEVICES:
            # Handle event of device removed in HAHM.
            for address in args[1]:
                # HA only needs channel_addresses
                if ":" in address:
                    continue
                if entities := self._get_active_entities_by_device_address(
                    device_address=address
                ):
                    for entity in entities:
                        entity.remove_entity()
            return None
        elif src == HH_EVENT_ERROR:
            return None
        elif src == HH_EVENT_LIST_DEVICES:
            return None
        elif src == HH_EVENT_RE_ADDED_DEVICE:
            return None
        elif src == HH_EVENT_REPLACE_DEVICE:
            return None
        elif src == HH_EVENT_UPDATE_DEVICE:
            return None

    @callback
    def _async_callback_ha_event(
        self, hm_event_type: HmEventType, event_data: dict[str, Any]
    ) -> None:
        """Execute the callback used for device related events."""
        if device_id := self._async_get_device_id(event_data[ATTR_ADDRESS]):
            event_data[CONF_DEVICE_ID] = device_id

        if hm_event_type == HmEventType.KEYPRESS:
            self._hass.bus.fire(
                hm_event_type.value,
                event_data,
            )
        elif hm_event_type == HmEventType.SPECIAL:
            device_address = event_data[ATTR_ADDRESS]
            name = self._async_get_device_name(device_address=device_address)
            interface_id = event_data[ATTR_INTERFACE_ID]
            parameter = event_data[ATTR_PARAMETER]
            value = event_data[ATTR_VALUE]
            if parameter in (EVENT_STICKY_UN_REACH, EVENT_UN_REACH):
                if value is True:
                    title = f"{DOMAIN.upper()}-Device not reachable"
                    message = f"{name} / {device_address} on interface {interface_id}"
                    self._async_create_persistent_notification(
                        identifier=device_address, title=title, message=message
                    )
                else:
                    self._async_dismiss_persistent_notification(
                        identifier=device_address
                    )

    @callback
    def _async_create_persistent_notification(
        self, identifier: str, title: str, message: str
    ) -> None:
        """Create a message for user to UI."""
        self._hass.components.persistent_notification.async_create(
            message, title, identifier
        )

    @callback
    def _async_dismiss_persistent_notification(self, identifier: str) -> None:
        """Dismiss a message for user on UI."""
        self._hass.components.persistent_notification.async_dismiss(identifier)

    @callback
    def _async_get_device_name(self, device_address: str) -> str | None:
        """Return the device name of the ha device."""
        if device := self._async_get_device(device_address=device_address):
            return device.name_by_user if device.name_by_user else device.name
        return None

    @callback
    def _async_get_device_id(self, device_address: str) -> str | None:
        """Return the device id of the ha device."""
        if device := self._async_get_device(device_address=device_address):
            return device.id
        return None

    @callback
    def _async_get_device(self, device_address: str) -> DeviceEntry | None:
        """Return the device of the ha device."""
        if (hm_device := self.central.hm_devices.get(device_address)) is None:
            return None
        identifiers: set[tuple[str, str]] = hm_device.device_info["identifiers"]
        device_registry = dr.async_get(self._hass)
        return device_registry.async_get_device(identifiers=identifiers)

    async def async_create_central(self) -> CentralUnit:
        """Create the central unit for ccu callbacks."""
        xml_rpc_server = register_xml_rpc_server(
            local_ip=self._data.get(ATTR_CALLBACK_HOST, IP_ANY_V4),
            local_port=self._data.get(ATTR_CALLBACK_PORT, PORT_ANY),
        )

        storage_folder = f"{self._hass.config.config_dir}/{DOMAIN}"
        client_session = aiohttp_client.async_get_clientsession(self._hass)
        central = await CentralConfig(
            domain=DOMAIN,
            name=self._data[ATTR_INSTANCE_NAME],
            loop=self._hass.loop,
            xml_rpc_server=xml_rpc_server,
            storage_folder=storage_folder,
            host=self._data[ATTR_HOST],
            username=self._data[ATTR_USERNAME],
            password=self._data[ATTR_PASSWORD],
            tls=self._data[ATTR_TLS],
            verify_tls=self._data[ATTR_VERIFY_TLS],
            client_session=client_session,
            json_port=self._data[ATTR_JSON_PORT],
            callback_host=self._data.get(ATTR_CALLBACK_HOST)
            if not self._data.get(ATTR_CALLBACK_HOST) == IP_ANY_V4
            else None,
            callback_port=self._data.get(ATTR_CALLBACK_PORT)
            if not self._data.get(ATTR_CALLBACK_PORT) == PORT_ANY
            else None,
        ).get_central()
        # register callback
        central.callback_system_event = self._async_callback_system_event
        central.callback_ha_event = self._async_callback_ha_event
        return central

    async def async_create_clients(self) -> None:
        """Create clients for the central unit."""
        client_configs: set[ClientConfig] = set()
        for interface_name in self._data[ATTR_INTERFACE]:
            interface = self._data[ATTR_INTERFACE][interface_name]
            client_configs.add(
                ClientConfig(
                    central=self.central,
                    name=interface_name,
                    port=interface[ATTR_PORT],
                    path=interface.get(ATTR_PATH),
                )
            )
        if self._central:
            await self._central.create_clients(client_configs=client_configs)
        else:
            _LOGGER.exception(
                "ControlUnit.async_create_clients: Unable to create clients. Central is not available"
            )

    def _get_active_entities_by_device_address(
        self, device_address: str
    ) -> list[HmBaseEntity]:
        """Return used hm_entities by address."""
        entities: list[HmBaseEntity] = []
        for entity in self._active_hm_entities.values():
            if (
                isinstance(entity, HmCallbackEntity)
                and device_address == entity.device_address
            ):
                entities.append(entity)
        return entities


class ControlConfig:
    """Config for a ControlUnit."""

    def __init__(
        self,
        hass: HomeAssistant,
        entry_id: str,
        data: Mapping[str, Any],
    ) -> None:
        """Create the required config for the ControlUnit."""
        self.hass = hass
        self.entry_id = entry_id
        self.data = data

    async def async_get_control_unit(self) -> ControlUnit:
        """Identify the used client."""
        control_unit = ControlUnit(self)
        await control_unit.async_init_central()
        return control_unit


class HaHub(Entity):
    """The HomeMatic hub. (CCU2/HomeGear)."""

    _attr_should_poll = False
    _attr_icon = "mdi:gradient-vertical"

    def __init__(
        self, hass: HomeAssistant, control_unit: ControlUnit, hm_hub: HmHub | HmDummyHub
    ) -> None:
        """Initialize HomeMatic hub."""
        self.hass = hass
        self._control: ControlUnit = control_unit
        self._hm_hub: HmHub | HmDummyHub = hm_hub
        self._attr_name: str = self._control.central.instance_name
        self.entity_id = f"{DOMAIN}.{slugify(self._attr_name.lower())}"
        self._hm_hub.register_update_callback(self._async_update_hub)
        self.remove_listener: Callable | None = None

    async def async_init(self) -> None:
        """Init fetch scheduler."""
        self.remove_listener = self.hass.helpers.event.async_track_time_interval(
            self._async_fetch_data, SCAN_INTERVAL
        )
        await self._async_fetch_data(now=datetime.now())

    def de_init(self) -> None:
        """De_init the hub."""
        if self.remove_listener and callback(self.remove_listener):
            self.remove_listener()

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        return self._hm_hub.available

    async def _async_fetch_data(self, now: datetime) -> None:
        """Fetch data from backend."""
        await self._hm_hub.fetch_data()

    @property
    def state(self) -> Any | None:
        """Return the value of the entity."""
        return self._hm_hub.value

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return the state attributes."""
        return self._hm_hub.attributes

    async def async_set_variable(self, name: str, value: Any) -> None:
        """Set variable value on CCU/Homegear."""
        sensor = self._hm_hub.hub_entities.get(name)
        if not sensor or name in self.extra_state_attributes:
            _LOGGER.error("Variable %s not found on %s", name, self.name)
            return

        old_value = None
        if sensor:
            old_value = sensor.value
        if old_value is None:
            old_value = self.extra_state_attributes.get(name)

        value = cv.boolean(value) if isinstance(old_value, bool) else float(value)
        await self._hm_hub.set_system_variable(name=name, value=value)

    @callback
    def _async_update_hub(self, *args: Any) -> None:
        """Update the HA hub."""
        self.async_schedule_update_ha_state(True)
