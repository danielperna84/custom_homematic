"""HaHomematic is a Python 3 module for Home Assistant and Homematic(IP) devices."""
from __future__ import annotations

import asyncio
from collections.abc import Callable, Mapping
from copy import deepcopy
from datetime import datetime, timedelta
import logging
from typing import Any, Final, cast

from hahomematic.central import INTERFACE_EVENT_SCHEMA, CentralConfig, CentralUnit
from hahomematic.client import InterfaceConfig
from hahomematic.const import (
    CONF_PASSWORD,
    CONF_USERNAME,
    ENTITY_EVENTS,
    EVENT_ADDRESS,
    EVENT_AVAILABLE,
    EVENT_DATA,
    EVENT_INTERFACE_ID,
    EVENT_PARAMETER,
    EVENT_SECONDS_SINCE_LAST_EVENT,
    EVENT_TYPE,
    EVENT_VALUE,
    HUB_PLATFORMS,
    IP_ANY_V4,
    PLATFORMS,
    PORT_ANY,
    DeviceFirmwareState,
    EntityUsage,
    EventType,
    HmPlatform,
    InterfaceEventType,
    InterfaceName,
    Manufacturer,
    Parameter,
    ParamsetKey,
    SystemEvent,
    SystemInformation,
)
from hahomematic.platforms.custom.entity import CustomEntity
from hahomematic.platforms.device import HmDevice
from hahomematic.platforms.entity import BaseEntity
from hahomematic.platforms.event import GenericEvent
from hahomematic.platforms.generic.entity import GenericEntity, WrapperEntity
from hahomematic.platforms.hub.entity import GenericHubEntity
from hahomematic.platforms.update import HmUpdate

from homeassistant.const import CONF_HOST, CONF_PATH, CONF_PORT
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import aiohttp_client, device_registry as dr
from homeassistant.helpers.device_registry import (
    DeviceEntry,
    DeviceEntryType,
    DeviceInfo,
)
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.helpers.issue_registry import (
    IssueSeverity,
    async_create_issue,
    async_delete_issue,
)

from .const import (
    CONF_CALLBACK_HOST,
    CONF_CALLBACK_PORT,
    CONF_ENABLE_SYSTEM_NOTIFICATIONS,
    CONF_INSTANCE_NAME,
    CONF_INTERFACE,
    CONF_JSON_PORT,
    CONF_SYSVAR_SCAN_ENABLED,
    CONF_SYSVAR_SCAN_INTERVAL,
    CONF_TLS,
    CONF_VERIFY_TLS,
    CONTROL_UNITS,
    DEFAULT_DEVICE_FIRMWARE_CHECK_ENABLED,
    DEFAULT_DEVICE_FIRMWARE_CHECK_INTERVAL,
    DEFAULT_DEVICE_FIRMWARE_DELIVERING_CHECK_INTERVAL,
    DEFAULT_DEVICE_FIRMWARE_UPDATING_CHECK_INTERVAL,
    DEFAULT_SYSVAR_SCAN_ENABLED,
    DEFAULT_SYSVAR_SCAN_INTERVAL,
    DOMAIN,
    EVENT_DEVICE_ID,
    EVENT_ERROR,
    EVENT_ERROR_VALUE,
    EVENT_IDENTIFIER,
    EVENT_MESSAGE,
    EVENT_NAME,
    EVENT_TITLE,
    EVENT_UNAVAILABLE,
    FILTER_ERROR_EVENT_PARAMETERS,
    HMIP_LOCAL_PLATFORMS,
    LEARN_MORE_URL_PING_PONG_MISMATCH,
    LEARN_MORE_URL_XMLRPC_SERVER_RECEIVES_NO_EVENTS,
    MASTER_SCAN_INTERVAL,
)
from .support import (
    CLICK_EVENT_SCHEMA,
    DEVICE_AVAILABILITY_EVENT_SCHEMA,
    DEVICE_ERROR_EVENT_SCHEMA,
    HmBaseEntity,
    cleanup_click_event_data,
    get_device_address_at_interface_from_identifiers,
    is_valid_event,
)

_LOGGER = logging.getLogger(__name__)


