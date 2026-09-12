"""Homematic(IP) Local for OpenCCU is a Python 3 module for Home Assistant and Homematic(IP) devices."""

from __future__ import annotations

from collections.abc import Callable
import contextlib
from dataclasses import dataclass
import logging
import re
import time
from typing import Any, TypeAlias

from awesomeversion import AwesomeVersion

from aiohomematic import __version__ as HAHM_VERSION
from aiohomematic.const import (
    DEFAULT_ENABLE_SYSVAR_SCAN,
    DEFAULT_UN_IGNORES,
    IDENTIFIER_SEPARATOR,
    IntegrationIssueType,
    Interface,
    OptionalSettings,
    is_interface_default_port,
)
from aiohomematic.exceptions import AuthFailure
from aiohomematic.store.persistent import cleanup_files
from aiohomematic.support import find_free_port
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_PORT, EVENT_HOMEASSISTANT_STOP, __version__ as HA_VERSION_STR
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryError
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.helpers.entity_registry import async_migrate_entries
from homeassistant.util.hass_dict import HassKey

from .backup import async_notify_backup_listeners
from .const import (
    BACKEND_LOOM,
    CONF_ACTION_SELECT_VALUES,
    CONF_ADVANCED_CONFIG,
    CONF_BACKEND,
    CONF_CALLBACK_PORT_XML_RPC,
    CONF_COMMAND_THROTTLE_INTERVAL,
    CONF_CUSTOM_PORTS,
    CONF_DISABLE_CONFIG_PANEL,
    CONF_ENABLE_PROGRAM_SCAN,
    CONF_ENABLE_SYSTEM_NOTIFICATIONS,
    CONF_ENABLE_SYSVAR_SCAN,
    CONF_INSTANCE_NAME,
    CONF_INTERFACE,
    CONF_OPTIONAL_SETTINGS,
    CONF_SYS_SCAN_INTERVAL,
    CONF_UN_IGNORES,
    DEFAULT_AUTO_CONFIRM_NEW_DEVICES_TIMEOUT,
    DEFAULT_COMMAND_THROTTLE_INTERVAL,
    DEFAULT_DISABLE_CONFIG_PANEL,
    DEFAULT_ENABLE_SYSTEM_NOTIFICATIONS,
    DEFAULT_SYS_SCAN_INTERVAL,
    DOMAIN,
    HMIP_LOCAL_MIN_HA_VERSION,
    HMIP_LOCAL_PLATFORMS,
    ISSUE_TYPE_CALLBACK,
    ISSUE_TYPE_CONNECTION,
)
from .control_unit import ControlConfig, ControlUnit, get_storage_directory
from .device_icon import ICON_VIEW_REGISTERED_KEY, DeviceIconView
from .panel import async_register_cards, async_register_panel, async_unregister_cards, async_unregister_panel
from .services import async_get_loaded_config_entries, async_setup_services, async_unload_services
from .support import (
    async_delete_issues,
    get_aiohomematic_version,
    get_device_address_from_identifiers,
    realign_hub_unique_id,
)
from .websocket_api import async_register_websocket_commands

HA_VERSION = AwesomeVersion(HA_VERSION_STR)
HomematicConfigEntry: TypeAlias = ConfigEntry[ControlUnit]


@dataclass(kw_only=True, slots=True)
class HomematicData:
    """Common data for shared Homematic ip local data."""

    default_callback_port_xml_rpc: int | None = None


HM_KEY: HassKey[HomematicData] = HassKey(DOMAIN)
_LOGGER = logging.getLogger(__name__)

# Issue types that a setup of the config entry has to withdraw itself, because
# nothing else ever will: what would take them back is a per-session object
# that is rebuilt empty together with the entry. A connection issue is only
# withdrawn for an interface the central's connection state tracker holds
# (``CentralConnectionState.remove_issue``), and a restored callback only for a
# client whose ``_is_callback_alive`` had been set to False — both start out
# blank, so a repair left over from the previous session would stay forever. A
# fault that is still present raises its issue anew within seconds of the
# start. ``client`` is deliberately not in this list: a fresh client always
# transitions to CONNECTED, and that transition withdraws the repair.
_STALE_ISSUE_TYPES: tuple[str, ...] = (
    IntegrationIssueType.PING_PONG_MISMATCH,
    IntegrationIssueType.FETCH_DATA_FAILED,
    IntegrationIssueType.INCOMPLETE_DEVICE_DATA,
    ISSUE_TYPE_CALLBACK,
    ISSUE_TYPE_CONNECTION,
)


def _cleanup_stale_issues(*, hass: HomeAssistant, entry_id: str) -> None:
    """Delete stale issues from previous sessions for this config entry."""
    for issue_id in async_delete_issues(hass=hass, entry_id=entry_id, issue_types=_STALE_ISSUE_TYPES):
        _LOGGER.debug("Deleted stale issue %s on startup", issue_id)


def _any_entry_has_panel_enabled(*, hass: HomeAssistant) -> bool:
    """
    Return True if any loaded config entry has the config panel enabled.

    Entries on the openccu-loom backend never count. The daemon ships its
    own Config UI covering everything this panel offers — paramsets,
    direct links, schedules, change history — and covering it for *every*
    CCU it serves rather than the one behind a single config entry. 2.9.1
    already retired the CCU and Integration tabs on that reasoning; this
    is the same argument applied to what was left.

    The panel is registered once for all entries, so a mixed installation
    (one CCU entry, one loom entry) still registers it. The panel's own
    entry picker drops the loom ones.
    """
    for entry in hass.config_entries.async_entries(domain=DOMAIN, include_ignore=False, include_disabled=False):
        if entry.data.get(CONF_BACKEND) == BACKEND_LOOM:
            continue
        if entry.data.get(CONF_ADVANCED_CONFIG, {}).get(CONF_DISABLE_CONFIG_PANEL, DEFAULT_DISABLE_CONFIG_PANEL):
            continue
        if hasattr(entry, "runtime_data") and entry.runtime_data:
            return True
    return False


