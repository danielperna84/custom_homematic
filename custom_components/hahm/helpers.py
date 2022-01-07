"""Helper."""
from __future__ import annotations

from typing import TypeVar, Union

from hahomematic.const import IDENTIFIERS_SEPARATOR
from hahomematic.entity import BaseParameterEntity, CustomEntity, GenericEntity
from hahomematic.hub import BaseHubEntity

# Union for entity types used as base class for entities
HmBaseEntity = Union[BaseHubEntity, BaseParameterEntity, CustomEntity, GenericEntity]
# Entities that support callbacks from backend
HmCallbackEntity = (CustomEntity, GenericEntity)
# Generic base type used for entities in Homematic(IP) Local
HmGenericEntity = TypeVar("HmGenericEntity", bound=HmBaseEntity)


def get_device_address_from_identifiers(
    identifiers: set[tuple[str, str]]
) -> str | None:
    """Get the device_address from device_info.identifiers."""
    for identifier in identifiers:
        if IDENTIFIERS_SEPARATOR in identifier[1]:
            return identifier[1].split(IDENTIFIERS_SEPARATOR)[0]
    return None


def get_device_address_at_interface_from_identifiers(
    identifiers: set[tuple[str, str]]
) -> list[str] | None:
    """Get the device_address from device_info.identifiers."""
    for identifier in identifiers:
        if IDENTIFIERS_SEPARATOR in identifier[1]:
            return identifier[1].split(IDENTIFIERS_SEPARATOR)
    return None
