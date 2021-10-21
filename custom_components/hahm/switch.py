"""binary_switch for hahm."""
import logging

from hahomematic.const import HA_PLATFORM_SWITCH
from homeassistant.components.switch import SwitchEntity

from .const import DOMAIN
from .control_unit import Control_Unit
from .generic_entity import HaHomematicGenericEntity

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass, entry, async_add_entities) -> None:
    """Set up the hahm switch platform."""
    cu: Control_Unit = hass.data[DOMAIN][entry.entry_id]
    entities: list[HaHomematicGenericEntity] = []
    # for hm_entity in cu.get_new_hm_entities(HA_PLATFORM_SWITCH):
    #    entities.append(HaHomematicSwitch(cu, hm_entity))
    async_add_entities(entities)


class HaHomematicSwitch(HaHomematicGenericEntity, SwitchEntity):
    """Representation of the HomematicIP switch entity."""
