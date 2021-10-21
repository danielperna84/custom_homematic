"""binary_sensor for hahm."""
import logging

from hahomematic.const import HA_PLATFORM_SENSOR
from homeassistant.components.sensor import SensorEntity

from .const import DOMAIN
from .control_unit import Control_Unit
from .generic_entity import HaHomematicGenericEntity

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass, entry, async_add_entities) -> None:
    """Set up the hahm sensor platform."""
    cu: Control_Unit = hass.data[DOMAIN][entry.entry_id]
    entities: list[HaHomematicGenericEntity] = []
    # for hm_entity in cu.get_new_hm_entities(HA_PLATFORM_SENSOR):
    #    entities.append(HaHomematicSensor(cu, hm_entity))
    async_add_entities(entities)


class HaHomematicSensor(HaHomematicGenericEntity, SensorEntity):
    """Representation of the HomematicIP sensor entity."""

    @property
    def native_value(self):
        self._hm_entity._state

    @property
    def native_unit_of_measurement(self) -> str:
        return "%"
