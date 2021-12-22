""" hahomematic services """
from __future__ import annotations

from datetime import datetime
import logging

from hahomematic.const import (
    ATTR_ADDRESS,
    ATTR_INTERFACE_ID,
    ATTR_NAME,
    ATTR_PARAMETER,
    ATTR_VALUE,
)
from hahomematic.entity import GenericEntity
import voluptuous as vol

from homeassistant.const import ATTR_ENTITY_ID, ATTR_MODE, ATTR_TIME
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers import device_registry as dr
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.device_registry import DeviceEntry
from homeassistant.helpers.service import (
    async_register_admin_service,
    verify_domain_control,
)

from .const import (
    ATTR_PARAMSET,
    ATTR_PARAMSET_KEY,
    ATTR_RX_MODE,
    ATTR_VALUE_TYPE,
    DOMAIN,
)
from .control_unit import ControlUnit, HaHub
from .helpers import get_address_at_interface_from_identifiers

_LOGGER = logging.getLogger(__name__)

ATTR_CHANNEL = "channel"
ATTR_DEVICE_ID = "device_id"

DEFAULT_CHANNEL = 1

SERVICE_PUT_PARAMSET = "put_paramset"
SERVICE_SET_DEVICE_VALUE = "set_device_value"
SERVICE_SET_INSTALL_MODE = "set_install_mode"
SERVICE_SET_VARIABLE_VALUE = "set_variable_value"

HAHM_SERVICES = [
    SERVICE_PUT_PARAMSET,
    SERVICE_SET_DEVICE_VALUE,
    SERVICE_SET_INSTALL_MODE,
    SERVICE_SET_VARIABLE_VALUE,
]

SCHEMA_SERVICE_SET_VARIABLE_VALUE = vol.Schema(
    {
        vol.Required(ATTR_ENTITY_ID): cv.string,
        vol.Required(ATTR_NAME): cv.string,
        vol.Required(ATTR_VALUE): cv.match_all,
    }
)

SCHEMA_SERVICE_SET_INSTALL_MODE = vol.Schema(
    {
        vol.Required(ATTR_INTERFACE_ID): cv.string,
        vol.Optional(ATTR_TIME, default=60): cv.positive_int,
        vol.Optional(ATTR_MODE, default=1): vol.All(vol.Coerce(int), vol.In([1, 2])),
        vol.Optional(ATTR_ADDRESS): vol.All(cv.string, vol.Upper),
    }
)

SCHEMA_SERVICE_SET_DEVICE_VALUE = vol.Schema(
    {
        vol.Required(ATTR_DEVICE_ID): cv.string,
        vol.Required(ATTR_CHANNEL, default=DEFAULT_CHANNEL): vol.Coerce(int),
        vol.Required(ATTR_PARAMETER): vol.All(cv.string, vol.Upper),
        vol.Required(ATTR_VALUE): cv.match_all,
        vol.Optional(ATTR_VALUE_TYPE): vol.In(
            ["boolean", "dateTime.iso8601", "double", "int", "string"]
        ),
        vol.Optional(ATTR_RX_MODE): vol.All(cv.string, vol.Upper),
    }
)

SCHEMA_SERVICE_PUT_PARAMSET = vol.Schema(
    {
        vol.Required(ATTR_DEVICE_ID): cv.string,
        vol.Required(ATTR_CHANNEL, default=DEFAULT_CHANNEL): vol.Coerce(int),
        vol.Required(ATTR_PARAMSET_KEY): vol.All(cv.string, vol.Upper),
        vol.Required(ATTR_PARAMSET): dict,
        vol.Optional(ATTR_RX_MODE): vol.All(cv.string, vol.Upper),
    }
)


async def async_setup_services(hass: HomeAssistant) -> None:
    """Setup servives"""

    if hass.services.async_services().get(DOMAIN):
        return

    @verify_domain_control(hass, DOMAIN)
    async def async_call_hahm_service(service: ServiceCall) -> None:
        """Call correct HomematicIP Cloud service."""
        service_name = service.service

        if service_name == SERVICE_PUT_PARAMSET:
            await _async_service_put_paramset(hass, service)
        elif service_name == SERVICE_SET_INSTALL_MODE:
            await _async_service_set_install_mode(hass, service)
        elif service_name == SERVICE_SET_DEVICE_VALUE:
            await _async_service_set_device_value(hass, service)
        elif service_name == SERVICE_SET_VARIABLE_VALUE:
            await _async_service_set_variable_value(hass, service)

    hass.services.async_register(
        domain=DOMAIN,
        service=SERVICE_SET_VARIABLE_VALUE,
        service_func=async_call_hahm_service,
        schema=SCHEMA_SERVICE_SET_VARIABLE_VALUE,
    )

    hass.services.async_register(
        domain=DOMAIN,
        service=SERVICE_SET_DEVICE_VALUE,
        service_func=async_call_hahm_service,
        schema=SCHEMA_SERVICE_SET_DEVICE_VALUE,
    )

    async_register_admin_service(
        hass=hass,
        domain=DOMAIN,
        service=SERVICE_SET_INSTALL_MODE,
        service_func=async_call_hahm_service,
        schema=SCHEMA_SERVICE_SET_INSTALL_MODE,
    )

    hass.services.async_register(
        domain=DOMAIN,
        service=SERVICE_PUT_PARAMSET,
        service_func=async_call_hahm_service,
        schema=SCHEMA_SERVICE_PUT_PARAMSET,
    )


async def async_unload_services(hass: HomeAssistant) -> None:
    """Unload HAHM services."""
    if hass.data[DOMAIN]:
        return

    for hahm_service in HAHM_SERVICES:
        hass.services.async_remove(domain=DOMAIN, service=hahm_service)


