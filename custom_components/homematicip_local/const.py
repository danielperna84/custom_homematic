"""Constants."""
from __future__ import annotations

from datetime import timedelta

from hahomematic.const import AVAILABLE_HM_PLATFORMS

from homeassistant.const import Platform

DOMAIN = "homematicip_local"

ATTR_INSTANCE_NAME = "instance_name"
ATTR_INTERFACE = "interface"
ATTR_PARAMSET = "paramset"
ATTR_PARAMSET_KEY = "paramset_key"
ATTR_PATH = "path"
ATTR_RX_MODE = "rx_mode"
ATTR_VALUE_TYPE = "value_type"

CONF_INTERFACE_ID = "interface_id"
CONF_EVENT_TYPE = "event_type"
CONF_SUBTYPE = "subtype"

EVENT_DEVICE_AVAILABILITY = "homematic.device_availability"
EVENT_DATA_IDENTIFIER = "identifier"
EVENT_DATA_TITLE = "title"
EVENT_DATA_MESSAGE = "message"
EVENT_DATA_AVAILABLE = "available"

SERVICE_PUT_PARAMSET = "put_paramset"
SERVICE_SET_DEVICE_VALUE = "set_device_value"
SERVICE_SET_INSTALL_MODE = "set_install_mode"
SERVICE_SET_VARIABLE_VALUE = "set_variable_value"
SERVICE_VIRTUAL_KEY = "virtual_key"

SYSVAR_SCAN_INTERVAL = timedelta(seconds=30)


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
