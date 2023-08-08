"""event for Homematic(IP) Local."""
from __future__ import annotations

import logging
from typing import Any

from hahomematic.const import ENTITY_EVENTS, HmPlatform
from hahomematic.platforms.event import GenericEvent
from homeassistant.components.event import EventDeviceClass, EventEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import UndefinedType

from .const import ATTR_ADDRESS, ATTR_INTERFACE_ID, ATTR_MODEL, CONTROL_UNITS, DOMAIN
from .control_unit import ControlUnit, async_signal_new_hm_entity

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Homematic(IP) Local event platform."""
    control_unit: ControlUnit = hass.data[DOMAIN][CONTROL_UNITS][entry.entry_id]

    @callback
    def async_add_event(args: Any) -> None:
        """Add event from Homematic(IP) Local."""
        entities: list[HaHomematicEvent] = []

        for hm_channel_events in args:
            entities.append(
                HaHomematicEvent(
                    control_unit=control_unit,
                    hm_channel_events=hm_channel_events,
                )
            )

        if entities:
            async_add_entities(entities)

    entry.async_on_unload(
        async_dispatcher_connect(
            hass,
            async_signal_new_hm_entity(
                entry_id=entry.entry_id, platform=HmPlatform.EVENT
            ),
            async_add_event,
        )
    )

    for event_type in ENTITY_EVENTS:
        async_add_event(
            control_unit.async_get_new_hm_channel_event_entities_by_event_type(
                event_type=event_type
            )
        )


class HaHomematicEvent(EventEntity):
    """Representation of the Homematic(IP) Local event."""

    _attr_device_class = EventDeviceClass.BUTTON
    _attr_entity_registry_enabled_default = True
    _attr_has_entity_name = True
    _attr_should_poll = False

    def __init__(
        self,
        control_unit: ControlUnit,
        hm_channel_events: list[GenericEvent],
    ) -> None:
        """Initialize the event."""
        self._cu: ControlUnit = control_unit
        self._attr_event_types = [
            event.parameter.lower() for event in hm_channel_events
        ]
        self._hm_primary_entity: GenericEvent = hm_channel_events[0]
        self._hm_channel_events = hm_channel_events
        self._attr_translation_key = self._hm_primary_entity.event_type.value.replace(
            ".", "_"
        )

        self._attr_unique_id = (
            f"{DOMAIN}_{self._hm_primary_entity.channel_unique_identifier}"
        )

        _LOGGER.debug(
            "init: Setting up %s %s",
            self._hm_primary_entity.device.name,
            self._hm_primary_entity.channel_name,
        )

    @property
    def available(self) -> bool:
        """Return if event is available."""
        return self._hm_primary_entity.device.available

    @property
    def device_info(self) -> DeviceInfo | None:
        """Return device specific attributes."""
        return DeviceInfo(
            identifiers={(DOMAIN, self._hm_primary_entity.device.identifier)},
        )

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return the state attributes of the generic channel event entity."""
        attributes: dict[str, Any] = {
            ATTR_INTERFACE_ID: self._hm_primary_entity.device.interface_id,
            ATTR_ADDRESS: self._hm_primary_entity.channel_address,
            ATTR_MODEL: self._hm_primary_entity.device.device_type,
        }

        return attributes

    @property
    def name(self) -> str | UndefinedType | None:
        """Return the name of the entity."""

        return self._hm_primary_entity.channel_name

    async def async_added_to_hass(self) -> None:
        """Register callbacks and load initial data."""

        for event in self._hm_channel_events:
            event.register_update_callback(update_callback=self._async_device_changed)
            event.register_remove_callback(remove_callback=self._async_device_removed)
        self._cu.async_add_hm_channel_events(
            entity_id=self.entity_id, hm_channel_events=self._hm_channel_events
        )

    @callback
    def _async_device_changed(self, *args: Any, **kwargs: Any) -> None:
        """Handle device state changes."""
        # Don't update disabled entities
        if self.enabled:
            self._trigger_event(event_type=kwargs["parameter"])
            _LOGGER.debug("Event %s", self.name)
            self.async_write_ha_state()
        else:
            _LOGGER.debug(
                "Device Changed Event for %s not fired. Entity is disabled",
                self.name,
            )

    async def async_will_remove_from_hass(self) -> None:
        """Run when hmip device will be removed from hass."""
        self._cu.async_remove_hm_channel_events(self.entity_id)

        # Remove callback from device.
        for event in self._hm_channel_events:
            event.unregister_update_callback(update_callback=self._async_device_changed)
            event.unregister_remove_callback(remove_callback=self._async_device_removed)

    @callback
    def _async_device_removed(self, *args: Any, **kwargs: Any) -> None:
        """Handle hm device removal."""
        self.hass.async_create_task(self.async_remove(force_remove=True))

        if not self.registry_entry:
            return

        if device_id := self.registry_entry.device_id:
            # Remove from device registry.
            device_registry = dr.async_get(self.hass)
            if device_id in device_registry.devices:
                # This will also remove associated entities from entity registry.
                device_registry.async_remove_device(device_id)
