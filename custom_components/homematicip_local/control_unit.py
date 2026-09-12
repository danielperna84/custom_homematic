"""Homematic(IP) Local for OpenCCU is a Python 3 module for Home Assistant and Homematic(IP) devices."""

from __future__ import annotations

from collections.abc import Awaitable, Callable, Mapping
from copy import deepcopy
from datetime import datetime
from functools import partial
import logging
import time
from typing import TYPE_CHECKING, Any, Final, Self, TypeVar, cast

from slugify import slugify

from aiohomematic import __version__ as AIOHM_VERSION
from aiohomematic.central import CentralConfig, CentralUnit, check_config
from aiohomematic.central.events import (
    CentralStateChangedEvent,
    DataPointsCreatedEvent,
    DeviceLifecycleEvent,
    DeviceLifecycleEventType,
    DeviceTriggerEvent,
    OptimisticRollbackEvent,
    SubscriptionGroup,
    SystemStatusChangedEvent,
)
from aiohomematic.client import InterfaceConfig
from aiohomematic.const import (
    CONF_PASSWORD,
    CONF_USERNAME,
    DEFAULT_ENABLE_PROGRAM_SCAN,
    DEFAULT_ENABLE_SYSVAR_SCAN,
    DEFAULT_INTERFACES_REQUIRING_PERIODIC_REFRESH,
    DEFAULT_OPTIONAL_SETTINGS,
    DEFAULT_PROGRAM_MARKERS,
    DEFAULT_SYSVAR_MARKERS,
    DEFAULT_UN_IGNORES,
    DEFAULT_USE_GROUP_CHANNEL_FOR_COVER_STATE,
    IDENTIFIER_SEPARATOR,
    IP_ANY_V4,
    PORT_ANY,
    CentralState,
    ClientState,
    DataPointCategory,
    DataPointType,
    DescriptionMarker,
    DeviceTriggerEventType,
    FailureReason,
    IntegrationIssueSeverity,
    IntegrationIssueType,
    Interface,
    Manufacturer,
    OptionalSettings,
    ScheduleTimerConfig,
    SystemInformation,
    TimeoutConfig,
    get_interface_default_port,
)
from aiohomematic.exceptions import AuthFailure, BaseHomematicException
from aiohomematic.interfaces import DeviceProtocol
from aiohomematic.model.data_point import CallbackDataPoint
from aiohomematic.support.address import get_device_address
from homeassistant.const import CONF_HOST, CONF_PATH, CONF_PORT
from homeassistant.core import CALLBACK_TYPE, HomeAssistant, callback

# --- Repairs/fix flow support ---
from homeassistant.helpers import aiohttp_client, device_registry as dr, entity_registry as er, issue_registry as ir
from homeassistant.helpers.device_registry import DeviceEntry, DeviceEntryType, DeviceInfo
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.event import async_call_later
from homeassistant.helpers.issue_registry import async_delete_issue

from .const import (
    BACKEND_LOOM,
    CONF_ADVANCED_CONFIG,
    CONF_BACKEND,
    CONF_BACKUP_PATH,
    CONF_CALLBACK_HOST,
    CONF_CALLBACK_PORT_XML_RPC,
    CONF_COMMAND_RETRY_MAX_ATTEMPTS,
    CONF_COMMAND_THROTTLE_INTERVAL,
    CONF_DISABLE_CONFIG_PANEL,
    CONF_ENABLE_LIGHT_LAST_BRIGHTNESS,
    CONF_ENABLE_MQTT,
    CONF_ENABLE_PROGRAM_SCAN,
    CONF_ENABLE_SUB_DEVICES,
    CONF_ENABLE_SYSTEM_NOTIFICATIONS,
    CONF_ENABLE_SYSVAR_SCAN,
    CONF_INSTANCE_NAME,
    CONF_INTERFACE,
    CONF_JSON_PORT,
    CONF_LISTEN_ON_ALL_IP,
    CONF_LOOM_PORT,
    CONF_LOOM_TOKEN,
    CONF_MQTT_PREFIX,
    CONF_OPTIONAL_SETTINGS,
    CONF_PROGRAM_MARKERS,
    CONF_SYS_SCAN_INTERVAL,
    CONF_SYSVAR_MARKERS,
    CONF_TLS,
    CONF_UN_IGNORES,
    CONF_USE_GROUP_CHANNEL_FOR_COVER_STATE,
    CONF_VERIFY_TLS,
    DEFAULT_BACKEND,
    DEFAULT_BACKUP_PATH,
    DEFAULT_COMMAND_RETRY_MAX_ATTEMPTS,
    DEFAULT_COMMAND_THROTTLE_INTERVAL,
    DEFAULT_DISABLE_CONFIG_PANEL,
    DEFAULT_ENABLE_DEVICE_FIRMWARE_CHECK,
    DEFAULT_ENABLE_LIGHT_LAST_BRIGHTNESS,
    DEFAULT_ENABLE_MQTT,
    DEFAULT_ENABLE_SUB_DEVICES,
    DEFAULT_ENABLE_SYSTEM_NOTIFICATIONS,
    DEFAULT_LISTEN_ON_ALL_IP,
    DEFAULT_MQTT_PREFIX,
    DEFAULT_SYS_SCAN_INTERVAL,
    DOMAIN,
    EVENT_ADDRESS,
    EVENT_AGE_SECONDS,
    EVENT_CHANNEL_NO,
    EVENT_DEVICE_ID,
    EVENT_ERROR,
    EVENT_ERROR_VALUE,
    EVENT_IDENTIFIER,
    EVENT_INTERFACE_ID,
    EVENT_MESSAGE,
    EVENT_MODEL,
    EVENT_NAME,
    EVENT_PARAMETER,
    EVENT_REASON,
    EVENT_RESTORED_VALUE,
    EVENT_ROLLED_BACK_VALUE,
    EVENT_TITLE,
    EVENT_UNAVAILABLE,
    EVENT_VALUE,
    FILTER_ERROR_EVENT_PARAMETERS,
    ISSUE_TYPE_CALLBACK,
    ISSUE_TYPE_CLIENT,
    ISSUE_TYPE_CONNECTION,
)
from .mqtt import MQTTConsumer
from .repairs import REPAIR_CALLBACKS
from .support import (
    CLICK_EVENT_SCHEMA,
    DEVICE_AVAILABILITY_EVENT_SCHEMA,
    DEVICE_ERROR_EVENT_SCHEMA,
    InvalidConfig,
    cleanup_click_event_data,
    cleanup_instance_name,
    get_device_identifier,
    get_issue_id,
    is_valid_event,
    realign_hub_unique_id,
)

if TYPE_CHECKING:
    from openccu_loom_client.compat.aiohomematic.central import CentralConfig as LoomCentralConfig

_LOGGER = logging.getLogger(__name__)

# The routing-key slot that carries the renameable identity. Both backends
# build hub keys as ``<central-id>_<address>_<slot>`` with the address being
# ``sysvar`` / ``program``, and a slug never contains an underscore, so the
# marker locates the slot without parsing the rest of the key.
_SYSVAR_KEY_MARKER: Final = "_sysvar_"
_PROGRAM_KEY_MARKER: Final = "_program_"


def hub_key_from_name_slug(unique_id: str, *, legacy_name: str) -> str | None:
    """Return the pre-id key for a sysvar / program unique_id, or None.

    Both backends used to key these two families on ``slugify(legacy_name)``
    and now key them on the id the CCU carries. This rebuilds the old key by
    swapping the identity slot back — everything after the ``_sysvar_`` /
    ``_program_`` marker, which a slug can never contain because slugify emits
    dashes.

    Returns None when the key belongs to neither family, when the name yields
    no slug, or when the slot is already the slug — the last of which is both
    the idempotency guard and the correct answer while an id is unresolved and
    the producer still falls back to the name.
    """
    for marker in (_SYSVAR_KEY_MARKER, _PROGRAM_KEY_MARKER):
        head, found, current_slot = unique_id.rpartition(marker)
        if not found:
            continue
        if not (old_slot := slugify(legacy_name)) or old_slot == current_slot:
            return None
        return f"{head}{marker}{old_slot}"
    return None


# Delay before pruning orphaned entity registry entries. Most hub data points
# (inbox, service/alarm messages, install_mode, metrics, connectivity, programs,
# sysvars) are populated by init_hub() during start_clients(). Only system_update
# is fetched lazily by the scheduler after the central reaches RUNNING — 60s
# comfortably covers the first scheduler iteration of fetch_system_update_data.
ORPHAN_CLEANUP_DELAY: Final = 60

# Config entries whose hub key migration has already asked for its one reload,
# kept in hass.data so it survives that reload. The pass is idempotent, so a
# second run finds nothing to migrate and asks for nothing — but that is an
# argument about the pass, and an automatic reload loop is a bad enough failure
# to close by construction instead.
HUB_KEY_RELOAD_SCHEDULED: Final = f"{DOMAIN}_hub_key_reload_scheduled"

# Safety threshold for the orphan entity registry cleanup. The central reports
# RUNNING as soon as all clients are connected, which does not guarantee that the
# device descriptions were actually loaded (e.g. a transient auth error during a
# CCU restore leaves the device cache empty/partial — see aiohomematic#3215). In
# that situation almost every registry entry looks orphaned. Since deleting entries
# is permanent and breaks dashboards/automations, the sweep refuses to run when it
# would remove more than this fraction of the integration's registry entries.
ORPHAN_CLEANUP_MAX_DELETE_RATIO: Final = 0.5

