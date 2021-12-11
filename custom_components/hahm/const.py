"""Constants."""
from __future__ import annotations

from typing import Union, TypeVar
from hahomematic.const import AVAILABLE_HM_PLATFORMS

from homeassistant.const import Platform
from hahomematic.entity import CustomEntity, GenericEntity, BaseParameterEntity
from hahomematic.hub import BaseHubEntity

DOMAIN = "hahm"

HM_ENTITIES = Union[BaseHubEntity, BaseParameterEntity, CustomEntity, GenericEntity]
HmCallbackEntity = (CustomEntity, GenericEntity)
HMEntityType = TypeVar("HMEntityType", bound=HM_ENTITIES)

ATTR_ADD_ANOTHER_INTERFACE = "add_another_interface"
ATTR_CHANNEL = "channel"
ATTR_INSTANCE_NAME = "instance_name"
ATTR_INTERFACE = "interface"
ATTR_INTERFACE_NAME = "interface_name"
ATTR_JSON_TLS = "json_tls"
ATTR_PARAM = "param"
ATTR_PARAMSET = "paramset"
ATTR_PARAMSET_KEY = "paramset_key"
ATTR_PATH = "path"
ATTR_RX_MODE = "rx_mode"
ATTR_VALUE_TYPE = "value_type"

CONF_ENABLE_SENSORS_FOR_SYSTEM_VARIABLES = "enable_sensors_for_system_variables"
CONF_ENABLE_VIRTUAL_CHANNELS = "enable_virtual_channels"

SERVICE_PUT_PARAMSET = "put_paramset"
SERVICE_SET_DEVICE_VALUE = "set_device_value"
SERVICE_SET_INSTALL_MODE = "set_install_mode"
SERVICE_SET_VARIABLE_VALUE = "set_variable_value"
SERVICE_VIRTUAL_KEY = "virtual_key"


def _get_hahm_platforms() -> list[str]:
    """Return relevant hahm platforms."""
    platforms = [entry.value for entry in Platform]
    hm_platforms = [entry.value for entry in AVAILABLE_HM_PLATFORMS]
    hahm_platforms: list[str] = []
    for hm_platform in hm_platforms:
        if hm_platform in platforms:
            hahm_platforms.append(hm_platform)

    return hahm_platforms


HAHM_PLATFORMS: list[str] = _get_hahm_platforms()