class BaseControlUnit:
    """Base central point to control a central unit."""

    def __init__(self, control_config: ControlConfig) -> None:
        """Init the control unit."""
        self._config: Final = control_config
        self._hass = control_config.hass
        self._entry_id = control_config.entry_id
        self._config_data = control_config.data
        self._default_callback_port = control_config.default_callback_port
        self._start_direct = control_config.start_direct
        self._instance_name = self._config_data[CONF_INSTANCE_NAME]
        self._enable_system_notifications = self._config_data[CONF_ENABLE_SYSTEM_NOTIFICATIONS]
        self._central: CentralUnit = self._create_central()
        self._attr_device_info = DeviceInfo(
            identifiers={
                (
                    DOMAIN,
                    self._central.name,
                )
            },
            manufacturer=Manufacturer.EQ3,
            model=self._central.model,
            name=self._central.name,
            sw_version=self._central.version,
            # Link to the homematic control unit.
            via_device=cast(tuple[str, str], self._central.name),
        )

    async def start_central(self) -> None:
        """Start the central unit."""
        _LOGGER.debug(
            "Starting central unit %s",
            self._instance_name,
        )
        await self._central.start()
        _LOGGER.info("Started central unit for %s", self._instance_name)

    async def stop_central(self, *args: Any) -> None:
        """Stop the control unit."""
        _LOGGER.debug(
            "Stopping central unit %s",
            self._instance_name,
        )
        if self._central.started:
            await self._central.stop()
            _LOGGER.info("Stopped central unit for %s", self._instance_name)

    @property
    def central(self) -> CentralUnit:
        """Return the Homematic(IP) Local central unit instance."""
        return self._central

    @property
    def config(self) -> ControlConfig:
        """Return the Homematic(IP) Local central unit instance."""
        return self._config

    @property
    def device_info(self) -> DeviceInfo | None:
        """Return device specific attributes."""
        return self._attr_device_info

    def _create_central(self) -> CentralUnit:
        """Create the central unit for ccu callbacks."""
        interface_configs: set[InterfaceConfig] = set()
        for interface_name in self._config_data[CONF_INTERFACE]:
            interface = self._config_data[CONF_INTERFACE][interface_name]
            interface_configs.add(
                InterfaceConfig(
                    central_name=self._instance_name,
                    interface=InterfaceName(interface_name),
                    port=interface[CONF_PORT],
                    remote_path=interface.get(CONF_PATH),
                )
            )
        # use last 10 chars of entry_id for central_id uniqueness
        central_id = self._entry_id[-10:]
        return CentralConfig(
            name=self._instance_name,
            storage_folder=get_storage_folder(self._hass),
            host=self._config_data[CONF_HOST],
            username=self._config_data[CONF_USERNAME],
            password=self._config_data[CONF_PASSWORD],
            central_id=central_id,
            tls=self._config_data[CONF_TLS],
            verify_tls=self._config_data[CONF_VERIFY_TLS],
            client_session=aiohttp_client.async_get_clientsession(self._hass),
            json_port=self._config_data[CONF_JSON_PORT],
            callback_host=self._config_data.get(CONF_CALLBACK_HOST)
            if self._config_data.get(CONF_CALLBACK_HOST) != IP_ANY_V4
            else None,
            callback_port=self._config_data.get(CONF_CALLBACK_PORT)
            if self._config_data.get(CONF_CALLBACK_PORT) != PORT_ANY
            else None,
            default_callback_port=self._default_callback_port,
            interface_configs=interface_configs,
            start_direct=self._start_direct,
        ).create_central()


