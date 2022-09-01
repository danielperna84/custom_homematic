"""binary_sensor for Homematic(IP) Local."""
from __future__ import annotations

import logging
from typing import Any

from hahomematic.const import HmPlatform
from hahomematic.platforms.binary_sensor import HmBinarySensor, HmSysvarBinarySensor

from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import STATE_ON, STATE_UNAVAILABLE, STATE_UNKNOWN
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import CONTROL_UNITS, DOMAIN
from .control_unit import ControlUnit
from .generic_entity import (
    HaHomematicGenericRestoreEntity,
    HaHomematicGenericSysvarEntity,
)

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Homematic(IP) Local binary_sensor platform."""
    control_unit: ControlUnit = hass.data[DOMAIN][CONTROL_UNITS][config_entry.entry_id]

    @callback
    def async_add_binary_sensor(args: Any) -> None:
        """Add binary_sensor from Homematic(IP) Local."""
        entities: list[HaHomematicGenericRestoreEntity] = []

        for hm_entity in args:
            entities.append(HaHomematicBinarySensor(control_unit, hm_entity))

        if entities:
            async_add_entities(entities)

    @callback
    def async_add_hub_binary_sensor(args: Any) -> None:
        """Add sysvar binary sensor from Homematic(IP) Local."""

        entities = []

        for hm_entity in args:
            entities.append(HaHomematicSysvarBinarySensor(control_unit, hm_entity))

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
            async_add_hub_binary_sensor,
        )
    )

    async_add_binary_sensor(
        control_unit.async_get_new_hm_entities_by_platform(
            platform=HmPlatform.BINARY_SENSOR
        )
    )

    async_add_hub_binary_sensor(
        control_unit.async_get_new_hm_hub_entities_by_platform(
            platform=HmPlatform.HUB_BINARY_SENSOR
        )
    )


class HaHomematicBinarySensor(
    HaHomematicGenericRestoreEntity[HmBinarySensor], BinarySensorEntity
):
    """Representation of the Homematic binary sensor."""

    @property
    def is_on(self) -> bool | None:
        """Return true if sensor is active."""
        if self._hm_entity.is_valid:
            return self._hm_entity.value
        if self.is_restored:
            if (restored_state := self._restored_state.state) not in (  # type: ignore[union-attr]
                STATE_UNKNOWN,
                STATE_UNAVAILABLE,
            ):
                return restored_state == STATE_ON
        return self._hm_entity.default


class HaHomematicSysvarBinarySensor(
    HaHomematicGenericSysvarEntity[HmSysvarBinarySensor], BinarySensorEntity
):
    """Representation of the HomematicIP hub binary_sensor entity."""

    def is_on(self) -> bool | None:
        """Return the native value of the entity."""
        return bool(self._hm_hub_entity.value)
