"""Test the Homematic(IP) Local init."""
from __future__ import annotations

from unittest.mock import patch

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.homematicip_local.const import DOMAIN
from custom_components.homematicip_local.control_unit import ControlUnit


async def test_async_setup_entry(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, mock_control_unit: ControlUnit
) -> None:
    """Test async setup entry."""
    # no config_entry exists
    assert len(hass.config_entries.async_entries(DOMAIN)) == 0
    assert not hass.data.get(DOMAIN)

    with patch("custom_components.homematicip_local.find_free_port", return_value=8765), patch(
        "custom_components.homematicip_local.control_unit.ControlConfig.async_get_control_unit",
        return_value=mock_control_unit,
    ):
        mock_config_entry.add_to_hass(hass)
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()
        config_entries = hass.config_entries.async_entries(DOMAIN)
        assert len(config_entries) == 1
        config_entry = config_entries[0]
        assert config_entry.state == ConfigEntryState.LOADED
