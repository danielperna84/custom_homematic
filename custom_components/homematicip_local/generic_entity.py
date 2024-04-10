"""Generic entity for the HomematicIP Cloud component."""

from __future__ import annotations

from collections.abc import Mapping
import logging
from typing import Any, Final, Generic

from hahomematic.const import CallSource
from hahomematic.platforms.custom.entity import CustomEntity
from hahomematic.platforms.entity import CallbackEntity
from hahomematic.platforms.generic.entity import GenericEntity
from hahomematic.platforms.hub.entity import GenericHubEntity, GenericSystemVariable

from homeassistant.core import State, callback
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.restore_state import RestoreEntity
from homeassistant.helpers.typing import UndefinedType

from .const import DOMAIN, HmEntityState, HmEntityType
from .control_unit import ControlUnit
from .entity_helpers import get_entity_description
from .support import HmGenericEntity, HmGenericSysvarEntity, get_hm_entity

_LOGGER = logging.getLogger(__name__)
ATTR_ADDRESS: Final = "address"
ATTR_ENTITY_TYPE: Final = "entity_type"
ATTR_FUNCTION: Final = "function"
ATTR_INTERFACE_ID: Final = "interface_id"
ATTR_MODEL: Final = "model"
ATTR_NAME: Final = "name"
ATTR_PARAMETER: Final = "parameter"
ATTR_VALUE_STATE: Final = "value_state"


