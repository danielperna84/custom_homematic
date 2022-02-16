"""siren for Homematic(IP) Local."""
from __future__ import annotations

import logging
from typing import Any

from hahomematic.const import HmPlatform
from hahomematic.devices.siren import (
    DISABLE_ACOUSTIC_SIGNAL,
    DISABLE_OPTICAL_SIGNAL,
    BaseSiren,
)
import voluptuous as vol

from homeassistant.components.siren import (
    ATTR_DURATION,
    ATTR_TONE,
    SUPPORT_DURATION,
    SUPPORT_TONES,
    SUPPORT_TURN_OFF,
    SUPPORT_TURN_ON,
    SirenEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import entity_platform
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .control_unit import ControlUnit
from .generic_entity import HaHomematicGenericEntity

_LOGGER = logging.getLogger(__name__)

ATTR_LIGHT = "light"
SERVICE_TURN_ON_SIREN = "turn_on_siren"

TURN_ON_SIREN_SCHEMA = {
    vol.Optional(ATTR_TONE): cv.string,
    vol.Optional(ATTR_LIGHT): cv.string,
    vol.Optional(ATTR_DURATION): cv.positive_int,
}


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Homematic(IP) Local siren platform."""
    control_unit: ControlUnit = hass.data[DOMAIN][config_entry.entry_id]

    @callback
    def async_add_siren(args: Any) -> None:
        """Add siren from Homematic(IP) Local."""
        entities: list[HaHomematicGenericEntity] = []

        for hm_entity in args:
            entities.append(HaHomematicSiren(control_unit, hm_entity))

        if entities:
            async_add_entities(entities)

    platform = entity_platform.async_get_current_platform()
    platform.async_register_entity_service(
        SERVICE_TURN_ON_SIREN,
        TURN_ON_SIREN_SCHEMA,
        "async_turn_on",
    )

    config_entry.async_on_unload(
        async_dispatcher_connect(
            hass,
            control_unit.async_signal_new_hm_entity(
                config_entry.entry_id, HmPlatform.SIREN
            ),
            async_add_siren,
        )
    )

    async_add_siren(
        control_unit.async_get_new_hm_entities_by_platform(HmPlatform.SIREN)
    )


class HaHomematicSiren(HaHomematicGenericEntity[BaseSiren], SirenEntity):
    """Representation of the HomematicIP siren entity."""

    _attr_supported_features = (
        SUPPORT_TONES | SUPPORT_DURATION | SUPPORT_TURN_OFF | SUPPORT_TURN_ON
    )

    @property
    def is_on(self) -> bool:
        """Return true if siren is on."""
        return self._hm_entity.is_on is True

    @property
    def available_tones(self) -> list[int | str] | dict[int, str] | None:
        """Return a list of available tones."""
        return self._hm_entity.available_tones  # type: ignore[return-value]

    @property
    def available_lights(self) -> list[int | str] | dict[int, str] | None:
        """Return a list of available lights."""
        return self._hm_entity.available_lights  # type: ignore[return-value]

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the device on."""
        acoustic_alarm = kwargs.get(ATTR_TONE, DISABLE_ACOUSTIC_SIGNAL)
        if not self.available_tones or acoustic_alarm not in self.available_tones:
            raise ValueError(
                f"Invalid tone specified for entity {self.entity_id}: {acoustic_alarm}, "
                "check the available_tones attribute for valid tones to pass in"
            )
        optical_alarm = kwargs.get(ATTR_LIGHT, DISABLE_OPTICAL_SIGNAL)
        if not self.available_lights or optical_alarm not in self.available_lights:
            raise ValueError(
                f"Invalid light specified for entity {self.entity_id}: {optical_alarm}, "
                "check the available_lights attribute for valid tones to pass in"
            )

        duration = kwargs.get(ATTR_DURATION, 60)
        await self._hm_entity.turn_on(
            acoustic_alarm=acoustic_alarm,
            optical_alarm=optical_alarm,
            duration=duration,
        )

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the device off."""
        await self._hm_entity.turn_off()
