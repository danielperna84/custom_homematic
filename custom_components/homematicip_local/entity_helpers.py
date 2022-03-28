"""Support for HomeMatic sensors."""
from __future__ import annotations

import logging
from typing import Any

from hahomematic.const import HmPlatform
from hahomematic.entity import CustomEntity, GenericEntity

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntityDescription,
)
from homeassistant.components.button import ButtonEntityDescription
from homeassistant.components.cover import CoverDeviceClass, CoverEntityDescription
from homeassistant.components.sensor import SensorDeviceClass, SensorStateClass
from homeassistant.components.switch import SwitchDeviceClass, SwitchEntityDescription
from homeassistant.const import (
    CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
    CONCENTRATION_PARTS_PER_MILLION,
    DEGREE,
    ELECTRIC_CURRENT_MILLIAMPERE,
    ELECTRIC_POTENTIAL_VOLT,
    ENERGY_KILO_WATT_HOUR,
    ENERGY_WATT_HOUR,
    FREQUENCY_HERTZ,
    LENGTH_MILLIMETERS,
    LIGHT_LUX,
    PERCENTAGE,
    POWER_WATT,
    PRESSURE_HPA,
    SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
    SPEED_KILOMETERS_PER_HOUR,
    TEMP_CELSIUS,
    TIME_MINUTES,
    VOLUME_CUBIC_METERS,
)
from homeassistant.helpers.entity import EntityCategory, EntityDescription

from .helpers import (
    HmGenericEntity,
    HmNumberEntityDescription,
    HmSensorEntityDescription,
)

_LOGGER = logging.getLogger(__name__)

CONCENTRATION_CM3 = "1/cm\u00b3"
PARTICLESIZE = "\u00b5m"
VAPOR_CONCENTRATION = "g/m³"


_BUTTON_DESCRIPTIONS_BY_PARAM: dict[str | frozenset[str], ButtonEntityDescription] = {}

_NUMBER_DESCRIPTIONS_BY_PARAM: dict[str | frozenset[str], HmNumberEntityDescription] = {
    "FREQUENCY": HmNumberEntityDescription(
        key="FREQUENCY",
        unit_of_measurement=FREQUENCY_HERTZ,
    ),
    frozenset({"LEVEL", "LEVEL_SLATS"}): HmNumberEntityDescription(
        key="LEVEL",
        unit_of_measurement=PERCENTAGE,
    ),
}

_NUMBER_DESCRIPTIONS_DEVICE_BY_PARAM: dict[
    tuple[str | frozenset[str], str], HmNumberEntityDescription
] = {
    (
        frozenset({"TRV", "TRV-B", "TRV-C", "TRV-E", "HmIP-HEATING"}),
        "LEVEL",
    ): HmNumberEntityDescription(
        key="LEVEL",
        icon="mdi:pipe-valve",
        unit_of_measurement=PERCENTAGE,
        multiplier=100,
    ),
}

