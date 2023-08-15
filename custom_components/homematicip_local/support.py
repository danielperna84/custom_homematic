"""Helper."""
from __future__ import annotations

from abc import ABC
from collections.abc import Callable
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
import logging
from typing import Any, TypeAlias, TypeVar, cast

from hahomematic.const import ATTR_CHANNEL_NO, ATTR_PARAMETER, ATTR_VALUE, IDENTIFIER_SEPARATOR
from hahomematic.platforms.custom.entity import CustomEntity
from hahomematic.platforms.entity import HM_EVENT_DATA_SCHEMA, CallbackEntity
from hahomematic.platforms.generic.entity import GenericEntity, WrapperEntity
from hahomematic.platforms.hub.entity import GenericHubEntity
from homeassistant.components.binary_sensor import BinarySensorEntityDescription
from homeassistant.components.button import ButtonEntityDescription
from homeassistant.components.number import NumberEntityDescription
from homeassistant.components.sensor import SensorEntityDescription
from homeassistant.const import ATTR_DEVICE_ID, CONF_TYPE
from homeassistant.helpers.typing import StateType
import voluptuous as vol

from .const import (
    ATTR_NAME,
    CONF_SUBTYPE,
    EVENT_DATA_ERROR,
    EVENT_DATA_ERROR_VALUE,
    EVENT_DATA_IDENTIFIER,
    EVENT_DATA_MESSAGE,
    EVENT_DATA_TITLE,
    EVENT_DATA_UNAVAILABLE,
    HmNameSource,
)

# Union for entity types used as base class for entities
HmBaseEntity: TypeAlias = CustomEntity | GenericEntity | WrapperEntity
# Generic base type used for entities in Homematic(IP) Local
HmGenericEntity = TypeVar("HmGenericEntity", bound=HmBaseEntity)
# Generic base type used for sysvar entities in Homematic(IP) Local
HmGenericSysvarEntity = TypeVar("HmGenericSysvarEntity", bound=GenericHubEntity)
T = TypeVar("T", bound=CallbackEntity)

BASE_EVENT_DATA_SCHEMA = HM_EVENT_DATA_SCHEMA.extend(
    {
        vol.Required(ATTR_DEVICE_ID): str,
        vol.Required(ATTR_NAME): str,
    }
)
HM_CLICK_EVENT_SCHEMA = BASE_EVENT_DATA_SCHEMA.extend(
    {
        vol.Required(CONF_TYPE): str,
        vol.Required(CONF_SUBTYPE): int,
        vol.Remove(ATTR_CHANNEL_NO): int,
        vol.Remove(ATTR_PARAMETER): str,
        vol.Remove(ATTR_VALUE): vol.Any(bool, int),
    },
    extra=vol.ALLOW_EXTRA,
)
HM_DEVICE_AVAILABILITY_EVENT_SCHEMA = BASE_EVENT_DATA_SCHEMA.extend(
    {
        vol.Required(EVENT_DATA_IDENTIFIER): str,
        vol.Required(EVENT_DATA_TITLE): str,
        vol.Required(EVENT_DATA_MESSAGE): str,
        vol.Required(EVENT_DATA_UNAVAILABLE): bool,
    },
    extra=vol.ALLOW_EXTRA,
)
HM_DEVICE_ERROR_EVENT_SCHEMA = BASE_EVENT_DATA_SCHEMA.extend(
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


def get_device_address_at_interface_from_identifiers(
    identifiers: set[tuple[str, str]]
) -> tuple[str, str] | None:
    """Get the device_address from device_info.identifiers."""
    for identifier in identifiers:
        if IDENTIFIER_SEPARATOR in identifier[1]:
            return cast(tuple[str, str], identifier[1].split(IDENTIFIER_SEPARATOR))
    return None


@dataclass
class HmEntityDescription(ABC):
    """Base class describing Homematic(IP) Local entities."""

    name_source: HmNameSource = HmNameSource.PARAMETER


@dataclass
class HmBinarySensorEntityDescription(
    HmEntityDescription, BinarySensorEntityDescription
):
    """Class describing Homematic(IP) Local binary sensor entities."""


@dataclass
class HmButtonEntityDescription(HmEntityDescription, ButtonEntityDescription):
    """Class describing Homematic(IP) Local button entities."""


@dataclass
class HmNumberEntityDescription(HmEntityDescription, NumberEntityDescription):
    """Class describing Homematic(IP) Local number entities."""

    multiplier: int | None = None


@dataclass
class HmSensorEntityDescription(HmEntityDescription, SensorEntityDescription):
    """Class describing Homematic(IP) Local sensor entities."""

    multiplier: int | None = None
    icon_fn: Callable[[StateType | date | datetime | Decimal], str | None] | None = None


def get_hm_entity(hm_entity: T) -> T:
    """Return the homematic entity."""
    return hm_entity