class HaHomematicGenericEntity(Generic[HmGenericEntity], Entity):
    """Representation of the HomematicIP generic entity."""

    _attr_has_entity_name = True
    _attr_should_poll = False

    _unrecorded_attributes = frozenset(
        {
            ATTR_ADDRESS,
            ATTR_ENTITY_TYPE,
            ATTR_FUNCTION,
            ATTR_INTERFACE_ID,
            ATTR_MODEL,
            ATTR_PARAMETER,
            ATTR_VALUE_STATE,
        }
    )

    def __init__(
        self,
        control_unit: ControlUnit,
        hm_entity: HmGenericEntity,
    ) -> None:
        """Initialize the generic entity."""
        self._cu: ControlUnit = control_unit
        self._hm_entity: HmGenericEntity = get_hm_entity(hm_entity=hm_entity)
        self._attr_unique_id = f"{DOMAIN}_{hm_entity.unique_id}"

        if entity_description := get_entity_description(hm_entity=hm_entity):
            self.entity_description = entity_description
        else:
            self._attr_entity_registry_enabled_default = hm_entity.enabled_default
            if isinstance(hm_entity, GenericEntity):
                self._attr_translation_key = hm_entity.parameter.lower()

        hm_device = hm_entity.device
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, hm_device.identifier)},
            manufacturer=hm_device.manufacturer,
            model=hm_device.device_type,
            name=hm_device.name,
            serial_number=hm_device.device_address,
            sw_version=hm_device.firmware,
            suggested_area=hm_device.room,
            # Link to the homematic control unit.
            via_device=(DOMAIN, hm_device.central.name),
        )

        self._static_state_attributes = self._get_static_state_attributes()

        _LOGGER.debug("init: Setting up %s", hm_entity.full_name)
        if (
            isinstance(hm_entity, GenericEntity)
            and hasattr(self, "entity_description")
            and hasattr(self.entity_description, "native_unit_of_measurement")
            and self.entity_description.native_unit_of_measurement != hm_entity.unit
        ):
            _LOGGER.debug(
                "Different unit for entity: %s: entity_description: %s vs device: %s",
                hm_entity.full_name,
                self.entity_description.native_unit_of_measurement,
                hm_entity.unit,
            )

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        return self._hm_entity.available

    def _get_static_state_attributes(self) -> Mapping[str, Any]:
        """Return the static attributes of the generic entity."""
        attributes: dict[str, Any] = {
            ATTR_INTERFACE_ID: self._hm_entity.device.interface_id,
            ATTR_ADDRESS: self._hm_entity.channel_address,
            ATTR_MODEL: self._hm_entity.device.device_type,
        }
        if isinstance(self._hm_entity, GenericEntity):
            attributes[ATTR_ENTITY_TYPE] = HmEntityType.GENERIC.value
            attributes[ATTR_PARAMETER] = self._hm_entity.parameter
            attributes[ATTR_FUNCTION] = self._hm_entity.function

        if isinstance(self._hm_entity, CustomEntity):
            attributes[ATTR_ENTITY_TYPE] = HmEntityType.CUSTOM.value
        return attributes

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return the state attributes of the generic entity."""
        attributes: dict[str, Any] = {}
        attributes.update(self._static_state_attributes)

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

    @property
    def name(self) -> str | UndefinedType | None:
        """Return the name of the entity.

        Override by CC.
        A hm entity can consist of two parts. The first part is already defined by the user,
        and the second part is the english named parameter that must be translated.
        This translated parameter will be used in the combined name.
        """
        entity_name = self._hm_entity.name

        if isinstance(self._hm_entity, GenericEntity) and entity_name:
            translated_name = super().name
            if self._do_remove_name():
                translated_name = ""
            if isinstance(translated_name, str):
                entity_name = entity_name.replace(
                    self._hm_entity.parameter.replace("_", " ").title(), translated_name
                )
        if entity_name == "":
            return None
        return entity_name

    def _do_remove_name(self) -> bool:
        """Check if entity name part should be removed.

        Here we use the HA translation support to identify if the translated name is ''
        This is guarded against failure due to future HA api changes.
        """
        try:
            if (
                self._name_translation_key
                and hasattr(self, "platform")
                and hasattr(self.platform, "platform_translations")
                and (name := self.platform.platform_translations.get(self._name_translation_key))
                is not None
            ):
                return bool(name == "")
        except Exception:  # pylint: disable=broad-exception-caught
            return False
        return False

    @property
    def use_device_name(self) -> bool:
        """Return if this entity does not have its own name.

        Override by CC.
        """
        return not self.name

    async def async_added_to_hass(self) -> None:
        """Register callbacks and load initial data."""
        if isinstance(self._hm_entity, CallbackEntity):
            self._hm_entity.register_entity_updated_callback(
                entity_updated_callback=self._async_entity_updated, custom_id=self.entity_id
            )
            self._hm_entity.register_device_removed_callback(
                device_removed_callback=self._async_device_removed
            )
        # Init value of entity.
        if isinstance(self._hm_entity, GenericEntity | CustomEntity):
            await self._hm_entity.load_entity_value(call_source=CallSource.HA_INIT)
        if (
            isinstance(self._hm_entity, GenericEntity)
            and not self._hm_entity.is_valid
            and self._hm_entity.is_readable
        ) or (isinstance(self._hm_entity, CustomEntity) and not self._hm_entity.is_valid):
            _LOGGER.debug(
                "CCU did not provide initial value for %s. See README for more information",
                self._hm_entity.full_name,
            )

    @callback
    def _async_entity_updated(self, *args: Any, **kwargs: Any) -> None:
        """Handle device state changes."""
        # Don't update disabled entities
        update_type = (
            "updated"
            if self._hm_entity.last_refreshed == self._hm_entity.last_updated
            else "refreshed"
        )
        if self.enabled:
            _LOGGER.debug("Device %s event fired for %s", update_type, self._hm_entity.full_name)
            self.async_schedule_update_ha_state()
        else:
            _LOGGER.debug(
                "Device %s event for %s not fired. Entity is disabled",
                update_type,
                self._hm_entity.full_name,
            )

    async def async_update(self) -> None:
        """Update entities from MASTER paramset."""
        if isinstance(self._hm_entity, GenericEntity | CustomEntity):
            await self._hm_entity.load_entity_value(call_source=CallSource.MANUAL_OR_SCHEDULED)

    async def async_will_remove_from_hass(self) -> None:
        """Run when hmip device will be removed from hass."""
        # Remove callback from device.
        self._hm_entity.unregister_entity_updated_callback(
            entity_updated_callback=self._async_entity_updated, custom_id=self.entity_id
        )
        self._hm_entity.unregister_device_removed_callback(
            device_removed_callback=self._async_device_removed
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


class HaHomematicGenericRestoreEntity(HaHomematicGenericEntity[HmGenericEntity], RestoreEntity):
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
    _attr_should_poll = False
    _attr_entity_registry_enabled_default = False

    _unrecorded_attributes = frozenset({ATTR_NAME})

    def __init__(
        self,
        control_unit: ControlUnit,
        hm_hub_entity: GenericHubEntity,
    ) -> None:
        """Initialize the generic entity."""
        self._cu: ControlUnit = control_unit
        self._hm_hub_entity = get_hm_entity(hm_hub_entity)
        self._attr_unique_id = f"{DOMAIN}_{hm_hub_entity.unique_id}"
        if entity_description := get_entity_description(hm_entity=hm_hub_entity):
            self.entity_description = entity_description
        self._attr_name = hm_hub_entity.name
        self._attr_device_info = control_unit.device_info
        _LOGGER.debug("init sysvar: Setting up %s", self.name)

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        return self._hm_hub_entity.available

    async def async_added_to_hass(self) -> None:
        """Register callbacks and load initial data."""
        if isinstance(self._hm_hub_entity, CallbackEntity):
            self._hm_hub_entity.register_entity_updated_callback(
                entity_updated_callback=self._async_hub_entity_updated, custom_id=self.entity_id
            )
            self._hm_hub_entity.register_device_removed_callback(
                device_removed_callback=self._async_hub_device_removed
            )

    async def async_will_remove_from_hass(self) -> None:
        """Run when hmip sysvar entity will be removed from hass."""
        # Remove callbacks.
        self._hm_hub_entity.unregister_entity_updated_callback(
            entity_updated_callback=self._async_hub_entity_updated, custom_id=self.entity_id
        )
        self._hm_hub_entity.unregister_device_removed_callback(
            device_removed_callback=self._async_hub_device_removed
        )

    @callback
    def _async_hub_entity_updated(self, *args: Any, **kwargs: Any) -> None:
        """Handle sysvar entity state changes."""
        # Don't update disabled entities
        if self.enabled:
            _LOGGER.debug("Sysvar changed event fired for %s", self.name)
            self.async_schedule_update_ha_state()
        else:
            _LOGGER.debug(
                "Sysvar changed event for %s not fired. Sysvar entity is disabled",
                self.name,
            )

    @callback
    def _async_hub_device_removed(self, *args: Any, **kwargs: Any) -> None:
        """Handle hm sysvar entity removal."""
        self.hass.async_create_task(self.async_remove(force_remove=True))

        if not self.registry_entry:
            return

        if entity_id := self.registry_entry.entity_id:
            entity_registry = er.async_get(self.hass)
            if entity_id in entity_registry.entities:
                entity_registry.async_remove(entity_id)


class HaHomematicGenericSysvarEntity(Generic[HmGenericSysvarEntity], HaHomematicGenericHubEntity):
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
        self._attr_extra_state_attributes = {ATTR_NAME: self._hm_hub_entity.ccu_var_name}
