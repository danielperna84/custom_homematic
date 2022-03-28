"""binary_sensor for Homematic(IP) Local."""
from __future__ import annotations

import logging
from typing import Any

from hahomematic.const import HmPlatform
from hahomematic.hub import HmSystemVariable
from hahomematic.platforms.binary_sensor import HmBinarySensor

from homeassistant.components.binary_sensor import BinarySensorEntity
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
    """Set up the Homematic(IP) Local binary_sensor platform."""
    control_unit: ControlUnit = hass.data[DOMAIN][config_entry.entry_id]

    @callback
    def async_add_binary_sensor(args: Any) -> None:
        """Add binary_sensor from Homematic(IP) Local."""
        entities: list[HaHomematicGenericEntity] = []

        for hm_entity in args:
            entities.append(HaHomematicBinarySensor(control_unit, hm_entity))

        if entities:
            async_add_entities(entities)

    @callback
    def async_add_hub_binary_sensors(args: Any) -> None:
        """Add hub binary sensor from Homematic(IP) Local."""

        entities = []

        for hm_entity in args:
            entities.append(HaHomematicHubBinarySensor(control_unit, hm_entity))

        if entities:
            async_add_entities(entities)

    config_entry.async_on_unload(
        async_dispatcher_connect(
            hass,
            control_unit.async_signal_new_hm_entity(
                config_entry.entry_id, HmPlatform.BINARY_SENSOR
            ),
            async_add_binary_sensor,
        )
    )
    config_entry.async_on_unload(
        async_dispatcher_connect(
            hass,
            control_unit.async_signal_new_hm_entity(
                config_entry.entry_id, HmPlatform.HUB_BINARY_SENSOR
            ),
            async_add_hub_binary_sensors,
        )
    )

    async_add_binary_sensor(
        control_unit.async_get_new_hm_entities_by_platform(HmPlatform.BINARY_SENSOR)
    )


class HaHomematicBinarySensor(
    HaHomematicGenericEntity[HmBinarySensor], BinarySensorEntity
):
    """Representation of the Homematic binary sensor."""

    @property
    def is_on(self) -> bool | None:
        """Return true if sensor is active."""
        return self._hm_entity.value


class HaHomematicHubBinarySensor(
    HaHomematicGenericEntity[HmSystemVariable], BinarySensorEntity
):
    """Representation of the HomematicIP hub binary_sensor entity."""

    def __init__(
        self,
        control_unit: ControlUnit,
        hm_entity: HmSystemVariable,
    ) -> None:
        """Initialize the binary_sensor entity."""
        super().__init__(control_unit=control_unit, hm_entity=hm_entity)
        self._attr_entity_registry_enabled_default = False

    @property
    def is_on(self) -> bool | None:
        """Return the native value of the entity."""
        return bool(self._hm_entity.value)
