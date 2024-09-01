"""switch for Homematic(IP) Local."""

from __future__ import annotations

import logging
from typing import Any, Final

from hahomematic.const import CALLBACK_TYPE, HmPlatform
from hahomematic.platforms.update import HmUpdate

from homeassistant.components.update import UpdateEntity, UpdateEntityFeature
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import HomematicConfigEntry
from .const import DOMAIN
from .control_unit import ControlUnit, signal_new_hm_entity

_LOGGER = logging.getLogger(__name__)
ATTR_FIRMWARE_UPDATE_STATE: Final = "firmware_update_state"


async def async_setup_entry(
    hass: HomeAssistant,
    entry: HomematicConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Homematic(IP) Local update platform."""
    control_unit: ControlUnit = entry.runtime_data

    @callback
    def async_add_update(hm_entities: tuple[HmUpdate, ...]) -> None:
        """Add update from Homematic(IP) Local."""
        _LOGGER.debug("ASYNC_ADD_UPDATE: Adding %i entities", len(hm_entities))

        if entities := [
            HaHomematicUpdate(
                control_unit=control_unit,
                hm_entity=hm_entity,
            )
            for hm_entity in hm_entities
        ]:
            async_add_entities(entities)

    entry.async_on_unload(
        func=async_dispatcher_connect(
            hass=hass,
            signal=signal_new_hm_entity(entry_id=entry.entry_id, platform=HmPlatform.UPDATE),
            target=async_add_update,
        )
    )

    async_add_update(hm_entities=control_unit.get_new_entities(entity_type=HmUpdate))


class HaHomematicUpdate(UpdateEntity):
    """Representation of the HomematicIP update entity."""

    _attr_supported_features = UpdateEntityFeature.PROGRESS | UpdateEntityFeature.INSTALL

    _attr_has_entity_name = True
    _attr_should_poll = False
    _attr_entity_registry_enabled_default = True

    _unrecorded_attributes = frozenset({ATTR_FIRMWARE_UPDATE_STATE})

    def __init__(
        self,
        control_unit: ControlUnit,
        hm_entity: HmUpdate,
    ) -> None:
        """Initialize the generic entity."""
        self._cu: ControlUnit = control_unit
        self._hm_entity: HmUpdate = hm_entity
        self._attr_unique_id = f"{DOMAIN}_{hm_entity.unique_id}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, hm_entity.device.identifier)},
        )
        self._attr_extra_state_attributes = {
            ATTR_FIRMWARE_UPDATE_STATE: hm_entity.device.firmware_update_state
        }
        self._unregister_callbacks: list[CALLBACK_TYPE] = []
        _LOGGER.debug("init: Setting up %s", hm_entity.full_name)

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        return self._hm_entity.available

    @property
    def installed_version(self) -> str | None:
        """Version installed and in use."""
        return self._hm_entity.firmware

    @property
    def in_progress(self) -> bool | int | None:
        """Update installation progress."""
        return self._hm_entity.in_progress()

    @property
    def latest_version(self) -> str | None:
        """Latest version available for install."""
        return self._hm_entity.latest_firmware

    @property
    def name(self) -> str | None:
        """Return the name of the entity."""
        return self._hm_entity.name

    async def async_install(self, version: str | None, backup: bool, **kwargs: Any) -> None:
        """Install an update."""
        await self._hm_entity.update_firmware(refresh_after_update_intervals=(10, 60))

    async def async_update(self) -> None:
        """Update entity."""
        await self._hm_entity.refresh_firmware_data()

    async def async_added_to_hass(self) -> None:
        """Register callbacks and load initial data."""
        self._unregister_callbacks.append(
            self._hm_entity.register_entity_updated_callback(
                cb=self._async_entity_changed, custom_id=self.entity_id
            )
        )
        self._unregister_callbacks.append(
            self._hm_entity.register_device_removed_callback(cb=self._async_device_removed)
        )

    @callback
    def _async_entity_changed(self, *args: Any, **kwargs: Any) -> None:
        """Handle device state changes."""
        # Don't update disabled entities
        if self.enabled:
            _LOGGER.debug("Update state changed event fired for %s", self.name)
            self.async_schedule_update_ha_state()
        else:
            _LOGGER.debug(
                "Update state changed event for %s not fired. Entity is disabled",
                self.name,
            )

    async def async_will_remove_from_hass(self) -> None:
        """Run when hmip device will be removed from hass."""
        # Remove callback from device.
        for unregister in self._unregister_callbacks:
            if unregister is not None:
                unregister()

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
