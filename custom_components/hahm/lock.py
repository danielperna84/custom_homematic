"""binary_sensor for hahm."""
import logging

from hahomematic.const import HA_PLATFORM_LOCK
from homeassistant.components.lock import LockEntity

from .const import DOMAIN, HAHM_SERVER
from .controlunit import ControlUnit
from .generic_entity import HaHomematicGenericEntity

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass, entry, async_add_entities) -> None:
    """Set up the hahm lock platform."""
    cu: ControlUnit = hass.data[DOMAIN][entry.entry_id]
    entities: list[HaHomematicGenericEntity] = []
    # for hm_entity in in cu.get_new_hm_entities(HA_PLATFORM_LOCK):
    #    entities.append(HaHomematicLock(cu, hm_entity))
    async_add_entities(entities)


class HaHomematicLock(HaHomematicGenericEntity, LockEntity):
    """Representation of the HomematicIP lock entity."""
