"""Generic entity for the HomematicIP Cloud component."""
from __future__ import annotations

from datetime import timedelta
import logging
from typing import Any, Generic, cast

from hahomematic.const import HmEntityUsage
from hahomematic.entity import (
    CallbackEntity,
    CustomEntity,
    GenericEntity,
    GenericSystemVariable,
)

from homeassistant.core import State, callback
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.helpers.entity import DeviceInfo, Entity
from homeassistant.helpers.restore_state import RestoreEntity

from .const import ATTR_VALUE_STATE, DOMAIN, HmEntityState
from .control_unit import ControlUnit
from .entity_helpers import get_entity_description
from .helpers import HmGenericEntity, HmGenericSysvarEntity

SCAN_INTERVAL = timedelta(seconds=120)
_LOGGER = logging.getLogger(__name__)


class HaHomematicGenericEntity(Generic[HmGenericEntity], Entity):
    """Representation of the HomematicIP generic entity."""

    def __init__(
        self,
        control_unit: ControlUnit,
        hm_entity: HmGenericEntity,
    ) -> None:
        """Initialize the generic entity."""
        self._cu: ControlUnit = control_unit
        self._hm_entity: HmGenericEntity = hm_entity
        self._attr_should_poll = self._hm_entity.should_poll
        if entity_description := get_entity_description(self._hm_entity):
            self.entity_description = entity_description
        if (
            entity_registry_enabled_default := self._get_entity_registry_enabled_default()
        ) is not None:
            self._attr_entity_registry_enabled_default = entity_registry_enabled_default
        self._attr_has_entity_name = True
        self._attr_name = hm_entity.name
        self._attr_unique_id = hm_entity.unique_id
        _LOGGER.debug("init: Setting up %s", hm_entity.entity_name_data.full_name)

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        return self._hm_entity.available

    @property
    def device_info(self) -> DeviceInfo | None:
        """Return device specific attributes."""
        info = self._hm_entity.device_information
        return DeviceInfo(
            identifiers={
                (
                    DOMAIN,
                    info.identifier,
                )
            },
            manufacturer=info.manufacturer,
            model=info.model,
            name=info.name,
            sw_version=info.version,
            suggested_area=info.room,
            # Link to the homematic control unit.
            via_device=cast(tuple[str, str], info.central),
        )

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return the state attributes of the generic entity."""
        attributes = self._hm_entity.attributes
        if (
            isinstance(self._hm_entity, GenericEntity) and self._hm_entity.is_readable
        ) or isinstance(self._hm_entity, CustomEntity):
            if self._hm_entity.is_valid:
                attributes[ATTR_VALUE_STATE] = (
                    HmEntityState.UNCERTAIN
                    if self._hm_entity.state_uncertain
                    else HmEntityState.VALID
                )
            else:
                attributes[ATTR_VALUE_STATE] = HmEntityState.NOT_VALID
        return attributes

    async def async_added_to_hass(self) -> None:
        """Register callbacks and load initial data."""
        if isinstance(self._hm_entity, CallbackEntity):
            self._hm_entity.register_update_callback(
                update_callback=self._async_device_changed
            )
            self._hm_entity.register_remove_callback(
                remove_callback=self._async_device_removed
            )
        self._cu.async_add_hm_entity(
            entity_id=self.entity_id, hm_entity=self._hm_entity
        )
        # Init value of entity.
        await self.async_update()
        if (
            isinstance(self._hm_entity, GenericEntity)
            and not self._hm_entity.is_valid
            and self._hm_entity.is_readable
        ) or (
            isinstance(self._hm_entity, CustomEntity) and not self._hm_entity.is_valid
        ):
            _LOGGER.info(
                "CCU did not provide initial value for %s. See README for more information",
                self._hm_entity.entity_name_data.full_name,
            )

    def _get_entity_registry_enabled_default(self) -> bool | None:
        """Return, if entity should be enabled based on usage attribute."""
        if self._hm_entity.usage in {
            HmEntityUsage.CE_SECONDARY,
            HmEntityUsage.CE_VISIBLE,
            HmEntityUsage.ENTITY_NO_CREATE,
        }:
            return False
        if self._hm_entity.usage in {HmEntityUsage.CE_PRIMARY}:
            return True
        return None

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

    async def async_update(self) -> None:
        """Update entities from MASTER paramset."""
        if isinstance(self._hm_entity, (GenericEntity, CustomEntity)):
            await self._hm_entity.load_entity_value()

    async def async_will_remove_from_hass(self) -> None:
        """Run when hmip device will be removed from hass."""
        self._cu.async_remove_hm_entity(self.entity_id)

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


class HaHomematicGenericRestoreEntity(
    HaHomematicGenericEntity[HmGenericEntity], RestoreEntity
):
    """Representation of the HomematicIP generic restore entity."""

    _restored_state: State | None = None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return the state attributes of the generic entity."""
        attributes = super().extra_state_attributes
        if self.is_restored:
            attributes[ATTR_VALUE_STATE] = HmEntityState.RESTORED
        return attributes

    @property
    def is_restored(self) -> bool:
        """Return if the state is restored."""
        return (
            not self._hm_entity.is_valid
            and self._restored_state is not None
            and self._restored_state.state is not None
        )

    async def async_added_to_hass(self) -> None:
        """Check, if state needs to be restored."""
        await super().async_added_to_hass()
        # if not self._hm_entity.is_valid:
        self._restored_state = await self.async_get_last_state()


