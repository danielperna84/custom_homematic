"""Helper."""
from __future__ import annotations

from dataclasses import dataclass
from typing import TypeVar, Union

from hahomematic.entity import CustomEntity, GenericEntity, GenericSystemVariable
from hahomematic.hub import HmHub

from homeassistant.components.number import NumberEntityDescription
from homeassistant.components.sensor import SensorEntityDescription
from .const import IDENTIFIER_SEPARATOR

# Union for entity types used as base class for entities
HmBaseEntity = Union[CustomEntity, GenericEntity]
# Union for entity types used as base class for sysvar entities
HmBaseSysvarEntity = Union[HmHub, GenericSystemVariable]
# Entities that support callbacks from backend
HmCallbackEntity = (CustomEntity, GenericEntity)
# Generic base type used for entities in Homematic(IP) Local
HmGenericEntity = TypeVar("HmGenericEntity", bound=HmBaseEntity)
# Generic base type used for sysvar entities in Homematic(IP) Local
HmGenericSysvarEntity = TypeVar("HmGenericSysvarEntity", bound=HmBaseSysvarEntity)


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
