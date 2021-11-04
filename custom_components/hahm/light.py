"""binary_sensor for HAHM."""
import logging
from typing import Any

from hahomematic.const import HA_PLATFORM_LIGHT

from homeassistant.components.light import LightEntity
from homeassistant.core import callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect

from .const import DOMAIN
from .controlunit import ControlUnit
from .generic_entity import HaHomematicGenericEntity

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass, entry, async_add_entities):
    """Set up the HAHM light platform."""
    cu: ControlUnit = hass.data[DOMAIN][entry.entry_id]

    @callback
    def async_add_light(args):
        """Add light from HAHM."""
        entities = []

        for hm_entity in args[0]:
            entities.append(HaHomematicLight(cu, hm_entity))

        if entities:
            async_add_entities(entities)

    entry.async_on_unload(
        async_dispatcher_connect(
            hass,
            cu.async_signal_new_hm_entity(HA_PLATFORM_LIGHT),
            async_add_light,
        )
    )

    async_add_light([cu.get_hm_entities_by_platform(HA_PLATFORM_LIGHT)])


class HaHomematicLight(HaHomematicGenericEntity, LightEntity):
    """Representation of the HomematicIP light entity."""

    def turn_on(self, **kwargs: Any) -> None:
        pass

    def turn_off(self, **kwargs: Any) -> None:
        pass
