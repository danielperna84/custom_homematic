"""binary_sensor for Homematic(IP) Local."""

from __future__ import annotations

import logging

from hahomematic.const import HmPlatform
from hahomematic.platforms.generic.binary_sensor import HmBinarySensor
from hahomematic.platforms.hub.binary_sensor import HmSysvarBinarySensor

from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import STATE_ON, STATE_UNAVAILABLE, STATE_UNKNOWN
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import CONTROL_UNITS, DOMAIN
from .control_unit import ControlUnit, signal_new_hm_entity
from .generic_entity import HaHomematicGenericRestoreEntity, HaHomematicGenericSysvarEntity

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Homematic(IP) Local binary_sensor platform."""
    control_unit: ControlUnit = hass.data[DOMAIN][CONTROL_UNITS][entry.entry_id]

    @callback
    def async_add_binary_sensor(hm_entities: tuple[HmBinarySensor, ...]) -> None:
        """Add binary_sensor from Homematic(IP) Local."""
        _LOGGER.debug("ASYNC_ADD_BINARY_SENSOR: Adding %i entities", len(hm_entities))
        entities: list[HaHomematicBinarySensor] = []

        for hm_entity in hm_entities:
            entities.append(
                HaHomematicBinarySensor(
                    control_unit=control_unit,
                    hm_entity=hm_entity,
                )
            )

        if entities:
            async_add_entities(entities)

    @callback
    def async_add_hub_binary_sensor(hm_entities: tuple[HmSysvarBinarySensor, ...]) -> None:
        """Add sysvar binary sensor from Homematic(IP) Local."""
        _LOGGER.debug("ASYNC_ADD_HUB_BINARY_SENSOR: Adding %i entities", len(hm_entities))
        entities: list[HaHomematicSysvarBinarySensor] = []

        for hm_entity in hm_entities:
            entities.append(
                HaHomematicSysvarBinarySensor(
                    control_unit=control_unit, hm_sysvar_entity=hm_entity
                )
            )

        if entities:
            async_add_entities(entities)

    entry.async_on_unload(
        func=async_dispatcher_connect(
            hass=hass,
            signal=signal_new_hm_entity(
                entry_id=entry.entry_id, platform=HmPlatform.BINARY_SENSOR
            ),
            target=async_add_binary_sensor,
        )
    )
    entry.async_on_unload(
        func=async_dispatcher_connect(
            hass=hass,
            signal=signal_new_hm_entity(entry.entry_id, HmPlatform.HUB_BINARY_SENSOR),
            target=async_add_hub_binary_sensor,
        )
    )

    async_add_binary_sensor(hm_entities=control_unit.get_new_entities(entity_type=HmBinarySensor))

    async_add_hub_binary_sensor(
        hm_entities=control_unit.get_new_hub_entities(entity_type=HmSysvarBinarySensor)
    )


class HaHomematicBinarySensor(HaHomematicGenericRestoreEntity[HmBinarySensor], BinarySensorEntity):
    """Representation of the Homematic(IP) Local binary sensor."""

    @property
    def is_on(self) -> bool | None:
        """Return true if sensor is active."""
        if self._hm_entity.is_valid:
            return self._hm_entity.value
        if (
            self.is_restored
            and self._restored_state
            and (restored_state := self._restored_state.state)
            not in (STATE_UNKNOWN, STATE_UNAVAILABLE)
        ):
            return restored_state == STATE_ON
        return self._hm_entity.default


class HaHomematicSysvarBinarySensor(
    HaHomematicGenericSysvarEntity[HmSysvarBinarySensor], BinarySensorEntity
):
    """Representation of the HomematicIP hub binary_sensor entity."""

    @property
    def is_on(self) -> bool | None:
        """Return the native value of the entity."""
        return bool(self._hm_hub_entity.value)
