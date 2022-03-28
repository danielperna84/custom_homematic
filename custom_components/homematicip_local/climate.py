"""climate for Homematic(IP) Local."""
from __future__ import annotations

from datetime import datetime, timedelta
import logging
from typing import Any

from hahomematic.const import HmPlatform
from hahomematic.devices.climate import (
    HM_PRESET_MODE_PREFIX,
    BaseClimateEntity,
    HmHvacMode,
    HmPresetMode,
)
import voluptuous as vol

from homeassistant.components.climate import (
    ATTR_TEMPERATURE,
    SUPPORT_PRESET_MODE,
    SUPPORT_TARGET_TEMPERATURE,
    ClimateEntity,
)
from homeassistant.components.climate.const import (
    CURRENT_HVAC_ACTIONS,
    HVAC_MODE_OFF,
    HVAC_MODES,
    PRESET_AWAY,
    PRESET_BOOST,
    PRESET_COMFORT,
    PRESET_ECO,
    PRESET_NONE,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import TEMP_CELSIUS
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import entity_platform
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .control_unit import ControlUnit
from .generic_entity import HaHomematicGenericEntity

_LOGGER = logging.getLogger(__name__)

SERVICE_ENABLE_AWAY_MODE_BY_CALENDAR = "enable_away_mode_by_calendar"
SERVICE_ENABLE_AWAY_MODE_BY_DURATION = "enable_away_mode_by_duration"
SERVICE_DISABLE_AWAY_MODE = "disable_away_mode"
ATTR_AWAY_END = "end"
ATTR_AWAY_HOURS = "hours"
ATTR_AWAY_TEMPERATURE = "away_temperature"

SUPPORTED_HA_PRESET_MODES = [
    PRESET_AWAY,
    PRESET_BOOST,
    PRESET_COMFORT,
    PRESET_ECO,
    PRESET_NONE,
]


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Homematic(IP) Local climate platform."""
    control_unit: ControlUnit = hass.data[DOMAIN][config_entry.entry_id]

    @callback
    def async_add_climate(args: Any) -> None:
        """Add climate from Homematic(IP) Local."""
        entities: list[HaHomematicGenericEntity] = []

        for hm_entity in args:
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
        control_unit.async_get_new_hm_entities_by_platform(HmPlatform.CLIMATE)
    )

    platform = entity_platform.async_get_current_platform()

    platform.async_register_entity_service(
        SERVICE_ENABLE_AWAY_MODE_BY_CALENDAR,
        {
            vol.Required(ATTR_AWAY_END): cv.datetime,
            vol.Required(ATTR_AWAY_TEMPERATURE, default=18.0): vol.All(
                vol.Coerce(float), vol.Range(min=4.5, max=30.5)
            ),
        },
        "async_enable_away_mode_by_calendar",
    )
    platform.async_register_entity_service(
        SERVICE_ENABLE_AWAY_MODE_BY_DURATION,
        {
            vol.Required(ATTR_AWAY_HOURS): cv.positive_int,
            vol.Required(ATTR_AWAY_TEMPERATURE, default=18.0): vol.All(
                vol.Coerce(float), vol.Range(min=4.5, max=30.5)
            ),
        },
        "async_enable_away_mode_by_duration",
    )
    platform.async_register_entity_service(
        SERVICE_DISABLE_AWAY_MODE,
        {},
        "async_disable_away_mode",
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
        self._attr_temperature_unit = TEMP_CELSIUS
        self._attr_target_temperature_step = hm_entity.target_temperature_step
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
    def hvac_action(self) -> str | None:
        """Return the hvac action"""
        if self._hm_entity.hvac_action in CURRENT_HVAC_ACTIONS:
            return str(self._hm_entity.hvac_action.value)
        return None

    @property
    def hvac_mode(self) -> str:
        """Return hvac operation ie."""
        if self._hm_entity.hvac_mode in HVAC_MODES:
            return str(self._hm_entity.hvac_mode.value)
        return HVAC_MODE_OFF

    @property
    def hvac_modes(self) -> list[str]:
        """Return the list of available hvac operation modes."""
        hvac_modes = []
        for hm_hvav_mode in self._hm_entity.hvac_modes:
            if hm_hvav_mode.value in HVAC_MODES:
                hvac_modes.append(hm_hvav_mode.value)
        return hvac_modes

    @property
    def preset_mode(self) -> str | None:
        """Return the current preset mode."""
        if self._hm_entity.preset_mode in SUPPORTED_HA_PRESET_MODES or str(
            self._hm_entity.preset_mode.value
        ).startswith(HM_PRESET_MODE_PREFIX):
            return self._hm_entity.preset_mode
        return None

    @property
    def preset_modes(self) -> list[str]:
        """Return a list of available preset modes incl. hmip profiles."""
        preset_modes = []
        for hm_preset_mode in self._hm_entity.preset_modes:
            if hm_preset_mode.value in SUPPORTED_HA_PRESET_MODES:
                preset_modes.append(hm_preset_mode.value)
            if str(hm_preset_mode.value).startswith(HM_PRESET_MODE_PREFIX):
                preset_modes.append(hm_preset_mode.value)
        return preset_modes

    @property
    def supported_features(self) -> int:
        """Return the list of supported features."""
        supported_features = SUPPORT_TARGET_TEMPERATURE
        if self._hm_entity.supports_preset:
            supported_features += SUPPORT_PRESET_MODE
        return supported_features

    async def async_set_temperature(self, **kwargs: Any) -> None:
        """Set new target temperature."""
        temperature = kwargs.get(ATTR_TEMPERATURE)
        if temperature is None:
            return None
        await self._hm_entity.set_temperature(temperature=temperature)

    async def async_set_hvac_mode(self, hvac_mode: str) -> None:
        """Set new target hvac mode."""
        if hvac_mode not in [enum.value for enum in HmHvacMode]:
            _LOGGER.warning("Hvac mode %s is not supported by integration", hvac_mode)
            return None
        await self._hm_entity.set_hvac_mode(HmHvacMode(hvac_mode))

    async def async_set_preset_mode(self, preset_mode: str) -> None:
        """Set new preset mode."""
        if preset_mode not in [enum.value for enum in HmPresetMode]:
            _LOGGER.warning(
                "Preset mode %s is not supported by integration", preset_mode
            )
            return None
        await self._hm_entity.set_preset_mode(HmPresetMode(preset_mode))

    async def async_enable_away_mode_by_calendar(
        self, end: datetime, away_temperature: float
    ) -> None:
        """Enable the away mode by calendar on thermostat."""
        start = datetime.now() - timedelta(minutes=10)
        await self._hm_entity.enable_away_mode_by_calendar(
            start=start, end=end, away_temperature=away_temperature
        )

    async def async_enable_away_mode_by_duration(
        self, hours: int, away_temperature: float
    ) -> None:
        """Enable the away mode by duration on thermostat."""
        await self._hm_entity.enable_away_mode_by_duration(
            hours=hours, away_temperature=away_temperature
        )

    async def async_disable_away_mode(self) -> None:
        """Disable the away mode on thermostat."""
        await self._hm_entity.disable_away_mode()