# Event type for device availability (not in DeviceTriggerEventType as it comes from DeviceLifecycleEvent)
EVENT_TYPE_DEVICE_AVAILABILITY: Final = "homematic.device_availability"
# Event type for optimistic rollback (from OptimisticRollbackEvent)
EVENT_TYPE_OPTIMISTIC_ROLLBACK: Final = f"{DOMAIN}.optimistic_rollback"

_DATA_POINT_T = TypeVar("_DATA_POINT_T", bound=CallbackDataPoint)


class BaseControlUnit:
    """Base central point to control a central unit."""

    def __init__(self, *, control_config: ControlConfig, central: CentralUnit) -> None:
        """Init the control unit."""
        self._config: Final = control_config
        self._hass: Final = control_config.hass
        self._entry_id: Final = control_config.entry_id
        self._instance_name: Final = control_config.instance_name
        self._backup_directory: Final = control_config.backup_directory
        self._disable_config_panel: Final = control_config.disable_config_panel
        self._enable_light_last_brightness: Final = control_config.enable_light_last_brightness
        self._enable_mqtt: Final = control_config.enable_mqtt
        self._enable_sub_devices: Final = control_config.enable_sub_devices
        self._mqtt_prefix: Final = control_config.mqtt_prefix
        self._enable_system_notifications: Final = control_config.enable_system_notifications
        self._central: Final = central
        self._attr_device_info: Final = DeviceInfo(
            identifiers={
                (
                    DOMAIN,
                    self._central.name,
                )
            },
            manufacturer=Manufacturer.EQ3,
            model=self._central.model,
            name=self._central.name,
            serial_number=self._central.system_information.serial,
            sw_version=self._central.version,
        )

    @classmethod
    async def async_create(cls, *, control_config: ControlConfig) -> Self:
        """Create a new control unit instance asynchronously."""
        central = await control_config.create_central()
        return cls(control_config=control_config, central=central)

    @property
    def backup_directory(self) -> str:
        """Return the backup directory path."""
        return self._backup_directory

    @property
    def central(self) -> CentralUnit:
        """Return the Homematic(IP) Local for OpenCCU central unit instance."""
        return self._central

    @property
    def config(self) -> ControlConfig:
        """Return the control unit configuration."""
        return self._config

    @property
    def device_info(self) -> DeviceInfo | None:
        """Return device specific attributes."""
        return self._attr_device_info

    @property
    def disable_config_panel(self) -> bool:
        """Return if the configuration panel is disabled."""
        return self._disable_config_panel

    @property
    def enable_light_last_brightness(self) -> bool:
        """Return if last brightness for lights is enabled."""
        return self._enable_light_last_brightness

    @property
    def enable_sub_devices(self) -> bool:
        """Return if sub devices are enabled."""
        return self._enable_sub_devices

    @property
    def entry_id(self) -> str:
        """Return the Homematic(IP) Local config entry id."""
        return self._entry_id

    def device_configuration_url(self, *, address: str, interface_id: str) -> str | None:
        """
        Return the "Configure" target for a device page, or ``None``.

        The two backends answer differently because they own different
        editors. On the direct-CCU backend that is this integration's own
        config panel. On openccu-loom the panel is not registered at all —
        the daemon's Config UI covers the same ground for every CCU it
        serves — so the link points there instead.

        The loom address is the daemon's own answer (``config_ui_url``,
        from the operator's ``north.rest.public_url``) before it is a
        guess: the address this integration uses to reach the daemon may
        be a container or proxy-internal one that a browser cannot follow.
        Guessing from it is the fallback, not the first choice, and
        returning ``None`` is better than a link into nothing.
        """
        if self._config.backend == BACKEND_LOOM:
            if base := _loom_config_ui_base(central=self._central):
                return f"{base}#/devices/{address}"
            return None
        if self._disable_config_panel:
            return None
        return (
            f"homeassistant://homematic-config#view=device-detail"
            f"&entry={self._entry_id}"
            f"&device={address}"
            f"&interface={interface_id}"
        )

    def device_identifier(self, *, device: DeviceProtocol) -> str:
        """
        Return the device registry identifier of a Homematic device.

        Built from the HA instance name and the interface type rather than
        from the backend's own interface id, so the same device keys
        identically on both backends and a backend switch keeps its
        ``device_id`` — see :func:`get_device_identifier`.

        Falls back to the backend's own identifier when the interface is not
        one aiohomematic knows. That happens for a device the loom store
        seeded from a ``device.created`` push and has not completed yet; the
        migration in ``async_setup_entry`` moves such an entry onto the
        neutral key on the next start-up.
        """
        if (
            identifier := get_device_identifier(
                instance_name=self._central.name, address=device.address, interface=str(device.interface)
            )
        ) is not None:
            return identifier
        _LOGGER.warning(
            "DEVICE_IDENTIFIER: Unknown interface %s for device %s; keying it on the backend identifier for now",
            device.interface,
            device.address,
        )
        return device.identifier

    async def start_central(self) -> None:
        """Start the central unit."""
        _LOGGER.debug(
            "Starting central unit %s",
            self._instance_name,
        )
        try:
            await self._central.start()
            _LOGGER.info("Started central unit for %s (%s)", self._instance_name, AIOHM_VERSION)
        except AuthFailure:
            # Don't catch - let it propagate to trigger reauth
            raise
        except BaseHomematicException as ex:
            _LOGGER.warning(
                "START_CENTRAL: Failed to start central unit for %s: %s",
                self._instance_name,
                ex,
                exc_info=True,
            )

    async def stop_central(self, *args: Any) -> None:
        """Stop the control unit."""
        _LOGGER.debug(
            "Stopping central unit %s",
            self._instance_name,
        )
        if self._central.state != CentralState.STOPPED:
            await self._central.stop()
            _LOGGER.info("Stopped central unit for %s", self._instance_name)


