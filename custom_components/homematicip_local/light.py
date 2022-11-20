"""binary_sensor for Homematic(IP) Local."""
from __future__ import annotations

import logging
from typing import Any

from hahomematic.const import HmPlatform
from hahomematic.custom_platforms.light import (
    HM_ARG_COLOR_TEMP,
    HM_ARG_EFFECT,
    HM_ARG_HS_COLOR,
    HM_ARG_RAMP_TIME,
    BaseHmLight,
    CeDimmer,
    CeIpFixedColorLight,
)
import voluptuous as vol

from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ATTR_COLOR_TEMP,
    ATTR_EFFECT,
    ATTR_HS_COLOR,
    ATTR_TRANSITION,
    ColorMode,
    LightEntity,
    LightEntityFeature,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import STATE_ON, STATE_UNAVAILABLE, STATE_UNKNOWN
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import entity_platform
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import CONTROL_UNITS, DOMAIN
from .control_unit import ControlUnit, async_signal_new_hm_entity
from .generic_entity import HaHomematicGenericRestoreEntity

_LOGGER = logging.getLogger(__name__)
ATTR_ON_TIME = "on_time"

ATTR_RESTORE_COLOR_MODE = "color_mode"
ATTR_RESTORE_BRIGHTNESS = "brightness"
ATTR_RESTORE_COLOR_TEMP = "color_temp"
ATTR_RESTORE_HS_COLOR = "hs_color"

ATTR_COLOR = "color"
ATTR_CHANNEL_COLOR = "channel_color"
ATTR_CHANNEL_LEVEL = "channel_level"

