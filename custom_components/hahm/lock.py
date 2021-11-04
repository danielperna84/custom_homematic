"""binary_sensor for HAHM."""
import logging
from typing import Any

from hahomematic.const import HA_PLATFORM_LOCK

from homeassistant.components.lock import LockEntity
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

    def lock(self, **kwargs: Any) -> None:
        pass

    def unlock(self, **kwargs: Any) -> None:
        pass

    def open(self, **kwargs: Any) -> None:
        pass
