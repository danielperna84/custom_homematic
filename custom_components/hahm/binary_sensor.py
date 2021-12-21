"""binary_sensor for HAHM."""
from __future__ import annotations

import logging
from typing import Any

from hahomematic.const import HmPlatform
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
    """Set up the HAHM binary_sensor platform."""
    control_unit: ControlUnit = hass.data[DOMAIN][config_entry.entry_id]

    @callback
    def async_add_binary_sensor(args: Any) -> None:
        """Add binary_sensor from HAHM."""
        entities: list[HaHomematicGenericEntity] = []

        for hm_entity in args[0]:
            entities.append(HaHomematicBinarySensor(control_unit, hm_entity))

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

    async_add_binary_sensor(
        [control_unit.async_get_hm_entities_by_platform(HmPlatform.BINARY_SENSOR)]
    )


class HaHomematicBinarySensor(
    HaHomematicGenericEntity[HmBinarySensor], BinarySensorEntity
):
    """Representation of the Homematic binary sensor."""

    @property
    def is_on(self) -> bool:
        """Return true if motion is detected."""
        return self._hm_entity.state is True
