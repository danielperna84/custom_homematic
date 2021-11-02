"""Config flow for hahomematic integration."""
from __future__ import annotations

import logging
from typing import Any
from xmlrpc.client import ProtocolError

import voluptuous as vol
from hahomematic import config
from hahomematic.const import (
    ATTR_CALLBACK_HOST,
    ATTR_CALLBACK_PORT,
    ATTR_HOST,
    ATTR_JSON_PORT,
    ATTR_PASSWORD,
    ATTR_PATH,
    ATTR_PORT,
    ATTR_TLS,
    ATTR_USERNAME,
    ATTR_VERIFY_TLS,
    DEFAULT_TLS,
    IP_ANY_V4,
    PORT_ANY,
    PORT_HMIP,
    PORT_JSON_RPC,
)

from homeassistant import config_entries
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResult
from homeassistant.exceptions import HomeAssistantError

from .const import (
    ATTR_ADD_ANOTHER_INTERFACE,
    ATTR_INSTANCE_NAME,
    ATTR_INTERFACE,
    ATTR_INTERFACE_NAME,
    ATTR_JSON_TLS,
    DOMAIN,
)
from .controlunit import ControlUnit

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
        vol.Optional(ATTR_JSON_PORT, default=PORT_JSON_RPC): int,
        vol.Optional(ATTR_JSON_TLS, default=DEFAULT_TLS): bool,
    }
)


async def validate_input(
    hass: HomeAssistant, data: dict[str, Any], interface_name: str
) -> bool:
    """Validate the user input allows us to connect.

    Data has the keys with values provided by the user.
    """

    # For testing we set a short INIT_TIMEOUT
    config.INIT_TIMEOUT = 10
    # We have to set the cache location of stored data so the server can load
    # it while initializing.
    config.CACHE_DIR = "cache"

    cu = ControlUnit(hass, data=data)
    cu.create_server()
    try:
        await cu.create_clients()
        return True
    except ConnectionError as e:
        _LOGGER.exception(e)
        raise CannotConnect
    except ProtocolError as e:
        _LOGGER.exception(e)
        raise InvalidAuth
    except Exception as e:
        _LOGGER.exception(e)
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
                ATTR_INSTANCE_NAME: user_input[ATTR_INSTANCE_NAME],
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
            info = await validate_input(
                self.hass, self.data, user_input[ATTR_INTERFACE_NAME]
            )
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


class CannotConnect(HomeAssistantError):
    """Error to indicate we cannot connect."""


class InvalidAuth(HomeAssistantError):
    """Error to indicate there is invalid auth."""
