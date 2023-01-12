"""Describe Homematic(IP) Local logbook events."""

from __future__ import annotations

from collections.abc import Callable

from hahomematic.const import ATTR_ADDRESS, HmEventType

from homeassistant.components.logbook import LOGBOOK_ENTRY_MESSAGE, LOGBOOK_ENTRY_NAME
from homeassistant.const import ATTR_DEVICE_ID, CONF_TYPE
from homeassistant.core import Event, HomeAssistant, callback
from homeassistant.helpers import device_registry as dr

from .const import (
    CONF_SUBTYPE,
    DOMAIN as HMIP_DOMAIN,
    EVENT_DATA_ERROR,
    EVENT_DATA_ERROR_NAME,
    EVENT_DATA_ERROR_VALUE,
    EVENT_DATA_UNAVAILABLE,
)


@callback
def async_describe_events(
    hass: HomeAssistant,
    async_describe_event: Callable[[str, str, Callable[[Event], dict[str, str]]], None],
) -> None:
    """Describe logbook events."""
    device_registry = dr.async_get(hass)

    def _get_device_name(event: Event) -> str:
        """Get device name from registry."""
        if device_entry := device_registry.async_get(
            device_id=event.data[ATTR_DEVICE_ID]
        ):
            if device_name := device_entry.name_by_user or device_entry.name:
                return device_name
        return event.data[ATTR_ADDRESS]

    @callback
    def async_describe_homematic_click_event(event: Event) -> dict[str, str]:
        """Describe Homematic(IP) Local logbook click event."""
        parameter = event.data[CONF_TYPE]
        channel_no = event.data[CONF_SUBTYPE]

        return {
            LOGBOOK_ENTRY_NAME: _get_device_name(event=event),
            LOGBOOK_ENTRY_MESSAGE: f" fired event {parameter.upper()} on channel {channel_no}",
        }

    @callback
    def async_describe_homematic_device_error_event(event: Event) -> dict[str, str]:
        """Describe Homematic(IP) Local logbook device error event."""
        error_name = event.data[EVENT_DATA_ERROR_NAME].replace("_", " ").title()
        error_value = event.data[EVENT_DATA_ERROR_VALUE]
        is_error = event.data[EVENT_DATA_ERROR]
        error_message = (
            f"{error_name} {error_value} occurred"
            if is_error
            else f"{error_name} resolved"
        )

        return {
            LOGBOOK_ENTRY_NAME: _get_device_name(event=event),
            LOGBOOK_ENTRY_MESSAGE: error_message,
        }

    @callback
    def async_describe_homematic_device_availability_event(
        event: Event,
    ) -> dict[str, str]:
        """Describe Homematic(IP) Local logbook device availability event."""
        unavailable = event.data[EVENT_DATA_UNAVAILABLE]

        return {
            LOGBOOK_ENTRY_NAME: _get_device_name(event=event),
            LOGBOOK_ENTRY_MESSAGE: "is not reachable"
            if unavailable
            else "is reachable again",
        }

    async_describe_event(
        HMIP_DOMAIN,
        HmEventType.KEYPRESS.value,
        async_describe_homematic_click_event,
    )

    async_describe_event(
        HMIP_DOMAIN,
        HmEventType.DEVICE_ERROR.value,
        async_describe_homematic_device_error_event,
    )

    async_describe_event(
        HMIP_DOMAIN,
        HmEventType.DEVICE_AVAILABILITY.value,
        async_describe_homematic_device_availability_event,
    )
