"""climate for HAHM."""
from __future__ import annotations

import logging
from typing import Any

from hahomematic.const import HmPlatform
from hahomematic.devices.climate import BaseClimateEntity

from homeassistant.components.climate import ClimateEntity
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
    """Set up the HAHM climate platform."""
    control_unit: ControlUnit = hass.data[DOMAIN][config_entry.entry_id]

    @callback
    def async_add_climate(args: Any) -> None:
        """Add climate from HAHM."""
        entities: list[HaHomematicGenericEntity] = []

        for hm_entity in args[0]:
            entities.append(HaHomematicClimate(control_unit, hm_entity))

        if entities:
            async_add_entities(entities)

    config_entry.async_on_unload(
        async_dispatcher_connect(
            hass,
            control_unit.async_signal_new_hm_entity(
                config_entry.entry_id, HmPlatform.CLIMATE
            ),
            async_add_climate,
        )
    )

    async_add_climate(
        [control_unit.async_get_hm_entities_by_platform(HmPlatform.CLIMATE)]
    )


class HaHomematicClimate(HaHomematicGenericEntity[BaseClimateEntity], ClimateEntity):
    """Representation of the HomematicIP climate entity."""

    def __init__(
        self,
        control_unit: ControlUnit,
        hm_entity: BaseClimateEntity,
    ) -> None:
        """Initialize the climate entity."""
        super().__init__(control_unit=control_unit, hm_entity=hm_entity)
        self._attr_temperature_unit = hm_entity.temperature_unit
        self._attr_supported_features = hm_entity.supported_features
        self._attr_target_temperature_step = hm_entity.target_temperature_step
        self._attr_hvac_modes = hm_entity.hvac_modes
        self._attr_preset_modes = hm_entity.preset_modes
        self._attr_min_temp = float(hm_entity.min_temp)
        self._attr_max_temp = float(hm_entity.max_temp)

    @property
    def target_temperature(self) -> float | None:
        """Return the temperature we try to reach."""
        return self._hm_entity.target_temperature

    @property
    def current_temperature(self) -> float | None:
        """Return the current temperature."""
        return self._hm_entity.current_temperature

    @property
    def current_humidity(self) -> int | None:
        """Return the current humidity."""
        return self._hm_entity.current_humidity

    @property
    def hvac_mode(self) -> str:
        """Return hvac operation ie."""
        return self._hm_entity.hvac_mode

    @property
    def preset_mode(self) -> str:
        """Return the current preset mode."""
        return self._hm_entity.preset_mode

    async def async_set_temperature(self, **kwargs: Any) -> None:
        """Set new target temperature."""
        await self._hm_entity.set_temperature(**kwargs)

    async def async_set_hvac_mode(self, hvac_mode: str) -> None:
        """Set new target hvac mode."""
        await self._hm_entity.set_hvac_mode(hvac_mode)

    async def async_set_preset_mode(self, preset_mode: str) -> None:
        """Set new preset mode."""
        await self._hm_entity.set_preset_mode(preset_mode)
