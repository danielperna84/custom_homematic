"""select for Homematic(IP) Local."""
from __future__ import annotations

import logging
from typing import Any

from hahomematic.const import HmPlatform
from hahomematic.generic_platforms.select import HmSelect, HmSysvarSelect

from homeassistant.components.select import SelectEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import STATE_UNAVAILABLE, STATE_UNKNOWN
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import CONTROL_UNITS, DOMAIN
from .control_unit import ControlUnit, async_signal_new_hm_entity
from .generic_entity import (
    HaHomematicGenericRestoreEntity,
    HaHomematicGenericSysvarEntity,
)

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Homematic(IP) Local select platform."""
    control_unit: ControlUnit = hass.data[DOMAIN][CONTROL_UNITS][config_entry.entry_id]

    @callback
    def async_add_select(args: Any) -> None:
        """Add select from Homematic(IP) Local."""
        entities: list[HaHomematicGenericRestoreEntity] = []

        for hm_entity in args:
            entities.append(HaHomematicSelect(control_unit, hm_entity))

        if entities:
            async_add_entities(entities)

    @callback
    def async_add_hub_select(args: Any) -> None:
        """Add sysvar select from Homematic(IP) Local."""

        entities = []

        for hm_entity in args:
            entities.append(HaHomematicSysvarSelect(control_unit, hm_entity))

        if entities:
            async_add_entities(entities)

    config_entry.async_on_unload(
        async_dispatcher_connect(
            hass,
            async_signal_new_hm_entity(config_entry.entry_id, HmPlatform.SELECT),
            async_add_select,
        )
    )

    config_entry.async_on_unload(
        async_dispatcher_connect(
            hass,
            async_signal_new_hm_entity(config_entry.entry_id, HmPlatform.HUB_SELECT),
            async_add_hub_select,
        )
    )

    async_add_select(
        control_unit.async_get_new_hm_entities_by_platform(platform=HmPlatform.SELECT)
    )

    async_add_hub_select(
        control_unit.async_get_new_hm_hub_entities_by_platform(
            platform=HmPlatform.HUB_SELECT
        )
    )


class HaHomematicSelect(HaHomematicGenericRestoreEntity[HmSelect], SelectEntity):
    """Representation of the HomematicIP select entity."""

    _attr_entity_category: EntityCategory | None = EntityCategory.CONFIG

    @property
    def options(self) -> list[str]:
        """Return the options."""
        if options := self._hm_entity.value_list:
            return options
        return []

    @property
    def current_option(self) -> str | None:
        """Return the currently selected option."""
        if self._hm_entity.is_valid:
            return self._hm_entity.value
        if self.is_restored:
            if (restored_state := self._restored_state.state) not in (  # type: ignore[union-attr]
                STATE_UNKNOWN,
                STATE_UNAVAILABLE,
            ):
                return restored_state
        return None

    async def async_select_option(self, option: str) -> None:
        """Select an option."""
        await self._hm_entity.send_value(option)


class HaHomematicSysvarSelect(
    HaHomematicGenericSysvarEntity[HmSysvarSelect], SelectEntity
):
    """Representation of the HomematicIP hub select entity."""

    @property
    def options(self) -> list[str]:
        """Return the options."""
        if options := self._hm_hub_entity.value_list:
            return options
        return []

    @property
    def current_option(self) -> str | None:
        """Return the currently selected option."""
        return self._hm_hub_entity.value

    async def async_select_option(self, option: str) -> None:
        """Select an option."""
        await self._hm_hub_entity.send_variable(option)
