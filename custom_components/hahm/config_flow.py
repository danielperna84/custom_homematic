"""Config flow for hahomematic integration."""
from __future__ import annotations

import logging
from typing import Any
from xmlrpc.client import ProtocolError

from hahomematic import config
from hahomematic.client import Client
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
    PORT_HMIP,
)
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.core import HomeAssistant, callback
from homeassistant.data_entry_flow import FlowResult
from homeassistant.exceptions import HomeAssistantError

from .const import (
    ATTR_ADD_ANOTHER_INTERFACE,
    ATTR_INSTANCE_NAME,
    ATTR_INTERFACE,
    ATTR_INTERFACE_NAME,
    ATTR_JSON_TLS,
    ATTR_PATH,
    CONF_ENABLE_SENSORS_FOR_SYSTEM_VARIABLES,
    CONF_ENABLE_VIRTUAL_CHANNELS,
    DOMAIN,
)
from .control_unit import ControlConfig

_LOGGER = logging.getLogger(__name__)

INTERFACE_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_INTERFACE_NAME): str,
        vol.Required(ATTR_PORT, default=PORT_HMIP): int,
        vol.Optional(ATTR_PATH): str,
        vol.Optional(ATTR_ADD_ANOTHER_INTERFACE, default=False): bool,
    }
)

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


async def validate_input(
    hass: HomeAssistant, data: dict[str, Any], interface_name: str
) -> bool:
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
        first_client: Client = control_unit.central.get_primary_client()
        return await first_client.is_connected()
    except ConnectionError as cex:
        _LOGGER.exception(cex)
        raise CannotConnect from cex
    except ProtocolError as cex:
        _LOGGER.exception(cex)
        raise InvalidAuth from cex
    except Exception as cex:
        _LOGGER.exception(cex)
    return False


class DomainConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a instance flow for hahomematic."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_LOCAL_PUSH

    def __init__(self):
        self.data = {}

    async def async_step_user(self, user_input: dict[str, Any] = None) -> FlowResult:
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
        self, user_input: dict[str, Any] = None
    ) -> FlowResult:
        """Handle the initial step."""
        if user_input is None:
            _LOGGER.warning("Landed, no user input    ")
            return self.async_show_form(
                step_id="interface", data_schema=INTERFACE_SCHEMA
            )

        if user_input is not None:
            _LOGGER.warning("Landed here: %s", user_input)

            interface_data = {
                ATTR_PORT: user_input[ATTR_PORT],
                ATTR_PATH: user_input.get(ATTR_PATH),
            }

            self.data[ATTR_INTERFACE][user_input[ATTR_INTERFACE_NAME]] = interface_data

        errors = {}

        try:
            await validate_input(self.hass, self.data, user_input[ATTR_INTERFACE_NAME])
        except CannotConnect:
            errors["base"] = "cannot_connect"
        except InvalidAuth:
            errors["base"] = "invalid_auth"
        except Exception:  # pylint: disable=broad-except
            _LOGGER.exception("Unexpected exception")
            errors["base"] = "unknown"
        else:
            # If user ticked the box show this form again so they can add an
            # additional repo.
            if user_input.get("add_another_interface", False):
                return await self.async_step_interface()

            return self.async_create_entry(
                title=self.data[ATTR_INSTANCE_NAME], data=self.data
            )

        return self.async_show_form(
            step_id="interface", data_schema=INTERFACE_SCHEMA, errors=errors
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        """Get the options flow for this handler."""
        return HahmOptionsFlowHandler(config_entry)


class HahmOptionsFlowHandler(config_entries.OptionsFlow):
    """Handle hahm options."""

    def __init__(self, config_entry):
        """Initialize hahm options flow."""
        self.config_entry = config_entry
        self.options = dict(config_entry.options)
        self._cu = None

    async def async_step_init(self, user_input=None):
        """Manage the hahm options."""
        self._cu = self.hass.data[DOMAIN][self.config_entry.entry_id]
        return await self.async_step_hahm_devices()

    async def async_step_hahm_devices(self, user_input=None):
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


class CannotConnect(HomeAssistantError):
    """Error to indicate we cannot connect."""


class InvalidAuth(HomeAssistantError):
    """Error to indicate there is invalid auth."""
