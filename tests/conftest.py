"""Initializer helpers for Homematic(IP) Local."""
from __future__ import annotations

import datetime
from typing import Any

from homeassistant import config_entries
from homeassistant.components import ssdp
import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry
from pytest_homeassistant_custom_component.plugins import (  # noqa: F401
    enable_custom_integrations,
)

from custom_components.homematicip_local.const import DOMAIN

TEST_ENTRY_ID = "12345678"
TEST_INSTANCE_NAME = "pytest"
TEST_HOST = "1.2.3.4"
TEST_USERNAME = "test-username"
TEST_PASSWORD = "test-password"
TEST_UNIQUE_ID = "9876543210"


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations: Any):  # noqa: F811
    """Auto add enable_custom_integrations."""
    yield


@pytest.fixture
def hmip_mock_config_entry() -> config_entries.ConfigEntry:  # )
    """Create a mock config entry for Homematic(IP) Local."""
    entry_data = {
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
    return MockConfigEntry(
        entry_id=TEST_ENTRY_ID,
        version=2,
        domain=DOMAIN,
        title=TEST_INSTANCE_NAME,
        data=entry_data,
        options={},
        pref_disable_new_entities=False,
        pref_disable_polling=False,
        source="user",
        unique_id=TEST_UNIQUE_ID,
        disabled_by=None,
    )


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