_SENSOR_DESCRIPTIONS_BY_PARAM: dict[str | frozenset[str], HmSensorEntityDescription] = {
    "AIR_PRESSURE": HmSensorEntityDescription(
        key="AIR_PRESSURE",
        native_unit_of_measurement=PRESSURE_HPA,
        device_class=SensorDeviceClass.PRESSURE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    "BRIGHTNESS": HmSensorEntityDescription(
        key="BRIGHTNESS",
        native_unit_of_measurement="#",
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:invert-colors",
    ),
    "CARRIER_SENSE_LEVEL": HmSensorEntityDescription(
        key="CARRIER_SENSE_LEVEL",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    "CONCENTRATION": HmSensorEntityDescription(
        key="CONCENTRATION",
        native_unit_of_measurement=CONCENTRATION_PARTS_PER_MILLION,
        device_class=SensorDeviceClass.CO2,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    "CURRENT": HmSensorEntityDescription(
        key="CURRENT",
        native_unit_of_measurement=ELECTRIC_CURRENT_MILLIAMPERE,
        device_class=SensorDeviceClass.CURRENT,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    frozenset({"ACTIVITY_STATE", "DIRECTION"}): HmSensorEntityDescription(
        key="DIRECTION",
        icon="mdi:arrow-up-down",
        device_class="hmip_local__direction",
    ),
    "DOOR_STATE": HmSensorEntityDescription(
        key="DOOR_STATE",
        icon="mdi:arrow-up-down",
        device_class="hmip_local__door_state",
    ),
    "DUTY_CYCLE_LEVEL": HmSensorEntityDescription(
        key="DUTY_CYCLE_LEVEL",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    "ENERGY_COUNTER": HmSensorEntityDescription(
        key="ENERGY_COUNTER",
        native_unit_of_measurement=ENERGY_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    "FREQUENCY": HmSensorEntityDescription(
        key="FREQUENCY",
        native_unit_of_measurement=FREQUENCY_HERTZ,
        device_class=SensorDeviceClass.FREQUENCY,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    "GAS_ENERGY_COUNTER": HmSensorEntityDescription(
        key="GAS_ENERGY_COUNTER",
        native_unit_of_measurement=VOLUME_CUBIC_METERS,
        device_class=SensorDeviceClass.GAS,
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    "GAS_POWER": HmSensorEntityDescription(
        key="GAS_POWER",
        native_unit_of_measurement=VOLUME_CUBIC_METERS,
        device_class=SensorDeviceClass.GAS,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    frozenset(["HUMIDITY", "ACTUAL_HUMIDITY"]): HmSensorEntityDescription(
        key="HUMIDITY",
        native_unit_of_measurement=PERCENTAGE,
        device_class=SensorDeviceClass.HUMIDITY,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    "IEC_ENERGY_COUNTER": HmSensorEntityDescription(
        key="IEC_ENERGY_COUNTER",
        native_unit_of_measurement=ENERGY_KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    "IEC_POWER": HmSensorEntityDescription(
        key="IEC_POWER",
        native_unit_of_measurement=POWER_WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    frozenset(
        {
            "ILLUMINATION",
            "AVERAGE_ILLUMINATION",
            "CURRENT_ILLUMINATION",
            "HIGHEST_ILLUMINATION",
            "LOWEST_ILLUMINATION",
            "LUX",
        }
    ): HmSensorEntityDescription(
        key="ILLUMINATION",
        native_unit_of_measurement=LIGHT_LUX,
        device_class=SensorDeviceClass.ILLUMINANCE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    "IP_ADDRESS": HmSensorEntityDescription(
        key="IP_ADDRESS",
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    frozenset(["LEVEL", "FILLING_LEVEL"]): HmSensorEntityDescription(
        key="LEVEL",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    "LOCK_STATE": HmSensorEntityDescription(
        key="LOCK_STATE",
        icon="mdi:lock",
        device_class="hmip_local__lock_state",
    ),
    frozenset(
        {"MASS_CONCENTRATION_PM_1", "MASS_CONCENTRATION_PM_1_24H_AVERAGE"}
    ): HmSensorEntityDescription(
        key="MASS_CONCENTRATION_PM_1",
        native_unit_of_measurement=CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
        device_class=SensorDeviceClass.PM1,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    frozenset(
        {"MASS_CONCENTRATION_PM_10", "MASS_CONCENTRATION_PM_10_24H_AVERAGE"}
    ): HmSensorEntityDescription(
        key="MASS_CONCENTRATION_PM_10",
        native_unit_of_measurement=CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
        device_class=SensorDeviceClass.PM10,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    frozenset(
        {"MASS_CONCENTRATION_PM_2_5", "MASS_CONCENTRATION_PM_2_5_24H_AVERAGE"}
    ): HmSensorEntityDescription(
        key="MASS_CONCENTRATION_PM_2_5",
        native_unit_of_measurement=CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
        device_class=SensorDeviceClass.PM25,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    "NUMBER_CONCENTRATION_PM_1": HmSensorEntityDescription(
        key="NUMBER_CONCENTRATION_PM_1",
        native_unit_of_measurement=CONCENTRATION_CM3,
        device_class=SensorDeviceClass.PM1,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    "NUMBER_CONCENTRATION_PM_10": HmSensorEntityDescription(
        key="NUMBER_CONCENTRATION_PM_10",
        native_unit_of_measurement=CONCENTRATION_CM3,
        device_class=SensorDeviceClass.PM10,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    "NUMBER_CONCENTRATION_PM_2_5": HmSensorEntityDescription(
        key="NUMBER_CONCENTRATION_PM_2_5",
        native_unit_of_measurement=CONCENTRATION_CM3,
        device_class=SensorDeviceClass.PM25,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    "TYPICAL_PARTICLE_SIZE": HmSensorEntityDescription(
        key="TYPICAL_PARTICLE_SIZE",
        native_unit_of_measurement=PARTICLESIZE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    "OPERATING_VOLTAGE": HmSensorEntityDescription(
        key="OPERATING_VOLTAGE",
        native_unit_of_measurement=ELECTRIC_POTENTIAL_VOLT,
        device_class=SensorDeviceClass.VOLTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    "POWER": HmSensorEntityDescription(
        key="POWER",
        native_unit_of_measurement=POWER_WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    "RAIN_COUNTER": HmSensorEntityDescription(
        key="RAIN_COUNTER",
        native_unit_of_measurement=LENGTH_MILLIMETERS,
        icon="mdi:weather-rainy",
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    frozenset({"RSSI_DEVICE", "RSSI_PEER"}): HmSensorEntityDescription(
        key="RSSI",
        native_unit_of_measurement=SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    frozenset(
        {"ACTUAL_TEMPERATURE", "TEMPERATURE", "DEWPOINT"}
    ): HmSensorEntityDescription(
        key="TEMPERATURE",
        native_unit_of_measurement=TEMP_CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    "SMOKE_DETECTOR_ALARM_STATUS": HmSensorEntityDescription(
        key="SMOKE_DETECTOR_ALARM_STATUS",
        icon="mdi:smoke-detector",
        device_class="hmip_local__smoke_detector_alarm_status",
    ),
    "SUNSHINEDURATION": HmSensorEntityDescription(
        key="SUNSHINEDURATION",
        native_unit_of_measurement=TIME_MINUTES,
        icon="mdi:weather-sunny",
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    "VALUE": HmSensorEntityDescription(
        key="VALUE",
        native_unit_of_measurement="#",
        state_class=SensorStateClass.MEASUREMENT,
    ),
    "VALVE_STATE": HmSensorEntityDescription(
        key="VALVE_STATE",
        native_unit_of_measurement=PERCENTAGE,
        icon="mdi:pipe-valve",
        state_class=SensorStateClass.MEASUREMENT,
    ),
    "VAPOR_CONCENTRATION": HmSensorEntityDescription(
        key="VAPOR_CONCENTRATION",
        native_unit_of_measurement=VAPOR_CONCENTRATION,
        device_class=SensorDeviceClass.HUMIDITY,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    "VOLTAGE": HmSensorEntityDescription(
        key="VOLTAGE",
        native_unit_of_measurement=ELECTRIC_POTENTIAL_VOLT,
        device_class=SensorDeviceClass.VOLTAGE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    frozenset(
        {"WIND_DIR", "WIND_DIR_RANGE", "WIND_DIRECTION", "WIND_DIRECTION_RANGE"}
    ): HmSensorEntityDescription(
        key="WIND_DIR",
        native_unit_of_measurement=DEGREE,
        icon="mdi:windsock",
        state_class=SensorStateClass.MEASUREMENT,
    ),
    "WIND_SPEED": HmSensorEntityDescription(
        key="WIND_SPEED",
        native_unit_of_measurement=SPEED_KILOMETERS_PER_HOUR,
        icon="mdi:weather-windy",
        state_class=SensorStateClass.MEASUREMENT,
    ),
}

_SENSOR_DESCRIPTIONS_BY_DEVICE_PARAM: dict[
    tuple[str | frozenset[str], str], HmSensorEntityDescription
] = {
    (
        frozenset({"HmIP-SRH", "HM-Sec-RHS", "HM-Sec-xx", "ZEL STG RM FDK"}),
        "STATE",
    ): HmSensorEntityDescription(
        key="SRH_STATE",
        icon="mdi:window-closed",
        device_class="hmip_local__srh",
    ),
    ("HM-Sec-Win", "STATUS"): HmSensorEntityDescription(
        key="SEC-WIN_STATUS",
        icon="mdi:battery-50",
        device_class="hmip_local__sec_win_status",
    ),
    ("HM-Sec-Win", "DIRECTION"): HmSensorEntityDescription(
        key="SEC-WIN_DIRECTION",
        icon="mdi:arrow-up-down",
        device_class="hmip_local__sec_direction",
    ),
    ("HM-Sec-Win", "ERROR"): HmSensorEntityDescription(
        key="SEC-WIN_ERROR",
        icon="mdi:lock-alert",
        device_class="hmip_local__sec_win_error",
    ),
    ("HM-Sec-Key", "DIRECTION"): HmSensorEntityDescription(
        key="SEC-KEY_DIRECTION",
        icon="mdi:arrow-up-down",
        device_class="hmip_local__sec_direction",
    ),
    ("HM-Sec-Key", "ERROR"): HmSensorEntityDescription(
        key="SEC-KEY_ERROR",
        icon="mdi:lock-alert",
        device_class="hmip_local__sec_key_error",
    ),
}

_SENSOR_DESCRIPTIONS_BY_UNIT: dict[str, HmSensorEntityDescription] = {
    TEMP_CELSIUS: HmSensorEntityDescription(
        key="TEMPERATURE",
        native_unit_of_measurement=TEMP_CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    VAPOR_CONCENTRATION: HmSensorEntityDescription(
        key="VAPOR_CONCENTRATION",
        native_unit_of_measurement=VAPOR_CONCENTRATION,
        device_class=SensorDeviceClass.HUMIDITY,
        state_class=SensorStateClass.MEASUREMENT,
    ),
}

_BINARY_SENSOR_DESCRIPTIONS_BY_PARAM: dict[
    str | frozenset[str], BinarySensorEntityDescription
] = {
    "ALARMSTATE": BinarySensorEntityDescription(
        key="ALARMSTATE",
        device_class=BinarySensorDeviceClass.SAFETY,
    ),
    "ACOUSTIC_ALARM_ACTIVE": BinarySensorEntityDescription(
        key="ACOUSTIC_ALARM_ACTIVE",
        device_class=BinarySensorDeviceClass.SAFETY,
    ),
    frozenset({"DUTYCYCLE", "DUTY_CYCLE"}): BinarySensorEntityDescription(
        key="DUTY_CYCLE",
        device_class=BinarySensorDeviceClass.PROBLEM,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    "HEATER_STATE": BinarySensorEntityDescription(
        key="HEATER_STATE",
        device_class=BinarySensorDeviceClass.HEAT,
    ),
    frozenset({"LOWBAT", "LOW_BAT", "LOWBAT_SENSOR"}): BinarySensorEntityDescription(
        key="LOW_BAT",
        device_class=BinarySensorDeviceClass.BATTERY,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    "MOISTURE_DETECTED": BinarySensorEntityDescription(
        key="MOISTURE_DETECTED",
        device_class=BinarySensorDeviceClass.MOISTURE,
    ),
    "MOTION": BinarySensorEntityDescription(
        key="MOTION",
        device_class=BinarySensorDeviceClass.MOTION,
    ),
    "OPTICAL_ALARM_ACTIVE": BinarySensorEntityDescription(
        key="OPTICAL_ALARM_ACTIVE",
        device_class=BinarySensorDeviceClass.SAFETY,
    ),
    "PRESENCE_DETECTION_STATE": BinarySensorEntityDescription(
        key="PRESENCE_DETECTION_STATE",
        device_class=BinarySensorDeviceClass.PRESENCE,
    ),
    frozenset({"PROCESS", "WORKING"}): BinarySensorEntityDescription(
        key="PROCESS",
        device_class=BinarySensorDeviceClass.RUNNING,
    ),
    "RAINING": BinarySensorEntityDescription(
        key="RAINING",
        device_class=BinarySensorDeviceClass.MOISTURE,
    ),
    "SABOTAGE": BinarySensorEntityDescription(
        key="SABOTAGE",
        device_class=BinarySensorDeviceClass.SAFETY,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    "WATERLEVEL_DETECTED": BinarySensorEntityDescription(
        key="WATERLEVEL_DETECTED",
        device_class=BinarySensorDeviceClass.MOISTURE,
    ),
    "WINDOW_STATE": BinarySensorEntityDescription(
        key="WINDOW_STATE",
        device_class=BinarySensorDeviceClass.WINDOW,
    ),
}

_BINARY_SENSOR_DESCRIPTIONS_BY_DEVICE_PARAM: dict[
    tuple[str | frozenset[str], str], BinarySensorEntityDescription
] = {
    (frozenset({"SCI", "FCI1", "FCI16"}), "STATE"): BinarySensorEntityDescription(
        key="STATE",
        device_class=BinarySensorDeviceClass.OPENING,
    ),
    ("HM-Sec-SD", "STATE"): BinarySensorEntityDescription(
        key="STATE",
        device_class=BinarySensorDeviceClass.SMOKE,
    ),
    (
        frozenset(
            {
                "SWD",
                "SWDO-I",
                "SWDM",
                "SWDO-PL",
                "HM-Sec-SC",
                "HM-SCI-3-FM",
                "ZEL STG RM FFK",
            }
        ),
        "STATE",
    ): BinarySensorEntityDescription(
        key="STATE",
        device_class=BinarySensorDeviceClass.WINDOW,
    ),
    ("HM-Sen-RD-O", "STATE"): BinarySensorEntityDescription(
        key="STATE",
        device_class=BinarySensorDeviceClass.MOISTURE,
    ),
    ("HM-Sec-Win", "WORKING"): BinarySensorEntityDescription(
        key="WORKING",
        device_class=BinarySensorDeviceClass.RUNNING,
        entity_registry_enabled_default=False,
    ),
}

_COVER_DESCRIPTIONS_BY_DEVICE: dict[str | frozenset[str], CoverEntityDescription] = {
    frozenset(
        {"HmIP-BBL", "HmIP-FBL", "HmIP-DRBLI4", "HmIPW-DRBL4"}
    ): CoverEntityDescription(
        key="BLIND",
        device_class=CoverDeviceClass.BLIND,
    ),
    frozenset({"HmIP-BROLL", "HmIP-FROLL"}): CoverEntityDescription(
        key="SHUTTER",
        device_class=CoverDeviceClass.SHUTTER,
    ),
    "HmIP-HDM1": CoverEntityDescription(
        key="HDM1",
        device_class=CoverDeviceClass.SHADE,
    ),
    frozenset({"HmIP-MOD-HO", "HmIP-MOD-TM"}): CoverEntityDescription(
        key="GARAGE-HO",
        device_class=CoverDeviceClass.GARAGE,
    ),
    "HM-Sec-Win": CoverEntityDescription(
        key="HM-Sec-Win",
        device_class=CoverDeviceClass.WINDOW,
    ),
}

_SWITCH_DESCRIPTIONS_BY_PARAM: dict[str | frozenset[str], SwitchEntityDescription] = {
    "INHIBIT": SwitchEntityDescription(
        key="INHIBIT",
        device_class=SwitchDeviceClass.SWITCH,
        entity_registry_enabled_default=False,
    ),
}

_SWITCH_DESCRIPTIONS_BY_DEVICE: dict[str | frozenset[str], SwitchEntityDescription] = {}

_SWITCH_DESCRIPTIONS_BY_DEVICE_PARAM: dict[
    tuple[str | frozenset[str], str], SwitchEntityDescription
] = {}

_ENTITY_DESCRIPTION_DEVICE: dict[HmPlatform, dict[str | frozenset[str], Any]] = {
    HmPlatform.COVER: _COVER_DESCRIPTIONS_BY_DEVICE,
    HmPlatform.SWITCH: _SWITCH_DESCRIPTIONS_BY_DEVICE,
}

_ENTITY_DESCRIPTION_PARAM: dict[HmPlatform, dict[str | frozenset[str], Any]] = {
    HmPlatform.BINARY_SENSOR: _BINARY_SENSOR_DESCRIPTIONS_BY_PARAM,
    HmPlatform.BUTTON: _BUTTON_DESCRIPTIONS_BY_PARAM,
    HmPlatform.NUMBER: _NUMBER_DESCRIPTIONS_BY_PARAM,
    HmPlatform.SENSOR: _SENSOR_DESCRIPTIONS_BY_PARAM,
    HmPlatform.SWITCH: _SWITCH_DESCRIPTIONS_BY_PARAM,
}

_ENTITY_DESCRIPTION_DEVICE_PARAM: dict[
    HmPlatform, dict[tuple[str | frozenset[str], str], Any]
] = {
    HmPlatform.BINARY_SENSOR: _BINARY_SENSOR_DESCRIPTIONS_BY_DEVICE_PARAM,
    HmPlatform.NUMBER: _NUMBER_DESCRIPTIONS_DEVICE_BY_PARAM,
    HmPlatform.SENSOR: _SENSOR_DESCRIPTIONS_BY_DEVICE_PARAM,
    HmPlatform.SWITCH: _SWITCH_DESCRIPTIONS_BY_DEVICE_PARAM,
}

_DEFAULT_DESCRIPTION: dict[HmPlatform, Any] = {
    HmPlatform.BINARY_SENSOR: None,
    HmPlatform.BUTTON: ButtonEntityDescription(
        key="button_default",
        icon="mdi:gesture-tap",
        entity_registry_enabled_default=False,
    ),
    HmPlatform.COVER: None,
    HmPlatform.SENSOR: None,
    HmPlatform.SWITCH: SwitchEntityDescription(
        key="switch_default",
        device_class=SwitchDeviceClass.SWITCH,
    ),
}


def get_entity_description(hm_entity: HmGenericEntity) -> EntityDescription | None:
    """Get the entity_description for platform."""
    entity_description: EntityDescription | None = None
    if isinstance(hm_entity, GenericEntity):
        if entity_desc := _get_entity_description_by_device_type_and_param(
            platform=hm_entity.platform,
            device_type=hm_entity.device_type,
            parameter=hm_entity.parameter,
        ):
            entity_description = entity_desc

        if entity_description is None and hm_entity.sub_type:
            if entity_desc := _get_entity_description_by_device_type_and_param(
                platform=hm_entity.platform,
                device_type=hm_entity.sub_type,
                parameter=hm_entity.parameter,
                do_wildcard_search=False,
            ):
                entity_description = entity_desc

        if entity_description is None:
            if entity_desc := _get_entity_description_by_param(
                platform=hm_entity.platform,
                parameter=hm_entity.parameter,
            ):
                entity_description = entity_desc

    elif isinstance(hm_entity, CustomEntity):
        if entity_desc := _get_entity_description_by_device_type(
            platform=hm_entity.platform, device_type=hm_entity.device_type
        ):
            entity_description = entity_desc

        if entity_description is None and hm_entity.sub_type:
            if entity_desc := _get_entity_description_by_device_type(
                platform=hm_entity.platform,
                device_type=hm_entity.sub_type,
                do_wildcard_search=False,
            ):
                entity_description = entity_desc

    if entity_description is None and isinstance(hm_entity, GenericEntity):
        if hm_entity.platform == HmPlatform.SENSOR and hm_entity.unit is not None:
            if entity_desc := _SENSOR_DESCRIPTIONS_BY_UNIT.get(hm_entity.unit):
                entity_description = entity_desc

    if entity_description:
        return entity_description

    if hasattr(hm_entity, "platform"):
        return _DEFAULT_DESCRIPTION.get(hm_entity.platform, None)
    return None


def _get_entity_description_by_device_type_and_param(
    platform: HmPlatform,
    device_type: str,
    parameter: str,
    do_wildcard_search: bool = True,
) -> EntityDescription | None:
    """Get entity_description by device_type and parameter"""
    if platform_device_param_descriptions := _ENTITY_DESCRIPTION_DEVICE_PARAM.get(
        platform
    ):
        entity_description: EntityDescription | None = None
        for data, entity_desc in platform_device_param_descriptions.items():
            if (
                _device_in_list(
                    devices=data[0],
                    device_type=device_type,
                    do_wildcard_search=do_wildcard_search,
                )
                and data[1] == parameter
            ):
                entity_description = entity_desc
                break

        return entity_description
    return None


def _get_entity_description_by_param(
    platform: HmPlatform,
    parameter: str,
) -> EntityDescription | None:
    """Get entity_description by device_type and parameter"""
    if platform_param_descriptions := _ENTITY_DESCRIPTION_PARAM.get(platform):
        entity_description: EntityDescription | None = None
        for params, entity_desc in platform_param_descriptions.items():
            if _param_in_list(params=params, parameter=parameter):
                entity_description = entity_desc
                break

        return entity_description
    return None


def _get_entity_description_by_device_type(
    platform: HmPlatform, device_type: str, do_wildcard_search: bool = True
) -> EntityDescription | None:
    """Get entity_description by device_type"""
    if platform_device_descriptions := _ENTITY_DESCRIPTION_DEVICE.get(platform):
        entity_description: EntityDescription | None = None
        for devices, entity_desc in platform_device_descriptions.items():
            if _device_in_list(
                devices=devices,
                device_type=device_type,
                do_wildcard_search=do_wildcard_search,
            ):
                entity_description = entity_desc
                break

        return entity_description
    return None


def _device_in_list(
    devices: str | frozenset[str], device_type: str, do_wildcard_search: bool
) -> bool:
    """Return if device is in set."""
    if isinstance(devices, str):
        if do_wildcard_search:
            return device_type.lower().startswith(devices.lower())
        return device_type.lower() == devices.lower()
    if isinstance(devices, frozenset):
        for device in devices:
            if do_wildcard_search:
                if device_type.lower().startswith(device.lower()):
                    return True
            else:
                if device_type.lower() == device.lower():
                    return True
    return False


def _param_in_list(params: str | frozenset[str], parameter: str) -> bool:
    """Return if parameter is in set."""
    if isinstance(params, str):
        return parameter.lower() == params.lower()
    if isinstance(params, frozenset):
        for device in params:
            if parameter.lower() == device.lower():
                return True
    return False
