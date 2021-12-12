"""Helper."""
from __future__ import annotations

from typing import TypeVar, Union

from hahomematic.entity import BaseParameterEntity, CustomEntity, GenericEntity
from hahomematic.hub import BaseHubEntity

# Union for entity types used as base class for entities
HmBaseEntity = Union[BaseHubEntity, BaseParameterEntity, CustomEntity, GenericEntity]
# Entities that support callbacks from backend
HmCallbackEntity = (CustomEntity, GenericEntity)
# Generic base type usedcfor entities in hahm
HmGenericEntity = TypeVar("HmGenericEntity", bound=HmBaseEntity)
