"""sensor for Homematic(IP) Local."""
from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
import logging
from typing import Any

from hahomematic.const import (
    TYPE_ENUM,
    TYPE_FLOAT,
    TYPE_INTEGER,
    TYPE_STRING,
    HmPlatform,
)
from hahomematic.generic_platforms.sensor import HmSensor, HmSysvarSensor

from homeassistant.components.sensor import RestoreSensor, SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import StateType

from .const import (
    ATTR_VALUE_LIST,
    ATTR_VALUE_STATE,
    CONTROL_UNITS,
    DOMAIN,
    HmEntityState,
)
from .control_unit import ControlUnit, async_signal_new_hm_entity
from .generic_entity import HaHomematicGenericEntity, HaHomematicGenericSysvarEntity
from .helpers import HmSensorEntityDescription

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Homematic(IP) Local sensor platform."""
    control_unit: ControlUnit = hass.data[DOMAIN][CONTROL_UNITS][config_entry.entry_id]

    @callback
    def async_add_sensor(args: Any) -> None:
        """Add sensor from Homematic(IP) Local."""
        entities: list[HaHomematicGenericEntity] = []

        for hm_entity in args:
            entities.append(HaHomematicSensor(control_unit, hm_entity))

        if entities:
            async_add_entities(entities)

    @callback
    def async_add_hub_sensor(args: Any) -> None:
        """Add sysvar sensor from Homematic(IP) Local."""

        entities = []

        for hm_entity in args:
            entities.append(HaHomematicSysvarSensor(control_unit, hm_entity))

        if entities:
            async_add_entities(entities)

    config_entry.async_on_unload(
        async_dispatcher_connect(
            hass,
            async_signal_new_hm_entity(config_entry.entry_id, HmPlatform.SENSOR),
            async_add_sensor,
        )
    )
    config_entry.async_on_unload(
        async_dispatcher_connect(
            hass,
            async_signal_new_hm_entity(config_entry.entry_id, HmPlatform.HUB_SENSOR),
            async_add_hub_sensor,
        )
    )

    async_add_sensor(
        control_unit.async_get_new_hm_entities_by_platform(platform=HmPlatform.SENSOR)
    )

    async_add_hub_sensor(
        control_unit.async_get_new_hm_hub_entities_by_platform(
            platform=HmPlatform.HUB_SENSOR
        )
    )


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
        super().__init__(control_unit=control_unit, hm_entity=hm_entity)
        self._multiplier: int = (
            self.entity_description.multiplier
            if hasattr(self, "entity_description")
            and self.entity_description
            and self.entity_description.multiplier is not None
            else hm_entity.multiplier
        )
        if not hasattr(self, "entity_description") and hm_entity.unit:
            self._attr_native_unit_of_measurement = hm_entity.unit

    @property
    def native_value(self) -> StateType | date | datetime | Decimal:
        """Return the native value of the entity."""
        if self._hm_entity.is_valid:
            if (
                self._hm_entity.value is not None
                and self._hm_entity.hmtype in (TYPE_FLOAT, TYPE_INTEGER)
                and self._multiplier != 1
            ):
                return self._hm_entity.value * self._multiplier
            # Strings and enums with custom device class must be lowercase to be translatable.
            if (
                self._hm_entity.value is not None
                and self.device_class is not None
                and self._hm_entity.hmtype in (TYPE_ENUM, TYPE_STRING)
                and self.device_class.startswith(DOMAIN.lower())
            ):
                return self._hm_entity.value.lower()
            return self._hm_entity.value
        if self.is_restored:
            return self._restored_native_value
        return None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return the state attributes of the generic entity."""
        attributes = super().extra_state_attributes
        if self.is_restored:
            attributes[ATTR_VALUE_STATE] = HmEntityState.RESTORED
        if self._hm_entity.value_list:
            attributes[ATTR_VALUE_LIST] = [
                item.lower() for item in self._hm_entity.value_list
            ]
        return attributes

    @property
    def icon(self) -> str | None:
        """Return the icon to use in the frontend, if any."""
        if self.entity_description.icon_fn:
            return self.entity_description.icon_fn(self.native_value)
        return super().icon

    @property
    def is_restored(self) -> bool:
        """Return if the state is restored."""
        return not self._hm_entity.is_valid and self._restored_native_value is not None

    async def async_added_to_hass(self) -> None:
        """Check, if state needs to be restored."""
        await super().async_added_to_hass()
        if not self._hm_entity.is_valid:
            if restored_sensor_data := await self.async_get_last_sensor_data():
                self._restored_native_value = restored_sensor_data.native_value


class HaHomematicSysvarSensor(
    HaHomematicGenericSysvarEntity[HmSysvarSensor], SensorEntity
):
    """Representation of the HomematicIP hub sensor entity."""

    def __init__(
        self,
        control_unit: ControlUnit,
        hm_sysvar_entity: HmSysvarSensor,
    ) -> None:
        """Initialize the sensor entity."""
        super().__init__(control_unit=control_unit, hm_sysvar_entity=hm_sysvar_entity)
        self._attr_native_unit_of_measurement = hm_sysvar_entity.unit

    @property
    def native_value(self) -> StateType | date | datetime | Decimal:
        """Return the native value of the entity."""
        return self._hm_hub_entity.value
