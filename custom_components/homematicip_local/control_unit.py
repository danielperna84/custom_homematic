"""HaHomematic is a Python 3 module for Home Assistant and Homematic(IP) devices."""
from __future__ import annotations

from collections.abc import Callable, Mapping
from copy import deepcopy
from datetime import datetime, timedelta
import logging
from typing import Any, cast

from hahomematic.central_unit import CentralConfig, CentralUnit
from hahomematic.client import InterfaceConfig
from hahomematic.const import (
    ATTR_ADDRESS,
    ATTR_CALLBACK_HOST,
    ATTR_CALLBACK_PORT,
    ATTR_HOST,
    ATTR_INTERFACE,
    ATTR_INTERFACE_ID,
    ATTR_JSON_PORT,
    ATTR_MESSAGE,
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
    ENTITY_EVENTS,
    EVENT_STICKY_UN_REACH,
    EVENT_UN_REACH,
    HH_EVENT_DEVICES_CREATED,
    HH_EVENT_HUB_REFRESHED,
    IP_ANY_V4,
    MANUFACTURER_EQ3,
    PARAMSET_KEY_MASTER,
    PORT_ANY,
    HmDeviceFirmwareState,
    HmEntityUsage,
    HmEventType,
    HmInterface,
    HmInterfaceEventType,
    HmPlatform,
)
from hahomematic.platforms.custom.entity import CustomEntity
from hahomematic.platforms.device import HmDevice
from hahomematic.platforms.entity import BaseEntity
from hahomematic.platforms.event import GenericEvent
from hahomematic.platforms.generic.entity import GenericEntity, WrapperEntity
from hahomematic.platforms.hub.entity import GenericHubEntity
from hahomematic.platforms.update import HmUpdate
from hahomematic.support import HM_INTERFACE_EVENT_SCHEMA, SystemInformation

from homeassistant.const import ATTR_DEVICE_ID
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import aiohttp_client, device_registry as dr
from homeassistant.helpers.device_registry import DeviceEntry, DeviceEntryType
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.event import async_track_time_interval

