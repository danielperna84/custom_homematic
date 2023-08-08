"""Initializer helpers for Homematic(IP) Local."""
from __future__ import annotations

from typing import Any

from homeassistant import config_entries
import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry
from pytest_homeassistant_custom_component.plugins import (  # noqa: F401
    enable_custom_integrations,
)

from custom_components.homematicip_local.const import DOMAIN

TEST_ENTRY_ID = "12345678"
TEST_INSTANCE_NAME = "pytest"
TEST_HOST = "1.1.1.1"
TEST_USERNAME = "test-username"
TEST_PASSWORD = "test-password"
TEST_UNIQUE_ID = "9876543210"


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations: Any):  # noqa: F811
    """Auto add enable_custom_integrations."""
    yield


@pytest.fixture
def hmip_mock_config_entry() -> config_entries.ConfigEntry:  # )
    """Create a mock config entry for homematic ip local."""
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
