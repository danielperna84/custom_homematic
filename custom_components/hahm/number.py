"""binary_sensor for hahm."""
import logging

from hahomematic.const import HA_PLATFORM_NUMBER
from homeassistant.components.number import NumberEntity
from homeassistant.core import callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect

from .const import DOMAIN
from .controlunit import ControlUnit
from .generic_entity import HaHomematicGenericEntity

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass, entry, async_add_entities):
    """Set up the hahm number platform."""
    cu: ControlUnit = hass.data[DOMAIN][entry.entry_id]

    @callback
    def async_add_number(args):
        """Add number from HAHM."""
        entities = []

        # for hm_entity in args[0]:
        #    entities.append(HaHomematicNumber(cu, hm_entity))

        if entities:
            async_add_entities(entities)

    entry.async_on_unload(
        async_dispatcher_connect(
            hass,
            cu.async_signal_new_hm_entity(HA_PLATFORM_NUMBER),
            async_add_number,
        )
    )

    async_add_number([cu.server.get_hm_entities_by_platform(HA_PLATFORM_NUMBER)])


class HaHomematicNumber(HaHomematicGenericEntity, NumberEntity):
    """Representation of the HomematicIP number entity."""
