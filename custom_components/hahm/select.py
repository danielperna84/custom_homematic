"""binary_sensor for Homematic(IP) Local."""
from __future__ import annotations

import logging
from typing import Any

from hahomematic.const import HmPlatform
from hahomematic.platforms.select import HmSelect

from homeassistant.components.select import SelectEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity import EntityCategory
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
    """Set up the Homematic(IP) Local select platform."""
    control_unit: ControlUnit = hass.data[DOMAIN][config_entry.entry_id]

    @callback
    def async_add_select(args: Any) -> None:
        """Add select from Homematic(IP) Local."""
        entities: list[HaHomematicGenericEntity] = []

        for hm_entity in args:
            entities.append(HaHomematicSelect(control_unit, hm_entity))

        if entities:
            async_add_entities(entities)

    config_entry.async_on_unload(
        async_dispatcher_connect(
            hass,
            control_unit.async_signal_new_hm_entity(
                config_entry.entry_id, HmPlatform.SELECT
            ),
            async_add_select,
        )
    )

    async_add_select(
        control_unit.async_get_new_hm_entities_by_platform(HmPlatform.SELECT)
    )


class HaHomematicSelect(HaHomematicGenericEntity[HmSelect], SelectEntity):
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
        return self._hm_entity.value

    async def async_select_option(self, option: str) -> None:
        """Select an option."""
        await self._hm_entity.send_value(option)
