"""Config flow for hahomematic integration."""
from __future__ import annotations

import logging
from pprint import pformat
from typing import Any, cast
from urllib.parse import urlparse

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
    IF_BIDCOS_RF_NAME,
    IF_BIDCOS_RF_PORT,
    IF_BIDCOS_RF_TLS_PORT,
    IF_BIDCOS_WIRED_NAME,
    IF_BIDCOS_WIRED_PORT,
    IF_BIDCOS_WIRED_TLS_PORT,
    IF_HMIP_RF_NAME,
    IF_HMIP_RF_PORT,
    IF_HMIP_RF_TLS_PORT,
    IF_VIRTUAL_DEVICES_NAME,
    IF_VIRTUAL_DEVICES_PATH,
    IF_VIRTUAL_DEVICES_PORT,
    IF_VIRTUAL_DEVICES_TLS_PORT,
    IP_ANY_V4,
    PORT_ANY,
)
from hahomematic.exceptions import AuthFailure, NoClients, NoConnection
import voluptuous as vol
from voluptuous.schema_builder import UNDEFINED, Schema

from homeassistant import config_entries
from homeassistant.components import ssdp
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_NAME
from homeassistant.core import HomeAssistant, callback
from homeassistant.data_entry_flow import FlowResult
from homeassistant.exceptions import HomeAssistantError
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.typing import ConfigType

from .const import ATTR_INSTANCE_NAME, ATTR_INTERFACE, ATTR_PATH, DOMAIN
from .control_unit import ControlConfig, ControlUnit, validate_config_and_get_serial

_LOGGER = logging.getLogger(__name__)

ATTR_HMIP_RF_ENABLED = "hmip_rf_enabled"
ATTR_HMIP_RF_PORT = "hmip_rf_port"
ATTR_BIDCOS_RF_ENABLED = "bidcos_rf_enabled"
ATTR_BIDCOS_RF_PORT = "bidcos_rf_port"
ATTR_VIRTUAL_DEVICES_ENABLED = "virtual_devices_enabled"
ATTR_VIRTUAL_DEVICES_PORT = "virtual_devices_port"
ATTR_VIRTUAL_DEVICES_PATH = "virtual_devices_path"
ATTR_BIDCOS_WIRED_ENABLED = "bidcos_wired_enabled"
ATTR_BIDCOS_WIRED_PORT = "bidcos_wired_port"


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
        }
    )


def get_options_schema(data: ConfigType) -> Schema:
    """Return the interface schema with or without tls ports."""
    options_schema = get_domain_schema(data=data)
    del options_schema.schema[ATTR_INSTANCE_NAME]
    return options_schema


def get_interface_schema(use_tls: bool, data: ConfigType) -> Schema:
    """Return the interface schema with or without tls ports."""
    interfaces = data.get(ATTR_INTERFACE, {})
    # HmIP-RF
    if IF_HMIP_RF_NAME in interfaces:
        hmip_rf_enabled = interfaces.get(IF_HMIP_RF_NAME) is not None
    else:
        hmip_rf_enabled = True
    hmip_port = IF_HMIP_RF_TLS_PORT if use_tls else IF_HMIP_RF_PORT

    # BidCos-RF
    if IF_BIDCOS_RF_NAME in interfaces:
        bidcos_rf_enabled = interfaces.get(IF_BIDCOS_RF_NAME) is not None
    else:
        bidcos_rf_enabled = True
    bidcos_rf_port = IF_BIDCOS_RF_TLS_PORT if use_tls else IF_BIDCOS_RF_PORT

    # Virtual devices
    if IF_VIRTUAL_DEVICES_NAME in interfaces:
        virtual_devices_enabled = interfaces.get(IF_VIRTUAL_DEVICES_NAME) is not None
    else:
        virtual_devices_enabled = False
    virtual_devices_port = (
        IF_VIRTUAL_DEVICES_TLS_PORT if use_tls else IF_VIRTUAL_DEVICES_PORT
    )

    # BidCos-Wired
    if IF_BIDCOS_WIRED_NAME in interfaces:
        bidcos_wired_enabled = interfaces.get(IF_BIDCOS_WIRED_NAME) is not None
    else:
        bidcos_wired_enabled = False
    bidcos_wired_port = IF_BIDCOS_WIRED_TLS_PORT if use_tls else IF_BIDCOS_WIRED_PORT

    return vol.Schema(
        {
            vol.Required(ATTR_HMIP_RF_ENABLED, default=hmip_rf_enabled): bool,
            vol.Required(ATTR_HMIP_RF_PORT, default=hmip_port): int,
            vol.Required(ATTR_BIDCOS_RF_ENABLED, default=bidcos_rf_enabled): bool,
            vol.Required(ATTR_BIDCOS_RF_PORT, default=bidcos_rf_port): int,
            vol.Required(
                ATTR_VIRTUAL_DEVICES_ENABLED, default=virtual_devices_enabled
            ): bool,
            vol.Required(ATTR_VIRTUAL_DEVICES_PORT, default=virtual_devices_port): int,
            vol.Required(
                ATTR_VIRTUAL_DEVICES_PATH, default=IF_VIRTUAL_DEVICES_PATH
            ): str,
            vol.Required(ATTR_BIDCOS_WIRED_ENABLED, default=bidcos_wired_enabled): bool,
            vol.Required(ATTR_BIDCOS_WIRED_PORT, default=bidcos_wired_port): int,
        }
    )


