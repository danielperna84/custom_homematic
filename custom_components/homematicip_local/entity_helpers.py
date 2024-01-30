"""Support for Homematic(IP) Local sensors."""
from __future__ import annotations

from collections.abc import Mapping
import dataclasses
import logging
from typing import Final

from hahomematic.const import HmPlatform
from hahomematic.platforms.custom.entity import CustomEntity
from hahomematic.platforms.generic.entity import GenericEntity
from hahomematic.platforms.hub.entity import GenericHubEntity
from hahomematic.support import element_matches_key

from homeassistant.components.binary_sensor import BinarySensorDeviceClass
from homeassistant.components.cover import CoverDeviceClass, CoverEntityDescription
from homeassistant.components.number import NumberDeviceClass
from homeassistant.components.select import SelectEntityDescription
from homeassistant.components.sensor import SensorDeviceClass, SensorStateClass
from homeassistant.components.siren import SirenEntityDescription
from homeassistant.components.switch import SwitchDeviceClass, SwitchEntityDescription
from homeassistant.const import (
    CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
    CONCENTRATION_PARTS_PER_MILLION,
    DEGREE,
    LIGHT_LUX,
    PERCENTAGE,
    SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
    EntityCategory,
    UnitOfElectricCurrent,
    UnitOfElectricPotential,
    UnitOfEnergy,
    UnitOfFrequency,
    UnitOfLength,
    UnitOfPower,
    UnitOfPressure,
    UnitOfSpeed,
    UnitOfTemperature,
    UnitOfTime,
    UnitOfVolume,
)
from homeassistant.helpers.entity import EntityDescription
from homeassistant.helpers.typing import UNDEFINED, UndefinedType

from .const import HmNameSource
from .support import (
    HmBinarySensorEntityDescription,
    HmButtonEntityDescription,
    HmEntityDescription,
    HmGenericEntity,
    HmNumberEntityDescription,
    HmSensorEntityDescription,
)

_LOGGER = logging.getLogger(__name__)

CONCENTRATION_CM3: Final = "1/cm\u00b3"  # HmIP-SFD
CONCENTRATION_GRAMS_PER_CUBIC_METER: Final = "g/m³"  # HB-UNI-Sensor-THPD-BME280
LENGTH_MICROMETER: Final = "\u00b5m"  # HmIP-SFD


_NUMBER_DESCRIPTIONS_BY_PARAM: Mapping[str | tuple[str, ...], EntityDescription] = {
    "FREQUENCY": HmNumberEntityDescription(
        key="FREQUENCY",
        device_class=NumberDeviceClass.FREQUENCY,
        native_unit_of_measurement=UnitOfFrequency.HERTZ,
    ),
    ("LEVEL", "LEVEL_2"): HmNumberEntityDescription(
        key="LEVEL",
        multiplier=100,
        native_unit_of_measurement=PERCENTAGE,
    ),
}

_NUMBER_DESCRIPTIONS_BY_DEVICE_AND_PARAM: Mapping[
    tuple[str | tuple[str, ...], str], EntityDescription
] = {
    (
        ("HmIP-eTRV", "HmIP-HEATING"),
        "LEVEL",
    ): HmNumberEntityDescription(
        key="LEVEL",
        icon="mdi:pipe-valve",
        multiplier=100,
        native_unit_of_measurement=PERCENTAGE,
        entity_registry_enabled_default=False,
    ),
    ("HMW-IO-12-Sw14-DR", "FREQUENCY"): HmNumberEntityDescription(
        key="FREQUENCY",
        icon="mdi:sine-wave",
        native_unit_of_measurement="mHz",
    ),
}

