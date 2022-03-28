"""binary_sensor for Homematic(IP) Local."""
from __future__ import annotations

import logging
from typing import Any

from hahomematic.const import HmPlatform
from hahomematic.platforms.number import BaseNumber

from homeassistant.components.number import NumberEntity, NumberMode
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .control_unit import ControlUnit
from .generic_entity import HaHomematicGenericEntity
from .helpers import HmNumberEntityDescription

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Homematic(IP) Local number platform."""
    control_unit: ControlUnit = hass.data[DOMAIN][config_entry.entry_id]

    @callback
    def async_add_number(args: Any) -> None:
        """Add number from Homematic(IP) Local."""
        entities: list[HaHomematicGenericEntity] = []

        for hm_entity in args:
            entities.append(HaHomematicNumber(control_unit, hm_entity))

        if entities:
            async_add_entities(entities)

    config_entry.async_on_unload(
        async_dispatcher_connect(
            hass,
            control_unit.async_signal_new_hm_entity(
                config_entry.entry_id, HmPlatform.NUMBER
            ),
            async_add_number,
        )
    )

    async_add_number(
        control_unit.async_get_new_hm_entities_by_platform(HmPlatform.NUMBER)
    )


class HaHomematicNumber(HaHomematicGenericEntity[BaseNumber], NumberEntity):
    """Representation of the HomematicIP number entity."""

    entity_description: HmNumberEntityDescription
    _attr_entity_category = EntityCategory.CONFIG
    _attr_mode = NumberMode.BOX

    def __init__(
        self,
        control_unit: ControlUnit,
        hm_entity: BaseNumber,
    ) -> None:
        """Initialize the number entity."""
        super().__init__(control_unit=control_unit, hm_entity=hm_entity)
        self._multiplier: int = (
            self.entity_description.multiplier
            if hasattr(self, "entity_description")
            and self.entity_description
            and self.entity_description.multiplier is not None
            else hm_entity.multiplier
        )
        self._attr_min_value = hm_entity.min * self._multiplier
        self._attr_max_value = hm_entity.max * self._multiplier
        self._attr_step = (
            1.0 if hm_entity.hmtype == "INTEGER" else 0.01 * self._multiplier
        )
        if not hasattr(self, "entity_description") and hm_entity.unit:
            self._attr_unit_of_measurement = hm_entity.unit

    @property
    def value(self) -> float | None:
        """Return the current value."""
        if self._hm_entity.value is not None:
            return float(self._hm_entity.value * self._multiplier)
        return None

    async def async_set_value(self, value: float) -> None:
        """Update the current value."""
        await self._hm_entity.send_value(value / self._multiplier)