class _NeverRaised(Exception):
    """Placeholder type so an `except` clause can be written unconditionally."""


def _loom_incompatible_version_error() -> type[Exception]:
    """
    Return the loom client's incompatible-version error, or an unraisable stand-in.

    Imported lazily like every other `openccu_loom_client` reference in this
    integration, and degraded to a type nothing raises when the package is
    absent — the `except` clause then simply never matches, which is the
    correct behaviour on a backend that has no daemon.
    """
    try:
        from openccu_loom_client import LoomIncompatibleVersionError  # noqa: PLC0415
    except ImportError:
        return _NeverRaised
    return LoomIncompatibleVersionError


async def async_setup_entry(hass: HomeAssistant, entry: HomematicConfigEntry) -> bool:
    """Set up Homematic(IP) Local for OpenCCU from a config entr11y."""
    # The openccu-loom backend talks to the daemon via openccu-loom-client
    # and does not depend on the aiohomematic runtime version, so skip the
    # aiohomematic version gate for it.
    is_loom_backend = entry.data.get(CONF_BACKEND) == BACKEND_LOOM
    expected_version = await get_aiohomematic_version(hass=hass, domain=entry.domain, package_name="aiohomematic")
    # Only block when the installed aiohomematic is OLDER than the version this
    # release was built against. A newer (patch) version is fine and must not
    # abort setup - HA/pip can legitimately resolve a newer aiohomematic than
    # the manifest pin via transitive, upper-bound-less dependencies.
    if (
        not is_loom_backend
        and expected_version is not None
        and AwesomeVersion(HAHM_VERSION) < AwesomeVersion(expected_version)
    ):
        _LOGGER.error(
            "This release of Homematic(IP) Local for OpenCCU requires aiohomematic version %s or newer, "
            "but found the older version %s. "
            "Looks like HA has a problem with dependency management. "
            "This is NOT an issue of the integration.",
            expected_version,
            HAHM_VERSION,
        )
        _LOGGER.warning("Homematic(IP) Local for OpenCCU setup blocked")
        return False
    _LOGGER.debug(
        "Homematic(IP) Local for OpenCCU setup with aiohomematic version %s",
        HAHM_VERSION,
    )

    if AwesomeVersion(HMIP_LOCAL_MIN_HA_VERSION) > HA_VERSION:
        _LOGGER.warning(
            "This release of Homematic(IP) Local for OpenCCU requires HA version %s and above",
            HMIP_LOCAL_MIN_HA_VERSION,
        )
        _LOGGER.warning("HHomematic(IP) Local for OpenCCU setup blocked")
        return False

    # Clean up stale issues from previous sessions
    _cleanup_stale_issues(hass=hass, entry_id=entry.entry_id)

    # For the openccu-loom backend, migrate any legacy aiohomematic entity
    # unique_ids to the canonical loom/serial scheme before entities are
    # (re)created, so existing entities keep their identity on cutover.
    central_id = (entry.unique_id or entry.entry_id)[-10:].lower()
    if is_loom_backend:
        await _async_migrate_loom_unique_ids(hass, entry)
    else:
        # Switched back from loom: strip the loom_ namespace. Then align any
        # legacy entry_id-anchored hub keys onto the CCU-serial scheme.
        await _async_restore_aiohomematic_unique_ids(hass, entry)
        await _async_migrate_aiohomematic_hub_unique_ids(hass, entry)
    # Both backends inherited CUxD keys without the central-id slot; scope them
    # once. Runs after the scheme migrations above so it sees final-shape keys.
    await _async_migrate_cuxd_unique_ids(
        hass, entry, namespace="loom_" if is_loom_backend else "", central_id=central_id
    )
    # Device registry entries keyed on a backend's own interface id move onto
    # the backend-neutral one. Runs before the platforms are forwarded, so no
    # freshly keyed device exists yet and the rename is plain.
    _async_migrate_device_identifiers(hass, entry)

    hass.data.setdefault(HM_KEY, HomematicData())
    if (default_callback_port_xml_rpc := hass.data[HM_KEY].default_callback_port_xml_rpc) is None:
        default_callback_port_xml_rpc = find_free_port()
        hass.data[HM_KEY].default_callback_port_xml_rpc = default_callback_port_xml_rpc

    # Check if this is an initial setup (no devices exist for this entry)
    # If so, enable auto-confirm for new devices during a time window
    device_registry = dr.async_get(hass)
    existing_devices = dr.async_entries_for_config_entry(device_registry, entry.entry_id)
    auto_confirm_until: float | None = None
    if len(existing_devices) == 0:
        auto_confirm_until = time.time() + DEFAULT_AUTO_CONFIRM_NEW_DEVICES_TIMEOUT
        _LOGGER.debug(
            "Initial setup detected for %s. Auto-confirming new devices for %s seconds",
            entry.data.get(CONF_INSTANCE_NAME),
            DEFAULT_AUTO_CONFIRM_NEW_DEVICES_TIMEOUT,
        )

    control = await ControlConfig(
        hass=hass,
        entry_id=entry.entry_id,
        data=entry.data,
        # The config entry's HA unique_id is the CCU serial; inject it so
        # the loom backend keys entities identically to the unique_id
        # registry migration above.
        serial=entry.unique_id,
        auto_confirm_until=auto_confirm_until,
        default_callback_port_xml_rpc=default_callback_port_xml_rpc,
    ).create_control_unit()
    entry.runtime_data = control
    await hass.config_entries.async_forward_entry_setups(entry, HMIP_LOCAL_PLATFORMS)
    try:
        await control.start_central()
    except AuthFailure as err:
        _LOGGER.warning(
            "Authentication failed for %s. Triggering reauthentication flow",
            entry.data.get(CONF_INSTANCE_NAME),
        )
        raise ConfigEntryAuthFailed("Authentication failed") from err
    except _loom_incompatible_version_error() as err:
        # Not a transient failure: the daemon on the other end speaks a
        # contract this build cannot, and retrying reaches the same daemon
        # with the same answer until somebody upgrades one side. Raising
        # ConfigEntryError stops the retry loop and tells the user, where
        # ConfigEntryNotReady would retry forever behind a spinner.
        #
        # Must be caught after AuthFailure and before any handler for the
        # general loom transport error, which it subclasses.
        _LOGGER.error(
            "The openccu-loom daemon for %s is not compatible with this integration: %s",
            entry.data.get(CONF_INSTANCE_NAME),
            err,
        )
        raise ConfigEntryError(str(err)) from err
    if not is_loom_backend:
        await _async_reanchor_hub_unique_ids_on_serial_change(hass, entry, control)
    await async_setup_services(hass)

    # Register WebSocket commands once (HA raises on duplicate registration)
    if not hass.data.get("homematicip_local_ws_registered"):
        async_register_websocket_commands(hass)
        hass.data["homematicip_local_ws_registered"] = True

    # Register device icon proxy view once
    if not hass.data.get(ICON_VIEW_REGISTERED_KEY):
        hass.http.register_view(DeviceIconView)
        hass.data[ICON_VIEW_REGISTERED_KEY] = True

    # Register or unregister the panel per config-entry settings and
    # backend — see _any_entry_has_panel_enabled for what counts.
    if _any_entry_has_panel_enabled(hass=hass):
        await async_register_panel(hass)
    else:
        async_unregister_panel(hass)

    # Register Lovelace cards (always, independent of panel setting)
    await async_register_cards(hass)

    # Register on HA stop event to gracefully shutdown Homematic(IP) Local connection
    hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, control.stop_central)
    entry.async_on_unload(entry.add_update_listener(update_listener))
    async_notify_backup_listeners(hass)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: HomematicConfigEntry) -> bool:
    """Unload a config entry."""
    await async_unload_services(hass)
    # First unload platforms so entities can unsubscribe from events
    # (async_will_remove_from_hass is called for each entity)
    unload_ok = await hass.config_entries.async_unload_platforms(entry, HMIP_LOCAL_PLATFORMS)
    # Then stop the central unit
    if hasattr(entry, "runtime_data") and (control := entry.runtime_data):
        await control.stop_central()
    if len(async_get_loaded_config_entries(hass=hass)) == 0:
        async_unregister_panel(hass)
        async_unregister_cards(hass)
        del hass.data[HM_KEY]
    elif not _any_entry_has_panel_enabled(hass=hass):
        async_unregister_panel(hass)
    async_notify_backup_listeners(hass)
    return unload_ok


