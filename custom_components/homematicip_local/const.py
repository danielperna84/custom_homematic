"""Constants."""
from __future__ import annotations

from datetime import timedelta

from hahomematic.const import AVAILABLE_HM_PLATFORMS

from homeassistant.backports.enum import StrEnum
from homeassistant.const import Platform

DOMAIN = "homematicip_local"
MANUFACTURER = "eQ-3"
HMIP_LOCAL_MIN_VERSION = "2022.9"
IDENTIFIER_SEPARATOR = "@"
HOMEMATIC_HUB_DEVICE_CLASS = "homematic_hub"

ATTR_INSTANCE_NAME = "instance_name"
ATTR_INTERFACE = "interface"
ATTR_PARAMSET = "paramset"
ATTR_PARAMSET_KEY = "paramset_key"
ATTR_PATH = "path"
ATTR_RX_MODE = "rx_mode"
ATTR_VALUE_TYPE = "value_type"
ATTR_VALUE_STATE = "value_state"

ATTR_NAME = "name"
ATTR_INTERFACE_ID = "interface_id"
ATTR_ADDRESS = "address"
ATTR_MODEL = "model"
ATTR_FUNCTION = "function"
ATTR_PARAMETER = "parameter"
ATTR_ENTITY_TYPE = "entity_type"

CONF_INTERFACE_ID = "interface_id"
CONF_EVENT_TYPE = "event_type"
CONF_SUBTYPE = "subtype"

DEFAULT_CALLBACK_PORT = "default_callback_port"
CONTROL_UNITS = "control_units"

EVENT_DEVICE_AVAILABILITY = "homematic.device_availability"
EVENT_DEVICE_TYPE = "device_type"
EVENT_DATA_IDENTIFIER = "identifier"
EVENT_DATA_TITLE = "title"
EVENT_DATA_MESSAGE = "message"
EVENT_DATA_UNAVAILABLE = "unavailable"

SERVICE_PUT_PARAMSET = "put_paramset"
SERVICE_SET_DEVICE_VALUE = "set_device_value"
SERVICE_SET_INSTALL_MODE = "set_install_mode"
SERVICE_SET_VARIABLE_VALUE = "set_variable_value"
SERVICE_VIRTUAL_KEY = "virtual_key"

SYSVAR_SCAN_INTERVAL = timedelta(seconds=30)


class HmEntityState(StrEnum):
    """Enum with homematic entity states."""

    NOT_VALID = "not valid"
    RESTORED = "restored"
    UNCERTAIN = "uncertain"
    VALID = "valid"


class HmEntityType(StrEnum):
    """Enum with hahomematic entity types."""

    GENERIC = "generic"
    CUSTOM = "custom"


def _get_hmip_local_platforms() -> list[str]:
    """Return relevant Homematic(IP) Local platforms."""
    platforms = [entry.value for entry in Platform]
    hm_platforms = [entry.value for entry in AVAILABLE_HM_PLATFORMS]
    hmip_local_platforms: list[str] = []
    for hm_platform in hm_platforms:
        if hm_platform in platforms:
            hmip_local_platforms.append(hm_platform)

    return hmip_local_platforms


HMIP_LOCAL_PLATFORMS: list[str] = _get_hmip_local_platforms()
