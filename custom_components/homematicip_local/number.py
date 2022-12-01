"""number for Homematic(IP) Local."""
from __future__ import annotations

import logging
from typing import Any

from hahomematic.const import HmPlatform
from hahomematic.generic_platforms.number import BaseNumber, HmSysvarNumber

from homeassistant.components.number import NumberEntity, NumberMode, RestoreNumber
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import ATTR_VALUE_STATE, CONTROL_UNITS, DOMAIN, HmEntityState
from .control_unit import ControlUnit, async_signal_new_hm_entity
from .generic_entity import HaHomematicGenericEntity, HaHomematicGenericSysvarEntity
from .helpers import HmNumberEntityDescription

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Homematic(IP) Local number platform."""
    control_unit: ControlUnit = hass.data[DOMAIN][CONTROL_UNITS][config_entry.entry_id]

    @callback
    def async_add_number(args: Any) -> None:
        """Add number from Homematic(IP) Local."""
        entities: list[HaHomematicGenericEntity] = []

        for hm_entity in args:
            entities.append(HaHomematicNumber(control_unit, hm_entity))

        if entities:
            async_add_entities(entities)

    @callback
    def async_add_hub_number(args: Any) -> None:
        """Add sysvar number from Homematic(IP) Local."""

        entities = []

        for hm_entity in args:
            entities.append(HaHomematicSysvarNumber(control_unit, hm_entity))

        if entities:
            async_add_entities(entities)

    config_entry.async_on_unload(
        async_dispatcher_connect(
            hass,
            async_signal_new_hm_entity(config_entry.entry_id, HmPlatform.NUMBER),
            async_add_number,
        )
    )

    config_entry.async_on_unload(
        async_dispatcher_connect(
            hass,
            async_signal_new_hm_entity(config_entry.entry_id, HmPlatform.HUB_NUMBER),
            async_add_hub_number,
        )
    )

    async_add_number(
        control_unit.async_get_new_hm_entities_by_platform(platform=HmPlatform.NUMBER)
    )

    async_add_hub_number(
        control_unit.async_get_new_hm_hub_entities_by_platform(
            platform=HmPlatform.HUB_NUMBER
        )
    )


class HaHomematicNumber(HaHomematicGenericEntity[BaseNumber], RestoreNumber):
    """Representation of the HomematicIP number entity."""

    entity_description: HmNumberEntityDescription
    _attr_entity_category = EntityCategory.CONFIG
    _attr_mode = NumberMode.BOX
    _restored_native_value: float | None = None

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
        self._attr_native_min_value = hm_entity.min * self._multiplier
        self._attr_native_max_value = hm_entity.max * self._multiplier
        self._attr_native_step = (
            1.0 if hm_entity.hmtype == "INTEGER" else 0.01 * self._multiplier
        )
        if not hasattr(self, "entity_description") and hm_entity.unit:
            self._attr_native_unit_of_measurement = hm_entity.unit

    @property
    def native_value(self) -> float | None:
        """Return the current value."""
        if self._hm_entity.is_valid and self._hm_entity.value is not None:
            return float(self._hm_entity.value * self._multiplier)
        if self.is_restored:
            return self._restored_native_value
        return None

    async def async_set_native_value(self, value: float) -> None:
        """Update the current value."""
        await self._hm_entity.send_value(value / self._multiplier)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return the state attributes of the generic entity."""
        attributes = super().extra_state_attributes
        if self.is_restored:
            attributes[ATTR_VALUE_STATE] = HmEntityState.RESTORED
        return attributes

    @property
    def is_restored(self) -> bool:
        """Return if the state is restored."""
        return not self._hm_entity.is_valid and self._restored_native_value is not None

    async def async_added_to_hass(self) -> None:
        """Check, if state needs to be restored."""
        await super().async_added_to_hass()
        if not self._hm_entity.is_valid:
            if restored_sensor_data := await self.async_get_last_number_data():
                self._restored_native_value = restored_sensor_data.native_value


class HaHomematicSysvarNumber(
    HaHomematicGenericSysvarEntity[HmSysvarNumber], NumberEntity
):
    """Representation of the HomematicIP hub number entity."""

    _attr_mode = NumberMode.BOX

    def __init__(
        self,
        control_unit: ControlUnit,
        hm_sysvar_entity: HmSysvarNumber,
    ) -> None:
        """Initialize the number entity."""
        super().__init__(control_unit=control_unit, hm_sysvar_entity=hm_sysvar_entity)
        if hm_sysvar_entity.min:
            self._attr_native_min_value = float(hm_sysvar_entity.min)
        if hm_sysvar_entity.max:
            self._attr_native_max_value = float(hm_sysvar_entity.max)
        if hm_sysvar_entity.unit:
            self._attr_native_unit_of_measurement = hm_sysvar_entity.unit

    @property
    def native_value(self) -> float | None:
        """Return the current value."""
        if self._hm_hub_entity.value:
            return float(self._hm_hub_entity.value)
        return None

    async def async_set_native_value(self, value: float) -> None:
        """Update the current value."""
        await self._hm_hub_entity.send_variable(value)
