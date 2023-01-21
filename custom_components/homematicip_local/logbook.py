"""Describe Homematic(IP) Local logbook events."""

from __future__ import annotations

from collections.abc import Callable

from hahomematic.const import ATTR_PARAMETER, HmEventType

from homeassistant.components.logbook import LOGBOOK_ENTRY_MESSAGE, LOGBOOK_ENTRY_NAME
from homeassistant.const import CONF_TYPE
from homeassistant.core import Event, HomeAssistant, callback

from .const import (
    ATTR_NAME,
    CONF_SUBTYPE,
    DOMAIN as HMIP_DOMAIN,
    EVENT_DATA_ERROR,
    EVENT_DATA_ERROR_VALUE,
)
from .helpers import HM_CLICK_EVENT_SCHEMA, HM_DEVICE_ERROR_EVENT_SCHEMA, is_valid_event


@callback
def async_describe_events(
    hass: HomeAssistant,
    async_describe_event: Callable[[str, str, Callable[[Event], dict[str, str]]], None],
) -> None:
    """Describe logbook events."""

    @callback
    def async_describe_homematic_click_event(event: Event) -> dict[str, str]:
        """Describe Homematic(IP) Local logbook click event."""
        if not is_valid_event(event_data=event.data, schema=HM_CLICK_EVENT_SCHEMA):
            return {}
        parameter = event.data[CONF_TYPE]
        channel_no = event.data[CONF_SUBTYPE]

        return {
            LOGBOOK_ENTRY_NAME: event.data[ATTR_NAME],
            LOGBOOK_ENTRY_MESSAGE: f" fired event {parameter.upper()} on channel {channel_no}",
        }

    @callback
    def async_describe_homematic_device_error_event(event: Event) -> dict[str, str]:
        """Describe Homematic(IP) Local logbook device error event."""
        if not is_valid_event(
            event_data=event.data, schema=HM_DEVICE_ERROR_EVENT_SCHEMA
        ):
            return {}
        error_name = event.data[ATTR_PARAMETER].replace("_", " ").title()
        error_value = event.data[EVENT_DATA_ERROR_VALUE]
        is_error = event.data[EVENT_DATA_ERROR]
        error_message = (
            f"{error_name} {error_value} occurred"
            if is_error
            else f"{error_name} resolved"
        )

        return {
            LOGBOOK_ENTRY_NAME: event.data[ATTR_NAME],
            LOGBOOK_ENTRY_MESSAGE: error_message,
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