class HaHomematicGenericSysvarEntity(Generic[HmGenericSysvarEntity], Entity):
    """Representation of the HomematicIP generic sysvar entity."""

    def __init__(
        self,
        control_unit: ControlUnit,
        hm_sysvar_entity: GenericSystemVariable,
    ) -> None:
        """Initialize the generic entity."""
        self._cu: ControlUnit = control_unit
        self._hm_sysvar_entity: GenericSystemVariable = hm_sysvar_entity
        self._attr_should_poll = self._hm_sysvar_entity.should_poll
        self._attr_has_entity_name = True
        self._attr_name = hm_sysvar_entity.name
        self._attr_unique_id = hm_sysvar_entity.unique_id
        self._attr_entity_registry_enabled_default = False
        _LOGGER.debug("init sysvar: Setting up %s", self.name)

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        return self._hm_sysvar_entity.available

    @property
    def device_info(self) -> DeviceInfo | None:
        """Return device specific attributes."""
        info = self._hm_sysvar_entity.device_information
        return DeviceInfo(
            identifiers={
                (
                    DOMAIN,
                    info.identifier,
                )
            },
            manufacturer=info.manufacturer,
            model=info.model,
            name=info.name,
            sw_version=info.version,
            suggested_area=info.room,
            # Link to the homematic control unit.
            via_device=cast(tuple[str, str], info.central),
        )

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return the state attributes of the generic entity."""
        return self._hm_sysvar_entity.attributes

    async def async_added_to_hass(self) -> None:
        """Register callbacks and load initial data."""
        if isinstance(self._hm_sysvar_entity, CallbackEntity):
            self._hm_sysvar_entity.register_update_callback(
                update_callback=self._async_sysvar_changed
            )
            self._hm_sysvar_entity.register_remove_callback(
                remove_callback=self._async_sysvar_removed
            )
        self._cu.async_add_hm_sysvar_entity(
            entity_id=self.entity_id, hm_sysvar_entity=self._hm_sysvar_entity
        )

    @callback
    def _async_sysvar_changed(self, *args: Any, **kwargs: Any) -> None:
        """Handle sysvar entity state changes."""
        # Don't update disabled entities
        if self.enabled:
            _LOGGER.debug("Sysvar changed event %s", self.name)
            self.async_write_ha_state()
        else:
            _LOGGER.debug(
                "Sysvar Changed Event for %s not fired. Sysvar entity is disabled",
                self.name,
            )

    async def async_will_remove_from_hass(self) -> None:
        """Run when hmip sysvar entity will be removed from hass."""
        self._cu.async_remove_hm_sysvar_entity(self.entity_id)

        # Remove callbacks.
        self._hm_sysvar_entity.unregister_update_callback(
            update_callback=self._async_sysvar_changed
        )
        self._hm_sysvar_entity.unregister_remove_callback(
            remove_callback=self._async_sysvar_removed
        )

    @callback
    def _async_sysvar_removed(self, *args: Any, **kwargs: Any) -> None:
        """Handle hm sysvar entity removal."""
        self.hass.async_create_task(self.async_remove(force_remove=True))

        if not self.registry_entry:
            return

        if entity_id := self.registry_entry.entity_id:
            entity_registry = er.async_get(self.hass)
            if entity_id in entity_registry.entities:
                entity_registry.async_remove(entity_id)
