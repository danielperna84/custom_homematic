"""Tests for event entities of Homematic(IP) Local."""

from __future__ import annotations

import asyncio

import pytest
from pytest_homeassistant_custom_component.common import async_capture_events

from aiohomematic.const import DeviceTriggerEventType
from homeassistant.components.event import DoorbellEventType
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.entity_platform import async_get_platforms

from tests import const
from tests.helper import Factory

TEST_DEVICES: dict[str, str] = {
    "VCU4567298": "HmIP-DBB.json",
    "VCU7935803": "HMIP-WRC2.json",
}

# pylint: disable=protected-access


async def _wait_for_entity(*, hass: HomeAssistant, unique_id: str) -> str:
    """
    Poll until the event entity with the given unique_id appears and return its entity_id.

    Event entities are added via dispatcher after platform setup, and their
    entity_id depends on registration order (the device may not carry its
    name yet), so the entity is resolved via the registry instead of by a
    hard-coded entity_id.
    """
    registry = er.async_get(hass)
    async with asyncio.timeout(2):
        while (
            entity_id := registry.async_get_entity_id("event", "homematicip_local", unique_id)
        ) is None or hass.states.get(entity_id) is None:
            await hass.async_block_till_done()
            await asyncio.sleep(0.01)
    return entity_id


async def _wait_for_event_type(*, hass: HomeAssistant, entity_id: str, expected: str) -> None:
    """
    Poll until the entity's last event_type matches the expected one.

    The chain GenericEvent -> ChannelEventGroup -> entity crosses two
    aiohomematic task hops that HA's block_till_done does not track, so a
    fixed number of loop ticks is not deterministic. Raises TimeoutError
    when the event never arrives.
    """
    async with asyncio.timeout(2):
        while (state := hass.states.get(entity_id)) is None or state.attributes["event_type"] != expected:
            await hass.async_block_till_done()
            await asyncio.sleep(0.01)


async def _wait_for_bus_event(*, hass: HomeAssistant, events: list) -> None:
    """
    Poll until at least one event has been captured from the HA event bus.

    Same reasoning as _wait_for_event_type: the trigger crosses aiohomematic
    task hops that block_till_done does not track. Raises TimeoutError when the
    event never arrives.
    """
    async with asyncio.timeout(2):
        while not events:
            await hass.async_block_till_done()
            await asyncio.sleep(0.01)


