"""sensor for Homematic(IP) Local."""
from __future__ import annotations

import logging
from typing import Any

from hahomematic.const import TYPE_FLOAT, TYPE_INTEGER, HmPlatform
from hahomematic.hub import HmSystemVariable
from hahomematic.platforms.sensor import HmSensor

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .control_unit import ControlUnit
from .generic_entity import HaHomematicGenericEntity
from .helpers import HmSensorEntityDescription

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Homematic(IP) Local sensor platform."""
    control_unit: ControlUnit = hass.data[DOMAIN][config_entry.entry_id]

    @callback
    def async_add_sensor(args: Any) -> None:
        """Add sensor from Homematic(IP) Local."""
        entities: list[HaHomematicGenericEntity] = []

        for hm_entity in args:
            entities.append(HaHomematicSensor(control_unit, hm_entity))

        if entities:
            async_add_entities(entities)

    @callback
    def async_add_hub_sensors(args: Any) -> None:
        """Add hub sensor from Homematic(IP) Local."""

        entities = []

        for hm_entity in args:
            entities.append(HaHomematicHubSensor(control_unit, hm_entity))

        if entities:
            async_add_entities(entities)

    config_entry.async_on_unload(
        async_dispatcher_connect(
            hass,
            control_unit.async_signal_new_hm_entity(
                config_entry.entry_id, HmPlatform.SENSOR
            ),
            async_add_sensor,
        )
    )
    config_entry.async_on_unload(
        async_dispatcher_connect(
            hass,
            control_unit.async_signal_new_hm_entity(
                config_entry.entry_id, HmPlatform.HUB_SENSOR
            ),
            async_add_hub_sensors,
        )
    )

    async_add_sensor(
        control_unit.async_get_new_hm_entities_by_platform(HmPlatform.SENSOR)
    )


class HaHomematicSensor(HaHomematicGenericEntity[HmSensor], SensorEntity):
    """Representation of the HomematicIP sensor entity."""

    entity_description: HmSensorEntityDescription

    def __init__(
        self,
        control_unit: ControlUnit,
        hm_entity: HmSensor,
    ) -> None:
        """Initialize the sensor entity."""
        super().__init__(control_unit=control_unit, hm_entity=hm_entity)
        self._multiplier: int = (
            self.entity_description.multiplier
            if hasattr(self, "entity_description")
            and self.entity_description
            and self.entity_description.multiplier is not None
            else hm_entity.multiplier
        )
        if not hasattr(self, "entity_description") and hm_entity.unit:
            self._attr_native_unit_of_measurement = hm_entity.unit

    @property
    def native_value(self) -> Any:
        """Return the native value of the entity."""
        if (
            self._hm_entity.value is not None
            and self._hm_entity.hmtype in (TYPE_FLOAT, TYPE_INTEGER)
            and self._multiplier != 1
        ):
            return self._hm_entity.value * self._multiplier
        return self._hm_entity.value


class HaHomematicHubSensor(HaHomematicGenericEntity[HmSystemVariable], SensorEntity):
    """Representation of the HomematicIP hub sensor entity."""

    def __init__(
        self,
        control_unit: ControlUnit,
        hm_entity: HmSystemVariable,
    ) -> None:
        """Initialize the sensor entity."""
        super().__init__(control_unit=control_unit, hm_entity=hm_entity)
        self._attr_native_unit_of_measurement = hm_entity.unit
        self._attr_entity_registry_enabled_default = False

    @property
    def native_value(self) -> Any:
        """Return the native value of the entity."""
        return self._hm_entity.value
