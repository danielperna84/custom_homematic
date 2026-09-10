"""Event platform for Homematic(IP) Local for OpenCCU."""

from __future__ import annotations

import logging
from typing import Final

from aiohomematic.central.events import DataPointStateChangedEvent, DeviceRemovedEvent, SubscriptionGroup
from aiohomematic.const import DATA_POINT_EVENTS, DataPointCategory, Parameter
from aiohomematic.interfaces import ChannelEventGroupProtocol
from aiohomematic.support.address import get_channel_no
from homeassistant.components.event import DoorbellEventType, EventDeviceClass, EventEntity
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import UndefinedType

from . import HomematicConfigEntry
from .const import DOMAIN, EVENT_ADDRESS, EVENT_CHANNEL_NO, EVENT_INTERFACE_ID, EVENT_MODEL
from .control_unit import ControlUnit, signal_new_data_point
from .entity_helpers.base import HmEventEntityDescription
from .entity_helpers.registry import REGISTRY

_LOGGER = logging.getLogger(__name__)

# The Homematic keypress that represents the ring on doorbell devices. HA requires
# doorbell event entities to support the standard 'ring' event type (mandatory from
# HA 2027.4), so this type is exposed and fired as 'ring' instead of 'press_short'.
_DOORBELL_RING_SOURCE: Final = Parameter.PRESS_SHORT.lower()


