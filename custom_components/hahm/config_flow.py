"""Config flow for hahomematic integration."""
from __future__ import annotations

import logging
from xmlrpc.client import ProtocolError

from hahomematic.const import (
    ATTR_CALLBACK_HOST,
    ATTR_CALLBACK_PORT,
    ATTR_HOST,
    ATTR_JSON_PORT,
    ATTR_PASSWORD,
    ATTR_PORT,
    ATTR_TLS,
    ATTR_USERNAME,
    ATTR_VERIFY_TLS,
    DEFAULT_TLS,
    IP_ANY_V4,
    PORT_ANY,
)
from hahomematic.xml_rpc_proxy import NoConnection
import voluptuous as vol
from voluptuous.schema_builder import UNDEFINED, Schema

from homeassistant import config_entries
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.data_entry_flow import FlowResult
from homeassistant.exceptions import HomeAssistantError
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.typing import ConfigType

from .const import (
    ATTR_INSTANCE_NAME,
    ATTR_INTERFACE,
    ATTR_PATH,
    CONF_ENABLE_SENSORS_FOR_SYSTEM_VARIABLES,
    CONF_ENABLE_VIRTUAL_CHANNELS,
    DOMAIN,
)
from .control_unit import ControlConfig, ControlUnit

_LOGGER = logging.getLogger(__name__)

ATTR_HMIP_RF_ENABLED = "hmip_rf_enabled"
ATTR_HMIP_RF_PORT = "hmip_rf_port"
ATTR_BICDOS_RF_ENABLED = "bidos_rf_enabled"
ATTR_BICDOS_RF_PORT = "bidos_rf_port"
ATTR_VIRTUAL_DEVICES_ENABLED = "virtual_devices_enabled"
ATTR_VIRTUAL_DEVICES_PORT = "virtual_devices_port"
ATTR_VIRTUAL_DEVICES_PATH = "virtual_devices_path"
ATTR_HS485D_ENABLED = "hs485d_enabled"
ATTR_HS485D_PORT = "hs485d_port"

IF_VIRTUAL_DEVICES_NAME = "VirtualDevices"
IF_VIRTUAL_DEVICES_PORT = 9292
IF_VIRTUAL_DEVICES_TLS_PORT = 49292
IF_VIRTUAL_DEVICES_PATH = "/groups"
IF_HMIP_RF_NAME = "HmIP-RF"
IF_HMIP_RF_PORT = 2010
IF_HMIP_RF_TLS_PORT = 42010
IF_HS485D_NAME = "HS485D"
IF_HS485D_PORT = 2000
IF_HS485D_TLS_PORT = 42000
IF_BIDCOS_RF_NAME = "BidCos-RF"
IF_BICDOS_RF_PORT = 2001
IF_BICDOS_RF_TLS_PORT = 42001


def get_domain_schema(data: ConfigType) -> Schema:
    """Return the interface schema with or without tls ports."""
    return vol.Schema(
        {
            vol.Required(
                ATTR_INSTANCE_NAME, default=data.get(ATTR_INSTANCE_NAME) or UNDEFINED
            ): cv.string,
            vol.Required(ATTR_HOST, default=data.get(ATTR_HOST)): cv.string,
            vol.Required(ATTR_USERNAME, default=data.get(ATTR_USERNAME)): cv.string,
            vol.Required(ATTR_PASSWORD, default=data.get(ATTR_PASSWORD)): cv.string,
            vol.Optional(
                ATTR_CALLBACK_HOST, default=data.get(ATTR_CALLBACK_HOST) or UNDEFINED
            ): cv.string,
            vol.Optional(
                ATTR_CALLBACK_PORT, default=data.get(ATTR_CALLBACK_PORT) or UNDEFINED
            ): cv.port,
            vol.Optional(
                ATTR_TLS, default=data.get(ATTR_TLS) or DEFAULT_TLS
            ): cv.boolean,
            vol.Optional(
                ATTR_VERIFY_TLS, default=data.get(ATTR_VERIFY_TLS) or False
            ): cv.boolean,
            vol.Optional(
                ATTR_JSON_PORT, default=data.get(ATTR_JSON_PORT) or UNDEFINED
            ): cv.port,
            vol.Optional(
                CONF_ENABLE_VIRTUAL_CHANNELS,
                default=data.get(CONF_ENABLE_VIRTUAL_CHANNELS) or False,
            ): bool,
            vol.Optional(
                CONF_ENABLE_SENSORS_FOR_SYSTEM_VARIABLES,
                default=data.get(CONF_ENABLE_VIRTUAL_CHANNELS) or False,
            ): bool,
        }
    )


