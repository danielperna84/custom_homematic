"""select for Homematic(IP) Local."""

from __future__ import annotations

import logging

from hahomematic.const import HmPlatform
from hahomematic.platforms.generic import HmSelect
from hahomematic.platforms.hub import HmSysvarSelect

from homeassistant.components.select import SelectEntity
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
    """Set up the Homematic(IP) Local select platform."""
    control_unit: ControlUnit = entry.runtime_data

    @callback
    def async_add_select(hm_entities: tuple[HmSelect, ...]) -> None:
        """Add select from Homematic(IP) Local."""
        _LOGGER.debug("ASYNC_ADD_SELECT: Adding %i entities", len(hm_entities))

        if entities := [
            HaHomematicSelect(
                control_unit=control_unit,
                hm_entity=hm_entity,
            )
            for hm_entity in hm_entities
        ]:
            async_add_entities(entities)

    @callback
    def async_add_hub_select(hm_entities: tuple[HmSysvarSelect, ...]) -> None:
        """Add sysvar select from Homematic(IP) Local."""
        _LOGGER.debug("ASYNC_ADD_HUB_SELECT: Adding %i entities", len(hm_entities))

        if entities := [
            HaHomematicSysvarSelect(control_unit=control_unit, hm_sysvar_entity=hm_entity)
            for hm_entity in hm_entities
        ]:
            async_add_entities(entities)

    entry.async_on_unload(
        func=async_dispatcher_connect(
            hass=hass,
            signal=signal_new_hm_entity(entry_id=entry.entry_id, platform=HmPlatform.SELECT),
            target=async_add_select,
        )
    )

    entry.async_on_unload(
        func=async_dispatcher_connect(
            hass=hass,
            signal=signal_new_hm_entity(entry_id=entry.entry_id, platform=HmPlatform.HUB_SELECT),
            target=async_add_hub_select,
        )
    )

    async_add_select(hm_entities=control_unit.get_new_entities(entity_type=HmSelect))

    async_add_hub_select(hm_entities=control_unit.get_new_hub_entities(entity_type=HmSysvarSelect))


class HaHomematicSelect(HaHomematicGenericRestoreEntity[HmSelect], SelectEntity):
    """Representation of the HomematicIP select entity."""

    @property
    def options(self) -> list[str]:
        """Return the options."""
        if options := self._hm_entity.values:
            return [option.lower() for option in options]
        return []

    @property
    def current_option(self) -> str | None:
        """Return the currently selected option."""
        if self._hm_entity.is_valid:
            return self._hm_entity.value.lower() if self._hm_entity.value is not None else None
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

    async def async_select_option(self, option: str) -> None:
        """Select an option."""
        await self._hm_entity.send_value(option.upper())


class HaHomematicSysvarSelect(HaHomematicGenericSysvarEntity[HmSysvarSelect], SelectEntity):
    """Representation of the HomematicIP hub select entity."""

    @property
    def options(self) -> list[str]:
        """Return the options."""
        if options := self._hm_hub_entity.values:
            return list(options)
        return []

    @property
    def current_option(self) -> str | None:
        """Return the currently selected option."""
        return self._hm_hub_entity.value

    async def async_select_option(self, option: str) -> None:
        """Select an option."""
        await self._hm_hub_entity.send_variable(option)
