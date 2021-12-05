"""binary_sensor for HAHM."""
from __future__ import annotations

import logging

from hahomematic.const import HmPlatform
from hahomematic.platforms.number import HmNumber

from homeassistant.components.number import NumberEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ENTITY_CATEGORY_CONFIG
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
    """Set up the HAHM number platform."""
    control_unit: ControlUnit = hass.data[DOMAIN][config_entry.entry_id]

    @callback
    def async_add_number(args):
        """Add number from HAHM."""
        entities = []

        for hm_entity in args[0]:
            entities.append(HaHomematicNumber(control_unit, hm_entity))

        if entities:
            async_add_entities(entities)

    config_entry.async_on_unload(
        async_dispatcher_connect(
            hass,
            control_unit.async_signal_new_hm_entity(
                config_entry.entry_id, HmPlatform.NUMBER
            ),
            async_add_number,
        )
    )

    async_add_number([control_unit.get_hm_entities_by_platform(HmPlatform.NUMBER)])


class HaHomematicNumber(HaHomematicGenericEntity, NumberEntity):
    """Representation of the HomematicIP number entity."""

    _hm_entity: HmNumber

    @property
    def min_value(self) -> float:
        """Return the minimum value."""
        return self._hm_entity.min

    @property
    def max_value(self) -> float:
        """Return the maximum value."""
        return self._hm_entity.max

    @property
    def step(self) -> float:
        """Return the increment/decrement step."""
        return 0.1

    @property
    def unit_of_measurement(self) -> str:
        """Return the unit of measurement."""
        return self._hm_entity.unit

    @property
    def value(self):
        """Return the current value."""
        return self._hm_entity.state

    async def async_set_value(self, value: float) -> None:
        """Update the current value."""
        await self._hm_entity.set_state(value)

    @property
    def entity_category(self) -> str:
        """Return the entity categorie."""
        return ENTITY_CATEGORY_CONFIG
