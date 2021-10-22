"""binary_sensor for hahm."""
import logging

from hahomematic.const import HA_PLATFORM_CLIMATE
from homeassistant.components.climate import ClimateEntity
from homeassistant.core import callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect

from .const import DOMAIN
from .controlunit import ControlUnit
from .generic_entity import HaHomematicGenericEntity

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass, entry, async_add_entities):
    """Set up the hahm climate platform."""
    cu: ControlUnit = hass.data[DOMAIN][entry.entry_id]

    @callback
    def async_add_climate(args):
        """Add climate from HAHM."""
        entities = []

        # for hm_entity in args[0]:
        #    entities.append(HaHomematicClimate(cu, hm_entity))

        if entities:
            async_add_entities(entities)

    entry.async_on_unload(
        async_dispatcher_connect(
            hass,
            cu.async_signal_new_hm_entity(HA_PLATFORM_CLIMATE),
            async_add_climate,
        )
    )


class HaHomematicClimate(HaHomematicGenericEntity, ClimateEntity):
    """Representation of the HomematicIP climate entity."""