class ControlUnit(BaseControlUnit):
    """Unit to control a central unit."""

    def __init__(self, control_config: ControlConfig) -> None:
        """Init the control unit."""
        super().__init__(control_config=control_config)

        # {entity_id, entity}
        self._active_hm_entities: dict[str, HmBaseEntity] = {}
        # {entity_id, [channel_events]}
        self._active_hm_channel_events: dict[str, list[GenericEvent]] = {}
        # {entity_id, entity}
        self._active_hm_update_entities: dict[str, HmUpdate] = {}
        # {entity_id, sysvar_entity}
        self._active_hm_hub_entities: dict[str, GenericHubEntity] = {}
        self._scheduler = HmScheduler(
            hass=self._hass,
            control_unit=self,
        )

    async def start_central(self) -> None:
        """Start the central unit."""
        self._central.register_system_event_callback(callback_handler=self._callback_system_event)
        self._central.register_ha_event_callback(callback_handler=self._callback_ha_event)
        await super().start_central()
        self._add_central_to_device_registry()

    async def stop_central(self, *args: Any) -> None:
        """Stop the central unit."""
        if self._scheduler.initialized:
            self._scheduler.de_init()
        if central := self._central:
            central.unregister_system_event_callback(callback_handler=self._callback_system_event)
            central.unregister_ha_event_callback(callback_handler=self._callback_ha_event)

        await super().stop_central(*args)

    @callback
    def _add_central_to_device_registry(self) -> None:
        """Add the central to device registry."""
        device_registry = dr.async_get(self._hass)
        device_registry.async_get_or_create(
            config_entry_id=self._entry_id,
            identifiers={
                (
                    DOMAIN,
                    self._central.name,
                )
            },
            manufacturer=Manufacturer.EQ3,
            model=self._central.model,
            sw_version=self._central.version,
            name=self._central.name,
            entry_type=DeviceEntryType.SERVICE,
            configuration_url=self._central.central_url,
        )

    @callback
    def _add_virtual_remotes_to_device_registry(self) -> None:
        """Add the virtual remotes to device registry."""
        if not self._central.has_clients:
            _LOGGER.error(
                "Cannot create ControlUnit %s virtual remote devices. No clients",
                self._instance_name,
            )
            return

        device_registry = dr.async_get(self._hass)
        for virtual_remote in self._central.get_virtual_remotes():
            device_registry.async_get_or_create(
                config_entry_id=self._entry_id,
                identifiers={
                    (
                        DOMAIN,
                        virtual_remote.identifier,
                    )
                },
                manufacturer=Manufacturer.EQ3,
                name=virtual_remote.name,
                model=virtual_remote.device_type,
                sw_version=virtual_remote.firmware,
                # Link to the homematic control unit.
                via_device=cast(tuple[str, str], self._central.name),
            )

    @callback
    def get_hm_entity(self, entity_id: str) -> HmBaseEntity | None:
        """Return hm-entity by requested entity_id."""
        return self._active_hm_entities.get(entity_id)

    @callback
    def _identify_new_hm_channel_events(
        self, new_channel_events: list[dict[int, list[GenericEvent]]]
    ) -> list[list[GenericEvent]]:
        """Return all hm-update-entities."""
        active_unique_ids: list[str] = []
        for events in self._active_hm_channel_events.values():
            for event in events:
                active_unique_ids.append(event.unique_identifier)
        hm_channel_events: list[list[GenericEvent]] = []

        for device_channel_events in new_channel_events:
            for channel_events in device_channel_events.values():
                if channel_events[0].channel_unique_identifier not in active_unique_ids:
                    hm_channel_events.append(channel_events)
                    continue

        return hm_channel_events

    @callback
    def get_new_hm_channel_events_by_event_type(
        self, event_type: EventType
    ) -> list[list[GenericEvent]]:
        """Return all channel event entities."""
        active_unique_ids: list[str] = []
        for events in self._active_hm_channel_events.values():
            for event in events:
                active_unique_ids.append(event.unique_identifier)

        hm_channel_events: list[list[GenericEvent]] = []
        for device in self._central.devices:
            for channel_events in device.get_channel_events(event_type=event_type).values():
                if channel_events[0].channel_unique_identifier not in active_unique_ids:
                    hm_channel_events.append(channel_events)
                    continue

        return hm_channel_events

    @callback
    def _identify_new_hm_entities(
        self, new_entities: list[BaseEntity]
    ) -> dict[HmPlatform, list[BaseEntity]]:
        """Return all hm-entities."""
        active_unique_ids = [
            entity.unique_identifier for entity in self._active_hm_entities.values()
        ]
        # init dict
        hm_entities: dict[HmPlatform, list[BaseEntity]] = {}
        for hm_platform in PLATFORMS:
            hm_entities[hm_platform] = []

        for entity in new_entities:
            if (
                entity.usage != EntityUsage.NO_CREATE
                and entity.unique_identifier not in active_unique_ids
                and entity.platform.value in HMIP_LOCAL_PLATFORMS
            ):
                hm_entities[entity.platform].append(entity)

        return hm_entities

    @callback
    def _identify_new_hm_update_entities(
        self, new_update_entities: list[HmUpdate]
    ) -> list[HmUpdate]:
        """Return all hm-update-entities."""
        active_unique_ids = [
            entity.unique_identifier for entity in self._active_hm_update_entities.values()
        ]
        hm_update_entities: list[HmUpdate] = []

        for update_entity in new_update_entities:
            if update_entity.unique_identifier not in active_unique_ids:
                hm_update_entities.append(update_entity)

        return hm_update_entities

    @callback
    def get_new_hm_entities_by_platform(self, platform: HmPlatform) -> list[BaseEntity]:
        """Return all new hm-entities by platform."""
        active_unique_ids = [
            entity.unique_identifier for entity in self._active_hm_entities.values()
        ]
        return self._central.get_entities_by_platform(
            platform=platform, existing_unique_ids=active_unique_ids
        )

    @callback
    def _identify_new_hm_hub_entities(
        self, new_hub_entities: list[GenericHubEntity]
    ) -> dict[HmPlatform, list[GenericHubEntity]]:
        """Return all hm-hub-entities."""
        active_unique_ids = [
            entity.unique_identifier for entity in self._active_hm_hub_entities.values()
        ]
        # init dict
        hm_hub_entities: dict[HmPlatform, list[GenericHubEntity]] = {}
        for hm_hub_platform in HUB_PLATFORMS:
            hm_hub_entities[hm_hub_platform] = []

        for hub_entity in new_hub_entities:
            if hub_entity.unique_identifier not in active_unique_ids:
                hm_hub_entities[hub_entity.platform].append(hub_entity)

        return hm_hub_entities

    @callback
    def get_new_hm_hub_entities_by_platform(self, platform: HmPlatform) -> list[GenericHubEntity]:
        """Return all new hm-hub-entities by platform."""
        active_unique_ids = [
            entity.unique_identifier for entity in self._active_hm_hub_entities.values()
        ]

        return self._central.get_hub_entities_by_platform(
            platform=platform, existing_unique_ids=active_unique_ids
        )

    @callback
    def get_new_hm_update_entities(self) -> list[HmUpdate]:
        """Return all update entities."""
        active_unique_ids = [
            entity.unique_identifier for entity in self._active_hm_update_entities.values()
        ]
        return [
            device.update_entity
            for device in self._central.devices
            if device.update_entity
            and device.update_entity.unique_identifier not in active_unique_ids
        ]

    @callback
    def add_hm_entity(self, entity_id: str, hm_entity: HmBaseEntity) -> None:
        """Add entity to active entities."""
        self._active_hm_entities[entity_id] = hm_entity

    @callback
    def add_hm_channel_events(self, entity_id: str, hm_channel_events: list[GenericEvent]) -> None:
        """Add channel events to active channel events."""
        self._active_hm_channel_events[entity_id] = hm_channel_events

    @callback
    def add_hm_update_entity(self, entity_id: str, hm_entity: HmUpdate) -> None:
        """Add entity to active update entities."""
        self._active_hm_update_entities[entity_id] = hm_entity

    @callback
    def add_hm_hub_entity(self, entity_id: str, hm_hub_entity: GenericHubEntity) -> None:
        """Add entity to active hub entities."""
        self._active_hm_hub_entities[entity_id] = hm_hub_entity

    @callback
    def remove_hm_entity(self, entity_id: str) -> None:
        """Remove entity from active entities."""
        del self._active_hm_entities[entity_id]

    @callback
    def remove_hm_channel_events(self, entity_id: str) -> None:
        """Remove channel_events from active channel_events."""
        del self._active_hm_channel_events[entity_id]

    @callback
    def remove_hm_update_entity(self, entity_id: str) -> None:
        """Remove entity from active update entities."""
        del self._active_hm_update_entities[entity_id]

    @callback
    def remove_hm_hub_entity(self, entity_id: str) -> None:
        """Remove entity from active hub entities."""
        del self._active_hm_hub_entities[entity_id]

    @callback
    def _callback_system_event(self, system_event: SystemEvent, **kwargs: Any) -> None:
        """Execute the callback for system based events."""
        _LOGGER.debug(
            "callback_system_event: Received system event %s for event for %s",
            system_event,
            self._instance_name,
        )

        if system_event == SystemEvent.DEVICES_CREATED:
            new_devices = kwargs["new_devices"]
            new_channel_events = []
            new_entities = []
            new_update_entities = []
            for device in new_devices:
                for event_type in ENTITY_EVENTS:
                    if channel_events := device.get_channel_events(event_type=event_type):
                        new_channel_events.append(channel_events)
                new_entities.extend(device.get_all_entities())
                if device.update_entity:
                    new_update_entities.append(device.update_entity)

            # Handle event of new device creation in Homematic(IP) Local.
            for platform, hm_entities in self._identify_new_hm_entities(
                new_entities=new_entities
            ).items():
                if hm_entities and len(hm_entities) > 0:
                    async_dispatcher_send(
                        self._hass,
                        signal_new_hm_entity(entry_id=self._entry_id, platform=platform),
                        hm_entities,
                    )
            if hm_update_entities := self._identify_new_hm_update_entities(
                new_update_entities=new_update_entities
            ):
                async_dispatcher_send(
                    self._hass,
                    signal_new_hm_entity(entry_id=self._entry_id, platform=HmPlatform.UPDATE),
                    hm_update_entities,
                )
            if hm_channel_events := self._identify_new_hm_channel_events(
                new_channel_events=new_channel_events
            ):
                async_dispatcher_send(
                    self._hass,
                    signal_new_hm_entity(entry_id=self._entry_id, platform=HmPlatform.EVENT),
                    hm_channel_events,
                )
            self._add_virtual_remotes_to_device_registry()
        elif system_event == SystemEvent.HUB_REFRESHED:
            if not self._scheduler.initialized:
                self._hass.create_task(target=self._scheduler.init())
            if self._config.sysvar_scan_enabled:
                new_hub_entities = kwargs["new_hub_entities"]
                # Handle event of new hub entity creation in Homematic(IP) Local.
                for platform, hm_hub_entities in self._identify_new_hm_hub_entities(
                    new_hub_entities=new_hub_entities
                ).items():
                    if hm_hub_entities and len(hm_hub_entities) > 0:
                        async_dispatcher_send(
                            self._hass,
                            signal_new_hm_entity(entry_id=self._entry_id, platform=platform),
                            hm_hub_entities,
                        )
            return None
        return None

    @callback
    def _callback_ha_event(self, hm_event_type: EventType, event_data: dict[str, Any]) -> None:
        """Execute the callback used for device related events."""

        interface_id = event_data[EVENT_INTERFACE_ID]
        if hm_event_type == EventType.INTERFACE:
            interface_event_type = event_data[EVENT_TYPE]
            issue_id = f"{interface_event_type}-{interface_id}"
            event_data = cast(dict[str, Any], INTERFACE_EVENT_SCHEMA(event_data))
            data = event_data[EVENT_DATA]
            if interface_event_type == InterfaceEventType.CALLBACK:
                if not self._enable_system_notifications:
                    _LOGGER.debug("SYSTEM NOTIFICATION disabled for CALLBACK")
                    return
                if data[EVENT_AVAILABLE]:
                    async_delete_issue(hass=self._hass, domain=DOMAIN, issue_id=issue_id)
                else:
                    async_create_issue(
                        hass=self._hass,
                        domain=DOMAIN,
                        issue_id=issue_id,
                        is_fixable=False,
                        learn_more_url=LEARN_MORE_URL_XMLRPC_SERVER_RECEIVES_NO_EVENTS,
                        severity=IssueSeverity.WARNING,
                        translation_key="xmlrpc_server_receives_no_events",
                        translation_placeholders={
                            EVENT_INTERFACE_ID: interface_id,
                            EVENT_SECONDS_SINCE_LAST_EVENT: data[EVENT_SECONDS_SINCE_LAST_EVENT],
                        },
                    )
            elif interface_event_type == InterfaceEventType.PINGPONG:
                if not self._enable_system_notifications:
                    _LOGGER.debug("SYSTEM NOTIFICATION disabled for PINGPONG")
                    return
                async_create_issue(
                    hass=self._hass,
                    domain=DOMAIN,
                    issue_id=issue_id,
                    is_fixable=False,
                    learn_more_url=LEARN_MORE_URL_PING_PONG_MISMATCH,
                    severity=IssueSeverity.WARNING,
                    translation_key="ping_pong_mismatch",
                    translation_placeholders={
                        CONF_INSTANCE_NAME: self._instance_name,
                    },
                )
            elif interface_event_type == InterfaceEventType.PROXY:
                if data[EVENT_AVAILABLE]:
                    async_delete_issue(hass=self._hass, domain=DOMAIN, issue_id=issue_id)
                else:
                    async_create_issue(
                        hass=self._hass,
                        domain=DOMAIN,
                        issue_id=issue_id,
                        is_fixable=False,
                        severity=IssueSeverity.WARNING,
                        translation_key="interface_not_reachable",
                        translation_placeholders={
                            EVENT_INTERFACE_ID: interface_id,
                        },
                    )

        else:
            device_address = event_data[EVENT_ADDRESS]
            name: str | None = None
            if device_entry := self._get_device_entry(device_address=device_address):
                name = device_entry.name_by_user or device_entry.name
                event_data.update({EVENT_DEVICE_ID: device_entry.id, EVENT_NAME: name})
            if hm_event_type in (EventType.IMPULSE, EventType.KEYPRESS):
                event_data = cleanup_click_event_data(event_data=event_data)
                if is_valid_event(event_data=event_data, schema=CLICK_EVENT_SCHEMA):
                    self._hass.bus.fire(
                        event_type=hm_event_type.value,
                        event_data=event_data,
                    )
            elif hm_event_type == EventType.DEVICE_AVAILABILITY:
                parameter = event_data[EVENT_PARAMETER]
                unavailable = event_data[EVENT_VALUE]
                if parameter in (Parameter.STICKY_UN_REACH, Parameter.UN_REACH):
                    title = f"{DOMAIN.upper()} Device not reachable"
                    event_data.update(
                        {
                            EVENT_IDENTIFIER: f"{device_address}_DEVICE_AVAILABILITY",
                            EVENT_TITLE: title,
                            EVENT_MESSAGE: f"{name}/{device_address} "
                            f"on interface {interface_id}",
                            EVENT_UNAVAILABLE: unavailable,
                        }
                    )
                    if is_valid_event(
                        event_data=event_data,
                        schema=DEVICE_AVAILABILITY_EVENT_SCHEMA,
                    ):
                        self._hass.bus.fire(
                            event_type=hm_event_type.value,
                            event_data=event_data,
                        )
            elif hm_event_type == EventType.DEVICE_ERROR:
                error_parameter = event_data[EVENT_PARAMETER]
                if error_parameter in FILTER_ERROR_EVENT_PARAMETERS:
                    return None
                error_parameter_display = error_parameter.replace("_", " ").title()
                title = f"{DOMAIN.upper()} Device Error"
                error_message: str = ""
                error_value = event_data[EVENT_VALUE]
                display_error: bool = False
                if isinstance(error_value, bool):
                    display_error = error_value
                    error_message = (
                        f"{name}/{device_address} on interface {interface_id}: "
                        f"{error_parameter_display}"
                    )
                if isinstance(error_value, int):
                    display_error = error_value != 0
                    error_message = (
                        f"{name}/{device_address} on interface {interface_id}: "
                        f"{error_parameter_display} {error_value}"
                    )
                event_data.update(
                    {
                        EVENT_IDENTIFIER: f"{device_address}_{error_parameter}",
                        EVENT_TITLE: title,
                        EVENT_MESSAGE: error_message,
                        EVENT_ERROR_VALUE: error_value,
                        EVENT_ERROR: display_error,
                    }
                )
                if is_valid_event(event_data=event_data, schema=DEVICE_ERROR_EVENT_SCHEMA):
                    self._hass.bus.fire(
                        event_type=hm_event_type.value,
                        event_data=event_data,
                    )

    @callback
    def _get_device_entry(self, device_address: str) -> DeviceEntry | None:
        """Return the device of the ha device."""
        if (hm_device := self._central.get_device(address=device_address)) is None:
            return None
        device_registry = dr.async_get(self._hass)
        return device_registry.async_get_device(
            identifiers={
                (
                    DOMAIN,
                    hm_device.identifier,
                )
            }
        )

    async def fetch_all_system_variables(self) -> None:
        """Fetch all system variables from CCU / Homegear."""
        if not self._scheduler.initialized:
            _LOGGER.debug("Hub scheduler for %s is not initialized", self._instance_name)
            return None

        await self._scheduler.fetch_sysvars()

    @callback
    def get_entity_stats(self) -> tuple[dict[str, int], list[str]]:
        """Return statistics data about entities per platform."""
        device_types: list[str] = []
        platform_stats: dict[str, int] = {}
        for entity in self._active_hm_entities.values():
            platform = entity.platform.value
            if platform not in platform_stats:
                platform_stats[platform] = 0
            counter = platform_stats[platform]
            platform_stats[platform] = counter + 1
            if isinstance(entity, CustomEntity | GenericEntity):
                device_types.append(entity.device.device_type)
        return platform_stats, sorted(set(device_types))

    @callback
    def _get_active_hm_entities_by_device_address(self, device_address: str) -> list[HmBaseEntity]:
        """Return used hm_entities by address."""
        entities: list[HmBaseEntity] = []
        for entity in self._active_hm_entities.values():
            if (
                isinstance(entity, CustomEntity | GenericEntity | WrapperEntity)
                and device_address == entity.device.device_address
            ):
                entities.append(entity)
        return entities


