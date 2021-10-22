"""binary_sensor for hahm."""
import logging

from hahomematic.const import HA_PLATFORM_INPUT_SELECT
from homeassistant.components.input_select import InputSelect
from homeassistant.core import callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect

from .const import DOMAIN
from .controlunit import ControlUnit
from .generic_entity import HaHomematicGenericEntity

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass, entry, async_add_entities):
    """Set up the hahm input_select platform."""
    cu: ControlUnit = hass.data[DOMAIN][entry.entry_id]

    @callback
    def async_add_input_select(args):
        """Add input_select from HAHM."""
        entities = []

        # for hm_entity in args[0]:
        #    entities.append(HaHomematicInput_Select(cu, hm_entity))

        if entities:
            async_add_entities(entities)

    entry.async_on_unload(
        async_dispatcher_connect(
            hass,
            cu.async_signal_new_hm_entity(HA_PLATFORM_INPUT_SELECT),
            async_add_input_select,
        )
    )


class HaHomematicInput_Select(HaHomematicGenericEntity, InputSelect):
    """Representation of the HomematicIP input_select entity."""
