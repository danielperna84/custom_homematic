"""
hahomematic is a Python 3 (>= 3.6) module for Home Assistant to interact with
HomeMatic and homematic IP devices.
Some other devices (f.ex. Bosch, Intertechno) might be supported as well.
https://github.com/danielperna84/hahomematic
"""
from __future__ import annotations

import logging
from datetime import datetime
from typing import Optional

import voluptuous as vol
from hahomematic.const import (
    ATTR_ADDRESS,
    ATTR_INTERFACE_ID,
    ATTR_NAME,
    ATTR_PARAMETER,
    ATTR_PARAMSET,
    ATTR_PARAMSET_KEY,
    ATTR_RX_MODE,
    ATTR_VALUE,
    ATTR_VALUE_TYPE,
    HA_PLATFORMS,
    HM_VIRTUAL_REMOTE_HM,
    HM_VIRTUAL_REMOTE_HMIP,
)
from hahomematic.entity import GenericEntity

import homeassistant.helpers.config_validation as cv
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_ENTITY_ID, ATTR_MODE, ATTR_TIME
from homeassistant.core import HomeAssistant

from .const import (
    ATTR_CHANNEL,
    ATTR_INSTANCE_NAME,
    ATTR_INTERFACE,
    ATTR_PARAM,
    DOMAIN,
    SERVICE_PUT_PARAMSET,
    SERVICE_SET_DEVICE_VALUE,
    SERVICE_SET_INSTALL_MODE,
    SERVICE_SET_VARIABLE_VALUE,
    SERVICE_VIRTUAL_KEY,
)
from .controlunit import ControlUnit

_LOGGER = logging.getLogger(__name__)

SCHEMA_SERVICE_VIRTUALKEY = vol.Schema(
    {
        vol.Optional(ATTR_INTERFACE_ID): cv.string,
        vol.Required(ATTR_ADDRESS): vol.All(cv.string, vol.Upper),
        vol.Required(ATTR_PARAMETER): cv.string,
    }
)

SCHEMA_SERVICE_SET_VARIABLE_VALUE = vol.Schema(
    {
        vol.Required(ATTR_ENTITY_ID): cv.string,
        vol.Required(ATTR_NAME): cv.string,
        vol.Required(ATTR_VALUE): cv.match_all,
    }
)

