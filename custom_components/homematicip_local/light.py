"""binary_sensor for Homematic(IP) Local."""
from __future__ import annotations

import logging
from typing import Any

from hahomematic.const import HmPlatform
from hahomematic.devices.light import (
    ATTR_HM_COLOR_TEMP,
    ATTR_HM_HS_COLOR,
    ATTR_HM_RAMP_TIME,
    BaseHmLight,
)

from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ATTR_COLOR_TEMP,
    ATTR_HS_COLOR,
    ATTR_TRANSITION,
    COLOR_MODE_BRIGHTNESS,
    COLOR_MODE_COLOR_TEMP,
    COLOR_MODE_HS,
    COLOR_MODE_ONOFF,
    SUPPORT_BRIGHTNESS,
    SUPPORT_COLOR,
    SUPPORT_COLOR_TEMP,
    SUPPORT_TRANSITION,
    LightEntity,
)
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
    """Set up the Homematic(IP) Local light platform."""
    control_unit: ControlUnit = hass.data[DOMAIN][config_entry.entry_id]

    @callback
    def async_add_light(args: Any) -> None:
        """Add light from Homematic(IP) Local."""
        entities: list[HaHomematicGenericEntity] = []

        for hm_entity in args:
            entities.append(HaHomematicLight(control_unit, hm_entity))

        if entities:
            async_add_entities(entities)

    config_entry.async_on_unload(
        async_dispatcher_connect(
            hass,
            control_unit.async_signal_new_hm_entity(
                config_entry.entry_id, HmPlatform.LIGHT
            ),
            async_add_light,
        )
    )

    async_add_light(
        control_unit.async_get_new_hm_entities_by_platform(HmPlatform.LIGHT)
    )


class HaHomematicLight(HaHomematicGenericEntity[BaseHmLight], LightEntity):
    """Representation of the HomematicIP light entity."""

    @property
    def color_mode(self) -> str:
        """Return the color mode of the light."""
        if self._hm_entity.supports_hs_color:
            return COLOR_MODE_HS
        if self._hm_entity.supports_color_temperature:
            return COLOR_MODE_COLOR_TEMP
        if self._hm_entity.supports_brightness:
            return COLOR_MODE_BRIGHTNESS
        return COLOR_MODE_ONOFF

    @property
    def supported_color_modes(self) -> set[str]:
        """Flag supported color modes."""
        return {self.color_mode}

    @property
    def supported_features(self) -> int:
        """Return the list of supported features."""
        supported_features = 0
        if self._hm_entity.supports_brightness:
            supported_features += SUPPORT_BRIGHTNESS
        if self._hm_entity.supports_color_temperature:
            supported_features += SUPPORT_COLOR_TEMP
        if self._hm_entity.supports_hs_color:
            supported_features += SUPPORT_COLOR
        if self._hm_entity.supports_transition:
            supported_features += SUPPORT_TRANSITION
        return supported_features

    @property
    def is_on(self) -> bool:
        """Return true if dimmer is on."""
        return self._hm_entity.is_on is True

    @property
    def brightness(self) -> int | None:
        """Return the brightness of this light between 0..255."""
        return self._hm_entity.brightness

    @property
    def color_temp(self) -> int | None:
        """Return the color temperature of this light between 0..255."""
        return self._hm_entity.color_temp

    @property
    def hs_color(self) -> tuple[float, float] | None:
        """Return the hue and saturation color value [float, float]."""
        return self._hm_entity.hs_color

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the light on."""
        hm_kwargs: dict[str, Any] = {}
        # Use hs_color from kwargs, if not applicable use current hs_color.
        if color_temp := kwargs.get(ATTR_COLOR_TEMP, self.color_temp):
            hm_kwargs[ATTR_HM_COLOR_TEMP] = color_temp
        if hs_color := kwargs.get(ATTR_HS_COLOR, self.hs_color):
            hm_kwargs[ATTR_HM_HS_COLOR] = hs_color
        # Use brightness from kwargs, if not applicable use current brightness.
        if brightness := kwargs.get(ATTR_BRIGHTNESS, self.brightness) or 255:
            hm_kwargs[ATTR_BRIGHTNESS] = brightness
        # Use transition from kwargs, if not applicable use 0.
        if ramp_time := kwargs.get(ATTR_TRANSITION, 0):
            hm_kwargs[ATTR_HM_RAMP_TIME] = ramp_time

        await self._hm_entity.turn_on(**hm_kwargs)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the light off."""
        await self._hm_entity.turn_off()
