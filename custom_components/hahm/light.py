"""binary_sensor for HAHM."""
import logging
from typing import Any

from hahomematic.const import HA_PLATFORM_LIGHT

from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ATTR_HS_COLOR,
    LightEntity,
)
from homeassistant.core import callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect

from .const import DOMAIN
from .controlunit import ControlUnit
from .generic_entity import HaHomematicGenericEntity

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass, entry, async_add_entities):
    """Set up the HAHM light platform."""
    cu: ControlUnit = hass.data[DOMAIN][entry.entry_id]

    @callback
    def async_add_light(args):
        """Add light from HAHM."""
        entities = []

        for hm_entity in args[0]:
            entities.append(HaHomematicLight(cu, hm_entity))

        if entities:
            async_add_entities(entities)

    entry.async_on_unload(
        async_dispatcher_connect(
            hass,
            cu.async_signal_new_hm_entity(HA_PLATFORM_LIGHT),
            async_add_light,
        )
    )

    async_add_light([cu.get_hm_entities_by_platform(HA_PLATFORM_LIGHT)])


class HaHomematicLight(HaHomematicGenericEntity, LightEntity):
    """Representation of the HomematicIP light entity."""

    @property
    def is_on(self) -> bool:
        """Return true if dimmer is on."""
        return self._hm_entity.is_on

    @property
    def brightness(self) -> int:
        """Return the brightness of this light between 0..255."""
        return self._hm_entity.brightness

    @property
    def color_mode(self) -> str:
        """Return the color mode of the light."""
        return self._hm_entity.color_mode

    @property
    def hs_color(self) -> tuple[float, float]:
        """Return the hue and saturation color value [float, float]."""
        return self._hm_entity.hs_color

    @property
    def supported_color_modes(self) -> set[str]:
        """Flag supported color_modes."""
        return self._hm_entity.supported_color_modes

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the light on."""
        # Use hs_color from kwargs,
        # if not applicable use current hs_color.
        hs_color = None
        if hasattr(self, "hs_color"):
            hs_color = kwargs.get(ATTR_HS_COLOR, self.hs_color)

        # Use brightness from kwargs,
        # if not applicable use current brightness.
        brightness = None
        if hasattr(self, "brightness"):
            brightness = kwargs.get(ATTR_BRIGHTNESS, self.brightness)

            # If no kwargs, use default value.
            if not kwargs:
                brightness = 255

            # Minimum brightness is 10, otherwise the led is disabled
            brightness = max(10, brightness)

        await self._hm_entity.async_turn_on(hs_color, brightness)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the light off."""
        await self._hm_entity.async_turn_off()