class ControlUnitTemp(BaseControlUnit):
    """Central unit to control a central unit for temporary usage."""

    async def stop_central(self, *args: Any) -> None:
        """Stop the control unit."""
        await self._central.clear_all_caches()
        await super().stop_central(*args)


class ControlConfig:
    """Config for a ControlUnit."""

    def __init__(
        self,
        hass: HomeAssistant,
        entry_id: str,
        data: Mapping[str, Any],
        default_port: int = PORT_ANY,
        start_direct: bool = False,
        device_firmware_check_enabled: bool = DEFAULT_DEVICE_FIRMWARE_CHECK_ENABLED,
        device_firmware_check_interval: int = DEFAULT_DEVICE_FIRMWARE_CHECK_INTERVAL,
        device_firmware_delivering_check_interval: int = DEFAULT_DEVICE_FIRMWARE_DELIVERING_CHECK_INTERVAL,
        device_firmware_updating_check_interval: int = DEFAULT_DEVICE_FIRMWARE_UPDATING_CHECK_INTERVAL,
        master_scan_interval: int = MASTER_SCAN_INTERVAL,
    ) -> None:
        """Create the required config for the ControlUnit."""
        self.hass: Final = hass
        self.entry_id: Final = entry_id
        self.data: Final = data
        self.default_callback_port: Final = default_port
        self.start_direct: Final = start_direct
        self.device_firmware_check_enabled: Final = device_firmware_check_enabled
        self.device_firmware_check_interval: Final = device_firmware_check_interval
        self.device_firmware_delivering_check_interval: Final = (
            device_firmware_delivering_check_interval
        )
        self.device_firmware_updating_check_interval: Final = (
            device_firmware_updating_check_interval
        )
        self.master_scan_interval: Final = master_scan_interval
        self.sysvar_scan_enabled: Final = data.get(
            CONF_SYSVAR_SCAN_ENABLED, DEFAULT_SYSVAR_SCAN_ENABLED
        )
        self.sysvar_scan_interval: Final = data.get(
            CONF_SYSVAR_SCAN_INTERVAL, DEFAULT_SYSVAR_SCAN_INTERVAL
        )

    async def create_control_unit(self) -> ControlUnit:
        """Identify the used client."""
        return ControlUnit(self)

    async def create_control_unit_temp(self) -> ControlUnitTemp:
        """Identify the used client."""
        return ControlUnitTemp(self._temporary_config)

    @property
    def _temporary_config(self) -> ControlConfig:
        """Return a config for validation."""
        temporary_data: dict[str, Any] = deepcopy(dict(self.data))
        temporary_data[CONF_INSTANCE_NAME] = "temporary_instance"
        return ControlConfig(
            hass=self.hass,
            entry_id="hmip_local_temporary",
            data=temporary_data,
            start_direct=True,
        )