class ControlUnit(BaseControlUnit):
    """Unit to control a central unit."""

    def __init__(self, *, control_config: ControlConfig, central: CentralUnit) -> None:
        """Init the control unit."""
        super().__init__(control_config=control_config, central=central)
        self._mqtt_consumer: MQTTConsumer | None = None
        self._auto_confirm_until: Final = control_config.auto_confirm_until
        self._subscription_group: Final[SubscriptionGroup] = self._central.event_bus.create_subscription_group(
            name="homematicip_local"
        )
        self._orphan_cleanup_unsub: CALLBACK_TYPE | None = None

    def ensure_via_device_exists(
        self,
        *,
        identifier: str,
        suggested_area: str | None,
        via_device: str,
        via_suggested_area: str | None = None,
    ) -> str:
        """
        Create the via device of a device and return its device registry id.

        A device info links its via device by registry id, and HA rejects the
        whole device info when that id is not a registered device — so the via
        device (and, one rung further up, the central it hangs off) has to
        exist before the entity carrying the link is added.
        """
        device_registry = dr.async_get(self._hass)

        if (via_entry := device_registry.async_get_device_by_identifier((DOMAIN, via_device), self._entry_id)) is None:
            central_entry = self._async_add_central_to_device_registry()
            if via_device == self.central.name:
                via_entry = central_entry
            else:
                # The parent carries its own room: HA applies suggested_area
                # only at creation, so seeding the parent with a sub-device's
                # area (e.g. a channel-group room) would pin the wrong area.
                via_entry = device_registry.async_get_or_create(
                    config_entry_id=self._entry_id,
                    identifiers={
                        (
                            DOMAIN,
                            via_device,
                        )
                    },
                    suggested_area=via_suggested_area,
                    via_device_id=central_entry.id,
                )

            device_registry.async_get_or_create(
                config_entry_id=self._entry_id,
                identifiers={
                    (
                        DOMAIN,
                        identifier,
                    )
                },
                suggested_area=suggested_area,
                via_device_id=via_entry.id,
            )

        return via_entry.id

    def get_new_data_points(
        self,
        *,
        data_point_type: DataPointType,
        category: DataPointCategory | None = None,
    ) -> tuple[Any, ...]:
        """Return all new data points by type, optionally filtered by category."""
        return self.central.query_facade.get_data_points(
            data_point_type=data_point_type,
            category=category,
            exclude_no_create=True,
            registered=False,
        )

    def get_new_hub_data_points(
        self,
        *,
        data_point_type: type[_DATA_POINT_T],
    ) -> tuple[_DATA_POINT_T, ...]:
        """Return all data points by type."""
        return cast(
            tuple[_DATA_POINT_T, ...],
            self.central.hub_coordinator.get_hub_data_points(
                category=data_point_type.default_category(),
                registered=False,
            ),
        )

    async def start_central(self) -> None:
        """Start the central unit."""
        # Subscribe to integration events
        _LOGGER.debug("Subscribing to integration events")

        # Central state transition handler
        self._subscription_group.subscribe(
            event_type=CentralStateChangedEvent,
            event_key=self._central.name,
            handler=self._on_central_state_changed,
        )

        # SystemStatusChangedEvent for detail-dependent logic (DEGRADED/FAILED + infra)
        self._subscription_group.subscribe(
            event_type=SystemStatusChangedEvent,
            event_key=None,
            handler=self._on_system_status,
        )
        self._subscription_group.subscribe(
            event_type=DeviceLifecycleEvent,
            event_key=None,
            handler=self._on_device_lifecycle,
        )
        self._subscription_group.subscribe(
            event_type=DataPointsCreatedEvent,
            event_key=None,
            handler=self._on_data_points_created,
        )
        self._subscription_group.subscribe(
            event_type=DeviceTriggerEvent,
            event_key=None,
            handler=self._on_device_trigger,
        )
        self._subscription_group.subscribe(
            event_type=OptimisticRollbackEvent,
            event_key=None,
            handler=self._on_optimistic_rollback,
        )
        self._async_add_central_to_device_registry()
        await super().start_central()
        # The central is available now. Standalone hub entities that key their
        # availability on it (the backup button) are added before this runs,
        # have no data point to refresh on and do not poll — so tell them to
        # re-evaluate. The loom backend in particular reaches its running state
        # without emitting a state event, so nothing else would.
        self._async_signal_central_state_changed()
        if self._enable_mqtt:
            self._mqtt_consumer = MQTTConsumer(hass=self._hass, central=self._central, mqtt_prefix=self._mqtt_prefix)
            await self._mqtt_consumer.subscribe()
        # Remove orphaned entity registry entries (incl. disabled ones) whose
        # underlying data point no longer exists in the central. Deferred so
        # the aiohomematic scheduler can perform its initial hub data fetch
        # before we evaluate which entries are truly orphaned.
        self._orphan_cleanup_unsub = async_call_later(
            hass=self._hass,
            delay=ORPHAN_CLEANUP_DELAY,
            action=self._async_scheduled_orphan_cleanup,
        )

    async def stop_central(self, *args: Any) -> None:
        """Stop the central unit."""
        if self._orphan_cleanup_unsub is not None:
            self._orphan_cleanup_unsub()
            self._orphan_cleanup_unsub = None

        if self._mqtt_consumer:
            self._mqtt_consumer.unsubscribe()

        self._subscription_group.unsubscribe_all()

        await super().stop_central(*args)

    @callback
    def _async_add_central_to_device_registry(self) -> DeviceEntry:
        """Add the central to device registry and return its entry."""
        device_registry = dr.async_get(self._hass)
        return device_registry.async_get_or_create(
            config_entry_id=self._entry_id,
            identifiers={
                (
                    DOMAIN,
                    self._central.name,
                )
            },
            manufacturer=Manufacturer.EQ3,
            model=self._central.model,
            sw_version=self._central.version,
            name=self._central.name,
            entry_type=DeviceEntryType.SERVICE,
            configuration_url=self._central.url,
        )

    @callback
    def _async_add_virtual_remotes_to_device_registry(self) -> None:
        """Add the virtual remotes to device registry."""
        if not self._central.client_coordinator.has_clients:
            _LOGGER.error(
                "Cannot create ControlUnit %s virtual remote devices. No clients",
                self._instance_name,
            )
            return

        device_registry = dr.async_get(self._hass)
        central_device_id = self._async_add_central_to_device_registry().id
        for virtual_remote in self._central.device_coordinator.get_virtual_remotes():
            device_registry.async_get_or_create(
                config_entry_id=self._entry_id,
                identifiers={
                    (
                        DOMAIN,
                        virtual_remote.identifier,
                    )
                },
                manufacturer=Manufacturer.EQ3,
                name=virtual_remote.name,
                model=virtual_remote.model,
                sw_version=virtual_remote.firmware,
                # Link to the Homematic control unit.
                via_device_id=central_device_id,
            )

    @callback
    def _async_cleanup_orphaned_entity_registry_entries(self) -> None:
        """
        Remove entity-registry entries whose data point no longer exists in the central.

        HA only auto-cleans entities that successfully go through ``async_added_to_hass``,
        which never runs for disabled entities. As a result, disabled entries whose
        underlying data point is gone (e.g. after un_ignore/profile changes or a
        backend device removal) remain in the entity registry indefinitely and cannot
        be removed via the UI. This sweep removes them on integration startup.
        Only runs when the central is fully started so that we don't delete entries
        whose data points just haven't been loaded yet. Device-anchored entries are
        additionally cross-checked against the devices the central currently exposes:
        an entry whose backing device is not (yet) loaded is kept, because a device
        that is merely still materialising (e.g. after a paramset-cache rebuild on
        upgrade) is indistinguishable from a removed one by unique_id alone, and
        deleting would re-create the entity disabled and under a fresh entity_id. As
        an additional safeguard it refuses to run when it would remove more than
        ``ORPHAN_CLEANUP_MAX_DELETE_RATIO`` of the registry entries, which protects
        against a permanent mass deletion when the device descriptions failed to load
        despite the central reporting RUNNING (see aiohomematic#3215).
        """
        if self._config.backend == BACKEND_LOOM:
            # The openccu-loom adapter exposes only a partial hub-coordinator
            # surface (no alarm/service messages, inbox, metrics, connectivity or
            # install-mode data points), so the per-singleton accounting below
            # cannot be built. Skip the sweep until the loom adapter models the
            # full hub surface rather than risk deleting still-valid entries.
            _LOGGER.debug("Skipping orphan entity registry cleanup: not supported on the loom backend")
            return

        if self._central.state != CentralState.RUNNING:
            _LOGGER.debug(
                "Skipping orphan entity registry cleanup, central not RUNNING (state=%s)",
                self._central.state,
            )
            return

        current_unique_ids: set[str] = {
            f"{DOMAIN}_{dp.unique_id}" for dp in self._central.query_facade.get_data_points()
        }
        hub_coordinator = self._central.hub_coordinator
        # Programs + sysvars
        hub_data_points = hub_coordinator.get_hub_data_points()
        current_unique_ids.update(f"{DOMAIN}_{dp.unique_id}" for dp in hub_data_points)
        # Singleton hub data points (alarm/service messages, inbox, system update)
        for single_dp in (
            hub_coordinator.alarm_messages_dp,
            hub_coordinator.service_messages_dp,
            hub_coordinator.inbox_dp,
            hub_coordinator.update_dp,
        ):
            if single_dp is not None:
                current_unique_ids.add(f"{DOMAIN}_{single_dp.unique_id}")
        # Metrics (system_health, connection_latency, last_event_age)
        if (metrics_dps := hub_coordinator.metrics_dps) is not None:
            current_unique_ids.update(
                f"{DOMAIN}_{dp.unique_id}"
                for dp in (metrics_dps.system_health, metrics_dps.connection_latency, metrics_dps.last_event_age)
            )
        # Connectivity binary sensors (one per interface)
        current_unique_ids.update(
            f"{DOMAIN}_{conn.sensor.unique_id}" for conn in hub_coordinator.connectivity_dps.values()
        )
        # Install mode button + sensor (one pair per interface)
        for install_mode in hub_coordinator.install_mode_dps.values():
            current_unique_ids.add(f"{DOMAIN}_{install_mode.button.unique_id}")
            current_unique_ids.add(f"{DOMAIN}_{install_mode.sensor.unique_id}")
        # Device trigger event groups
        for event_type in DeviceTriggerEventType:
            current_unique_ids.update(
                f"{DOMAIN}_{eg.unique_id}" for eg in self._central.query_facade.get_event_groups(event_type=event_type)
            )

        # The pre-id keys the slug-to-id migration would rename onto one of the
        # live data points above. It runs in this same callback, immediately
        # before this sweep, so an entry still holding one here means it did
        # not take: it raised, or that data point yielded no old key. Deletion
        # is permanent and the next start retries the migration, so these are
        # kept rather than swept — the same reasoning as the central-id drift
        # exemption below.
        migratable_unique_ids: set[str] = {
            f"{DOMAIN}_{old_unique_id}"
            for dp in hub_data_points
            if (legacy_name := getattr(dp, "legacy_name", None))
            and (old_unique_id := hub_key_from_name_slug(dp.unique_id, legacy_name=legacy_name)) is not None
        }

        entity_registry = er.async_get(self._hass)
        device_registry = dr.async_get(self._hass)
        platform_entries: list[er.RegistryEntry] = [
            entry
            for entry in er.async_entries_for_config_entry(entity_registry, self._entry_id)
            if entry.platform == DOMAIN
        ]
        central_id = self._config.central_id

        # Device addresses the central currently exposes. A device data point can be
        # absent from current_unique_ids for two very different reasons: its device
        # is gone (genuine orphan) or its device simply has not finished
        # materialising yet (e.g. a slow start or a paramset-cache rebuild after an
        # upgrade, where the central reports RUNNING before every device is built).
        # The two are indistinguishable from unique_ids alone, so device entries are
        # cross-checked against this set below.
        known_device_addresses: set[str] = {device.address for device in self._central.device_coordinator.devices}

        orphaned_entries: list[er.RegistryEntry] = [
            entry
            for entry in platform_entries
            if _is_orphan_registry_entry(
                entry,
                current_unique_ids=current_unique_ids,
                migratable_unique_ids=migratable_unique_ids,
                known_device_addresses=known_device_addresses,
                device_registry=device_registry,
                central_id=central_id,
            )
        ]

        # Refuse implausibly large sweeps: a near-total wipe almost always means the
        # central is RUNNING (clients connected) while the device descriptions failed
        # to load, not that the user actually removed those devices (#3215). Deleting
        # the entries is permanent, so skip and let a later sweep clean up once the
        # device data is fully loaded.
        if platform_entries and len(orphaned_entries) > len(platform_entries) * ORPHAN_CLEANUP_MAX_DELETE_RATIO:
            _LOGGER.warning(
                "Skipping orphan entity registry cleanup: %s of %s entries look orphaned, "
                "which exceeds the safety threshold (likely an incomplete device load)",
                len(orphaned_entries),
                len(platform_entries),
            )
            return

        for entry in orphaned_entries:
            _LOGGER.info(
                "Removing orphan entity registry entry %s (unique_id=%s, disabled=%s)",
                entry.entity_id,
                entry.unique_id,
                entry.disabled,
            )
            entity_registry.async_remove(entry.entity_id)

    @callback
    def _async_get_device_entry(self, *, device_address: str) -> DeviceEntry | None:
        """Return the device of the ha device."""
        if (hm_device := self._central.device_coordinator.get_device(address=device_address)) is None:
            return None
        device_registry = dr.async_get(self._hass)
        return device_registry.async_get_device_by_identifier(
            (
                DOMAIN,
                hm_device.identifier,
            ),
            self._entry_id,
        )

    def _async_migrate_hub_keys_from_name_slug(self) -> None:
        """Move sysvar / program registry keys from the name slug onto the CCU id.

        Both backends used to key these two families on ``slugify(legacy_name)``.
        A rename in the CCU WebUI therefore re-keyed the entity and took its
        history, area and every automation with it, so both moved onto the id
        the CCU already carries — aiohomematic in 2026.8.8, openccu-loom in
        0.68.0. Existing registry entries still hold the slug key.

        The old key is reconstructed rather than transported over the wire: the
        data point carries ``legacy_name``, and the old key was the slug of it,
        so this needs nothing the consumer does not already receive. That is the
        bar the daemon's ADR 0068 sets for a re-key on this plane, and it is
        what makes this pass possible without a contract field.

        Deferred with the orphan cleanup because it needs loaded hub data, which
        means the freshly-keyed twins already exist. A collision is therefore
        expected and resolved rather than skipped: the twin was created seconds
        ago and holds nothing, the registry entry holds the history, so the twin
        is removed and the historied entry takes the key. The other passes skip
        on collision because they run before any entity exists, where a
        collision means something genuinely unexpected.

        Idempotent: a second run finds no slug-keyed entries and does nothing,
        which is also what stops the reload below from repeating.
        """
        try:
            hub_data_points = self._central.hub_coordinator.get_hub_data_points()
        except Exception:
            _LOGGER.debug("Skipping hub key migration: hub data points unavailable", exc_info=True)
            return

        # old registry unique_id -> current unique_id, for the two renameable
        # families only. Every other hub data point takes its name from a module
        # constant, cannot be renamed, and was never keyed on anything else.
        mapping: dict[str, str] = {}
        for data_point in hub_data_points:
            if not (legacy_name := getattr(data_point, "legacy_name", None)):
                continue
            if (old_unique_id := hub_key_from_name_slug(data_point.unique_id, legacy_name=legacy_name)) is not None:
                mapping[f"{DOMAIN}_{old_unique_id}"] = f"{DOMAIN}_{data_point.unique_id}"

        if not mapping:
            return

        entity_registry = er.async_get(self._hass)
        migrated = 0
        for entity_entry in list(er.async_entries_for_config_entry(entity_registry, self._entry_id)):
            if (new_unique_id := mapping.get(entity_entry.unique_id)) is None:
                continue
            if (
                twin_entity_id := entity_registry.async_get_entity_id(
                    entity_entry.domain, entity_entry.platform, new_unique_id
                )
            ) is not None:
                if twin_entity_id == entity_entry.entity_id:
                    continue
                _LOGGER.debug(
                    "Removing the freshly created twin so the historied entry can take its key: %s",
                    twin_entity_id,
                )
                entity_registry.async_remove(twin_entity_id)
            _LOGGER.info(
                "Migrating hub unique_id from the name slug onto the CCU id: %s -> %s",
                entity_entry.unique_id,
                new_unique_id,
            )
            entity_registry.async_update_entity(entity_entry.entity_id, new_unique_id=new_unique_id)
            migrated += 1

        if not migrated:
            return

        # The renamed entry holds the history but nothing live: the entity that
        # existed a moment ago was bound to the twin, and removing the twin
        # removed it. Binding happens at `async_add_entities`, which is over for
        # this session, so without a reload the entity stays gone until the user
        # restarts — which is what an update used to cost.
        already_reloaded: set[str] = self._hass.data.setdefault(HUB_KEY_RELOAD_SCHEDULED, set())
        if self._entry_id in already_reloaded:
            # Reaching here twice means the pass did not converge, so reloading
            # again would not either. Say so and leave it to the next restart.
            _LOGGER.warning(
                "Migrated %s hub entity registry key(s) onto the CCU id after a reload already ran; "
                "not reloading again — those entities re-bind on the next restart",
                migrated,
            )
            return
        already_reloaded.add(self._entry_id)
        _LOGGER.info(
            "Migrated %s hub entity registry key(s) onto the CCU id; reloading so the entities re-bind",
            migrated,
        )
        self._hass.config_entries.async_schedule_reload(self._entry_id)

    @callback
    def _async_scheduled_orphan_cleanup(self, _now: datetime) -> None:
        """Run the deferred hub key migration, then the orphan cleanup."""
        self._orphan_cleanup_unsub = None
        # Order matters and is not incidental: the migration reclaims registry
        # entries the cleanup would otherwise consider orphaned and delete.
        self._async_migrate_hub_keys_from_name_slug()
        self._async_cleanup_orphaned_entity_registry_entries()

    @callback
    def _async_signal_central_state_changed(self) -> None:
        """Fan out that the central's availability may have changed.

        Standalone hub entities that have no data point of their own — the
        backup button — key their availability directly on ``central.available``
        and cannot subscribe to a per-data-point refresh. They connect to this
        dispatcher signal instead and re-render on it.
        """
        async_dispatcher_send(self._hass, signal_central_state_changed(entry_id=self._entry_id))

    @callback
    def _fire_device_availability_event(self, *, device_address: str, device_name: str | None, available: bool) -> None:
        """Fire device availability event to HA event bus."""
        hm_device = self._central.device_coordinator.get_device(address=device_address)
        if hm_device is None:
            _LOGGER.debug("Cannot fire availability event: device %s not found", device_address)
            return

        # Build base event data
        event_data: dict[str, Any] = {
            EVENT_INTERFACE_ID: hm_device.interface_id,
            EVENT_ADDRESS: device_address,
            EVENT_CHANNEL_NO: 0,  # Availability is per device, not channel
            EVENT_MODEL: hm_device.model,
            EVENT_PARAMETER: "AVAILABILITY",
        }

        # Use device_name from event, prefer name_by_user from HA device registry,
        # fall back to the registered HA device name to ensure EVENT_NAME is always set.
        name: str | None = device_name
        if device_entry := self._async_get_device_entry(device_address=device_address):
            name = device_entry.name_by_user or name or device_entry.name
            event_data[EVENT_DEVICE_ID] = device_entry.id
        if name:
            event_data[EVENT_NAME] = name

        title = f"{DOMAIN.upper()} Device {'Available' if available else 'Unavailable'}"
        availability_message = (
            f"{name}/{device_address} on interface {hm_device.interface_id}: "
            f"{'available' if available else 'unavailable'}"
        )

        event_data.update(
            {
                EVENT_IDENTIFIER: f"{device_address}_availability",
                EVENT_TITLE: title,
                EVENT_MESSAGE: availability_message,
                EVENT_UNAVAILABLE: not available,
            }
        )

        if is_valid_event(event_data=event_data, schema=DEVICE_AVAILABILITY_EVENT_SCHEMA):
            self._hass.bus.async_fire(
                event_type=EVENT_TYPE_DEVICE_AVAILABILITY,
                event_data=event_data,
            )

    def _handle_aiohomematic_issue(self, issue: Any) -> None:
        """Process a single aiohomematic-reported issue."""
        issue_id = f"{self._entry_id}_{issue.issue_id}"
        if issue.issue_type == IntegrationIssueType.PING_PONG_MISMATCH and (
            issue.mismatch_count == 0 or issue.severity == IntegrationIssueSeverity.WARNING
        ):
            async_delete_issue(hass=self._hass, domain=DOMAIN, issue_id=issue_id)
            return
        if issue.issue_type == IntegrationIssueType.PARAMSET_INCONSISTENCY:
            ir.async_create_issue(
                hass=self._hass,
                domain=DOMAIN,
                issue_id=issue_id,
                is_fixable=False,
                severity=ir.IssueSeverity.WARNING,
                learn_more_url="https://homematic-forum.de/forum/viewtopic.php?t=77531",
                translation_key=issue.translation_key,
                translation_placeholders=issue.translation_placeholders,
            )
            return
        if issue.severity == IntegrationIssueSeverity.ERROR:
            ir.async_create_issue(
                hass=self._hass,
                domain=DOMAIN,
                issue_id=issue_id,
                is_fixable=False,
                severity=ir.IssueSeverity.ERROR,
                translation_key=issue.translation_key,
                translation_placeholders=issue.translation_placeholders,
            )

    def _handle_callback_state(self, event: SystemStatusChangedEvent) -> None:
        """Process callback_state event detail."""
        if not event.callback_state:
            return
        interface_id, alive = event.callback_state
        _LOGGER.debug("Callback state for %s: alive=%s", interface_id, alive)
        issue_id = get_issue_id(entry_id=self._entry_id, issue_type=ISSUE_TYPE_CALLBACK, interface_id=interface_id)
        if alive:
            async_delete_issue(hass=self._hass, domain=DOMAIN, issue_id=issue_id)
        else:
            ir.async_create_issue(
                hass=self._hass,
                domain=DOMAIN,
                issue_id=issue_id,
                is_fixable=False,
                severity=ir.IssueSeverity.ERROR,
                translation_key="callback_server_failed",
                translation_placeholders={"interface_id": interface_id},
            )

    def _handle_central_state(self, event: SystemStatusChangedEvent) -> bool:
        """Process central_state event detail; return True when reauth was triggered."""
        central_state = event.central_state
        if not central_state:
            return False
        issue_id_degraded = f"{self._entry_id}_central_degraded"
        issue_id_failed = f"{self._entry_id}_central_failed"

        if central_state == CentralState.DEGRADED:
            async_delete_issue(hass=self._hass, domain=DOMAIN, issue_id=issue_id_failed)
            if self._handle_degraded_state(event, issue_id_degraded):
                return True
        elif central_state == CentralState.FAILED:
            async_delete_issue(hass=self._hass, domain=DOMAIN, issue_id=issue_id_degraded)
            if self._handle_failed_state(event, issue_id_failed):
                return True
        else:
            return False

        self._hass.bus.async_fire(
            event_type=f"{DOMAIN}.central_state_changed",
            event_data={"instance_name": self._instance_name, "new_state": central_state.value},
        )
        return False

    def _handle_client_state(self, event: SystemStatusChangedEvent) -> None:
        """Process client_state event detail."""
        if not event.client_state:
            return
        interface_id, old_state, new_state = event.client_state
        _LOGGER.debug("Client state for %s: %s -> %s", interface_id, old_state, new_state)
        issue_id = get_issue_id(entry_id=self._entry_id, issue_type=ISSUE_TYPE_CLIENT, interface_id=interface_id)
        if new_state == ClientState.CONNECTED:
            async_delete_issue(hass=self._hass, domain=DOMAIN, issue_id=issue_id)
        elif new_state == ClientState.DISCONNECTED:
            ir.async_create_issue(
                hass=self._hass,
                domain=DOMAIN,
                issue_id=issue_id,
                is_fixable=False,
                severity=ir.IssueSeverity.ERROR,
                translation_key="client_failed",
                translation_placeholders={"interface_id": interface_id},
            )

    def _handle_connection_state(self, event: SystemStatusChangedEvent) -> None:
        """Process connection_state event detail."""
        if not event.connection_state:
            return
        interface_id, connected = event.connection_state
        _LOGGER.debug("Connection state for %s: connected=%s", interface_id, connected)
        issue_id = get_issue_id(entry_id=self._entry_id, issue_type=ISSUE_TYPE_CONNECTION, interface_id=interface_id)
        if connected:
            async_delete_issue(hass=self._hass, domain=DOMAIN, issue_id=issue_id)
        else:
            ir.async_create_issue(
                hass=self._hass,
                domain=DOMAIN,
                issue_id=issue_id,
                is_fixable=False,
                severity=ir.IssueSeverity.ERROR,
                translation_key="connection_failed",
                translation_placeholders={"interface_id": interface_id},
            )
        self._hass.bus.async_fire(
            event_type=f"{DOMAIN}.interface_connection_changed",
            event_data={
                "instance_name": self._instance_name,
                "interface_id": interface_id,
                "connected": connected,
            },
        )

    def _handle_degraded_state(self, event: SystemStatusChangedEvent, issue_id_degraded: str) -> bool:
        """Handle DEGRADED central state. Return True if reauth was triggered."""
        # Check if any degraded interface has an authentication failure
        auth_failed_interfaces: list[str] = []
        if event.degraded_interfaces:
            for interface_id, reason in event.degraded_interfaces.items():
                if reason == FailureReason.AUTH:
                    auth_failed_interfaces.append(interface_id)
                    _LOGGER.warning(
                        "Interface %s in DEGRADED state due to authentication error",
                        interface_id,
                    )

        # If any interface has AUTH failure, trigger reauth
        if auth_failed_interfaces:
            _LOGGER.warning(
                "Central %s DEGRADED due to authentication error on interfaces: %s. Triggering reauthentication flow",
                self._instance_name,
                ", ".join(auth_failed_interfaces),
            )
            # Get config entry and trigger reauth
            if entry := self._hass.config_entries.async_get_entry(self._entry_id):
                entry.async_start_reauth(self._hass)
            return True

        # No AUTH failures - create normal degraded warning if enabled
        if self._enable_system_notifications:
            ir.async_create_issue(
                hass=self._hass,
                domain=DOMAIN,
                issue_id=issue_id_degraded,
                is_fixable=False,
                severity=ir.IssueSeverity.WARNING,
                translation_key="central_degraded",
                translation_placeholders={
                    "instance_name": self._instance_name,
                    "reason": "Some interfaces disconnected",
                },
            )
            _LOGGER.warning("Central %s is DEGRADED - some interfaces disconnected", self._instance_name)
        else:
            # Also delete DEGRADED issue if notifications are disabled
            async_delete_issue(hass=self._hass, domain=DOMAIN, issue_id=issue_id_degraded)
            _LOGGER.debug("SYSTEM NOTIFICATION disabled for DEGRADED state")
        return False

    def _handle_failed_state(self, event: SystemStatusChangedEvent, issue_id_failed: str) -> bool:
        """Handle FAILED central state. Return True if reauth was triggered."""
        # Check if failure is due to authentication issue
        if event.failure_reason == FailureReason.AUTH:
            # Trigger reauth flow for authentication failures
            _LOGGER.warning(
                "Central %s FAILED due to authentication error. Triggering reauthentication flow",
                self._instance_name,
            )
            # Get config entry and trigger reauth
            if entry := self._hass.config_entries.async_get_entry(self._entry_id):
                entry.async_start_reauth(self._hass)
            return True

        # For non-auth failures, create appropriate repair issue
        if self._enable_system_notifications:
            translation_key = "central_failed"
            reason_text = "All recovery attempts exhausted"

            # Customize message based on failure reason
            if event.failure_reason == FailureReason.NETWORK:
                translation_key = "central_failed_network"
                reason_text = "Network connectivity issue"
            elif event.failure_reason == FailureReason.TIMEOUT:
                translation_key = "central_failed_timeout"
                reason_text = "Connection timeout"
            elif event.failure_reason == FailureReason.INTERNAL:
                translation_key = "central_failed_internal"
                reason_text = "CCU internal error"

            ir.async_create_issue(
                hass=self._hass,
                domain=DOMAIN,
                issue_id=issue_id_failed,
                is_fixable=False,
                severity=ir.IssueSeverity.ERROR,
                translation_key=translation_key,
                translation_placeholders={
                    "instance_name": self._instance_name,
                    "reason": reason_text,
                    "interface_id": event.failure_interface_id or "Unknown",
                },
            )
            _LOGGER.error(
                "Central %s FAILED - %s (interface: %s)",
                self._instance_name,
                reason_text,
                event.failure_interface_id or "Unknown",
            )
        else:
            # Also delete FAILED issue if notifications are disabled
            async_delete_issue(hass=self._hass, domain=DOMAIN, issue_id=issue_id_failed)
            _LOGGER.debug("SYSTEM NOTIFICATION disabled for FAILED state")
        return False

    async def _on_central_recovering(self) -> None:
        """Handle transition to RECOVERING state."""
        _LOGGER.info("Central %s is RECOVERING - attempting reconnection", self._instance_name)
        self._hass.bus.async_fire(
            event_type=f"{DOMAIN}.central_state_changed",
            event_data={"instance_name": self._instance_name, "new_state": CentralState.RECOVERING.value},
        )

    async def _on_central_running(self) -> None:
        """Handle transition to RUNNING state."""
        issue_id_degraded = f"{self._entry_id}_central_degraded"
        issue_id_failed = f"{self._entry_id}_central_failed"
        async_delete_issue(hass=self._hass, domain=DOMAIN, issue_id=issue_id_degraded)
        async_delete_issue(hass=self._hass, domain=DOMAIN, issue_id=issue_id_failed)
        _LOGGER.info("Central %s is RUNNING - all interfaces connected", self._instance_name)
        self._hass.bus.async_fire(
            event_type=f"{DOMAIN}.central_state_changed",
            event_data={"instance_name": self._instance_name, "new_state": CentralState.RUNNING.value},
        )

    async def _on_central_state_changed(self, *, event: CentralStateChangedEvent) -> None:
        """Handle central state transitions."""
        # Every transition can flip central.available, so re-notify availability
        # dependent standalone entities regardless of the specific target state.
        self._async_signal_central_state_changed()
        if event.new_state == CentralState.RECOVERING:
            await self._on_central_recovering()
        elif event.new_state == CentralState.RUNNING:
            await self._on_central_running()

    async def _on_data_points_created(self, event: DataPointsCreatedEvent) -> None:
        """Handle data points created event from aiohomematic (Entity discovery)."""
        for category, data_points in event.new_data_points.items():
            if data_points and len(data_points) > 0:
                async_dispatcher_send(
                    self._hass,
                    signal_new_data_point(entry_id=self._entry_id, platform=category),
                    data_points,
                )

    async def _on_device_lifecycle(self, event: DeviceLifecycleEvent) -> None:
        """Handle device lifecycle event from aiohomematic (Device lifecycle + availability)."""
        if event.event_type == DeviceLifecycleEventType.CREATED:
            _LOGGER.debug("Devices created: %s", event.device_addresses)
            if event.includes_virtual_remotes:
                self._async_add_virtual_remotes_to_device_registry()

        elif event.event_type == DeviceLifecycleEventType.DELAYED:
            _LOGGER.debug("Devices delayed: %s on interface %s", event.device_addresses, event.interface_id)
            interface_id = event.interface_id
            if not interface_id:
                return

            # Check if we're in auto-confirm window (initial setup)
            if self._auto_confirm_until is not None and time.time() < self._auto_confirm_until:
                _LOGGER.debug(
                    "Auto-confirming devices during initial setup: %s on interface %s",
                    event.device_addresses,
                    interface_id,
                )
                # Directly add devices without creating repair issues
                await self._central.device_coordinator.add_new_devices_manually(
                    interface_id=interface_id,
                    address_names=dict.fromkeys(event.device_addresses, ""),
                )
                return

            # Check which devices already exist in HA device registry (e.g., after cache clear)
            # These should be auto-confirmed without creating repair issues
            device_registry = dr.async_get(self._hass)
            existing_addresses: list[str] = []
            new_addresses: list[str] = []

            for address in event.device_addresses:
                # Device identifier format is: {address}@{interface_id}
                expected_identifier = f"{address}@{interface_id}"
                if device_registry.async_get_device_by_identifier((DOMAIN, expected_identifier), self._entry_id):
                    existing_addresses.append(address)
                else:
                    new_addresses.append(address)

            # Auto-confirm devices that already exist in HA (cache was cleared but devices are known)
            if existing_addresses:
                _LOGGER.debug(
                    "Auto-confirming existing devices after cache clear: %s on interface %s",
                    existing_addresses,
                    interface_id,
                )
                await self._central.device_coordinator.add_new_devices_manually(
                    interface_id=interface_id,
                    address_names=dict.fromkeys(existing_addresses, ""),
                )

            # Create repair issues only for truly new devices
            for address in new_addresses:
                issue_id = f"devices_delayed|{interface_id}|{address}"

                async def _fix_callback(*, device_name: str, _interface_id: str, _address: str) -> None:
                    """Rename, accept inbox device, and trigger manual add of the delayed device."""
                    if not _interface_id:
                        return
                    # Trigger manual add of the device
                    await self._central.device_coordinator.add_new_devices_manually(
                        interface_id=_interface_id, address_names={_address: device_name}
                    )

                REPAIR_CALLBACKS[issue_id] = partial(_fix_callback, _interface_id=interface_id, _address=address)

                ir.async_create_issue(
                    hass=self._hass,
                    domain=DOMAIN,
                    issue_id=issue_id,
                    is_fixable=True,
                    severity=ir.IssueSeverity.WARNING,
                    translation_key="devices_delayed",
                    translation_placeholders={
                        "instance_name": self._instance_name,
                        "interface_id": interface_id,
                        "address": address,
                    },
                )

        elif event.event_type == DeviceLifecycleEventType.AVAILABILITY_CHANGED:
            # Build address-to-name mapping from event
            name_by_address: dict[str, str] = dict(zip(event.device_addresses, event.device_names, strict=False))
            for device_address, available in event.availability_changes:
                _LOGGER.debug("Device %s availability: %s", device_address, available)

                # Fire HA event for automations (e.g., blueprints)
                self._fire_device_availability_event(
                    device_address=device_address,
                    device_name=name_by_address.get(device_address),
                    available=available,
                )

    async def _on_device_trigger(self, event: DeviceTriggerEvent) -> None:
        """Handle device trigger event from aiohomematic (Device triggers for HA event bus)."""

        device_address = event.device_address
        # Build base event data
        event_data: dict[str, Any] = {
            EVENT_INTERFACE_ID: event.interface_id,
            EVENT_ADDRESS: device_address,
            EVENT_CHANNEL_NO: event.channel_no,
            EVENT_MODEL: event.model,
            EVENT_PARAMETER: event.parameter,
            EVENT_VALUE: event.value,
        }

        # Use event.device_name from aiohomematic, prefer name_by_user from HA device registry,
        # fall back to the registered HA device name to ensure EVENT_NAME is always set.
        name: str | None = event.device_name
        if device_entry := self._async_get_device_entry(device_address=device_address):
            name = device_entry.name_by_user or name or device_entry.name
            event_data[EVENT_DEVICE_ID] = device_entry.id
        if name:
            event_data[EVENT_NAME] = name

        trigger_type = event.trigger_type

        if trigger_type in (DeviceTriggerEventType.IMPULSE, DeviceTriggerEventType.KEYPRESS):
            # Transform data to match CLICK_EVENT_SCHEMA
            cleaned_event_data = cleanup_click_event_data(event_data=event_data)
            if is_valid_event(event_data=cleaned_event_data, schema=CLICK_EVENT_SCHEMA):
                self._hass.bus.async_fire(
                    event_type=trigger_type.value,
                    event_data=cleaned_event_data,
                )

        elif trigger_type == DeviceTriggerEventType.DEVICE_ERROR:
            error_parameter = event.parameter
            if error_parameter in FILTER_ERROR_EVENT_PARAMETERS:
                return

            error_parameter_display = error_parameter.replace("_", " ").title()
            title = f"{DOMAIN.upper()} Device Error"
            error_message: str = ""
            error_value = event.value
            display_error: bool = False

            if isinstance(error_value, bool):
                display_error = error_value
                error_message = f"{name}/{device_address} on interface {event.interface_id}: {error_parameter_display}"
            if isinstance(error_value, int):
                display_error = error_value != 0
                error_message = (
                    f"{name}/{device_address} on interface {event.interface_id}: "
                    f"{error_parameter_display} {error_value}"
                )

            event_data.update(
                {
                    EVENT_IDENTIFIER: f"{device_address}_{error_parameter}",
                    EVENT_TITLE: title,
                    EVENT_MESSAGE: error_message,
                    EVENT_ERROR_VALUE: error_value,
                    EVENT_ERROR: display_error,
                }
            )
            if is_valid_event(event_data=event_data, schema=DEVICE_ERROR_EVENT_SCHEMA):
                self._hass.bus.async_fire(
                    event_type=trigger_type.value,
                    event_data=event_data,
                )

    async def _on_optimistic_rollback(self, event: OptimisticRollbackEvent) -> None:
        """Handle optimistic rollback event from aiohomematic."""
        if not self._enable_system_notifications:
            return

        device_address = get_device_address(address=event.dpk.channel_address)

        # Use event.device_name from aiohomematic, prefer name_by_user from HA device registry
        name: str | None = event.device_name
        if device_entry := self._async_get_device_entry(device_address=device_address):
            name = device_entry.name_by_user or name

        display_name = name or device_address

        event_data: dict[str, Any] = {
            EVENT_INTERFACE_ID: event.dpk.interface_id,
            EVENT_ADDRESS: device_address,
            EVENT_PARAMETER: event.dpk.parameter,
            EVENT_REASON: event.reason,
            EVENT_ROLLED_BACK_VALUE: event.rolled_back_value,
            EVENT_RESTORED_VALUE: event.restored_value,
            EVENT_AGE_SECONDS: event.age_seconds,
        }

        if device_entry:
            event_data[EVENT_DEVICE_ID] = device_entry.id
            event_data[EVENT_NAME] = display_name

        if event.error:
            event_data[EVENT_ERROR] = event.error

        self._hass.bus.async_fire(
            event_type=EVENT_TYPE_OPTIMISTIC_ROLLBACK,
            event_data=event_data,
        )

        _LOGGER.warning(
            "Optimistic rollback for %s/%s: %s -> %s (reason=%s, age=%.1fs)",
            display_name,
            event.dpk.parameter,
            event.rolled_back_value,
            event.restored_value,
            event.reason,
            event.age_seconds,
        )

    async def _on_system_status(self, event: SystemStatusChangedEvent) -> None:
        """Handle system status event from aiohomematic (detail-dependent logic)."""
        if self._handle_central_state(event):
            return  # Reauth triggered, suppress further processing
        self._handle_connection_state(event)
        self._handle_client_state(event)
        self._handle_callback_state(event)
        for issue in event.issues:
            self._handle_aiohomematic_issue(issue)


