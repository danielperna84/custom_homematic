"""lock for Homematic(IP) Local."""

from __future__ import annotations

import logging
from typing import Any

from hahomematic.const import HmPlatform
from hahomematic.platforms.custom import BaseLock, LockState

from homeassistant.components.lock import LockEntity, LockEntityFeature
from homeassistant.const import STATE_UNAVAILABLE, STATE_UNKNOWN
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import HomematicConfigEntry
from .control_unit import ControlUnit, signal_new_hm_entity
from .generic_entity import HaHomematicGenericRestoreEntity

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: HomematicConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Homematic(IP) Local lock platform."""
    control_unit: ControlUnit = entry.runtime_data

    @callback
    def async_add_lock(hm_entities: tuple[BaseLock, ...]) -> None:
        """Add lock from Homematic(IP) Local."""
        _LOGGER.debug("ASYNC_ADD_LOCK: Adding %i entities", len(hm_entities))

        if entities := [
            HaHomematicLock(
                control_unit=control_unit,
                hm_entity=hm_entity,
            )
            for hm_entity in hm_entities
        ]:
            async_add_entities(entities)

    entry.async_on_unload(
        func=async_dispatcher_connect(
            hass=hass,
            signal=signal_new_hm_entity(entry_id=entry.entry_id, platform=HmPlatform.LOCK),
            target=async_add_lock,
        )
    )

    async_add_lock(hm_entities=control_unit.get_new_entities(entity_type=BaseLock))


class HaHomematicLock(HaHomematicGenericRestoreEntity[BaseLock], LockEntity):
    """Representation of the HomematicIP lock entity."""

    def __init__(
        self,
        control_unit: ControlUnit,
        hm_entity: BaseLock,
    ) -> None:
        """Initialize the lock entity."""
        super().__init__(control_unit=control_unit, hm_entity=hm_entity)
        if hm_entity.supports_open:
            self._attr_supported_features = LockEntityFeature.OPEN

    @property
    def is_locked(self) -> bool | None:
        """Return true if lock is on."""
        if self._hm_entity.is_valid:
            return self._hm_entity.is_locked
        if (
            self.is_restored
            and self._restored_state
            and (restored_state := self._restored_state.state)
            not in (
                STATE_UNKNOWN,
                STATE_UNAVAILABLE,
            )
        ):
            return restored_state == LockState.LOCKED
        return None

    @property
    def is_locking(self) -> bool | None:
        """Return true if the lock is locking."""
        return self._hm_entity.is_locking

    @property
    def is_unlocking(self) -> bool | None:
        """Return true if the lock is unlocking."""
        return self._hm_entity.is_unlocking

    @property
    def is_jammed(self) -> bool:
        """Return true if lock is jammed."""
        return self._hm_entity.is_jammed is True

    async def async_lock(self, **kwargs: Any) -> None:
        """Lock the lock."""
        await self._hm_entity.lock()

    async def async_unlock(self, **kwargs: Any) -> None:
        """Unlock the lock."""
        await self._hm_entity.unlock()

    async def async_open(self, **kwargs: Any) -> None:
        """Open the lock."""
        await self._hm_entity.open()
