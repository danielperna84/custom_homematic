"""Generic entity for the HomematicIP Cloud component."""
from __future__ import annotations

import logging
from typing import Any, Generic, cast

from hahomematic.const import HmCallSource
from hahomematic.platforms.custom.entity import CustomEntity
from hahomematic.platforms.entity import CallbackEntity
from hahomematic.platforms.generic.entity import GenericEntity, WrapperEntity
from hahomematic.platforms.hub.entity import GenericHubEntity, GenericSystemVariable

from homeassistant.core import State, callback
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.helpers.entity import DeviceInfo, Entity
from homeassistant.helpers.restore_state import RestoreEntity

from .const import (
    ATTR_ADDRESS,
    ATTR_ENTITY_TYPE,
    ATTR_FUNCTION,
    ATTR_INTERFACE_ID,
    ATTR_MODEL,
    ATTR_NAME,
    ATTR_PARAMETER,
    ATTR_VALUE_STATE,
    DOMAIN,
    IDENTIFIER_SEPARATOR,
    MANUFACTURER_EQ3,
    HmEntityState,
    HmEntityType,
)
from .control_unit import ControlUnit
from .entity_helpers import get_entity_description
from .helpers import HmGenericEntity, HmGenericSysvarEntity

_LOGGER = logging.getLogger(__name__)