class HmScheduler:
    """The Homematic(IP) Local hub scheduler. (CCU/HomeGear)."""

    def __init__(
        self,
        hass: HomeAssistant,
        control_unit: ControlUnit,
    ) -> None:
        """Initialize Homematic(IP) Local hub scheduler."""
        self._hass = hass
        self._control: ControlUnit = control_unit
        self._central: CentralUnit = control_unit.central
        self._initialized = False
        self._remove_device_firmware_check_listener: Callable | None = None
        self._remove_device_firmware_delivering_check_listener: Callable | None = None
        self._remove_device_firmware_updating_check_listener: Callable | None = None
        self._remove_master_listener: Callable | None = None
        self._remove_sysvar_listener: Callable | None = None
        self._sema_init: Final = asyncio.Semaphore()

    @property
    def initialized(self) -> bool:
        """Return initialized state."""
        return self._initialized

    async def init(self) -> None:
        """Execute the initial data refresh."""
        async with self._sema_init:
            if self._initialized:
                return
            self._initialized = True
            if self._control.config.sysvar_scan_enabled:
                # sysvar_scan_interval == 0 means sysvar scanning is disabled
                self._remove_sysvar_listener = async_track_time_interval(
                    hass=self._hass,
                    action=self._fetch_data,
                    interval=timedelta(seconds=self._control.config.sysvar_scan_interval),
                    cancel_on_shutdown=True,
                )
            self._remove_master_listener = async_track_time_interval(
                hass=self._hass,
                action=self._fetch_master_data,
                interval=timedelta(seconds=self._control.config.master_scan_interval),
                cancel_on_shutdown=True,
            )

            if self._control.config.device_firmware_check_enabled:
                self._remove_device_firmware_check_listener = async_track_time_interval(
                    hass=self._hass,
                    action=self._fetch_device_firmware_update_data,
                    interval=timedelta(
                        seconds=self._control.config.device_firmware_check_interval
                    ),
                    cancel_on_shutdown=True,
                )
                self._remove_device_firmware_delivering_check_listener = async_track_time_interval(
                    hass=self._hass,
                    action=self._fetch_device_firmware_update_data_in_delivery,
                    interval=timedelta(
                        seconds=self._control.config.device_firmware_delivering_check_interval
                    ),
                    cancel_on_shutdown=True,
                )
                self._remove_device_firmware_updating_check_listener = async_track_time_interval(
                    hass=self._hass,
                    action=self._fetch_device_firmware_update_data_in_update,
                    interval=timedelta(
                        seconds=self._control.config.device_firmware_updating_check_interval
                    ),
                )
            await self._central.refresh_firmware_data()

    def de_init(self) -> None:
        """De_init the hub scheduler."""
        if self._remove_sysvar_listener and callable(self._remove_sysvar_listener):
            self._remove_sysvar_listener()
        if self._remove_master_listener and callable(self._remove_master_listener):
            self._remove_master_listener()
        if self._remove_device_firmware_check_listener and callable(
            self._remove_device_firmware_check_listener
        ):
            self._remove_device_firmware_check_listener()
        if self._remove_device_firmware_delivering_check_listener and callable(
            self._remove_device_firmware_delivering_check_listener
        ):
            self._remove_device_firmware_delivering_check_listener()
        if self._remove_device_firmware_updating_check_listener and callable(
            self._remove_device_firmware_updating_check_listener
        ):
            self._remove_device_firmware_updating_check_listener()
        self._initialized = False

    async def _fetch_data(self, now: datetime) -> None:
        """Fetch data from backend."""
        if self._control.config.sysvar_scan_enabled is False:
            _LOGGER.warning(
                "Scheduled fetching of programs and sysvars for %s is disabled",
                self._central.name,
            )
            return None
        _LOGGER.debug(
            "Scheduled fetching of programs and sysvars for %s",
            self._central.name,
        )
        await self._central.fetch_sysvar_data()
        await self._central.fetch_program_data()

    async def fetch_sysvars(self) -> None:
        """Fetch sysvars from backend."""
        if self._control.config.sysvar_scan_enabled is False:
            _LOGGER.warning(
                "Manually fetching of sysvars for %s is disabled",
                self._central.name,
            )
            return None
        _LOGGER.debug("Manually fetching of sysvars for %s", self._central.name)
        await self._central.fetch_sysvar_data()

    async def _fetch_master_data(self, now: datetime) -> None:
        """Fetch master entities from backend."""
        _LOGGER.debug(
            "Scheduled fetching of master entities for %s",
            self._central.name,
        )
        await self._central.load_and_refresh_entity_data(paramset_key=ParamsetKey.MASTER)

    async def _fetch_device_firmware_update_data(self, now: datetime) -> None:
        """Fetch device firmware update data from backend."""
        _LOGGER.debug(
            "Scheduled fetching of device firmware update data for %s",
            self._central.name,
        )
        await self._central.refresh_firmware_data()

    async def _fetch_device_firmware_update_data_in_delivery(self, now: datetime) -> None:
        """Fetch device firmware update data from backend for delivering devices."""
        _LOGGER.debug(
            "Scheduled fetching of device firmware update data for delivering devices for %s",
            self._central.name,
        )
        await self._central.refresh_firmware_data_by_state(
            device_firmware_states=(
                DeviceFirmwareState.DELIVER_FIRMWARE_IMAGE,
                DeviceFirmwareState.LIVE_DELIVER_FIRMWARE_IMAGE,
            )
        )

    async def _fetch_device_firmware_update_data_in_update(self, now: datetime) -> None:
        """Fetch device firmware update data from backend for updating devices."""
        _LOGGER.debug(
            "Scheduled fetching of device firmware update data for updating devices for %s",
            self._central.name,
        )
        await self._central.refresh_firmware_data_by_state(
            device_firmware_states=(
                DeviceFirmwareState.READY_FOR_UPDATE,
                DeviceFirmwareState.DO_UPDATE_PENDING,
                DeviceFirmwareState.PERFORMING_UPDATE,
            )
        )


