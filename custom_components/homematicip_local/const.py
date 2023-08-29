"""Constants."""
from __future__ import annotations

from enum import StrEnum
from typing import Final

from hahomematic.const import AVAILABLE_HM_PLATFORMS
from homeassistant.const import Platform

DOMAIN: Final = "homematicip_local"
HMIP_LOCAL_MIN_VERSION: Final = "2023.8.0.dev0"

LEARN_MORE_URL_XMLRPC_SERVER_RECEIVES_NO_EVENTS: Final = "https://github.com/danielperna84/custom_homematic#what-is-the-meaning-of-xmlrpc-server-received-no-events"
LEARN_MORE_URL_PING_PONG_MISMATCH: Final = "https://github.com/danielperna84/custom_homematic#what-is-the-meaning-of-pingpong-mismatch-on-interface"

ATTR_ADDRESS: Final = "address"
ATTR_CALLBACK_HOST: Final = "callback_host"
ATTR_CALLBACK_PORT: Final = "callback_port"
ATTR_CHANNEL_NO: Final = "channel_no"
ATTR_ENABLE_SYSTEM_NOTIFICATIONS: Final = "enable_system_notifications"
ATTR_ENTITY_TYPE: Final = "entity_type"
ATTR_FUNCTION: Final = "function"
ATTR_HOST: Final = "host"
ATTR_INSTANCE_NAME: Final = "instance_name"
ATTR_INTERFACE: Final = "interface"
ATTR_INTERFACE_ID: Final = "interface_id"
ATTR_JSON_PORT: Final = "json_port"
ATTR_MODEL: Final = "model"
ATTR_NAME: Final = "name"
ATTR_PARAMETER: Final = "parameter"
ATTR_PARAMSET: Final = "paramset"
ATTR_PARAMSET_KEY: Final = "paramset_key"
ATTR_PATH: Final = "path"
ATTR_PORT: Final = "port"
ATTR_RX_MODE: Final = "rx_mode"
ATTR_SYSVAR_SCAN_ENABLED: Final = "sysvar_scan_enabled"
ATTR_SYSVAR_SCAN_INTERVAL: Final = "sysvar_scan_interval"
ATTR_TLS: Final = "tls"
ATTR_VALUE: Final = "value"
ATTR_VALUE_STATE: Final = "value_state"
ATTR_VALUE_TYPE: Final = "value_type"
ATTR_VERIFY_TLS: Final = "verify_tls"

CONF_INTERFACE_ID: Final = "interface_id"
CONF_EVENT_TYPE: Final = "event_type"
CONF_SUBTYPE: Final = "subtype"

DEFAULT_CALLBACK_PORT: Final = "default_callback_port"
CONTROL_UNITS: Final = "control_units"

EVENT_ADDRESS = "address"
EVENT_DATA_ERROR: Final = "error"
EVENT_DATA_ERROR_VALUE: Final = "error_value"
EVENT_DATA_IDENTIFIER: Final = "identifier"
EVENT_DATA_MESSAGE: Final = "message"
EVENT_DATA_TITLE: Final = "title"
EVENT_DATA_UNAVAILABLE: Final = "unavailable"

SERVICE_PUT_PARAMSET: Final = "put_paramset"
SERVICE_SET_DEVICE_VALUE: Final = "set_device_value"
SERVICE_SET_INSTALL_MODE: Final = "set_install_mode"
SERVICE_SET_VARIABLE_VALUE: Final = "set_variable_value"
SERVICE_VIRTUAL_KEY: Final = "virtual_key"

# only used for entities from MASTER paramset

TOTAL_INCREASING_SYSVAR: Final[tuple[str, ...]] = (
    "svEnergyCounter_",
    "svHmIPRainCounter_",
    "svHmIPSunshineCounter_",
)

# filter out event error parameters, that should not be displayed in logbook
FILTER_ERROR_EVENT_PARAMETERS: Final[list[str]] = ["ERROR_CODE"]


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


class HmNameSource(StrEnum):
    """Enum to define the source of a translation."""

    DEVICE_CLASS = "device_class"
    ENTITY_NAME = "entity_name"
    PARAMETER = "parameter"


BLOCK_PLATFORMS: Final[tuple[str, ...]] = ()


def _get_hmip_local_platforms() -> list[str]:
    """Return relevant Homematic(IP) Local platforms."""
    platforms = list(Platform)
    hm_platforms = [
        platform.value
        for platform in AVAILABLE_HM_PLATFORMS
        if platform not in BLOCK_PLATFORMS
    ]
    hmip_local_platforms: list[str] = []
    for hm_platform in hm_platforms:
        if hm_platform in platforms:
            hmip_local_platforms.append(hm_platform)

    return hmip_local_platforms


HMIP_LOCAL_PLATFORMS: Final[list[str]] = _get_hmip_local_platforms()