async def async_remove_entry(hass: HomeAssistant, entry: HomematicConfigEntry) -> None:
    """Handle removal of an entry."""
    cleanup_files(central_name=entry.data[CONF_INSTANCE_NAME], storage_directory=get_storage_directory(hass=hass))


async def async_remove_config_entry_device(
    hass: HomeAssistant, entry: HomematicConfigEntry, device_entry: dr.DeviceEntry
) -> bool:
    """Remove a config entry from a device."""

    if (device_address := get_device_address_from_identifiers(identifiers=device_entry.identifiers)) is None:
        return False

    # The interface id is read off the device rather than parsed out of the
    # identifier: the identifier is backend-neutral now, while delete_device
    # needs the id the running backend routes on.
    if (control_unit := entry.runtime_data) and (
        hm_device := control_unit.central.device_coordinator.get_device(address=device_address)
    ):
        await control_unit.central.device_coordinator.delete_device(
            interface_id=hm_device.interface_id, device_address=device_address
        )
        _LOGGER.debug(
            "Called delete_device: %s, %s",
            hm_device.interface_id,
            device_address,
        )
    return True


async def update_listener(hass: HomeAssistant, entry: HomematicConfigEntry) -> None:
    """Handle options update."""
    await hass.config_entries.async_reload(entry.entry_id)


def _split_device_identifier(identifier: str) -> tuple[str, str, str] | None:
    """
    Split a device identifier into address, interface and sub-device suffix.

    ``<address>@<central>-<interface>[-<group_no>|-schedule]`` is parsed
    against the ``Interface`` values rather than with a suffix pattern: the
    leading component is a CCU or instance name that may contain anything,
    including a dash and a digit, so only the interface itself is a reliable
    landmark. ``None`` when the identifier carries no separator, no known
    interface, or more than one — the last of which would make the split
    ambiguous (a CCU named after an interface), and is better skipped than
    guessed.
    """
    address, separator, remainder = identifier.partition(IDENTIFIER_SEPARATOR)
    if not separator:
        return None
    matches = [interface for interface in Interface if f"-{interface}" in remainder]
    if len(matches) != 1:
        return None
    interface = matches[0]
    _, _, suffix = remainder.partition(f"-{interface}")
    if suffix and not suffix.startswith("-"):
        # The interface matched inside a longer word rather than as its own
        # trailing component (``…-HmIP-RFX``); not ours to rewrite.
        return None
    return address, str(interface), suffix


