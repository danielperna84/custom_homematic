"""binary_sensor for hahm."""
import logging

from hahomematic.const import HA_PLATFORM_NUMBER
from homeassistant.components.number import NumberEntity

from .const import DOMAIN
from .control_unit import Control_Unit
from .generic_entity import HaHomematicGenericEntity

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass, entry, async_add_entities) -> None:
    """Set up the hahm number platform."""
    cu: Control_Unit = hass.data[DOMAIN][entry.entry_id]
    entities: list[HaHomematicGenericEntity] = []
    # for hm_entity in in cu.get_new_hm_entities(HA_PLATFORM_NUMBER):
    #    entities.append(HaHomematicNumber(cu, hm_entity))
    async_add_entities(entities)


class HaHomematicNumber(HaHomematicGenericEntity, NumberEntity):
    """Representation of the HomematicIP number entity."""
