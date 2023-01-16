"""Helper."""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
import logging
from typing import Any, TypeVar, Union

from hahomematic.const import ATTR_CHANNEL_NO, ATTR_PARAMETER, ATTR_VALUE
from hahomematic.entity import (
    HM_EVENT_SCHEMA,
    CustomEntity,
    GenericEntity,
    GenericHubEntity,
    WrapperEntity,
)
import voluptuous as vol

from homeassistant.components.number import NumberEntityDescription
from homeassistant.components.sensor import SensorEntityDescription
from homeassistant.const import ATTR_DEVICE_ID, CONF_TYPE
from homeassistant.helpers.typing import StateType

from .const import (
    ATTR_NAME,
    CONF_SUBTYPE,
    EVENT_DATA_ERROR,
    EVENT_DATA_ERROR_VALUE,
    EVENT_DATA_IDENTIFIER,
    EVENT_DATA_MESSAGE,
    EVENT_DATA_TITLE,
    EVENT_DATA_UNAVAILABLE,
    IDENTIFIER_SEPARATOR,
)

# Union for entity types used as base class for entities
HmBaseEntity = Union[CustomEntity, GenericEntity, WrapperEntity]
# Entities that support callbacks from backend
HmCallbackEntity = (CustomEntity, GenericEntity, WrapperEntity)
# Generic base type used for entities in Homematic(IP) Local
HmGenericEntity = TypeVar("HmGenericEntity", bound=HmBaseEntity)
# Generic base type used for sysvar entities in Homematic(IP) Local
HmGenericSysvarEntity = TypeVar("HmGenericSysvarEntity", bound=GenericHubEntity)


BASE_EVENT_SCHEMA = HM_EVENT_SCHEMA.extend(
    {
        vol.Required(ATTR_DEVICE_ID): str,
        vol.Required(ATTR_NAME): str,
    }
)
HM_CLICK_EVENT_SCHEMA = BASE_EVENT_SCHEMA.extend(
    {
        vol.Required(CONF_TYPE): str,
        vol.Required(CONF_SUBTYPE): int,
        vol.Remove(ATTR_CHANNEL_NO): int,
        vol.Remove(ATTR_PARAMETER): str,
        vol.Remove(ATTR_VALUE): vol.Any(bool, int),
    },
    extra=vol.ALLOW_EXTRA,
)
HM_DEVICE_AVAILABILITY_EVENT_SCHEMA = BASE_EVENT_SCHEMA.extend(
    {
        vol.Required(EVENT_DATA_IDENTIFIER): str,
        vol.Required(EVENT_DATA_TITLE): str,
        vol.Required(EVENT_DATA_MESSAGE): str,
        vol.Required(EVENT_DATA_UNAVAILABLE): bool,
    },
    extra=vol.ALLOW_EXTRA,
)
HM_DEVICE_ERROR_EVENT_SCHEMA = BASE_EVENT_SCHEMA.extend(
    {
        vol.Required(EVENT_DATA_IDENTIFIER): str,
        vol.Required(EVENT_DATA_TITLE): str,
        vol.Required(EVENT_DATA_MESSAGE): str,
        vol.Required(EVENT_DATA_ERROR_VALUE): vol.Any(bool, int),
        vol.Required(EVENT_DATA_ERROR): bool,
    },
    extra=vol.ALLOW_EXTRA,
)

_LOGGER = logging.getLogger(__name__)


def cleanup_click_event_data(event_data: dict[str, Any]) -> dict[str, Any]:
    """Cleanup the click_event."""
    event_data.update(
        {
            CONF_TYPE: event_data[ATTR_PARAMETER].lower(),
            CONF_SUBTYPE: event_data[ATTR_CHANNEL_NO],
        }
    )
    del event_data[ATTR_PARAMETER]
    del event_data[ATTR_CHANNEL_NO]
    return event_data


def is_valid_event(event_data: dict[str, Any], schema: vol.Schema) -> bool:
    """Validate evenc_data against a given schema."""
    try:
        schema(event_data)
        return True
    except vol.Invalid as err:
        _LOGGER.debug("The EVENT could not be validated. %s, %s", err.path, err.msg)
    return False


def get_device_address_from_identifiers(
    identifiers: set[tuple[str, str]]
) -> str | None:
    """Get the device_address from device_info.identifiers."""
    for identifier in identifiers:
        if IDENTIFIER_SEPARATOR in identifier[1]:
            return identifier[1].split(IDENTIFIER_SEPARATOR)[0]
    return None


def get_device_address_at_interface_from_identifiers(
    identifiers: set[tuple[str, str]]
) -> list[str] | None:
    """Get the device_address from device_info.identifiers."""
    for identifier in identifiers:
        if IDENTIFIER_SEPARATOR in identifier[1]:
            return identifier[1].split(IDENTIFIER_SEPARATOR)
    return None


@dataclass
class HmNumberEntityDescription(NumberEntityDescription):
    """Class describing Homematic(IP) Local number entities."""

    multiplier: int | None = None


@dataclass
class HmSensorEntityDescription(SensorEntityDescription):
    """Class describing Homematic(IP) Local sensor entities."""

    multiplier: int | None = None
    icon_fn: Callable[[StateType | date | datetime | Decimal], str | None] | None = None