from .const import (
    ATTR_ENABLE_SYSTEM_NOTIFICATIONS,
    ATTR_INSTANCE_NAME,
    ATTR_NAME,
    ATTR_PATH,
    ATTR_SYSVAR_SCAN_ENABLED,
    ATTR_SYSVAR_SCAN_INTERVAL,
    CONTROL_UNITS,
    DEFAULT_SYSVAR_SCAN_INTERVAL,
    DEVICE_FIRMWARE_CHECK_INTERVAL,
    DEVICE_FIRMWARE_DELIVERING_CHECK_INTERVAL,
    DEVICE_FIRMWARE_UPDATING_CHECK_INTERVAL,
    DOMAIN,
    EVENT_DATA_ERROR,
    EVENT_DATA_ERROR_VALUE,
    EVENT_DATA_IDENTIFIER,
    EVENT_DATA_MESSAGE,
    EVENT_DATA_TITLE,
    EVENT_DATA_UNAVAILABLE,
    FILTER_ERROR_EVENT_PARAMETERS,
    HMIP_LOCAL_PLATFORMS,
    MASTER_SCAN_INTERVAL,
)
from .helpers import (
    HM_CLICK_EVENT_SCHEMA,
    HM_DEVICE_AVAILABILITY_EVENT_SCHEMA,
    HM_DEVICE_ERROR_EVENT_SCHEMA,
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
        self._hass = control_config.hass
        self._entry_id = control_config.entry_id
        self._config_data = control_config.data
        self._default_callback_port = control_config.default_callback_port
        self._instance_name = self._config_data[ATTR_INSTANCE_NAME]
        self._enable_system_notifications = self._config_data[
            ATTR_ENABLE_SYSTEM_NOTIFICATIONS
        ]
        self._central: CentralUnit | None = None

    async def async_init_central(self) -> None:
        """Start the central unit."""
        _LOGGER.debug(
            "Init central unit %s",
            self._instance_name,
        )
        self._central = await self._async_create_central()

    async def async_start_central(self) -> None:
        """Start the central unit."""
        _LOGGER.debug(
            "Starting central unit %s",
            self._instance_name,
        )
        if self._central:
            await self._central.start()
        else:
            _LOGGER.exception(
                "Starting central unit %s not possible",
                self._instance_name,
            )
        _LOGGER.info("Started central unit for %s", self._instance_name)

    @callback
    def stop_central(self, *args: Any) -> None:
        """
        Wrap the call to async_stop.

        Used as an argument to EventBus.async_listen_once.
        """
        self._hass.async_create_task(self.async_stop_central())
        _LOGGER.info("Stopped central unit for %s", self._instance_name)

    async def async_stop_central(self) -> None:
        """Stop the control unit."""
        _LOGGER.debug(
            "Stopping central unit %s",
            self._instance_name,
        )
        if self._central is not None:
            await self._central.stop()

    @property
    def central(self) -> CentralUnit:
        """Return the Homematic(IP) Local central unit instance."""
        if self._central is not None:
            return self._central
        raise HomeAssistantError("homematicip_local.central not initialized")

    async def _async_create_central(self) -> CentralUnit:
        """Create the central unit for ccu callbacks."""
        interface_configs: set[InterfaceConfig] = set()
        for interface_name in self._config_data[ATTR_INTERFACE]:
            interface = self._config_data[ATTR_INTERFACE][interface_name]
            interface_configs.add(
                InterfaceConfig(
                    central_name=self._instance_name,
                    interface=HmInterface(interface_name),
                    port=interface[ATTR_PORT],
                    remote_path=interface.get(ATTR_PATH),
                )
            )
        # use last 10 chars of entry_id for central_id uniqueness
        central_id = self._entry_id[-10:]
        return await CentralConfig(
            name=self._instance_name,
            storage_folder=get_storage_folder(self._hass),
            host=self._config_data[ATTR_HOST],
            username=self._config_data[ATTR_USERNAME],
            password=self._config_data[ATTR_PASSWORD],
            central_id=central_id,
            tls=self._config_data[ATTR_TLS],
            verify_tls=self._config_data[ATTR_VERIFY_TLS],
            client_session=aiohttp_client.async_get_clientsession(self._hass),
            json_port=self._config_data[ATTR_JSON_PORT],
            callback_host=self._config_data.get(ATTR_CALLBACK_HOST)
            if self._config_data.get(ATTR_CALLBACK_HOST) != IP_ANY_V4
            else None,
            callback_port=self._config_data.get(ATTR_CALLBACK_PORT)
            if self._config_data.get(ATTR_CALLBACK_PORT) != PORT_ANY
            else None,
            default_callback_port=self._default_callback_port,
            interface_configs=interface_configs,
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
        self._scheduler: HmScheduler | None = None

    async def async_start_central(self) -> None:
        """Start the central unit."""
        if self._central:
            self._central.register_system_event_callback(
                callback_handler=self._async_callback_system_event
            )
            self._central.register_ha_event_callback(
                callback_handler=self._async_callback_ha_event
            )
            await super().async_start_central()
            self._async_add_central_to_device_registry()

    async def async_stop_central(self) -> None:
        """Stop the central unit."""
        if self._scheduler:
            self._scheduler.de_init()
        if self._central:
            self._central.unregister_system_event_callback(
                callback_handler=self._async_callback_system_event
            )
            self._central.unregister_ha_event_callback(
                callback_handler=self._async_callback_ha_event
            )

        await super().async_stop_central()

    @property
    def device_info(self) -> DeviceInfo | None:
        """Return device specific attributes."""
        if self._central:
            return DeviceInfo(
                identifiers={
                    (
                        DOMAIN,
                        self._central.name,
                    )
                },
                manufacturer=MANUFACTURER_EQ3,
                model=self._central.model,
                name=self._central.name,
                sw_version=self._central.version,
                # Link to the homematic control unit.
                via_device=cast(tuple[str, str], self._central.name),
            )
        return None

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
            manufacturer=MANUFACTURER_EQ3,
            model=self.central.model,
            sw_version=self.central.version,
            name=self.central.name,
            entry_type=DeviceEntryType.SERVICE,
            configuration_url=self.central.central_url,
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
                manufacturer=MANUFACTURER_EQ3,
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
    def async_get_new_hm_channel_event_entities(
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
    def async_get_new_hm_channel_event_entities_by_event_type(
        self, event_type: HmEventType
    ) -> list[list[GenericEvent]]:
        """Return all channel event entities."""
        active_unique_ids: list[str] = []
        for events in self._active_hm_channel_events.values():
            for event in events:
                active_unique_ids.append(event.unique_identifier)

        hm_channel_events: list[list[GenericEvent]] = []
        for device in self.central.devices:
            for channel_events in device.get_channel_events(
                event_type=event_type
            ).values():
                if channel_events[0].channel_unique_identifier not in active_unique_ids:
                    hm_channel_events.append(channel_events)
                    continue

        return hm_channel_events

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
                entity.usage != HmEntityUsage.NO_CREATE
                and entity.unique_identifier not in active_unique_ids
                and entity.platform.value in HMIP_LOCAL_PLATFORMS
            ):
                hm_entities[entity.platform].append(entity)

        return hm_entities

    @callback
    def async_get_new_hm_update_entities(
        self, new_update_entities: list[HmUpdate]
    ) -> list[HmUpdate]:
        """Return all hm-update-entities."""
        active_unique_ids = [
            entity.unique_identifier
            for entity in self._active_hm_update_entities.values()
        ]
        hm_update_entities: list[HmUpdate] = []

        for update_entity in new_update_entities:
            if update_entity.unique_identifier not in active_unique_ids:
                hm_update_entities.append(update_entity)

        return hm_update_entities

    @callback
    def async_get_new_hm_entities_by_platform(
        self, platform: HmPlatform
    ) -> list[BaseEntity]:
        """Return all new hm-entities by platform."""
        active_unique_ids = [
            entity.unique_identifier for entity in self._active_hm_entities.values()
        ]
        return self.central.get_entities_by_platform(
            platform=platform, existing_unique_ids=active_unique_ids
        )

    @callback
    def async_get_new_hm_hub_entities(
        self, new_hub_entities: list[GenericHubEntity]
    ) -> dict[HmPlatform, list[GenericHubEntity]]:
        """Return all hm-hub-entities."""
        active_unique_ids = [
            entity.unique_identifier for entity in self._active_hm_hub_entities.values()
        ]
        # init dict
        hm_hub_entities: dict[HmPlatform, list[GenericHubEntity]] = {}
        for hm_hub_platform in AVAILABLE_HM_HUB_PLATFORMS:
            hm_hub_entities[hm_hub_platform] = []

        for hub_entity in new_hub_entities:
            if hub_entity.unique_identifier not in active_unique_ids:
                hm_hub_entities[hub_entity.platform].append(hub_entity)

        return hm_hub_entities

    @callback
    def async_get_new_hm_hub_entities_by_platform(
        self, platform: HmPlatform
    ) -> list[GenericHubEntity]:
        """Return all new hm-hub-entities by platform."""
        active_unique_ids = [
            entity.unique_identifier for entity in self._active_hm_hub_entities.values()
        ]

        return self.central.get_hub_entities_by_platform(
            platform=platform, existing_unique_ids=active_unique_ids
        )

    @callback
    def async_get_update_entities(self) -> list[HmUpdate]:
        """Return all update entities."""
        active_unique_ids = [
            entity.unique_identifier
            for entity in self._active_hm_update_entities.values()
        ]
        return [
            device.update_entity
            for device in self.central.devices
            if device.update_entity
            and device.update_entity.unique_identifier not in active_unique_ids
        ]

    @callback
    def async_add_hm_entity(self, entity_id: str, hm_entity: HmBaseEntity) -> None:
        """Add entity to active entities."""
        self._active_hm_entities[entity_id] = hm_entity

    @callback
    def async_add_hm_channel_events(
        self, entity_id: str, hm_channel_events: list[GenericEvent]
    ) -> None:
        """Add channel events to active channel events."""
        self._active_hm_channel_events[entity_id] = hm_channel_events

    @callback
    def async_add_hm_update_entity(self, entity_id: str, hm_entity: HmUpdate) -> None:
        """Add entity to active update entities."""
        self._active_hm_update_entities[entity_id] = hm_entity

    @callback
    def async_add_hm_hub_entity(
        self, entity_id: str, hm_hub_entity: GenericHubEntity
    ) -> None:
        """Add entity to active hub entities."""
        self._active_hm_hub_entities[entity_id] = hm_hub_entity

    @callback
    def async_remove_hm_entity(self, entity_id: str) -> None:
        """Remove entity from active entities."""
        del self._active_hm_entities[entity_id]

    @callback
    def async_remove_hm_channel_events(self, entity_id: str) -> None:
        """Remove channel_events from active channel_events."""
        del self._active_hm_channel_events[entity_id]

    @callback
    def async_remove_hm_update_entity(self, entity_id: str) -> None:
        """Remove entity from active update entities."""
        del self._active_hm_update_entities[entity_id]

    @callback
    def async_remove_hm_hub_entity(self, entity_id: str) -> None:
        """Remove entity from active hub entities."""
        del self._active_hm_hub_entities[entity_id]

    @callback
    def _async_callback_system_event(self, name: str, **kwargs: Any) -> None:
        """Execute the callback for system based events."""
        _LOGGER.debug(
            "callback_system_event: Received system event %s for event for %s",
            name,
            self._instance_name,
        )

        if name == HH_EVENT_DEVICES_CREATED:
            new_devices = kwargs["new_devices"]
            new_channel_events = []
            new_entities = []
            new_update_entities = []
            for device in new_devices:
                for event_type in ENTITY_EVENTS:
                    if channel_events := device.get_channel_events(
                        event_type=event_type
                    ):
                        new_channel_events.append(channel_events)
                new_entities.extend(device.get_all_entities())
                if device.update_entity:
                    new_update_entities.append(device.update_entity)

            # Handle event of new device creation in Homematic(IP) Local.
            for platform, hm_entities in self.async_get_new_hm_entities(
                new_entities=new_entities
            ).items():
                if hm_entities and len(hm_entities) > 0:
                    async_dispatcher_send(
                        self._hass,
                        async_signal_new_hm_entity(
                            entry_id=self._entry_id, platform=platform
                        ),
                        hm_entities,
                    )
            if hm_update_entities := self.async_get_new_hm_update_entities(
                new_update_entities=new_update_entities
            ):
                async_dispatcher_send(
                    self._hass,
                    async_signal_new_hm_entity(
                        entry_id=self._entry_id, platform=HmPlatform.UPDATE
                    ),
                    hm_update_entities,
                )
            if hm_channel_events := self.async_get_new_hm_channel_event_entities(
                new_channel_events=new_channel_events
            ):
                async_dispatcher_send(
                    self._hass,
                    async_signal_new_hm_entity(
                        entry_id=self._entry_id, platform=HmPlatform.EVENT
                    ),
                    hm_channel_events,
                )
            self._async_add_virtual_remotes_to_device_registry()
        elif name == HH_EVENT_HUB_REFRESHED:
            if not self._scheduler:
                sysvar_scan_enabled: bool = self._config_data.get(
                    ATTR_SYSVAR_SCAN_ENABLED, True
                )
                sysvar_scan_interval: int = self._config_data.get(
                    ATTR_SYSVAR_SCAN_INTERVAL, DEFAULT_SYSVAR_SCAN_INTERVAL
                )
                self._scheduler = HmScheduler(
                    self._hass,
                    control_unit=self,
                    sysvar_scan_enabled=sysvar_scan_enabled,
                    sysvar_scan_interval=sysvar_scan_interval,
                )
                self._hass.create_task(target=self._scheduler.init())
            if self._scheduler and self._scheduler.sysvar_scan_enabled:
                new_hub_entities = kwargs["new_hub_entities"]
                # Handle event of new hub entity creation in Homematic(IP) Local.
                for platform, hm_hub_entities in self.async_get_new_hm_hub_entities(
                    new_hub_entities=new_hub_entities
                ).items():
                    if hm_hub_entities and len(hm_hub_entities) > 0:
                        async_dispatcher_send(
                            self._hass,
                            async_signal_new_hm_entity(
                                entry_id=self._entry_id, platform=platform
                            ),
                            hm_hub_entities,
                        )
            return None
        return None

    @callback
    def _async_callback_ha_event(
        self, hm_event_type: HmEventType, event_data: dict[str, Any]
    ) -> None:
        """Execute the callback used for device related events."""

        interface_id = event_data[ATTR_INTERFACE_ID]
        if hm_event_type == HmEventType.INTERFACE:
            interface_event_type = event_data[ATTR_TYPE]
            identifier = f"{interface_event_type}-{interface_id}"
            event_data = cast(dict[str, Any], HM_INTERFACE_EVENT_SCHEMA(event_data))
            if interface_event_type == HmInterfaceEventType.CALLBACK:
                if not self._enable_system_notifications:
                    _LOGGER.debug("SYSTEM NOTIFICATION disabled for CALLBACK")
                    return
                title = f"{DOMAIN.upper()}-XmlRPC-Server received no events."
                if event_data[ATTR_VALUE]:
                    self._async_dismiss_persistent_notification(identifier=identifier)
                else:
                    self._async_create_persistent_notification(
                        identifier=identifier,
                        title=title,
                        message=event_data[ATTR_MESSAGE],
                    )
            elif interface_event_type == HmInterfaceEventType.PINGPONG:
                if not self._enable_system_notifications:
                    _LOGGER.debug("SYSTEM NOTIFICATION disabled for PINGPONG")
                    return
                self._async_create_persistent_notification(
                    identifier=identifier,
                    title=f"{DOMAIN.upper()}-Ping/Pong Mismatch on Interface",
                    message=event_data[ATTR_MESSAGE],
                )
            elif interface_event_type == HmInterfaceEventType.PROXY:
                if event_data[ATTR_VALUE]:
                    self._async_dismiss_persistent_notification(identifier=identifier)
                else:
                    self._async_create_persistent_notification(
                        identifier=identifier,
                        title=f"{DOMAIN.upper()}-Interface not reachable",
                        message=event_data[ATTR_MESSAGE],
                    )
        else:
            device_address = event_data[ATTR_ADDRESS]
            name: str | None = None
            if device_entry := self._async_get_device(device_address=device_address):
                name = device_entry.name_by_user or device_entry.name
                event_data.update({ATTR_DEVICE_ID: device_entry.id, ATTR_NAME: name})
            if hm_event_type in (HmEventType.IMPULSE, HmEventType.KEYPRESS):
                event_data = cleanup_click_event_data(event_data=event_data)
                if is_valid_event(event_data=event_data, schema=HM_CLICK_EVENT_SCHEMA):
                    self._hass.bus.fire(
                        event_type=hm_event_type.value,
                        event_data=event_data,
                    )
            elif hm_event_type == HmEventType.DEVICE_AVAILABILITY:
                parameter = event_data[ATTR_PARAMETER]
                unavailable = event_data[ATTR_VALUE]
                if parameter in (EVENT_STICKY_UN_REACH, EVENT_UN_REACH):
                    title = f"{DOMAIN.upper()} Device not reachable"
                    event_data.update(
                        {
                            EVENT_DATA_IDENTIFIER: f"{device_address}_DEVICE_AVAILABILITY",
                            EVENT_DATA_TITLE: title,
                            EVENT_DATA_MESSAGE: f"{name}/{device_address} "
                            f"on interface {interface_id}",
                            EVENT_DATA_UNAVAILABLE: unavailable,
                        }
                    )
                    if is_valid_event(
                        event_data=event_data,
                        schema=HM_DEVICE_AVAILABILITY_EVENT_SCHEMA,
                    ):
                        self._hass.bus.fire(
                            event_type=hm_event_type.value,
                            event_data=event_data,
                        )
            elif hm_event_type == HmEventType.DEVICE_ERROR:
                error_parameter = event_data[ATTR_PARAMETER]
                if error_parameter in FILTER_ERROR_EVENT_PARAMETERS:
                    return None
                error_parameter_display = error_parameter.replace("_", " ").title()
                title = f"{DOMAIN.upper()} Device Error"
                error_message: str = ""
                error_value = event_data[ATTR_VALUE]
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
                        EVENT_DATA_IDENTIFIER: f"{device_address}_{error_parameter}",
                        EVENT_DATA_TITLE: title,
                        EVENT_DATA_MESSAGE: error_message,
                        EVENT_DATA_ERROR_VALUE: error_value,
                        EVENT_DATA_ERROR: display_error,
                    }
                )
                if is_valid_event(
                    event_data=event_data, schema=HM_DEVICE_ERROR_EVENT_SCHEMA
                ):
                    self._hass.bus.fire(
                        event_type=hm_event_type.value,
                        event_data=event_data,
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
        if (
            hm_device := self.central.get_device(device_address=device_address)
        ) is None:
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

    async def async_fetch_all_system_variables(self) -> None:
        """Fetch all system variables from CCU / Homegear."""
        if not self._scheduler:
            _LOGGER.debug(
                "Hub scheduler for %s is not initialized", self._instance_name
            )
            return None

        await self._scheduler.async_fetch_sysvars()

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
            if isinstance(entity, CustomEntity | GenericEntity):
                device_types.append(entity.device.device_type)
        return platform_stats, sorted(set(device_types))

    def _get_active_entities_by_device_address(
        self, device_address: str
    ) -> list[HmBaseEntity]:
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
                "Starting temporary ControlUnit %s not possible, "
                "central unit is not available",
                self._instance_name,
            )

    async def async_stop_central(self) -> None:
        """Stop the control unit."""
        await self.central.clear_all_caches()
        await super().async_stop_central()


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


