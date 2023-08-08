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
    ATTR_INTERFACE,
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
)
from hahomematic.exceptions import AuthFailure, NoClients, NoConnection
from hahomematic.support import SystemInformation, check_password
from homeassistant import config_entries
from homeassistant.components import ssdp
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_NAME
from homeassistant.core import HomeAssistant, callback
from homeassistant.data_entry_flow import FlowResult
from homeassistant.exceptions import HomeAssistantError
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.typing import ConfigType
import voluptuous as vol
from voluptuous.schema_builder import UNDEFINED, Schema

from .const import (
    ATTR_ENABLE_SYSTEM_NOTIFICATIONS,
    ATTR_INSTANCE_NAME,
    ATTR_PATH,
    ATTR_SYSVAR_SCAN_ENABLED,
    ATTR_SYSVAR_SCAN_INTERVAL,
    CONTROL_UNITS,
    DEFAULT_SYSVAR_SCAN_INTERVAL,
    DOMAIN,
)
from .control_unit import (
    ControlConfig,
    ControlUnit,
    validate_config_and_get_system_information,
)

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
            vol.Required(ATTR_TLS, default=data.get(ATTR_TLS, DEFAULT_TLS)): cv.boolean,
            vol.Required(
                ATTR_VERIFY_TLS, default=data.get(ATTR_VERIFY_TLS, False)
            ): cv.boolean,
            vol.Optional(ATTR_CALLBACK_HOST): cv.string,
            vol.Optional(ATTR_CALLBACK_PORT): cv.port,
            vol.Optional(ATTR_JSON_PORT): cv.port,
            vol.Required(
                ATTR_SYSVAR_SCAN_ENABLED,
                default=data.get(ATTR_SYSVAR_SCAN_ENABLED, True),
            ): cv.boolean,
            vol.Required(
                ATTR_SYSVAR_SCAN_INTERVAL,
                default=data.get(
                    ATTR_SYSVAR_SCAN_INTERVAL, DEFAULT_SYSVAR_SCAN_INTERVAL
                ),
            ): vol.All(vol.Coerce(int), vol.Range(min=5)),
            vol.Required(
                ATTR_ENABLE_SYSTEM_NOTIFICATIONS,
                default=data.get(ATTR_ENABLE_SYSTEM_NOTIFICATIONS, True),
            ): cv.boolean,
        }
    )


def get_options_schema(data: ConfigType) -> Schema:
    """Return the options schema."""
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


async def _async_validate_config_and_get_system_information(
    hass: HomeAssistant, data: ConfigType
) -> SystemInformation | None:
    """Validate the user input allows us to connect."""
    control_config = ControlConfig(hass=hass, entry_id="validate", data=data)
    if not check_password(control_config.data.get(ATTR_PASSWORD)):
        raise InvalidPassword()
    return await validate_config_and_get_system_information(
        control_config=control_config
    )


class DomainConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle the instance flow for Homematic(IP) Local."""

    VERSION = 2
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
            system_information = (
                await _async_validate_config_and_get_system_information(
                    self.hass, self.data
                )
            )
            if system_information is not None:
                await self.async_set_unique_id(system_information.serial)
            self._abort_if_unique_id_configured()
        except (NoClients, NoConnection):
            errors["base"] = "cannot_connect"
        except AuthFailure:
            errors["base"] = "invalid_auth"
        except InvalidPassword:
            errors["base"] = "invalid_password"
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
        """Handle a discovered HomeMatic CCU."""
        _LOGGER.debug("Homematic(IP) Local SSDP discovery %s", pformat(discovery_info))
        instance_name = _get_instance_name(
            friendly_name=discovery_info.upnp.get("friendlyName")
        )
        serial = _get_serial(
            model_description=discovery_info.upnp.get("modelDescription")
        )

        host = cast(str, urlparse(discovery_info.ssdp_location).hostname)
        await self.async_set_unique_id(serial)

        self._abort_if_unique_id_configured()

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

    def __init__(self, entry: ConfigEntry) -> None:
        """Initialize Homematic(IP) Local options flow."""
        self.entry = entry
        self.data: ConfigType = dict(self.entry.data.items())

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
            step_id="central",
            data_schema=get_options_schema(data=self.data),
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
            system_information = (
                await _async_validate_config_and_get_system_information(
                    self.hass, self.data
                )
            )
        except (NoClients, NoConnection):
            errors["base"] = "cannot_connect"
        except AuthFailure:
            errors["base"] = "invalid_auth"
        except InvalidPassword:
            errors["base"] = "invalid_password"
        except Exception:  # pylint: disable=broad-except
            _LOGGER.exception("Unexpected exception")
            errors["base"] = "unknown"
        else:
            if system_information is not None:
                self.hass.config_entries.async_update_entry(
                    entry=self.entry,
                    unique_id=system_information.serial,
                    data=self.data,
                )
            return self.async_create_entry(title="", data={})

        return self.async_show_form(
            step_id="central",
            data_schema=get_options_schema(data=self.data),
            errors=errors,
        )

    @property
    def _control_unit(self) -> ControlUnit:
        control_unit: ControlUnit = self.hass.data[DOMAIN][CONTROL_UNITS][
            self.entry.entry_id
        ]
        return control_unit


class InvalidPassword(HomeAssistantError):
    """Error to indicate there is invalid password."""


def _get_ccu_data(data: ConfigType, user_input: ConfigType) -> ConfigType:
    return {
        ATTR_INSTANCE_NAME: user_input.get(
            ATTR_INSTANCE_NAME, data.get(ATTR_INSTANCE_NAME)
        ),
        ATTR_HOST: user_input[ATTR_HOST],
        ATTR_USERNAME: user_input[ATTR_USERNAME],
        ATTR_PASSWORD: user_input[ATTR_PASSWORD],
        ATTR_TLS: user_input[ATTR_TLS],
        ATTR_VERIFY_TLS: user_input[ATTR_VERIFY_TLS],
        ATTR_SYSVAR_SCAN_ENABLED: user_input[ATTR_SYSVAR_SCAN_ENABLED],
        ATTR_SYSVAR_SCAN_INTERVAL: user_input[ATTR_SYSVAR_SCAN_INTERVAL],
        ATTR_CALLBACK_HOST: user_input.get(ATTR_CALLBACK_HOST),
        ATTR_CALLBACK_PORT: user_input.get(ATTR_CALLBACK_PORT),
        ATTR_JSON_PORT: user_input.get(ATTR_JSON_PORT),
        ATTR_ENABLE_SYSTEM_NOTIFICATIONS: user_input[ATTR_ENABLE_SYSTEM_NOTIFICATIONS],
        ATTR_INTERFACE: {},
    }


def _update_interface_input(data: ConfigType, interface_input: ConfigType) -> None:
    if interface_input is not None:
        data[ATTR_INTERFACE] = {}
        if interface_input[ATTR_HMIP_RF_ENABLED] is True:
            data[ATTR_INTERFACE][IF_HMIP_RF_NAME] = {
                ATTR_PORT: interface_input[ATTR_HMIP_RF_PORT],
            }
        if interface_input[ATTR_BIDCOS_RF_ENABLED] is True:
            data[ATTR_INTERFACE][IF_BIDCOS_RF_NAME] = {
                ATTR_PORT: interface_input[ATTR_BIDCOS_RF_PORT],
            }
        if interface_input[ATTR_VIRTUAL_DEVICES_ENABLED] is True:
            data[ATTR_INTERFACE][IF_VIRTUAL_DEVICES_NAME] = {
                ATTR_PORT: interface_input[ATTR_VIRTUAL_DEVICES_PORT],
                ATTR_PATH: interface_input.get(ATTR_VIRTUAL_DEVICES_PATH),
            }
        if interface_input[ATTR_BIDCOS_WIRED_ENABLED] is True:
            data[ATTR_INTERFACE][IF_BIDCOS_WIRED_NAME] = {
                ATTR_PORT: interface_input[ATTR_BIDCOS_WIRED_PORT],
            }


def _get_instance_name(friendly_name: Any | None) -> str | None:
    """Return the instance name from the friendly_name."""
    if not friendly_name:
        return None
    name = str(friendly_name)
    if name.startswith("HomeMatic Central - "):
        return name.replace("HomeMatic Central - ", "")
    if name.startswith("HomeMatic Central "):
        return name.replace("HomeMatic Central ", "")
    return name


def _get_serial(model_description: Any | None) -> str | None:
    """Return the serial from the model_description."""
    if not model_description:
        return None
    model_desc = str(model_description)
    if len(model_desc) > 10:
        return model_desc[-10:]
    return None
