"""binary_sensor for HAHM."""
import logging

from hahomematic.const import HA_PLATFORM_BINARY_SENSOR

from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.core import callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect

from .const import DOMAIN
from .controlunit import ControlUnit
from .generic_entity import HaHomematicGenericEntity
from .helper import get_binary_sensor_entity_description

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass, entry, async_add_entities):
    """Set up the HAHM binary_sensor platform."""
    cu: ControlUnit = hass.data[DOMAIN][entry.entry_id]

    @callback
    def async_add_binary_sensor(args):
        """Add binary_sensor from HAHM."""
        entities = []

        for hm_entity in args[0]:
            entities.append(HaHomematicBinarySensor(cu, hm_entity))

        if entities:
            async_add_entities(entities)

    entry.async_on_unload(
        async_dispatcher_connect(
            hass,
            cu.async_signal_new_hm_entity(HA_PLATFORM_BINARY_SENSOR),
            async_add_binary_sensor,
        )
    )

    async_add_binary_sensor([cu.get_hm_entities_by_platform(HA_PLATFORM_BINARY_SENSOR)])


class HaHomematicBinarySensor(HaHomematicGenericEntity, BinarySensorEntity):
    """Representation of the Homematic binary sensor."""

    def __init__(self, cu: ControlUnit, hm_entity) -> None:
        """Initialize the binary_sensor entity."""
        entity_description = get_binary_sensor_entity_description(hm_entity.device_type, hm_entity.parameter)
        super().__init__(
            cu=cu, hm_entity=hm_entity, entity_description=entity_description
        )

    @property
    def is_on(self) -> bool:
        """Return true if motion is detected."""
        return self._hm_entity.state
