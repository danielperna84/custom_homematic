"""binary_sensor for HAHM."""
import logging
from typing import Any

from hahomematic.const import HA_PLATFORM_LOCK

from homeassistant.components.lock import SUPPORT_OPEN, LockEntity
from homeassistant.core import callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect

from .const import DOMAIN
from .controlunit import ControlUnit
from .generic_entity import HaHomematicGenericEntity

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass, entry, async_add_entities):
    """Set up the HAHM lock platform."""
    cu: ControlUnit = hass.data[DOMAIN][entry.entry_id]

    @callback
    def async_add_lock(args):
        """Add lock from HAHM."""
        entities = []

        for hm_entity in args[0]:
            entities.append(HaHomematicLock(cu, hm_entity))

        if entities:
            async_add_entities(entities)

    entry.async_on_unload(
        async_dispatcher_connect(
            hass,
            cu.async_signal_new_hm_entity(HA_PLATFORM_LOCK),
            async_add_lock,
        )
    )

    async_add_lock([cu.get_hm_entities_by_platform(HA_PLATFORM_LOCK)])


class HaHomematicLock(HaHomematicGenericEntity, LockEntity):
    """Representation of the HomematicIP lock entity."""

    @property
    def is_locked(self):
        """Return true if lock is on."""
        return self._hm_device.is_locked

    @property
    def supported_features(self) -> int:
        """Flag supported features."""
        return SUPPORT_OPEN

    async def async_lock(self, **kwargs):
        """Lock the lock."""
        await self._hm_device.async_lock()

    async def async_unlock(self, **kwargs):
        """Unlock the lock."""
        await self._hm_device.async_unlock()

    async def async_open(self, **kwargs: Any) -> None:
        """Open the lock."""
        await self._hm_device.async_open()
