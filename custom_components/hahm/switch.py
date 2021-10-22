"""binary_switch for hahm."""
import logging

from hahomematic.const import HA_PLATFORM_SWITCH
from homeassistant.components.switch import SwitchEntity
from homeassistant.core import callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect

from .const import DOMAIN
from .controlunit import ControlUnit
from .generic_entity import HaHomematicGenericEntity

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass, entry, async_add_entities):
    """Set up the hahm switch platform."""
    cu: ControlUnit = hass.data[DOMAIN][entry.entry_id]

    @callback
    def async_add_switch(args):
        """Add switch from HAHM."""
        entities = []

        # for hm_entity in args[0]:
        #    entities.append(HaHomematicSwitch(cu, hm_entity))

        if entities:
            async_add_entities(entities)

    entry.async_on_unload(
        async_dispatcher_connect(
            hass,
            cu.async_signal_new_hm_entity(HA_PLATFORM_SWITCH),
            async_add_switch,
        )
    )


class HaHomematicSwitch(HaHomematicGenericEntity, SwitchEntity):
    """Representation of the HomematicIP switch entity."""
