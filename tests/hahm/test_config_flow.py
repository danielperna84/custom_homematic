"""Test the HaHomematic config flow."""
from typing import Any
from unittest.mock import patch

from homeassistant import config_entries
from homeassistant.components.homematicip_local.config_flow import (
    ATTR_BIDCOS_RF_ENABLED,
    ATTR_BIDCOS_RF_PORT,
    ATTR_HMIP_RF_ENABLED,
    ATTR_HOST,
    ATTR_BIDCOS_WIRED_ENABLED,
    ATTR_INSTANCE_NAME,
    ATTR_PASSWORD,
    ATTR_PORT,
    ATTR_TLS,
    ATTR_USERNAME,
    ATTR_VIRTUAL_DEVICES_ENABLED,
    IF_BIDCOS_RF_NAME,
    IF_HMIP_RF_NAME,
    IF_BIDCOS_WIRED_NAME,
    IF_VIRTUAL_DEVICES_NAME,
    CannotConnect,
    InvalidAuth,
)
from homeassistant.components.homematicip_local.const import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import RESULT_TYPE_CREATE_ENTRY, RESULT_TYPE_FORM

TEST_INSTANCE_NAME = "pytest"
TEST_HOST = "1.1.1.1"
TEST_USERNAME = "test-username"
TEST_PASSWORD = "test-password"


async def test_form(hass: HomeAssistant) -> None:
    """Test we get the form."""
    interface = await async_check_form(hass, interface_data={})

    if_hmip_rf = interface[IF_HMIP_RF_NAME]
    assert if_hmip_rf[ATTR_PORT] == 2010
    if_bidcos_rf = interface[IF_BIDCOS_RF_NAME]
    assert if_bidcos_rf[ATTR_PORT] == 2001
    if_virtual_devices = interface[IF_VIRTUAL_DEVICES_NAME]
    assert if_virtual_devices[ATTR_PORT] == 9292
    assert interface.get(IF_BIDCOS_WIRED_NAME) is None


async def test_form_no_hmip_other_bidcos_port(hass: HomeAssistant) -> None:
    """Test we get the form."""
    interface_data = {ATTR_HMIP_RF_ENABLED: False, ATTR_BIDCOS_RF_PORT: 5555}
    interface = await async_check_form(hass, interface_data=interface_data)

    assert interface.get(IF_HMIP_RF_NAME) is None
    if_bidcos_rf = interface[IF_BIDCOS_RF_NAME]
    assert if_bidcos_rf[ATTR_PORT] == 5555
    if_virtual_devices = interface[IF_VIRTUAL_DEVICES_NAME]
    assert if_virtual_devices[ATTR_PORT] == 9292
    assert interface.get(IF_BIDCOS_WIRED_NAME) is None


async def test_form_only_hs485(hass: HomeAssistant) -> None:
    """Test we get the form."""
    interface_data = {
        ATTR_HMIP_RF_ENABLED: False,
        ATTR_BIDCOS_RF_ENABLED: False,
        ATTR_VIRTUAL_DEVICES_ENABLED: False,
        ATTR_BIDCOS_WIRED_ENABLED: True,
    }
    interface = await async_check_form(hass, interface_data=interface_data)

    assert interface.get(IF_HMIP_RF_NAME) is None
    assert interface.get(IF_BIDCOS_RF_NAME) is None
    assert interface.get(IF_VIRTUAL_DEVICES_NAME) is None

    if_BIDCOS_WIRED = interface[IF_BIDCOS_WIRED_NAME]
    assert if_BIDCOS_WIRED[ATTR_PORT] == 2000


async def test_form_tls(hass: HomeAssistant) -> None:
    """Test we get the form with tls."""
    interface = await async_check_form(hass, interface_data={}, tls=True)

    if_hmip_rf = interface[IF_HMIP_RF_NAME]
    assert if_hmip_rf[ATTR_PORT] == 42010
    if_bidcos_rf = interface[IF_BIDCOS_RF_NAME]
    assert if_bidcos_rf[ATTR_PORT] == 42001
    if_virtual_devices = interface[IF_VIRTUAL_DEVICES_NAME]
    assert if_virtual_devices[ATTR_PORT] == 49292
    assert interface.get(IF_BIDCOS_WIRED_NAME) is None


