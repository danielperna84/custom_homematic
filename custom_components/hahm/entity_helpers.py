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
from homeassistant.components.number import NumberEntityDescription
from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.components.switch import SwitchDeviceClass, SwitchEntityDescription
from homeassistant.const import (
    CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
    CONCENTRATION_PARTS_PER_MILLION,
    DEGREE,
    ELECTRIC_CURRENT_MILLIAMPERE,
    ELECTRIC_POTENTIAL_VOLT,
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

from .helpers import HmGenericEntity

_LOGGER = logging.getLogger(__name__)

CONCENTRATION_CM3 = "1/cm\u00b3"
PARTICLESIZE = "\u00b5m"


_BUTTON_DESCRIPTIONS_BY_PARAM: dict[str, ButtonEntityDescription] = {}

_NUMBER_DESCRIPTIONS_BY_PARAM: dict[str, NumberEntityDescription] = {}

_NUMBER_DESCRIPTIONS_DEVICE_BY_PARAM: dict[
    tuple[str | frozenset[str], str], NumberEntityDescription
] = {
    # HmIP-eTRV, HmIP-eTRV-2
    (
        frozenset({"TRV", "TRV-B", "TRV-C", "HMIP_FALMOT-C12", "HMIPW_FALMOT-C12"}),
        "LEVEL",
    ): NumberEntityDescription(
        key="LEVEL",
        icon="mdi:pipe-valve",
    ),
}

_SENSOR_DESCRIPTIONS_BY_PARAM: dict[str, SensorEntityDescription] = {
    "ACTUAL_TEMPERATURE": SensorEntityDescription(
        key="ACTUAL_TEMPERATURE",
        native_unit_of_measurement=TEMP_CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    "AIR_PRESSURE": SensorEntityDescription(
        key="AIR_PRESSURE",
        native_unit_of_measurement=PRESSURE_HPA,
        device_class=SensorDeviceClass.PRESSURE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    "AVERAGE_ILLUMINATION": SensorEntityDescription(
        key="AVERAGE_ILLUMINATION",
        native_unit_of_measurement=LIGHT_LUX,
        device_class=SensorDeviceClass.ILLUMINANCE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    "BRIGHTNESS": SensorEntityDescription(
        key="BRIGHTNESS",
        native_unit_of_measurement="#",
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:invert-colors",
    ),
    "CARRIER_SENSE_LEVEL": SensorEntityDescription(
        key="CARRIER_SENSE_LEVEL",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    "CONCENTRATION": SensorEntityDescription(
        key="CONCENTRATION",
        native_unit_of_measurement=CONCENTRATION_PARTS_PER_MILLION,
        device_class=SensorDeviceClass.CO2,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    "CURRENT": SensorEntityDescription(
        key="CURRENT",
        native_unit_of_measurement=ELECTRIC_CURRENT_MILLIAMPERE,
        device_class=SensorDeviceClass.CURRENT,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    "CURRENT_ILLUMINATION": SensorEntityDescription(
        key="CURRENT_ILLUMINATION",
        native_unit_of_measurement=LIGHT_LUX,
        device_class=SensorDeviceClass.ILLUMINANCE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    "DUTY_CYCLE_LEVEL": SensorEntityDescription(
        key="DUTY_CYCLE_LEVEL",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    "ENERGY_COUNTER": SensorEntityDescription(
        key="ENERGY_COUNTER",
        native_unit_of_measurement=ENERGY_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    "FREQUENCY": SensorEntityDescription(
        key="FREQUENCY",
        native_unit_of_measurement=FREQUENCY_HERTZ,
        device_class=SensorDeviceClass.FREQUENCY,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    "GAS_ENERGY_COUNTER": SensorEntityDescription(
        key="GAS_ENERGY_COUNTER",
        native_unit_of_measurement=VOLUME_CUBIC_METERS,
        device_class=SensorDeviceClass.GAS,
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    "GAS_POWER": SensorEntityDescription(
        key="GAS_POWER",
        native_unit_of_measurement=VOLUME_CUBIC_METERS,
        device_class=SensorDeviceClass.GAS,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    "HIGHEST_ILLUMINATION": SensorEntityDescription(
        key="HIGHEST_ILLUMINATION",
        native_unit_of_measurement=LIGHT_LUX,
        device_class=SensorDeviceClass.ILLUMINANCE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    "HUMIDITY": SensorEntityDescription(
        key="HUMIDITY",
        native_unit_of_measurement=PERCENTAGE,
        device_class=SensorDeviceClass.HUMIDITY,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    "IEC_ENERGY_COUNTER": SensorEntityDescription(
        key="IEC_ENERGY_COUNTER",
        native_unit_of_measurement=ENERGY_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    "IEC_POWER": SensorEntityDescription(
        key="IEC_POWER",
        native_unit_of_measurement=POWER_WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    "ILLUMINATION": SensorEntityDescription(
        key="ILLUMINATION",
        native_unit_of_measurement=LIGHT_LUX,
        device_class=SensorDeviceClass.ILLUMINANCE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    "IP_ADDRESS": SensorEntityDescription(
        key="IP_ADDRESS",
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    "LEVEL": SensorEntityDescription(
        key="LEVEL",
        native_unit_of_measurement="#",
        state_class=SensorStateClass.MEASUREMENT,
    ),
    "LOCK_STATE": SensorEntityDescription(
        key="LOCK_STATE",
        icon="mdi:lock",
        device_class="hahm__lock_state",
    ),
    "LOWEST_ILLUMINATION": SensorEntityDescription(
        key="LOWEST_ILLUMINATION",
        native_unit_of_measurement=LIGHT_LUX,
        device_class=SensorDeviceClass.ILLUMINANCE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    "LUX": SensorEntityDescription(
        key="LUX",
        native_unit_of_measurement=LIGHT_LUX,
        device_class=SensorDeviceClass.ILLUMINANCE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    "MASS_CONCENTRATION_PM_1": SensorEntityDescription(
        key="MASS_CONCENTRATION_PM_1",
        native_unit_of_measurement=CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
        device_class=SensorDeviceClass.PM1,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    "MASS_CONCENTRATION_PM_1_24H_AVERAGE": SensorEntityDescription(
        key="MASS_CONCENTRATION_PM_1_24H_AVERAGE",
        native_unit_of_measurement=CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
        device_class=SensorDeviceClass.PM1,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    "MASS_CONCENTRATION_PM_10": SensorEntityDescription(
        key="MASS_CONCENTRATION_PM_10",
        native_unit_of_measurement=CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
        device_class=SensorDeviceClass.PM10,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    "MASS_CONCENTRATION_PM_10_24H_AVERAGE": SensorEntityDescription(
        key="MASS_CONCENTRATION_PM_10_24H_AVERAGE",
        native_unit_of_measurement=CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
        device_class=SensorDeviceClass.PM10,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    "MASS_CONCENTRATION_PM_2_5": SensorEntityDescription(
        key="MASS_CONCENTRATION_PM_2_5",
        native_unit_of_measurement=CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
        device_class=SensorDeviceClass.PM25,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    "MASS_CONCENTRATION_PM_2_5_24H_AVERAGE": SensorEntityDescription(
        key="MASS_CONCENTRATION_PM_2_5_24H_AVERAGE",
        native_unit_of_measurement=CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
        device_class=SensorDeviceClass.PM25,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    "NUMBER_CONCENTRATION_PM_1": SensorEntityDescription(
        key="NUMBER_CONCENTRATION_PM_1",
        native_unit_of_measurement=CONCENTRATION_CM3,
        device_class=SensorDeviceClass.PM1,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    "NUMBER_CONCENTRATION_PM_10": SensorEntityDescription(
        key="NUMBER_CONCENTRATION_PM_10",
        native_unit_of_measurement=CONCENTRATION_CM3,
        device_class=SensorDeviceClass.PM10,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    "NUMBER_CONCENTRATION_PM_2_5": SensorEntityDescription(
        key="NUMBER_CONCENTRATION_PM_2_5",
        native_unit_of_measurement=CONCENTRATION_CM3,
        device_class=SensorDeviceClass.PM25,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    "TYPICAL_PARTICLE_SIZE": SensorEntityDescription(
        key="TYPICAL_PARTICLE_SIZE",
        native_unit_of_measurement=PARTICLESIZE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    "OPERATING_VOLTAGE": SensorEntityDescription(
        key="OPERATING_VOLTAGE",
        native_unit_of_measurement=ELECTRIC_POTENTIAL_VOLT,
        device_class=SensorDeviceClass.VOLTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    "POWER": SensorEntityDescription(
        key="POWER",
        native_unit_of_measurement=POWER_WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    "RAIN_COUNTER": SensorEntityDescription(
        key="RAIN_COUNTER",
        native_unit_of_measurement=LENGTH_MILLIMETERS,
        icon="mdi:weather-rainy",
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    "RSSI_DEVICE": SensorEntityDescription(
        key="RSSI_DEVICE",
        native_unit_of_measurement=SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    "RSSI_PEER": SensorEntityDescription(
        key="RSSI_PEER",
        native_unit_of_measurement=SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    "TEMPERATURE": SensorEntityDescription(
        key="TEMPERATURE",
        native_unit_of_measurement=TEMP_CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    "SMOKE_DETECTOR_ALARM_STATUS": SensorEntityDescription(
        key="SMOKE_DETECTOR_ALARM_STATUS",
        icon="mdi:smoke-detector",
        device_class="hahm__smoke_detector_alarm_status",
    ),
    "SUNSHINEDURATION": SensorEntityDescription(
        key="SUNSHINEDURATION",
        native_unit_of_measurement=TIME_MINUTES,
        icon="mdi:weather-sunny",
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    "VALUE": SensorEntityDescription(
        key="VALUE",
        native_unit_of_measurement="#",
        state_class=SensorStateClass.MEASUREMENT,
    ),
    "VALVE_STATE": SensorEntityDescription(
        key="VALVE_STATE",
        native_unit_of_measurement=PERCENTAGE,
        icon="mdi:pipe-valve",
        state_class=SensorStateClass.MEASUREMENT,
    ),
    "VOLTAGE": SensorEntityDescription(
        key="VOLTAGE",
        native_unit_of_measurement=ELECTRIC_POTENTIAL_VOLT,
        device_class=SensorDeviceClass.VOLTAGE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    "WIND_DIR": SensorEntityDescription(
        key="WIND_DIR",
        native_unit_of_measurement=DEGREE,
        icon="mdi:windsock",
        state_class=SensorStateClass.MEASUREMENT,
    ),
    "WIND_DIR_RANGE": SensorEntityDescription(
        key="WIND_DIR_RANGE",
        native_unit_of_measurement=DEGREE,
        icon="mdi:windsock",
        state_class=SensorStateClass.MEASUREMENT,
    ),
    "WIND_SPEED": SensorEntityDescription(
        key="WIND_SPEED",
        native_unit_of_measurement=SPEED_KILOMETERS_PER_HOUR,
        icon="mdi:weather-windy",
        state_class=SensorStateClass.MEASUREMENT,
    ),
}

_SENSOR_DESCRIPTIONS_BY_DEVICE_PARAM: dict[
    tuple[str | frozenset[str], str], SensorEntityDescription
] = {
    (frozenset({"HmIP-SRH", "HM-Sec-RHS", "HM-Sec-xx", "ZEL STG RM FDK"}), "STATE"): SensorEntityDescription(
        key="SRH_STATE",
        icon="mdi:window-closed",
        device_class="hahm__srh",
    ),
    ("HM-Sec-Win", "STATUS"): SensorEntityDescription(
        key="SEC-WIN_STATUS",
        icon="mdi:battery-50",
        device_class="hahm__sec_win_status",
        entity_registry_enabled_default=False,
    ),
    ("HM-Sec-Win", "DIRECTION"): SensorEntityDescription(
        key="SEC-WIN_DIRECTION",
        icon="mdi:arrow-up-down",
        device_class="hahm__sec_direction",
        entity_registry_enabled_default=False,
    ),
    ("HM-Sec-Win", "ERROR"): SensorEntityDescription(
        key="SEC-WIN_ERROR",
        icon="mdi:lock-alert",
        device_class="hahm__sec_error",
        entity_registry_enabled_default=False,
    ),
    ("HM-Sec-Key", "DIRECTION"): SensorEntityDescription(
        key="SEC-KEY_DIRECTION",
        icon="mdi:arrow-up-down",
        device_class="hahm__sec_direction",
        entity_registry_enabled_default=False,
    ),
    ("HM-Sec-Key", "ERROR"): SensorEntityDescription(
        key="SEC-KEY_ERROR",
        icon="mdi:lock-alert",
        device_class="hahm__sec_error",
        entity_registry_enabled_default=False,
    ),
}

_BINARY_SENSOR_DESCRIPTIONS_BY_PARAM: dict[str, BinarySensorEntityDescription] = {
    "ALARMSTATE": BinarySensorEntityDescription(
        key="ALARMSTATE",
        device_class=BinarySensorDeviceClass.SAFETY,
    ),
    "ACOUSTIC_ALARM_ACTIVE": BinarySensorEntityDescription(
        key="ACOUSTIC_ALARM_ACTIVE",
        device_class=BinarySensorDeviceClass.SAFETY,
    ),
    "DUTYCYCLE": BinarySensorEntityDescription(
        key="DUTYCYCLE",
        device_class=BinarySensorDeviceClass.PROBLEM,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    "DUTY_CYCLE": BinarySensorEntityDescription(
        key="DUTY_CYCLE",
        device_class=BinarySensorDeviceClass.PROBLEM,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    "HEATER_STATE": BinarySensorEntityDescription(
        key="HEATER_STATE",
        device_class=BinarySensorDeviceClass.HEAT,
    ),
    "LOWBAT": BinarySensorEntityDescription(
        key="LOWBAT",
        device_class=BinarySensorDeviceClass.BATTERY,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    "LOW_BAT": BinarySensorEntityDescription(
        key="LOW_BAT",
        device_class=BinarySensorDeviceClass.BATTERY,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    "LOWBAT_SENSOR": BinarySensorEntityDescription(
        key="LOWBAT_SENSOR",
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
    # HmIP-SCI
    ("SCI", "STATE"): BinarySensorEntityDescription(
        key="STATE",
        device_class=BinarySensorDeviceClass.OPENING,
    ),
    ("HM-Sec-SD", "STATE"): BinarySensorEntityDescription(
        key="STATE",
        device_class=BinarySensorDeviceClass.SMOKE,
    ),
    (
        frozenset({"SWD", "SWDO-I", "SWDM", "SWDO-PL", "HM-Sec-SC", "HM-SCI-3-FM", "ZEL STG RM FFK"}),
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

_COVER_DESCRIPTIONS_BY_DEVICE: dict[str, CoverEntityDescription] = {
    "HmIP-BBL": CoverEntityDescription(
        key="BBL",
        device_class=CoverDeviceClass.BLIND,
    ),
    "HmIP-BROLL": CoverEntityDescription(
        key="BROLL",
        device_class=CoverDeviceClass.SHUTTER,
    ),
    "HmIP-DRBLI4": CoverEntityDescription(
        key="DRBLI4",
        device_class=CoverDeviceClass.BLIND,
    ),
    "HmIPW-DRBL4": CoverEntityDescription(
        key="W-DRBL4",
        device_class=CoverDeviceClass.BLIND,
    ),
    "HmIP-FBL": CoverEntityDescription(
        key="FBL",
        device_class=CoverDeviceClass.BLIND,
    ),
    "HmIP-FROLL": CoverEntityDescription(
        key="FROLL",
        device_class=CoverDeviceClass.SHUTTER,
    ),
    "HmIP-HDM1": CoverEntityDescription(
        key="HDM1",
        device_class=CoverDeviceClass.SHADE,
    ),
    "HmIP-MOD-HO": CoverEntityDescription(
        key="MOD-HO",
        device_class=CoverDeviceClass.GARAGE,
    ),
    "HmIP-MOD-TM": CoverEntityDescription(
        key="MOD-TM",
        device_class=CoverDeviceClass.GARAGE,
    ),
}

_SWITCH_DESCRIPTIONS_BY_DEVICE: dict[str, SwitchEntityDescription] = {}

_SWITCH_DESCRIPTIONS_BY_DEVICE_PARAM: dict[
    tuple[str | frozenset[str], str], SwitchEntityDescription
] = {}

_ENTITY_DESCRIPTION_DEVICE: dict[HmPlatform, dict[str, Any]] = {
    HmPlatform.COVER: _COVER_DESCRIPTIONS_BY_DEVICE,
    HmPlatform.SWITCH: _SWITCH_DESCRIPTIONS_BY_DEVICE,
}

_ENTITY_DESCRIPTION_PARAM: dict[HmPlatform, dict[str, Any]] = {
    HmPlatform.BINARY_SENSOR: _BINARY_SENSOR_DESCRIPTIONS_BY_PARAM,
    HmPlatform.BUTTON: _BUTTON_DESCRIPTIONS_BY_PARAM,
    HmPlatform.NUMBER: _NUMBER_DESCRIPTIONS_BY_PARAM,
    HmPlatform.SENSOR: _SENSOR_DESCRIPTIONS_BY_PARAM,
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
            if platform_param_descriptions := _ENTITY_DESCRIPTION_PARAM.get(
                hm_entity.platform
            ):
                entity_description = platform_param_descriptions.get(
                    hm_entity.parameter
                )

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
                    device_list=data[0],
                    device_type=device_type,
                    do_wildcard_search=do_wildcard_search,
                )
                and data[1] == parameter
            ):
                entity_description = entity_desc
                break

        return entity_description
    return None


def _device_in_list(
    device_list: str | frozenset[str], device_type: str, do_wildcard_search: bool
) -> bool:
    """Return if device is in list."""
    if isinstance(device_list, str):
        if do_wildcard_search:
            return device_type.lower().startswith(device_list.lower())
        return device_type.lower() == device_list.lower()
    if isinstance(device_list, frozenset):
        for device in device_list:
            if do_wildcard_search:
                if device_type.lower().startswith(device.lower()):
                    return True
            else:
                if device_type.lower() == device.lower():
                    return True
    return False


def _get_entity_description_by_device_type(
    platform: HmPlatform, device_type: str, do_wildcard_search: bool = True
) -> EntityDescription | None:
    """Get entity_description by device_type"""
    if platform_device_descriptions := _ENTITY_DESCRIPTION_DEVICE.get(platform):
        entity_description = platform_device_descriptions.get(device_type)
        if entity_description is None and do_wildcard_search:
            for data, entity_desc in platform_device_descriptions.items():
                if device_type.lower().startswith(data.lower()):
                    entity_description = entity_desc
                    break

        return entity_description
    return None