class ControlUnitTemp(BaseControlUnit):
    """Central unit to control a central unit for temporary usage."""

    async def stop_central(self, *args: Any) -> None:
        """Stop the control unit."""
        await self._central.cache_coordinator.clear_all()
        await super().stop_central(*args)


class ControlConfig:
    """Config for a ControlUnit."""

    def __init__(
        self,
        *,
        hass: HomeAssistant,
        entry_id: str,
        data: Mapping[str, Any],
        serial: str | None = None,
        auto_confirm_until: float | None = None,
        default_callback_port_xml_rpc: int = PORT_ANY,
        enable_device_firmware_check: bool = DEFAULT_ENABLE_DEVICE_FIRMWARE_CHECK,
        start_direct: bool = False,
    ) -> None:
        """Create the required config for the ControlUnit."""
        self.hass: Final = hass
        self.entry_id: Final = entry_id
        self._data: Final = data
        # The CCU serial (HA's config-entry unique_id). For the loom backend
        # it is injected into the adapter to fill the central-id slot of
        # canonical HA routing keys, so live keys match the one-time
        # unique_id registry migration. ``None`` on the validate path (no
        # entry yet) → the adapter falls back to /system/ccu.
        self._serial: Final = serial
        self.auto_confirm_until: Final = auto_confirm_until
        self._default_callback_port_xml_rpc: Final = default_callback_port_xml_rpc
        self._start_direct: Final = start_direct
        self._enable_device_firmware_check: Final = enable_device_firmware_check

        # backend: aiohomematic direct-CCU (default) or openccu-loom daemon
        self._backend: Final[str] = self._data.get(CONF_BACKEND, DEFAULT_BACKEND)
        # central — credentials are optional for the loom backend (it
        # authenticates with a bearer token), so read them defensively.
        self.instance_name: Final[str] = cleanup_instance_name(instance_name=self._data[CONF_INSTANCE_NAME])
        self._host: Final[str] = self._data[CONF_HOST]
        self._username: Final[str] = self._data.get(CONF_USERNAME, "")
        self._password: Final[str] = self._data.get(CONF_PASSWORD, "")
        self._tls: Final[bool] = self._data.get(CONF_TLS, False)
        self._verify_tls: Final[bool] = self._data.get(CONF_VERIFY_TLS, False)
        # loom-only connection inputs
        self._loom_token: Final[str | None] = self._data.get(CONF_LOOM_TOKEN)
        self._loom_port: Final[int | None] = self._data.get(CONF_LOOM_PORT)
        self._callback_host: Final[str | None] = self._data.get(CONF_CALLBACK_HOST)
        self._callback_port_xml_rpc: Final[int | None] = self._data.get(CONF_CALLBACK_PORT_XML_RPC)
        self._json_port: Final[int | None] = self._data.get(CONF_JSON_PORT)

        # interface_config
        self._interface_config: Final[Mapping[str, Any]] = self._data.get(CONF_INTERFACE, {})
        # advanced_config
        ac = self._data.get(CONF_ADVANCED_CONFIG, {})
        self.disable_config_panel: Final[bool] = ac.get(CONF_DISABLE_CONFIG_PANEL, DEFAULT_DISABLE_CONFIG_PANEL)
        self.enable_light_last_brightness: Final[bool] = ac.get(
            CONF_ENABLE_LIGHT_LAST_BRIGHTNESS, DEFAULT_ENABLE_LIGHT_LAST_BRIGHTNESS
        )
        self.enable_mqtt: Final[bool] = ac.get(CONF_ENABLE_MQTT, DEFAULT_ENABLE_MQTT)
        self._enable_program_scan: Final[bool] = ac.get(CONF_ENABLE_PROGRAM_SCAN, DEFAULT_ENABLE_PROGRAM_SCAN)
        self.enable_sub_devices: Final[bool] = ac.get(CONF_ENABLE_SUB_DEVICES, DEFAULT_ENABLE_SUB_DEVICES)
        self.enable_system_notifications: Final[bool] = ac.get(
            CONF_ENABLE_SYSTEM_NOTIFICATIONS, DEFAULT_ENABLE_SYSTEM_NOTIFICATIONS
        )
        self._enable_sysvar_scan: Final[bool] = ac.get(CONF_ENABLE_SYSVAR_SCAN, DEFAULT_ENABLE_SYSVAR_SCAN)
        self._listen_on_all_ip: Final[bool] = ac.get(CONF_LISTEN_ON_ALL_IP, DEFAULT_LISTEN_ON_ALL_IP)
        self.mqtt_prefix: Final[str] = ac.get(CONF_MQTT_PREFIX, DEFAULT_MQTT_PREFIX)
        self._optional_settings: Final[tuple[OptionalSettings | str, ...]] = (
            optional_settings if (optional_settings := ac.get(CONF_OPTIONAL_SETTINGS)) else DEFAULT_OPTIONAL_SETTINGS
        )
        self._program_markers: Final[tuple[DescriptionMarker | str, ...]] = (
            program_markers if (program_markers := ac.get(CONF_PROGRAM_MARKERS)) else DEFAULT_PROGRAM_MARKERS
        )
        self._sys_scan_interval: Final[int] = ac.get(CONF_SYS_SCAN_INTERVAL, DEFAULT_SYS_SCAN_INTERVAL)
        self._command_retry_max_attempts: Final[int] = ac.get(
            CONF_COMMAND_RETRY_MAX_ATTEMPTS, DEFAULT_COMMAND_RETRY_MAX_ATTEMPTS
        )
        self._command_throttle_interval: Final[float] = ac.get(
            CONF_COMMAND_THROTTLE_INTERVAL, DEFAULT_COMMAND_THROTTLE_INTERVAL
        )
        self._sysvar_markers: Final[tuple[DescriptionMarker | str, ...]] = (
            sysvar_markers if (sysvar_markers := ac.get(CONF_SYSVAR_MARKERS)) else DEFAULT_SYSVAR_MARKERS
        )
        self._un_ignore: Final[frozenset[str]] = frozenset(ac.get(CONF_UN_IGNORES, DEFAULT_UN_IGNORES))
        self._use_group_channel_for_cover_state: Final[bool] = ac.get(
            CONF_USE_GROUP_CHANNEL_FOR_COVER_STATE, DEFAULT_USE_GROUP_CHANNEL_FOR_COVER_STATE
        )
        self._backup_path: Final[str] = ac.get(CONF_BACKUP_PATH, DEFAULT_BACKUP_PATH)

    @property
    def _temporary_config(self) -> ControlConfig:
        """Return a config for validation."""
        temporary_data: dict[str, Any] = deepcopy(dict(self._data))
        temporary_data[CONF_INSTANCE_NAME] = "temporary_instance"
        return ControlConfig(
            hass=self.hass,
            entry_id="hmip_local_temporary",
            data=temporary_data,
            start_direct=True,
        )

    @property
    def backend(self) -> str:
        """Return the configured backend (CCU or openccu-loom)."""
        return self._backend

    @property
    def backup_directory(self) -> str:
        """Return the full path to the backup directory."""
        return f"{get_storage_directory(hass=self.hass)}/{self._backup_path}"

    @property
    def central_id(self) -> str:
        """Return the central id that anchors hub / virtual-remote unique_ids.

        The CCU serial when known, else the entry_id, truncated to the last 10
        chars and lower-cased to match aiohomematic's key slot (it lower-cases the
        whole unique_id). Survives an integration delete + re-add when a serial is
        available (the entry_id is regenerated then).
        """
        return (self._serial or self.entry_id)[-10:].lower()

    @property
    def interface_config(self) -> Mapping[str, Any]:
        """Return the interface configuration."""
        return self._interface_config

    async def check_config(self) -> None:
        """Check config. Throws BaseHomematicException on failure."""
        if not self._check_instance_name_is_unique():
            raise InvalidConfig("Instance name must be unique.")
        storage_directory = get_storage_directory(hass=self.hass)
        if self._backend == BACKEND_LOOM:
            loom_check_config = await self.hass.async_add_import_executor_job(_import_loom_check_config)

            # Credentials are optional for the loom backend; pass None instead of
            # an empty string so the daemon does not reject a "given but empty"
            # username (or password).
            config_failures = await loom_check_config(
                central_name=self.instance_name,
                host=self._host,
                username=self._username or None,
                password=self._password or None,
                callback_host=self._callback_host,
                callback_port_xml_rpc=self._callback_port_xml_rpc,
                json_port=self._json_port,
                storage_directory=storage_directory,
            )
        else:
            config_failures = await check_config(
                central_name=self.instance_name,
                host=self._host,
                username=self._username,
                password=self._password,
                callback_host=self._callback_host,
                callback_port_xml_rpc=self._callback_port_xml_rpc,
                json_port=self._json_port,
                storage_directory=storage_directory,
            )
        if config_failures:
            failures = ", ".join(config_failures)
            raise InvalidConfig(failures)

    async def create_central(self) -> CentralUnit:
        """Create the central unit.

        For the openccu-loom backend the central is the
        ``LoomCentralAdapter`` from openccu-loom-client's
        aiohomematic-compatible package; for the default CCU backend it
        is aiohomematic's own ``CentralUnit``.
        """
        if self._backend == BACKEND_LOOM:
            return await self._create_loom_central()
        return await self._create_ccu_central()

    async def create_control_unit(self) -> ControlUnit:
        """Create the control unit asynchronously."""
        return await ControlUnit.async_create(control_config=self)

    async def create_control_unit_temp(self) -> ControlUnitTemp:
        """Create a temporary control unit asynchronously."""
        return await ControlUnitTemp.async_create(control_config=self._temporary_config)

    def _check_instance_name_is_unique(self) -> bool:
        """Check if instance_name is unique in HA."""
        for entry in self.hass.config_entries.async_entries(domain=DOMAIN):
            if entry.entry_id == self.entry_id or len(entry.data) == 0:
                continue
            if hasattr(entry.data, CONF_INSTANCE_NAME) and entry.data[CONF_INSTANCE_NAME] == self.instance_name:
                return False
        return True

    async def _create_ccu_central(self) -> CentralUnit:
        """Create the central unit for ccu callbacks."""
        interface_configs: set[InterfaceConfig] = set()
        for interface_name in self._interface_config:
            interface = self._interface_config[interface_name]
            interface_type = Interface(interface_name)
            # Use configured port, fall back to default port
            # JSON-RPC-only interfaces (CUxD, CCU-Jack) don't have an XML-RPC port
            if (configured_port := interface.get(CONF_PORT)) is not None:
                port: int | None = configured_port
            else:
                port = get_interface_default_port(interface=interface_type, tls=self._tls)
            interface_configs.add(
                InterfaceConfig(
                    central_name=self.instance_name,
                    interface=interface_type,
                    port=port,
                    remote_path=interface.get(CONF_PATH),
                )
            )
        # The CCU serial anchors hub / sysvar / program / virtual-remote
        # entity unique_ids so they survive an integration delete + re-add
        # (the entry_id is regenerated then); falls back to the entry_id while
        # the serial is not yet known. See :attr:`central_id`.
        central_id = self.central_id
        return await CentralConfig(
            callback_host=self._callback_host if self._callback_host != IP_ANY_V4 else None,
            callback_port_xml_rpc=self._callback_port_xml_rpc if self._callback_port_xml_rpc != PORT_ANY else None,
            central_id=central_id,
            client_session=aiohttp_client.async_get_clientsession(self.hass),
            delay_new_device_creation=True,
            enable_device_firmware_check=DEFAULT_ENABLE_DEVICE_FIRMWARE_CHECK,
            enable_program_scan=self._enable_program_scan,
            enable_sysvar_scan=self._enable_sysvar_scan,
            listen_ip_addr=IP_ANY_V4 if self._listen_on_all_ip else None,
            default_callback_port_xml_rpc=self._default_callback_port_xml_rpc,
            host=self._host,
            interface_configs=frozenset(interface_configs),
            interfaces_requiring_periodic_refresh=frozenset(
                () if self.enable_mqtt else DEFAULT_INTERFACES_REQUIRING_PERIODIC_REFRESH
            ),
            json_port=self._json_port,
            locale=self.hass.config.language,
            max_read_workers=1,
            name=self.instance_name,
            optional_settings=frozenset(self._optional_settings),
            password=self._password,
            program_markers=self._program_markers,
            schedule_timer_config=ScheduleTimerConfig(sys_scan_interval=self._sys_scan_interval),
            timeout_config=TimeoutConfig(
                command_retry_max_attempts=self._command_retry_max_attempts,
                command_throttle_interval=self._command_throttle_interval,
            ),
            start_direct=self._start_direct,
            storage_directory=get_storage_directory(hass=self.hass),
            sysvar_markers=self._sysvar_markers,
            tls=self._tls,
            un_ignore_list=self._un_ignore,
            use_group_channel_for_cover_state=self._use_group_channel_for_cover_state,
            username=self._username,
            verify_tls=self._verify_tls,
        ).create_central()

    async def _create_loom_central(self) -> CentralUnit:
        """Build the openccu-loom-backed central via the compat adapter.

        Imported lazily so a CCU-only install does not need
        openccu-loom-client present.
        """
        try:
            loom_central_config = await self.hass.async_add_import_executor_job(_import_loom_central_config)
        except ImportError as err:  # pragma: no cover - install-time guard
            raise InvalidConfig(
                "The 'loom' backend requires the 'openccu-loom-client' package to be installed."
            ) from err

        central = await loom_central_config(
            name=self.instance_name,
            host=self._host,
            port=self._loom_port,
            tls=self._tls,
            verify_tls=self._verify_tls,
            token=self._loom_token,
            username=self._username or None,
            password=self._password or None,
            serial=self._serial,
            client_session=aiohttp_client.async_get_clientsession(self.hass),
            # Sysvar/program marker filtering and enabled-by-default are
            # resolved daemon-side, so this backend threads no markers
            # through the way the direct-CCU path does. The versions that
            # guarantee it are the pins in manifest.json.
            locale=self.hass.config.language,
        ).create_central()
        # The loom adapter duck-types CentralUnit; aiohomematic's Protocol
        # metaclass blocks subclassing, so a cast is the only bridge.
        return cast(CentralUnit, central)