class HmScheduler:
    """The Homematic(IP) Local hub scheduler. (CCU/HomeGear)."""

    def __init__(
        self,
        hass: HomeAssistant,
        control_unit: ControlUnit,
        sysvar_scan_enabled: bool,
        sysvar_scan_interval: int,
        master_scan_interval: int = MASTER_SCAN_INTERVAL,
        device_firmware_check_enabled: bool = True,
        device_firmware_check_interval: int = DEVICE_FIRMWARE_CHECK_INTERVAL,
        device_firmware_delivering_check_interval: int = DEVICE_FIRMWARE_DELIVERING_CHECK_INTERVAL,
        device_firmware_updating_check_interval: int = DEVICE_FIRMWARE_UPDATING_CHECK_INTERVAL,
    ) -> None:
        """Initialize Homematic(IP) Local hub scheduler."""
        self.hass = hass
        self._control: ControlUnit = control_unit
        self._central: CentralUnit = control_unit.central
        self.remove_sysvar_listener: Callable | None = None
        # sysvar_scan_interval == 0 means sysvar scanning is disabled
        self.sysvar_scan_enabled = sysvar_scan_enabled
        if self.sysvar_scan_enabled:
            self.remove_sysvar_listener = async_track_time_interval(
                self.hass,
                self._async_fetch_data,
                timedelta(seconds=sysvar_scan_interval),
            )
        self.remove_master_listener: Callable | None = async_track_time_interval(
            self.hass,
            self._async_fetch_master_data,
            timedelta(seconds=master_scan_interval),
        )
        self.device_firmware_check_enabled = device_firmware_check_enabled
        if self.device_firmware_check_enabled:
            self.remove_device_firmware_check_listener = async_track_time_interval(
                self.hass,
                self._async_fetch_device_firmware_update_data,
                timedelta(seconds=device_firmware_check_interval),
            )
            self.remove_device_firmware_delivering_check_listener = (
                async_track_time_interval(
                    self.hass,
                    self._async_fetch_device_firmware_update_data_in_delivery,
                    timedelta(seconds=device_firmware_delivering_check_interval),
                )
            )
            self.remove_device_firmware_updating_check_listener = (
                async_track_time_interval(
                    self.hass,
                    self._async_fetch_device_firmware_update_data_in_update,
                    timedelta(seconds=device_firmware_updating_check_interval),
                )
            )

    async def init(self) -> None:
        """Execute the initial data refresh."""
        await self._central.refresh_firmware_data()

    def de_init(self) -> None:
        """De_init the hub scheduler."""
        if self.remove_sysvar_listener is not None:
            self.remove_sysvar_listener()
        if self.remove_master_listener is not None:
            self.remove_master_listener()
        if self.remove_device_firmware_check_listener is not None:
            self.remove_device_firmware_check_listener()
        if self.remove_device_firmware_delivering_check_listener is not None:
            self.remove_device_firmware_delivering_check_listener()

    async def _async_fetch_data(self, now: datetime) -> None:
        """Fetch data from backend."""
        if self.sysvar_scan_enabled is False:
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

    async def async_fetch_sysvars(self) -> None:
        """Fetch sysvars from backend."""
        if self.sysvar_scan_enabled is False:
            _LOGGER.warning(
                "Manually fetching of sysvars for %s is disabled",
                self._central.name,
            )
            return None
        _LOGGER.debug("Manually fetching of sysvars for %s", self._central.name)
        await self._central.fetch_sysvar_data()

    async def _async_fetch_master_data(self, now: datetime) -> None:
        """Fetch master entities from backend."""
        _LOGGER.debug(
            "Scheduled fetching of master entities for %s",
            self._central.name,
        )
        await self._central.load_and_refresh_entity_data(
            paramset_key=PARAMSET_KEY_MASTER
        )

    async def _async_fetch_device_firmware_update_data(self, now: datetime) -> None:
        """Fetch device firmware update data from backend."""
        _LOGGER.debug(
            "Scheduled fetching of device firmware update data for %s",
            self._central.name,
        )
        await self._central.refresh_firmware_data()

    async def _async_fetch_device_firmware_update_data_in_delivery(
        self, now: datetime
    ) -> None:
        """Fetch device firmware update data from backend for delivering devices."""
        _LOGGER.debug(
            "Scheduled fetching of device firmware update data for delivering devices for %s",
            self._central.name,
        )
        await self._central.refresh_firmware_data_by_state(
            device_firmware_states=(
                HmDeviceFirmwareState.DELIVER_FIRMWARE_IMAGE,
                HmDeviceFirmwareState.LIVE_DELIVER_FIRMWARE_IMAGE,
            )
        )

    async def _async_fetch_device_firmware_update_data_in_update(
        self, now: datetime
    ) -> None:
        """Fetch device firmware update data from backend for updating devices."""
        _LOGGER.debug(
            "Scheduled fetching of device firmware update data for updating devices for %s",
            self._central.name,
        )
        await self._central.refresh_firmware_data_by_state(
            device_firmware_states=(
                HmDeviceFirmwareState.READY_FOR_UPDATE,
                HmDeviceFirmwareState.DO_UPDATE_PENDING,
                HmDeviceFirmwareState.PERFORMING_UPDATE,
            )
        )


