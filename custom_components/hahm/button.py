"""binary_sensor for HAHM."""
from __future__ import annotations

import logging

from hahomematic.const import HA_PLATFORM_BUTTON

from homeassistant.components.button import ButtonEntity
from homeassistant.core import callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect

from .const import DOMAIN
from .controlunit import ControlUnit
from .generic_entity import HaHomematicGenericEntity

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass, entry, async_add_entities):
    """Set up the HAHM binary_sensor platform."""
    control_unit: ControlUnit = hass.data[DOMAIN][entry.entry_id]

    @callback
    def async_add_button(args):
        """Add button from HAHM."""
        entities = []

        for hm_entity in args[0]:
            entities.append(HaHomematicButton(control_unit, hm_entity))

        if entities:
            async_add_entities(entities)

    entry.async_on_unload(
        async_dispatcher_connect(
            hass,
            control_unit.async_signal_new_hm_entity(entry.entry_id, HA_PLATFORM_BUTTON),
            async_add_button,
        )
    )

    async_add_button([control_unit.get_hm_entities_by_platform(HA_PLATFORM_BUTTON)])


class HaHomematicButton(HaHomematicGenericEntity, ButtonEntity):
    """Representation of the Homematic button."""

    async def async_press(self) -> None:
        await self._hm_entity.press()
