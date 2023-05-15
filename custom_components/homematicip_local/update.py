"""switch for Homematic(IP) Local."""
from __future__ import annotations

import logging
from typing import Any, cast

from hahomematic.const import HmDeviceFirmwareState, HmPlatform
from hahomematic.platforms.update import HmUpdate

from homeassistant.components.update import UpdateEntity, UpdateEntityFeature
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import CONTROL_UNITS, DOMAIN, IDENTIFIER_SEPARATOR, MANUFACTURER_EQ3
from .control_unit import ControlUnit, async_signal_new_hm_entity

_LOGGER = logging.getLogger(__name__)
ATTR_FIRMWARE_UPDATE_STATE = "firmware_update_state"


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Homematic(IP) Local update platform."""
    control_unit: ControlUnit = hass.data[DOMAIN][CONTROL_UNITS][config_entry.entry_id]

    @callback
    def async_add_update(args: Any) -> None:
        """Add update from Homematic(IP) Local."""
        entities: list[HaHomematicUpdate] = []

        for hm_entity in args:
            entities.append(
                HaHomematicUpdate(
                    control_unit=control_unit,
                    hm_entity=hm_entity,
                )
            )

        if entities:
            async_add_entities(entities)

    config_entry.async_on_unload(
        async_dispatcher_connect(
            hass,
            async_signal_new_hm_entity(
                entry_id=config_entry.entry_id, platform=HmPlatform.UPDATE
            ),
            async_add_update,
        )
    )

    async_add_update(control_unit.async_get_update_entities())


class HaHomematicUpdate(UpdateEntity):
    """Representation of the HomematicIP update entity."""

    _attr_supported_features = (
        UpdateEntityFeature.PROGRESS | UpdateEntityFeature.INSTALL
    )

    _attr_has_entity_name = True
    _attr_should_poll = False
    _attr_entity_registry_enabled_default = True

    def __init__(
        self,
        control_unit: ControlUnit,
        hm_entity: HmUpdate,
    ) -> None:
        """Initialize the generic entity."""
        self._cu: ControlUnit = control_unit
        self._hm_entity: HmUpdate = hm_entity
        self._attr_unique_id = f"{DOMAIN}_{hm_entity.unique_identifier}"

        _LOGGER.debug("init: Setting up %s", hm_entity.full_name)

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        return self._hm_entity.available

    @property
    def device_info(self) -> DeviceInfo | None:
        """Return device specific attributes."""
        hm_device = self._hm_entity.device
        return DeviceInfo(
            identifiers={
                (
                    DOMAIN,
                    f"{hm_device.device_address}"
                    f"{IDENTIFIER_SEPARATOR}"
                    f"{hm_device.interface_id}",
                )
            },
            manufacturer=MANUFACTURER_EQ3,
            model=hm_device.device_type,
            name=hm_device.name,
            suggested_area=hm_device.room,
            # Link to the homematic control unit.
            via_device=cast(tuple[str, str], hm_device.central.name),
        )

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return the state attributes of the generic entity."""
        attributes: dict[str, Any] = {
            ATTR_FIRMWARE_UPDATE_STATE: self._hm_entity.firmware_update_state
        }

        return attributes

    @property
    def installed_version(self) -> str | None:
        """Version installed and in use."""
        return self._hm_entity.firmware

    @property
    def in_progress(self) -> bool | int | None:
        """Update installation progress."""
        return self._hm_entity.firmware_update_state not in (
            HmDeviceFirmwareState.UP_TO_DATE,
            HmDeviceFirmwareState.READY_FOR_UPDATE,
        )

    @property
    def latest_version(self) -> str | None:
        """Latest version available for install."""
        return self._hm_entity.available_firmware

    @property
    def name(self) -> str | None:
        """Return the name of the entity."""
        return self._hm_entity.name

    async def async_install(
        self, version: str | None, backup: bool, **kwargs: Any
    ) -> None:
        """Install an update."""
        await self._hm_entity.update_firmware()

    async def async_update(self) -> None:
        """Update entity."""
        await self._hm_entity.refresh_firmware_data()

    async def async_added_to_hass(self) -> None:
        """Register callbacks and load initial data."""

        self._hm_entity.register_update_callback(
            update_callback=self._async_device_changed
        )
        self._hm_entity.register_remove_callback(
            remove_callback=self._async_device_removed
        )
        self._cu.async_add_hm_update_entity(
            entity_id=self.entity_id, hm_entity=self._hm_entity
        )

    @callback
    def _async_device_changed(self, *args: Any, **kwargs: Any) -> None:
        """Handle device state changes."""
        # Don't update disabled entities
        if self.enabled:
            _LOGGER.debug("Event %s", self.name)
            self.async_write_ha_state()
        else:
            _LOGGER.debug(
                "Device Changed Event for %s not fired. Entity is disabled",
                self.name,
            )

    async def async_will_remove_from_hass(self) -> None:
        """Run when hmip device will be removed from hass."""
        # Remove callback from device.
        self._hm_entity.unregister_update_callback(
            update_callback=self._async_device_changed
        )
        self._hm_entity.unregister_remove_callback(
            remove_callback=self._async_device_removed
        )

    @callback
    def _async_device_removed(self, *args: Any, **kwargs: Any) -> None:
        """Handle hm device removal."""
        self.hass.async_create_task(self.async_remove(force_remove=True))

        if not self.registry_entry:
            return

        if device_id := self.registry_entry.device_id:
            # Remove from device registry.
            device_registry = dr.async_get(self.hass)
            if device_id in device_registry.devices:
                # This will also remove associated entities from entity registry.
                device_registry.async_remove_device(device_id)