_SENSOR_DESCRIPTIONS_BY_PARAM: Mapping[str | tuple[str, ...], EntityDescription] = {
    "AIR_PRESSURE": HmSensorEntityDescription(
        key="AIR_PRESSURE",
        native_unit_of_measurement=UnitOfPressure.HPA,
        device_class=SensorDeviceClass.PRESSURE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    "BRIGHTNESS": HmSensorEntityDescription(
        key="BRIGHTNESS",
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:invert-colors",
    ),
    "CARRIER_SENSE_LEVEL": HmSensorEntityDescription(
        key="CARRIER_SENSE_LEVEL",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    "CODE_ID": HmSensorEntityDescription(
        key="CODE_ID",
    ),
    "CONCENTRATION": HmSensorEntityDescription(
        key="CONCENTRATION",
        native_unit_of_measurement=CONCENTRATION_PARTS_PER_MILLION,
        device_class=SensorDeviceClass.CO2,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    "CURRENT": HmSensorEntityDescription(
        key="CURRENT",
        native_unit_of_measurement=UnitOfElectricCurrent.MILLIAMPERE,
        device_class=SensorDeviceClass.CURRENT,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    "DEWPOINT": HmSensorEntityDescription(
        key="DEWPOINT",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    ("ACTIVITY_STATE", "DIRECTION"): HmSensorEntityDescription(
        key="DIRECTION",
        device_class=SensorDeviceClass.ENUM,
        icon="mdi:arrow-up-down",
        translation_key="direction",
    ),
    "DOOR_STATE": HmSensorEntityDescription(
        key="DOOR_STATE",
        device_class=SensorDeviceClass.ENUM,
        translation_key="door_state",
    ),
    "DUTY_CYCLE_LEVEL": HmSensorEntityDescription(
        key="DUTY_CYCLE_LEVEL",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    "ENERGY_COUNTER": HmSensorEntityDescription(
        key="ENERGY_COUNTER",
        native_unit_of_measurement=UnitOfEnergy.WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL,
    ),
    "FILLING_LEVEL": HmSensorEntityDescription(
        key="FILLING_LEVEL",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    "FREQUENCY": HmSensorEntityDescription(
        key="FREQUENCY",
        native_unit_of_measurement=UnitOfFrequency.HERTZ,
        device_class=SensorDeviceClass.FREQUENCY,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    "GAS_ENERGY_COUNTER": HmSensorEntityDescription(
        key="GAS_ENERGY_COUNTER",
        native_unit_of_measurement=UnitOfVolume.CUBIC_METERS,
        device_class=SensorDeviceClass.GAS,
        state_class=SensorStateClass.TOTAL,
    ),
    "GAS_POWER": HmSensorEntityDescription(
        key="GAS_POWER",
        native_unit_of_measurement=UnitOfVolume.CUBIC_METERS,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    ("HUMIDITY", "ACTUAL_HUMIDITY"): HmSensorEntityDescription(
        key="HUMIDITY",
        native_unit_of_measurement=PERCENTAGE,
        device_class=SensorDeviceClass.HUMIDITY,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    "IEC_ENERGY_COUNTER": HmSensorEntityDescription(
        key="IEC_ENERGY_COUNTER",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL,
    ),
    "IEC_POWER": HmSensorEntityDescription(
        key="IEC_POWER",
        native_unit_of_measurement=UnitOfPower.WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    (
        "ILLUMINATION",
        "AVERAGE_ILLUMINATION",
        "CURRENT_ILLUMINATION",
        "HIGHEST_ILLUMINATION",
        "LOWEST_ILLUMINATION",
        "LUX",
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
    ("LEVEL", "LEVEL_2"): HmSensorEntityDescription(
        key="LEVEL",
        native_unit_of_measurement=PERCENTAGE,
        multiplier=100,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    "LOCK_STATE": HmSensorEntityDescription(
        key="LOCK_STATE",
        device_class=SensorDeviceClass.ENUM,
        translation_key="lock_state",
    ),
    (
        "MASS_CONCENTRATION_PM_1",
        "MASS_CONCENTRATION_PM_1_24H_AVERAGE",
    ): HmSensorEntityDescription(
        key="MASS_CONCENTRATION_PM_1",
        native_unit_of_measurement=CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
        device_class=SensorDeviceClass.PM1,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    (
        "MASS_CONCENTRATION_PM_10",
        "MASS_CONCENTRATION_PM_10_24H_AVERAGE",
    ): HmSensorEntityDescription(
        key="MASS_CONCENTRATION_PM_10",
        native_unit_of_measurement=CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
        device_class=SensorDeviceClass.PM10,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    (
        "MASS_CONCENTRATION_PM_2_5",
        "MASS_CONCENTRATION_PM_2_5_24H_AVERAGE",
    ): HmSensorEntityDescription(
        key="MASS_CONCENTRATION_PM_2_5",
        native_unit_of_measurement=CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
        device_class=SensorDeviceClass.PM25,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    "NUMBER_CONCENTRATION_PM_1": HmSensorEntityDescription(
        key="NUMBER_CONCENTRATION_PM_1",
        native_unit_of_measurement=CONCENTRATION_CM3,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    "NUMBER_CONCENTRATION_PM_10": HmSensorEntityDescription(
        key="NUMBER_CONCENTRATION_PM_10",
        native_unit_of_measurement=CONCENTRATION_CM3,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    "NUMBER_CONCENTRATION_PM_2_5": HmSensorEntityDescription(
        key="NUMBER_CONCENTRATION_PM_2_5",
        native_unit_of_measurement=CONCENTRATION_CM3,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    "TYPICAL_PARTICLE_SIZE": HmSensorEntityDescription(
        key="TYPICAL_PARTICLE_SIZE",
        native_unit_of_measurement=LENGTH_MICROMETER,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    ("BATTERY_STATE", "OPERATING_VOLTAGE"): HmSensorEntityDescription(
        key="OPERATING_VOLTAGE",
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        device_class=SensorDeviceClass.VOLTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    "POWER": HmSensorEntityDescription(
        key="POWER",
        native_unit_of_measurement=UnitOfPower.WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    "RAIN_COUNTER": HmSensorEntityDescription(
        key="RAIN_COUNTER",
        native_unit_of_measurement=UnitOfLength.MILLIMETERS,
        icon="mdi:weather-rainy",
        state_class=SensorStateClass.TOTAL,
    ),
    ("RSSI_DEVICE", "RSSI_PEER"): HmSensorEntityDescription(
        key="RSSI",
        native_unit_of_measurement=SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    ("ACTUAL_TEMPERATURE", "TEMPERATURE"): HmSensorEntityDescription(
        key="TEMPERATURE",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    "SMOKE_DETECTOR_ALARM_STATUS": HmSensorEntityDescription(
        key="SMOKE_DETECTOR_ALARM_STATUS",
        device_class=SensorDeviceClass.ENUM,
        translation_key="smoke_detector_alarm_status",
    ),
    "SUNSHINEDURATION": HmSensorEntityDescription(
        key="SUNSHINEDURATION",
        native_unit_of_measurement=UnitOfTime.MINUTES,
        icon="mdi:weather-sunny",
        state_class=SensorStateClass.TOTAL,
    ),
    "VALUE": HmSensorEntityDescription(
        key="VALUE",
        state_class=SensorStateClass.MEASUREMENT,
    ),
    "VAPOR_CONCENTRATION": HmSensorEntityDescription(
        key="VAPOR_CONCENTRATION",
        native_unit_of_measurement=CONCENTRATION_GRAMS_PER_CUBIC_METER,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    "VOLTAGE": HmSensorEntityDescription(
        key="VOLTAGE",
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        device_class=SensorDeviceClass.VOLTAGE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    (
        "WIND_DIR",
        "WIND_DIR_RANGE",
        "WIND_DIRECTION",
        "WIND_DIRECTION_RANGE",
    ): HmSensorEntityDescription(
        key="WIND_DIR",
        native_unit_of_measurement=DEGREE,
        icon="mdi:windsock",
        state_class=SensorStateClass.MEASUREMENT,
    ),
    "WIND_SPEED": HmSensorEntityDescription(
        key="WIND_SPEED",
        native_unit_of_measurement=UnitOfSpeed.KILOMETERS_PER_HOUR,
        device_class=SensorDeviceClass.WIND_SPEED,
        icon="mdi:weather-windy",
        state_class=SensorStateClass.MEASUREMENT,
    ),
}

_SENSOR_DESCRIPTIONS_BY_DEVICE_AND_PARAM: Mapping[
    tuple[str | tuple[str, ...], str], EntityDescription
] = {
    (
        "HmIP-WKP",
        "CODE_STATE",
    ): HmSensorEntityDescription(
        key="WKP_CODE_STATE",
        device_class=SensorDeviceClass.ENUM,
        translation_key="wkp_code_state",
    ),
    (
        ("HmIP-SRH", "HM-Sec-RHS", "HM-Sec-xx", "ZEL STG RM FDK"),
        "STATE",
    ): HmSensorEntityDescription(
        key="SRH_STATE",
        device_class=SensorDeviceClass.ENUM,
        translation_key="srh_state",
    ),
    ("HM-Sec-Win", "STATUS"): HmSensorEntityDescription(
        key="SEC-WIN_STATUS",
        device_class=SensorDeviceClass.ENUM,
        icon="mdi:battery-50",
        translation_key="sec_win_status",
    ),
    ("HM-Sec-Win", "DIRECTION"): HmSensorEntityDescription(
        key="SEC-WIN_DIRECTION",
        device_class=SensorDeviceClass.ENUM,
        icon="mdi:arrow-up-down",
        translation_key="sec_direction",
    ),
    ("HM-Sec-Win", "ERROR"): HmSensorEntityDescription(
        key="SEC-WIN_ERROR",
        device_class=SensorDeviceClass.ENUM,
        icon="mdi:lock-alert",
        translation_key="sec_win_error",
    ),
    ("HM-Sec-Key", "DIRECTION"): HmSensorEntityDescription(
        key="SEC-KEY_DIRECTION",
        device_class=SensorDeviceClass.ENUM,
        icon="mdi:arrow-up-down",
        translation_key="sec_direction",
    ),
    ("HM-Sec-Key", "ERROR"): HmSensorEntityDescription(
        key="SEC-KEY_ERROR",
        device_class=SensorDeviceClass.ENUM,
        icon="mdi:lock-alert",
        translation_key="sec_key_error",
    ),
    (
        ("HmIP-eTRV", "HmIP-HEATING"),
        "LEVEL",
    ): HmSensorEntityDescription(
        key="LEVEL",
        icon="mdi:pipe-valve",
        native_unit_of_measurement=PERCENTAGE,
        multiplier=100,
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
    ),
    ("HMW-IO-12-Sw14-DR", "FREQUENCY"): HmSensorEntityDescription(
        key="FREQUENCY",
        icon="mdi:sine-wave",
        native_unit_of_measurement="mHz",
    ),
    (("HM-CC-RT-DN", "HM-CC-VD"), "VALVE_STATE"): HmSensorEntityDescription(
        key="VALVE_STATE",
        native_unit_of_measurement=PERCENTAGE,
        icon="mdi:pipe-valve",
        state_class=SensorStateClass.MEASUREMENT,
    ),
}

_SENSOR_DESCRIPTIONS_BY_UNIT: Mapping[str, EntityDescription] = {
    PERCENTAGE: HmSensorEntityDescription(
        key="PERCENTAGE",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    UnitOfPressure.BAR: HmSensorEntityDescription(
        key="PRESSURE_BAR",
        native_unit_of_measurement=UnitOfPressure.BAR,
        device_class=SensorDeviceClass.PRESSURE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    UnitOfTemperature.CELSIUS: HmSensorEntityDescription(
        key="TEMPERATURE",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    CONCENTRATION_GRAMS_PER_CUBIC_METER: HmSensorEntityDescription(
        key="CONCENTRATION_GRAMS_PER_CUBIC_METER",
        native_unit_of_measurement=CONCENTRATION_GRAMS_PER_CUBIC_METER,
        state_class=SensorStateClass.MEASUREMENT,
    ),
}

_BINARY_SENSOR_DESCRIPTIONS_BY_PARAM: Mapping[str | tuple[str, ...], EntityDescription] = {
    "ALARMSTATE": HmBinarySensorEntityDescription(
        key="ALARMSTATE",
        device_class=BinarySensorDeviceClass.SAFETY,
    ),
    "ACOUSTIC_ALARM_ACTIVE": HmBinarySensorEntityDescription(
        key="ACOUSTIC_ALARM_ACTIVE",
        device_class=BinarySensorDeviceClass.SAFETY,
    ),
    ("BLOCKED_PERMANENT", "BLOCKED_TEMPORARY"): HmBinarySensorEntityDescription(
        key="BLOCKED",
        device_class=BinarySensorDeviceClass.PROBLEM,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    "BURST_LIMIT_WARNING": HmBinarySensorEntityDescription(
        key="BURST_LIMIT_WARNING",
        device_class=BinarySensorDeviceClass.PROBLEM,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    ("DUTYCYCLE", "DUTY_CYCLE"): HmBinarySensorEntityDescription(
        key="DUTY_CYCLE",
        device_class=BinarySensorDeviceClass.PROBLEM,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    "DEW_POINT_ALARM": HmBinarySensorEntityDescription(
        key="DEW_POINT_ALARM",
        device_class=BinarySensorDeviceClass.PROBLEM,
        entity_registry_enabled_default=False,
    ),
    "EMERGENCY_OPERATION": HmBinarySensorEntityDescription(
        key="EMERGENCY_OPERATION",
        device_class=BinarySensorDeviceClass.SAFETY,
        entity_registry_enabled_default=False,
    ),
    "ERROR_JAMMED": HmBinarySensorEntityDescription(
        key="ERROR_JAMMED",
        device_class=BinarySensorDeviceClass.PROBLEM,
        entity_registry_enabled_default=False,
    ),
    "HEATER_STATE": HmBinarySensorEntityDescription(
        key="HEATER_STATE",
        device_class=BinarySensorDeviceClass.HEAT,
    ),
    ("LOWBAT", "LOW_BAT", "LOWBAT_SENSOR"): HmBinarySensorEntityDescription(
        key="LOW_BAT",
        device_class=BinarySensorDeviceClass.BATTERY,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    "MOISTURE_DETECTED": HmBinarySensorEntityDescription(
        key="MOISTURE_DETECTED",
        device_class=BinarySensorDeviceClass.MOISTURE,
    ),
    "MOTION": HmBinarySensorEntityDescription(
        key="MOTION",
        device_class=BinarySensorDeviceClass.MOTION,
    ),
    "OPTICAL_ALARM_ACTIVE": HmBinarySensorEntityDescription(
        key="OPTICAL_ALARM_ACTIVE",
        device_class=BinarySensorDeviceClass.SAFETY,
    ),
    "POWER_MAINS_FAILURE": HmBinarySensorEntityDescription(
        key="POWER_MAINS_FAILURE",
        device_class=BinarySensorDeviceClass.POWER,
    ),
    "PRESENCE_DETECTION_STATE": HmBinarySensorEntityDescription(
        key="PRESENCE_DETECTION_STATE",
        device_class=BinarySensorDeviceClass.PRESENCE,
    ),
    ("PROCESS", "WORKING"): HmBinarySensorEntityDescription(
        key="PROCESS",
        device_class=BinarySensorDeviceClass.RUNNING,
    ),
    "RAINING": HmBinarySensorEntityDescription(
        key="RAINING",
        device_class=BinarySensorDeviceClass.MOISTURE,
    ),
    ("SABOTAGE", "SABOTAGE_STICKY"): HmBinarySensorEntityDescription(
        key="SABOTAGE",
        device_class=BinarySensorDeviceClass.TAMPER,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    "WATERLEVEL_DETECTED": HmBinarySensorEntityDescription(
        key="WATERLEVEL_DETECTED",
        device_class=BinarySensorDeviceClass.MOISTURE,
    ),
    "WINDOW_STATE": HmBinarySensorEntityDescription(
        key="WINDOW_STATE",
        device_class=BinarySensorDeviceClass.WINDOW,
    ),
}

_BINARY_SENSOR_DESCRIPTIONS_BY_DEVICE_AND_PARAM: Mapping[
    tuple[str | tuple[str, ...], str], EntityDescription
] = {
    ("HmIP-DSD-PCB", "STATE"): HmBinarySensorEntityDescription(
        key="STATE",
        device_class=BinarySensorDeviceClass.OCCUPANCY,
    ),
    (
        ("HmIP-SCI", "HmIP-FCI1", "HmIP-FCI6"),
        "STATE",
    ): HmBinarySensorEntityDescription(
        key="STATE",
        device_class=BinarySensorDeviceClass.OPENING,
    ),
    ("HM-Sec-SD", "STATE"): HmBinarySensorEntityDescription(
        key="STATE",
        device_class=BinarySensorDeviceClass.SMOKE,
    ),
    (
        (
            "HmIP-SWD",
            "HmIP-SWDO",
            "HmIP-SWDM",
            "HM-Sec-SC",
            "HM-SCI-3-FM",
            "ZEL STG RM FFK",
        ),
        "STATE",
    ): HmBinarySensorEntityDescription(
        key="STATE",
        device_class=BinarySensorDeviceClass.WINDOW,
    ),
    ("HM-Sen-RD-O", "STATE"): HmBinarySensorEntityDescription(
        key="STATE",
        device_class=BinarySensorDeviceClass.MOISTURE,
    ),
    ("HM-Sec-Win", "WORKING"): HmBinarySensorEntityDescription(
        key="WORKING",
        device_class=BinarySensorDeviceClass.RUNNING,
        entity_registry_enabled_default=False,
    ),
}

_BUTTOM_DESCRIPTIONS_BY_PARAM: Mapping[str | tuple[str, ...], EntityDescription] = {
    "RESET_MOTION": HmButtonEntityDescription(
        key="RESET_MOTION",
        entity_category=EntityCategory.CONFIG,
        entity_registry_enabled_default=False,
    ),
    "RESET_PRESENCE": HmButtonEntityDescription(
        key="RESET_PRESENCE",
        entity_category=EntityCategory.CONFIG,
        entity_registry_enabled_default=False,
    ),
}

_COVER_DESCRIPTIONS_BY_DEVICE: Mapping[str | tuple[str, ...], EntityDescription] = {
    ("HmIP-BBL", "HmIP-FBL", "HmIP-DRBLI4", "HmIPW-DRBL4"): CoverEntityDescription(
        key="BLIND",
        device_class=CoverDeviceClass.BLIND,
    ),
    ("HmIP-BROLL", "HmIP-FROLL"): CoverEntityDescription(
        key="SHUTTER",
        device_class=CoverDeviceClass.SHUTTER,
    ),
    "HmIP-HDM1": CoverEntityDescription(
        key="HmIP-HDM1",
        device_class=CoverDeviceClass.SHADE,
    ),
    ("HmIP-MOD-HO", "HmIP-MOD-TM"): CoverEntityDescription(
        key="GARAGE-HO",
        device_class=CoverDeviceClass.GARAGE,
    ),
    "HM-Sec-Win": CoverEntityDescription(
        key="HM-Sec-Win",
        device_class=CoverDeviceClass.WINDOW,
    ),
}

_SIREN_DESCRIPTIONS_BY_DEVICE: Mapping[str | tuple[str, ...], EntityDescription] = {
    "HmIP-SWSD": SirenEntityDescription(
        key="SWSD",
        entity_registry_enabled_default=False,
    ),
}

_SWITCH_DESCRIPTIONS_BY_DEVICE: Mapping[str | tuple[str, ...], EntityDescription] = {
    "HmIP-PS": SwitchEntityDescription(
        key="OUTLET",
        device_class=SwitchDeviceClass.OUTLET,
    ),
}

_SWITCH_DESCRIPTIONS_BY_PARAM: Mapping[str | tuple[str, ...], EntityDescription] = {
    "INHIBIT": SwitchEntityDescription(
        key="INHIBIT",
        device_class=SwitchDeviceClass.SWITCH,
        entity_registry_enabled_default=False,
    ),
    ("MOTION_DETECTION_ACTIVE", "PRESENCE_DETECTION_ACTIVE"): SwitchEntityDescription(
        key="MOTION_DETECTION_ACTIVE",
        device_class=SwitchDeviceClass.SWITCH,
        entity_category=EntityCategory.CONFIG,
        entity_registry_enabled_default=False,
    ),
}

_ENTITY_DESCRIPTION_BY_DEVICE: Mapping[
    HmPlatform, Mapping[str | tuple[str, ...], EntityDescription]
] = {
    HmPlatform.COVER: _COVER_DESCRIPTIONS_BY_DEVICE,
    HmPlatform.SIREN: _SIREN_DESCRIPTIONS_BY_DEVICE,
    HmPlatform.SWITCH: _SWITCH_DESCRIPTIONS_BY_DEVICE,
}

_ENTITY_DESCRIPTION_BY_PARAM: Mapping[
    HmPlatform, Mapping[str | tuple[str, ...], EntityDescription]
] = {
    HmPlatform.BINARY_SENSOR: _BINARY_SENSOR_DESCRIPTIONS_BY_PARAM,
    HmPlatform.BUTTON: _BUTTOM_DESCRIPTIONS_BY_PARAM,
    HmPlatform.NUMBER: _NUMBER_DESCRIPTIONS_BY_PARAM,
    HmPlatform.SENSOR: _SENSOR_DESCRIPTIONS_BY_PARAM,
    HmPlatform.SWITCH: _SWITCH_DESCRIPTIONS_BY_PARAM,
}

_ENTITY_DESCRIPTION_BY_DEVICE_AND_PARAM: Mapping[
    HmPlatform, Mapping[tuple[str | tuple[str, ...], str], EntityDescription]
] = {
    HmPlatform.BINARY_SENSOR: _BINARY_SENSOR_DESCRIPTIONS_BY_DEVICE_AND_PARAM,
    HmPlatform.NUMBER: _NUMBER_DESCRIPTIONS_BY_DEVICE_AND_PARAM,
    HmPlatform.SENSOR: _SENSOR_DESCRIPTIONS_BY_DEVICE_AND_PARAM,
}


_DEFAULT_PLATFORM_DESCRIPTION: Mapping[HmPlatform, EntityDescription] = {
    HmPlatform.BUTTON: HmButtonEntityDescription(
        key="button_default",
        icon="mdi:gesture-tap",
        entity_registry_enabled_default=False,
    ),
    HmPlatform.SWITCH: SwitchEntityDescription(
        key="switch_default",
        device_class=SwitchDeviceClass.SWITCH,
    ),
    HmPlatform.SELECT: SelectEntityDescription(
        key="select_default", entity_category=EntityCategory.CONFIG
    ),
    HmPlatform.HUB_BUTTON: HmButtonEntityDescription(
        key="hub_button_default",
        icon="mdi:gesture-tap",
        entity_registry_enabled_default=False,
    ),
    HmPlatform.HUB_SWITCH: SwitchEntityDescription(
        key="hub_switch_default",
        device_class=SwitchDeviceClass.SWITCH,
    ),
}


def get_entity_description(
    hm_entity: HmGenericEntity | GenericHubEntity,
) -> EntityDescription | None:
    """Get the entity_description."""
    if entity_desc := _find_entity_description(hm_entity=hm_entity):
        name, translation_key = get_name_and_translation_key(
            hm_entity=hm_entity, entity_desc=entity_desc
        )
        enabled_default = (
            hm_entity.enabled_default if entity_desc.entity_registry_enabled_default else False
        )
        return dataclasses.replace(
            entity_desc,
            name=name,
            translation_key=translation_key,
            has_entity_name=True,
            entity_registry_enabled_default=enabled_default,
        )

    return None


def get_name_and_translation_key(
    hm_entity: HmGenericEntity | GenericHubEntity,
    entity_desc: EntityDescription,
) -> tuple[str | UndefinedType | None, str | None]:
    """Get the name and translation_key."""
    if isinstance(hm_entity, GenericEntity):
        if isinstance(entity_desc, HmEntityDescription) and entity_desc.translation_key is None:
            if entity_desc.name_source == HmNameSource.PARAMETER:
                return None, hm_entity.parameter.lower()
            if entity_desc.name_source == HmNameSource.DEVICE_CLASS:
                return UNDEFINED, None

        if entity_desc.translation_key is None:
            return None, hm_entity.parameter.lower()
        return None, entity_desc.translation_key

    # custom entities use the customizable name from the CCU WebUI,
    # that does not need to be translated in HA
    return hm_entity.name, None


def _find_entity_description(
    hm_entity: HmGenericEntity | GenericHubEntity,
) -> EntityDescription | None:
    """Find the entity_description for platform."""
    if isinstance(hm_entity, GenericEntity):
        if entity_desc := _get_entity_description_by_device_type_and_param(hm_entity=hm_entity):
            return entity_desc

        if entity_desc := _get_entity_description_by_param(hm_entity=hm_entity):
            return entity_desc

        if (
            hm_entity.platform == HmPlatform.SENSOR
            and hm_entity.unit
            and (entity_desc := _SENSOR_DESCRIPTIONS_BY_UNIT.get(hm_entity.unit))
        ):
            return entity_desc

    if isinstance(hm_entity, CustomEntity) and (
        entity_desc := _get_entity_description_by_device_type(hm_entity=hm_entity)
    ):
        return entity_desc

    return _DEFAULT_PLATFORM_DESCRIPTION.get(hm_entity.platform)


def _get_entity_description_by_device_type_and_param(
    hm_entity: GenericEntity,
) -> EntityDescription | None:
    """Get entity_description by device_type and parameter."""
    if platform_device_and_param_descriptions := _ENTITY_DESCRIPTION_BY_DEVICE_AND_PARAM.get(  # noqa: E501
        hm_entity.platform
    ):
        for data, entity_desc in platform_device_and_param_descriptions.items():
            if data[1] == hm_entity.parameter and (
                element_matches_key(
                    search_elements=data[0],
                    compare_with=hm_entity.device.device_type,
                )
            ):
                return entity_desc
    return None


def _get_entity_description_by_param(
    hm_entity: GenericEntity,
) -> EntityDescription | None:
    """Get entity_description by device_type and parameter."""
    if platform_param_descriptions := _ENTITY_DESCRIPTION_BY_PARAM.get(hm_entity.platform):
        for params, entity_desc in platform_param_descriptions.items():
            if _param_in_list(params=params, parameter=hm_entity.parameter):
                return entity_desc
    return None


def _get_entity_description_by_device_type(
    hm_entity: HmGenericEntity,
) -> EntityDescription | None:
    """Get entity_description by device_type."""
    if platform_device_descriptions := _ENTITY_DESCRIPTION_BY_DEVICE.get(hm_entity.platform):
        for devices, entity_desc in platform_device_descriptions.items():
            if element_matches_key(
                search_elements=devices,
                compare_with=hm_entity.device.device_type,
            ):
                return entity_desc
    return None


def _param_in_list(params: str | tuple[str, ...], parameter: str) -> bool:
    """Return if parameter is in set."""
    if isinstance(params, str):
        return parameter.lower() == params.lower()
    if isinstance(params, tuple):
        for device in params:
            if parameter.lower() == device.lower():
                return True
    return False
