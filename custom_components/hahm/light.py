"""binary_sensor for hahm."""
import logging

from hahomematic.const import HA_PLATFORM_LIGHT
from homeassistant.components.light import LightEntity

from .const import DOMAIN
from .control_unit import Control_Unit
from .generic_entity import HaHomematicGenericEntity

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass, entry, async_add_entities) -> None:
    """Set up the hahm light platform."""
    cu: Control_Unit = hass.data[DOMAIN][entry.entry_id]
    entities: list[HaHomematicGenericEntity] = []
    # for hm_entity in cu.get_new_hm_entities(HA_PLATFORM_LIGHT):
    #    entities.append(HaHomematicLight(cu, hm_entity))
    async_add_entities(entities)


class HaHomematicLight(HaHomematicGenericEntity, LightEntity):
    """Representation of the HomematicIP light entity."""