@callback
def _async_migrate_device_identifiers(hass: HomeAssistant, entry: HomematicConfigEntry) -> None:
    """
    Move device registry entries onto the backend-neutral identifier.

    Both backends compose ``<address>@<central>-<interface>``, but disagree on
    the leading component: aiohomematic uses the HA instance name, openccu-loom
    the daemon's own CCU name. A backend switch therefore used to leave every
    device entry behind and create a second one beside it — the entities moved
    on (their unique_ids are migrated), the ``device_id`` did not, and with it
    went the area, the custom name and every automation pointing at the device.

    This rewrites those entries onto the neutral key. On the direct-CCU backend
    the neutral key is what aiohomematic already produced, so nothing matches
    and the pass is a no-op.

    Runs before ``async_forward_entry_setups``, where no freshly keyed entry
    exists yet. Two outcomes per entry:

    - the target key is free: a plain rename, the ``device_id`` survives.
    - the target key is taken, which is what a registry looks like after a
      switch that already happened: the entry holding the target is the older
      one, so its entities and children are moved over and the stale entry is
      removed. The older ``device_id`` wins, which is the one automations use.

    Idempotent: an entry already on the neutral key is skipped, so a second
    start migrates nothing.
    """
    instance_name = entry.data[CONF_INSTANCE_NAME]
    device_registry = dr.async_get(hass)
    entity_registry = er.async_get(hass)
    migrated = merged = 0

    for device_entry in list(dr.async_entries_for_config_entry(device_registry, entry.entry_id)):
        for domain, identifier in device_entry.identifiers:
            if domain != DOMAIN:
                continue
            if (parts := _split_device_identifier(identifier)) is None:
                continue
            address, interface, suffix = parts
            new_identifier = f"{address}{IDENTIFIER_SEPARATOR}{instance_name}-{interface}{suffix}"
            if new_identifier == identifier:
                continue
            if (
                existing := device_registry.async_get_device_by_identifier((DOMAIN, new_identifier), entry.entry_id)
            ) is not None:
                if existing.id == device_entry.id:
                    continue
                _LOGGER.info(
                    "Merging device %s into the entry already holding %s, so its device_id survives",
                    identifier,
                    new_identifier,
                )
                for entity_entry in er.async_entries_for_device(
                    entity_registry, device_entry.id, include_disabled_entities=True
                ):
                    entity_registry.async_update_entity(entity_entry.entity_id, device_id=existing.id)
                for child in dr.async_entries_for_config_entry(device_registry, entry.entry_id):
                    if child.via_device_id == device_entry.id:
                        device_registry.async_update_device(child.id, via_device_id=existing.id)
                device_registry.async_remove_device(device_entry.id)
                merged += 1
                break
            _LOGGER.info("Migrating device identifier: %s -> %s", identifier, new_identifier)
            device_registry.async_update_device(device_entry.id, new_identifiers={(DOMAIN, new_identifier)})
            migrated += 1
            break

    if migrated or merged:
        _LOGGER.info(
            "Moved %s device registry entries onto the backend-neutral identifier, merged %s",
            migrated,
            merged,
        )


async def _async_migrate_event_entity_unique_ids(hass: HomeAssistant, entry: HomematicConfigEntry) -> None:
    """Migrate event entity unique_ids from channel-based to event_group-based format."""

    @callback
    def update_event_entity_unique_id(entity_entry: er.RegistryEntry) -> dict[str, str] | None:
        """Update unique ID of event entity entry."""
        # Only migrate event platform entities
        if entity_entry.domain != "event":
            return None
        # Check if this is an old-format unique_id (doesn't contain "event_group_")
        if "event_group_" in entity_entry.unique_id:
            return None
        # Extract the channel unique_id part after the domain prefix
        prefix = f"{DOMAIN}_"
        if not entity_entry.unique_id.startswith(prefix):
            return None
        channel_unique_id = entity_entry.unique_id[len(prefix) :]
        # Create new unique_id with event_group format (default to keypress)
        new_unique_id = f"{DOMAIN}_event_group_keypress_{channel_unique_id}"
        _LOGGER.debug(
            "Migrating event entity unique_id: %s -> %s",
            entity_entry.unique_id,
            new_unique_id,
        )
        return {"new_unique_id": new_unique_id}

    await async_migrate_entries(hass, entry.entry_id, update_event_entity_unique_id)


def _loom_migrated_unique_id(unique_id: str, *, entry_suffix: str, serial_suffix: str) -> str | None:
    """Map a legacy aiohomematic HA ``unique_id`` to the loom/serial scheme.

    HA stores ``{DOMAIN}_<routing-key>``. The openccu-loom backend keys its
    data points with the canonical ``loom_<routing-key>`` (the CCU serial
    suffix fills the central-id slot of hub / internal / virtual-remote
    keys, replacing aiohomematic's ``entry_id[-10:]`` prefix). This rewrites
    the legacy key to the loom one; see openccu-loom
    ``docs/external-clients/ha-unique-id-migration.md``.

    Returns ``None`` when no rewrite applies: already migrated, not one of
    our entities, or a synthetic entity that is not a data-point routing key
    (the per-central backup button, and the legacy event-group entities the
    loom backend does not emit yet — those are out of scope here).
    """
    prefix = f"{DOMAIN}_"
    if not unique_id.startswith(prefix):
        return None
    key = unique_id[len(prefix) :]
    if key.startswith("loom_"):  # idempotent
        return None
    if key.endswith("_create_backup") or key.startswith("event_group_"):
        return None
    if key.startswith("openccu-loom_"):
        # Daemon-computed ids (the alarm panels: ``openccu-loom_alarm_<area>``)
        # are deliberately NOT loom_-routing-scheme keys and never existed on
        # the CCU backend — there is nothing legacy to migrate. Prefixing them
        # orphaned the live entity and crash-looped setup once the correctly
        # keyed duplicate spawned (repaired in _async_migrate_loom_unique_ids).
        return None
    # Hub / internal / virtual-remote keys carried the entry_id suffix as
    # their prefix; swap it for the CCU serial suffix. Everything else
    # (devices, channels, custom DPs) carried no central prefix.
    entry_prefix = f"{entry_suffix}_"
    if key.startswith(entry_prefix):
        return f"{prefix}loom_{serial_suffix}_{key[len(entry_prefix) :]}"
    return f"{prefix}loom_{key}"


# A CUxD serial is ``CUX`` + a two-digit device type + a five-digit running
# number, so ``CUX2801001`` — the first "(28) System" device on essentially
# every install. The shape is what makes the family recognisable in a routing
# key regardless of what prefix precedes it (``calculated_``,
# ``week_profile_``, ``schedule_channel_switch_``).
_CUXD_KEY = re.compile(r"(?:^|_)cux\d{7}(?:_|$)")


