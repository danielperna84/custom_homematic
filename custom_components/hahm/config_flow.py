"""Config flow for hahomematic integration."""
from __future__ import annotations

import logging
from xmlrpc.client import ProtocolError

from hahomematic import config
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
import voluptuous as vol
from voluptuous.schema_builder import Schema

from homeassistant import config_entries
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.data_entry_flow import FlowResult
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.typing import ConfigType

from .const import (
    ATTR_INSTANCE_NAME,
    ATTR_INTERFACE,
    ATTR_JSON_TLS,
    ATTR_PATH,
    CONF_ENABLE_SENSORS_FOR_SYSTEM_VARIABLES,
    CONF_ENABLE_VIRTUAL_CHANNELS,
    DOMAIN,
)
from .control_unit import ControlConfig, ControlUnit

_LOGGER = logging.getLogger(__name__)

ATTR_HMIP_RF_ENABLED = "hmip_rf_enabled"
ATTR_HMIP_RF_PORT = "hmip_rf_port"
ATTR_HM_RF_ENABLED = "hm_rf_enabled"
ATTR_HM_RF_PORT = "hm_rf_port"
ATTR_GROUPS_ENABLED = "groups_enabled"
ATTR_GROUPS_PORT = "groups_port"
ATTR_GROUPS_PATH = "groups_path"
ATTR_HS485D_ENABLED = "hs485d_enabled"
ATTR_HS485D_PORT = "hs485d_port"

IF_GROUPS_NAME = "Groups"
IF_GROUPS_PORT = 9292
IF_GROUPS_TLS_PORT = 49292
IF_GROUPS_PATH = "/groups"
IF_HMIP_RF_NAME = "HmIP-RF"
IF_HMIP_RF_PORT = 2010
IF_HMIP_RF_TLS_PORT = 42010
IF_HS485D_NAME = "HS485D"
IF_HS485D_PORT = 2000
IF_HS485D_TLS_PORT = 42000
IF_HM_RF_NAME = "HM-RF"
IF_HM_RF_PORT = 2001
IF_HM_RF_TLS_PORT = 42001

DOMAIN_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_INSTANCE_NAME): str,
        vol.Required(ATTR_HOST): str,
        vol.Optional(ATTR_USERNAME, default=""): str,
        vol.Optional(ATTR_PASSWORD, default=""): str,
        vol.Optional(ATTR_CALLBACK_HOST, default=IP_ANY_V4): str,
        vol.Optional(ATTR_CALLBACK_PORT, default=PORT_ANY): int,
        vol.Optional(ATTR_TLS, default=DEFAULT_TLS): bool,
        vol.Optional(ATTR_VERIFY_TLS, default=False): bool,
        vol.Optional(ATTR_JSON_PORT): int,
        vol.Optional(ATTR_JSON_TLS, default=DEFAULT_TLS): bool,
    }
)


def get_interface_schema(use_tls: bool) -> Schema:
    """Return the interface schema with or without tls ports."""
    return vol.Schema(
        {
            vol.Required(ATTR_HMIP_RF_ENABLED, default=True): bool,
            vol.Required(
                ATTR_HMIP_RF_PORT,
                default=IF_HMIP_RF_TLS_PORT if use_tls else IF_HMIP_RF_PORT,
            ): int,
            vol.Required(ATTR_HM_RF_ENABLED, default=True): bool,
            vol.Required(
                ATTR_HM_RF_PORT, default=IF_HM_RF_TLS_PORT if use_tls else IF_HM_RF_PORT
            ): int,
            vol.Required(ATTR_GROUPS_ENABLED, default=True): bool,
            vol.Required(
                ATTR_GROUPS_PORT,
                default=IF_GROUPS_TLS_PORT if use_tls else IF_GROUPS_PORT,
            ): int,
            vol.Required(ATTR_GROUPS_PATH, default=IF_GROUPS_PATH): str,
            vol.Required(ATTR_HS485D_ENABLED, default=False): bool,
            vol.Required(
                ATTR_HS485D_PORT,
                default=IF_HS485D_TLS_PORT if use_tls else IF_HS485D_PORT,
            ): int,
        }
    )


async def validate_input(hass: HomeAssistant, data: ConfigType) -> bool:
    """
    Validate the user input allows us to connect.
    Data has the keys with values provided by the user.
    """

    # We have to set the cache location of stored data so the server can load
    # it while initializing.
    config.CACHE_DIR = "cache"

    control_unit = ControlConfig(
        hass=hass, entry_id="validate", data=data
    ).get_control_unit()
    control_unit.create_central()
    try:
        await control_unit.create_clients()
        if first_client := control_unit.central.get_primary_client():
            return await first_client.is_connected()
    except ConnectionError as cex:
        _LOGGER.exception(cex)
        raise CannotConnect from cex
    except ProtocolError as cex:
        _LOGGER.exception(cex)
        raise InvalidAuth from cex
    except Exception as cex:  # pylint: disable=broad-except
        _LOGGER.exception(cex)
    return False


class DomainConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a instance flow for hahomematic."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_LOCAL_PUSH

    def __init__(self) -> None:
        self.data: ConfigType = {}

    async def async_step_user(self, user_input: ConfigType | None = None) -> FlowResult:
        """Handle the initial step."""
        if user_input is not None:
            await self.async_set_unique_id(user_input[ATTR_INSTANCE_NAME])
            self._abort_if_unique_id_configured()
            self.data = {
                ATTR_INSTANCE_NAME: user_input[ATTR_INSTANCE_NAME].title(),
                ATTR_HOST: user_input[ATTR_HOST],
                ATTR_USERNAME: user_input[ATTR_USERNAME],
                ATTR_PASSWORD: user_input[ATTR_PASSWORD],
                ATTR_CALLBACK_HOST: user_input.get(ATTR_CALLBACK_HOST),
                ATTR_CALLBACK_PORT: user_input.get(ATTR_CALLBACK_PORT),
                ATTR_TLS: user_input.get(ATTR_TLS),
                ATTR_VERIFY_TLS: user_input.get(ATTR_VERIFY_TLS),
                ATTR_JSON_PORT: user_input.get(ATTR_JSON_PORT),
                ATTR_JSON_TLS: user_input.get(ATTR_JSON_TLS),
                ATTR_INTERFACE: {},
            }

            return await self.async_step_interface()

        return self.async_show_form(step_id="user", data_schema=DOMAIN_SCHEMA)

    async def async_step_interface(
        self, user_input: ConfigType | None = None
    ) -> FlowResult:
        """Handle the initial step."""
        use_tls = self.data[ATTR_TLS]
        if user_input is None:
            _LOGGER.warning("ConfigFlow.step_interface, no user input")
            return self.async_show_form(
                step_id="interface", data_schema=get_interface_schema(use_tls)
            )

        if user_input is not None:
            if user_input[ATTR_HMIP_RF_ENABLED]:
                self.data[ATTR_INTERFACE][IF_HMIP_RF_NAME] = {
                    ATTR_PORT: user_input[ATTR_HMIP_RF_PORT],
                }
            if user_input[ATTR_HM_RF_ENABLED]:
                self.data[ATTR_INTERFACE][IF_HM_RF_NAME] = {
                    ATTR_PORT: user_input[ATTR_HM_RF_PORT],
                }
            if user_input[ATTR_GROUPS_ENABLED]:
                self.data[ATTR_INTERFACE][IF_GROUPS_NAME] = {
                    ATTR_PORT: user_input[ATTR_GROUPS_PORT],
                    ATTR_PATH: user_input.get(ATTR_GROUPS_PATH),
                }
            if user_input[ATTR_HS485D_ENABLED]:
                self.data[ATTR_INTERFACE][IF_HS485D_NAME] = {
                    ATTR_PORT: user_input[ATTR_HS485D_PORT],
                }

        errors = {}

        try:
            await validate_input(self.hass, self.data)
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
            step_id="interface",
            data_schema=get_interface_schema(use_tls),
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
        self.options = dict(config_entry.options)

    async def async_step_init(self, user_input: ConfigType | None = None) -> FlowResult:
        """Manage the hahm options."""
        return await self.async_step_hahm_devices()

    async def async_step_hahm_devices(
        self, user_input: ConfigType | None = None
    ) -> FlowResult:
        """Manage the hahm devices options."""
        if user_input is not None:
            self.options.update(user_input)
            return self.async_create_entry(title="", data=self.options)

        return self.async_show_form(
            step_id="hahm_devices",
            data_schema=vol.Schema(
                {
                    vol.Optional(
                        CONF_ENABLE_VIRTUAL_CHANNELS,
                        default=self._cu.enable_virtual_channels,
                    ): bool,
                    vol.Optional(
                        CONF_ENABLE_SENSORS_FOR_SYSTEM_VARIABLES,
                        default=self._cu.enable_sensors_for_system_variables,
                    ): bool,
                }
            ),
        )

    @property
    def _cu(self) -> ControlUnit:
        control_unit: ControlUnit = self.hass.data[DOMAIN][self.config_entry.entry_id]
        return control_unit


class CannotConnect(HomeAssistantError):
    """Error to indicate we cannot connect."""


class InvalidAuth(HomeAssistantError):
    """Error to indicate there is invalid auth."""