SCHEMA_SERVICE_SET_DEVICE_VALUE = vol.Schema(
    {
        vol.Required(ATTR_INTERFACE_ID): cv.string,
        vol.Required(ATTR_ADDRESS): vol.All(cv.string, vol.Upper),
        vol.Required(ATTR_PARAMETER): vol.All(cv.string, vol.Upper),
        vol.Required(ATTR_VALUE): cv.match_all,
        vol.Optional(ATTR_VALUE_TYPE): vol.In(
            ["boolean", "dateTime.iso8601", "double", "int", "string"]
        ),
        vol.Optional(ATTR_INTERFACE_ID): cv.string,
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

SCHEMA_SERVICE_PUT_PARAMSET = vol.Schema(
    {
        vol.Required(ATTR_INTERFACE_ID): cv.string,
        vol.Required(ATTR_ADDRESS): vol.All(cv.string, vol.Upper),
        vol.Required(ATTR_PARAMSET_KEY): vol.All(cv.string, vol.Upper),
        vol.Required(ATTR_PARAMSET): dict,
        vol.Optional(ATTR_RX_MODE): vol.All(cv.string, vol.Upper),
    }
)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up HA-Homematic from a config entry."""

    cu = ControlUnit(hass, entry=entry)
    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = cu
    hass.config_entries.async_setup_platforms(entry, HA_PLATFORMS)
    await cu.start()
    #await hass.async_add_executor_job(cu.init_hub)
    await async_setup_services(hass)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, HA_PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok


async def async_setup_services(hass: HomeAssistant) -> None:
    """Setup servives"""

    async def _service_virtualkey(service):
        """Service to handle virtualkey servicecalls."""
        interface_id = service.data[ATTR_INTERFACE_ID]
        address = service.data[ATTR_ADDRESS]
        parameter = service.data[ATTR_PARAMETER]

        cu = _get_cu_by_interface_id(hass, interface_id)
        await cu.central.press_virtual_remote_key(address, parameter)

    hass.services.async_register(
        domain=DOMAIN,
        service=SERVICE_VIRTUAL_KEY,
        service_func=_service_virtualkey,
        schema=SCHEMA_SERVICE_VIRTUALKEY,
    )

    async def _service_set_variable_value(service):
        """Service to call setValue method for HomeMatic system variable."""
        entity_id = service.data.get(ATTR_ENTITY_ID)
        name = service.data[ATTR_NAME]
        value = service.data[ATTR_VALUE]

        hub = _get_hub_by_entity_id(hass, entity_id)
        if hub:
            await hub.set_variable(name, value)

    hass.services.async_register(
        domain=DOMAIN,
        service=SERVICE_SET_VARIABLE_VALUE,
        service_func=_service_set_variable_value,
        schema=SCHEMA_SERVICE_SET_VARIABLE_VALUE,
    )

    async def _service_set_device_value(service):
        """Service to call setValue method for HomeMatic devices."""
        interface_id = service.data[ATTR_INTERFACE_ID]
        address = service.data[ATTR_ADDRESS]
        parameter = service.data[ATTR_PARAMETER]
        value = service.data[ATTR_VALUE]
        value_type = service.data.get(ATTR_VALUE_TYPE)

        # Convert value into correct XML-RPC Type.
        # https://docs.python.org/3/library/xmlrpc.client.html#xmlrpc.client.ServerProxy
        if value_type:
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

        # Device not found
        hm_entity = _get_hm_entity(hass, interface_id, address, parameter)
        if hm_entity is None:
            _LOGGER.error("%s not found!", address)
            return

        await hm_entity.send_value(value)

    hass.services.async_register(
        domain=DOMAIN,
        service=SERVICE_SET_DEVICE_VALUE,
        service_func=_service_set_device_value,
        schema=SCHEMA_SERVICE_SET_DEVICE_VALUE,
    )

    async def _service_set_install_mode(service):
        """Service to set interface_id into install mode."""
        interface_id = service.data[ATTR_INTERFACE_ID]
        mode = service.data.get(ATTR_MODE)
        time = service.data.get(ATTR_TIME)
        address = service.data.get(ATTR_ADDRESS)

        cu = _get_cu_by_interface_id(hass, interface_id)
        if cu:
            await cu.set_install_mode(interface_id, t=time, mode=mode, address=address)

    hass.services.async_register(
        domain=DOMAIN,
        service=SERVICE_SET_INSTALL_MODE,
        service_func=_service_set_install_mode,
        schema=SCHEMA_SERVICE_SET_INSTALL_MODE,
    )

    async def _service_put_paramset(service):
        """Service to call the putParamset method on a HomeMatic connection."""
        interface_id = service.data[ATTR_INTERFACE_ID]
        address = service.data[ATTR_ADDRESS]
        paramset_key = service.data[ATTR_PARAMSET_KEY]
        # When passing in the paramset from a YAML file we get an OrderedDict
        # here instead of a dict, so add this explicit cast.
        # The service schema makes sure that this cast works.
        paramset = dict(service.data[ATTR_PARAMSET])
        rx_mode = service.data.get(ATTR_RX_MODE)

        _LOGGER.debug(
            "Calling putParamset: %s, %s, %s, %s, %s",
            interface_id,
            address,
            paramset_key,
            paramset,
            rx_mode,
        )
        cu = _get_cu_by_interface_id(hass, interface_id)
        if cu:
            await cu.put_paramset(
                interface_id, address, paramset_key, paramset, rx_mode
            )

    hass.services.async_register(
        domain=DOMAIN,
        service=SERVICE_PUT_PARAMSET,
        service_func=_service_put_paramset,
        schema=SCHEMA_SERVICE_PUT_PARAMSET,
    )


def _get_hm_entity(hass, interface_id, address, parameter) -> GenericEntity:
    """Get homematic entity."""
    cu = _get_cu_by_interface_id(hass, interface_id)
    return cu.central.get_hm_entity_by_parameter(address, parameter)


def _get_cu_by_interface_id(hass, interface_id) -> Optional[ControlUnit]:
    """
    Get ControlUnit by device address
    """
    for cu in hass.data[DOMAIN].values():
        if cu.central.clients.get(interface_id):
            return cu
    return None


def _get_hub_by_entity_id(hass, entity_id) -> Optional[HMHub]:
    """
    Get ControlUnit by device address
    """
    for cu in hass.data[DOMAIN].values():
        if cu.hub.entity_id == entity_id:
            return cu.hub
    return None