async def _async_validate_config_and_get_serial(hass: HomeAssistant, data: ConfigType) -> str:
    """Validate the user input allows us to connect."""
    control_config = ControlConfig(hass=hass, entry_id="validate", data=data)
    try:
        return await validate_config_and_get_serial(control_config=control_config)
    except AuthFailure as auf:
        _LOGGER.warning(auf)
        raise InvalidAuth from auf
    except NoConnection as noc:
        _LOGGER.warning(noc)
        raise CannotConnect from noc
    except NoClients as nocl:
        _LOGGER.warning(nocl)
        raise CannotConnect from nocl


class DomainConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle the instance flow for Homematic(IP) Local."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_LOCAL_PUSH

    def __init__(self) -> None:
        """Init the ConfigFlow."""
        self.data: ConfigType = {}
        self.serial: str | None = None

    async def async_step_user(self, user_input: ConfigType | None = None) -> FlowResult:
        """Handle the initial step."""
        return await self.async_step_central(user_input=user_input)

    async def async_step_central(
        self, user_input: ConfigType | None = None
    ) -> FlowResult:
        """Handle the initial step."""
        if user_input is not None:
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
            _LOGGER.debug("ConfigFlow.step_interface, no user input")
            return self.async_show_form(
                step_id="interface",
                data_schema=get_interface_schema(self.data[ATTR_TLS], self.data),
            )

        _update_interface_input(data=self.data, interface_input=interface_input)
        errors = {}

        try:
            serial = await _async_validate_config_and_get_serial(self.hass, self.data)
            await self.async_set_unique_id(serial)
            self._abort_if_unique_id_configured()
        except CannotConnect:
            errors["base"] = "cannot_connect"
        except InvalidAuth:
            errors["base"] = "invalid_auth"
        else:
            return self.async_create_entry(
                title=self.data[ATTR_INSTANCE_NAME], data=self.data
            )

        return self.async_show_form(
            step_id="central",
            data_schema=get_domain_schema(data=self.data),
            errors=errors,
        )

    async def async_step_ssdp(self, discovery_info: ssdp.SsdpServiceInfo) -> FlowResult:
        """Handle a discovered Homematic(IP) Local CCU."""
        _LOGGER.debug("Homematic(IP) Local SSDP discovery %s", pformat(discovery_info))
        instance_name = _get_instance_name(
            friendly_name=discovery_info.upnp.get("friendlyName")
        )
        serial = _get_serial(
            model_description=discovery_info.upnp.get("modelDescription")
        )

        host = cast(str, urlparse(discovery_info.ssdp_location).hostname)
        await self.async_set_unique_id(serial)

        self._abort_if_unique_id_configured(updates={CONF_HOST: host})

        self.data = {ATTR_INSTANCE_NAME: instance_name, ATTR_HOST: host}
        self.context["title_placeholders"] = {CONF_NAME: instance_name, CONF_HOST: host}
        return await self.async_step_user()

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> config_entries.OptionsFlow:
        """Get the options flow for this handler."""
        return HomematicIPLocalOptionsFlowHandler(config_entry)


