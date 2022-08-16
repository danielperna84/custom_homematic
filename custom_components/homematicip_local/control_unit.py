"""HaHomematic is a Python 3 module for Home Assistant and Homematic(IP) devices."""
from __future__ import annotations

from collections.abc import Callable, Mapping
from copy import deepcopy
from datetime import datetime
import logging
from typing import Any, cast

from hahomematic.central_unit import CentralConfig, CentralUnit
from hahomematic.client import InterfaceConfig
from hahomematic.config import CHECK_INTERVAL
from hahomematic.const import (
    ATTR_ADDRESS,
    ATTR_CALLBACK_HOST,
    ATTR_CALLBACK_PORT,
    ATTR_HOST,
    ATTR_INTERFACE,
    ATTR_INTERFACE_ID,
    ATTR_JSON_PORT,
    ATTR_PARAMETER,
    ATTR_PASSWORD,
    ATTR_PORT,
    ATTR_TLS,
    ATTR_TYPE,
    ATTR_USERNAME,
    ATTR_VALUE,
    ATTR_VERIFY_TLS,
    AVAILABLE_HM_HUB_PLATFORMS,
    AVAILABLE_HM_PLATFORMS,
    EVENT_STICKY_UN_REACH,
    EVENT_UN_REACH,
    HH_EVENT_DELETE_DEVICES,
    HH_EVENT_DEVICES_CREATED,
    HH_EVENT_ERROR,
    HH_EVENT_HUB_ENTITY_CREATED,
    HH_EVENT_LIST_DEVICES,
    HH_EVENT_NEW_DEVICES,
    HH_EVENT_RE_ADDED_DEVICE,
    HH_EVENT_REPLACE_DEVICE,
    HH_EVENT_UPDATE_DEVICE,
    IP_ANY_V4,
    PORT_ANY,
    HmEntityUsage,
    HmEventType,
    HmInterfaceEventType,
    HmPlatform,
)
from hahomematic.device import HmDevice
from hahomematic.entity import BaseEntity, CustomEntity, GenericEntity
from hahomematic.hub import HmHub
from hahomematic.xml_rpc_server import register_xml_rpc_server

from homeassistant.const import ATTR_DEVICE_ID, ATTR_ENTITY_ID, ATTR_NAME
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import aiohttp_client, device_registry as dr
from homeassistant.helpers.device_registry import DeviceEntry, DeviceEntryType
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.util import slugify

from .const import (
    ATTR_INSTANCE_NAME,
    ATTR_INTERFACE,
    ATTR_PATH,
    CONTROL_UNITS,
    DOMAIN,
    EVENT_DATA_AVAILABLE,
    EVENT_DATA_IDENTIFIER,
    EVENT_DATA_MESSAGE,
    EVENT_DATA_TITLE,
    EVENT_DEVICE_AVAILABILITY,
    HMIP_LOCAL_PLATFORMS,
    IDENTIFIER_SEPARATOR,
    MANUFACTURER,
    SYSVAR_SCAN_INTERVAL,
)
from .helpers import (
    HmBaseEntity,
    HmBaseHubEntity,
    HmCallbackEntity,
    get_device_address_at_interface_from_identifiers,
)

_LOGGER = logging.getLogger(__name__)


