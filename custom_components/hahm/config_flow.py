"""Config flow for hahomematic integration."""
from __future__ import annotations

import logging
import functools
from typing import Any

import voluptuous as vol
from xmlrpc.client import ProtocolError

from homeassistant import config_entries
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResult
from homeassistant.exceptions import HomeAssistantError

from .const import DOMAIN, ATTR_INSTANCENAME

from hahomematic.const import (
    ATTR_HOSTNAME,
    ATTR_PORT,
    ATTR_PATH,
    ATTR_USERNAME,
    ATTR_PASSWORD,
    ATTR_SSL,
    ATTR_VERIFY_SSL,
    ATTR_CALLBACK_IP,
    ATTR_CALLBACK_PORT,
    ATTR_JSONPORT,
    PORT_HMIP,
    PORT_JSONRPC,
)
import hahomematic.config
from hahomematic.server import Server
from hahomematic.client import Client

_LOGGER = logging.getLogger(__name__)


DOMAIN_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_INSTANCENAME): str,
    }
)

DATA_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_HOSTNAME): str,
        vol.Required(ATTR_PORT, default=PORT_HMIP): int,
        vol.Required(ATTR_PATH, default="/"): str,
        vol.Optional(ATTR_USERNAME, default=""): str,
        vol.Optional(ATTR_PASSWORD, default=""): str,
        vol.Optional(ATTR_SSL, default=False): bool,
        vol.Optional(ATTR_VERIFY_SSL, default=False): bool,
        vol.Optional(ATTR_CALLBACK_IP): str,
        vol.Optional(ATTR_CALLBACK_PORT): int,
        vol.Optional(ATTR_JSONPORT, default=PORT_JSONRPC): int,
    }
)


async def validate_input(
    hass: HomeAssistant, data: dict[str, Any], instancename: str
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
    _server = Server(
        local_ip=data[ATTR_CALLBACK_IP], local_port=data[ATTR_CALLBACK_PORT]
    )
    try:

        _client = await hass.async_add_executor_job(
            functools.partial(
                Client,
                name=instancename,
                host=data[ATTR_HOSTNAME],
                port=data[ATTR_PORT],
                username=data[ATTR_USERNAME],
                password=data[ATTR_PASSWORD],
                local_port=_server.local_port,
            )
        )
    except ConnectionError as e:
        _LOGGER.exception(e)
        raise CannotConnect
    except ProtocolError as e:
        _LOGGER.exception(e)
        raise InvalidAuth
    except Exception as e:
        _LOGGER.exception(e)

    # Return info that you want to store in the config entry.
    return {"title": "Name of the device"}


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
            return self.async_create_entry(
                title=user_input[ATTR_INSTANCENAME], data=user_input
            )

        return self.async_show_form(step_id="user", data_schema=DOMAIN_SCHEMA)

    @staticmethod
    def async_get_options_flow(config_entry: config_entries.ConfigEntry):
        """Return config flow for options."""
        return OptionsConfigFlow(config_entry)


class OptionsConfigFlow(config_entries.ConfigFlow):
    """Handle a config flow for hahomematic."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_LOCAL_POLL

    def __init__(self, config_entry: config_entries.ConfigEntry):
        """initialize configflow"""
        self.config_entry = config_entry

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step."""
        if user_input is None:
            _LOGGER.warning("Landed, no user input    ")
            return self.async_show_form(
                step_id="init", data_schema=DATA_SCHEMA, last_step=True
            )

        if user_input is not None:
            _LOGGER.warning("Landed here: %s", user_input)
        #            return self.async_show_form(step_id="init", data_schema=DATA_SCHEMA)

        errors = {}

        try:
            info = await validate_input(
                self.hass, user_input, self.config_entry.data.get(ATTR_INSTANCENAME)
            )
        except CannotConnect:
            errors["base"] = "cannot_connect"
        except InvalidAuth:
            errors["base"] = "invalid_auth"
        except Exception:  # pylint: disable=broad-except
            _LOGGER.exception("Unexpected exception")
            errors["base"] = "unknown"
        else:
            return self.async_create_entry(title="", data=user_input)

        return self.async_show_form(
            step_id="init", data_schema=DATA_SCHEMA, errors=errors
        )


class CannotConnect(HomeAssistantError):
    """Error to indicate we cannot connect."""


class InvalidAuth(HomeAssistantError):
    """Error to indicate there is invalid auth."""