async def async_check_form(
    hass: HomeAssistant, interface_data: dict[str, Any], tls: bool = False
) -> dict[str, Any]:
    """Test we get the form."""
    if interface_data is None:
        interface_data = {}

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == RESULT_TYPE_FORM
    assert result["errors"] is None

    with patch(
        "homeassistant.components.homematicip_local.config_flow._async_validate_input",
        return_value=True,
    ), patch(
        "homeassistant.components.homematicip_local.async_setup_entry",
        return_value=True,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                ATTR_INSTANCE_NAME: TEST_INSTANCE_NAME,
                ATTR_HOST: TEST_HOST,
                ATTR_USERNAME: TEST_USERNAME,
                ATTR_PASSWORD: TEST_PASSWORD,
                ATTR_TLS: tls,
            },
        )
        await hass.async_block_till_done()

        assert result2["type"] == RESULT_TYPE_FORM
        assert result2["handler"] == DOMAIN
        assert result2["step_id"] == "interface"

        flow = next(
            flow
            for flow in hass.config_entries.flow.async_progress()
            if flow["flow_id"] == result["flow_id"]
        )
        assert flow["context"]["unique_id"] == TEST_HOST

        result3 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            interface_data,
        )
        await hass.async_block_till_done()

    assert result3["type"] == RESULT_TYPE_CREATE_ENTRY
    assert result3["handler"] == DOMAIN
    assert result3["title"] == TEST_INSTANCE_NAME
    data = result3["data"]
    assert data[ATTR_INSTANCE_NAME] == TEST_INSTANCE_NAME
    assert data[ATTR_HOST] == TEST_HOST
    assert data[ATTR_USERNAME] == TEST_USERNAME
    assert data[ATTR_PASSWORD] == TEST_PASSWORD
    return data["interface"]


async def test_form_invalid_auth(hass: HomeAssistant) -> None:
    """Test we handle invalid auth."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == RESULT_TYPE_FORM
    assert result["errors"] is None

    with patch(
        "homeassistant.components.homematicip_local.config_flow._async_validate_input",
        side_effect=InvalidAuth,
    ), patch(
        "homeassistant.components.homematicip_local.async_setup_entry",
        return_value=True,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                ATTR_INSTANCE_NAME: TEST_INSTANCE_NAME,
                ATTR_HOST: TEST_HOST,
                ATTR_USERNAME: TEST_USERNAME,
                ATTR_PASSWORD: TEST_PASSWORD,
            },
        )
        await hass.async_block_till_done()

        assert result2["type"] == RESULT_TYPE_FORM
        assert result2["handler"] == DOMAIN
        assert result2["step_id"] == "interface"

        flow = next(
            flow
            for flow in hass.config_entries.flow.async_progress()
            if flow["flow_id"] == result["flow_id"]
        )
        assert flow["context"]["unique_id"] == TEST_HOST

        result3 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {},
        )
        await hass.async_block_till_done()

    assert result3["type"] == RESULT_TYPE_FORM
    assert result3["errors"] == {"base": "invalid_auth"}


async def test_form_cannot_connect(hass: HomeAssistant) -> None:
    """Test we handle cannot connect error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == RESULT_TYPE_FORM
    assert result["errors"] is None

    with patch(
        "homeassistant.components.homematicip_local.config_flow._async_validate_input",
        side_effect=CannotConnect,
    ), patch(
        "homeassistant.components.homematicip_local.async_setup_entry",
        return_value=True,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                ATTR_INSTANCE_NAME: TEST_INSTANCE_NAME,
                ATTR_HOST: TEST_HOST,
                ATTR_USERNAME: TEST_USERNAME,
                ATTR_PASSWORD: TEST_PASSWORD,
            },
        )
        await hass.async_block_till_done()

        assert result2["type"] == RESULT_TYPE_FORM
        assert result2["handler"] == DOMAIN
        assert result2["step_id"] == "interface"

        flow = next(
            flow
            for flow in hass.config_entries.flow.async_progress()
            if flow["flow_id"] == result["flow_id"]
        )
        assert flow["context"]["unique_id"] == TEST_HOST

        result3 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {},
        )
        await hass.async_block_till_done()

    assert result3["type"] == RESULT_TYPE_FORM
    assert result3["errors"] == {"base": "cannot_connect"}
