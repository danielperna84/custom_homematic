"""binary_sensor for hahm."""
import logging

from hahomematic.const import HA_PLATFORM_INPUT_TEXT
from homeassistant.components.input_text import InputText

from .const import DOMAIN
from .controlunit import ControlUnit
from .generic_entity import HaHomematicGenericEntity

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass, entry, async_add_entities) -> None:
    """Set up the hahm input_text platform."""
    cu: ControlUnit = hass.data[DOMAIN][entry.entry_id]
    entities: list[HaHomematicGenericEntity] = []
    # for hm_entity in cu.get_new_hm_entities(HA_PLATFORM_INPUT_TEXT):
    #    entities.append(HaHomematicInput_Text(cu, hm_entity))
    async_add_entities(entities)


class HaHomematicInput_Text(HaHomematicGenericEntity, InputText):
    """Representation of the HomematicIP input_text entity."""
