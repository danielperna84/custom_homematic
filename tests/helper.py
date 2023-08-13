"""Helpers for tests."""
from __future__ import annotations

import logging
from unittest.mock import MagicMock, Mock, patch

from hahomematic import const as hahomematic_const
from hahomematic.central_unit import CentralConfig
from hahomematic.client import InterfaceConfig, LocalRessources, _ClientConfig
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
import homeassistant.helpers.aiohttp_client as http_client
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.homematicip_local import config
from custom_components.homematicip_local.const import CONTROL_UNITS, DOMAIN
from custom_components.homematicip_local.control_unit import ControlUnit
from tests import const

_LOGGER = logging.getLogger(__name__)

# pylint: disable=protected-access


class Factory:
    """Factory for a central_unit with one local client."""

    def __init__(self, hass: HomeAssistant, mock_config_entry: MockConfigEntry):
        """Init the central factory."""
        self._hass = hass
        self.mock_config_entry = mock_config_entry
        self.system_event_mock = MagicMock()
        self.entity_event_mock = MagicMock()
        self.ha_event_mock = MagicMock()
        config.DEFAULT_SYSVAR_REGISTRY_ENABLED = True

    async def setup_environment(
        self,
        address_device_translation: dict[str, str],
        add_sysvars: bool = False,
        add_programs: bool = False,
        ignore_devices_on_create: list[str] | None = None,
        un_ignore_list: list[str] | None = None,
    ) -> tuple[HomeAssistant, ControlUnit]:
        """Return a central based on give address_device_translation."""
        interface_config = _get_local_client_interface_config(
            address_device_translation=address_device_translation,
            ignore_devices_on_create=ignore_devices_on_create,
        )

        central = await CentralConfig(
            name=const.INSTANCE_NAME,
            host=const.HOST,
            username=const.USERNAME,
            password=const.PASSWORD,
            central_id="test1234",
            storage_folder="homematicip_local",
            interface_configs={
                interface_config,
            },
            default_callback_port=54321,
            client_session=http_client.async_get_clientsession(self._hass),
            load_un_ignore=un_ignore_list is not None,
            un_ignore_list=un_ignore_list,
        ).create_central()

        central.register_system_event_callback(self.system_event_mock)
        central.register_entity_event_callback(self.entity_event_mock)
        central.register_ha_event_callback(self.ha_event_mock)

        client = await _ClientConfig(
            central=central,
            interface_config=interface_config,
            local_ip="127.0.0.1",
        ).get_client()

        with (
            patch(
                "hahomematic.client.create_client",
                return_value=client,
            ),
            patch(
                "hahomematic.client.ClientLocal.get_all_system_variables",
                return_value=const.SYSVAR_DATA if add_sysvars else [],
            ),
            patch(
                "hahomematic.client.ClientLocal.get_all_programs",
                return_value=const.PROGRAM_DATA if add_programs else [],
            ),
            patch(
                "hahomematic.central_unit.CentralUnit._identify_callback_ip",
                return_value="127.0.0.1",
            ),
            patch("custom_components.homematicip_local.find_free_port", return_value=8765),
            patch(
                "custom_components.homematicip_local.control_unit.ControlUnit._async_create_central",
                return_value=central,
            ),
        ):
            self.mock_config_entry.add_to_hass(self._hass)
            await self._hass.config_entries.async_setup(self.mock_config_entry.entry_id)
            await self._hass.async_block_till_done()
            assert self.mock_config_entry.state == ConfigEntryState.LOADED

        control: ControlUnit = self._hass.data[DOMAIN][CONTROL_UNITS][
            self.mock_config_entry.entry_id
        ]
        if control._scheduler:
            control._scheduler.de_init()
        await self._hass.async_block_till_done()
        return self._hass, control


def get_and_check_state(
    hass: HomeAssistant, control: ControlUnit, entity_id: str, entity_name: str
):
    """Get and test basic device."""
    ha_state = hass.states.get(entity_id)
    assert ha_state is not None
    assert ha_state.name == entity_name
    hm_entity = control.async_get_hm_entity(entity_id=entity_id)

    return ha_state, hm_entity


def _get_local_client_interface_config(
    address_device_translation: dict[str, str],
    ignore_devices_on_create: list[str] | None = None,
) -> InterfaceConfig:
    """Return a central based on give address_device_translation."""
    _ignore_devices_on_create: list[str] = (
        ignore_devices_on_create if ignore_devices_on_create else []
    )

    return InterfaceConfig(
        central_name=const.INSTANCE_NAME,
        interface=hahomematic_const.HmInterface.LOCAL,
        port=const.LOCAL_PORT,
        local_resources=LocalRessources(
            address_device_translation=address_device_translation,
            ignore_devices_on_create=_ignore_devices_on_create,
        ),
    )


def get_mock(instance, **kwargs):
    """Create a mock and copy instance attributes over mock."""
    if isinstance(instance, Mock):
        instance.__dict__.update(instance._mock_wraps.__dict__)
        return instance

    mock = MagicMock(spec=instance, wraps=instance, **kwargs)
    mock.__dict__.update(instance.__dict__)
    return mock