def _import_loom_central_config() -> type[LoomCentralConfig]:
    """Import the loom-backed CentralConfig.

    Pydantic's lazy submodule imports make this a blocking call, so it must
    run in Home Assistant's import executor rather than the event loop.
    """
    from openccu_loom_client.compat.aiohomematic.central import CentralConfig as LoomCentralConfig  # noqa: PLC0415

    return LoomCentralConfig


def _import_loom_check_config() -> Callable[..., Awaitable[list[str]]]:
    """Import the loom-backed check_config.

    Blocking for the same reason as :func:`_import_loom_central_config`; run
    it in the import executor.
    """
    from openccu_loom_client.compat.aiohomematic.central import check_config as loom_check_config  # noqa: PLC0415

    return loom_check_config


def signal_new_data_point(*, entry_id: str, platform: DataPointCategory | str) -> str:
    """Gateway specific event to signal new device."""
    platform_value = platform.value if isinstance(platform, DataPointCategory) else platform
    return f"{DOMAIN}-new-data-point-{entry_id}-{platform_value}"


def signal_central_state_changed(*, entry_id: str) -> str:
    """Gateway specific event to signal that the central's availability changed."""
    return f"{DOMAIN}-central-state-changed-{entry_id}"


async def validate_config_and_get_system_information(
    *,
    control_config: ControlConfig,
) -> SystemInformation | None:
    """Validate the control configuration."""
    if control_unit := await control_config.create_control_unit_temp():
        return await control_unit.central.validate_config_and_get_system_information()
    return None


