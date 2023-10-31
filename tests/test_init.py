"""Test the Homematic(IP) Local init."""
from __future__ import annotations

from unittest.mock import patch

from pytest_homeassistant_custom_component.common import MockConfigEntry

import custom_components.homematicip_local
from custom_components.homematicip_local import async_unload_entry
from custom_components.homematicip_local.const import CONF_ENABLE_SYSTEM_NOTIFICATIONS, DOMAIN
from custom_components.homematicip_local.control_unit import ControlUnit
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant

from tests import const


async def test_setup_entry(
    hass: HomeAssistant,
    mock_config_entry_v2: MockConfigEntry,
    mock_control_unit: ControlUnit,
) -> None:
    """Test setup entry."""
    # no config_entry exists
    assert len(hass.config_entries.async_entries(DOMAIN)) == 0
    assert not hass.data.get(DOMAIN)

    with patch("custom_components.homematicip_local.find_free_port", return_value=8765), patch(
        "custom_components.homematicip_local.control_unit.ControlConfig.create_control_unit",
        return_value=mock_control_unit,
    ):
        mock_config_entry_v2.add_to_hass(hass)
        await hass.config_entries.async_setup(mock_config_entry_v2.entry_id)
        await hass.async_block_till_done()
        config_entries = hass.config_entries.async_entries(DOMAIN)
        assert len(config_entries) == 1
        config_entry = config_entries[0]
        assert config_entry.state == ConfigEntryState.LOADED


async def test_check_min_version(
    hass: HomeAssistant,
    mock_config_entry_v2: MockConfigEntry,
    mock_control_unit: ControlUnit,
) -> None:
    """Test check_min_version."""
    # no config_entry exists

    orig_version = custom_components.homematicip_local.HMIP_LOCAL_MIN_VERSION
    custom_components.homematicip_local.HMIP_LOCAL_MIN_VERSION = "2099.1.1"
    mock_config_entry_v2.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_config_entry_v2.entry_id) is False
    custom_components.homematicip_local.HMIP_LOCAL_MIN_VERSION = orig_version


async def test_migrate_entry(
    hass: HomeAssistant,
    mock_config_entry_v1: MockConfigEntry,
    mock_control_unit: ControlUnit,
) -> None:
    """Test setup entry."""
    # no config_entry exists
    assert len(hass.config_entries.async_entries(DOMAIN)) == 0
    assert not hass.data.get(DOMAIN)

    with patch("custom_components.homematicip_local.find_free_port", return_value=8765), patch(
        "custom_components.homematicip_local.control_unit.ControlConfig.create_control_unit",
        return_value=mock_control_unit,
    ):
        mock_config_entry_v1.add_to_hass(hass)
        await hass.config_entries.async_setup(mock_config_entry_v1.entry_id)
        await hass.async_block_till_done()
        config_entries = hass.config_entries.async_entries(DOMAIN)
        assert len(config_entries) == 1
        config_entry = config_entries[0]
        assert config_entry.state == ConfigEntryState.LOADED
        assert config_entry.version == 2
        assert config_entry.data[CONF_ENABLE_SYSTEM_NOTIFICATIONS] is True


async def test_unload_entry(
    hass: HomeAssistant, mock_loaded_config_entry: MockConfigEntry
) -> None:
    """Test unload entry."""
    assert hass.data[DOMAIN]
    await hass.config_entries.async_unload(mock_loaded_config_entry.entry_id)
    await hass.async_block_till_done()
    assert DOMAIN not in hass.data
    # retry possible?
    assert await async_unload_entry(hass, mock_loaded_config_entry) is False


async def test_unload_wrong_entry(
    hass: HomeAssistant, mock_loaded_config_entry: MockConfigEntry
) -> None:
    """Test unload wrong entry."""
    mock_loaded_config_entry.entry_id = "123"
    assert hass.data[DOMAIN]

    # await hass.config_entries.async_unload(mock_loaded_config_entry.entry_id)
    assert await async_unload_entry(hass, mock_loaded_config_entry) is False
    await hass.async_block_till_done()
    assert hass.data[DOMAIN]


async def test_remove_entry(
    hass: HomeAssistant, mock_loaded_config_entry: MockConfigEntry
) -> None:
    """Test unload entry."""
    assert hass.data[DOMAIN]
    await hass.config_entries.async_remove(mock_loaded_config_entry.entry_id)
    await hass.async_block_till_done()
    assert DOMAIN not in hass.data


async def test_reload_entry(
    hass: HomeAssistant, mock_loaded_config_entry: MockConfigEntry
) -> None:
    """Test unload entry."""
    mock_loaded_config_entry.title = const.INSTANCE_NAME
    assert hass.data[DOMAIN]
    hass.config_entries.async_update_entry(mock_loaded_config_entry, title="Reload")
    await hass.async_block_till_done()
    assert hass.data[DOMAIN]
    mock_loaded_config_entry.title = "Reload"
