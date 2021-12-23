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
    SIGNAL_STRENGTH_DECIBELS,
    SPEED_KILOMETERS_PER_HOUR,
    TEMP_CELSIUS,
    TIME_MINUTES,
    VOLUME_CUBIC_METERS,
)
from homeassistant.helpers.entity import EntityCategory, EntityDescription

from .helpers import HmGenericEntity

_LOGGER = logging.getLogger(__name__)

_NUMBER_DESCRIPTIONS_BY_PARAM: dict[str, NumberEntityDescription] = {
    "ACTIVE_PROFILE": NumberEntityDescription(
        key="ACTIVE_PROFILE",
        icon="mdi:hvac",
        min_value=1,
        max_value=6,
        step=1,
    ),
    "LEVEL": NumberEntityDescription(
        key="LEVEL",
        icon="mdi:radiator",
        min_value=0.0,
        max_value=1.01,
        step=0.1,
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
        native_unit_of_measurement=SIGNAL_STRENGTH_DECIBELS,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    "RSSI_PEER": SensorEntityDescription(
        key="RSSI_PEER",
        native_unit_of_measurement=SIGNAL_STRENGTH_DECIBELS,
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

_SENSOR_DESCRIPTIONS_BY_DEVICE_PARAM: dict[tuple[str, str], SensorEntityDescription] = {
    ("HmIP-SRH", "STATE"): SensorEntityDescription(
        key="STATE",
        device_class="hahm__srh",
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
    tuple[str, str], BinarySensorEntityDescription
] = {
    # HmIP-SCI
    ("SCI", "STATE"): BinarySensorEntityDescription(
        key="STATE",
        device_class=BinarySensorDeviceClass.SAFETY,
    ),
    # HmIP-SWDO
    ("SWD", "STATE"): BinarySensorEntityDescription(
        key="STATE",
        device_class=BinarySensorDeviceClass.WINDOW,
    ),
    # HmIP-SWDO-I
    ("SWDO-I", "STATE"): BinarySensorEntityDescription(
        key="STATE",
        device_class=BinarySensorDeviceClass.WINDOW,
    ),
    # HmIP-SWDM, HmIP-SWDM-B2
    ("SWDM", "STATE"): BinarySensorEntityDescription(
        key="STATE",
        device_class=BinarySensorDeviceClass.WINDOW,
    ),
    # HmIP-SWDO-PL
    ("SWDO-PL", "STATE"): BinarySensorEntityDescription(
        key="STATE",
        device_class=BinarySensorDeviceClass.WINDOW,
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

_SWITCH_DESCRIPTIONS_BY_DEVICE: dict[str, SwitchEntityDescription] = {
    "PS": SwitchEntityDescription(
        key="PS",
        device_class=SwitchDeviceClass.OUTLET,
    ),
    "PSM": SwitchEntityDescription(
        key="PSM",
        device_class=SwitchDeviceClass.OUTLET,
    ),
}

_SWITCH_DESCRIPTIONS_BY_DEVICE_PARAM: dict[
    tuple[str, str], SwitchEntityDescription
] = {}

_ENTITY_DESCRIPTION_DEVICE: dict[HmPlatform, dict[str, Any]] = {
    HmPlatform.COVER: _COVER_DESCRIPTIONS_BY_DEVICE,
    HmPlatform.SWITCH: _SWITCH_DESCRIPTIONS_BY_DEVICE,
}

_ENTITY_DESCRIPTION_PARAM: dict[HmPlatform, dict[str, Any]] = {
    HmPlatform.BINARY_SENSOR: _BINARY_SENSOR_DESCRIPTIONS_BY_PARAM,
    HmPlatform.NUMBER: _NUMBER_DESCRIPTIONS_BY_PARAM,
    HmPlatform.SENSOR: _SENSOR_DESCRIPTIONS_BY_PARAM,
}

_ENTITY_DESCRIPTION_DEVICE_PARAM: dict[HmPlatform, dict[tuple[str, str], Any]] = {
    HmPlatform.BINARY_SENSOR: _BINARY_SENSOR_DESCRIPTIONS_BY_DEVICE_PARAM,
    HmPlatform.SENSOR: _SENSOR_DESCRIPTIONS_BY_DEVICE_PARAM,
    HmPlatform.SWITCH: _SWITCH_DESCRIPTIONS_BY_DEVICE_PARAM,
}

_DEFAULT_DESCRIPTION: dict[HmPlatform, Any] = {
    HmPlatform.BINARY_SENSOR: None,
    HmPlatform.BUTTON: ButtonEntityDescription(
        key="button_default",
        icon="mdi:gesture-tap",
        entity_category=EntityCategory.SYSTEM,
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
        if platform_device_param_descriptions := _ENTITY_DESCRIPTION_DEVICE_PARAM.get(
            hm_entity.platform
        ):
            entity_description = platform_device_param_descriptions.get(
                (hm_entity.device_type, hm_entity.parameter)
            )

        if entity_description is None and hm_entity.sub_type:
            if platform_device_param_descriptions := _ENTITY_DESCRIPTION_DEVICE_PARAM.get(
                hm_entity.platform
            ):
                entity_description = platform_device_param_descriptions.get(
                    (hm_entity.sub_type, hm_entity.parameter)
                )
        if entity_description:
            return entity_description

        if hm_entity.parameter in ["STATE"]:
            return _DEFAULT_DESCRIPTION.get(hm_entity.platform, {})

        if platform_param_descriptions := _ENTITY_DESCRIPTION_PARAM.get(
            hm_entity.platform
        ):
            return platform_param_descriptions.get(hm_entity.parameter)

    elif isinstance(hm_entity, CustomEntity):
        if platform_device_descriptions := _ENTITY_DESCRIPTION_DEVICE.get(
            hm_entity.platform
        ):
            entity_description = platform_device_descriptions.get(hm_entity.device_type)

        if entity_description is None and hm_entity.sub_type:
            if platform_device_descriptions := _ENTITY_DESCRIPTION_DEVICE.get(
                hm_entity.platform
            ):
                entity_description = platform_device_descriptions.get(
                    hm_entity.sub_type
                )

        if entity_description:
            return entity_description

    if hasattr(hm_entity, "platform"):
        return _DEFAULT_DESCRIPTION.get(hm_entity.platform, None)
    return None
