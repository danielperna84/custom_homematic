"""Tests for switch entities of hahomematic."""
from __future__ import annotations

import pytest

from homeassistant.const import STATE_UNKNOWN

from tests import const, helper

TEST_DEVICES: dict[str, str] = {
    "VCU7837366": "HB-UNI-Sensor1.json",
}

# pylint: disable=protected-access


@pytest.mark.asyncio
async def test_sensor_trans(factory: helper.Factory) -> None:
    """Test sensor with translation."""
    entity_id = "sensor.hb_uni_sensor1_vcu7837366_dew_point"
    entity_name = "HB-UNI-Sensor1_VCU7837366 dew point"

    hass, control = await factory.setup_environment(TEST_DEVICES)
    ha_state, hm_entity = helper.get_and_check_state(
        hass=hass, control=control, entity_id=entity_id, entity_name=entity_name
    )
    assert ha_state.state == STATE_UNKNOWN

    control.central.event(const.INTERFACE_ID, "VCU7837366:1", "Taupunkt", 1)
    assert hass.states.get(entity_id).state == "1.0"

    control.central.event(const.INTERFACE_ID, "VCU7837366:1", "Taupunkt", 0)
    assert hass.states.get(entity_id).state == "0.0"


@pytest.mark.asyncio
async def test_sensor_to_trans(factory: helper.Factory) -> None:
    """Test sensor without translation."""
    entity_id = "sensor.hb_uni_sensor1_vcu7837366_abs_luftfeuchte"
    entity_name = "HB-UNI-Sensor1_VCU7837366 Abs Luftfeuchte"

    hass, control = await factory.setup_environment(TEST_DEVICES)
    ha_state, hm_entity = helper.get_and_check_state(
        hass=hass, control=control, entity_id=entity_id, entity_name=entity_name
    )
    assert ha_state.state == STATE_UNKNOWN

    control.central.event(const.INTERFACE_ID, "VCU7837366:1", "Abs_Luftfeuchte", 1)
    assert hass.states.get(entity_id).state == "1.0"

    control.central.event(const.INTERFACE_ID, "VCU7837366:1", "Abs_Luftfeuchte", 0)
    assert hass.states.get(entity_id).state == "0.0"
