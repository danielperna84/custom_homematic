"""binary_sensor for Homematic(IP) Local."""
from __future__ import annotations

import logging
from typing import Any, TypeVar

from hahomematic.const import HmPlatform
from hahomematic.platforms.custom.cover import CeBlind, CeCover, CeGarage, CeIpBlind

from homeassistant.components.cover import (
    ATTR_CURRENT_POSITION,
    ATTR_CURRENT_TILT_POSITION,
    ATTR_POSITION,
    ATTR_TILT_POSITION,
    CoverEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import STATE_CLOSED, STATE_UNAVAILABLE, STATE_UNKNOWN
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import CONTROL_UNITS, DOMAIN
from .control_unit import ControlUnit, async_signal_new_hm_entity
from .generic_entity import HaHomematicGenericRestoreEntity

_LOGGER = logging.getLogger(__name__)

HmBaseCoverEntity = CeCover | CeGarage
HmGenericCover = TypeVar("HmGenericCover", bound=HmBaseCoverEntity)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Homematic(IP) Local cover platform."""
    control_unit: ControlUnit = hass.data[DOMAIN][CONTROL_UNITS][config_entry.entry_id]

    @callback
    def async_add_cover(args: Any) -> None:
        """Add cover from Homematic(IP) Local."""
        entities: list[HaHomematicGenericRestoreEntity] = []

        for hm_entity in args:
            if isinstance(hm_entity, CeIpBlind):
                if (
                    hm_entity.channel_operation_mode
                    and hm_entity.channel_operation_mode == "SHUTTER"
                ):
                    entities.append(HaHomematicCover(control_unit, hm_entity))
                else:
                    entities.append(HaHomematicBlind(control_unit, hm_entity))
            elif isinstance(hm_entity, CeBlind):
                entities.append(HaHomematicBlind(control_unit, hm_entity))
            elif isinstance(hm_entity, CeCover):
                entities.append(HaHomematicCover(control_unit, hm_entity))
            elif isinstance(hm_entity, CeGarage):
                entities.append(HaHomematicGarage(control_unit, hm_entity))

        if entities:
            async_add_entities(entities)

    config_entry.async_on_unload(
        async_dispatcher_connect(
            hass,
            async_signal_new_hm_entity(config_entry.entry_id, HmPlatform.COVER),
            async_add_cover,
        )
    )

    async_add_cover(
        control_unit.async_get_new_hm_entities_by_platform(platform=HmPlatform.COVER)
    )


class HaHomematicBaseCover(
    HaHomematicGenericRestoreEntity[HmGenericCover], CoverEntity
):
    """Representation of the HomematicIP cover entity."""

    @property
    def current_cover_position(self) -> int | None:
        """Return current position of cover."""
        if self._hm_entity.is_valid:
            return self._hm_entity.current_position
        if self.is_restored and self._restored_state:
            return self._restored_state.attributes.get(ATTR_CURRENT_POSITION)
        return None

    @property
    def is_closed(self) -> bool | None:
        """Return if the cover is closed."""
        if self._hm_entity.is_valid:
            return self._hm_entity.is_closed
        if (
            self.is_restored
            and self._restored_state
            and (restored_state := self._restored_state.state)
            not in (
                STATE_UNKNOWN,
                STATE_UNAVAILABLE,
            )
        ):
            return restored_state == STATE_CLOSED
        return None

    @property
    def is_opening(self) -> bool | None:
        """Return if the cover is opening."""
        return self._hm_entity.is_opening

    @property
    def is_closing(self) -> bool | None:
        """Return if the cover is closing."""
        return self._hm_entity.is_closing

    async def async_set_cover_position(self, **kwargs: Any) -> None:
        """Move the cover to a specific position."""
        # Hm cover is closed:1 -> open:0
        if ATTR_POSITION in kwargs:
            position = float(kwargs[ATTR_POSITION])
            await self._hm_entity.set_position(position=position)

    async def async_open_cover(self, **kwargs: Any) -> None:
        """Open the cover."""
        await self._hm_entity.open()

    async def async_close_cover(self, **kwargs: Any) -> None:
        """Close the cover."""
        await self._hm_entity.close()

    async def async_stop_cover(self, **kwargs: Any) -> None:
        """Stop the device if in motion."""
        await self._hm_entity.stop()


class HaHomematicCover(HaHomematicBaseCover[CeCover]):
    """Representation of the HomematicIP cover entity."""


class HaHomematicBlind(HaHomematicBaseCover[CeBlind | CeIpBlind]):
    """Representation of the HomematicIP blind entity."""

    @property
    def current_cover_tilt_position(self) -> int | None:
        """Return current tilt position of cover."""
        if self._hm_entity.is_valid:
            return self._hm_entity.current_tilt_position
        if self.is_restored and self._restored_state:
            return self._restored_state.attributes.get(ATTR_CURRENT_TILT_POSITION)
        return None

    async def async_set_cover_tilt_position(self, **kwargs: Any) -> None:
        """Move the cover to a specific tilt position."""
        if ATTR_TILT_POSITION in kwargs:
            tilt_position = float(kwargs[ATTR_TILT_POSITION])
            await self._hm_entity.set_tilt_position(tilt_position=tilt_position)

    async def async_open_cover_tilt(self, **kwargs: Any) -> None:
        """Open the tilt."""
        await self._hm_entity.open_tilt()

    async def async_close_cover_tilt(self, **kwargs: Any) -> None:
        """Close the tilt."""
        await self._hm_entity.close_tilt()

    async def async_stop_cover_tilt(self, **kwargs: Any) -> None:
        """Stop the device if in motion."""
        await self._hm_entity.stop_tilt()


class HaHomematicGarage(HaHomematicBaseCover[CeGarage]):
    """Representation of the HomematicIP garage entity."""
