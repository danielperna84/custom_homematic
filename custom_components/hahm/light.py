"""binary_sensor for HAHM."""
from __future__ import annotations

import logging
from typing import Any

from hahomematic.const import HmPlatform
from hahomematic.devices.light import BaseHmLight

from homeassistant.components.light import ATTR_BRIGHTNESS, ATTR_HS_COLOR, LightEntity
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
    """Set up the HAHM light platform."""
    control_unit: ControlUnit = hass.data[DOMAIN][config_entry.entry_id]

    @callback
    def async_add_light(args: Any) -> None:
        """Add light from HAHM."""
        entities: list[HaHomematicGenericEntity] = []

        for hm_entity in args[0]:
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

    async_add_light([control_unit.get_hm_entities_by_platform(HmPlatform.LIGHT)])


class HaHomematicLight(HaHomematicGenericEntity[BaseHmLight], LightEntity):
    """Representation of the HomematicIP light entity."""

    def __init__(
        self,
        control_unit: ControlUnit,
        hm_entity: BaseHmLight,
    ) -> None:
        """Initialize the light entity."""
        super().__init__(control_unit=control_unit, hm_entity=hm_entity)
        self._attr_color_mode = hm_entity.color_mode
        self._attr_supported_color_modes = hm_entity.supported_color_modes

    @property
    def is_on(self) -> bool:
        """Return true if dimmer is on."""
        return self._hm_entity.is_on is True

    @property
    def brightness(self) -> int:
        """Return the brightness of this light between 0..255."""
        return self._hm_entity.brightness

    @property
    def hs_color(self) -> tuple[float, float] | None:
        """Return the hue and saturation color value [float, float]."""
        return self._hm_entity.hs_color

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the light on."""
        # Use hs_color from kwargs,
        # if not applicable use current hs_color.
        hs_color: tuple[float, float] | None = None
        if hasattr(self, "hs_color"):
            hs_color = kwargs.get(ATTR_HS_COLOR, self.hs_color)

        # Use brightness from kwargs,
        # if not applicable use current brightness.
        brightness: int = 255
        if hasattr(self, "brightness"):
            brightness = kwargs.get(ATTR_BRIGHTNESS, self.brightness)

            # If no kwargs, use default value.
            if not kwargs:
                brightness = 255

            # Minimum brightness is 10, otherwise the led is disabled
            brightness = max(10, brightness)

        await self._hm_entity.turn_on(hs_color, brightness)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the light off."""
        await self._hm_entity.turn_off()