def _cuxd_scoped_unique_id(unique_id: str, *, namespace: str, central_id: str) -> str | None:
    """Insert the central-id slot into a CUxD routing key, or ``None`` if not needed.

    CUxD hands out the same synthetic addresses on every CCU, so two CCUs
    bridged into one Home Assistant declared byte-identical unique_ids for
    their CUxD data points and HA kept only the first. aiohomematic 2026.8.7
    scopes the family by central id, as the daemon always had; every CUxD
    entity keyed before that adoption therefore has to move once.

    ``namespace`` is ``"loom_"`` on the openccu-loom backend and ``""`` on the
    direct-CCU one — the loom scheme carries the serial *after* its namespace
    (``loom_<serial>_cux…``) while aiohomematic carries the central id at the
    front (``<central>_cux…``).

    Idempotent: a key already carrying the slot is left alone, so this is safe
    on every setup rather than only the first after the upgrade.
    """
    prefix = f"{DOMAIN}_"
    if not unique_id.startswith(prefix):
        return None
    key = unique_id[len(prefix) :]
    if namespace:
        if not key.startswith(namespace):
            return None
        key = key[len(namespace) :]
    elif key.startswith("loom_"):
        # A loom key on the direct-CCU path is not ours to touch here.
        return None
    if not _CUXD_KEY.search(key):
        return None
    if key.startswith(f"{central_id}_"):  # already scoped
        return None
    return f"{prefix}{namespace}{central_id}_{key}"


async def _async_migrate_cuxd_unique_ids(
    hass: HomeAssistant, entry: HomematicConfigEntry, *, namespace: str, central_id: str
) -> None:
    """Scope CUxD entity unique_ids by the central id, once.

    Runs on both backends, because both inherited the unscoped key: the daemon
    always scoped CUxD, but the openccu-loom client rebuilds the keys the
    daemon does not stamp — custom data points, week profiles, the combined
    duration number, the device-update entity, event groups — through
    aiohomematic, and aiohomematic did not scope them until 2026.8.7. On the
    direct-CCU backend every CUxD entity is affected.

    Without this the entities orphan: they keep their history, area and
    customisations in the registry while the platform spawns freshly keyed
    duplicates beside them, and the orphan-cleanup sweep eventually deletes
    the originals. An installation with no CUxD devices sees nothing happen.
    """
    if not central_id:
        return
    entity_registry = er.async_get(hass)

    @callback
    def _migrator(entity_entry: er.RegistryEntry) -> dict[str, str] | None:
        new_unique_id = _cuxd_scoped_unique_id(entity_entry.unique_id, namespace=namespace, central_id=central_id)
        if new_unique_id is None or new_unique_id == entity_entry.unique_id:
            return None
        # HA raises on a duplicate unique_id, which would abort the whole
        # migration and fail setup — skip instead (same guard as the other
        # passes). The duplicate is the one without history; it loses.
        if entity_registry.async_get_entity_id(entity_entry.domain, entity_entry.platform, new_unique_id):
            _LOGGER.warning(
                "Skipping CUxD unique_id migration, target already exists: %s -> %s",
                entity_entry.unique_id,
                new_unique_id,
            )
            return None
        _LOGGER.info(
            "Scoping CUxD unique_id by central: %s -> %s",
            entity_entry.unique_id,
            new_unique_id,
        )
        return {"new_unique_id": new_unique_id}

    await async_migrate_entries(hass, entry.entry_id, _migrator)


async def _async_migrate_loom_unique_ids(hass: HomeAssistant, entry: HomematicConfigEntry) -> None:
    """Rewrite legacy entity unique_ids to the loom/serial scheme.

    Runs once, early in setup, for the openccu-loom backend. A config entry
    switched from the CCU backend still holds aiohomematic-era keys in the
    entity registry; the loom backend produces canonical ``loom_`` keys, so
    without this rewrite every entity would orphan (losing history, area and
    customisations). The rewrite is purely string-level, idempotent, and
    scoped to this entry, so it is safe to run on every setup.
    """
    serial = entry.unique_id  # the config entry's HA unique_id is the CCU serial
    if not serial:
        _LOGGER.warning(
            "Skipping loom unique_id migration for %s: config entry has no serial",
            entry.data.get(CONF_INSTANCE_NAME),
        )
        return
    entry_suffix = entry.entry_id[-10:]
    serial_suffix = serial[-10:].lower()
    entity_registry = er.async_get(hass)

    # Repair the damage a pre-fix sweep did to alarm panels: it treated the
    # daemon-computed ``openccu-loom_alarm_<area>`` ids as legacy keys and
    # prefixed ``loom_`` — orphaning the original entity (which keeps the
    # user's entity_id, history, area and customisations) and crash-looping
    # setup with "unique id already in use" once the platform had spawned a
    # correctly keyed duplicate. Strip the wrong prefix back off; a duplicate
    # spawned in the meantime loses (it is the one without history).
    wrong_prefix = f"{DOMAIN}_loom_openccu-loom_"
    for entity_entry in list(er.async_entries_for_config_entry(entity_registry, entry.entry_id)):
        if not entity_entry.unique_id.startswith(wrong_prefix):
            continue
        corrected = f"{DOMAIN}_openccu-loom_{entity_entry.unique_id[len(wrong_prefix) :]}"
        duplicate_id = entity_registry.async_get_entity_id(entity_entry.domain, entity_entry.platform, corrected)
        if duplicate_id is not None and duplicate_id != entity_entry.entity_id:
            _LOGGER.warning(
                "Removing duplicate %s so %s can reclaim its unique_id %s",
                duplicate_id,
                entity_entry.entity_id,
                corrected,
            )
            entity_registry.async_remove(duplicate_id)
        _LOGGER.warning(
            "Repairing wrongly migrated alarm-panel unique_id: %s -> %s",
            entity_entry.unique_id,
            corrected,
        )
        entity_registry.async_update_entity(entity_entry.entity_id, new_unique_id=corrected)

    @callback
    def _migrator(entity_entry: er.RegistryEntry) -> dict[str, str] | None:
        new_unique_id = _loom_migrated_unique_id(
            entity_entry.unique_id,
            entry_suffix=entry_suffix,
            serial_suffix=serial_suffix,
        )
        if new_unique_id is None or new_unique_id == entity_entry.unique_id:
            return None
        # HA raises on a duplicate unique_id, which would abort the whole
        # migration and fail the config-entry setup — skip instead (same
        # guard as _async_realign_hub_unique_ids).
        if entity_registry.async_get_entity_id(entity_entry.domain, entity_entry.platform, new_unique_id):
            _LOGGER.warning(
                "Skipping loom unique_id migration, target already exists: %s -> %s",
                entity_entry.unique_id,
                new_unique_id,
            )
            return None
        _LOGGER.debug(
            "Migrating unique_id to loom scheme: %s -> %s",
            entity_entry.unique_id,
            new_unique_id,
        )
        return {"new_unique_id": new_unique_id}

    await async_migrate_entries(hass, entry.entry_id, _migrator)