def get_storage_directory(*, hass: HomeAssistant) -> str:
    """Return the base path where to store files for this integration."""
    return f"{hass.config.config_dir}/{DOMAIN}"


def _loom_config_ui_base(*, central: Any) -> str:
    """
    Return the loom Config-UI base URL, or ``""`` when none can be built.

    Prefers the daemon's own answer over anything derived here. The
    address this integration connects on may be a container or
    proxy-internal one that no browser can follow, which is precisely the
    case ``north.rest.public_url`` exists to record.
    """
    if configured := str(getattr(central, "config_ui_url", "") or ""):
        return configured
    # Derived fallback: correct for a LAN-direct install, wrong behind a
    # reverse proxy. Better than nothing, worse than a declared value.
    if not (url := str(getattr(central, "url", "") or "")):
        return ""
    return url.removesuffix("/api/v1").rstrip("/") + "/app/"


def _entry_device_address(*, entry: er.RegistryEntry, device_registry: dr.DeviceRegistry) -> str | None:
    """
    Return the backing device address of a device-anchored registry entry, else None.

    Returns None for hub / program / sysvar / install-mode / virtual-remote entries
    (their HA device is the central pseudo-device, whose identifier carries no
    ``IDENTIFIER_SEPARATOR``) and for entries whose HA device no longer exists
    (``device_id`` unset or the device already removed) — a genuine removal, which
    must stay subject to the normal orphan rules.
    """
    if entry.device_id is None or (device := device_registry.async_get(entry.device_id)) is None:
        return None
    for domain, identifier in device.identifiers:
        if domain != DOMAIN:
            continue
        address, separator, _interface_id = identifier.partition(IDENTIFIER_SEPARATOR)
        if separator:
            return address
    return None