def get_options_schema(data: ConfigType) -> Schema:
    """Return the interface schema with or without tls ports."""
    options_schema = get_domain_schema(data=data)
    del options_schema.schema[ATTR_INSTANCE_NAME]
    return options_schema


def get_interface_schema(use_tls: bool) -> Schema:
    """Return the interface schema with or without tls ports."""
    return vol.Schema(
        {
            vol.Required(ATTR_HMIP_RF_ENABLED, default=True): bool,
            vol.Required(
                ATTR_HMIP_RF_PORT,
                default=IF_HMIP_RF_TLS_PORT if use_tls else IF_HMIP_RF_PORT,
            ): int,
            vol.Required(ATTR_BICDOS_RF_ENABLED, default=True): bool,
            vol.Required(
                ATTR_BICDOS_RF_PORT,
                default=IF_BICDOS_RF_TLS_PORT if use_tls else IF_BICDOS_RF_PORT,
            ): int,
            vol.Required(ATTR_VIRTUAL_DEVICES_ENABLED, default=True): bool,
            vol.Required(
                ATTR_VIRTUAL_DEVICES_PORT,
                default=IF_VIRTUAL_DEVICES_TLS_PORT
                if use_tls
                else IF_VIRTUAL_DEVICES_PORT,
            ): int,
            vol.Required(
                ATTR_VIRTUAL_DEVICES_PATH, default=IF_VIRTUAL_DEVICES_PATH
            ): str,
            vol.Required(ATTR_HS485D_ENABLED, default=False): bool,
            vol.Required(
                ATTR_HS485D_PORT,
                default=IF_HS485D_TLS_PORT if use_tls else IF_HS485D_PORT,
            ): int,
        }
    )


async def _async_validate_input(hass: HomeAssistant, data: ConfigType) -> bool:
    """Validate the user input allows us to connect."""
    control_unit = await ControlConfig(
        hass=hass, entry_id="validate", data=data
    ).async_get_control_unit()
    await control_unit.async_create_central()
    try:
        await control_unit.async_create_clients()
        if first_client := control_unit.central.get_client():
            return await first_client.is_connected()
    except ConnectionError as cex:
        _LOGGER.exception(cex)
        raise CannotConnect from cex
    except NoConnection as noc:
        _LOGGER.exception(noc)
        raise CannotConnect from noc
    except OSError as oer:
        _LOGGER.exception(oer)
        raise CannotConnect from oer
    except ProtocolError as cex:
        _LOGGER.exception(cex)
        raise InvalidAuth from cex
    except Exception as cex:  # pylint: disable=broad-except
        _LOGGER.exception(cex)
    return False


class DomainConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle the instance flow for hahomematic."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_LOCAL_PUSH

    def __init__(self) -> None:
        """Init the ConfigFlow."""
        self.data: ConfigType = {}

    async def async_step_user(self, user_input: ConfigType | None = None) -> FlowResult:
        """Handle the initial step."""
        return await self.async_step_central(user_input=user_input)

    async def async_step_central(self, user_input: ConfigType | None = None) -> FlowResult:
        """Handle the initial step."""
        if user_input is not None:
            await self.async_set_unique_id(user_input[ATTR_INSTANCE_NAME])
            self._abort_if_unique_id_configured()
            self.data = _get_ccu_data(self.data, user_input=user_input)
            return await self.async_step_interface()

        return self.async_show_form(
            step_id="central", data_schema=get_domain_schema(data=self.data)
        )

    async def async_step_interface(
        self,
        interface_input: ConfigType | None = None,
    ) -> FlowResult:
        """Handle the initial step."""
        if interface_input is None:
            _LOGGER.warning("ConfigFlow.step_interface, no user input")
            return self.async_show_form(
                step_id="interface",
                data_schema=get_interface_schema(self.data[ATTR_TLS]),
            )

        _update_interface_input(data=self.data, interface_input=interface_input)
        errors = {}

        try:
            await _async_validate_input(self.hass, self.data)
        except CannotConnect:
            errors["base"] = "cannot_connect"
        except InvalidAuth:
            errors["base"] = "invalid_auth"
        except Exception:  # pylint: disable=broad-except
            _LOGGER.exception("Unexpected exception")
            errors["base"] = "unknown"
        else:
            return self.async_create_entry(
                title=self.data[ATTR_INSTANCE_NAME], data=self.data
            )

        return self.async_show_form(
            step_id="central",
            data_schema=get_domain_schema(data=self.data),
            errors=errors,
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> config_entries.OptionsFlow:
        """Get the options flow for this handler."""
        return HahmOptionsFlowHandler(config_entry)


class HahmOptionsFlowHandler(config_entries.OptionsFlow):
    """Handle hahm options."""

    def __init__(self, config_entry: ConfigEntry) -> None:
        """Initialize hahm options flow."""
        self.config_entry = config_entry
        self.data: ConfigType = dict(self.config_entry.data.items())

    async def async_step_init(self, user_input: ConfigType | None = None) -> FlowResult:
        """Manage the hahm options."""
        return await self.async_step_central(user_input=user_input)

    async def async_step_central(
        self, user_input: ConfigType | None = None
    ) -> FlowResult:
        """Manage the hahm devices options."""
        if user_input is not None:
            self.data = _get_ccu_data(self.data, user_input=user_input)
            return await self.async_step_interface()

        return self.async_show_form(
            step_id="central", data_schema=get_options_schema(data=self.data)
        )

    async def async_step_interface(
        self,
        interface_input: ConfigType | None = None,
    ) -> FlowResult:
        """Handle the initial step."""
        if interface_input is None:
            _LOGGER.warning("ConfigFlow.step_interface, no user input")
            return self.async_show_form(
                step_id="interface",
                data_schema=get_interface_schema(self.data[ATTR_TLS]),
            )

        _update_interface_input(data=self.data, interface_input=interface_input)
        errors = {}

        try:
            await _async_validate_input(self.hass, self.data)
        except CannotConnect:
            errors["base"] = "cannot_connect"
        except InvalidAuth:
            errors["base"] = "invalid_auth"
        except Exception:  # pylint: disable=broad-except
            _LOGGER.exception("Unexpected exception")
            errors["base"] = "unknown"
        else:
            self.hass.config_entries.async_update_entry(
                entry=self.config_entry, data=self.data
            )
            return self.async_create_entry(title="", data={})

        return self.async_show_form(
            step_id="central",
            data_schema=get_options_schema(data=self.data),
            errors=errors,
        )

    @property
    def _control_unit(self) -> ControlUnit:
        control_unit: ControlUnit = self.hass.data[DOMAIN][self.config_entry.entry_id]
        return control_unit


class CannotConnect(HomeAssistantError):
    """Error to indicate we cannot connect."""


class InvalidAuth(HomeAssistantError):
    """Error to indicate there is invalid auth."""


def _get_ccu_data(data: ConfigType, user_input: ConfigType):
    return {
        ATTR_INSTANCE_NAME: user_input.get(
            ATTR_INSTANCE_NAME, data.get(ATTR_INSTANCE_NAME)
        ),
        ATTR_HOST: user_input[ATTR_HOST],
        ATTR_USERNAME: user_input.get(ATTR_USERNAME),
        ATTR_PASSWORD: user_input.get(ATTR_PASSWORD),
        ATTR_CALLBACK_HOST: user_input.get(ATTR_CALLBACK_HOST, IP_ANY_V4),
        ATTR_CALLBACK_PORT: user_input.get(ATTR_CALLBACK_PORT, PORT_ANY),
        ATTR_JSON_PORT: user_input.get(ATTR_JSON_PORT),
        ATTR_TLS: user_input.get(ATTR_TLS),
        ATTR_VERIFY_TLS: user_input.get(ATTR_VERIFY_TLS),
        CONF_ENABLE_VIRTUAL_CHANNELS: user_input.get(CONF_ENABLE_VIRTUAL_CHANNELS),
        CONF_ENABLE_SENSORS_FOR_SYSTEM_VARIABLES: user_input.get(
            CONF_ENABLE_SENSORS_FOR_SYSTEM_VARIABLES
        ),
        ATTR_INTERFACE: {},
    }


def _update_interface_input(data: ConfigType, interface_input: ConfigType):
    if interface_input is not None:
        if interface_input[ATTR_HMIP_RF_ENABLED]:
            data[ATTR_INTERFACE][IF_HMIP_RF_NAME] = {
                ATTR_PORT: interface_input[ATTR_HMIP_RF_PORT],
            }
        if interface_input[ATTR_BICDOS_RF_ENABLED]:
            data[ATTR_INTERFACE][IF_BIDCOS_RF_NAME] = {
                ATTR_PORT: interface_input[ATTR_BICDOS_RF_PORT],
            }
        if interface_input[ATTR_VIRTUAL_DEVICES_ENABLED]:
            data[ATTR_INTERFACE][IF_VIRTUAL_DEVICES_NAME] = {
                ATTR_PORT: interface_input[ATTR_VIRTUAL_DEVICES_PORT],
                ATTR_PATH: interface_input.get(ATTR_VIRTUAL_DEVICES_PATH),
            }
        if interface_input[ATTR_HS485D_ENABLED]:
            data[ATTR_INTERFACE][IF_HS485D_NAME] = {
                ATTR_PORT: interface_input[ATTR_HS485D_PORT],
            }