def _aiohomematic_restored_unique_id(unique_id: str) -> str | None:
    """Strip the ``loom_`` namespace from an HA ``unique_id``.

    The inverse of :func:`_loom_migrated_unique_id`. Both backends now anchor
    hub / internal / virtual-remote entities on the CCU serial (see
    ``central_id`` in :mod:`.control_unit`), so the two schemes differ only by
    the ``loom_`` namespace and restoring a key is a plain prefix strip — the
    serial-anchored central-id slot is already correct, no swap needed.

    Returns ``None`` when no rewrite applies: not one of our entities, or
    already in the aiohomematic scheme (no ``loom_`` namespace).
    """
    prefix = f"{DOMAIN}_"
    if not unique_id.startswith(prefix):
        return None
    key = unique_id[len(prefix) :]
    if not key.startswith("loom_"):  # idempotent: already aiohomematic-scheme
        return None
    body = key[len("loom_") :]
    return f"{prefix}{body}"


async def _async_restore_aiohomematic_unique_ids(hass: HomeAssistant, entry: HomematicConfigEntry) -> None:
    """Rewrite loom entity unique_ids back to the aiohomematic scheme.

    Runs once, early in setup, for the aiohomematic backend. A config entry
    switched back from the openccu-loom backend still holds canonical
    ``loom_`` keys in the entity registry; aiohomematic produces un-namespaced
    keys, so without this rewrite every entity would orphan (losing history,
    area and customisations). The inverse of
    :func:`_async_migrate_loom_unique_ids`, it is purely string-level,
    idempotent, and scoped to this entry, so it is safe to run on every setup.
    """

    entity_registry = er.async_get(hass)

    @callback
    def _migrator(entity_entry: er.RegistryEntry) -> dict[str, str] | None:
        new_unique_id = _aiohomematic_restored_unique_id(entity_entry.unique_id)
        if new_unique_id is None or new_unique_id == entity_entry.unique_id:
            return None
        # HA raises on a duplicate unique_id, which would abort the whole
        # migration and fail the config-entry setup — skip instead (same
        # guard as _async_realign_hub_unique_ids).
        if entity_registry.async_get_entity_id(entity_entry.domain, entity_entry.platform, new_unique_id):
            _LOGGER.warning(
                "Skipping aiohomematic unique_id restore, target already exists: %s -> %s",
                entity_entry.unique_id,
                new_unique_id,
            )
            return None
        _LOGGER.debug(
            "Restoring unique_id to aiohomematic scheme: %s -> %s",
            entity_entry.unique_id,
            new_unique_id,
        )
        return {"new_unique_id": new_unique_id}

    await async_migrate_entries(hass, entry.entry_id, _migrator)


async def _async_realign_hub_unique_ids(hass: HomeAssistant, entry: HomematicConfigEntry, *, central_id: str) -> None:
    """Force the central-id slot of every hub / virtual-remote registry key onto ``central_id``.

    Entry-scoped, idempotent and collision-safe. Hub / install-mode / program /
    sysvar / internal / virtual-remote keys (and the virtual-remote event groups)
    carry a central-id slot; this rewrites whatever value sits there onto the live
    ``central_id`` regardless of the old value, so a registry inherited from an
    earlier anchor (legacy ``entry_id[-10:]``, a prior serial, or a stale slot from
    a delete + re-add) realigns onto the live key instead of orphaning and being
    deleted by the orphan-cleanup sweep. Device / channel / custom-DP keys carry no
    slot and are left untouched.
    """
    entity_registry = er.async_get(hass)

    @callback
    def _migrator(entity_entry: er.RegistryEntry) -> dict[str, str] | None:
        new_unique_id = realign_hub_unique_id(entity_entry.unique_id, central_id=central_id)
        if new_unique_id is None or new_unique_id == entity_entry.unique_id:
            return None
        # A live-anchored entry may already exist (e.g. created under the live
        # anchor by an earlier setup); HA raises on a duplicate unique_id, so skip
        # rather than abort the whole migration.
        if entity_registry.async_get_entity_id(entity_entry.domain, entity_entry.platform, new_unique_id):
            _LOGGER.debug(
                "Skipping hub unique_id realign, target already exists: %s -> %s",
                entity_entry.unique_id,
                new_unique_id,
            )
            return None
        _LOGGER.debug(
            "Realigning hub unique_id onto the live central id: %s -> %s",
            entity_entry.unique_id,
            new_unique_id,
        )
        return {"new_unique_id": new_unique_id}

    await async_migrate_entries(hass, entry.entry_id, _migrator)


