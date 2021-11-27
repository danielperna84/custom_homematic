"""Provides device triggers for Home Assistant Homematic(IP)."""
from __future__ import annotations

from typing import Any

import voluptuous as vol
from hahomematic.const import CLICK_EVENTS, HM_VIRTUAL_REMOTES
from hahomematic.entity import ImpulseEvent

from homeassistant.components.automation import (
    AutomationActionType,
    AutomationTriggerInfo,
)
from homeassistant.components.device_automation import DEVICE_TRIGGER_BASE_SCHEMA
from homeassistant.components.homeassistant.triggers import event as event_trigger
from homeassistant.const import (
    CONF_ADDRESS,
    CONF_DEVICE_ID,
    CONF_DOMAIN,
    CONF_PLATFORM,
    CONF_TYPE,
)
from homeassistant.core import CALLBACK_TYPE, HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.typing import ConfigType

from . import DOMAIN
from .controlunit import ControlUnit

CONF_INTERFACE_ID = "interface_id"
CONF_EVENT_TYPE = "event_type"

TRIGGER_TYPES = CLICK_EVENTS

TRIGGER_SCHEMA = DEVICE_TRIGGER_BASE_SCHEMA.extend(
    {
        vol.Required(CONF_INTERFACE_ID): str,
        vol.Required(CONF_ADDRESS): str,
        vol.Required(CONF_EVENT_TYPE): str,
        vol.Required(CONF_TYPE): str,
    }
)


async def async_get_triggers(
    hass: HomeAssistant, device_id: str
) -> list[dict[str, Any]]:
    """List device triggers for Home Assistant Homematic(IP) devices."""
    device_registry = dr.async_get(hass)
    device = device_registry.async_get(device_id)
    address = list(device.identifiers)[0][1]
    if address.endswith(tuple(HM_VIRTUAL_REMOTES)):
        address = address.split("_")[1]
    triggers = []
    for entry_id in device.config_entries:
        control_unit: ControlUnit = hass.data[DOMAIN][entry_id]
        hm_device = control_unit.central.hm_devices.get(address)
        if hm_device:
            for action_event in hm_device.action_events.values():
                if isinstance(action_event, ImpulseEvent):
                    continue

                trigger = {
                    CONF_PLATFORM: "device",
                    CONF_DOMAIN: DOMAIN,
                    CONF_DEVICE_ID: device_id,
                    CONF_EVENT_TYPE: action_event.event_type,
                }
                trigger.update(action_event.get_event_data())
                triggers.append(trigger)

    return triggers


async def async_attach_trigger(
    hass: HomeAssistant,
    config: ConfigType,
    action: AutomationActionType,
    automation_info: AutomationTriggerInfo,
) -> CALLBACK_TYPE:
    """Listen for state changes based on configuration."""
    _event_data = {
        CONF_INTERFACE_ID: config[CONF_INTERFACE_ID],
        CONF_ADDRESS: config[CONF_ADDRESS],
        CONF_TYPE: config[CONF_TYPE],
    }

    event_config = {
        event_trigger.CONF_PLATFORM: "event",
        event_trigger.CONF_EVENT_TYPE: config[CONF_EVENT_TYPE],
        event_trigger.CONF_EVENT_DATA: _event_data,
    }

    event_config = event_trigger.TRIGGER_SCHEMA(event_config)
    return await event_trigger.async_attach_trigger(
        hass, event_config, action, automation_info, platform_type="device"
    )
