"""binary_sensor for HAHM."""
from __future__ import annotations

from datetime import timedelta
import logging
from typing import Any

from hahomematic.const import HmPlatform
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

_LOGGER = logging.getLogger(__name__)

SCAN_INTERVAL = timedelta(seconds=30)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the HAHM sensor platform."""
    control_unit: ControlUnit = hass.data[DOMAIN][config_entry.entry_id]

    @callback
    def async_add_sensor(args: Any) -> None:
        """Add sensor from HAHM."""
        entities: list[HaHomematicGenericEntity] = []

        for hm_entity in args[0]:
            entities.append(HaHomematicSensor(control_unit, hm_entity))

        if entities:
            async_add_entities(entities)

    def async_add_hub_sensors(args: Any) -> None:
        """Add hub sensor from HAHM."""

        entities = []

        for hm_entity in args[0]:
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
                config_entry.entry_id, HmPlatform.HUB
            ),
            async_add_hub_sensors,
        )
    )

    async_add_sensor([control_unit.get_hm_entities_by_platform(HmPlatform.SENSOR)])


class HaHomematicSensor(HaHomematicGenericEntity[HmSensor], SensorEntity):
    """Representation of the HomematicIP sensor entity."""

    @property
    def native_value(self) -> Any:
        return self._hm_entity.state


class HaHomematicHubSensor(HaHomematicGenericEntity[HmSystemVariable], SensorEntity):
    """Representation of the HomematicIP sensor entity."""

    @property
    def native_value(self) -> Any:
        """Return the native value of zhe entity."""
        return self._hm_entity.state

    @property
    def native_unit_of_measurement(self) -> str | None:
        """Return the unit of zhe entity."""
        return self._hm_entity.unit

    @property
    def should_poll(self) -> bool:
        """No polling needed."""
        return self._hm_entity.should_poll is True

    async def async_update(self) -> None:
        """Update the hub and all entities."""
        await self._hm_entity.fetch_data()