class HomematicIPLocalOptionsFlowHandler(config_entries.OptionsFlow):
    """Handle Homematic(IP) Local options."""

    def __init__(self, config_entry: ConfigEntry) -> None:
        """Initialize Homematic(IP) Local options flow."""
        self.config_entry = config_entry
        self.data: ConfigType = dict(self.config_entry.data.items())

    async def async_step_init(self, user_input: ConfigType | None = None) -> FlowResult:
        """Manage the Homematic(IP) Local options."""
        return await self.async_step_central(user_input=user_input)

    async def async_step_central(
        self, user_input: ConfigType | None = None
    ) -> FlowResult:
        """Manage the Homematic(IP) Local devices options."""
        if user_input is not None:
            old_interfaces = self.data[ATTR_INTERFACE]
            self.data = _get_ccu_data(self.data, user_input=user_input)
            self.data[ATTR_INTERFACE] = old_interfaces
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
            _LOGGER.debug("ConfigFlow.step_interface, no user input")
            return self.async_show_form(
                step_id="interface",
                data_schema=get_interface_schema(
                    use_tls=self.data[ATTR_TLS],
                    data=self.data,
                ),
            )

        _update_interface_input(data=self.data, interface_input=interface_input)
        errors = {}

        try:
            serial = await _async_validate_config_and_get_serial(self.hass, self.data)
        except CannotConnect:
            errors["base"] = "cannot_connect"
        except InvalidAuth:
            errors["base"] = "invalid_auth"
        except Exception:  # pylint: disable=broad-except
            _LOGGER.exception("Unexpected exception")
            errors["base"] = "unknown"
        else:
            self.hass.config_entries.async_update_entry(
                entry=self.config_entry, unique_id=serial, data=self.data
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


def _get_ccu_data(data: ConfigType, user_input: ConfigType) -> ConfigType:
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
        ATTR_INTERFACE: {},
    }


def _update_interface_input(data: ConfigType, interface_input: ConfigType) -> None:
    if interface_input is not None:
        if interface_input[ATTR_HMIP_RF_ENABLED]:
            data[ATTR_INTERFACE][IF_HMIP_RF_NAME] = {
                ATTR_PORT: interface_input[ATTR_HMIP_RF_PORT],
            }
        if interface_input[ATTR_BIDCOS_RF_ENABLED]:
            data[ATTR_INTERFACE][IF_BIDCOS_RF_NAME] = {
                ATTR_PORT: interface_input[ATTR_BIDCOS_RF_PORT],
            }
        if interface_input[ATTR_VIRTUAL_DEVICES_ENABLED]:
            data[ATTR_INTERFACE][IF_VIRTUAL_DEVICES_NAME] = {
                ATTR_PORT: interface_input[ATTR_VIRTUAL_DEVICES_PORT],
                ATTR_PATH: interface_input.get(ATTR_VIRTUAL_DEVICES_PATH),
            }
        if interface_input[ATTR_BIDCOS_WIRED_ENABLED]:
            data[ATTR_INTERFACE][IF_BIDCOS_WIRED_NAME] = {
                ATTR_PORT: interface_input[ATTR_BIDCOS_WIRED_PORT],
            }


def _get_instance_name(friendly_name: Any | None) -> str | None:
    if not friendly_name:
        return None
    name = str(friendly_name)
    if name.startswith("HomeMatic Central - "):
        return name.replace("HomeMatic Central - ", "")
    if name.startswith("HomeMatic Central "):
        return name.replace("HomeMatic Central ", "")
    return name


def _get_serial(model_description: Any | None) -> str | None:
    if not model_description:
        return None
    md = str(model_description)
    if len(md) > 10:
        return md[-10]
    return None
