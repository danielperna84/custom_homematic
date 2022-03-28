"""binary_switch for Homematic(IP) Local."""
from __future__ import annotations

import logging
from typing import Any, Union

from hahomematic.const import HmPlatform
from hahomematic.devices.switch import CeSwitch
from hahomematic.platforms.switch import HmSwitch

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .control_unit import ControlUnit
from .generic_entity import HaHomematicGenericEntity

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Homematic(IP) Local switch platform."""
    control_unit: ControlUnit = hass.data[DOMAIN][config_entry.entry_id]

    @callback
    def async_add_switch(args: Any) -> None:
        """Add switch from Homematic(IP) Local."""
        entities: list[HaHomematicGenericEntity] = []

        for hm_entity in args:
            entities.append(HaHomematicSwitch(control_unit, hm_entity))

        if entities:
            async_add_entities(entities)

    config_entry.async_on_unload(
        async_dispatcher_connect(
            hass,
            control_unit.async_signal_new_hm_entity(
                config_entry.entry_id, HmPlatform.SWITCH
            ),
            async_add_switch,
        )
    )

    async_add_switch(
        control_unit.async_get_new_hm_entities_by_platform(HmPlatform.SWITCH)
    )


class HaHomematicSwitch(
    HaHomematicGenericEntity[Union[CeSwitch, HmSwitch]], SwitchEntity
):
    """Representation of the HomematicIP switch entity."""

    @property
    def is_on(self) -> bool:
        """Return true if switch is on."""
        return self._hm_entity.value is True

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the switch on."""
        await self._hm_entity.turn_on()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the switch off."""
        await self._hm_entity.turn_off()