async def async_setup_entry(
    hass: HomeAssistant,
    entry: HomematicConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Homematic(IP) Local for OpenCCU event platform."""
    control_unit: ControlUnit = entry.runtime_data

    @callback
    def async_add_event(event_groups: tuple[ChannelEventGroupProtocol, ...]) -> None:
        """Add event from Homematic(IP) Local for OpenCCU."""
        _LOGGER.debug("ASYNC_ADD_EVENT: Adding %i event groups", len(event_groups))

        if entities := [
            AioHomematicEvent(
                control_unit=control_unit,
                event_group=event_group,
            )
            for event_group in event_groups
            if event_group.device_trigger_event_type in DATA_POINT_EVENTS
        ]:
            async_add_entities(entities)

    entry.async_on_unload(
        func=async_dispatcher_connect(
            hass=hass,
            signal=signal_new_data_point(entry_id=entry.entry_id, platform=DataPointCategory.EVENT_GROUP),
            target=async_add_event,
        )
    )

    for event_type in DATA_POINT_EVENTS:
        try:
            event_groups = control_unit.central.query_facade.get_event_groups(event_type=event_type, registered=False)
        except NotImplementedError as nie:
            # Both backends answer this call — aiohomematic in
            # central/query_facade.py, the loom client in
            # compat/aiohomematic/central/adapter.py — so this is a guard, not a
            # description of one of them: a backend that does not model event
            # groups sets up the platform without bootstrap entities instead of
            # failing the whole config entry.
            _LOGGER.debug("ASYNC_SETUP_ENTRY: Event groups unavailable for %s: %s", event_type, nie)
            continue
        async_add_event(event_groups=event_groups)


class AioHomematicEvent(EventEntity):
    """Representation of the Homematic(IP) Local for OpenCCU event."""

    _attr_entity_registry_enabled_default = True
    _attr_has_entity_name = True
    _attr_should_poll = False

    _unrecorded_attributes = frozenset({EVENT_ADDRESS, EVENT_CHANNEL_NO, EVENT_INTERFACE_ID, EVENT_MODEL})

    def __init__(
        self,
        control_unit: ControlUnit,
        event_group: ChannelEventGroupProtocol,
    ) -> None:
        """Initialize the event."""
        self._cu: ControlUnit = control_unit
        self._event_group = event_group
        self._attr_event_types = list(event_group.event_types)
        self._attr_translation_key = event_group.translation_key

        description = REGISTRY.find(
            category=DataPointCategory.EVENT_GROUP,
            device_model=event_group.device.model,
        )
        if isinstance(description, HmEventEntityDescription) and description.device_class is not None:
            self._attr_device_class = description.device_class
            if description.device_class == EventDeviceClass.DOORBELL:
                self._attr_event_types = [
                    DoorbellEventType.RING if event_type == _DOORBELL_RING_SOURCE else event_type
                    for event_type in self._attr_event_types
                ]

        self._attr_unique_id = f"{DOMAIN}_{event_group.unique_id}"
        # Carry the full device identity, not just the identifiers: if this
        # event entity happens to be the device's first registration, a bare
        # DeviceInfo would create the device entry without a name — the
        # generated (sticky) entity_id then degrades to the config-entry
        # title — and pin it area-less forever (suggested_area is
        # runtime-only and never re-applied after creation).
        hm_device = event_group.device
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, control_unit.device_identifier(device=hm_device))},
            manufacturer=hm_device.manufacturer,
            model=hm_device.model,
            model_id=hm_device.model_description,
            name=hm_device.name,
            serial_number=hm_device.address,
            sw_version=hm_device.firmware,
            suggested_area=hm_device.room,
        )
        self._attr_extra_state_attributes = {
            EVENT_INTERFACE_ID: event_group.device.interface_id,
            EVENT_ADDRESS: event_group.channel.address,
            # Parsed out of the channel address, not read off the channel: the
            # two backends spell the channel number differently — aiohomematic
            # has ChannelProtocol.no, the loom client's compat channel has
            # .number — while the address above is the one value both carry, in
            # the same '<address>:<no>' form. Automations need the number on its
            # own; deriving it here keeps that backend difference out of every
            # blueprint that would otherwise split the address itself.
            EVENT_CHANNEL_NO: get_channel_no(address=event_group.channel.address),
            EVENT_MODEL: event_group.device.model,
        }
        self._subscription_group: Final[SubscriptionGroup] = control_unit.central.event_bus.create_subscription_group(
            name=f"event_{event_group.unique_id}"
        )
        _LOGGER.debug(
            "init: Setting up %s %s",
            event_group.device.name,
            event_group.channel.name,
        )

    @property
    def available(self) -> bool:
        """Return if event is available."""
        return self._event_group.device.available

    @property
    def name(self) -> str | UndefinedType | None:
        """Return the name of the entity."""
        return self._event_group.name

    async def async_added_to_hass(self) -> None:
        """Register callbacks and load initial data."""
        self._event_group.register()
        self._subscription_group.subscribe(
            event_type=DataPointStateChangedEvent,
            event_key=self._event_group.unique_id,
            handler=self._async_event_changed,
        )
        self._subscription_group.subscribe(
            event_type=DeviceRemovedEvent,
            event_key=self._event_group.unique_id,
            handler=self._async_device_removed,
        )

    async def async_will_remove_from_hass(self) -> None:
        """Run when hmip device will be removed from hass."""
        self._event_group.unregister()
        self._subscription_group.unsubscribe_all()

    @callback
    def _async_device_removed(self, *, event: DeviceRemovedEvent) -> None:
        """Handle hm device removal."""
        # Fire-and-forget: HA tracks the task internally
        _ = self.hass.async_create_task(self.async_remove(force_remove=True))

        if not self.registry_entry:
            return

        if device_id := self.registry_entry.device_id:
            # Remove from device registry.
            device_registry = dr.async_get(self.hass)
            if device_registry.async_get(device_id) is not None:
                # This will also remove associated entities from entity registry.
                device_registry.async_remove_device(device_id)

    @callback
    def _async_event_changed(self, *, event: DataPointStateChangedEvent) -> None:
        """Handle device state changes."""
        # Don't update disabled entities
        if self.enabled:
            if triggered := self._event_group.last_triggered_event:
                event_type = triggered.parameter.lower()
                if self.device_class == EventDeviceClass.DOORBELL and event_type == _DOORBELL_RING_SOURCE:
                    event_type = DoorbellEventType.RING
                self._trigger_event(event_type)
                _LOGGER.debug("Device event emitted %s", self.name)
                self.async_schedule_update_ha_state()
        else:
            _LOGGER.debug(
                "Device event for %s not emitted. Entity is disabled",
                self.name,
            )
