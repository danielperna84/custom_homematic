"""binary_sensor for HAHM."""
import logging

from hahomematic.const import HA_PLATFORM_SENSOR

from homeassistant.components.sensor import SensorEntity
from homeassistant.core import callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect

from .const import DOMAIN
from .controlunit import ControlUnit
from .generic_entity import HaHomematicGenericEntity

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass, entry, async_add_entities):
    """Set up the HAHM sensor platform."""
    cu: ControlUnit = hass.data[DOMAIN][entry.entry_id]

    @callback
    def async_add_sensor(args):
        """Add sensor from HAHM."""
        entities = []

        for hm_entity in args[0]:
            entities.append(HaHomematicSensor(cu, hm_entity))

        if entities:
            async_add_entities(entities)

    entry.async_on_unload(
        async_dispatcher_connect(
            hass,
            cu.async_signal_new_hm_entity(HA_PLATFORM_SENSOR),
            async_add_sensor,
        )
    )

    async_add_sensor([cu.server.get_hm_entities_by_platform(HA_PLATFORM_SENSOR)])


class HaHomematicSensor(HaHomematicGenericEntity, SensorEntity):
    """Representation of the HomematicIP sensor entity."""

    @property
    def native_value(self):
        return self._hm_entity.state

    @property
    def native_unit_of_measurement(self) -> str:
        return self._hm_entity.unit
