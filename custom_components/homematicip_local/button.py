"""button for Homematic(IP) Local."""
from __future__ import annotations

import logging

from hahomematic.const import HmPlatform
from hahomematic.platforms.generic.button import HmButton
from hahomematic.platforms.hub.button import HmProgramButton

from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import CONTROL_UNITS, DOMAIN
from .control_unit import ControlUnit, signal_new_hm_entity
from .generic_entity import (
    ATTR_NAME,
    HaHomematicGenericEntity,
    HaHomematicGenericHubEntity,
)

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Homematic(IP) Local binary_sensor platform."""
    control_unit: ControlUnit = hass.data[DOMAIN][CONTROL_UNITS][entry.entry_id]

    @callback
    def async_add_button(hm_entities: tuple[HmButton, ...]) -> None:
        """Add button from Homematic(IP) Local."""
        _LOGGER.debug("ASYNC_ADD_BUTTON: Adding %i entities", len(hm_entities))
        entities: list[HaHomematicButton] = []

        for hm_entity in hm_entities:
            entities.append(
                HaHomematicButton(
                    control_unit=control_unit,
                    hm_entity=hm_entity,
                )
            )

        if entities:
            async_add_entities(entities)

    @callback
    def async_add_program_button(hm_entities: tuple[HmProgramButton, ...]) -> None:
        """Add program button from Homematic(IP) Local."""
        _LOGGER.debug("ASYNC_ADD_PROGRAM_BUTTON: Adding %i entities", len(hm_entities))
        entities: list[HaHomematicProgramButton] = []

        for hm_entity in hm_entities:
            entities.append(
                HaHomematicProgramButton(control_unit=control_unit, hm_program_button=hm_entity)
            )

        if entities:
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

    async_add_button(
        hm_entities=control_unit.central.get_entities(
            platform=HmPlatform.BUTTON,
            registered=False,
        )
    )

    async_add_program_button(
        hm_entities=control_unit.central.get_hub_entities(
            platform=HmPlatform.HUB_BUTTON, registered=False
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
        self._attr_extra_state_attributes = {ATTR_NAME: self._hm_hub_entity.ccu_program_name}

    async def async_press(self) -> None:
        """Execute a button press."""
        await self._hm_hub_entity.press()