class BaseControlUnit:
    """Base central point to control a Homematic CCU."""

    def __init__(self, control_config: ControlConfig) -> None:
        """Init the control unit."""
        self._hass = control_config.hass
        self._entry_id = control_config.entry_id
        self._data = control_config.data
        self._default_callback_port = control_config.default_callback_port
        self._instance_name = self._data[ATTR_INSTANCE_NAME]
        self._central: CentralUnit | None = None

    async def async_init_central(self) -> None:
        """Start the control unit."""
        _LOGGER.debug(
            "Init ControlUnit %s",
            self._instance_name,
        )
        self._central = await self._async_create_central()

    async def async_start(self) -> None:
        """Start the control unit."""
        _LOGGER.debug(
            "Starting ControlUnit %s",
            self._instance_name,
        )
        if self._central:
            await self._central.start()
        else:
            _LOGGER.exception(
                "Starting ControlUnit %s not possible, CentralUnit is not available",
                self._instance_name,
            )

    @callback
    def stop(self, *args: Any) -> None:
        """Wrap the call to async_stop.
        Used as an argument to EventBus.async_listen_once.
        """
        self._hass.async_create_task(self.async_stop())

    async def async_stop(self) -> None:
        """Stop the control unit."""
        _LOGGER.debug(
            "Stopping ControlUnit %s",
            self._instance_name,
        )
        if self._central is not None:
            await self._central.stop()

    @property
    def central(self) -> CentralUnit:
        """Return the Homematic(IP) Local central_unit instance."""
        if self._central is not None:
            return self._central
        raise HomeAssistantError("homematicip_local.central not initialized")

    async def _async_create_central(self) -> CentralUnit:
        """Create the central unit for ccu callbacks."""
        xml_rpc_server = register_xml_rpc_server(
            local_port=self._data.get(ATTR_CALLBACK_PORT)
            or self._default_callback_port,
        )

        storage_folder = get_storage_folder(self._hass)
        client_session = aiohttp_client.async_get_clientsession(self._hass)
        interface_configs: set[InterfaceConfig] = set()
        for interface_name in self._data[ATTR_INTERFACE]:
            interface = self._data[ATTR_INTERFACE][interface_name]
            interface_configs.add(
                InterfaceConfig(
                    interface=interface_name,
                    port=interface[ATTR_PORT],
                    path=interface.get(ATTR_PATH),
                )
            )
        # use last 10 chars of entry_id for central_id uniqueness
        central_id = self._entry_id[-10:]
        return await CentralConfig(
            name=self._instance_name,
            loop=self._hass.loop,
            xml_rpc_server=xml_rpc_server,
            storage_folder=storage_folder,
            host=self._data[ATTR_HOST],
            username=self._data[ATTR_USERNAME],
            password=self._data[ATTR_PASSWORD],
            central_id=central_id,
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
            interface_configs=interface_configs,
        ).get_central()