def signal_new_hm_entity(entry_id: str, platform: HmPlatform) -> str:
    """Gateway specific event to signal new device."""
    return f"{DOMAIN}-new-entity-{entry_id}-{platform.value}"


async def validate_config_and_get_system_information(
    control_config: ControlConfig,
) -> SystemInformation | None:
    """Validate the control configuration."""
    if control_unit := await control_config.create_control_unit_temp():
        return await control_unit.central.validate_config_and_get_system_information()
    return None


def get_storage_folder(hass: HomeAssistant) -> str:
    """Return the base path where to store files for this integration."""
    return f"{hass.config.config_dir}/{DOMAIN}"


def get_cu_by_interface_id(hass: HomeAssistant, interface_id: str) -> ControlUnit | None:
    """Get ControlUnit by interface_id."""
    for entry_id in hass.data[DOMAIN][CONTROL_UNITS]:
        control_unit: ControlUnit = hass.data[DOMAIN][CONTROL_UNITS][entry_id]
        if control_unit and control_unit.central.has_client(interface_id=interface_id):
            return control_unit
    return None


def get_hm_device_by_id(hass: HomeAssistant, device_id: str) -> HmDevice | None:
    """Return the homematic device."""
    device_entry: DeviceEntry | None = dr.async_get(hass).async_get(device_id)
    if not device_entry:
        return None
    if (
        data := get_device_address_at_interface_from_identifiers(
            identifiers=device_entry.identifiers
        )
    ) is None:
        return None

    device_address, interface_id = data
    if control_unit := get_cu_by_interface_id(hass=hass, interface_id=interface_id):
        return control_unit.central.get_device(address=device_address)
    return None


def get_hm_device_by_address(hass: HomeAssistant, device_address: str) -> HmDevice | None:
    """Return the homematic device."""
    for entry_id in hass.data[DOMAIN][CONTROL_UNITS]:
        control_unit: ControlUnit = hass.data[DOMAIN][CONTROL_UNITS][entry_id]
        if hm_device := control_unit.central.get_device(address=device_address):
            return hm_device
    return None