def _is_orphan_registry_entry(
    entry: er.RegistryEntry,
    *,
    current_unique_ids: set[str],
    migratable_unique_ids: set[str],
    known_device_addresses: set[str],
    device_registry: dr.DeviceRegistry,
    central_id: str,
) -> bool:
    """Return True only for entries whose data point is genuinely gone."""
    if entry.unique_id in current_unique_ids:
        return False
    # Pre-id hub key whose data point is right there under its id key: the
    # slug-to-id migration has not taken it yet. The entry carries the history
    # and the migration is retried on every start, so never sweep it.
    if entry.unique_id in migratable_unique_ids:
        return False
    # The per-central backup button is integration-native (not an aiohomematic
    # routing key) and is recreated on every setup, so it must never be swept.
    if entry.unique_id.endswith("_create_backup"):
        return False
    # Central-id drift: the data point still exists but the registry entry is on a
    # stale central-id anchor (a prior entry_id / serial). The setup-time realign
    # migration owns this; deleting here would discard the user's customisations
    # permanently, so never treat it as an orphan.
    realigned = realign_hub_unique_id(entry.unique_id, central_id=central_id)
    if realigned is not None and realigned in current_unique_ids:
        return False
    # Device-presence guard: when the entry is backed by a device the central does
    # not currently expose, the missing data point most likely means the device is
    # still materialising rather than gone. Skipping avoids permanently deleting
    # (and re-creating, disabled, under a fresh entity_id) entities whenever a
    # device loads slowly. A genuine removal drops the HA device too, so the address
    # resolves to None there and the entry stays sweepable.
    device_address = _entry_device_address(entry=entry, device_registry=device_registry)
    return device_address is None or device_address in known_device_addresses