def async_signal_new_hm_entity(entry_id: str, platform: HmPlatform) -> str:
    """Gateway specific event to signal new device."""
    return f"{DOMAIN}-new-entity-{entry_id}-{platform.value}"


async def validate_config_and_get_system_information(
    control_config: ControlConfig,
) -> SystemInformation | None:
    """Validate the control configuration."""
    if control_unit := await control_config.async_get_control_unit_temp():
        return await control_unit.central.validate_config_and_get_system_information()
    return None


def get_storage_folder(hass: HomeAssistant) -> str:
    """Return the base path where to store files for this integration."""
    return f"{hass.config.config_dir}/{DOMAIN}"


def get_cu_by_interface_id(
    hass: HomeAssistant, interface_id: str
) -> ControlUnit | None:
    """Get ControlUnit by interface_id."""
    for entry_id in hass.data[DOMAIN][CONTROL_UNITS]:
        control_unit: ControlUnit = hass.data[DOMAIN][CONTROL_UNITS][entry_id]
        if control_unit and control_unit.central.has_client(interface_id=interface_id):
            return control_unit
    return None


def get_device_by_id(hass: HomeAssistant, device_id: str) -> HmDevice | None:
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
        return control_unit.central.get_device(device_address=device_address)
    return None


def get_device_by_address(hass: HomeAssistant, device_address: str) -> HmDevice | None:
    """Return the homematic device."""
    for entry_id in hass.data[DOMAIN][CONTROL_UNITS]:
        control_unit: ControlUnit = hass.data[DOMAIN][CONTROL_UNITS][entry_id]
        if hm_device := control_unit.central.get_device(device_address=device_address):
            return hm_device
    return None
