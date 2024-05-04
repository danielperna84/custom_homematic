"""sensor for Homematic(IP) Local."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
import logging
from typing import Any

from hahomematic.const import HmPlatform, ParameterType, SysvarType
from hahomematic.platforms.generic.sensor import HmSensor
from hahomematic.platforms.hub.sensor import HmSysvarSensor

from homeassistant.components.sensor import (
    RestoreSensor,
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import StateType

from . import HomematicConfigEntry
from .const import TOTAL_SYSVAR, HmEntityState
from .control_unit import ControlUnit, signal_new_hm_entity
from .generic_entity import (
    ATTR_VALUE_STATE,
    HaHomematicGenericEntity,
    HaHomematicGenericSysvarEntity,
)
from .support import HmSensorEntityDescription

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: HomematicConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Homematic(IP) Local sensor platform."""
    control_unit: ControlUnit = entry.runtime_data

    @callback
    def async_add_sensor(hm_entities: tuple[HmSensor, ...]) -> None:
        """Add sensor from Homematic(IP) Local."""
        _LOGGER.debug("ASYNC_ADD_SENSOR: Adding %i entities", len(hm_entities))

        if entities := [
            HaHomematicSensor(
                control_unit=control_unit,
                hm_entity=hm_entity,
            )
            for hm_entity in hm_entities
        ]:
            async_add_entities(entities)

    @callback
    def async_add_hub_sensor(hm_entities: tuple[HmSysvarSensor, ...]) -> None:
        """Add sysvar sensor from Homematic(IP) Local."""
        _LOGGER.debug("ASYNC_ADD_HUB_SENSOR: Adding %i entities", len(hm_entities))

        if entities := [
            HaHomematicSysvarSensor(control_unit=control_unit, hm_sysvar_entity=hm_entity)
            for hm_entity in hm_entities
        ]:
            async_add_entities(entities)

    entry.async_on_unload(
        func=async_dispatcher_connect(
            hass=hass,
            signal=signal_new_hm_entity(entry_id=entry.entry_id, platform=HmPlatform.SENSOR),
            target=async_add_sensor,
        )
    )
    entry.async_on_unload(
        func=async_dispatcher_connect(
            hass=hass,
            signal=signal_new_hm_entity(entry_id=entry.entry_id, platform=HmPlatform.HUB_SENSOR),
            target=async_add_hub_sensor,
        )
    )

    async_add_sensor(hm_entities=control_unit.get_new_entities(entity_type=HmSensor))

    async_add_hub_sensor(hm_entities=control_unit.get_new_hub_entities(entity_type=HmSysvarSensor))


class HaHomematicSensor(HaHomematicGenericEntity[HmSensor], RestoreSensor):
    """Representation of the HomematicIP sensor entity."""

    entity_description: HmSensorEntityDescription
    _restored_native_value: Any = None

    def __init__(
        self,
        control_unit: ControlUnit,
        hm_entity: HmSensor,
    ) -> None:
        """Initialize the sensor entity."""
        super().__init__(
            control_unit=control_unit,
            hm_entity=hm_entity,
        )
        self._multiplier: int = (
            self.entity_description.multiplier
            if hasattr(self, "entity_description")
            and self.entity_description
            and self.entity_description.multiplier is not None
            else hm_entity.multiplier
        )
        if not hasattr(self, "entity_description") and hm_entity.unit:
            self._attr_native_unit_of_measurement = hm_entity.unit
        if self.device_class == SensorDeviceClass.ENUM:
            self._attr_options = (
                [item.lower() for item in hm_entity.values] if hm_entity.values else None
            )

    @property
    def native_value(self) -> StateType | date | datetime | Decimal:
        """Return the native value of the entity."""
        if self._hm_entity.is_valid:
            if (
                self._hm_entity.value is not None
                and self._hm_entity.hmtype in (ParameterType.FLOAT, ParameterType.INTEGER)
                and self._multiplier != 1
            ):
                return self._hm_entity.value * self._multiplier  # type: ignore[no-any-return]
            # Strings and enums with custom device class must be lowercase
            # to be translatable.
            if (
                self._hm_entity.value is not None
                and self.translation_key is not None
                and self._hm_entity.hmtype in (ParameterType.ENUM, ParameterType.STRING)
            ):
                return self._hm_entity.value.lower()  # type: ignore[no-any-return]
            return self._hm_entity.value
        if self.is_restored:
            return self._restored_native_value  # type: ignore[no-any-return]
        return None

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
        if not self._hm_entity.is_valid and (
            restored_sensor_data := await self.async_get_last_sensor_data()
        ):
            self._restored_native_value = restored_sensor_data.native_value


class HaHomematicSysvarSensor(HaHomematicGenericSysvarEntity[HmSysvarSensor], SensorEntity):
    """Representation of the HomematicIP hub sensor entity."""

    def __init__(
        self,
        control_unit: ControlUnit,
        hm_sysvar_entity: HmSysvarSensor,
    ) -> None:
        """Initialize the sensor entity."""
        super().__init__(control_unit=control_unit, hm_sysvar_entity=hm_sysvar_entity)
        if hm_sysvar_entity.data_type == SysvarType.LIST:
            self._attr_options = list(hm_sysvar_entity.values) if hm_sysvar_entity.values else None
            self._attr_device_class = SensorDeviceClass.ENUM
        else:
            if hm_sysvar_entity.data_type in (
                SysvarType.FLOAT,
                SysvarType.INTEGER,
            ):
                self._attr_state_class = (
                    SensorStateClass.TOTAL
                    if hm_sysvar_entity.ccu_var_name.startswith(TOTAL_SYSVAR)
                    else SensorStateClass.MEASUREMENT
                )
            if unit := hm_sysvar_entity.unit:
                self._attr_native_unit_of_measurement = unit

    @property
    def native_value(self) -> StateType | date | datetime | Decimal:
        """Return the native value of the entity."""
        return self._hm_hub_entity.value
