"""Config flow for hahomematic integration."""
from __future__ import annotations

import functools
import logging
from typing import Any
from xmlrpc.client import ProtocolError

import hahomematic.config
import voluptuous as vol
from hahomematic.client import Client
from hahomematic.const import (ATTR_CALLBACK_IP, ATTR_CALLBACK_PORT,
                               ATTR_HOSTNAME, ATTR_JSONPORT, ATTR_PASSWORD,
                               ATTR_PATH, ATTR_PORT, ATTR_SSL, ATTR_USERNAME,
                               ATTR_VERIFY_SSL, DEFAULT_TLS, IP_ANY_V4,
                               PORT_ANY, PORT_HMIP, PORT_JSONRPC)
from hahomematic.server import Server
from homeassistant import config_entries
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResult
from homeassistant.exceptions import HomeAssistantError

from . import create_client, create_server
from .const import (ATTR_ADD_ANOTHER_INTERFACE, ATTR_INSTANCENAME,
                    ATTR_INTERFACE, ATTR_INTERFACENAME, ATTR_JSONSSL, DOMAIN)

_LOGGER = logging.getLogger(__name__)

INTERFACE_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_INTERFACENAME): str,
        vol.Required(ATTR_PORT, default=PORT_HMIP): int,
        vol.Required(ATTR_PATH, default="/"): str,
        vol.Optional(ATTR_SSL, default=DEFAULT_TLS): bool,
        vol.Optional(ATTR_VERIFY_SSL, default=False): bool,
        vol.Optional(ATTR_ADD_ANOTHER_INTERFACE, default=False): bool,
    }
)

DOMAIN_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_INSTANCENAME): str,
        vol.Required(ATTR_HOSTNAME): str,
        vol.Optional(ATTR_USERNAME, default=""): str,
        vol.Optional(ATTR_PASSWORD, default=""): str,
        vol.Optional(ATTR_CALLBACK_IP, default=IP_ANY_V4): str,
        vol.Optional(ATTR_CALLBACK_PORT, default=PORT_ANY): int,
        vol.Optional(ATTR_JSONPORT, default=PORT_JSONRPC): int,
        vol.Optional(ATTR_JSONSSL, default=DEFAULT_TLS): bool,
    }
)


async def validate_input(
    hass: HomeAssistant, data: dict[str, Any], interface_name: str
) -> dict[str, Any]:
    """Validate the user input allows us to connect.

    Data has the keys with values provided by the user.
    """
    # Specify a unique name to identify our server.
    hahomematic.config.INTERFACE_ID = "homeassistant_homematic"
    # For testing we set a short INIT_TIMEOUT
    hahomematic.config.INIT_TIMEOUT = 10
    # We have to set the cache location of stored data so the server can load
    # it while initializing.
    hahomematic.config.CACHE_DIR = "cache"
    # Add callbacks to handle the events and see what happens on the system.
    # hahomematic.config.CALLBACK_SYSTEM = systemcallback
    # hahomematic.config.CALLBACK_EVENT = eventcallback
    # hahomematic.config.CALLBACK_ENTITY_UPDATE = entityupdatecallback
    # Create a server that listens on 127.0.0.1:* and identifies itself as instancename

    hahm_server = create_server(data)
    try:
        await create_client(hass, hahm_server, data, interface_name)
    except ConnectionError as e:
        _LOGGER.exception(e)
        raise CannotConnect
    except ProtocolError as e:
        _LOGGER.exception(e)
        raise InvalidAuth
    except Exception as e:
        _LOGGER.exception(e)
    else:
        return True


class DomainConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a instance flow for hahomematic."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_LOCAL_POLL

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step."""
        if user_input is not None:
            await self.async_set_unique_id(user_input[ATTR_INSTANCENAME])
            self._abort_if_unique_id_configured()
            self.data = {
                    ATTR_INSTANCENAME: user_input[ATTR_INSTANCENAME],
                    ATTR_HOSTNAME: user_input[ATTR_HOSTNAME],
                    ATTR_USERNAME: user_input[ATTR_USERNAME],
                    ATTR_PASSWORD: user_input[ATTR_PASSWORD],
                    ATTR_CALLBACK_IP: user_input[ATTR_CALLBACK_IP],
                    ATTR_CALLBACK_PORT: user_input[ATTR_CALLBACK_PORT],
                    ATTR_JSONPORT: user_input[ATTR_JSONPORT],
                    ATTR_JSONSSL: user_input[ATTR_JSONSSL],
                    ATTR_INTERFACE : {}
                }

            return await self.async_step_interface()

        return self.async_show_form(step_id="user", data_schema=DOMAIN_SCHEMA)

    async def async_step_interface(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step."""
        if user_input is None:
            _LOGGER.warning("Landed, no user input    ")
            return self.async_show_form(step_id="interface", data_schema=INTERFACE_SCHEMA)

        if user_input is not None:
            _LOGGER.warning("Landed here: %s", user_input)

            interface_data = {
                    ATTR_PORT: user_input[ATTR_PORT],
                    ATTR_PATH: user_input[ATTR_PATH],
                    ATTR_SSL: user_input[ATTR_SSL],
                    ATTR_VERIFY_SSL: user_input[ATTR_VERIFY_SSL],
                    ATTR_CALLBACK_IP: user_input[ATTR_CALLBACK_IP],
                    ATTR_CALLBACK_PORT: user_input[ATTR_CALLBACK_PORT],
                }

            self.data[ATTR_INTERFACE][user_input[ATTR_INTERFACENAME]] = interface_data

        errors = {}

        try:
            info = await validate_input(
                self.hass, self.data, user_input[ATTR_INTERFACENAME]
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

            return self.async_create_entry(title=self.data[ATTR_INSTANCENAME], data=self.data)

        return self.async_show_form(
            step_id="interface", data_schema=INTERFACE_SCHEMA, errors=errors
        )


class CannotConnect(HomeAssistantError):
    """Error to indicate we cannot connect."""


class InvalidAuth(HomeAssistantError):
    """Error to indicate there is invalid auth."""
