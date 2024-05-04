"""text for Homematic(IP) Local."""

from __future__ import annotations

import logging

from hahomematic.const import HmPlatform
from hahomematic.platforms.generic.text import HmText
from hahomematic.platforms.hub.text import HmSysvarText

from homeassistant.components.text import TextEntity
from homeassistant.const import STATE_UNAVAILABLE, STATE_UNKNOWN
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import HomematicConfigEntry
from .control_unit import ControlUnit, signal_new_hm_entity
from .generic_entity import HaHomematicGenericRestoreEntity, HaHomematicGenericSysvarEntity

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: HomematicConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Homematic(IP) Local text platform."""
    control_unit: ControlUnit = entry.runtime_data

    @callback
    def async_add_text(hm_entities: tuple[HmText, ...]) -> None:
        """Add text from Homematic(IP) Local."""
        _LOGGER.debug("ASYNC_ADD_TEXT: Adding %i entities", len(hm_entities))

        if entities := [
            HaHomematicText(
                control_unit=control_unit,
                hm_entity=hm_entity,
            )
            for hm_entity in hm_entities
        ]:
            async_add_entities(entities)

    @callback
    def async_add_hub_text(hm_entities: tuple[HmSysvarText, ...]) -> None:
        """Add sysvar text from Homematic(IP) Local."""
        _LOGGER.debug("ASYNC_ADD_HUB_TEXT: Adding %i entities", len(hm_entities))

        if entities := [
            HaHomematicSysvarText(control_unit=control_unit, hm_sysvar_entity=hm_entity)
            for hm_entity in hm_entities
        ]:
            async_add_entities(entities)

    entry.async_on_unload(
        func=async_dispatcher_connect(
            hass=hass,
            signal=signal_new_hm_entity(entry_id=entry.entry_id, platform=HmPlatform.TEXT),
            target=async_add_text,
        )
    )
    entry.async_on_unload(
        func=async_dispatcher_connect(
            hass=hass,
            signal=signal_new_hm_entity(entry_id=entry.entry_id, platform=HmPlatform.HUB_TEXT),
            target=async_add_hub_text,
        )
    )

    async_add_text(hm_entities=control_unit.get_new_entities(entity_type=HmText))

    async_add_hub_text(hm_entities=control_unit.get_new_hub_entities(entity_type=HmSysvarText))


class HaHomematicText(HaHomematicGenericRestoreEntity[HmText], TextEntity):
    """Representation of the HomematicIP text entity."""

    @property
    def native_value(self) -> str | None:
        """Return the value reported by the text."""
        if self._hm_entity.is_valid:
            return self._hm_entity.value
        if (
            self.is_restored
            and self._restored_state
            and (restored_state := self._restored_state.state)
            not in (
                STATE_UNKNOWN,
                STATE_UNAVAILABLE,
            )
        ):
            return restored_state
        return None

    async def async_set_value(self, value: str) -> None:
        """Send the text."""
        await self._hm_entity.send_value(value=value)


class HaHomematicSysvarText(HaHomematicGenericSysvarEntity[HmSysvarText], TextEntity):
    """Representation of the HomematicIP hub text entity."""

    @property
    def native_value(self) -> str | None:
        """Return the value reported by the text."""
        return self._hm_hub_entity.value

    async def async_set_value(self, value: str) -> None:
        """Send the text."""
        await self._hm_hub_entity.send_variable(value=value)
