"""button for Homematic(IP) Local."""
from __future__ import annotations

import logging
from typing import Any

from hahomematic.const import HmPlatform
from hahomematic.generic_platforms.button import HmButton, HmProgramButton

from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import ATTR_NAME, CONTROL_UNITS, DOMAIN
from .control_unit import ControlUnit, async_signal_new_hm_entity
from .generic_entity import HaHomematicGenericEntity, HaHomematicGenericHubEntity

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Homematic(IP) Local binary_sensor platform."""
    control_unit: ControlUnit = hass.data[DOMAIN][CONTROL_UNITS][config_entry.entry_id]

    @callback
    def async_add_button(args: Any) -> None:
        """Add button from Homematic(IP) Local."""
        entities: list[HaHomematicGenericEntity] = []

        for hm_entity in args:
            entities.append(HaHomematicButton(control_unit, hm_entity))

        if entities:
            async_add_entities(entities)

    @callback
    def async_add_program_button(args: Any) -> None:
        """Add program button from Homematic(IP) Local."""
        entities: list[HaHomematicProgramButton] = []

        for hm_entity in args:
            entities.append(HaHomematicProgramButton(control_unit, hm_entity))

        if entities:
            async_add_entities(entities)

    config_entry.async_on_unload(
        async_dispatcher_connect(
            hass,
            async_signal_new_hm_entity(config_entry.entry_id, HmPlatform.BUTTON),
            async_add_button,
        )
    )

    config_entry.async_on_unload(
        async_dispatcher_connect(
            hass,
            async_signal_new_hm_entity(config_entry.entry_id, HmPlatform.HUB_BUTTON),
            async_add_program_button,
        )
    )

    async_add_button(
        control_unit.async_get_new_hm_entities_by_platform(platform=HmPlatform.BUTTON)
    )

    async_add_program_button(
        control_unit.async_get_new_hm_hub_entities_by_platform(
            platform=HmPlatform.HUB_BUTTON
        )
    )


class HaHomematicButton(HaHomematicGenericEntity[HmButton], ButtonEntity):
    """Representation of the Homematic(IP) Local button."""

    async def async_press(self) -> None:
        """Execute a button press."""
        await self._hm_entity.press()


class HaHomematicProgramButton(HaHomematicGenericHubEntity, ButtonEntity):
    """Representation of the Homematic(IP) Local button."""

    def __init__(
        self,
        control_unit: ControlUnit,
        hm_program_button: HmProgramButton,
    ) -> None:
        """Initialize the button entity."""
        super().__init__(
            control_unit=control_unit,
            hm_hub_entity=hm_program_button,
        )
        self._hm_hub_entity: HmProgramButton = hm_program_button

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return the state attributes of the program button entity."""
        return {ATTR_NAME: self._hm_hub_entity.ccu_program_name}

    async def async_press(self) -> None:
        """Execute a button press."""
        await self._hm_hub_entity.press()