async def _async_migrate_aiohomematic_hub_unique_ids(hass: HomeAssistant, entry: HomematicConfigEntry) -> None:
    """Realign hub / virtual-remote unique_ids onto the live central id.

    aiohomematic anchors hub / sysvar / program / install-mode / internal /
    virtual-remote entities (and their event groups) on the central id — the CCU
    serial when known, else ``entry_id[-10:]`` (see ``central_id`` in
    :mod:`.control_unit`). A registry inherited from a different anchor (legacy
    ``entry_id``-prefixed keys, or a stale slot left by a delete + re-add) would
    otherwise no longer match the live keys, orphan, and be permanently deleted by
    the orphan-cleanup sweep. This one-time, entry-scoped, collision-safe rewrite
    runs early in setup, before entities are (re)created, and is a no-op once
    everything is on the live anchor. Device / channel keys carry no central slot
    and are left untouched.
    """
    central_id = (entry.unique_id or entry.entry_id)[-10:].lower()
    await _async_realign_hub_unique_ids(hass, entry, central_id=central_id)


async def _async_reanchor_hub_unique_ids_on_serial_change(
    hass: HomeAssistant, entry: HomematicConfigEntry, control: ControlUnit
) -> None:
    """Re-anchor hub unique_ids when the connected CCU serial has changed.

    The CCU serial (read from the radio module) anchors hub / sysvar /
    program / install-mode / internal / virtual-remote unique_ids and the
    config-entry identity. It is stable in normal operation but changes on a
    radio-module (Funkmodul) swap. When the freshly-connected serial differs
    from the stored one, this realigns those keys onto the new serial, updates
    the entry's unique_id and reloads so the running central rebuilds on the new
    anchor. A no-op when the serial is unchanged or unknown.
    """
    old_serial = entry.unique_id
    new_serial = control.central.system_information.serial
    if not old_serial or not new_serial or new_serial.lower() == "unknown":
        return
    if new_serial.lower() == old_serial.lower():
        return

    _LOGGER.warning(
        "CCU serial for %s changed (%s -> %s); re-anchoring hub entities and reloading",
        entry.data.get(CONF_INSTANCE_NAME),
        old_serial,
        new_serial,
    )
    await _async_realign_hub_unique_ids(hass, entry, central_id=new_serial[-10:].lower())
    hass.config_entries.async_update_entry(entry, unique_id=new_serial)
    hass.config_entries.async_schedule_reload(entry.entry_id)


def _migrate_v11_extract_custom_ports(data: dict[str, Any]) -> dict[str, Any]:
    """Extract custom (non-default) ports from v11 config entry data."""
    custom_ports: dict[str, int] = {}
    if interfaces := data.get(CONF_INTERFACE):
        for interface_key, interface_config in interfaces.items():
            if isinstance(interface_config, dict) and CONF_PORT in interface_config:
                port = interface_config[CONF_PORT]
                # Get interface name - could be enum or string key
                interface_name = interface_key.value if hasattr(interface_key, "value") else str(interface_key)
                # Check if port is non-default (custom)
                if not is_interface_default_port(interface=interface_name, port=port):
                    custom_ports[interface_name] = port
    # Only add CONF_CUSTOM_PORTS if there are custom ports
    if custom_ports:
        data[CONF_CUSTOM_PORTS] = custom_ports
    return data


def _migrate_v14_remove_deprecated_optional_settings(data: dict[str, Any]) -> dict[str, Any]:
    """Remove deprecated OptionalSettings values from v14 config entry data."""
    # Remove deprecated OptionalSettings values that were removed in aiohomematic 2026.1.44
    # - ENABLE_LINKED_ENTITY_CLIMATE_ACTIVITY (now always enabled)
    # - USE_INTERFACE_CLIENT (legacy client removed)
    if CONF_ADVANCED_CONFIG in data and CONF_OPTIONAL_SETTINGS in data[CONF_ADVANCED_CONFIG]:
        valid_settings = {str(s) for s in OptionalSettings}
        current_settings = data[CONF_ADVANCED_CONFIG][CONF_OPTIONAL_SETTINGS]
        filtered_settings = [s for s in current_settings if s in valid_settings]
        if filtered_settings != current_settings:
            data[CONF_ADVANCED_CONFIG] = dict(data[CONF_ADVANCED_CONFIG])
            data[CONF_ADVANCED_CONFIG][CONF_OPTIONAL_SETTINGS] = filtered_settings
    return data


def _migrate_v1_to_v2_data(data: dict[str, Any]) -> dict[str, Any]:
    """Migrate config entry data from v1 to v2: enable system notifications by default."""
    data[CONF_ENABLE_SYSTEM_NOTIFICATIONS] = True
    return data


def _migrate_v3_to_v4_data(data: dict[str, Any]) -> dict[str, Any]:
    """Migrate config entry data from v3 to v4: introduce un-ignores list."""
    data[CONF_UN_IGNORES] = []
    return data


def _migrate_v6_to_v7_data(data: dict[str, Any]) -> dict[str, Any]:
    """Migrate config entry data from v6 to v7: derive program scan from sysvar scan."""
    if data.get(CONF_ADVANCED_CONFIG):
        data[CONF_ADVANCED_CONFIG][CONF_ENABLE_PROGRAM_SCAN] = data[CONF_ADVANCED_CONFIG][CONF_ENABLE_SYSVAR_SCAN]
    return data


def _migrate_v2_unique_id(entry: HomematicConfigEntry) -> Callable[[er.RegistryEntry], dict[str, str] | None]:
    """Return entity-id migration callback used by v2->v3."""

    @callback
    def update_entity_unique_id(entity_entry: er.RegistryEntry) -> dict[str, str] | None:
        """Update unique ID of entity entry."""
        if entity_entry.unique_id.startswith(f"{DOMAIN}_bidcos_wir"):
            return {
                "new_unique_id": entity_entry.unique_id.replace(
                    f"{DOMAIN}_bidcos_wir",
                    f"{DOMAIN}_{entry.unique_id}_bidcos_wir",
                )
            }
        return None

    return update_entity_unique_id


