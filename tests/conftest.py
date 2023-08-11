"""Initializer helpers for Homematic(IP) Local."""
from __future__ import annotations

import datetime
from typing import Any
from unittest.mock import Mock, patch

from hahomematic.central_unit import CentralUnit
from homeassistant import config_entries
from homeassistant.components import ssdp
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry
from pytest_homeassistant_custom_component.plugins import enable_custom_integrations  # noqa: F401

from custom_components.homematicip_local.const import DOMAIN
from custom_components.homematicip_local.control_unit import ControlConfig, ControlUnit

TEST_DEFAULT_PORT = 8967
TEST_ENTRY_ID = "12345678"
TEST_HOST = "1.2.3.4"
TEST_INSTANCE_NAME = "pytest"
TEST_PASSWORD = "test-password"
TEST_UNIQUE_ID = "9876543210"
TEST_USERNAME = "test-username"
TEST_SERIAL = "0987654321"

INVALID_PASSWORD = "In_VäLid"


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations: Any):  # noqa: F811
    """Auto add enable_custom_integrations."""
    yield


@pytest.fixture
def entry_data_v1() -> dict[str, Any]:
    """Create data for config entry."""
    return {
        "instance_name": TEST_INSTANCE_NAME,
        "host": TEST_HOST,
        "username": TEST_USERNAME,
        "password": TEST_PASSWORD,
        "tls": False,
        "verify_tls": False,
        "sysvar_scan_enabled": True,
        "sysvar_scan_interval": 30,
        "callback_host": None,
        "callback_port": None,
        "json_port": None,
        "enable_system_notifications": True,
        "interface": {"HmIP-RF": {"port": 2010}, "BidCos-RF": {"port": 2001}},
    }


@pytest.fixture
def entry_data_v2(entry_data_v1) -> dict[str, Any]:
    """Create data for config entry."""
    entry_data_v2 = entry_data_v1
    entry_data_v2["enable_system_notifications"] = True
    return entry_data_v2


@pytest.fixture
def mock_config_entry_v1(entry_data_v1) -> config_entries.ConfigEntry:  # )
    """Create a mock config entry for Homematic(IP) Local."""

    return MockConfigEntry(
        entry_id=TEST_ENTRY_ID,
        version=1,
        domain=DOMAIN,
        title=TEST_INSTANCE_NAME,
        data=entry_data_v1,
        options={},
        pref_disable_new_entities=False,
        pref_disable_polling=False,
        source="user",
        unique_id=TEST_UNIQUE_ID,
        disabled_by=None,
    )


@pytest.fixture
def mock_config_entry_v2(mock_config_entry_v1, entry_data_v2) -> config_entries.ConfigEntry:  # )
    """Create a mock config entry for Homematic(IP) Local."""

    mock_config_entry_v2 = mock_config_entry_v1
    mock_config_entry_v2.version = 2
    mock_config_entry_v2.data = entry_data_v2
    return mock_config_entry_v2


@pytest.fixture
def discovery_info() -> ssdp.SsdpServiceInfo:
    """Create a discovery info for Homematic(IP) Local."""
    return ssdp.SsdpServiceInfo(
        ssdp_usn=f"uuid:upnp-BasicDevice-1_0-3014F711A0001F{TEST_UNIQUE_ID}::upnp:rootdevice",
        ssdp_st="upnp:rootdevice",
        upnp={
            "deviceType": "urn:schemas-upnp-org:device:Basic:1",
            "presentationURL": None,
            "friendlyName": f"HomeMatic Central - {TEST_INSTANCE_NAME}",
            "manufacturer": "EQ3",
            "manufacturerURL": "http://www.homematic.com",
            "modelDescription": f"HomeMatic Central 3014F711A0001F{TEST_UNIQUE_ID}",
            "modelName": "HomeMatic Central",
            "UDN": f"uuid:upnp-BasicDevice-1_0-3014F711A0001F{TEST_UNIQUE_ID}",
            "UPC": TEST_UNIQUE_ID,
            "serviceList": {
                "service": {
                    "serviceType": "urn:schemas-upnp-org:service:dummy:1",
                    "serviceId": "urn:upnp-org:serviceId:dummy1",
                    "controlURL": None,
                    "eventSubURL": None,
                    "SCPDURL": None,
                }
            },
        },
        ssdp_location=f"http://{TEST_HOST}/upnp/basic_dev.cgi",
        ssdp_nt=None,
        ssdp_udn=f"uuid:upnp-BasicDevice-1_0-3014F711A0001F{TEST_UNIQUE_ID}",
        ssdp_ext="",
        ssdp_server="HomeMatic",
        ssdp_headers={
            "CACHE-CONTROL": "max-age=5000",
            "EXT": "",
            "LOCATION": f"http://{TEST_HOST}/upnp/basic_dev.cgi",
            "SERVER": "HomeMatic",
            "ST": "upnp:rootdevice",
            "USN": f"uuid:upnp-BasicDevice-1_0-3014F711A0001F{TEST_UNIQUE_ID}::upnp:rootdevice",
            "_timestamp": datetime.datetime(2023, 8, 9, 10, 25, 39, 669454),
            "_host": TEST_HOST,
            "_port": 1900,
            "_local_addr": ("0.0.0.0", 40610),
            "_remote_addr": (TEST_HOST, 1900),
            "_udn": f"uuid:upnp-BasicDevice-1_0-3014F711A0001F{TEST_UNIQUE_ID}",
            "_location_original": f"http://{TEST_HOST}/upnp/basic_dev.cgi",
            "location": f"http://{TEST_HOST}/upnp/basic_dev.cgi",
        },
        x_homeassistant_matching_domains={"homematicip_local"},
    )


@pytest.fixture
def control_config(hass: HomeAssistant, entry_data_v2) -> ControlConfig:
    """Create a config for the control unit."""
    return ControlConfig(
        hass=hass,
        entry_id=TEST_ENTRY_ID,
        data=entry_data_v2,
        default_port=TEST_DEFAULT_PORT,
    )


@pytest.fixture
def mock_control_unit() -> ControlUnit:
    """Create mock control unit."""

    control_unit = Mock(
        spec=ControlUnit,
    )
    control_unit.async_get_new_hm_entities_by_platform.return_value = []
    control_unit.async_get_new_hm_hub_entities_by_platform.return_value = []
    control_unit.async_get_new_hm_channel_event_entities_by_event_type.return_value = []
    control_unit.async_get_update_entities.return_value = []

    with patch(
        "custom_components.homematicip_local.control_unit.ControlUnit",
        autospec=True,
        return_value=control_unit,
    ):
        yield control_unit


@pytest.fixture
async def mock_loaded_config_entry(
    hass, mock_config_entry_v2: MockConfigEntry, mock_control_unit: ControlUnit
) -> ControlUnit:
    """Create mock running control unit."""
    with patch("custom_components.homematicip_local.find_free_port", return_value=8765), patch(
        "custom_components.homematicip_local.control_unit.ControlConfig.async_get_control_unit",
        return_value=mock_control_unit,
    ):
        mock_config_entry_v2.add_to_hass(hass)
        await hass.config_entries.async_setup(mock_config_entry_v2.entry_id)
        await hass.async_block_till_done()
        assert mock_config_entry_v2.state == ConfigEntryState.LOADED
        yield mock_config_entry_v2


@pytest.fixture
def mock_central_unit() -> CentralUnit:
    """Create mock control unit."""
    central_unit = Mock(
        spec=CentralUnit,
    )

    with patch(
        "hahomematic.central_unit.CentralUnit",
        autospec=True,
        return_value=central_unit,
    ):
        yield central_unit