class HaHomematicGenericEntity(Generic[HmGenericEntity], Entity):
    """Representation of the HomematicIP generic entity."""

    _attr_has_entity_name = True
    _attr_should_poll = False

    def __init__(
        self,
        control_unit: ControlUnit,
        hm_entity: HmGenericEntity,
    ) -> None:
        """Initialize the generic entity."""
        self._cu: ControlUnit = control_unit
        self._hm_entity: HmGenericEntity = hm_entity
        self._attr_unique_id = f"{DOMAIN}_{hm_entity.unique_identifier}"
        if entity_description := get_entity_description(hm_entity=hm_entity):
            self.entity_description = entity_description
            if (
                entity_description.name is None
                and entity_description.translation_key is None
            ):
                self._attr_name = hm_entity.name
            if entity_description.entity_registry_enabled_default:
                self._attr_entity_registry_enabled_default = hm_entity.enabled_default
        else:
            self._attr_name = hm_entity.name
            self._attr_entity_registry_enabled_default = hm_entity.enabled_default

        _LOGGER.debug("init: Setting up %s", hm_entity.full_name)
        if (
            isinstance(self._hm_entity, GenericEntity | WrapperEntity)
            and hasattr(self, "entity_description")
            and hasattr(self.entity_description, "native_unit_of_measurement")
            and self.entity_description.native_unit_of_measurement
            != self._hm_entity.unit
        ):
            _LOGGER.info(
                "Different unit for entity: %s: entity_description: %s vs device: %s",
                self._hm_entity.full_name,
                self.entity_description.native_unit_of_measurement,
                self._hm_entity.unit,
            )

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
            manufacturer=get_manufacturer(device_type=hm_device.device_type),
            model=hm_device.device_type,
            name=hm_device.name,
            sw_version=hm_device.firmware,
            suggested_area=hm_device.room,
            # Link to the homematic control unit.
            via_device=cast(tuple[str, str], hm_device.central.name),
        )

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return the state attributes of the generic entity."""
        attributes: dict[str, Any] = {
            ATTR_INTERFACE_ID: self._hm_entity.device.interface_id,
            ATTR_ADDRESS: self._hm_entity.channel_address,
            ATTR_MODEL: self._hm_entity.device.device_type,
        }
        if isinstance(self._hm_entity, GenericEntity | WrapperEntity):
            attributes[ATTR_ENTITY_TYPE] = HmEntityType.GENERIC.value
            attributes[ATTR_PARAMETER] = self._hm_entity.parameter
            attributes[ATTR_FUNCTION] = self._hm_entity.function

        if isinstance(self._hm_entity, CustomEntity):
            attributes[ATTR_ENTITY_TYPE] = HmEntityType.CUSTOM.value

        if (
            isinstance(self._hm_entity, GenericEntity | WrapperEntity)
            and self._hm_entity.is_readable
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

    @property
    def name(self) -> str | None:
        """Return the name of the entity."""
        if isinstance(self._hm_entity, GenericEntity | WrapperEntity):
            return self._hm_entity.name.replace(
                self._hm_entity.parameter.replace("_", " ").title(), super().name
            )
        return super().name

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
        if isinstance(self._hm_entity, GenericEntity | CustomEntity | WrapperEntity):
            await self._hm_entity.load_entity_value(call_source=HmCallSource.HA_INIT)
        if (
            isinstance(self._hm_entity, GenericEntity)
            and not self._hm_entity.is_valid
            and self._hm_entity.is_readable
        ) or (
            isinstance(self._hm_entity, CustomEntity) and not self._hm_entity.is_valid
        ):
            _LOGGER.debug(
                "CCU did not provide initial value for %s. "
                "See README for more information",
                self._hm_entity.full_name,
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

    async def async_update(self) -> None:
        """Update entities from MASTER paramset."""
        if isinstance(self._hm_entity, GenericEntity | CustomEntity):
            await self._hm_entity.load_entity_value(
                call_source=HmCallSource.MANUAL_OR_SCHEDULED
            )

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


class HaHomematicGenericHubEntity(Entity):
    """Representation of the HomematicIP generic hub entity."""

    _attr_has_entity_name = True
    _attr_entity_registry_enabled_default = False
    _attr_should_poll = False

    def __init__(
        self,
        control_unit: ControlUnit,
        hm_hub_entity: GenericHubEntity,
    ) -> None:
        """Initialize the generic entity."""
        self._cu: ControlUnit = control_unit
        self._hm_hub_entity = hm_hub_entity
        self._attr_unique_id = f"{DOMAIN}_{hm_hub_entity.unique_identifier}"
        if entity_description := get_entity_description(hm_entity=hm_hub_entity):
            self.entity_description = entity_description
        self._attr_name = hm_hub_entity.name
        _LOGGER.debug("init sysvar: Setting up %s", self.name)

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        return self._hm_hub_entity.available

    @property
    def device_info(self) -> DeviceInfo | None:
        """Return device specific attributes."""
        return self._cu.device_info

    async def async_added_to_hass(self) -> None:
        """Register callbacks and load initial data."""
        if isinstance(self._hm_hub_entity, CallbackEntity):
            self._hm_hub_entity.register_update_callback(
                update_callback=self._async_hub_entity_changed
            )
            self._hm_hub_entity.register_remove_callback(
                remove_callback=self._async_hub_entity_removed
            )
        self._cu.async_add_hm_hub_entity(
            entity_id=self.entity_id, hm_hub_entity=self._hm_hub_entity
        )

    async def async_will_remove_from_hass(self) -> None:
        """Run when hmip sysvar entity will be removed from hass."""
        self._cu.async_remove_hm_hub_entity(self.entity_id)

        # Remove callbacks.
        self._hm_hub_entity.unregister_update_callback(
            update_callback=self._async_hub_entity_changed
        )
        self._hm_hub_entity.unregister_remove_callback(
            remove_callback=self._async_hub_entity_removed
        )

    @callback
    def _async_hub_entity_changed(self, *args: Any, **kwargs: Any) -> None:
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

    @callback
    def _async_hub_entity_removed(self, *args: Any, **kwargs: Any) -> None:
        """Handle hm sysvar entity removal."""
        self.hass.async_create_task(self.async_remove(force_remove=True))

        if not self.registry_entry:
            return

        if entity_id := self.registry_entry.entity_id:
            entity_registry = er.async_get(self.hass)
            if entity_id in entity_registry.entities:
                entity_registry.async_remove(entity_id)


class HaHomematicGenericSysvarEntity(
    Generic[HmGenericSysvarEntity], HaHomematicGenericHubEntity
):
    """Representation of the HomematicIP generic sysvar entity."""

    def __init__(
        self,
        control_unit: ControlUnit,
        hm_sysvar_entity: GenericSystemVariable,
    ) -> None:
        """Initialize the generic entity."""
        super().__init__(
            control_unit=control_unit,
            hm_hub_entity=hm_sysvar_entity,
        )
        self._hm_hub_entity: GenericSystemVariable = hm_sysvar_entity

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return the state attributes of the generic entity."""
        return {ATTR_NAME: self._hm_hub_entity.ccu_var_name}


def get_manufacturer(device_type: str) -> str | None:
    """Return the manufacturer of a device."""
    if device_type.lower().startswith("hb"):
        return "Homebrew"
    if device_type.lower().startswith("alpha"):
        return "Möhlenhoff"
    return MANUFACTURER_EQ3
