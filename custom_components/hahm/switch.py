"""binary_switch for HAHM."""
from __future__ import annotations

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
    """Set up the HAHM switch platform."""
    control_unit: ControlUnit = hass.data[DOMAIN][entry.entry_id]

    @callback
    def async_add_switch(args):
        """Add switch from HAHM."""
        entities = []

        for hm_entity in args[0]:
            entities.append(HaHomematicSwitch(control_unit, hm_entity))

        if entities:
            async_add_entities(entities)

    entry.async_on_unload(
        async_dispatcher_connect(
            hass,
            control_unit.async_signal_new_hm_entity(entry.entry_id, HA_PLATFORM_SWITCH),
            async_add_switch,
        )
    )

    async_add_switch([control_unit.get_hm_entities_by_platform(HA_PLATFORM_SWITCH)])


class HaHomematicSwitch(HaHomematicGenericEntity, SwitchEntity):
    """Representation of the HomematicIP switch entity."""

    @property
    def is_on(self) -> bool:
        """Return true if switch is on."""
        return self._hm_entity.state

    async def async_turn_on(self, **kwargs) -> None:
        """Turn the switch on."""
        await self._hm_entity.turn_on()

    async def async_turn_off(self, **kwargs) -> None:
        """Turn the switch off."""
        await self._hm_entity.turn_off()
