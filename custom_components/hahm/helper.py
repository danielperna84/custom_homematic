"""Support for HomeMatic sensors."""
from __future__ import annotations

import logging

from hahomematic.const import HmPlatform
from hahomematic.entity import BaseEntity, CustomEntity, GenericEntity

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntityDescription,
)
from homeassistant.components.button import ButtonEntityDescription
from homeassistant.components.cover import CoverDeviceClass, CoverEntityDescription
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
    ENTITY_CATEGORY_DIAGNOSTIC,
    ENTITY_CATEGORY_SYSTEM,
    FREQUENCY_HERTZ,
    LENGTH_MILLIMETERS,
    LIGHT_LUX,
    PERCENTAGE,
    POWER_WATT,
    PRESSURE_HPA,
    SIGNAL_STRENGTH_DECIBELS,
    SPEED_KILOMETERS_PER_HOUR,
    TEMP_CELSIUS,
    VOLUME_CUBIC_METERS,
)
from homeassistant.helpers.entity import EntityDescription

_LOGGER = logging.getLogger(__name__)

HM_STATE_HA_CAST = {
    "IPGarage": {0: "closed", 1: "open", 2: "ventilation", 3: None},
    "RotaryHandleSensor": {0: "closed", 1: "tilted", 2: "open"},
    "RotaryHandleSensorIP": {0: "closed", 1: "tilted", 2: "open"},
    "WaterSensor": {0: "dry", 1: "wet", 2: "water"},
    "CO2Sensor": {0: "normal", 1: "added", 2: "strong"},
    "IPSmoke": {0: "off", 1: "primary", 2: "intrusion", 3: "secondary"},
    "RFSiren": {
        0: "disarmed",
        1: "extsens_armed",
        2: "allsens_armed",
        3: "alarm_blocked",
    },
    "IPLockDLD": {0: None, 1: "locked", 2: "unlocked"},
}