SERVICE_LIGHT_SET_ON_TIME = "light_set_on_time"


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Homematic(IP) Local light platform."""
    control_unit: ControlUnit = hass.data[DOMAIN][CONTROL_UNITS][config_entry.entry_id]

    @callback
    def async_add_light(args: Any) -> None:
        """Add light from Homematic(IP) Local."""
        entities: list[HaHomematicGenericRestoreEntity] = []

        for hm_entity in args:
            entities.append(HaHomematicLight(control_unit, hm_entity))

        if entities:
            async_add_entities(entities)

    config_entry.async_on_unload(
        async_dispatcher_connect(
            hass,
            async_signal_new_hm_entity(config_entry.entry_id, HmPlatform.LIGHT),
            async_add_light,
        )
    )

    async_add_light(
        control_unit.async_get_new_hm_entities_by_platform(platform=HmPlatform.LIGHT)
    )

    platform = entity_platform.async_get_current_platform()
    platform.async_register_entity_service(
        SERVICE_LIGHT_SET_ON_TIME,
        {
            vol.Required(ATTR_ON_TIME): vol.All(
                vol.Coerce(int), vol.Range(min=0, max=8580000)
            ),
        },
        "async_set_on_time",
    )


class HaHomematicLight(HaHomematicGenericRestoreEntity[BaseHmLight], LightEntity):
    """Representation of the HomematicIP light entity."""

    @property
    def color_mode(self) -> ColorMode:
        """Return the color mode of the light."""
        if self._hm_entity.supports_hs_color:
            return ColorMode.HS
        if self._hm_entity.supports_color_temperature:
            return ColorMode.COLOR_TEMP
        if self._hm_entity.supports_brightness:
            return ColorMode.BRIGHTNESS
        return ColorMode.ONOFF

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return the state attributes of the generic entity."""
        attributes = super().extra_state_attributes
        if isinstance(self._hm_entity, CeDimmer):
            if (
                self._hm_entity.channel_brightness
                and self._hm_entity.brightness != self._hm_entity.channel_brightness
            ):
                attributes[ATTR_CHANNEL_LEVEL] = (
                    self._hm_entity.channel_brightness / 255 * 100
                )
        if isinstance(self._hm_entity, CeIpFixedColorLight):
            attributes[ATTR_COLOR] = self._hm_entity.color_name
            if (
                self._hm_entity.channel_brightness
                and self._hm_entity.brightness != self._hm_entity.channel_brightness
            ):
                attributes[ATTR_CHANNEL_LEVEL] = (
                    self._hm_entity.channel_brightness / 255 * 100
                )
            if (
                self._hm_entity.channel_color_name
                and self._hm_entity.color_name != self._hm_entity.channel_color_name
            ):
                attributes[ATTR_CHANNEL_COLOR] = self._hm_entity.channel_color_name

        return attributes

    @property
    def supported_color_modes(self) -> set[ColorMode]:
        """Flag supported color modes."""
        return {self.color_mode}

    @property
    def supported_features(self) -> LightEntityFeature:
        """Return the list of supported features."""
        supported_features = LightEntityFeature.TRANSITION
        if self._hm_entity.supports_effects:
            supported_features |= LightEntityFeature.EFFECT
        return supported_features

    @property
    def is_on(self) -> bool | None:
        """Return true if dimmer is on."""
        if self._hm_entity.is_valid:
            return self._hm_entity.is_on is True
        if self.is_restored:
            if (restored_state := self._restored_state.state) not in (  # type: ignore[union-attr]
                STATE_UNKNOWN,
                STATE_UNAVAILABLE,
            ):
                return restored_state == STATE_ON
        return None

    @property
    def brightness(self) -> int | None:
        """Return the brightness of this light between 0..255."""
        if self._hm_entity.is_valid:
            return self._hm_entity.brightness
        if self.is_restored:
            return self._restored_state.attributes.get(ATTR_RESTORE_BRIGHTNESS)  # type: ignore[union-attr]
        return None

    @property
    def color_temp(self) -> int | None:
        """Return the color temperature of this light between 0..255."""
        if self._hm_entity.is_valid:
            return self._hm_entity.color_temp
        if self.is_restored:
            return self._restored_state.attributes.get(ATTR_RESTORE_COLOR_TEMP)  # type: ignore[union-attr]
        return None

    @property
    def effect(self) -> str | None:
        """Return the current effect."""
        return self._hm_entity.effect

    @property
    def effect_list(self) -> list[str] | None:
        """Return the list of supported effects."""
        return self._hm_entity.effect_list

    @property
    def hs_color(self) -> tuple[float, float] | None:
        """Return the hue and saturation color value [float, float]."""
        if self._hm_entity.is_valid:
            return self._hm_entity.hs_color
        if self.is_restored:
            return self._restored_state.attributes.get(ATTR_RESTORE_HS_COLOR)  # type: ignore[union-attr]
        return None

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the light on."""
        hm_kwargs: dict[str, Any] = {}
        # Use hs_color from kwargs, if not applicable use current hs_color.
        if color_temp := kwargs.get(ATTR_COLOR_TEMP, self.color_temp):
            hm_kwargs[HM_ARG_COLOR_TEMP] = color_temp
        if hs_color := kwargs.get(ATTR_HS_COLOR, self.hs_color):
            hm_kwargs[HM_ARG_HS_COLOR] = hs_color
        # Use brightness from kwargs, if not applicable use current brightness.
        if brightness := kwargs.get(ATTR_BRIGHTNESS, self.brightness) or 255:
            hm_kwargs[ATTR_BRIGHTNESS] = brightness
        # Use transition from kwargs, if not applicable use 0.
        if ramp_time := kwargs.get(ATTR_TRANSITION, 0):
            hm_kwargs[HM_ARG_RAMP_TIME] = ramp_time
        # Use effect from kwargs
        if effect := kwargs.get(ATTR_EFFECT):
            hm_kwargs[HM_ARG_EFFECT] = effect

        await self._hm_entity.turn_on(**hm_kwargs)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the light off."""
        hm_kwargs: dict[str, Any] = {}
        # Use transition from kwargs, if not applicable use 0.
        if ramp_time := kwargs.get(ATTR_TRANSITION, 0):
            hm_kwargs[HM_ARG_RAMP_TIME] = ramp_time
        await self._hm_entity.turn_off(**hm_kwargs)

    async def async_set_on_time(self, on_time: float) -> None:
        """Set the on time of the light."""
        await self._hm_entity.set_on_time_value(on_time=on_time)
