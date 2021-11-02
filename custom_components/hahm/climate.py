"""climate for HAHM."""
import logging
from typing import Any

from hahomematic.const import HA_PLATFORM_CLIMATE
from hahomematic.entity import CustomEntity

from homeassistant.components.climate import ClimateEntity
from homeassistant.core import callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect

from .const import DOMAIN
from .controlunit import ControlUnit
from .generic_entity import HaHomematicGenericEntity

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass, entry, async_add_entities):
    """Set up the HAHM climate platform."""
    cu: ControlUnit = hass.data[DOMAIN][entry.entry_id]

    @callback
    def async_add_climate(args):
        """Add climate from HAHM."""
        entities = []

        for hm_entity in args[0]:
            entities.append(HaHomematicClimate(cu, hm_entity))

        if entities:
            async_add_entities(entities)

    entry.async_on_unload(
        async_dispatcher_connect(
            hass,
            cu.async_signal_new_hm_entity(HA_PLATFORM_CLIMATE),
            async_add_climate,
        )
    )

    async_add_climate([cu.server.get_hm_entities_by_platform(HA_PLATFORM_CLIMATE)])


class HaHomematicClimate(HaHomematicGenericEntity, ClimateEntity):
    """Representation of the HomematicIP climate entity."""

    @property
    def temperature_unit(self) -> str:
        """Return the unit of measurement."""
        return self._hm_entity.temperature_unit

    @property
    def supported_features(self) -> int:
        """Return the list of supported features."""
        return self._hm_entity.supported_features

    @property
    def target_temperature(self) -> float:
        """Return the temperature we try to reach."""
        return self._hm_entity.target_temperature

    @property
    def target_temperature_step(self) -> float:
        """Return the target_temperature_step we use."""
        return self._hm_entity.target_temperature_step

    @property
    def current_temperature(self) -> float:
        """Return the current temperature."""
        return self._hm_entity.current_temperature

    @property
    def current_humidity(self) -> int:
        """Return the current humidity."""
        return self._hm_entity.current_humidity

    @property
    def hvac_mode(self) -> str:
        """Return hvac operation ie."""
        return self._hm_entity.hvac_mode

    @property
    def hvac_modes(self) -> list[str]:
        """Return the list of available hvac operation modes."""
        return self._hm_entity.hvac_modes

    @property
    def preset_mode(self) -> str:
        """Return the current preset mode."""
        return self._hm_entity.preset_mode

    @property
    def preset_modes(self) -> list[str]:
        """Return a list of available preset modes incl. hmip profiles."""
        return self._hm_entity.preset_modes

    @property
    def min_temp(self) -> float:
        """Return the minimum temperature."""
        return self._hm_entity.min_temp

    @property
    def max_temp(self) -> float:
        """Return the maximum temperature."""
        return self._hm_entity.max_temp

    def set_temperature(self, **kwargs) -> None:
        """Set new target temperature."""
        self._hm_entity.set_temperature(**kwargs)

    def set_hvac_mode(self, hvac_mode: str) -> None:
        """Set new target hvac mode."""
        self._hm_entity.set_hvac_mode(hvac_mode)

    def set_preset_mode(self, preset_mode: str) -> None:
        """Set new preset mode."""
        self._hm_entity.set_preset_mode(preset_mode)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return the state attributes of the access point."""
        state_attr = super().extra_state_attributes

        return state_attr