_SENSOR_DESCRIPTIONS_BY_PARAM: dict[str, SensorEntityDescription] = {
    "HUMIDITY": SensorEntityDescription(
        key="HUMIDITY",
        native_unit_of_measurement=PERCENTAGE,
        device_class=SensorDeviceClass.HUMIDITY,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    "ACTUAL_TEMPERATURE": SensorEntityDescription(
        key="ACTUAL_TEMPERATURE",
        native_unit_of_measurement=TEMP_CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    "TEMPERATURE": SensorEntityDescription(
        key="TEMPERATURE",
        native_unit_of_measurement=TEMP_CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    "LUX": SensorEntityDescription(
        key="LUX",
        native_unit_of_measurement=LIGHT_LUX,
        device_class=SensorDeviceClass.ILLUMINANCE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    "CURRENT_ILLUMINATION": SensorEntityDescription(
        key="CURRENT_ILLUMINATION",
        native_unit_of_measurement=LIGHT_LUX,
        device_class=SensorDeviceClass.ILLUMINANCE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    "ILLUMINATION": SensorEntityDescription(
        key="ILLUMINATION",
        native_unit_of_measurement=LIGHT_LUX,
        device_class=SensorDeviceClass.ILLUMINANCE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    "AVERAGE_ILLUMINATION": SensorEntityDescription(
        key="AVERAGE_ILLUMINATION",
        native_unit_of_measurement=LIGHT_LUX,
        device_class=SensorDeviceClass.ILLUMINANCE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    "LOWEST_ILLUMINATION": SensorEntityDescription(
        key="LOWEST_ILLUMINATION",
        native_unit_of_measurement=LIGHT_LUX,
        device_class=SensorDeviceClass.ILLUMINANCE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    "HIGHEST_ILLUMINATION": SensorEntityDescription(
        key="HIGHEST_ILLUMINATION",
        native_unit_of_measurement=LIGHT_LUX,
        device_class=SensorDeviceClass.ILLUMINANCE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    "POWER": SensorEntityDescription(
        key="POWER",
        native_unit_of_measurement=POWER_WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    "IEC_POWER": SensorEntityDescription(
        key="IEC_POWER",
        native_unit_of_measurement=POWER_WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    "CURRENT": SensorEntityDescription(
        key="CURRENT",
        native_unit_of_measurement=ELECTRIC_CURRENT_MILLIAMPERE,
        device_class=SensorDeviceClass.CURRENT,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    "CONCENTRATION": SensorEntityDescription(
        key="CONCENTRATION",
        native_unit_of_measurement=CONCENTRATION_PARTS_PER_MILLION,
        device_class=SensorDeviceClass.CO2,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    "ENERGY_COUNTER": SensorEntityDescription(
        key="ENERGY_COUNTER",
        native_unit_of_measurement=ENERGY_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    "IEC_ENERGY_COUNTER": SensorEntityDescription(
        key="IEC_ENERGY_COUNTER",
        native_unit_of_measurement=ENERGY_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    "VOLTAGE": SensorEntityDescription(
        key="VOLTAGE",
        native_unit_of_measurement=ELECTRIC_POTENTIAL_VOLT,
        device_class=SensorDeviceClass.VOLTAGE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    "OPERATING_VOLTAGE": SensorEntityDescription(
        key="OPERATING_VOLTAGE",
        native_unit_of_measurement=ELECTRIC_POTENTIAL_VOLT,
        device_class=SensorDeviceClass.VOLTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=ENTITY_CATEGORY_DIAGNOSTIC,
    ),
    "GAS_POWER": SensorEntityDescription(
        key="GAS_POWER",
        native_unit_of_measurement=VOLUME_CUBIC_METERS,
        device_class=SensorDeviceClass.GAS,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    "GAS_ENERGY_COUNTER": SensorEntityDescription(
        key="GAS_ENERGY_COUNTER",
        native_unit_of_measurement=VOLUME_CUBIC_METERS,
        device_class=SensorDeviceClass.GAS,
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    "RAIN_COUNTER": SensorEntityDescription(
        key="RAIN_COUNTER",
        native_unit_of_measurement=LENGTH_MILLIMETERS,
    ),
    "WIND_SPEED": SensorEntityDescription(
        key="WIND_SPEED",
        native_unit_of_measurement=SPEED_KILOMETERS_PER_HOUR,
        icon="mdi:weather-windy",
    ),
    "WIND_DIR": SensorEntityDescription(
        key="WIND_DIR",
        native_unit_of_measurement=DEGREE,
    ),
    "WIND_DIR_RANGE": SensorEntityDescription(
        key="WIND_DIR_RANGE",
        native_unit_of_measurement=DEGREE,
    ),
    "SUNSHINEDURATION": SensorEntityDescription(
        key="SUNSHINEDURATION",
        native_unit_of_measurement="#",
    ),
    "AIR_PRESSURE": SensorEntityDescription(
        key="AIR_PRESSURE",
        native_unit_of_measurement=PRESSURE_HPA,
        device_class=SensorDeviceClass.PRESSURE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    "FREQUENCY": SensorEntityDescription(
        key="FREQUENCY",
        native_unit_of_measurement=FREQUENCY_HERTZ,
    ),
    "VALUE": SensorEntityDescription(
        key="VALUE",
        native_unit_of_measurement="#",
    ),
    "VALVE_STATE": SensorEntityDescription(
        key="VALVE_STATE",
        native_unit_of_measurement=PERCENTAGE,
    ),
    "CARRIER_SENSE_LEVEL": SensorEntityDescription(
        key="CARRIER_SENSE_LEVEL",
        native_unit_of_measurement=PERCENTAGE,
    ),
    "DUTY_CYCLE_LEVEL": SensorEntityDescription(
        key="DUTY_CYCLE_LEVEL",
        native_unit_of_measurement=PERCENTAGE,
    ),
    "BRIGHTNESS": SensorEntityDescription(
        key="BRIGHTNESS",
        native_unit_of_measurement="#",
        icon="mdi:invert-colors",
    ),
    "RSSI_DEVICE": SensorEntityDescription(
        key="RSSI_DEVICE",
        native_unit_of_measurement=SIGNAL_STRENGTH_DECIBELS,
        entity_category=ENTITY_CATEGORY_DIAGNOSTIC,
    ),
    "RSSI_PEER": SensorEntityDescription(
        key="RSSI_PEER",
        native_unit_of_measurement=SIGNAL_STRENGTH_DECIBELS,
        entity_category=ENTITY_CATEGORY_DIAGNOSTIC,
    ),
    "IP_ADDRESS": SensorEntityDescription(
        key="IP_ADDRESS",
        entity_category=ENTITY_CATEGORY_DIAGNOSTIC,
    ),
}

_SENSOR_DESCRIPTIONS_BY_DEVICE_PARAM: dict[(str, str), SensorEntityDescription] = {
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
    "OPTICAL_ALARM_ACTIVE": BinarySensorEntityDescription(
        key="OPTICAL_ALARM_ACTIVE",
        device_class=BinarySensorDeviceClass.SAFETY,
    ),
    "DUTY_CYCLE": BinarySensorEntityDescription(
        key="DUTY_CYCLE",
        device_class=BinarySensorDeviceClass.PROBLEM,
        entity_category=ENTITY_CATEGORY_DIAGNOSTIC,
    ),
    "DUTYCYCLE": BinarySensorEntityDescription(
        key="DUTYCYCLE",
        device_class=BinarySensorDeviceClass.PROBLEM,
        entity_category=ENTITY_CATEGORY_DIAGNOSTIC,
    ),
    "HEATER_STATE": BinarySensorEntityDescription(
        key="HEATER_STATE",
        device_class=BinarySensorDeviceClass.HEAT,
    ),
    "LOW_BAT": BinarySensorEntityDescription(
        key="LOW_BAT",
        device_class=BinarySensorDeviceClass.BATTERY,
        entity_category=ENTITY_CATEGORY_DIAGNOSTIC,
    ),
    "LOWBAT": BinarySensorEntityDescription(
        key="LOWBAT",
        device_class=BinarySensorDeviceClass.BATTERY,
        entity_category=ENTITY_CATEGORY_DIAGNOSTIC,
    ),
    "MOISTURE_DETECTED": BinarySensorEntityDescription(
        key="MOISTURE_DETECTED",
        device_class=BinarySensorDeviceClass.MOISTURE,
    ),
    "MOTION": BinarySensorEntityDescription(
        key="MOTION",
        device_class=BinarySensorDeviceClass.MOTION,
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
        entity_category=ENTITY_CATEGORY_DIAGNOSTIC,
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
    (str, str), BinarySensorEntityDescription
] = {
    ("HmIP-SWDO-I", "STATE"): BinarySensorEntityDescription(
        key="STATE",
        device_class=BinarySensorDeviceClass.WINDOW,
    ),
    ("HmIP-SWDO", "STATE"): BinarySensorEntityDescription(
        key="STATE",
        device_class=BinarySensorDeviceClass.WINDOW,
    ),
    ("HmIP-SCI", "STATE"): BinarySensorEntityDescription(
        key="STATE",
        device_class=BinarySensorDeviceClass.SAFETY,
    ),
}

_COVER_DESCRIPTIONS_BY_DEVICE: dict[str, CoverEntityDescription] = {
    "HmIP-BROLL": CoverEntityDescription(
        key="BROLL",
        device_class=CoverDeviceClass.SHUTTER,
    ),
    "HmIP-FROLL": CoverEntityDescription(
        key="FROLL",
        device_class=CoverDeviceClass.SHUTTER,
    ),
    "HmIP-BBL": CoverEntityDescription(
        key="BBL",
        device_class=CoverDeviceClass.BLIND,
    ),
    "HmIP-FBL": CoverEntityDescription(
        key="FBL",
        device_class=CoverDeviceClass.BLIND,
    ),
    "HmIP-DRBLI4": CoverEntityDescription(
        key="DRBLI4",
        device_class=CoverDeviceClass.BLIND,
    ),
    "HmIPW-DRBL4": CoverEntityDescription(
        key="W-DRBL4",
        device_class=CoverDeviceClass.BLIND,
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
    "HMIP-PS": SwitchEntityDescription(
        key="PS",
        device_class=SwitchDeviceClass.OUTLET,
    ),
    "HMIP-PSM": SwitchEntityDescription(
        key="PSM",
        device_class=SwitchDeviceClass.OUTLET,
    ),
}

_SWITCH_DESCRIPTIONS_BY_PARAM: dict[str, SwitchEntityDescription] = {}

_SWITCH_DESCRIPTIONS_BY_DEVICE_PARAM: dict[(str, str), SwitchEntityDescription] = {}

_ENTITY_DESCRIPTION_DEVICE = {
    HmPlatform.COVER: _COVER_DESCRIPTIONS_BY_DEVICE,
    HmPlatform.SWITCH: _SWITCH_DESCRIPTIONS_BY_DEVICE,
}

_ENTITY_DESCRIPTION_PARAM = {
    HmPlatform.BINARY_SENSOR: _BINARY_SENSOR_DESCRIPTIONS_BY_PARAM,
    HmPlatform.SENSOR: _SENSOR_DESCRIPTIONS_BY_PARAM,
    HmPlatform.SWITCH: _SWITCH_DESCRIPTIONS_BY_PARAM,
}

_ENTITY_DESCRIPTION_DEVICE_PARAM = {
    HmPlatform.BINARY_SENSOR: _BINARY_SENSOR_DESCRIPTIONS_BY_DEVICE_PARAM,
    HmPlatform.SENSOR: _SENSOR_DESCRIPTIONS_BY_DEVICE_PARAM,
    HmPlatform.SWITCH: _SWITCH_DESCRIPTIONS_BY_DEVICE_PARAM,
}

_DEFAULT_DESCRIPTION = {
    HmPlatform.BINARY_SENSOR: None,
    HmPlatform.BUTTON: ButtonEntityDescription(
        key="button_default",
        icon="mdi:gesture-tap",
        entity_category=ENTITY_CATEGORY_SYSTEM,
    ),
    HmPlatform.COVER: None,
    HmPlatform.SENSOR: None,
    HmPlatform.SWITCH: SwitchEntityDescription(
        key="switch_default",
        device_class=SwitchDeviceClass.SWITCH,
    ),
}


def get_entity_description(hm_entity: BaseEntity) -> EntityDescription | None:
    """Get the entity_description for platform."""
    if isinstance(hm_entity, GenericEntity):
        if device_description := _ENTITY_DESCRIPTION_DEVICE_PARAM.get(
            hm_entity.platform, {}
        ).get((hm_entity.device_type, hm_entity.parameter)):
            return device_description

        if hm_entity.parameter in ["STATE"]:
            return _DEFAULT_DESCRIPTION.get(hm_entity.platform, {})

        if param_description := _ENTITY_DESCRIPTION_PARAM.get(
            hm_entity.platform, {}
        ).get(hm_entity.parameter):
            return param_description

    elif isinstance(hm_entity, CustomEntity):
        if custom_description := _ENTITY_DESCRIPTION_DEVICE.get(
            hm_entity.platform, {}
        ).get(hm_entity.device_type):
            return custom_description

    if hasattr(hm_entity, "platform"):
        return _DEFAULT_DESCRIPTION.get(hm_entity.platform, None)
    return None
