"""Helper."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
import logging
from typing import Any, TypeAlias, TypeVar, cast

from hahomematic.const import EVENT_CHANNEL_NO, EVENT_PARAMETER, EVENT_VALUE, IDENTIFIER_SEPARATOR
from hahomematic.platforms.custom.entity import CustomEntity
from hahomematic.platforms.entity import EVENT_DATA_SCHEMA, CallbackEntity
from hahomematic.platforms.generic.entity import GenericEntity
from hahomematic.platforms.hub.entity import GenericHubEntity
import voluptuous as vol

from homeassistant.components.binary_sensor import BinarySensorEntityDescription
from homeassistant.components.button import ButtonEntityDescription
from homeassistant.components.number import NumberEntityDescription
from homeassistant.components.select import SelectEntityDescription
from homeassistant.components.sensor import SensorEntityDescription
from homeassistant.const import CONF_TYPE
from homeassistant.exceptions import HomeAssistantError

from .const import (
    CONF_SUBTYPE,
    EVENT_DEVICE_ID,
    EVENT_ERROR,
    EVENT_ERROR_VALUE,
    EVENT_IDENTIFIER,
    EVENT_MESSAGE,
    EVENT_NAME,
    EVENT_TITLE,
    EVENT_UNAVAILABLE,
    HmNameSource,
)

# Union for entity types used as base class for entities
HmBaseEntity: TypeAlias = CustomEntity | GenericEntity
# Generic base type used for entities in Homematic(IP) Local
HmGenericEntity = TypeVar("HmGenericEntity", bound=HmBaseEntity)
# Generic base type used for sysvar entities in Homematic(IP) Local
HmGenericSysvarEntity = TypeVar("HmGenericSysvarEntity", bound=GenericHubEntity)
T = TypeVar("T", bound=CallbackEntity)

BASE_EVENT_DATA_SCHEMA = EVENT_DATA_SCHEMA.extend(
    {
        vol.Required(EVENT_DEVICE_ID): str,
        vol.Required(EVENT_NAME): str,
    }
)
CLICK_EVENT_SCHEMA = BASE_EVENT_DATA_SCHEMA.extend(
    {
        vol.Required(CONF_TYPE): str,
        vol.Required(CONF_SUBTYPE): int,
        vol.Remove(EVENT_CHANNEL_NO): int,
        vol.Remove(EVENT_PARAMETER): str,
        vol.Remove(EVENT_VALUE): vol.Any(bool, int),
    },
    extra=vol.ALLOW_EXTRA,
)
DEVICE_AVAILABILITY_EVENT_SCHEMA = BASE_EVENT_DATA_SCHEMA.extend(
    {
        vol.Required(EVENT_IDENTIFIER): str,
        vol.Required(EVENT_TITLE): str,
        vol.Required(EVENT_MESSAGE): str,
        vol.Required(EVENT_UNAVAILABLE): bool,
    },
    extra=vol.ALLOW_EXTRA,
)
DEVICE_ERROR_EVENT_SCHEMA = BASE_EVENT_DATA_SCHEMA.extend(
    {
        vol.Required(EVENT_IDENTIFIER): str,
        vol.Required(EVENT_TITLE): str,
        vol.Required(EVENT_MESSAGE): str,
        vol.Required(EVENT_ERROR_VALUE): vol.Any(bool, int),
        vol.Required(EVENT_ERROR): bool,
    },
    extra=vol.ALLOW_EXTRA,
)

_LOGGER = logging.getLogger(__name__)


def cleanup_click_event_data(event_data: dict[str, Any]) -> dict[str, Any]:
    """Cleanup the click_event."""
    event_data.update(
        {
            CONF_TYPE: event_data[EVENT_PARAMETER].lower(),
            CONF_SUBTYPE: event_data[EVENT_CHANNEL_NO],
        }
    )
    del event_data[EVENT_PARAMETER]
    del event_data[EVENT_CHANNEL_NO]
    return event_data


def is_valid_event(event_data: Mapping[str, Any], schema: vol.Schema) -> bool:
    """Validate evenc_data against a given schema."""
    try:
        schema(event_data)
    except vol.Invalid as err:
        _LOGGER.debug("The EVENT could not be validated. %s, %s", err.path, err.msg)
        return False
    return True


def get_device_address_at_interface_from_identifiers(
    identifiers: set[tuple[str, str]],
) -> tuple[str, str] | None:
    """Get the device_address from device_info.identifiers."""
    for identifier in identifiers:
        if IDENTIFIER_SEPARATOR in identifier[1]:
            return cast(tuple[str, str], identifier[1].split(IDENTIFIER_SEPARATOR))
    return None


@dataclass(frozen=True, kw_only=True)
class HmEntityDescription:
    """Base class describing Homematic(IP) Local entities."""

    name_source: HmNameSource = HmNameSource.PARAMETER


@dataclass(frozen=True, kw_only=True)
class HmBinarySensorEntityDescription(HmEntityDescription, BinarySensorEntityDescription):
    """Class describing Homematic(IP) Local binary sensor entities."""


@dataclass(frozen=True, kw_only=True)
class HmButtonEntityDescription(HmEntityDescription, ButtonEntityDescription):
    """Class describing Homematic(IP) Local button entities."""


@dataclass(frozen=True, kw_only=True)
class HmNumberEntityDescription(HmEntityDescription, NumberEntityDescription):
    """Class describing Homematic(IP) Local number entities."""

    multiplier: int | None = None


@dataclass(frozen=True, kw_only=True)
class HmSelectEntityDescription(HmEntityDescription, SelectEntityDescription):
    """Class describing Homematic(IP) Local select entities."""


@dataclass(frozen=True, kw_only=True)
class HmSensorEntityDescription(HmEntityDescription, SensorEntityDescription):
    """Class describing Homematic(IP) Local sensor entities."""

    multiplier: int | None = None


def get_hm_entity(hm_entity: T) -> T:
    """Return the homematic entity. Makes it mockable."""
    return hm_entity


class InvalidConfig(HomeAssistantError):
    """Error to indicate there is invalid config."""