class TestAioHomematicEvent:
    """Tests for AioHomematicEvent entities."""

    @pytest.mark.asyncio
    async def test_doorbell_event_declares_and_fires_ring(
        self,
        factory_homegear: Factory,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """A doorbell event entity declares and fires 'ring' instead of 'press_short'."""
        hass, control = await factory_homegear.setup_environment(TEST_DEVICES)
        entity_id = await _wait_for_entity(hass=hass, unique_id="homematicip_local_event_group_keypress_vcu4567298_1")
        # HA warns on add when a doorbell event entity lacks the 'ring' event
        # type (and rejects it from HA 2027.4) - see issue #3300.
        assert "is a doorbell event entity but does not support" not in caplog.text
        ha_state = hass.states.get(entity_id)
        assert ha_state.attributes["device_class"] == "doorbell"

        event_types = ha_state.attributes["event_types"]
        assert DoorbellEventType.RING in event_types
        assert "press_short" not in event_types
        assert "press_long" in event_types

        await control.central.event_coordinator.data_point_event(
            interface_id=const.INTERFACE_ID, channel_address="VCU4567298:1", parameter="PRESS_SHORT", value=True
        )
        await _wait_for_event_type(hass=hass, entity_id=entity_id, expected=DoorbellEventType.RING)

        await control.central.event_coordinator.data_point_event(
            interface_id=const.INTERFACE_ID, channel_address="VCU4567298:1", parameter="PRESS_LONG", value=True
        )
        await _wait_for_event_type(hass=hass, entity_id=entity_id, expected="press_long")

    @pytest.mark.asyncio
    async def test_event_attributes_carry_channel_no(
        self,
        factory_homegear: Factory,
    ) -> None:
        """
        Event entities expose the channel number as an attribute of its own.

        The button blueprints match a press by channel. Without this attribute
        they would have to split the channel address themselves, which is how
        the two backends' channel spellings (aiohomematic ``.no`` vs. the loom
        client's ``.number``) would end up in every blueprint.
        """
        hass, _control = await factory_homegear.setup_environment(TEST_DEVICES)

        for channel_no in (1, 2):
            entity_id = await _wait_for_entity(
                hass=hass, unique_id=f"homematicip_local_event_group_keypress_vcu7935803_{channel_no}"
            )
            attributes = hass.states.get(entity_id).attributes
            assert attributes["channel_no"] == channel_no
            assert attributes["address"] == f"VCU7935803:{channel_no}"
            assert attributes["interface_id"] == const.INTERFACE_ID

    @pytest.mark.asyncio
    async def test_event_device_info_carries_device_name(
        self,
        factory_homegear: Factory,
    ) -> None:
        """
        Event entities carry the device name in their DeviceInfo.

        When the event platform registers its entities before any other
        platform creates the device entry, a name-less DeviceInfo would
        create the device without a name and the generated (sticky)
        entity_id degrades to the config-entry title (e.g.
        event.centraltest_ch1).
        """
        hass, _control = await factory_homegear.setup_environment(TEST_DEVICES)
        entity_id = await _wait_for_entity(hass=hass, unique_id="homematicip_local_event_group_keypress_vcu4567298_1")

        entity = next(
            entity
            for platform in async_get_platforms(hass, "homematicip_local")
            for entity in platform.entities.values()
            if entity.entity_id == entity_id
        )
        device_info = entity.device_info
        assert device_info is not None
        assert device_info.get("name") == "HmIP-DBB_VCU4567298"
        assert device_info.get("model") == "HmIP-DBB"
        assert device_info.get("serial_number") == "VCU4567298"

    @pytest.mark.asyncio
    async def test_keypress_reaches_the_ha_event_bus(
        self,
        factory_homegear: Factory,
    ) -> None:
        """
        A button press must arrive on the HA event bus as 'homematic.keypress'.

        The entity state and the bus event are two independent consumers of the
        same trigger, and only the bus event drives automations. When the click
        event schema rejected the payload, the entity kept updating while every
        keypress automation lost its trigger without a trace - the failure mode
        of aiohomematic#3374.
        """
        hass, control = await factory_homegear.setup_environment(TEST_DEVICES)
        await _wait_for_entity(hass=hass, unique_id="homematicip_local_event_group_keypress_vcu7935803_1")
        events = async_capture_events(hass, DeviceTriggerEventType.KEYPRESS)

        await control.central.event_coordinator.data_point_event(
            interface_id=const.INTERFACE_ID, channel_address="VCU7935803:1", parameter="PRESS_SHORT", value=True
        )
        await _wait_for_bus_event(hass=hass, events=events)

        event_data = events[0].data
        assert event_data["type"] == "press_short"
        # Blueprints match the channel numerically, so the type matters.
        assert event_data["subtype"] == 1
        assert event_data["address"] == "VCU7935803"
        assert event_data["device_id"]

    @pytest.mark.asyncio
    async def test_non_doorbell_event_keeps_native_event_types(
        self,
        factory_homegear: Factory,
    ) -> None:
        """A non-doorbell keypress entity keeps the native Homematic event types."""
        hass, control = await factory_homegear.setup_environment(TEST_DEVICES)
        entity_id = await _wait_for_entity(hass=hass, unique_id="homematicip_local_event_group_keypress_vcu7935803_1")
        ha_state = hass.states.get(entity_id)
        assert ha_state.attributes["device_class"] == "button"

        event_types = ha_state.attributes["event_types"]
        assert "press_short" in event_types
        assert DoorbellEventType.RING not in event_types

        await control.central.event_coordinator.data_point_event(
            interface_id=const.INTERFACE_ID, channel_address="VCU7935803:1", parameter="PRESS_SHORT", value=True
        )
        await _wait_for_event_type(hass=hass, entity_id=entity_id, expected="press_short")