def _migrate_v4_to_v5_data(data: dict[str, Any]) -> dict[str, Any]:
    """Migrate config entry data from v4 to v5: collapse advanced settings and drop legacy keys."""
    advanced_config = {
        CONF_ENABLE_SYSVAR_SCAN: data.get(CONF_ENABLE_SYSVAR_SCAN, DEFAULT_ENABLE_SYSVAR_SCAN),
        CONF_SYS_SCAN_INTERVAL: data.get(CONF_SYS_SCAN_INTERVAL, DEFAULT_SYS_SCAN_INTERVAL),
        CONF_ENABLE_SYSTEM_NOTIFICATIONS: data.get(
            CONF_ENABLE_SYSTEM_NOTIFICATIONS, DEFAULT_ENABLE_SYSTEM_NOTIFICATIONS
        ),
        CONF_UN_IGNORES: data.get(CONF_UN_IGNORES, DEFAULT_UN_IGNORES),
    }
    default_advanced_config = {
        CONF_ENABLE_SYSVAR_SCAN: DEFAULT_ENABLE_SYSVAR_SCAN,
        CONF_SYS_SCAN_INTERVAL: DEFAULT_SYS_SCAN_INTERVAL,
        CONF_ENABLE_SYSTEM_NOTIFICATIONS: DEFAULT_ENABLE_SYSTEM_NOTIFICATIONS,
        CONF_UN_IGNORES: DEFAULT_UN_IGNORES,
    }
    data[CONF_ADVANCED_CONFIG] = {} if advanced_config == default_advanced_config else advanced_config

    for key in (CONF_ENABLE_SYSVAR_SCAN, CONF_SYS_SCAN_INTERVAL, CONF_ENABLE_SYSTEM_NOTIFICATIONS, CONF_UN_IGNORES):
        with contextlib.suppress(KeyError):
            del data[key]

    return data


def _migrate_v9_to_v10_data(data: dict[str, Any]) -> dict[str, Any]:
    """Migrate config entry data from v9 to v10: rename callback_port to CONF_CALLBACK_PORT_XML_RPC."""
    if callback_port_xml_rpc := data.get("callback_port"):
        with contextlib.suppress(KeyError):
            del data["callback_port"]
        data[CONF_CALLBACK_PORT_XML_RPC] = callback_port_xml_rpc
    return data


def _migrate_v10_to_v11_data(data: dict[str, Any]) -> dict[str, Any]:
    """Migrate config entry data from v10 to v11: drop delay_new_device_creation."""
    if CONF_ADVANCED_CONFIG in data:
        with contextlib.suppress(KeyError):
            del data[CONF_ADVANCED_CONFIG]["delay_new_device_creation"]
    return data


def _migrate_v12_to_v13_data(data: dict[str, Any]) -> dict[str, Any]:
    """Migrate config entry data from v12 to v13: drop action_select_values from entry data."""
    with contextlib.suppress(KeyError):
        del data[CONF_ACTION_SELECT_VALUES]
    return data


def _migrate_v15_to_v16_data(data: dict[str, Any]) -> dict[str, Any]:
    """Migrate config entry data from v15 to v16: introduce command throttle interval default."""
    if CONF_ADVANCED_CONFIG in data:
        data[CONF_ADVANCED_CONFIG][CONF_COMMAND_THROTTLE_INTERVAL] = DEFAULT_COMMAND_THROTTLE_INTERVAL
    return data


def _migrate_v16_to_v17_data(data: dict[str, Any]) -> dict[str, Any]:
    """Migrate config entry data from v16 to v17: drop legacy enable_config_panel key."""
    if CONF_ADVANCED_CONFIG in data:
        # Panel is now enabled by default
        data[CONF_ADVANCED_CONFIG].pop("enable_config_panel", None)
    return data


# Dispatch table for pure data-only migrations (no hass / async work).
# Each entry maps from-version -> data transformer. The to-version is always from + 1.
_DATA_MIGRATIONS: dict[int, Callable[[dict[str, Any]], dict[str, Any]]] = {
    1: _migrate_v1_to_v2_data,
    3: _migrate_v3_to_v4_data,
    6: _migrate_v6_to_v7_data,
    9: _migrate_v9_to_v10_data,
    10: _migrate_v10_to_v11_data,
    11: _migrate_v11_extract_custom_ports,
    12: _migrate_v12_to_v13_data,
    14: _migrate_v14_remove_deprecated_optional_settings,
    15: _migrate_v15_to_v16_data,
    16: _migrate_v16_to_v17_data,
}

# Versions whose only side effect is calling cleanup_files() before bumping the version.
_CLEANUP_FILE_VERSIONS = frozenset({5, 7, 8})


async def async_migrate_entry(hass: HomeAssistant, entry: HomematicConfigEntry) -> bool:
    """Migrate old entry."""
    _LOGGER.debug("Migrating from version %s", entry.version)

    while entry.version < 17:
        version = entry.version
        if migrator := _DATA_MIGRATIONS.get(version):
            data = migrator(dict(entry.data))
            hass.config_entries.async_update_entry(entry, version=version + 1, data=data)
        elif version in _CLEANUP_FILE_VERSIONS:
            cleanup_files(
                central_name=entry.data[CONF_INSTANCE_NAME], storage_directory=get_storage_directory(hass=hass)
            )
            hass.config_entries.async_update_entry(entry, version=version + 1, data=dict(entry.data))
        elif version == 2:
            await async_migrate_entries(hass, entry.entry_id, _migrate_v2_unique_id(entry))
            hass.config_entries.async_update_entry(entry, version=3)
        elif version == 4:
            data = _migrate_v4_to_v5_data(data=dict(entry.data))
            cleanup_files(
                central_name=entry.data[CONF_INSTANCE_NAME], storage_directory=get_storage_directory(hass=hass)
            )
            hass.config_entries.async_update_entry(entry, version=5, data=data)
        elif version == 13:
            # Migrate event entity unique_ids from channel-based to event_group-based format
            await _async_migrate_event_entity_unique_ids(hass=hass, entry=entry)
            hass.config_entries.async_update_entry(entry, version=14)
        else:
            break  # Unknown version - stop migrating to avoid infinite loop

    _LOGGER.info("Migration to version %s successful", entry.version)
    return True
