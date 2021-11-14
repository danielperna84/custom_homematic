"""Support for HomeMatic sensors."""
from __future__ import annotations

import logging
from copy import copy

from homeassistant.components.binary_sensor import (
    DEVICE_CLASS_BATTERY,
    DEVICE_CLASS_HEAT,
    DEVICE_CLASS_MOISTURE,
    DEVICE_CLASS_MOTION,
    DEVICE_CLASS_PRESENCE,
    DEVICE_CLASS_PROBLEM,
    DEVICE_CLASS_SAFETY,
    DEVICE_CLASS_WINDOW,
    BinarySensorEntityDescription,
)
from homeassistant.components.sensor import (
    STATE_CLASS_MEASUREMENT,
    STATE_CLASS_TOTAL_INCREASING,
    SensorEntityDescription,
)
from homeassistant.const import (
    CONCENTRATION_PARTS_PER_MILLION,
    DEGREE,
    DEVICE_CLASS_CO2,
    DEVICE_CLASS_CURRENT,
    DEVICE_CLASS_ENERGY,
    DEVICE_CLASS_GAS,
    DEVICE_CLASS_HUMIDITY,
    DEVICE_CLASS_ILLUMINANCE,
    DEVICE_CLASS_POWER,
    DEVICE_CLASS_PRESSURE,
    DEVICE_CLASS_TEMPERATURE,
    DEVICE_CLASS_VOLTAGE,
    ELECTRIC_CURRENT_MILLIAMPERE,
    ELECTRIC_POTENTIAL_VOLT,
    ENERGY_WATT_HOUR,
    ENTITY_CATEGORY_DIAGNOSTIC,
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


_SENSOR_DESCRIPTIONS: dict[str, SensorEntityDescription] = {
    "HUMIDITY": SensorEntityDescription(
        key="HUMIDITY",
        native_unit_of_measurement=PERCENTAGE,
        device_class=DEVICE_CLASS_HUMIDITY,
        state_class=STATE_CLASS_MEASUREMENT,
    ),
    "ACTUAL_TEMPERATURE": SensorEntityDescription(
        key="ACTUAL_TEMPERATURE",
        native_unit_of_measurement=TEMP_CELSIUS,
        device_class=DEVICE_CLASS_TEMPERATURE,
        state_class=STATE_CLASS_MEASUREMENT,
    ),
    "TEMPERATURE": SensorEntityDescription(
        key="TEMPERATURE",
        native_unit_of_measurement=TEMP_CELSIUS,
        device_class=DEVICE_CLASS_TEMPERATURE,
        state_class=STATE_CLASS_MEASUREMENT,
    ),
    "LUX": SensorEntityDescription(
        key="LUX",
        native_unit_of_measurement=LIGHT_LUX,
        device_class=DEVICE_CLASS_ILLUMINANCE,
        state_class=STATE_CLASS_MEASUREMENT,
    ),
    "CURRENT_ILLUMINATION": SensorEntityDescription(
        key="CURRENT_ILLUMINATION",
        native_unit_of_measurement=LIGHT_LUX,
        device_class=DEVICE_CLASS_ILLUMINANCE,
        state_class=STATE_CLASS_MEASUREMENT,
    ),
    "ILLUMINATION": SensorEntityDescription(
        key="ILLUMINATION",
        native_unit_of_measurement=LIGHT_LUX,
        device_class=DEVICE_CLASS_ILLUMINANCE,
        state_class=STATE_CLASS_MEASUREMENT,
    ),
    "AVERAGE_ILLUMINATION": SensorEntityDescription(
        key="AVERAGE_ILLUMINATION",
        native_unit_of_measurement=LIGHT_LUX,
        device_class=DEVICE_CLASS_ILLUMINANCE,
        state_class=STATE_CLASS_MEASUREMENT,
    ),
    "LOWEST_ILLUMINATION": SensorEntityDescription(
        key="LOWEST_ILLUMINATION",
        native_unit_of_measurement=LIGHT_LUX,
        device_class=DEVICE_CLASS_ILLUMINANCE,
        state_class=STATE_CLASS_MEASUREMENT,
    ),
    "HIGHEST_ILLUMINATION": SensorEntityDescription(
        key="HIGHEST_ILLUMINATION",
        native_unit_of_measurement=LIGHT_LUX,
        device_class=DEVICE_CLASS_ILLUMINANCE,
        state_class=STATE_CLASS_MEASUREMENT,
    ),
    "POWER": SensorEntityDescription(
        key="POWER",
        native_unit_of_measurement=POWER_WATT,
        device_class=DEVICE_CLASS_POWER,
        state_class=STATE_CLASS_MEASUREMENT,
    ),
    "IEC_POWER": SensorEntityDescription(
        key="IEC_POWER",
        native_unit_of_measurement=POWER_WATT,
        device_class=DEVICE_CLASS_POWER,
        state_class=STATE_CLASS_MEASUREMENT,
    ),
    "CURRENT": SensorEntityDescription(
        key="CURRENT",
        native_unit_of_measurement=ELECTRIC_CURRENT_MILLIAMPERE,
        device_class=DEVICE_CLASS_CURRENT,
        state_class=STATE_CLASS_MEASUREMENT,
    ),
    "CONCENTRATION": SensorEntityDescription(
        key="CONCENTRATION",
        native_unit_of_measurement=CONCENTRATION_PARTS_PER_MILLION,
        device_class=DEVICE_CLASS_CO2,
        state_class=STATE_CLASS_MEASUREMENT,
    ),
    "ENERGY_COUNTER": SensorEntityDescription(
        key="ENERGY_COUNTER",
        native_unit_of_measurement=ENERGY_WATT_HOUR,
        device_class=DEVICE_CLASS_ENERGY,
        state_class=STATE_CLASS_TOTAL_INCREASING,
    ),
    "IEC_ENERGY_COUNTER": SensorEntityDescription(
        key="IEC_ENERGY_COUNTER",
        native_unit_of_measurement=ENERGY_WATT_HOUR,
        device_class=DEVICE_CLASS_ENERGY,
        state_class=STATE_CLASS_TOTAL_INCREASING,
    ),
    "VOLTAGE": SensorEntityDescription(
        key="VOLTAGE",
        native_unit_of_measurement=ELECTRIC_POTENTIAL_VOLT,
        device_class=DEVICE_CLASS_VOLTAGE,
        state_class=STATE_CLASS_MEASUREMENT,
    ),
    "OPERATING_VOLTAGE": SensorEntityDescription(
        key="OPERATING_VOLTAGE",
        native_unit_of_measurement=ELECTRIC_POTENTIAL_VOLT,
        device_class=DEVICE_CLASS_VOLTAGE,
        state_class=STATE_CLASS_MEASUREMENT,
        entity_category=ENTITY_CATEGORY_DIAGNOSTIC,
    ),
    "GAS_POWER": SensorEntityDescription(
        key="GAS_POWER",
        native_unit_of_measurement=VOLUME_CUBIC_METERS,
        device_class=DEVICE_CLASS_GAS,
        state_class=STATE_CLASS_MEASUREMENT,
    ),
    "GAS_ENERGY_COUNTER": SensorEntityDescription(
        key="GAS_ENERGY_COUNTER",
        native_unit_of_measurement=VOLUME_CUBIC_METERS,
        device_class=DEVICE_CLASS_GAS,
        state_class=STATE_CLASS_TOTAL_INCREASING,
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
        device_class=DEVICE_CLASS_PRESSURE,
        state_class=STATE_CLASS_MEASUREMENT,
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

_SENSOR_DESCRIPTIONS_BY_DEVICE: dict[(str, str), SensorEntityDescription] = {
    ("HmIP-SRH", "STATE"): SensorEntityDescription(
        key="STATE",
        device_class=DEVICE_CLASS_WINDOW,
    ),
}


_BINARY_SENSOR_DESCRIPTIONS: dict[str, BinarySensorEntityDescription] = {
    "ALARMSTATE": BinarySensorEntityDescription(
        key="ALARMSTATE",
        device_class=DEVICE_CLASS_SAFETY,
    ),
    "DUTY_CYCLE": BinarySensorEntityDescription(
        key="DUTY_CYCLE",
        device_class=DEVICE_CLASS_PROBLEM,
        entity_category=ENTITY_CATEGORY_DIAGNOSTIC,
    ),
    "DUTYCYCLE": BinarySensorEntityDescription(
        key="DUTYCYCLE",
        device_class=DEVICE_CLASS_PROBLEM,
        entity_category=ENTITY_CATEGORY_DIAGNOSTIC,
    ),
    "HEATER_STATE": BinarySensorEntityDescription(
        key="HEATER_STATE",
        device_class=DEVICE_CLASS_HEAT,
    ),
    "LOW_BAT": BinarySensorEntityDescription(
        key="LOW_BAT",
        device_class=DEVICE_CLASS_BATTERY,
        entity_category=ENTITY_CATEGORY_DIAGNOSTIC,
    ),
    "LOWBAT": BinarySensorEntityDescription(
        key="LOWBAT",
        device_class=DEVICE_CLASS_BATTERY,
        entity_category=ENTITY_CATEGORY_DIAGNOSTIC,
    ),
    "MOISTURE_DETECTED": BinarySensorEntityDescription(
        key="MOISTURE_DETECTED",
        device_class=DEVICE_CLASS_MOISTURE,
    ),
    "MOTION": BinarySensorEntityDescription(
        key="MOTION",
        device_class=DEVICE_CLASS_MOTION,
    ),
    "PRESENCE_DETECTION_STATE": BinarySensorEntityDescription(
        key="PRESENCE_DETECTION_STATE",
        device_class=DEVICE_CLASS_PRESENCE,
    ),
    "RAINING": BinarySensorEntityDescription(
        key="RAINING",
        device_class=DEVICE_CLASS_MOISTURE,
    ),
    "SABOTAGE": BinarySensorEntityDescription(
        key="SABOTAGE",
        device_class=DEVICE_CLASS_SAFETY,
        entity_category=ENTITY_CATEGORY_DIAGNOSTIC,
    ),
    "WATERLEVEL_DETECTED": BinarySensorEntityDescription(
        key="WATERLEVEL_DETECTED",
        device_class=DEVICE_CLASS_MOISTURE,
    ),
    "WINDOW_STATE": BinarySensorEntityDescription(
        key="WINDOW_STATE",
        device_class=DEVICE_CLASS_WINDOW,
    ),
}

_BINARY_SENSOR_DESCRIPTIONS_BY_DEVICE: dict[(str, str), BinarySensorEntityDescription] = {
    ("HmIP-SWDO-I", "STATE"): BinarySensorEntityDescription(
        key="STATE",
        device_class=DEVICE_CLASS_WINDOW,
    ),
    ("HmIP-SWDO", "STATE"): BinarySensorEntityDescription(
        key="STATE",
        device_class=DEVICE_CLASS_WINDOW,
    ),
    ("HmIP-SCI", "STATE"): BinarySensorEntityDescription(
        key="STATE",
        device_class=DEVICE_CLASS_SAFETY,
    ),
}


_DEFAULT_SENSOR_DESCRIPTION = EntityDescription(
    key="",
    entity_registry_enabled_default=True,
)


def get_binary_sensor_entity_description(
    device_type: str, parameter: str
) -> BinarySensorEntityDescription | None:
    """Get the entity_desription for binary_sensor."""
    description = _BINARY_SENSOR_DESCRIPTIONS_BY_DEVICE.get((device_type, parameter))
    if description:
        return description
    if parameter in ['STATE']:
        return None
    description = _BINARY_SENSOR_DESCRIPTIONS.get(parameter)
    if description:
        return description
    return None


def get_sensor_entity_description(device_type: str, parameter: str) -> SensorEntityDescription | None:
    """Get the entity_desription for sensor."""
    description = _SENSOR_DESCRIPTIONS_BY_DEVICE.get((device_type, parameter))
    if description:
        return description
    description = _SENSOR_DESCRIPTIONS.get(parameter)
    if description:
        return description

    if parameter in ['STATE']:
        return None
    return None


def get_default_description() -> EntityDescription:
    return copy(_DEFAULT_SENSOR_DESCRIPTION)
