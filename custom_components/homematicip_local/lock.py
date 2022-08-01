"""lock for Homematic(IP) Local."""
from __future__ import annotations

import logging
from typing import Any

from hahomematic.const import HmPlatform
from hahomematic.devices.lock import LOCK_STATE_LOCKED, BaseLock

from homeassistant.components.lock import LockEntity, LockEntityFeature
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import STATE_UNAVAILABLE, STATE_UNKNOWN
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .control_unit import ControlUnit
from .generic_entity import HaHomematicGenericRestoreEntity

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Homematic(IP) Local lock platform."""
    control_unit: ControlUnit = hass.data[DOMAIN][config_entry.entry_id]

    @callback
    def async_add_lock(args: Any) -> None:
        """Add lock from Homematic(IP) Local."""
        entities: list[HaHomematicGenericRestoreEntity] = []

        for hm_entity in args:
            entities.append(HaHomematicLock(control_unit, hm_entity))

        if entities:
            async_add_entities(entities)

    config_entry.async_on_unload(
        async_dispatcher_connect(
            hass,
            control_unit.async_signal_new_hm_entity(
                config_entry.entry_id, HmPlatform.LOCK
            ),
            async_add_lock,
        )
    )

    async_add_lock(
        control_unit.async_get_new_hm_entities_by_platform(platform=HmPlatform.LOCK)
    )


class HaHomematicLock(HaHomematicGenericRestoreEntity[BaseLock], LockEntity):
    """Representation of the HomematicIP lock entity."""

    _attr_supported_features = LockEntityFeature.OPEN

    @property
    def is_locked(self) -> bool | None:
        """Return true if lock is on."""
        if self._hm_entity.is_valid:
            return self._hm_entity.is_locked
        if self.is_restored:
            if (restored_state := self._restored_state.state) not in (  # type: ignore[union-attr]
                STATE_UNKNOWN,
                STATE_UNAVAILABLE,
            ):
                return restored_state == LOCK_STATE_LOCKED
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
