"""Provides device actions for Homematic(IP) Local."""
from __future__ import annotations

from typing import Any

from hahomematic.const import EVENT_PRESS_LONG, EVENT_PRESS_SHORT
from hahomematic.internal.action import HmAction
import voluptuous as vol

from homeassistant.const import CONF_DEVICE_ID, CONF_DOMAIN, CONF_TYPE
from homeassistant.core import Context, HomeAssistant
from homeassistant.helpers import device_registry as dr
import homeassistant.helpers.config_validation as cv

from . import DOMAIN
from .const import CONF_SUBTYPE
from .control_unit import ControlUnit
from .helpers import get_device_address_at_interface_from_identifiers

ACTION_PARAMS = {EVENT_PRESS_LONG, EVENT_PRESS_SHORT}
ACTION_TYPES = {param.lower() for param in ACTION_PARAMS}

ACTION_SCHEMA = cv.DEVICE_ACTION_BASE_SCHEMA.extend(
    {
        vol.Required(CONF_TYPE): vol.In(ACTION_TYPES),
        vol.Required(CONF_SUBTYPE): int,
    }
)


async def async_get_actions(
    hass: HomeAssistant, device_id: str
) -> list[dict[str, Any]]:
    """List device actions for Homematic(IP) Local devices."""

    device_registry = dr.async_get(hass)
    if (device := device_registry.async_get(device_id)) is None:
        return []
    if (
        data := get_device_address_at_interface_from_identifiers(
            identifiers=device.identifiers
        )
    ) is None:
        return []

    device_address = data[0]
    interface_id = data[1]

    actions = []
    for entry_id in device.config_entries:
        control_unit: ControlUnit = hass.data[DOMAIN][entry_id]
        if control_unit.central.clients.get(interface_id) is None:
            continue
        if hm_device := control_unit.central.hm_devices.get(device_address):
            for entity in hm_device.entities.values():
                if not isinstance(entity, HmAction):
                    continue
                if entity.parameter not in ACTION_PARAMS:
                    continue

                action = {
                    CONF_DOMAIN: DOMAIN,
                    CONF_DEVICE_ID: device_id,
                    CONF_TYPE: entity.parameter.lower(),
                    CONF_SUBTYPE: entity.channel_no,
                }
                actions.append(action)

    return actions


async def async_call_action_from_config(
    hass: HomeAssistant, config: dict, variables: dict, context: Context | None
) -> None:
    """Execute a device action."""
    device_id: str = config[CONF_DEVICE_ID]
    action_type: str = config[CONF_TYPE]
    action_subtype: int = config[CONF_SUBTYPE]

    device_registry = dr.async_get(hass)
    if (device := device_registry.async_get(device_id)) is None:
        return None
    if (
        data := get_device_address_at_interface_from_identifiers(
            identifiers=device.identifiers
        )
    ) is None:
        return None

    device_address = data[0]
    interface_id = data[1]

    for entry_id in device.config_entries:
        control_unit: ControlUnit = hass.data[DOMAIN][entry_id]
        if control_unit.central.clients.get(interface_id) is None:
            continue
        if hm_device := control_unit.central.hm_devices.get(device_address):
            for entity in hm_device.entities.values():
                if not isinstance(entity, HmAction):
                    continue
                if (
                    entity.parameter == action_type.upper()
                    and entity.channel_no == action_subtype
                ):
                    await entity.send_value(True)