class ControlUnit(BaseControlUnit):
    """Central unit to control a Homematic CCU."""

    def __init__(self, control_config: ControlConfig) -> None:
        """Init the control unit."""
        super().__init__(control_config=control_config)
        # {entity_id, entity}
        self._active_hm_entities: dict[str, HmBaseEntity] = {}
        # {entity_id, sysvar_entity}
        self._active_hm_hub_entities: dict[str, HmBaseHubEntity] = {}
        self._hub: HaHub | None = None

    async def async_init_central(self) -> None:
        """Start the control unit."""
        await super().async_init_central()
        # register callback
        if self._central:
            self._central.callback_system_event = self._async_callback_system_event
            self._central.callback_ha_event = self._async_callback_ha_event

        self._async_add_central_to_device_registry()

    async def async_stop(self) -> None:
        """Stop the control unit."""
        if self._hub:
            self._hub.de_init()

        await super().async_stop()

    @property
    def hub(self) -> HaHub | None:
        """Return the Hub."""
        return self._hub

    def _async_add_central_to_device_registry(self) -> None:
        """Add the central to device registry."""
        device_registry = dr.async_get(self._hass)
        device_registry.async_get_or_create(
            config_entry_id=self._entry_id,
            identifiers={
                (
                    DOMAIN,
                    self.central.name,
                )
            },
            manufacturer=MANUFACTURER,
            model="CU",
            name=self.central.name,
            entry_type=DeviceEntryType.SERVICE,
            configuration_url=self.central.config.central_url,
        )

    @callback
    def _async_add_virtual_remotes_to_device_registry(self) -> None:
        """Add the virtual remotes to device registry."""
        if not self._central:
            _LOGGER.error(
                "Cannot create ControlUnit %s virtual remote devices. No central",
                self._instance_name,
            )
            return

        if not self._central.clients:
            _LOGGER.error(
                "Cannot create ControlUnit %s virtual remote devices. No clients",
                self._instance_name,
            )
            return

        device_registry = dr.async_get(self._hass)
        for client in self._central.clients.values():
            if virtual_remote := client.get_virtual_remote():
                device_registry.async_get_or_create(
                    config_entry_id=self._entry_id,
                    identifiers={
                        (
                            DOMAIN,
                            f"{virtual_remote.device_address}{IDENTIFIER_SEPARATOR}{virtual_remote.interface_id}",
                        )
                    },
                    manufacturer=MANUFACTURER,
                    name=virtual_remote.name,
                    model=virtual_remote.device_type,
                    sw_version=virtual_remote.firmware,
                    # Link to the homematic control unit.
                    via_device=cast(tuple[str, str], self._central.name),
                )

    @callback
    def async_get_hm_entity(self, entity_id: str) -> HmBaseEntity | None:
        """Return hm-entity by requested entity_id."""
        return self._active_hm_entities.get(entity_id)

    @callback
    def async_get_new_hm_entities(
        self, new_entities: list[BaseEntity]
    ) -> dict[HmPlatform, list[BaseEntity]]:
        """Return all hm-entities."""
        active_unique_ids = [
            entity.unique_identifier for entity in self._active_hm_entities.values()
        ]
        # init dict
        hm_entities: dict[HmPlatform, list[BaseEntity]] = {}
        for hm_platform in AVAILABLE_HM_PLATFORMS:
            hm_entities[hm_platform] = []

        for entity in new_entities:
            if (
                entity.usage != HmEntityUsage.ENTITY_NO_CREATE
                and entity.unique_identifier not in active_unique_ids
                and entity.platform.value in HMIP_LOCAL_PLATFORMS
            ):
                hm_entities[entity.platform].append(entity)

        return hm_entities

    @callback
    def async_get_new_hm_hub_entities(
        self, new_hub_entities: list[HmBaseHubEntity]
    ) -> dict[HmPlatform, list[HmBaseHubEntity]]:
        """Return all hm-hub-entities."""
        active_unique_ids = [
            entity.unique_identifier for entity in self._active_hm_hub_entities.values()
        ]
        # init dict
        hm_hub_entities: dict[HmPlatform, list[HmBaseHubEntity]] = {}
        for hm_hub_platform in AVAILABLE_HM_HUB_PLATFORMS:
            hm_hub_entities[hm_hub_platform] = []

        for hub_entity in new_hub_entities:
            if hub_entity.unique_identifier not in active_unique_ids:
                hm_hub_entities[hub_entity.platform].append(hub_entity)

        return hm_hub_entities

    @callback
    def async_get_new_hm_hub_entities_by_platform(
        self, platform: HmPlatform
    ) -> list[HmBaseHubEntity]:
        """Return all new hm-hub-entities by platform."""
        active_unique_ids = [
            entity.unique_identifier for entity in self._active_hm_hub_entities.values()
        ]

        hm_hub_entities: list[HmBaseHubEntity] = []
        if not self.central.hub:
            _LOGGER.debug(
                "async_get_new_hm_sysvar_entities_by_platform: central.hub is not ready for %s",
                self.central.name,
            )
            return []

        for program_entity in self.central.hub.program_entities.values():
            if (
                program_entity.unique_identifier not in active_unique_ids
                and program_entity.platform == platform
            ):
                hm_hub_entities.append(program_entity)

        for sysvar_entity in self.central.hub.syvar_entities.values():
            if (
                sysvar_entity.unique_identifier not in active_unique_ids
                and sysvar_entity.platform == platform
            ):
                hm_hub_entities.append(sysvar_entity)

        return hm_hub_entities

    @callback
    def async_get_new_hm_entities_by_platform(
        self, platform: HmPlatform
    ) -> list[BaseEntity]:
        """Return all new hm-entities by platform."""
        active_unique_ids = [
            entity.unique_identifier for entity in self._active_hm_entities.values()
        ]

        hm_entities: list[BaseEntity] = []
        for entity in self.central.hm_entities.values():
            if (
                entity.usage != HmEntityUsage.ENTITY_NO_CREATE
                and entity.unique_identifier not in active_unique_ids
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
    def async_add_hm_hub_entity(
        self, entity_id: str, hm_hub_entity: HmBaseHubEntity
    ) -> None:
        """Add entity to active hub entities."""
        self._active_hm_hub_entities[entity_id] = hm_hub_entity

    @callback
    def async_remove_hm_entity(self, entity_id: str) -> None:
        """Remove entity from active entities."""
        del self._active_hm_entities[entity_id]

    @callback
    def async_remove_hm_hub_entity(self, entity_id: str) -> None:
        """Remove entity from active hub entities."""
        del self._active_hm_hub_entities[entity_id]

    @callback
    def async_signal_new_hm_entity(self, entry_id: str, platform: HmPlatform) -> str:
        """Gateway specific event to signal new device."""
        return f"{DOMAIN}-new-entity-{entry_id}-{platform.value}"

    @callback
    def _async_callback_system_event(self, src: str, *args: Any) -> None:
        """Execute the callback for system based events."""
        _LOGGER.debug(
            "callback_system_event: Received system event %s for event for %s",
            src,
            self._instance_name,
        )

        if src == HH_EVENT_DEVICES_CREATED:
            new_devices = args[0]
            new_entities = []
            for device in new_devices:
                new_entities.extend(device.entities.values())
                new_entities.extend(device.custom_entities.values())

            # Handle event of new device creation in Homematic(IP) Local.
            for (platform, hm_entities) in self.async_get_new_hm_entities(
                new_entities=new_entities
            ).items():
                if hm_entities and len(hm_entities) > 0:
                    async_dispatcher_send(
                        self._hass,
                        self.async_signal_new_hm_entity(
                            entry_id=self._entry_id, platform=platform
                        ),
                        hm_entities,  # Don't send device if None, it would override default value in listeners
                    )
            self._async_add_virtual_remotes_to_device_registry()
        elif src == HH_EVENT_HUB_ENTITY_CREATED:
            if not self._hub and self.central.hub:
                self._hub = HaHub(
                    self._hass, control_unit=self, hm_hub=self.central.hub
                )
                self._hub.async_write_ha_state()
            new_hub_entities = args[0]
            # Handle event of new hub entity creation in Homematic(IP) Local.
            for (platform, hm_hub_entities) in self.async_get_new_hm_hub_entities(
                new_hub_entities=new_hub_entities
            ).items():
                if hm_hub_entities and len(hm_hub_entities) > 0:
                    async_dispatcher_send(
                        self._hass,
                        self.async_signal_new_hm_entity(
                            entry_id=self._entry_id, platform=platform
                        ),
                        hm_hub_entities,
                    )
            return None
        elif src == HH_EVENT_NEW_DEVICES:
            # ignore
            return None
        elif src == HH_EVENT_DELETE_DEVICES:
            # Handle event of device removed in Homematic(IP) Local.
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
        if hm_event_type == HmEventType.KEYPRESS:
            device_address = event_data[ATTR_ADDRESS]
            if device_entry := self._async_get_device(device_address=device_address):
                event_data[ATTR_DEVICE_ID] = device_entry.id
                event_data[ATTR_NAME] = device_entry.name_by_user or device_entry.name
            self._hass.bus.fire(
                event_type=hm_event_type.value,
                event_data=event_data,
            )
        elif hm_event_type == HmEventType.IMPULSE:
            self._hass.bus.fire(
                event_type=hm_event_type.value,
                event_data=event_data,
            )
        elif hm_event_type == HmEventType.DEVICE:
            device_address = event_data[ATTR_ADDRESS]
            name: str | None = None
            if device_entry := self._async_get_device(device_address=device_address):
                event_data[ATTR_DEVICE_ID] = device_entry.id
                name = device_entry.name_by_user or device_entry.name
            interface_id = event_data[ATTR_INTERFACE_ID]
            parameter = event_data[ATTR_PARAMETER]
            value = event_data[ATTR_VALUE]
            if parameter in (EVENT_STICKY_UN_REACH, EVENT_UN_REACH):
                title = f"{DOMAIN.upper()}-Device not reachable"
                message = f"{name} / {device_address} on interface {interface_id}"
                if self._hub:
                    availability_event_data = {
                        ATTR_ENTITY_ID: self._hub.entity_id,
                        EVENT_DATA_IDENTIFIER: device_address,
                        EVENT_DATA_TITLE: title,
                        EVENT_DATA_MESSAGE: message,
                        EVENT_DATA_AVAILABLE: value is True,
                    }
                    self._hass.bus.fire(
                        event_type=EVENT_DEVICE_AVAILABILITY,
                        event_data=availability_event_data,
                    )
        elif hm_event_type == HmEventType.INTERFACE:
            interface_id = event_data[ATTR_INTERFACE_ID]
            interface_event_type = event_data[ATTR_TYPE]
            available = event_data[ATTR_VALUE]
            if interface_event_type == HmInterfaceEventType.PROXY:
                title = f"{DOMAIN.upper()}-Interface not reachable"
                message = f"No connection to interface {interface_id}"
                if available:
                    self._async_dismiss_persistent_notification(
                        identifier=f"proxy-{interface_id}"
                    )
                else:
                    self._async_create_persistent_notification(
                        identifier=f"proxy-{interface_id}", title=title, message=message
                    )
            if interface_event_type == HmInterfaceEventType.CALLBACK:
                title = f"{DOMAIN.upper()}-XmlRPC-Server received no events."
                message = f"No callback events received for interface {interface_id} {CHECK_INTERVAL}s."
                if available:
                    self._async_dismiss_persistent_notification(
                        identifier=f"callback-{interface_id}"
                    )
                else:
                    self._async_create_persistent_notification(
                        identifier=f"callback-{interface_id}",
                        title=title,
                        message=message,
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
    def _async_get_device(self, device_address: str) -> DeviceEntry | None:
        """Return the device of the ha device."""
        if (hm_device := self.central.hm_devices.get(device_address)) is None:
            return None
        device_registry = dr.async_get(self._hass)
        return device_registry.async_get_device(
            identifiers={
                (
                    DOMAIN,
                    f"{hm_device.device_address}{IDENTIFIER_SEPARATOR}{hm_device.interface_id}",
                )
            }
        )

    @callback
    def async_get_entity_stats(self) -> tuple[dict[str, int], list[str]]:
        """Return statistics data about entities per platform."""
        device_types: list[str] = []
        platform_stats: dict[str, int] = {}
        for entity in self._active_hm_entities.values():
            platform = entity.platform.value
            if platform not in platform_stats:
                platform_stats[platform] = 0
            counter = platform_stats[platform]
            platform_stats[platform] = counter + 1
            if isinstance(entity, (CustomEntity, GenericEntity)):
                device_types.append(entity.device.device_type)
        return platform_stats, sorted(set(device_types))

    def _get_active_entities_by_device_address(
        self, device_address: str
    ) -> list[HmBaseEntity]:
        """Return used hm_entities by address."""
        entities: list[HmBaseEntity] = []
        for entity in self._active_hm_entities.values():
            if (
                isinstance(entity, HmCallbackEntity)
                and device_address == entity.device.device_address
            ):
                entities.append(entity)
        return entities


class ControlUnitTemp(BaseControlUnit):
    """Central unit to control a Homematic CCU for temporary usage."""

    async def async_start_direct(self) -> None:
        """Start the temporary control unit."""
        _LOGGER.debug(
            "Starting temporary ControlUnit %s",
            self._instance_name,
        )
        if self._central:
            await self._central.start_direct()
        else:
            _LOGGER.exception(
                "Starting temporary ControlUnit %s not possible, CentralUnit is not available",
                self._instance_name,
            )

    async def async_stop(self) -> None:
        """Stop the control unit."""
        await self.central.clear_all()
        await super().async_stop()

    async def async_validate_config_and_get_serial(self) -> str | None:
        """Validate the control configuration."""
        central = await self._async_create_central()
        serial = await central.validate_config_and_get_serial()
        await central.stop()
        return serial


class ControlConfig:
    """Config for a ControlUnit."""

    def __init__(
        self,
        hass: HomeAssistant,
        entry_id: str,
        data: Mapping[str, Any],
        default_port: int = PORT_ANY,
    ) -> None:
        """Create the required config for the ControlUnit."""
        self.hass = hass
        self.entry_id = entry_id
        self.data = data
        self.default_callback_port = default_port

    async def async_get_control_unit(self) -> ControlUnit:
        """Identify the used client."""
        control_unit = ControlUnit(self)
        await control_unit.async_init_central()
        return control_unit

    async def async_get_control_unit_temp(self) -> ControlUnitTemp:
        """Identify the used client."""
        control_unit = ControlUnitTemp(self._temporary_config)
        await control_unit.async_init_central()
        return control_unit

    @property
    def _temporary_config(self) -> ControlConfig:
        """Return a config for validation."""
        temporary_data: dict[str, Any] = deepcopy(dict(self.data))
        temporary_data[ATTR_INSTANCE_NAME] = "temporary_instance"
        return ControlConfig(
            hass=self.hass, entry_id="hmip_local_temporary", data=temporary_data
        )


class HaHub(Entity):
    """The HomeMatic hub. (CCU2/HomeGear)."""

    _attr_should_poll = False
    _attr_icon = "mdi:gradient-vertical"

    def __init__(
        self, hass: HomeAssistant, control_unit: ControlUnit, hm_hub: HmHub
    ) -> None:
        """Initialize HomeMatic hub."""
        self.hass = hass
        self._control: ControlUnit = control_unit
        self._hm_hub: HmHub = hm_hub
        self._attr_name: str = self._control.central.name
        self.entity_id = f"{DOMAIN}.{slugify(self._attr_name.lower())}"
        self._hm_hub.register_update_callback(self._async_update_hub)
        self.remove_listener: Callable = async_track_time_interval(
            self.hass, self._async_fetch_data, SYSVAR_SCAN_INTERVAL
        )

    def de_init(self) -> None:
        """De_init the hub."""
        if self.remove_listener and callback(self.remove_listener):
            self.remove_listener()

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        return self._hm_hub.available

    @property
    def control(self) -> ControlUnit:
        """Return the control unit."""
        return self._control

    async def _async_fetch_data(self, now: datetime) -> None:
        """Fetch data from backend."""
        _LOGGER.debug(
            "Fetching sysvars for %s",
            self.name,
        )
        await self._hm_hub.fetch_sysvar_data()
        await self._hm_hub.fetch_program_data()

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
        sysvar_entity = self._hm_hub.syvar_entities.get(name)
        if not sysvar_entity or name in self.extra_state_attributes:
            _LOGGER.error("Variable %s not found on %s", name, self.name)
            return

        await self._hm_hub.set_system_variable(name=name, value=value)

    @callback
    def _async_update_hub(self, *args: Any) -> None:
        """Update the HA hub."""
        self.async_write_ha_state()


async def validate_config_and_get_serial(control_config: ControlConfig) -> str | None:
    """Validate the control configuration."""
    control_unit = await control_config.async_get_control_unit_temp()
    return await control_unit.async_validate_config_and_get_serial()


def get_storage_folder(hass: HomeAssistant) -> str:
    """Return the base path where to store files for this integration."""
    return f"{hass.config.config_dir}/{DOMAIN}"


def get_cu_by_interface_id(
    hass: HomeAssistant, interface_id: str
) -> ControlUnit | None:
    """Get ControlUnit by interface_id."""
    for entry_id in hass.data[DOMAIN][CONTROL_UNITS].keys():
        control_unit: ControlUnit = hass.data[DOMAIN][CONTROL_UNITS][entry_id]
        if control_unit and control_unit.central.clients.get(interface_id):
            return control_unit
    return None


def get_device(hass: HomeAssistant, device_id: str) -> HmDevice | None:
    """Return the homematic device."""
    device_registry = dr.async_get(hass)
    device_entry: DeviceEntry | None = device_registry.async_get(device_id)
    if not device_entry:
        return None
    if (
        data := get_device_address_at_interface_from_identifiers(
            identifiers=device_entry.identifiers
        )
    ) is None:
        return None

    device_address = data[0]
    interface_id = data[1]

    if control_unit := get_cu_by_interface_id(hass=hass, interface_id=interface_id):
        return control_unit.central.hm_devices.get(device_address)
    return None
