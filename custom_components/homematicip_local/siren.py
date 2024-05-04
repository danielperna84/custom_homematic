"""siren for Homematic(IP) Local."""

from __future__ import annotations

import logging
from typing import Any, Final

from hahomematic.const import HmPlatform
from hahomematic.platforms.custom.siren import BaseSiren, SirenOnArgs
import voluptuous as vol

from homeassistant.components.siren import (
    ATTR_DURATION,
    ATTR_TONE,
    SirenEntity,
    SirenEntityFeature,
)
from homeassistant.const import STATE_ON, STATE_UNAVAILABLE, STATE_UNKNOWN
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import entity_platform
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import HomematicConfigEntry
from .const import SERVICE_TURN_ON_SIREN
from .control_unit import ControlUnit, signal_new_hm_entity
from .generic_entity import HaHomematicGenericRestoreEntity

_LOGGER = logging.getLogger(__name__)

ATTR_LIGHT: Final = "light"

TURN_ON_SIREN_SCHEMA = {
    vol.Optional(ATTR_TONE): cv.string,
    vol.Optional(ATTR_LIGHT): cv.string,
    vol.Optional(ATTR_DURATION): cv.positive_int,
}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: HomematicConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Homematic(IP) Local siren platform."""
    control_unit: ControlUnit = entry.runtime_data

    @callback
    def async_add_siren(hm_entities: tuple[BaseSiren, ...]) -> None:
        """Add siren from Homematic(IP) Local."""
        _LOGGER.debug("ASYNC_ADD_SIREN: Adding %i entities", len(hm_entities))

        if entities := [
            HaHomematicSiren(
                control_unit=control_unit,
                hm_entity=hm_entity,
            )
            for hm_entity in hm_entities
        ]:
            async_add_entities(entities)

    platform = entity_platform.async_get_current_platform()
    platform.async_register_entity_service(
        SERVICE_TURN_ON_SIREN,
        TURN_ON_SIREN_SCHEMA,
        "async_turn_on",
    )

    entry.async_on_unload(
        func=async_dispatcher_connect(
            hass=hass,
            signal=signal_new_hm_entity(entry_id=entry.entry_id, platform=HmPlatform.SIREN),
            target=async_add_siren,
        )
    )

    async_add_siren(hm_entities=control_unit.get_new_entities(entity_type=BaseSiren))


class HaHomematicSiren(HaHomematicGenericRestoreEntity[BaseSiren], SirenEntity):
    """Representation of the HomematicIP siren entity."""

    _attr_supported_features = SirenEntityFeature.TURN_OFF | SirenEntityFeature.TURN_ON

    def __init__(
        self,
        control_unit: ControlUnit,
        hm_entity: BaseSiren,
    ) -> None:
        """Initialize the siren entity."""
        super().__init__(
            control_unit=control_unit,
            hm_entity=hm_entity,
        )
        if hm_entity.supports_tones:
            self._attr_supported_features |= SirenEntityFeature.TONES
        if hm_entity.supports_duration:
            self._attr_supported_features |= SirenEntityFeature.DURATION

    @property
    def is_on(self) -> bool | None:
        """Return true if siren is on."""
        if self._hm_entity.is_valid:
            return self._hm_entity.is_on is True
        if (
            self.is_restored
            and self._restored_state
            and (restored_state := self._restored_state.state)
            not in (
                STATE_UNKNOWN,
                STATE_UNAVAILABLE,
            )
        ):
            return restored_state == STATE_ON
        return None

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
        hm_kwargs = SirenOnArgs()
        if tone := kwargs.get(ATTR_TONE):
            hm_kwargs["acoustic_alarm"] = tone
        if light := kwargs.get(ATTR_LIGHT):
            hm_kwargs["optical_alarm"] = light
        if duration := kwargs.get(ATTR_DURATION):
            hm_kwargs["duration"] = duration
        await self._hm_entity.turn_on(**hm_kwargs)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the device off."""
        await self._hm_entity.turn_off()
