"""binary_sensor for HAHM."""
import logging

from hahomematic.const import HA_PLATFORM_NUMBER

from homeassistant.components.number import NumberEntity
from homeassistant.const import ENTITY_CATEGORY_CONFIG
from homeassistant.core import callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect

from .const import DOMAIN
from .controlunit import ControlUnit
from .generic_entity import HaHomematicGenericEntity

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass, entry, async_add_entities):
    """Set up the HAHM number platform."""
    control_unit: ControlUnit = hass.data[DOMAIN][entry.entry_id]

    @callback
    def async_add_number(args):
        """Add number from HAHM."""
        entities = []

        for hm_entity in args[0]:
            entities.append(HaHomematicNumber(control_unit, hm_entity))

        if entities:
            async_add_entities(entities)

    entry.async_on_unload(
        async_dispatcher_connect(
            hass,
            control_unit.async_signal_new_hm_entity(entry.entry_id, HA_PLATFORM_NUMBER),
            async_add_number,
        )
    )

    async_add_number([control_unit.get_hm_entities_by_platform(HA_PLATFORM_NUMBER)])


class HaHomematicNumber(HaHomematicGenericEntity, NumberEntity):
    """Representation of the HomematicIP number entity."""

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
