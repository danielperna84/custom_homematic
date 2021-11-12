"""Generic entity for the HomematicIP Cloud component."""
from __future__ import annotations

import logging
from typing import Any

from hahomematic.const import DATA_LOAD_FAIL

from homeassistant.core import callback
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.entity import DeviceInfo, Entity

from .const import (
    DEVICE_PARAMETER_BINARY_SENSOR_DEVICE_CLASSES,
    PARAMETER_BINARY_SENSOR_DEVICE_CLASSES,
    PARAMETER_ENTITY_CATEGORIES,
    PARAMETER_SENSOR_DEVICE_CLASSES,
)
from .controlunit import ControlUnit

_LOGGER = logging.getLogger(__name__)


class HaHomematicGenericEntity(Entity):
    """Representation of the HomematicIP generic entity."""

    def __init__(self, cu: ControlUnit, hm_entity) -> None:
        """Initialize the generic entity."""
        self._cu = cu
        self._hm_entity = hm_entity

        # Marker showing that the Hm device hase been removed.
        self.hm_device_removed = False
        self._device_class = _get_device_class(self._hm_entity)
        _LOGGER.info("Setting up %s", self.name)

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        return self._hm_entity.available

    @property
    def device_class(self) -> str:
        """Return the class of this sensor."""
        return self._device_class

    @property
    def device_info(self) -> DeviceInfo:
        """Return device specific attributes."""
        return self._hm_entity.device_info

    @property
    def entity_category(self) -> str | None:
        """Return the entity categorie."""
        if hasattr(self._hm_entity, "parameter"):
            return PARAMETER_ENTITY_CATEGORIES.get(self._hm_entity.parameter)
        return None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return the state attributes of the generic entity."""
        return self._hm_entity.extra_state_attributes

    @property
    def name(self) -> str:
        """Return the name of the generic entity."""
        return self._hm_entity.name

    @property
    def should_poll(self) -> bool:
        """No polling needed."""
        return False

    @property
    def unique_id(self) -> str:
        """Return a unique ID."""
        return self._hm_entity.unique_id

    async def async_added_to_hass(self) -> None:
        """Register callbacks."""
        self._hm_entity.register_update_callback(self._async_device_changed)
        self._hm_entity.register_remove_callback(self._async_device_removed)
        self._cu.add_hm_entity(hm_entity=self._hm_entity)
        await self._init_data()

    async def async_update(self):
        return

    async def _init_data(self) -> None:
        """Init data. Disable entity if data load fails due to missing device value."""
        load_state = await self._hm_entity.load_data()
        # if load_state == DATA_LOAD_FAIL and not self.registry_entry.disabled_by:
        #    await self._update_registry_entry(disabled_by=er.DISABLED_INTEGRATION)
        # elif self.registry_entry.disabled_by == er.DISABLED_INTEGRATION:
        #    await self._update_registry_entry(disabled_by=None)

    async def _update_registry_entry(self, disabled_by) -> None:
        """Update registry_entry disabled_by."""
        (await er.async_get_registry(self.hass)).async_update_entity(
            self.entity_id, disabled_by=disabled_by
        )

    @callback
    def _async_device_changed(self, *args, **kwargs) -> None:
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

        # Only go further if the device/entity should be removed from registries
        # due to a removal of the HM device.

        if self.hm_device_removed:
            try:
                self._cu.remove_hm_entity(self)
                await self.async_remove_from_registries()
            except KeyError as err:
                _LOGGER.debug("Error removing HM device from registry: %s", err)

    async def async_remove_from_registries(self) -> None:
        """Remove entity/device from registry."""

        # Remove callback from device.
        self._hm_entity.unregister_update_callback()
        self._hm_entity.unregister_remove_callback()

        if not self.registry_entry:
            return

        device_id = self.registry_entry.device_id
        if device_id:
            # Remove from device registry.
            device_registry = await dr.async_get_registry(self.hass)
            if device_id in device_registry.devices:
                # This will also remove associated entities from entity registry.
                device_registry.async_remove_device(device_id)
        else:
            # Remove from entity registry.
            # Only relevant for entities that do not belong to a device.
            entity_id = self.registry_entry.entity_id
            if entity_id:
                entity_registry = await er.async_get_registry(self.hass)
                if entity_id in entity_registry.entities:
                    entity_registry.async_remove(entity_id)

    @callback
    def _async_device_removed(self, *args, **kwargs) -> None:
        """Handle hm device removal."""
        # Set marker showing that the Hm device hase been removed.
        self.hm_device_removed = True
        self.hass.async_create_task(self.async_remove(force_remove=True))


def _get_device_class(hm_entity):
    """get device_class by parameter"""
    if hasattr(hm_entity, "parameter"):
        if hm_entity.platform == "binary_sensor":
            device_class = DEVICE_PARAMETER_BINARY_SENSOR_DEVICE_CLASSES.get((hm_entity._device.device_type, hm_entity.parameter))
            if not device_class:
                device_class = PARAMETER_BINARY_SENSOR_DEVICE_CLASSES.get(hm_entity.parameter)
            return device_class

        if hm_entity.platform == "sensor":
            return PARAMETER_SENSOR_DEVICE_CLASSES.get(hm_entity.parameter)

    return None
