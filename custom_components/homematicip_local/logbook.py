"""Describe Homematic(IP) Local logbook events."""

from __future__ import annotations

from collections.abc import Callable
from typing import cast

from hahomematic.const import HmEventType
from hahomematic.entity import ClickEvent

from homeassistant.components.logbook.const import (
    LOGBOOK_ENTRY_MESSAGE,
    LOGBOOK_ENTRY_NAME,
)
from homeassistant.const import ATTR_DEVICE_ID, CONF_ADDRESS, CONF_TYPE
from homeassistant.core import Event, HomeAssistant, callback

from .const import CONF_SUBTYPE, DOMAIN as HMIP_DOMAIN
from .control_unit import get_device


@callback
def async_describe_events(
    hass: HomeAssistant,
    async_describe_event: Callable[[str, str, Callable[[Event], dict[str, str]]], None],
) -> None:
    """Describe logbook events."""

    @callback
    def async_describe_homematic_keypress_event(event: Event) -> dict[str, str]:
        """Describe Homematic(IP) Local logbook event."""
        event_data: dict = event.data

        if hm_device := get_device(hass=hass, device_id=event.data[ATTR_DEVICE_ID]):
            channel_address = f"{event_data[CONF_ADDRESS]}:{event_data[CONF_SUBTYPE]}"
            e_type = event_data[CONF_TYPE].upper()
            hm_event: ClickEvent = cast(
                ClickEvent, hm_device.action_events.get((channel_address, e_type))
            )
            if hm_event:
                event_name = hm_event.entity_name_data.full_name.replace(
                    hm_event.parameter.replace("_", " ").title(), ""
                ).strip()
                return {
                    LOGBOOK_ENTRY_NAME: event_name,
                    LOGBOOK_ENTRY_MESSAGE: f"fired event '{hm_event.parameter}'",
                }
        return {}

    async_describe_event(
        HMIP_DOMAIN,
        str(HmEventType.KEYPRESS.value),
        async_describe_homematic_keypress_event,
    )
