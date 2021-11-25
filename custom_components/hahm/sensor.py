"""binary_sensor for HAHM."""
import logging
from datetime import timedelta

from hahomematic.const import HA_PLATFORM_SENSOR

from homeassistant.components.sensor import SensorEntity
from homeassistant.core import callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect

from .const import DOMAIN
from .controlunit import ControlUnit
from .generic_entity import HaHomematicGenericEntity
from .helper import get_sensor_entity_description

_LOGGER = logging.getLogger(__name__)

SCAN_INTERVAL = timedelta(seconds=30)


async def async_setup_entry(hass, entry, async_add_entities):
    """Set up the HAHM sensor platform."""
    control_unit: ControlUnit = hass.data[DOMAIN][entry.entry_id]

    @callback
    def async_add_sensor(args):
        """Add sensor from HAHM."""
        entities = []

        for hm_entity in args[0]:
            entities.append(HaHomematicSensor(control_unit, hm_entity))

        if entities:
            async_add_entities(entities)

    def async_add_hub_sensors(args):
        """Add hub sensor from HAHM."""

        entities = []

        for hm_entity in args[0]:
            entities.append(HaHomematicHubSensor(control_unit, hm_entity))

        for hm_entity in control_unit.central.hub.hub_entities.values():
            entities.append(HaHomematicHubSensor(control_unit, hm_entity))

        if entities:
            async_add_entities(entities)

    entry.async_on_unload(
        async_dispatcher_connect(
            hass,
            control_unit.async_signal_new_hm_entity(entry.entry_id, HA_PLATFORM_SENSOR),
            async_add_sensor,
        )
    )
    entry.async_on_unload(
        async_dispatcher_connect(
            hass,
            control_unit.async_signal_new_hm_entity(entry.entry_id, "hub"),
            async_add_hub_sensors,
        )
    )

    async_add_sensor([control_unit.get_hm_entities_by_platform(HA_PLATFORM_SENSOR)])


class HaHomematicSensor(HaHomematicGenericEntity, SensorEntity):
    """Representation of the HomematicIP sensor entity."""

    def __init__(self, control_unit: ControlUnit, hm_entity) -> None:
        """Initialize the sensor entity."""
        entity_description = get_sensor_entity_description(
            hm_entity.device_type, hm_entity.parameter
        )
        super().__init__(
            control_unit=control_unit,
            hm_entity=hm_entity,
            entity_description=entity_description,
        )

    @property
    def native_value(self):
        return self._hm_entity.state


class HaHomematicHubSensor(HaHomematicGenericEntity, SensorEntity):
    """Representation of the HomematicIP sensor entity."""

    def __init__(self, control_unit: ControlUnit, hm_entity) -> None:
        """Initialize the sensor entity."""
        super().__init__(
            control_unit=control_unit, hm_entity=hm_entity, entity_description=None
        )

    @property
    def native_value(self):
        return self._hm_entity.state

    @property
    def should_poll(self) -> bool:
        """No polling needed."""
        return self._hm_entity.should_poll

    async def async_update(self):
        """Update the hub and all entities."""
        await self._hm_entity.fetch_data()
