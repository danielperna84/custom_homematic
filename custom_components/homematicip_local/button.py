"""button for Homematic(IP) Local."""

from __future__ import annotations

import logging

from hahomematic.const import HmPlatform
from hahomematic.platforms.generic import HmButton
from hahomematic.platforms.hub import HmProgramButton

from homeassistant.components.button import ButtonEntity
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import HomematicConfigEntry
from .control_unit import ControlUnit, signal_new_hm_entity
from .generic_entity import ATTR_NAME, HaHomematicGenericEntity, HaHomematicGenericHubEntity

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: HomematicConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Homematic(IP) Local binary_sensor platform."""
    control_unit: ControlUnit = entry.runtime_data

    @callback
    def async_add_button(hm_entities: tuple[HmButton, ...]) -> None:
        """Add button from Homematic(IP) Local."""
        _LOGGER.debug("ASYNC_ADD_BUTTON: Adding %i entities", len(hm_entities))

        if entities := [
            HaHomematicButton(
                control_unit=control_unit,
                hm_entity=hm_entity,
            )
            for hm_entity in hm_entities
        ]:
            async_add_entities(entities)

    @callback
    def async_add_program_button(hm_entities: tuple[HmProgramButton, ...]) -> None:
        """Add program button from Homematic(IP) Local."""
        _LOGGER.debug("ASYNC_ADD_PROGRAM_BUTTON: Adding %i entities", len(hm_entities))

        if entities := [
            HaHomematicProgramButton(control_unit=control_unit, hm_program_button=hm_entity)
            for hm_entity in hm_entities
        ]:
            async_add_entities(entities)

    entry.async_on_unload(
        func=async_dispatcher_connect(
            hass=hass,
            signal=signal_new_hm_entity(entry_id=entry.entry_id, platform=HmPlatform.BUTTON),
            target=async_add_button,
        )
    )

    entry.async_on_unload(
        func=async_dispatcher_connect(
            hass=hass,
            signal=signal_new_hm_entity(entry_id=entry.entry_id, platform=HmPlatform.HUB_BUTTON),
            target=async_add_program_button,
        )
    )

    async_add_button(hm_entities=control_unit.get_new_entities(entity_type=HmButton))

    async_add_program_button(
        hm_entities=control_unit.get_new_hub_entities(entity_type=HmProgramButton)
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
        self._attr_extra_state_attributes = {ATTR_NAME: self._hm_hub_entity.ccu_program_name}

    async def async_press(self) -> None:
        """Execute a button press."""
        await self._hm_hub_entity.press()