async def _async_service_set_variable_value(
    hass: HomeAssistant, service: ServiceCall
) -> None:
    """Service to call setValue method for HomeMatic system variable."""
    entity_id = service.data[ATTR_ENTITY_ID]
    name = service.data[ATTR_NAME]
    value = service.data[ATTR_VALUE]

    if hub := _get_hub_by_entity_id(hass, entity_id):
        await hub.async_set_variable(name, value)


async def _async_service_set_device_value(
    hass: HomeAssistant, service: ServiceCall
) -> None:
    """Service to call setValue method for HomeMatic devices."""
    device_id = service.data[ATTR_DEVICE_ID]
    channel = service.data[ATTR_CHANNEL]
    parameter = service.data[ATTR_PARAMETER]
    value = service.data[ATTR_VALUE]
    rx_mode = service.data.get(ATTR_RX_MODE)

    # Convert value into correct XML-RPC Type.
    # https://docs.python.org/3/library/xmlrpc.client.html#xmlrpc.client.ServerProxy
    if value_type := service.data.get(ATTR_VALUE_TYPE):
        if value_type == "int":
            value = int(value)
        elif value_type == "double":
            value = float(value)
        elif value_type == "boolean":
            value = bool(value)
        elif value_type == "dateTime.iso8601":
            value = datetime.strptime(value, "%Y%m%dT%H:%M:%S")
        else:
            # Default is 'string'
            value = str(value)

    if (address_data := _get_interface_channel_address(
        hass=hass, device_id=device_id, channel=channel
    )) is None:
        return None

    interface_id: str = address_data[0]
    channel_address: str = address_data[1]

    _LOGGER.debug(
        "Calling setValue: %s, %s, %s, %s, %s, %s",
        interface_id,
        channel_address,
        parameter,
        value,
        value_type,
        rx_mode,
    )

    if interface_id and channel_address:
        if control_unit := _get_cu_by_interface_id(hass, interface_id):
            await control_unit.central.set_value(
                interface_id=interface_id,
                address=channel_address,
                value_key=parameter,
                value=value,
                rx_mode=rx_mode,
            )


async def _async_service_set_install_mode(
    hass: HomeAssistant, service: ServiceCall
) -> None:
    """Service to set interface_id into install mode."""
    interface_id = service.data[ATTR_INTERFACE_ID]
    mode: int = service.data.get(ATTR_MODE, 1)
    time: int = service.data.get(ATTR_TIME, 60)
    address = service.data.get(ATTR_ADDRESS)

    if control_unit := _get_cu_by_interface_id(hass, interface_id):
        await control_unit.central.set_install_mode(
            interface_id, t=time, mode=mode, address=address
        )


async def _async_service_put_paramset(
    hass: HomeAssistant, service: ServiceCall
) -> None:
    """Service to call the putParamset method on a HomeMatic connection."""
    device_id = service.data[ATTR_DEVICE_ID]
    channel = service.data[ATTR_CHANNEL]
    paramset_key = service.data[ATTR_PARAMSET_KEY]
    # When passing in the paramset from a YAML file we get an OrderedDict
    # here instead of a dict, so add this explicit cast.
    # The service schema makes sure that this cast works.
    paramset = dict(service.data[ATTR_PARAMSET])
    rx_mode = service.data.get(ATTR_RX_MODE)

    if (address_data := _get_interface_channel_address(
        hass=hass, device_id=device_id, channel=channel
    )) is None:
        return None

    interface_id: str = address_data[0]
    channel_address: str = address_data[1]

    _LOGGER.debug(
        "Calling putParamset: %s, %s, %s, %s, %s",
        interface_id,
        channel_address,
        paramset_key,
        paramset,
        rx_mode,
    )

    if interface_id and channel_address:
        if control_unit := _get_cu_by_interface_id(hass, interface_id):
            await control_unit.central.put_paramset(
                interface_id=interface_id,
                address=channel_address,
                paramset=paramset_key,
                value=paramset,
                rx_mode=rx_mode,
            )


def _get_interface_channel_address(
    hass: HomeAssistant, device_id: str, channel: int
) -> tuple[str, str] | None:
    """Return interface and channel_address with given device_id and channel."""
    device_registry = dr.async_get(hass)
    device_entry: DeviceEntry | None = device_registry.async_get(device_id)
    if not device_entry:
        return None
    if (data := get_address_at_interface_from_identifiers(
        device_entry.identifiers
    )) is None:
        return None

    address = data[0]
    interface_id = data[1]

    channel_address = f"{address}:{channel}"
    return interface_id, channel_address


def _get_hm_entity(
    hass: HomeAssistant, interface_id: str, address: str, parameter: str
) -> GenericEntity | None:
    """Get homematic entity."""
    if control_unit := _get_cu_by_interface_id(hass, interface_id):
        return control_unit.central.get_hm_entity_by_parameter(address, parameter)
    return None


def _get_cu_by_interface_id(
    hass: HomeAssistant, interface_id: str
) -> ControlUnit | None:
    """
    Get ControlUnit by interface_id
    """
    for entry_id in hass.data[DOMAIN].keys():
        control_unit: ControlUnit = hass.data[DOMAIN][entry_id]
        if control_unit and control_unit.central.clients.get(interface_id):
            return control_unit
    return None


def _get_hub_by_entity_id(hass: HomeAssistant, entity_id: str) -> HaHub | None:
    """
    Get ControlUnit by device address
    """
    for entry_id in hass.data[DOMAIN].keys():
        control_unit: ControlUnit = hass.data[DOMAIN][entry_id]
        if (
            control_unit
            and control_unit.hub
            and control_unit.hub.entity_id == entity_id
        ):
            return control_unit.hub
    return None
