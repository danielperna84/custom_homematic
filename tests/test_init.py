"""Test the Homematic(IP) Local for OpenCCU init."""

from __future__ import annotations

from collections.abc import Iterator
from datetime import datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from aiohomematic.central.events import SystemStatusChangedEvent
from aiohomematic.const import IDENTIFIER_SEPARATOR, CentralState, DeviceTriggerEventType
from aiohomematic.exceptions import AuthFailure
import custom_components.homematicip_local
from custom_components.homematicip_local import (
    _aiohomematic_restored_unique_id,
    _async_migrate_aiohomematic_hub_unique_ids,
    _async_migrate_cuxd_unique_ids,
    _async_migrate_device_identifiers,
    _async_migrate_loom_unique_ids,
    _async_reanchor_hub_unique_ids_on_serial_change,
    _async_restore_aiohomematic_unique_ids,
    _cleanup_stale_issues,
    _cuxd_scoped_unique_id,
    _loom_migrated_unique_id,
)
from custom_components.homematicip_local.config_flow import DomainConfigFlow
from custom_components.homematicip_local.const import (
    BACKEND_CCU,
    BACKEND_LOOM,
    CONF_ADVANCED_CONFIG,
    CONF_OPTIONAL_SETTINGS,
    DOMAIN as HMIP_DOMAIN,
    ISSUE_TYPE_CALLBACK,
    ISSUE_TYPE_CLIENT,
    ISSUE_TYPE_CONNECTION,
)
from custom_components.homematicip_local.control_unit import ControlUnit, hub_key_from_name_slug
from custom_components.homematicip_local.support import get_issue_id, realign_hub_unique_id
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er, issue_registry as ir

from tests import const


class TestSweepSparesUnmigratedHubKeys:
    """A pre-id sysvar / program key is not an orphan while its data point is live.

    The slug-to-id migration runs just before this sweep, in the same callback.
    When it does not take — ``get_hub_data_points()`` raised, or a data point
    yielded no old key — the historied entry keeps the slug, and without this
    exemption the sweep reads it as an orphan (no device address, so
    ``_is_orphan_registry_entry`` falls through to ``True``) and deletes it with
    its history, name and area. Keeping it costs one more start; deleting it is
    permanent.
    """

    _SERIAL = "11a0001234"

    @staticmethod
    def _seed(hass: HomeAssistant, entry: MockConfigEntry, *, unique_id: str) -> er.RegistryEntry:
        return er.async_get(hass).async_get_or_create(
            domain="sensor",
            platform=HMIP_DOMAIN,
            unique_id=f"{HMIP_DOMAIN}_{unique_id}",
            config_entry=entry,
        )

    async def test_a_slug_key_with_no_live_data_point_is_still_swept(
        self, hass: HomeAssistant, mock_config_entry_v2: MockConfigEntry
    ) -> None:
        """The exemption is narrow: it spares only keys a live data point claims.

        Negative control for the test above — without it, that one would pass
        just as well if the sweep had stopped removing hub entries altogether.
        """
        mock_config_entry_v2.add_to_hass(hass)
        alive = self._seed(hass, mock_config_entry_v2, unique_id="alive_dp")
        gone = self._seed(hass, mock_config_entry_v2, unique_id=f"loom_{self._SERIAL}_sysvar_geloeschte-variable")

        fake_self = _build_orphan_sweep_self(
            hass,
            mock_config_entry_v2.entry_id,
            data_point_unique_ids=("alive_dp",),
            named_hub_data_points=((f"loom_{self._SERIAL}_sysvar_12345", "Außen Temperatur"),),
        )
        ControlUnit._async_cleanup_orphaned_entity_registry_entries(fake_self)

        entity_registry = er.async_get(hass)
        assert entity_registry.async_get(alive.entity_id) is not None
        assert entity_registry.async_get(gone.entity_id) is None

    async def test_slug_keyed_entry_survives_while_its_data_point_is_live(
        self, hass: HomeAssistant, mock_config_entry_v2: MockConfigEntry
    ) -> None:
        """The entry the migration has yet to rename is kept, not swept."""
        mock_config_entry_v2.add_to_hass(hass)
        alive = self._seed(hass, mock_config_entry_v2, unique_id="alive_dp")
        unmigrated = self._seed(hass, mock_config_entry_v2, unique_id=f"loom_{self._SERIAL}_sysvar_aussen-temperatur")

        fake_self = _build_orphan_sweep_self(
            hass,
            mock_config_entry_v2.entry_id,
            data_point_unique_ids=("alive_dp",),
            named_hub_data_points=((f"loom_{self._SERIAL}_sysvar_12345", "Außen Temperatur"),),
        )
        ControlUnit._async_cleanup_orphaned_entity_registry_entries(fake_self)

        entity_registry = er.async_get(hass)
        assert entity_registry.async_get(alive.entity_id) is not None
        assert entity_registry.async_get(unmigrated.entity_id) is not None


class TestSetupEntry:
    """Tests for setup entry functionality."""

    async def test_setup_entry(
        self,
        hass: HomeAssistant,
        mock_config_entry_v2: MockConfigEntry,
        mock_control_unit: ControlUnit,
    ) -> None:
        """Test setup entry."""
        # no config_entry exists
        assert len(hass.config_entries.async_entries(HMIP_DOMAIN)) == 0
        assert not hass.data.get(HMIP_DOMAIN)

        with (
            patch("custom_components.homematicip_local.find_free_port", return_value=8765),
            patch(
                "custom_components.homematicip_local.control_unit.ControlConfig.create_control_unit",
                return_value=mock_control_unit,
            ),
        ):
            mock_config_entry_v2.add_to_hass(hass)
            await hass.config_entries.async_setup(mock_config_entry_v2.entry_id)
            await hass.async_block_till_done()
            config_entries = hass.config_entries.async_entries(HMIP_DOMAIN)
            assert len(config_entries) == 1
            config_entry = config_entries[0]
            assert config_entry.state == ConfigEntryState.LOADED

    async def test_setup_entry_auth_failure(
        self,
        hass: HomeAssistant,
        mock_config_entry_v2: MockConfigEntry,
        mock_control_unit: ControlUnit,
    ) -> None:
        """Test setup entry with authentication failure triggers reauth."""
        # Configure mock to raise AuthFailure during start_central
        mock_control_unit.start_central = AsyncMock(side_effect=AuthFailure("Invalid credentials"))

        with (
            patch("custom_components.homematicip_local.find_free_port", return_value=8765),
            patch(
                "custom_components.homematicip_local.control_unit.ControlConfig.create_control_unit",
                return_value=mock_control_unit,
            ),
        ):
            mock_config_entry_v2.add_to_hass(hass)

            # Setup should fail with auth error
            result = await hass.config_entries.async_setup(mock_config_entry_v2.entry_id)
            await hass.async_block_till_done()

            # Verify setup failed and entry is in SETUP_ERROR state
            assert result is False
            assert mock_config_entry_v2.state == ConfigEntryState.SETUP_ERROR

            # Verify a reauth flow was triggered via the repair issue
            from homeassistant.helpers import issue_registry as ir

            issue_reg = ir.async_get(hass)
            issue = issue_reg.async_get_issue(
                domain="homeassistant",
                issue_id=f"config_entry_reauth_{HMIP_DOMAIN}_{mock_config_entry_v2.entry_id}",
            )
            assert issue is not None
            assert issue.translation_key == "config_entry_reauth"


class TestCheckMinVersion:
    """Tests for minimum version check."""

    async def test_check_min_version(
        self,
        hass: HomeAssistant,
        mock_config_entry_v2: MockConfigEntry,
        mock_control_unit: ControlUnit,
    ) -> None:
        """Test check_min_version."""
        # no config_entry exists

        orig_version = custom_components.homematicip_local.HMIP_LOCAL_MIN_HA_VERSION
        custom_components.homematicip_local.HMIP_LOCAL_MIN_HA_VERSION = "2099.1.1"
        mock_config_entry_v2.add_to_hass(hass)
        assert await hass.config_entries.async_setup(mock_config_entry_v2.entry_id) is False
        custom_components.homematicip_local.HMIP_LOCAL_MIN_HA_VERSION = orig_version


class TestMigrateEntry:
    """Tests for entry migration."""

    async def test_migrate_entry(
        self,
        hass: HomeAssistant,
        mock_config_entry_v1: MockConfigEntry,
        mock_control_unit: ControlUnit,
    ) -> None:
        """Test setup entry."""
        # no config_entry exists
        assert len(hass.config_entries.async_entries(HMIP_DOMAIN)) == 0
        assert not hass.data.get(HMIP_DOMAIN)

        with (
            patch("custom_components.homematicip_local.find_free_port", return_value=8765),
            patch(
                "custom_components.homematicip_local.control_unit.ControlConfig.create_control_unit",
                return_value=mock_control_unit,
            ),
        ):
            mock_config_entry_v1.add_to_hass(hass)
            await hass.config_entries.async_setup(mock_config_entry_v1.entry_id)
            await hass.async_block_till_done()
            config_entries = hass.config_entries.async_entries(HMIP_DOMAIN)
            assert len(config_entries) == 1
            config_entry = config_entries[0]
            assert config_entry.state == ConfigEntryState.LOADED
            assert config_entry.version == DomainConfigFlow.VERSION
            assert config_entry.data[CONF_ADVANCED_CONFIG] == {
                "command_throttle_interval": 0.1,
                "enable_system_notifications": True,
                "program_scan_enabled": False,
                "sysvar_scan_enabled": False,
                "sysvar_scan_interval": 30,
                "un_ignore": [],
            }

    async def test_migrate_entry_v14_removes_deprecated_optional_settings(
        self,
        hass: HomeAssistant,
        mock_control_unit: ControlUnit,
    ) -> None:
        """Test migration from v14 removes deprecated OptionalSettings values."""
        # Create a v14 config entry with deprecated optional settings
        entry_data = {
            "instance_name": const.INSTANCE_NAME,
            "host": const.HOST,
            "username": const.USERNAME,
            "password": const.PASSWORD,
            "tls": False,
            "verify_tls": False,
            "interface": {"HmIP-RF": {"port": 2010}},
            "advanced_config": {
                "enable_system_notifications": True,
                "sysvar_scan_enabled": False,
                "sysvar_scan_interval": 30,
                "program_scan_enabled": False,
                "un_ignore": [],
                # Deprecated values that should be removed
                "optional_settings": [
                    "ENABLE_LINKED_ENTITY_CLIMATE_ACTIVITY",
                    "USE_INTERFACE_CLIENT",
                    "SR_DISABLE_RANDOMIZED_OUTPUT",  # Valid - should be kept
                ],
            },
        }

        mock_config_entry_v14 = MockConfigEntry(
            entry_id=const.CONFIG_ENTRY_ID,
            version=14,
            domain=HMIP_DOMAIN,
            title=const.INSTANCE_NAME,
            data=entry_data,
            options={},
            pref_disable_new_entities=False,
            pref_disable_polling=False,
            source="user",
            unique_id=const.CONFIG_ENTRY_UNIQUE_ID,
            disabled_by=None,
        )

        with (
            patch("custom_components.homematicip_local.find_free_port", return_value=8765),
            patch(
                "custom_components.homematicip_local.control_unit.ControlConfig.create_control_unit",
                return_value=mock_control_unit,
            ),
        ):
            mock_config_entry_v14.add_to_hass(hass)
            await hass.config_entries.async_setup(mock_config_entry_v14.entry_id)
            await hass.async_block_till_done()
            config_entries = hass.config_entries.async_entries(HMIP_DOMAIN)
            assert len(config_entries) == 1
            config_entry = config_entries[0]
            assert config_entry.state == ConfigEntryState.LOADED
            assert config_entry.version == DomainConfigFlow.VERSION

            # Check that deprecated values were removed and valid ones kept
            optional_settings = config_entry.data[CONF_ADVANCED_CONFIG].get(CONF_OPTIONAL_SETTINGS, [])
            assert "ENABLE_LINKED_ENTITY_CLIMATE_ACTIVITY" not in optional_settings
            assert "USE_INTERFACE_CLIENT" not in optional_settings
            assert "SR_DISABLE_RANDOMIZED_OUTPUT" in optional_settings


class TestUnloadEntry:
    """Tests for unload entry functionality."""

    async def test_unload_entry(self, hass: HomeAssistant, mock_loaded_config_entry: MockConfigEntry) -> None:
        """Test unload entry."""
        assert hass.data[HMIP_DOMAIN]
        assert mock_loaded_config_entry.state == ConfigEntryState.LOADED
        assert await hass.config_entries.async_unload(mock_loaded_config_entry.entry_id) is True
        assert mock_loaded_config_entry.state == ConfigEntryState.NOT_LOADED
        await hass.async_block_till_done()

    # assert HMIP_DOMAIN not in hass.data
    # retry possible?
    # assert await hass.config_entries.async_unload(mock_loaded_config_entry.entry_id) is False


async def test_remove_entry(hass: HomeAssistant, mock_loaded_config_entry: MockConfigEntry) -> None:
    """Test unload entry."""
    assert hass.data[HMIP_DOMAIN]
    assert mock_loaded_config_entry.state == ConfigEntryState.LOADED
    await hass.config_entries.async_remove(mock_loaded_config_entry.entry_id)
    assert mock_loaded_config_entry.state == ConfigEntryState.NOT_LOADED
    await hass.async_block_till_done()
    # assert HMIP_DOMAIN not in hass.data


async def test_reload_entry(hass: HomeAssistant, mock_loaded_config_entry: MockConfigEntry) -> None:
    """Test unload entry."""
    assert mock_loaded_config_entry.title == const.INSTANCE_NAME
    assert hass.data[HMIP_DOMAIN]
    hass.config_entries.async_update_entry(mock_loaded_config_entry, title="Reload")
    await hass.async_block_till_done()
    assert hass.data[HMIP_DOMAIN]
    assert mock_loaded_config_entry.title == "Reload"


def _build_orphan_sweep_self(
    hass: HomeAssistant,
    entry_id: str,
    *,
    state: CentralState = CentralState.RUNNING,
    data_point_unique_ids: tuple[str, ...] = (),
    hub_unique_ids: tuple[str, ...] = (),
    named_hub_data_points: tuple[tuple[str, str], ...] = (),
    event_group_unique_ids: tuple[str, ...] = (),
    alarm_messages_unique_id: str | None = None,
    service_messages_unique_id: str | None = None,
    inbox_unique_id: str | None = None,
    update_unique_id: str | None = None,
    metrics_unique_ids: tuple[str, str, str] | None = None,
    connectivity_unique_ids: tuple[str, ...] = (),
    install_mode_unique_ids: tuple[tuple[str, str], ...] = (),
    known_device_addresses: tuple[str, ...] = (),
    backend: str = BACKEND_CCU,
    central_id: str = "11a0001234",
) -> SimpleNamespace:
    """Build a minimal ControlUnit-shaped self for _async_cleanup_orphaned_entity_registry_entries."""
    central = MagicMock()
    central.state = state
    central.device_coordinator.devices = tuple(SimpleNamespace(address=address) for address in known_device_addresses)
    central.query_facade.get_data_points.return_value = tuple(
        SimpleNamespace(unique_id=uid) for uid in data_point_unique_ids
    )
    central.hub_coordinator.get_hub_data_points.return_value = tuple(
        SimpleNamespace(unique_id=uid) for uid in hub_unique_ids
    ) + tuple(SimpleNamespace(unique_id=uid, legacy_name=legacy_name) for uid, legacy_name in named_hub_data_points)
    central.hub_coordinator.alarm_messages_dp = (
        SimpleNamespace(unique_id=alarm_messages_unique_id) if alarm_messages_unique_id else None
    )
    central.hub_coordinator.service_messages_dp = (
        SimpleNamespace(unique_id=service_messages_unique_id) if service_messages_unique_id else None
    )
    central.hub_coordinator.inbox_dp = SimpleNamespace(unique_id=inbox_unique_id) if inbox_unique_id else None
    central.hub_coordinator.update_dp = SimpleNamespace(unique_id=update_unique_id) if update_unique_id else None
    if metrics_unique_ids is None:
        central.hub_coordinator.metrics_dps = None
    else:
        sh, cl, le = metrics_unique_ids
        central.hub_coordinator.metrics_dps = SimpleNamespace(
            system_health=SimpleNamespace(unique_id=sh),
            connection_latency=SimpleNamespace(unique_id=cl),
            last_event_age=SimpleNamespace(unique_id=le),
        )
    central.hub_coordinator.connectivity_dps = {
        uid: SimpleNamespace(sensor=SimpleNamespace(unique_id=uid)) for uid in connectivity_unique_ids
    }
    central.hub_coordinator.install_mode_dps = {
        button_uid: SimpleNamespace(
            button=SimpleNamespace(unique_id=button_uid),
            sensor=SimpleNamespace(unique_id=sensor_uid),
        )
        for button_uid, sensor_uid in install_mode_unique_ids
    }
    central.query_facade.get_event_groups.return_value = tuple(
        SimpleNamespace(unique_id=uid) for uid in event_group_unique_ids
    )
    return SimpleNamespace(
        _hass=hass,
        _entry_id=entry_id,
        _central=central,
        _config=SimpleNamespace(backend=backend, central_id=central_id),
    )


async def test_cleanup_orphan_entries_removes_disabled_entity_without_data_point(
    hass: HomeAssistant,
    mock_config_entry_v2: MockConfigEntry,
) -> None:
    """Disabled entity without a corresponding data point is removed."""
    mock_config_entry_v2.add_to_hass(hass)
    entry_id = mock_config_entry_v2.entry_id

    entity_registry = er.async_get(hass)
    alive_entity = entity_registry.async_get_or_create(
        domain="sensor",
        platform=HMIP_DOMAIN,
        unique_id=f"{HMIP_DOMAIN}_alive_dp",
        config_entry=mock_config_entry_v2,
    )
    orphan_disabled = entity_registry.async_get_or_create(
        domain="sensor",
        platform=HMIP_DOMAIN,
        unique_id=f"{HMIP_DOMAIN}_orphan_dp",
        config_entry=mock_config_entry_v2,
        disabled_by=er.RegistryEntryDisabler.USER,
    )
    assert orphan_disabled.disabled

    fake_self = _build_orphan_sweep_self(hass, entry_id, data_point_unique_ids=("alive_dp",))
    ControlUnit._async_cleanup_orphaned_entity_registry_entries(fake_self)

    assert entity_registry.async_get(alive_entity.entity_id) is not None
    assert entity_registry.async_get(orphan_disabled.entity_id) is None


async def test_cleanup_orphan_entries_skipped_on_loom_backend(
    hass: HomeAssistant,
    mock_config_entry_v2: MockConfigEntry,
) -> None:
    """The sweep is skipped for the loom backend (partial hub-coordinator surface)."""
    mock_config_entry_v2.add_to_hass(hass)
    entry_id = mock_config_entry_v2.entry_id

    entity_registry = er.async_get(hass)
    orphan_disabled = entity_registry.async_get_or_create(
        domain="sensor",
        platform=HMIP_DOMAIN,
        unique_id=f"{HMIP_DOMAIN}_orphan_dp",
        config_entry=mock_config_entry_v2,
        disabled_by=er.RegistryEntryDisabler.USER,
    )

    # No data points reported: on the CCU backend this would orphan the entry,
    # but the loom backend must skip the sweep entirely and leave it untouched.
    fake_self = _build_orphan_sweep_self(hass, entry_id, backend=BACKEND_LOOM)
    ControlUnit._async_cleanup_orphaned_entity_registry_entries(fake_self)

    assert entity_registry.async_get(orphan_disabled.entity_id) is not None


async def test_cleanup_orphan_entries_recognizes_hub_and_event_unique_ids(
    hass: HomeAssistant,
    mock_config_entry_v2: MockConfigEntry,
) -> None:
    """Hub data points and event groups must protect their entries from cleanup."""
    mock_config_entry_v2.add_to_hass(hass)
    entry_id = mock_config_entry_v2.entry_id

    entity_registry = er.async_get(hass)
    sysvar_entity = entity_registry.async_get_or_create(
        domain="sensor",
        platform=HMIP_DOMAIN,
        unique_id=f"{HMIP_DOMAIN}_sysvar_dp",
        config_entry=mock_config_entry_v2,
        disabled_by=er.RegistryEntryDisabler.USER,
    )
    event_entity = entity_registry.async_get_or_create(
        domain="event",
        platform=HMIP_DOMAIN,
        unique_id=f"{HMIP_DOMAIN}_event_group_dp",
        config_entry=mock_config_entry_v2,
    )

    fake_self = _build_orphan_sweep_self(
        hass,
        entry_id,
        hub_unique_ids=("sysvar_dp",),
        event_group_unique_ids=("event_group_dp",),
    )
    ControlUnit._async_cleanup_orphaned_entity_registry_entries(fake_self)

    assert entity_registry.async_get(sysvar_entity.entity_id) is not None
    assert entity_registry.async_get(event_entity.entity_id) is not None
    # get_event_groups must have been queried for every DeviceTriggerEventType
    assert fake_self._central.query_facade.get_event_groups.call_count == len(list(DeviceTriggerEventType))


async def test_cleanup_orphan_entries_skipped_when_central_not_running(
    hass: HomeAssistant,
    mock_config_entry_v2: MockConfigEntry,
) -> None:
    """No cleanup when central is not RUNNING (avoids deleting entries during degraded startup)."""
    mock_config_entry_v2.add_to_hass(hass)
    entry_id = mock_config_entry_v2.entry_id

    entity_registry = er.async_get(hass)
    entry = entity_registry.async_get_or_create(
        domain="sensor",
        platform=HMIP_DOMAIN,
        unique_id=f"{HMIP_DOMAIN}_some_dp",
        config_entry=mock_config_entry_v2,
        disabled_by=er.RegistryEntryDisabler.USER,
    )

    fake_self = _build_orphan_sweep_self(hass, entry_id, state=CentralState.DEGRADED)
    ControlUnit._async_cleanup_orphaned_entity_registry_entries(fake_self)

    # Entry survives because the sweep bailed out early
    assert entity_registry.async_get(entry.entity_id) is not None
    fake_self._central.query_facade.get_data_points.assert_not_called()


async def test_cleanup_orphan_entries_ignores_other_platforms(
    hass: HomeAssistant,
    mock_config_entry_v2: MockConfigEntry,
) -> None:
    """Entries from other platforms must not be touched even with matching config entry."""
    mock_config_entry_v2.add_to_hass(hass)
    entry_id = mock_config_entry_v2.entry_id

    entity_registry = er.async_get(hass)
    foreign_entry = entity_registry.async_get_or_create(
        domain="sensor",
        platform="some_other_integration",
        unique_id="foreign_uid",
        config_entry=mock_config_entry_v2,
        disabled_by=er.RegistryEntryDisabler.USER,
    )

    fake_self = _build_orphan_sweep_self(hass, entry_id)
    ControlUnit._async_cleanup_orphaned_entity_registry_entries(fake_self)

    assert entity_registry.async_get(foreign_entry.entity_id) is not None


async def test_cleanup_orphan_entries_keeps_native_backup_button(
    hass: HomeAssistant,
    mock_config_entry_v2: MockConfigEntry,
) -> None:
    """The integration-native backup button has no data point but must never be swept."""
    mock_config_entry_v2.add_to_hass(hass)
    entry_id = mock_config_entry_v2.entry_id

    entity_registry = er.async_get(hass)
    backup_button = entity_registry.async_get_or_create(
        domain="button",
        platform=HMIP_DOMAIN,
        unique_id=f"{HMIP_DOMAIN}_openccu_create_backup",
        config_entry=mock_config_entry_v2,
    )

    # No data points reported at all -> without the guard the backup button would orphan.
    fake_self = _build_orphan_sweep_self(hass, entry_id)
    ControlUnit._async_cleanup_orphaned_entity_registry_entries(fake_self)

    assert entity_registry.async_get(backup_button.entity_id) is not None


async def test_cleanup_orphan_entries_keeps_central_id_drift(
    hass: HomeAssistant,
    mock_config_entry_v2: MockConfigEntry,
) -> None:
    """A hub entry on a stale central-id anchor whose data point still exists must not be deleted."""
    mock_config_entry_v2.add_to_hass(hass)
    entry_id = mock_config_entry_v2.entry_id

    entity_registry = er.async_get(hass)
    # Registry anchored on a stale central id; the live data point uses the current one.
    drifted = entity_registry.async_get_or_create(
        domain="sensor",
        platform=HMIP_DOMAIN,
        unique_id=f"{HMIP_DOMAIN}_w78v4413eq_sysvar_x",
        config_entry=mock_config_entry_v2,
        disabled_by=er.RegistryEntryDisabler.USER,
    )

    fake_self = _build_orphan_sweep_self(
        hass,
        entry_id,
        central_id="11a0001234",
        hub_unique_ids=("11a0001234_sysvar_x",),
    )
    ControlUnit._async_cleanup_orphaned_entity_registry_entries(fake_self)

    # The drifted entry stays (the setup-time realign migration owns re-anchoring it),
    # rather than being permanently deleted.
    assert entity_registry.async_get(drifted.entity_id) is not None


async def test_cleanup_orphan_entries_recognizes_all_hub_data_point_sources(
    hass: HomeAssistant,
    mock_config_entry_v2: MockConfigEntry,
) -> None:
    """Singleton/mapping hub data points (inbox, update, alarm/service messages, metrics, connectivity, install_mode) must protect their entries."""
    mock_config_entry_v2.add_to_hass(hass)
    entry_id = mock_config_entry_v2.entry_id

    entity_registry = er.async_get(hass)
    hub_unique_ids = (
        "hub_inbox",
        "hub_system-update",
        "hub_alarm-messages",
        "hub_service-messages",
        "hub_system-health",
        "hub_connection-latency",
        "hub_last-event-age",
        "hub_connectivity-hmip-rf",
        "install_mode_hmip-button",
        "install_mode_hmip",
    )
    created = [
        entity_registry.async_get_or_create(
            domain="sensor",
            platform=HMIP_DOMAIN,
            unique_id=f"{HMIP_DOMAIN}_{uid}",
            config_entry=mock_config_entry_v2,
        )
        for uid in hub_unique_ids
    ]

    fake_self = _build_orphan_sweep_self(
        hass,
        entry_id,
        inbox_unique_id="hub_inbox",
        update_unique_id="hub_system-update",
        alarm_messages_unique_id="hub_alarm-messages",
        service_messages_unique_id="hub_service-messages",
        metrics_unique_ids=("hub_system-health", "hub_connection-latency", "hub_last-event-age"),
        connectivity_unique_ids=("hub_connectivity-hmip-rf",),
        install_mode_unique_ids=(("install_mode_hmip-button", "install_mode_hmip"),),
    )
    ControlUnit._async_cleanup_orphaned_entity_registry_entries(fake_self)

    for entry in created:
        assert entity_registry.async_get(entry.entity_id) is not None, f"{entry.entity_id} was unexpectedly removed"


async def test_cleanup_orphan_entries_skipped_when_data_load_incomplete(
    hass: HomeAssistant,
    mock_config_entry_v2: MockConfigEntry,
) -> None:
    """
    A near-total wipe must be refused (regression for #3215).

    The central can report RUNNING (all clients connected) while the device
    descriptions failed to load (e.g. transient auth error during a CCU restore).
    ``get_data_points()`` then returns only the few devices that did load, which
    would make almost every registry entry look orphaned. Deleting them is
    permanent and breaks dashboards/automations, so the sweep must bail out.
    """
    mock_config_entry_v2.add_to_hass(hass)
    entry_id = mock_config_entry_v2.entry_id

    entity_registry = er.async_get(hass)
    created = [
        entity_registry.async_get_or_create(
            domain="sensor",
            platform=HMIP_DOMAIN,
            unique_id=f"{HMIP_DOMAIN}_dp_{index}",
            config_entry=mock_config_entry_v2,
        )
        for index in range(10)
    ]

    # Only one of ten data points loaded -> 9/10 would be orphaned (90% > threshold).
    fake_self = _build_orphan_sweep_self(hass, entry_id, data_point_unique_ids=("dp_0",))
    ControlUnit._async_cleanup_orphaned_entity_registry_entries(fake_self)

    for entry in created:
        assert entity_registry.async_get(entry.entity_id) is not None, (
            f"{entry.entity_id} was deleted despite an incomplete device load"
        )


def _create_alive_entities(
    entity_registry: er.EntityRegistry,
    mock_config_entry: MockConfigEntry,
    count: int,
) -> tuple[str, ...]:
    """Create ``count`` entities whose data points are reported alive; return their unique_id stems."""
    stems = tuple(f"alive_{index}" for index in range(count))
    for stem in stems:
        entity_registry.async_get_or_create(
            domain="sensor",
            platform=HMIP_DOMAIN,
            unique_id=f"{HMIP_DOMAIN}_{stem}",
            config_entry=mock_config_entry,
        )
    return stems


async def test_cleanup_orphan_entries_keeps_entry_of_not_yet_loaded_device(
    hass: HomeAssistant,
    mock_config_entry_v2: MockConfigEntry,
) -> None:
    """
    A device entry whose device is not (yet) loaded must be kept, not swept.

    When the central reports RUNNING before every device is materialised (e.g. a
    paramset-cache rebuild on upgrade), the device's data points are missing from
    ``get_data_points()``. Deleting the (disabled) entry would re-create the entity
    disabled and under a fresh entity_id, breaking dashboards/automations/history.
    The device-presence guard keeps it because the backing device is still known to
    HA but absent from the central's loaded devices.
    """
    mock_config_entry_v2.add_to_hass(hass)
    entry_id = mock_config_entry_v2.entry_id

    entity_registry = er.async_get(hass)
    device_registry = dr.async_get(hass)
    alive = _create_alive_entities(entity_registry, mock_config_entry_v2, count=3)

    device = device_registry.async_get_or_create(
        config_entry_id=entry_id,
        identifiers={(HMIP_DOMAIN, f"ABC0000001{IDENTIFIER_SEPARATOR}CCU-Homematic")},
    )
    calculated_disabled = entity_registry.async_get_or_create(
        domain="sensor",
        platform=HMIP_DOMAIN,
        unique_id=f"{HMIP_DOMAIN}_calculated_abc0000001_1_dew_point",
        config_entry=mock_config_entry_v2,
        device_id=device.id,
        disabled_by=er.RegistryEntryDisabler.USER,
    )

    # Device ABC0000001 is NOT among the central's loaded devices -> not-yet-loaded.
    fake_self = _build_orphan_sweep_self(hass, entry_id, data_point_unique_ids=alive)
    ControlUnit._async_cleanup_orphaned_entity_registry_entries(fake_self)

    assert entity_registry.async_get(calculated_disabled.entity_id) is not None


async def test_cleanup_orphan_entries_removes_entry_when_device_loaded_but_data_point_gone(
    hass: HomeAssistant,
    mock_config_entry_v2: MockConfigEntry,
) -> None:
    """A device entry whose device IS loaded but whose data point is gone stays sweepable.

    This is the genuine-orphan case (e.g. un_ignore / profile change removed the
    data point while the device itself is present), which must still be cleaned up.
    """
    mock_config_entry_v2.add_to_hass(hass)
    entry_id = mock_config_entry_v2.entry_id

    entity_registry = er.async_get(hass)
    device_registry = dr.async_get(hass)
    alive = _create_alive_entities(entity_registry, mock_config_entry_v2, count=3)

    device = device_registry.async_get_or_create(
        config_entry_id=entry_id,
        identifiers={(HMIP_DOMAIN, f"ABC0000001{IDENTIFIER_SEPARATOR}CCU-Homematic")},
    )
    orphan_disabled = entity_registry.async_get_or_create(
        domain="sensor",
        platform=HMIP_DOMAIN,
        unique_id=f"{HMIP_DOMAIN}_abc0000001_1_gone_parameter",
        config_entry=mock_config_entry_v2,
        device_id=device.id,
        disabled_by=er.RegistryEntryDisabler.USER,
    )

    # Device ABC0000001 IS loaded, but its data point is not reported -> real orphan.
    fake_self = _build_orphan_sweep_self(
        hass, entry_id, data_point_unique_ids=alive, known_device_addresses=("ABC0000001",)
    )
    ControlUnit._async_cleanup_orphaned_entity_registry_entries(fake_self)

    assert entity_registry.async_get(orphan_disabled.entity_id) is None


async def test_cleanup_orphan_entries_removes_hub_anchored_entry_regardless_of_devices(
    hass: HomeAssistant,
    mock_config_entry_v2: MockConfigEntry,
) -> None:
    """A hub-anchored orphan is still swept: the guard only shields real device entries.

    Hub / program / sysvar entries hang off the central pseudo-device, whose
    identifier carries no ``IDENTIFIER_SEPARATOR``, so the device-presence guard must
    not shield them even when no devices are loaded.
    """
    mock_config_entry_v2.add_to_hass(hass)
    entry_id = mock_config_entry_v2.entry_id

    entity_registry = er.async_get(hass)
    device_registry = dr.async_get(hass)
    alive = _create_alive_entities(entity_registry, mock_config_entry_v2, count=3)

    hub_device = device_registry.async_get_or_create(
        config_entry_id=entry_id,
        identifiers={(HMIP_DOMAIN, "CCU-Homematic")},
    )
    hub_orphan = entity_registry.async_get_or_create(
        domain="sensor",
        platform=HMIP_DOMAIN,
        unique_id=f"{HMIP_DOMAIN}_deleted_sysvar",
        config_entry=mock_config_entry_v2,
        device_id=hub_device.id,
        disabled_by=er.RegistryEntryDisabler.USER,
    )

    fake_self = _build_orphan_sweep_self(hass, entry_id, data_point_unique_ids=alive)
    ControlUnit._async_cleanup_orphaned_entity_registry_entries(fake_self)

    assert entity_registry.async_get(hub_orphan.entity_id) is None


class TestCuxdMigrationAgainstTheRegistry:
    """The registry walk of the CUxD scoping pass, not just its arithmetic.

    `TestCuxdUniqueIdScoping` covers the key rebuild. This covers what happens
    to a registry, which is what a user actually loses: whether the historied
    entry keeps its entity_id, what becomes of a freshly keyed duplicate, and
    that a rename is never attempted onto a key already taken — the "unique id
    already in use" that aborts a config entry and fails setup.

    Worth having because the pass is not hypothetical for anyone: it runs on
    both backends, and on a direct-CCU install *every* CUxD entity is
    affected. The maintainer runs CUxD devices, so this touches real
    registries rather than a shape nobody has.
    """

    _CENTRAL = "11a0001234"
    _DOMAIN_PREFIX = HMIP_DOMAIN

    @staticmethod
    def _seed(hass: HomeAssistant, entry: MockConfigEntry, *, unique_id: str, entity_suffix: str) -> er.RegistryEntry:
        return er.async_get(hass).async_get_or_create(
            domain="sensor",
            platform=HMIP_DOMAIN,
            unique_id=unique_id,
            suggested_object_id=entity_suffix,
            config_entry=entry,
        )

    async def test_a_non_cuxd_entry_is_left_alone(
        self, hass: HomeAssistant, mock_config_entry_v2: MockConfigEntry
    ) -> None:
        """An install with no CUxD devices sees nothing happen — the docstring's promise."""
        mock_config_entry_v2.add_to_hass(hass)
        untouched = self._seed(
            hass,
            mock_config_entry_v2,
            unique_id=f"{self._DOMAIN_PREFIX}_vcu0000001_1_state",
            entity_suffix="regular_switch",
        )

        await _async_migrate_cuxd_unique_ids(hass, mock_config_entry_v2, namespace="", central_id=self._CENTRAL)

        entity_registry = er.async_get(hass)
        assert entity_registry.async_get(untouched.entity_id).unique_id == untouched.unique_id

    async def test_a_second_run_changes_nothing(
        self, hass: HomeAssistant, mock_config_entry_v2: MockConfigEntry
    ) -> None:
        """The pass runs on every start-up, so it has to be idempotent."""
        mock_config_entry_v2.add_to_hass(hass)
        self._seed(
            hass,
            mock_config_entry_v2,
            unique_id=f"{self._DOMAIN_PREFIX}_cux2801001_1_state",
            entity_suffix="cuxd_switch",
        )
        entity_registry = er.async_get(hass)

        await _async_migrate_cuxd_unique_ids(hass, mock_config_entry_v2, namespace="", central_id=self._CENTRAL)
        after_first = {
            (e.entity_id, e.unique_id)
            for e in er.async_entries_for_config_entry(entity_registry, mock_config_entry_v2.entry_id)
        }

        await _async_migrate_cuxd_unique_ids(hass, mock_config_entry_v2, namespace="", central_id=self._CENTRAL)
        after_second = {
            (e.entity_id, e.unique_id)
            for e in er.async_entries_for_config_entry(entity_registry, mock_config_entry_v2.entry_id)
        }
        assert after_second == after_first

    async def test_a_taken_target_key_is_skipped_not_raised(
        self, hass: HomeAssistant, mock_config_entry_v2: MockConfigEntry
    ) -> None:
        """The collision must not abort setup.

        `async_migrate_entries` propagates a duplicate-unique_id error, which
        would fail the whole config entry — every entity gone, not just this
        one. The duplicate is the entry without history, so skipping is right;
        what matters is that the historied entry survives either way.
        """
        mock_config_entry_v2.add_to_hass(hass)
        old_key = f"{self._DOMAIN_PREFIX}_cux2801001_1_state"
        new_key = _cuxd_scoped_unique_id(old_key, namespace="", central_id=self._CENTRAL)
        assert new_key is not None

        historied = self._seed(hass, mock_config_entry_v2, unique_id=old_key, entity_suffix="cuxd_historied")
        twin = self._seed(hass, mock_config_entry_v2, unique_id=new_key, entity_suffix="cuxd_twin")

        await _async_migrate_cuxd_unique_ids(hass, mock_config_entry_v2, namespace="", central_id=self._CENTRAL)

        entity_registry = er.async_get(hass)
        assert entity_registry.async_get(historied.entity_id) is not None, "setup-aborting collision"
        assert entity_registry.async_get(historied.entity_id).unique_id == old_key
        assert entity_registry.async_get(twin.entity_id).unique_id == new_key

    async def test_the_historied_entry_gains_the_central_slot(
        self, hass: HomeAssistant, mock_config_entry_v2: MockConfigEntry
    ) -> None:
        """A CUxD entry is re-keyed in place, keeping its entity_id and history."""
        mock_config_entry_v2.add_to_hass(hass)
        seeded = self._seed(
            hass,
            mock_config_entry_v2,
            unique_id=f"{self._DOMAIN_PREFIX}_cux2801001_1_state",
            entity_suffix="cuxd_switch",
        )

        await _async_migrate_cuxd_unique_ids(hass, mock_config_entry_v2, namespace="", central_id=self._CENTRAL)

        entity_registry = er.async_get(hass)
        migrated = entity_registry.async_get(seeded.entity_id)
        assert migrated is not None, "the entry was removed instead of migrated"
        assert migrated.unique_id == _cuxd_scoped_unique_id(
            f"{self._DOMAIN_PREFIX}_cux2801001_1_state", namespace="", central_id=self._CENTRAL
        )
        assert self._CENTRAL in migrated.unique_id


class TestCuxdUniqueIdScoping:
    """``_cuxd_scoped_unique_id`` inserts the central-id slot into CUxD keys.

    CUxD hands out the same synthetic addresses on every CCU — the first
    "(28) System" device is ``CUX2801001`` on essentially every install — so
    two bridged CCUs declared byte-identical unique_ids and Home Assistant
    kept only the first. aiohomematic 2026.8.7 scopes the family, as the
    daemon always had, so every CUxD entity keyed before that moves once.
    """

    _D = HMIP_DOMAIN
    _CENTRAL = "abc1234567"

    @pytest.mark.parametrize(
        ("unique_id", "namespace"),
        [
            # Already scoped — the pass runs on every setup, so this matters.
            (f"{_D}_abc1234567_cux2801001_1_state", ""),
            (f"{_D}_loom_abc1234567_cux2801001_1_state", "loom_"),
            # Not a CUxD address.
            (f"{_D}_vcu1234567_1_state", ""),
            (f"{_D}_loom_vcu1234567_1_state", "loom_"),
            # A loom key reached on the direct-CCU path is not ours to touch.
            (f"{_D}_loom_cux2801001_1_state", ""),
            # Daemon-computed alarm-panel ids carry no routing key at all.
            (f"{_D}_openccu-loom_alarm_55f96726", "loom_"),
            # Another integration's entity in the same registry.
            ("other_integration_cux2801001_1_state", ""),
        ],
    )
    def test_leaves_everything_else_alone(self, unique_id: str, namespace: str) -> None:
        assert _cuxd_scoped_unique_id(unique_id, namespace=namespace, central_id=self._CENTRAL) is None

    @pytest.mark.parametrize(
        ("unique_id", "namespace", "expected"),
        [
            # Direct-CCU backend: the central id goes at the front.
            (f"{_D}_cux2801001_1_state", "", f"{_D}_abc1234567_cux2801001_1_state"),
            # …including behind a routing-key prefix, which is why the family
            # is matched on the CUX serial shape rather than on a leading
            # substring.
            (
                f"{_D}_calculated_cux2801001_1_state",
                "",
                f"{_D}_abc1234567_calculated_cux2801001_1_state",
            ),
            # openccu-loom backend: after the namespace, not before it.
            (
                f"{_D}_loom_cux2801001_1_state",
                "loom_",
                f"{_D}_loom_abc1234567_cux2801001_1_state",
            ),
        ],
    )
    def test_scopes_a_cuxd_key(self, unique_id: str, namespace: str, expected: str) -> None:
        assert _cuxd_scoped_unique_id(unique_id, namespace=namespace, central_id=self._CENTRAL) == expected

    def test_scoping_is_idempotent(self) -> None:
        """Applying the rewrite to its own output is a no-op."""
        once = _cuxd_scoped_unique_id(f"{self._D}_cux2801001_1_state", namespace="", central_id=self._CENTRAL)
        assert once is not None
        assert _cuxd_scoped_unique_id(once, namespace="", central_id=self._CENTRAL) is None


class TestLoomUniqueIdMigration:
    """``_loom_migrated_unique_id`` maps legacy keys to the loom/serial scheme."""

    _ENTRY_SUFFIX = "a1b2c3d4e5"  # legacy entry_id[-10:] hub prefix
    _SERIAL_SUFFIX = "11a0001234"  # new serial[-10:]
    _D = HMIP_DOMAIN  # "homematicip_local"

    @pytest.mark.parametrize(
        "unique_id",
        [
            f"{_D}_loom_vcu1234567_1_state",  # already migrated → idempotent
            f"{_D}_home_create_backup",  # synthetic backup button
            f"{_D}_event_group_keypress_vcu1234567_1",  # event group (loom n/a yet)
            # Daemon-computed alarm-panel ids are backend-agnostic — never
            # legacy keys. Prefixing them orphaned the entity and
            # crash-looped setup ("unique id already in use").
            f"{_D}_openccu-loom_alarm_55f96726-76d9-43b9-8b20-71f6266e24d9",
            f"{_D}_openccu-loom_alarm_master",
            "other_integration_xyz",  # not ours
        ],
    )
    def test_left_untouched(self, unique_id: str) -> None:
        assert (
            _loom_migrated_unique_id(unique_id, entry_suffix=self._ENTRY_SUFFIX, serial_suffix=self._SERIAL_SUFFIX)
            is None
        )

    @pytest.mark.parametrize(
        ("old", "expected"),
        [
            # Device data point — no central prefix, just the loom_ namespace.
            (f"{_D}_vcu1234567_1_state", f"{_D}_loom_vcu1234567_1_state"),
            # Custom DP / channel — no parameter, still no prefix.
            (f"{_D}_vcu1234567_1", f"{_D}_loom_vcu1234567_1"),
            # Hub key — entry_id prefix swapped for the serial suffix.
            (
                f"{_D}_a1b2c3d4e5_sysvar_aussen-temperatur",
                f"{_D}_loom_11a0001234_sysvar_aussen-temperatur",
            ),
            # Internal address — same prefix swap.
            (f"{_D}_a1b2c3d4e5_int0001234_1_level", f"{_D}_loom_11a0001234_int0001234_1_level"),
        ],
    )
    def test_rewrites(self, old: str, expected: str) -> None:
        assert (
            _loom_migrated_unique_id(old, entry_suffix=self._ENTRY_SUFFIX, serial_suffix=self._SERIAL_SUFFIX)
            == expected
        )


class TestAioHomematicUniqueIdRestore:
    """``_aiohomematic_restored_unique_id`` strips the loom_ namespace."""

    _D = HMIP_DOMAIN  # "homematicip_local"

    @pytest.mark.parametrize(
        "unique_id",
        [
            f"{_D}_vcu1234567_1_state",  # already aiohomematic-scheme → idempotent
            f"{_D}_11a0001234_sysvar_aussen-temperatur",  # serial hub key, no loom_ namespace
            f"{_D}_home_create_backup",  # synthetic backup button (never loom-keyed)
            "other_integration_xyz",  # not ours
        ],
    )
    def test_left_untouched(self, unique_id: str) -> None:
        assert _aiohomematic_restored_unique_id(unique_id) is None

    @pytest.mark.parametrize(
        ("old", "expected"),
        [
            # Device data point — only the loom_ namespace is stripped.
            (f"{_D}_loom_vcu1234567_1_state", f"{_D}_vcu1234567_1_state"),
            # Custom DP / channel — no parameter, still just strips loom_.
            (f"{_D}_loom_vcu1234567_1", f"{_D}_vcu1234567_1"),
            # Hub key — the serial-anchored slot is already correct, strip loom_.
            (
                f"{_D}_loom_11a0001234_sysvar_aussen-temperatur",
                f"{_D}_11a0001234_sysvar_aussen-temperatur",
            ),
            # Internal address — same plain strip.
            (f"{_D}_loom_11a0001234_int0001234_1_level", f"{_D}_11a0001234_int0001234_1_level"),
        ],
    )
    def test_rewrites(self, old: str, expected: str) -> None:
        assert _aiohomematic_restored_unique_id(old) == expected

    @pytest.mark.parametrize(
        "original",
        [
            f"{_D}_vcu1234567_1_state",
            f"{_D}_vcu1234567_1",
            # Hub keys are serial-anchored on both backends, so they round-trip.
            f"{_D}_11a0001234_sysvar_aussen-temperatur",
            f"{_D}_11a0001234_int0001234_1_level",
            f"{_D}_11a0001234_bidcos_rf_1_press_short",
        ],
    )
    def test_round_trip(self, original: str) -> None:
        """Round-trip aiohomematic → loom → aiohomematic restores the serial key."""
        loom = _loom_migrated_unique_id(original, entry_suffix="a1b2c3d4e5", serial_suffix="11a0001234")
        assert loom is not None
        assert _aiohomematic_restored_unique_id(loom) == original


class TestRealignedHubUniqueId:
    """``_realigned_hub_unique_id`` forces the hub central-id slot onto the live anchor."""

    _D = HMIP_DOMAIN
    _NEW = "11a0001234"  # the live central id (serial[-10:])

    def test_already_aligned_is_noop(self) -> None:
        assert realign_hub_unique_id(f"{self._D}_11a0001234_sysvar_x", central_id="11a0001234") is None

    @pytest.mark.parametrize(
        "unique_id",
        [
            f"{_D}_vcu1234567_1_state",  # device key — no central slot
            f"{_D}_loom_a1b2c3d4e5_sysvar_x",  # loom-namespaced — not ours here
            f"{_D}_11a0001234_sysvar_x",  # already on the live anchor
            f"{_D}_openccu_create_backup",  # synthetic native button — not a routing key
            f"{_D}_event_group_keypress_0008dd8997b338_1",  # device event group — no central slot
            f"{_D}_calculated_0008dd8997b338_1_dew_point",  # device-anchored calculated DP — no central slot
            "other_integration_xyz",  # not ours
        ],
    )
    def test_left_untouched(self, unique_id: str) -> None:
        assert self._realign(unique_id) is None

    @pytest.mark.parametrize(
        ("old", "expected"),
        [
            # Any stale slot value is rewritten onto the live anchor, regardless of
            # whether it was a legacy entry_id, an old serial or a re-add leftover.
            (f"{_D}_a1b2c3d4e5_sysvar_x", f"{_D}_11a0001234_sysvar_x"),
            (f"{_D}_w78v4413eq_hub_system-update", f"{_D}_11a0001234_hub_system-update"),
            (f"{_D}_w78v4413eq_install_mode_hmip", f"{_D}_11a0001234_install_mode_hmip"),
            (f"{_D}_a1b2c3d4e5_program_my-prog", f"{_D}_11a0001234_program_my-prog"),
            (f"{_D}_a1b2c3d4e5_int0001234_1_level", f"{_D}_11a0001234_int0001234_1_level"),
            (f"{_D}_a1b2c3d4e5_bidcos_rf_1_press_short", f"{_D}_11a0001234_bidcos_rf_1_press_short"),
            (f"{_D}_w78v4413eq_hmip_rcv_1_9_press_long", f"{_D}_11a0001234_hmip_rcv_1_9_press_long"),
            # Calculated DPs on internal/hub channels: the central-id slot sits before
            # the `calculated_` marker and must be realigned like any other hub key.
            (
                f"{_D}_a1b2c3d4e5_calculated_int0001234_1_dew_point",
                f"{_D}_11a0001234_calculated_int0001234_1_dew_point",
            ),
            (
                f"{_D}_w78v4413eq_calculated_int0001234_1_vapor_concentration",
                f"{_D}_11a0001234_calculated_int0001234_1_vapor_concentration",
            ),
            # Virtual-remote event groups keep their event_group_<type>_ prefix.
            (
                f"{_D}_event_group_keypress_w78v4413eq_bidcos_rf_1",
                f"{_D}_event_group_keypress_11a0001234_bidcos_rf_1",
            ),
        ],
    )
    def test_rewrites(self, old: str, expected: str) -> None:
        assert self._realign(old) == expected

    def _realign(self, unique_id: str) -> str | None:
        return realign_hub_unique_id(unique_id, central_id=self._NEW)


async def test_async_migrate_loom_unique_ids_repairs_wrongly_prefixed_panel(hass: HomeAssistant) -> None:
    """The repair sweep restores a wrongly loom_-prefixed panel and removes its duplicate.

    Regression: the pre-fix sweep prefixed the daemon-computed alarm-panel
    ids with loom_, orphaning the original entity; once the platform had
    spawned a correctly keyed duplicate, the next setup crash-looped with
    "Unique id ... is already in use".
    """
    serial = "3014F711A0001234"
    entry = MockConfigEntry(domain=HMIP_DOMAIN, unique_id=serial)
    entry.add_to_hass(hass)
    entity_registry = er.async_get(hass)
    area = "55f96726-76d9-43b9-8b20-71f6266e24d9"
    correct_unique_id = f"{HMIP_DOMAIN}_openccu-loom_alarm_{area}"
    # The original entity, wrongly renamed by the pre-fix sweep — it keeps
    # the user's entity_id, history and customisations and must win.
    original = entity_registry.async_get_or_create(
        domain="alarm_control_panel",
        platform=HMIP_DOMAIN,
        unique_id=f"{HMIP_DOMAIN}_loom_openccu-loom_alarm_{area}",
        config_entry=entry,
        suggested_object_id="ottoloom_obergeschoss",
    )
    # The duplicate the platform spawned after the original stopped matching.
    duplicate = entity_registry.async_get_or_create(
        domain="alarm_control_panel",
        platform=HMIP_DOMAIN,
        unique_id=correct_unique_id,
        config_entry=entry,
        suggested_object_id="ottoloom_obergeschoss_2",
    )
    # A genuine legacy key must still migrate in the same pass.
    legacy = entity_registry.async_get_or_create(
        domain="switch",
        platform=HMIP_DOMAIN,
        unique_id=f"{HMIP_DOMAIN}_vcu1234567_1_state",
        config_entry=entry,
    )

    await _async_migrate_loom_unique_ids(hass, entry)

    assert entity_registry.async_get(duplicate.entity_id) is None
    repaired = entity_registry.async_get(original.entity_id)
    assert repaired is not None
    assert repaired.unique_id == correct_unique_id
    migrated = entity_registry.async_get(legacy.entity_id)
    assert migrated is not None
    assert migrated.unique_id == f"{HMIP_DOMAIN}_loom_vcu1234567_1_state"


async def test_async_migrate_loom_unique_ids_repairs_without_duplicate(hass: HomeAssistant) -> None:
    """A damaged panel with no duplicate is renamed straight back."""
    serial = "3014F711A0001234"
    entry = MockConfigEntry(domain=HMIP_DOMAIN, unique_id=serial)
    entry.add_to_hass(hass)
    entity_registry = er.async_get(hass)
    original = entity_registry.async_get_or_create(
        domain="alarm_control_panel",
        platform=HMIP_DOMAIN,
        unique_id=f"{HMIP_DOMAIN}_loom_openccu-loom_alarm_master",
        config_entry=entry,
    )

    await _async_migrate_loom_unique_ids(hass, entry)

    repaired = entity_registry.async_get(original.entity_id)
    assert repaired is not None
    assert repaired.unique_id == f"{HMIP_DOMAIN}_openccu-loom_alarm_master"


async def test_async_migrate_loom_unique_ids_skips_on_collision(hass: HomeAssistant) -> None:
    """A legacy key whose loom target is already taken is skipped, not fatal."""
    serial = "3014F711A0001234"
    entry = MockConfigEntry(domain=HMIP_DOMAIN, unique_id=serial)
    entry.add_to_hass(hass)
    entity_registry = er.async_get(hass)
    legacy = entity_registry.async_get_or_create(
        domain="switch",
        platform=HMIP_DOMAIN,
        unique_id=f"{HMIP_DOMAIN}_vcu1234567_1_state",
        config_entry=entry,
    )
    occupant = entity_registry.async_get_or_create(
        domain="switch",
        platform=HMIP_DOMAIN,
        unique_id=f"{HMIP_DOMAIN}_loom_vcu1234567_1_state",
        config_entry=entry,
    )

    # Must not raise ("unique id already in use" would fail the whole setup).
    await _async_migrate_loom_unique_ids(hass, entry)

    unchanged = entity_registry.async_get(legacy.entity_id)
    assert unchanged is not None
    assert unchanged.unique_id == f"{HMIP_DOMAIN}_vcu1234567_1_state"
    assert entity_registry.async_get(occupant.entity_id) is not None


async def test_async_restore_aiohomematic_unique_ids_rewrites_registry(hass: HomeAssistant) -> None:
    """The registry rewrite strips loom_ from device and hub keys alike."""
    serial = "3014F711A0001234"
    entry = MockConfigEntry(domain=HMIP_DOMAIN, unique_id=serial)
    entry.add_to_hass(hass)
    serial_suffix = serial[-10:].lower()

    entity_registry = er.async_get(hass)
    device = entity_registry.async_get_or_create(
        domain="sensor",
        platform=HMIP_DOMAIN,
        unique_id=f"{HMIP_DOMAIN}_loom_vcu1234567_1_state",
        config_entry=entry,
    )
    hub = entity_registry.async_get_or_create(
        domain="sensor",
        platform=HMIP_DOMAIN,
        unique_id=f"{HMIP_DOMAIN}_loom_{serial_suffix}_sysvar_aussen-temperatur",
        config_entry=entry,
    )

    await _async_restore_aiohomematic_unique_ids(hass, entry)

    assert entity_registry.async_get(device.entity_id).unique_id == f"{HMIP_DOMAIN}_vcu1234567_1_state"
    assert (
        entity_registry.async_get(hub.entity_id).unique_id == f"{HMIP_DOMAIN}_{serial_suffix}_sysvar_aussen-temperatur"
    )


async def test_async_migrate_aiohomematic_hub_unique_ids_reanchors_onto_serial(hass: HomeAssistant) -> None:
    """Legacy entry_id-prefixed hub keys are re-anchored onto the CCU serial."""
    serial = "3014F711A0001234"
    entry = MockConfigEntry(domain=HMIP_DOMAIN, unique_id=serial)
    entry.add_to_hass(hass)
    serial_suffix = serial[-10:].lower()
    entry_suffix = entry.entry_id[-10:]

    entity_registry = er.async_get(hass)
    hub = entity_registry.async_get_or_create(
        domain="sensor",
        platform=HMIP_DOMAIN,
        unique_id=f"{HMIP_DOMAIN}_{entry_suffix}_sysvar_aussen-temperatur",
        config_entry=entry,
    )
    device = entity_registry.async_get_or_create(
        domain="sensor",
        platform=HMIP_DOMAIN,
        unique_id=f"{HMIP_DOMAIN}_vcu1234567_1_state",
        config_entry=entry,
    )

    await _async_migrate_aiohomematic_hub_unique_ids(hass, entry)

    assert (
        entity_registry.async_get(hub.entity_id).unique_id == f"{HMIP_DOMAIN}_{serial_suffix}_sysvar_aussen-temperatur"
    )
    # device keys carry no central prefix → untouched
    assert entity_registry.async_get(device.entity_id).unique_id == f"{HMIP_DOMAIN}_vcu1234567_1_state"


async def test_async_migrate_aiohomematic_hub_unique_ids_without_serial_uses_entry_id(hass: HomeAssistant) -> None:
    """Without a serial the live anchor is ``entry_id[-10:]``; a key already there is a no-op."""
    entry = MockConfigEntry(domain=HMIP_DOMAIN, unique_id=None)
    entry.add_to_hass(hass)
    entry_suffix = entry.entry_id[-10:].lower()  # the live anchor when no serial is known

    entity_registry = er.async_get(hass)
    hub = entity_registry.async_get_or_create(
        domain="sensor",
        platform=HMIP_DOMAIN,
        unique_id=f"{HMIP_DOMAIN}_{entry_suffix}_sysvar_x",
        config_entry=entry,
    )

    await _async_migrate_aiohomematic_hub_unique_ids(hass, entry)

    assert entity_registry.async_get(hub.entity_id).unique_id == f"{HMIP_DOMAIN}_{entry_suffix}_sysvar_x"


async def test_async_migrate_aiohomematic_hub_unique_ids_realigns_stale_anchor(hass: HomeAssistant) -> None:
    """A stale central-id slot (not the live anchor) is realigned, not left to orphan.

    Regression for the disappearing hub / virtual-remote entities: after #1166 the
    live central anchors these keys on the CCU serial. A registry left on an
    unrelated slot (e.g. a prior entry_id from a delete + re-add, or a stale
    serial) fell through the entry_id-only migration and was then permanently
    deleted by the orphan-cleanup sweep. The realign must rewrite whatever slot is
    present onto the live serial — for plain hub keys, virtual-remote keys and the
    virtual-remote event groups alike.
    """
    serial = "3014F711A0001234"
    entry = MockConfigEntry(domain=HMIP_DOMAIN, unique_id=serial)
    entry.add_to_hass(hass)
    serial_suffix = serial[-10:].lower()  # 11a0001234
    stale = "w78v4413eq"  # neither entry_id[-10:] nor the serial suffix
    assert stale not in (entry.entry_id[-10:].lower(), serial_suffix)

    entity_registry = er.async_get(hass)
    hub = entity_registry.async_get_or_create(
        domain="update",
        platform=HMIP_DOMAIN,
        unique_id=f"{HMIP_DOMAIN}_{stale}_hub_system-update",
        config_entry=entry,
    )
    vremote = entity_registry.async_get_or_create(
        domain="button",
        platform=HMIP_DOMAIN,
        unique_id=f"{HMIP_DOMAIN}_{stale}_bidcos_rf_9_press_long",
        config_entry=entry,
    )
    # Calculated DP on an internal heating-group channel: <central-id>_calculated_int...
    # (regression for #3272 — these fell through the realign and were orphan-deleted).
    calculated = entity_registry.async_get_or_create(
        domain="sensor",
        platform=HMIP_DOMAIN,
        unique_id=f"{HMIP_DOMAIN}_{stale}_calculated_int0001234_1_dew_point",
        config_entry=entry,
    )
    event_group = entity_registry.async_get_or_create(
        domain="event",
        platform=HMIP_DOMAIN,
        unique_id=f"{HMIP_DOMAIN}_event_group_keypress_{stale}_bidcos_rf_1",
        config_entry=entry,
    )
    device = entity_registry.async_get_or_create(
        domain="sensor",
        platform=HMIP_DOMAIN,
        unique_id=f"{HMIP_DOMAIN}_0008dd8997b338_1_state",
        config_entry=entry,
    )

    await _async_migrate_aiohomematic_hub_unique_ids(hass, entry)

    assert entity_registry.async_get(hub.entity_id).unique_id == f"{HMIP_DOMAIN}_{serial_suffix}_hub_system-update"
    assert (
        entity_registry.async_get(vremote.entity_id).unique_id
        == f"{HMIP_DOMAIN}_{serial_suffix}_bidcos_rf_9_press_long"
    )
    assert (
        entity_registry.async_get(calculated.entity_id).unique_id
        == f"{HMIP_DOMAIN}_{serial_suffix}_calculated_int0001234_1_dew_point"
    )
    assert (
        entity_registry.async_get(event_group.entity_id).unique_id
        == f"{HMIP_DOMAIN}_event_group_keypress_{serial_suffix}_bidcos_rf_1"
    )
    # device keys carry no central slot -> untouched
    assert entity_registry.async_get(device.entity_id).unique_id == f"{HMIP_DOMAIN}_0008dd8997b338_1_state"


async def test_async_migrate_aiohomematic_hub_unique_ids_skips_on_collision(hass: HomeAssistant) -> None:
    """A stale key whose live-anchored target already exists is left as-is (no crash)."""
    serial = "3014F711A0001234"
    entry = MockConfigEntry(domain=HMIP_DOMAIN, unique_id=serial)
    entry.add_to_hass(hass)
    serial_suffix = serial[-10:].lower()
    stale = "w78v4413eq"

    entity_registry = er.async_get(hass)
    live = entity_registry.async_get_or_create(
        domain="sensor",
        platform=HMIP_DOMAIN,
        unique_id=f"{HMIP_DOMAIN}_{serial_suffix}_sysvar_x",
        config_entry=entry,
    )
    stale_entry = entity_registry.async_get_or_create(
        domain="sensor",
        platform=HMIP_DOMAIN,
        unique_id=f"{HMIP_DOMAIN}_{stale}_sysvar_x",
        config_entry=entry,
    )

    await _async_migrate_aiohomematic_hub_unique_ids(hass, entry)

    # No collision crash: the pre-existing live entry keeps the target id and the
    # stale duplicate is left untouched (the sweep can retire it later).
    assert entity_registry.async_get(live.entity_id).unique_id == f"{HMIP_DOMAIN}_{serial_suffix}_sysvar_x"
    assert entity_registry.async_get(stale_entry.entity_id).unique_id == f"{HMIP_DOMAIN}_{stale}_sysvar_x"


async def test_async_reanchor_on_serial_change_rewrites_and_updates_entry(hass: HomeAssistant) -> None:
    """A changed CCU serial re-anchors hub keys and updates the entry unique_id."""
    old_serial = "3014F711A0001234"  # suffix 11a0001234
    new_serial = "3014F711B0009999"  # suffix 11b0009999
    entry = MockConfigEntry(domain=HMIP_DOMAIN, unique_id=old_serial)
    entry.add_to_hass(hass)

    entity_registry = er.async_get(hass)
    hub = entity_registry.async_get_or_create(
        domain="sensor",
        platform=HMIP_DOMAIN,
        unique_id=f"{HMIP_DOMAIN}_{old_serial[-10:].lower()}_sysvar_x",
        config_entry=entry,
    )

    control = MagicMock()
    control.central.system_information.serial = new_serial

    await _async_reanchor_hub_unique_ids_on_serial_change(hass, entry, control)

    assert entry.unique_id == new_serial
    assert entity_registry.async_get(hub.entity_id).unique_id == f"{HMIP_DOMAIN}_{new_serial[-10:].lower()}_sysvar_x"


@pytest.mark.parametrize("connected", [None, "unknown", "3014F711A0001234"])
async def test_async_reanchor_on_serial_change_noop(hass: HomeAssistant, connected: str | None) -> None:
    """No re-anchor when the serial is unknown or unchanged."""
    serial = "3014F711A0001234"
    entry = MockConfigEntry(domain=HMIP_DOMAIN, unique_id=serial)
    entry.add_to_hass(hass)

    entity_registry = er.async_get(hass)
    hub = entity_registry.async_get_or_create(
        domain="sensor",
        platform=HMIP_DOMAIN,
        unique_id=f"{HMIP_DOMAIN}_{serial[-10:].lower()}_sysvar_x",
        config_entry=entry,
    )

    control = MagicMock()
    control.central.system_information.serial = connected

    await _async_reanchor_hub_unique_ids_on_serial_change(hass, entry, control)

    assert entry.unique_id == serial
    assert entity_registry.async_get(hub.entity_id).unique_id == f"{HMIP_DOMAIN}_{serial[-10:].lower()}_sysvar_x"


class TestHubKeyFromNameSlug:
    """``hub_key_from_name_slug`` rebuilds the pre-id sysvar / program key."""

    _SERIAL = "11a0001234"

    def test_is_idempotent(self) -> None:
        """Feeding the rebuilt key back in yields None rather than looping."""
        once = hub_key_from_name_slug(f"loom_{self._SERIAL}_sysvar_12345", legacy_name="Außen Temperatur")
        assert once is not None
        assert hub_key_from_name_slug(once, legacy_name="Außen Temperatur") is None

    @pytest.mark.parametrize(
        ("unique_id", "legacy_name"),
        [
            # Already on the slug: the producer has no id yet and still falls
            # back to the name. Also the idempotency guard.
            (f"loom_{_SERIAL}_sysvar_aussen-temperatur", "Außen Temperatur"),
            (f"loom_{_SERIAL}_program_my-prog", "My Prog"),
            # Neither family. Hub singletons take their names from module
            # constants, cannot be renamed and were never re-keyed.
            (f"loom_{_SERIAL}_hub_alarm_messages", "Alarm Messages"),
            (f"loom_{_SERIAL}_install_mode_hmip", "Install Mode"),
            # A device key carries no identity slot at all.
            ("loom_vcu1234567_1_state", "irrelevant"),
            # A name that slugifies to nothing must not produce a bare marker
            # key that could collide with something else.
            (f"loom_{_SERIAL}_sysvar_12345", "***"),
        ],
    )
    def test_left_untouched(self, unique_id: str, legacy_name: str) -> None:
        assert hub_key_from_name_slug(unique_id, legacy_name=legacy_name) is None

    @pytest.mark.parametrize(
        ("unique_id", "legacy_name", "expected"),
        [
            # The two renameable families, keyed on the CCU id, rebuilt onto
            # the slug they used to carry.
            (
                f"loom_{_SERIAL}_sysvar_12345",
                "Außen Temperatur",
                f"loom_{_SERIAL}_sysvar_aussen-temperatur",
            ),
            (f"loom_{_SERIAL}_program_1234", "My Prog", f"loom_{_SERIAL}_program_my-prog"),
            # The aiohomematic backend carries no loom_ namespace; the slot
            # swap is the same.
            (f"{_SERIAL}_sysvar_12345", "Außen Temperatur", f"{_SERIAL}_sysvar_aussen-temperatur"),
            # Transliteration matters: a naive lower() would produce
            # "au�en-temperatur" and orphan the entity it was meant to save.
            (f"loom_{_SERIAL}_sysvar_7", "Grüne Straße", f"loom_{_SERIAL}_sysvar_grune-strasse"),
        ],
    )
    def test_rebuilds_the_slug_key(self, unique_id: str, legacy_name: str, expected: str) -> None:
        assert hub_key_from_name_slug(unique_id, legacy_name=legacy_name) == expected


def _build_hub_migration_self(
    hass: HomeAssistant,
    entry_id: str,
    *,
    hub_data_points: tuple[SimpleNamespace, ...],
) -> SimpleNamespace:
    """Build a minimal ControlUnit-shaped self for _async_migrate_hub_keys_from_name_slug."""
    central = MagicMock()
    central.hub_coordinator.get_hub_data_points.return_value = hub_data_points
    return SimpleNamespace(_hass=hass, _entry_id=entry_id, _central=central)


class TestHubKeyMigrationAgainstTheRegistry:
    """The registry walk of the sysvar / program key migration, not just its arithmetic.

    `TestHubKeyFromNameSlug` covers the pure rebuild. This covers what actually
    happens to a registry: which entry keeps its history, what becomes of the
    freshly created twin, and that no rename is attempted onto a key that is
    already taken — the "unique id already in use" that aborts a config entry.
    """

    @pytest.fixture(autouse=True)
    def scheduled_reload(self, hass: HomeAssistant) -> Iterator[MagicMock]:
        """Capture the reload the migration schedules instead of performing it."""
        with patch.object(hass.config_entries, "async_schedule_reload") as scheduled:
            yield scheduled

    _SERIAL = "11a0001234"

    async def test_historied_entry_takes_the_id_key(
        self, hass: HomeAssistant, mock_config_entry_v2: MockConfigEntry, scheduled_reload: MagicMock
    ) -> None:
        """The pre-upgrade entry keeps its entity_id and gains the new key."""
        mock_config_entry_v2.add_to_hass(hass)
        old = self._seed(
            hass,
            mock_config_entry_v2,
            unique_id=f"loom_{self._SERIAL}_sysvar_aussen-temperatur",
            entity_suffix="aussen_temperatur",
        )

        fake_self = _build_hub_migration_self(
            hass,
            mock_config_entry_v2.entry_id,
            hub_data_points=(
                SimpleNamespace(unique_id=f"loom_{self._SERIAL}_sysvar_12345", legacy_name="Außen Temperatur"),
            ),
        )
        ControlUnit._async_migrate_hub_keys_from_name_slug(fake_self)

        entity_registry = er.async_get(hass)
        migrated = entity_registry.async_get(old.entity_id)
        assert migrated is not None, "the historied entry was removed instead of migrated"
        assert migrated.unique_id == f"{HMIP_DOMAIN}_loom_{self._SERIAL}_sysvar_12345"
        # The renamed entry has no live entity: the one that existed was bound
        # to the twin this pass just removed. Without the reload it stays gone
        # until the user restarts — the two restarts an update used to need.
        scheduled_reload.assert_called_once_with(mock_config_entry_v2.entry_id)

    async def test_second_run_changes_nothing(
        self, hass: HomeAssistant, mock_config_entry_v2: MockConfigEntry, scheduled_reload: MagicMock
    ) -> None:
        """Idempotent: the pass runs on every start-up, not only the first."""
        mock_config_entry_v2.add_to_hass(hass)
        self._seed(
            hass,
            mock_config_entry_v2,
            unique_id=f"loom_{self._SERIAL}_sysvar_aussen-temperatur",
            entity_suffix="aussen_temperatur",
        )
        fake_self = _build_hub_migration_self(
            hass,
            mock_config_entry_v2.entry_id,
            hub_data_points=(
                SimpleNamespace(unique_id=f"loom_{self._SERIAL}_sysvar_12345", legacy_name="Außen Temperatur"),
            ),
        )
        ControlUnit._async_migrate_hub_keys_from_name_slug(fake_self)
        entity_registry = er.async_get(hass)
        after_first = {
            (entry.entity_id, entry.unique_id)
            for entry in er.async_entries_for_config_entry(entity_registry, mock_config_entry_v2.entry_id)
        }

        ControlUnit._async_migrate_hub_keys_from_name_slug(fake_self)
        after_second = {
            (entry.entity_id, entry.unique_id)
            for entry in er.async_entries_for_config_entry(entity_registry, mock_config_entry_v2.entry_id)
        }
        assert after_second == after_first
        # And the reload does not repeat — a pass that migrates nothing
        # schedules nothing, so this cannot become a loop.
        scheduled_reload.assert_called_once_with(mock_config_entry_v2.entry_id)

    async def test_a_later_migrating_pass_does_not_reload_again(
        self, hass: HomeAssistant, mock_config_entry_v2: MockConfigEntry, scheduled_reload: MagicMock
    ) -> None:
        """A pass that migrates after the reload already ran asks for nothing.

        Idempotency makes a second migrating pass unreachable in theory, which
        is exactly why this is pinned by construction: if it ever were reached,
        reloading on every one of them would put the config entry in a loop.
        """
        mock_config_entry_v2.add_to_hass(hass)
        self._seed(
            hass,
            mock_config_entry_v2,
            unique_id=f"loom_{self._SERIAL}_sysvar_aussen-temperatur",
            entity_suffix="aussen_temperatur",
        )
        ControlUnit._async_migrate_hub_keys_from_name_slug(
            _build_hub_migration_self(
                hass,
                mock_config_entry_v2.entry_id,
                hub_data_points=(
                    SimpleNamespace(unique_id=f"loom_{self._SERIAL}_sysvar_12345", legacy_name="Außen Temperatur"),
                ),
            )
        )
        scheduled_reload.assert_called_once_with(mock_config_entry_v2.entry_id)

        # A second, genuinely migrating pass — a different variable this time.
        self._seed(
            hass,
            mock_config_entry_v2,
            unique_id=f"loom_{self._SERIAL}_sysvar_luftfeuchte",
            entity_suffix="luftfeuchte",
        )
        ControlUnit._async_migrate_hub_keys_from_name_slug(
            _build_hub_migration_self(
                hass,
                mock_config_entry_v2.entry_id,
                hub_data_points=(
                    SimpleNamespace(unique_id=f"loom_{self._SERIAL}_sysvar_67890", legacy_name="Luftfeuchte"),
                ),
            )
        )

        entity_registry = er.async_get(hass)
        assert {
            entry.unique_id
            for entry in er.async_entries_for_config_entry(entity_registry, mock_config_entry_v2.entry_id)
        } == {
            f"{HMIP_DOMAIN}_loom_{self._SERIAL}_sysvar_12345",
            f"{HMIP_DOMAIN}_loom_{self._SERIAL}_sysvar_67890",
        }, "the second pass did not migrate, so it does not test the guard"
        scheduled_reload.assert_called_once_with(mock_config_entry_v2.entry_id)

    async def test_two_sysvars_differing_only_in_punctuation(
        self, hass: HomeAssistant, mock_config_entry_v2: MockConfigEntry
    ) -> None:
        """The collision the id-keying exists to end, replayed end to end.

        `Alarm: Küche` and `Alarm Küche` both slug to `alarm-kuche`, so before
        the change they produced byte-identical keys and Home Assistant kept
        whichever arrived first — the other variable had no entity at all.

        After it they have distinct vids. The platform has already created both
        freshly-keyed twins by the time this runs, so the migration has to hand
        the surviving history to one of them and leave the other alone, without
        ever attempting a rename onto a key that exists.
        """
        mock_config_entry_v2.add_to_hass(hass)
        entity_registry = er.async_get(hass)

        # What a pre-upgrade registry actually holds: one entry, because the
        # second variable collided and never got one.
        historied = self._seed(
            hass,
            mock_config_entry_v2,
            unique_id=f"loom_{self._SERIAL}_sysvar_alarm-kuche",
            entity_suffix="alarm_kuche",
        )
        # And the two twins the platform spawned on this start-up.
        twin_a = self._seed(
            hass, mock_config_entry_v2, unique_id=f"loom_{self._SERIAL}_sysvar_12345", entity_suffix="twin_a"
        )
        twin_b = self._seed(
            hass, mock_config_entry_v2, unique_id=f"loom_{self._SERIAL}_sysvar_12346", entity_suffix="twin_b"
        )

        fake_self = _build_hub_migration_self(
            hass,
            mock_config_entry_v2.entry_id,
            hub_data_points=(
                SimpleNamespace(unique_id=f"loom_{self._SERIAL}_sysvar_12345", legacy_name="Alarm: Küche"),
                SimpleNamespace(unique_id=f"loom_{self._SERIAL}_sysvar_12346", legacy_name="Alarm Küche"),
            ),
        )
        ControlUnit._async_migrate_hub_keys_from_name_slug(fake_self)

        surviving = entity_registry.async_get(historied.entity_id)
        assert surviving is not None, "the entry holding the history was removed"
        assert surviving.unique_id in {
            f"{HMIP_DOMAIN}_loom_{self._SERIAL}_sysvar_12345",
            f"{HMIP_DOMAIN}_loom_{self._SERIAL}_sysvar_12346",
        }

        # Two variables, two entities: the other twin is untouched, and the one
        # whose key the historied entry took is gone.
        remaining = {
            entry.unique_id
            for entry in er.async_entries_for_config_entry(entity_registry, mock_config_entry_v2.entry_id)
        }
        assert remaining == {
            f"{HMIP_DOMAIN}_loom_{self._SERIAL}_sysvar_12345",
            f"{HMIP_DOMAIN}_loom_{self._SERIAL}_sysvar_12346",
        }, f"expected exactly the two id-keyed entities, got {sorted(remaining)}"
        assert surviving.entity_id in {
            entry.entity_id
            for entry in er.async_entries_for_config_entry(entity_registry, mock_config_entry_v2.entry_id)
        }
        # Whichever twin lost its key was removed, not left as a duplicate.
        survivors = {twin_a.entity_id, twin_b.entity_id, historied.entity_id}
        live = {
            entry.entity_id
            for entry in er.async_entries_for_config_entry(entity_registry, mock_config_entry_v2.entry_id)
        }
        assert len(live) == 2, f"expected two entities, got {sorted(live)}"
        assert live <= survivors

    def _seed(
        self,
        hass: HomeAssistant,
        entry: MockConfigEntry,
        *,
        unique_id: str,
        entity_suffix: str,
    ) -> er.RegistryEntry:
        return er.async_get(hass).async_get_or_create(
            domain="sensor",
            platform=HMIP_DOMAIN,
            unique_id=f"{HMIP_DOMAIN}_{unique_id}",
            suggested_object_id=entity_suffix,
            config_entry=entry,
        )


class TestDeviceIdentifierMigration:
    """The device registry walk that moves entries onto the backend-neutral key.

    Both backends compose ``<address>@<central>-<interface>`` but disagree on
    the leading component — aiohomematic uses the HA instance name, the loom
    daemon its own CCU name. Every device entry keyed the daemon's way has to
    move, or a backend switch leaves the ``device_id`` (and with it the area,
    the custom name and every automation) behind on an entry nothing writes to
    any more.
    """

    _ADDRESS = "0001D8A991F2DC"
    _DAEMON_CENTRAL = "Otto"

    async def test_ambiguous_central_name_is_skipped(
        self, hass: HomeAssistant, mock_config_entry_v2: MockConfigEntry
    ) -> None:
        """A CCU named after an interface makes the split ambiguous — skip, don't guess."""
        mock_config_entry_v2.add_to_hass(hass)
        ambiguous = f"{self._ADDRESS}{IDENTIFIER_SEPARATOR}my-CUxD-box-HmIP-RF"
        seeded = self._seed_device(hass, mock_config_entry_v2, identifier=ambiguous, name="Seltsam")

        _async_migrate_device_identifiers(hass, mock_config_entry_v2)

        device_registry = dr.async_get(hass)
        assert device_registry.async_get(seeded.id).identifiers == {(HMIP_DOMAIN, ambiguous)}

    async def test_central_device_is_untouched(
        self, hass: HomeAssistant, mock_config_entry_v2: MockConfigEntry
    ) -> None:
        """The central's own entry carries no address and is already backend-neutral."""
        mock_config_entry_v2.add_to_hass(hass)
        seeded = self._seed_device(hass, mock_config_entry_v2, identifier=const.INSTANCE_NAME, name=const.INSTANCE_NAME)

        _async_migrate_device_identifiers(hass, mock_config_entry_v2)

        device_registry = dr.async_get(hass)
        assert device_registry.async_get(seeded.id).identifiers == {(HMIP_DOMAIN, const.INSTANCE_NAME)}

    async def test_daemon_keyed_entry_is_renamed_in_place(
        self, hass: HomeAssistant, mock_config_entry_v2: MockConfigEntry
    ) -> None:
        """The device_id survives — that is the whole point of the pass."""
        mock_config_entry_v2.add_to_hass(hass)
        seeded = self._seed_device(
            hass, mock_config_entry_v2, identifier=self._daemon_identifier(), name="Waschmaschine"
        )

        _async_migrate_device_identifiers(hass, mock_config_entry_v2)

        device_registry = dr.async_get(hass)
        migrated = device_registry.async_get(seeded.id)
        assert migrated is not None, "the entry was removed instead of migrated"
        assert migrated.identifiers == {(HMIP_DOMAIN, self._neutral_identifier())}
        assert migrated.name == "Waschmaschine"

    async def test_direct_ccu_entries_are_left_alone(
        self, hass: HomeAssistant, mock_config_entry_v2: MockConfigEntry
    ) -> None:
        """Negative control: on the direct-CCU backend the key is already neutral.

        aiohomematic composes its interface id as ``<instance_name>-<interface>``,
        so its identifier *is* the target. Nothing may move — this is what makes
        the migration a no-op for the vast majority of installations.
        """
        mock_config_entry_v2.add_to_hass(hass)
        seeded = self._seed_device(
            hass, mock_config_entry_v2, identifier=self._neutral_identifier(), name="Waschmaschine"
        )

        _async_migrate_device_identifiers(hass, mock_config_entry_v2)

        device_registry = dr.async_get(hass)
        unchanged = device_registry.async_get(seeded.id)
        assert unchanged is not None
        assert unchanged.identifiers == {(HMIP_DOMAIN, self._neutral_identifier())}

    async def test_merge_keeps_the_older_device_id(
        self, hass: HomeAssistant, mock_config_entry_v2: MockConfigEntry
    ) -> None:
        """A registry after a switch that already happened holds both entries.

        The one on the neutral key is the pre-switch entry — the one carrying
        the area, the custom name and the automations. So its device_id wins,
        and the daemon-keyed entry hands over its entities and children.
        """
        mock_config_entry_v2.add_to_hass(hass)
        older = self._seed_device(
            hass, mock_config_entry_v2, identifier=self._neutral_identifier(), name="Waschmaschine"
        )
        daemon_keyed = self._seed_device(
            hass, mock_config_entry_v2, identifier=self._daemon_identifier(), name="Waschmaschine"
        )
        child = self._seed_device(
            hass,
            mock_config_entry_v2,
            identifier=self._daemon_identifier(suffix="-6"),
            name="Waschmaschine Kanal 6",
            via_device_id=daemon_keyed.id,
        )
        entity_registry = er.async_get(hass)
        live = entity_registry.async_get_or_create(
            domain="switch",
            platform=HMIP_DOMAIN,
            unique_id=f"{HMIP_DOMAIN}_loom_{self._ADDRESS}_4_STATE",
            device_id=daemon_keyed.id,
            config_entry=mock_config_entry_v2,
        )

        _async_migrate_device_identifiers(hass, mock_config_entry_v2)

        device_registry = dr.async_get(hass)
        assert device_registry.async_get(daemon_keyed.id) is None, "the stale entry was left behind"
        survivor = device_registry.async_get(older.id)
        assert survivor is not None, "the entry holding the history was removed"
        assert survivor.identifiers == {(HMIP_DOMAIN, self._neutral_identifier())}
        assert entity_registry.async_get(live.entity_id).device_id == older.id
        # The child moved onto the survivor and took the neutral key with it.
        migrated_child = device_registry.async_get(child.id)
        assert migrated_child.via_device_id == older.id
        assert migrated_child.identifiers == {(HMIP_DOMAIN, self._neutral_identifier(suffix="-6"))}

    async def test_second_run_changes_nothing(self, hass: HomeAssistant, mock_config_entry_v2: MockConfigEntry) -> None:
        """Idempotent: the pass runs on every start-up, not only the first."""
        mock_config_entry_v2.add_to_hass(hass)
        self._seed_device(hass, mock_config_entry_v2, identifier=self._daemon_identifier(), name="Waschmaschine")

        _async_migrate_device_identifiers(hass, mock_config_entry_v2)
        device_registry = dr.async_get(hass)
        after_first = {
            (device.id, tuple(sorted(device.identifiers)))
            for device in dr.async_entries_for_config_entry(device_registry, mock_config_entry_v2.entry_id)
        }

        _async_migrate_device_identifiers(hass, mock_config_entry_v2)
        after_second = {
            (device.id, tuple(sorted(device.identifiers)))
            for device in dr.async_entries_for_config_entry(device_registry, mock_config_entry_v2.entry_id)
        }
        assert after_second == after_first

    async def test_sub_device_and_schedule_suffixes_survive(
        self, hass: HomeAssistant, mock_config_entry_v2: MockConfigEntry
    ) -> None:
        """The suffix rides behind the interface and must not be swallowed."""
        mock_config_entry_v2.add_to_hass(hass)
        for suffix in ("-6", "-schedule"):
            self._seed_device(
                hass, mock_config_entry_v2, identifier=self._daemon_identifier(suffix=suffix), name=f"Sub{suffix}"
            )

        _async_migrate_device_identifiers(hass, mock_config_entry_v2)

        device_registry = dr.async_get(hass)
        assert {
            identifier
            for device in dr.async_entries_for_config_entry(device_registry, mock_config_entry_v2.entry_id)
            for _, identifier in device.identifiers
        } == {self._neutral_identifier(suffix="-6"), self._neutral_identifier(suffix="-schedule")}

    def _daemon_identifier(self, *, suffix: str = "") -> str:
        return f"{self._ADDRESS}{IDENTIFIER_SEPARATOR}{self._DAEMON_CENTRAL}-HmIP-RF{suffix}"

    def _neutral_identifier(self, *, suffix: str = "") -> str:
        return f"{self._ADDRESS}{IDENTIFIER_SEPARATOR}{const.INSTANCE_NAME}-HmIP-RF{suffix}"

    def _seed_device(
        self,
        hass: HomeAssistant,
        entry: MockConfigEntry,
        *,
        identifier: str,
        name: str,
        via_device_id: str | None = None,
    ) -> dr.DeviceEntry:
        """Register a device entry under one homematicip_local identifier."""
        device_registry = dr.async_get(hass)
        return device_registry.async_get_or_create(
            config_entry_id=entry.entry_id,
            identifiers={(HMIP_DOMAIN, identifier)},
            name=name,
            via_device_id=via_device_id,
        )


class TestDeviceIdentifierMigrationAtScale:
    """The migration against a registry shaped like a real one after a switch.

    A live installation reported 190 device entries becoming 380 on the switch
    to openccu-loom: every entry got a twin, base devices, sub devices and
    schedule devices alike. That is the shape this replays — the per-case class
    above covers one entry at a time, this covers all of them at once, in the
    proportions a real registry has (1 central, 124 base devices, 19 sub
    devices, 46 schedule devices).
    """

    _DAEMON_CENTRAL = "Otto"
    _BASE_DEVICES = 124
    _SUB_DEVICES = 19
    _SCHEDULE_DEVICES = 46

    async def test_a_doubled_registry_collapses_back_onto_the_original_device_ids(
        self, hass: HomeAssistant, mock_config_entry_v2: MockConfigEntry
    ) -> None:
        """380 entries become 190 again, and every surviving device_id is the pre-switch one."""
        mock_config_entry_v2.add_to_hass(hass)
        device_registry = dr.async_get(hass)
        entity_registry = er.async_get(hass)

        # The central carries no address and must come through untouched.
        central = device_registry.async_get_or_create(
            config_entry_id=mock_config_entry_v2.entry_id,
            identifiers={(HMIP_DOMAIN, const.INSTANCE_NAME)},
            name=const.INSTANCE_NAME,
        )

        addresses = self._addresses()
        expected_device_ids: dict[str, str] = {}
        live_entities: dict[str, str] = {}
        for index, address in enumerate(addresses):
            suffixes = [""]
            if index < self._SUB_DEVICES:
                suffixes.append("-4")
            if index < self._SCHEDULE_DEVICES:
                suffixes.append("-schedule")
            for suffix in suffixes:
                pre_switch, twin = self._seed_pair(hass, mock_config_entry_v2, address=address, suffix=suffix)
                key = f"{address}{suffix}"
                expected_device_ids[key] = pre_switch.id
                # The live entity sits on the twin — that is where the loom
                # backend put it — and has to end up on the pre-switch entry.
                live_entities[key] = entity_registry.async_get_or_create(
                    domain="switch",
                    platform=HMIP_DOMAIN,
                    unique_id=f"{HMIP_DOMAIN}_loom_{key}_STATE",
                    device_id=twin.id,
                    config_entry=mock_config_entry_v2,
                ).entity_id

        seeded = dr.async_entries_for_config_entry(device_registry, mock_config_entry_v2.entry_id)
        assert len(seeded) == 2 * (self._BASE_DEVICES + self._SUB_DEVICES + self._SCHEDULE_DEVICES) + 1

        _async_migrate_device_identifiers(hass, mock_config_entry_v2)

        surviving = dr.async_entries_for_config_entry(device_registry, mock_config_entry_v2.entry_id)
        assert len(surviving) == self._BASE_DEVICES + self._SUB_DEVICES + self._SCHEDULE_DEVICES + 1

        # Every device_id is the pre-switch one — the automations' anchor.
        for key, device_id in expected_device_ids.items():
            assert device_registry.async_get(device_id) is not None, f"{key} lost its pre-switch device_id"
            assert entity_registry.async_get(live_entities[key]).device_id == device_id, (
                f"the live entity of {key} did not move onto the pre-switch entry"
            )

        # No daemon-keyed identifier is left anywhere.
        assert not [
            identifier
            for device in surviving
            for _, identifier in device.identifiers
            if f"{self._DAEMON_CENTRAL}-HmIP-RF" in identifier
        ]
        assert device_registry.async_get(central.id).identifiers == {(HMIP_DOMAIN, const.INSTANCE_NAME)}

    def _addresses(self) -> list[str]:
        return [f"0001D8A9{index:06X}" for index in range(self._BASE_DEVICES)]

    def _seed_pair(
        self,
        hass: HomeAssistant,
        entry: MockConfigEntry,
        *,
        address: str,
        suffix: str = "",
    ) -> tuple[dr.DeviceEntry, dr.DeviceEntry]:
        """Seed the pre-switch entry and the twin the loom backend created."""
        device_registry = dr.async_get(hass)
        pre_switch = device_registry.async_get_or_create(
            config_entry_id=entry.entry_id,
            identifiers={(HMIP_DOMAIN, f"{address}{IDENTIFIER_SEPARATOR}{const.INSTANCE_NAME}-HmIP-RF{suffix}")},
            name=f"Device {address}{suffix}",
        )
        twin = device_registry.async_get_or_create(
            config_entry_id=entry.entry_id,
            identifiers={(HMIP_DOMAIN, f"{address}{IDENTIFIER_SEPARATOR}{self._DAEMON_CENTRAL}-HmIP-RF{suffix}")},
            name=f"Device {address}{suffix}",
        )
        return pre_switch, twin


class TestStaleIssueCleanup:
    """A repair nothing can withdraw any more is withdrawn by the next setup.

    The connection repair is raised from a ``connection_state`` event and
    taken back by the opposite one — and that one is only published for an
    interface the central's connection state tracker holds. The tracker is
    rebuilt empty with every setup of the entry, so a repair that outlived a
    reload (a CCU host change and its reconfigure is the ordinary way there)
    would have stayed visible next to two healthy connection sensors for as
    long as the entry was never torn down again.
    """

    _INTERFACE_ID = f"{const.INSTANCE_NAME}-HmIP-RF"

    @staticmethod
    def _control_unit(hass: HomeAssistant, entry: MockConfigEntry) -> SimpleNamespace:
        """Return the attributes the issue handlers of a control unit read."""
        return SimpleNamespace(_hass=hass, _entry_id=entry.entry_id, _instance_name=const.INSTANCE_NAME)

    @staticmethod
    def _issue_ids(hass: HomeAssistant) -> set[str]:
        return {issue_id for domain, issue_id in ir.async_get(hass).issues if domain == HMIP_DOMAIN}

    async def test_a_callback_repair_is_withdrawn_for_any_interface_id(
        self, hass: HomeAssistant, mock_config_entry_v2: MockConfigEntry
    ) -> None:
        """The sweep reads the ids out of the registry instead of rebuilding them.

        The cleanup this replaces composed ``{instance_name}-{interface}`` to
        address the repair, which is the aiohomematic interface id. On the
        openccu-loom backend the daemon names the leading component itself, so
        a repair raised there was never addressed by the id the integration
        built for it.
        """
        interface_id = "OttoDev-HmIP-RF"
        assert not interface_id.startswith(const.INSTANCE_NAME)
        ControlUnit._handle_callback_state(
            self._control_unit(hass, mock_config_entry_v2),
            SystemStatusChangedEvent(timestamp=datetime.now(), callback_state=(interface_id, False)),
        )
        issue_id = get_issue_id(
            entry_id=mock_config_entry_v2.entry_id, issue_type=ISSUE_TYPE_CALLBACK, interface_id=interface_id
        )
        assert issue_id in self._issue_ids(hass)

        _cleanup_stale_issues(hass=hass, entry_id=mock_config_entry_v2.entry_id)

        assert issue_id not in self._issue_ids(hass)

    async def test_a_connection_repair_from_a_previous_session_is_withdrawn(
        self, hass: HomeAssistant, mock_config_entry_v2: MockConfigEntry
    ) -> None:
        """The reported case: the repair survived the reload, nothing took it back."""
        issue_id = self._raise_connection_repair(hass, mock_config_entry_v2)
        assert issue_id in self._issue_ids(hass)

        _cleanup_stale_issues(hass=hass, entry_id=mock_config_entry_v2.entry_id)

        assert issue_id not in self._issue_ids(hass)

    async def test_a_fault_that_is_still_present_raises_the_repair_again(
        self, hass: HomeAssistant, mock_config_entry_v2: MockConfigEntry
    ) -> None:
        """Withdrawing on setup must not hide an interface that is still down."""
        issue_id = self._raise_connection_repair(hass, mock_config_entry_v2)
        _cleanup_stale_issues(hass=hass, entry_id=mock_config_entry_v2.entry_id)
        assert issue_id not in self._issue_ids(hass)

        assert self._raise_connection_repair(hass, mock_config_entry_v2) == issue_id
        assert issue_id in self._issue_ids(hass)

    async def test_other_repairs_and_other_entries_are_left_alone(
        self, hass: HomeAssistant, mock_config_entry_v2: MockConfigEntry
    ) -> None:
        """Only the types that cannot withdraw themselves are swept, and only for this entry."""
        foreign_entry_id = f"{mock_config_entry_v2.entry_id}9"
        survivors = {
            # A client repair is taken back by the CONNECTED transition every
            # fresh client makes, so it withdraws itself.
            get_issue_id(
                entry_id=mock_config_entry_v2.entry_id,
                issue_type=ISSUE_TYPE_CLIENT,
                interface_id=self._INTERFACE_ID,
            ): "client_failed",
            # A paramset inconsistency is a data problem, not a transport state.
            get_issue_id(
                entry_id=mock_config_entry_v2.entry_id,
                issue_type="paramset_inconsistency",
                interface_id=self._INTERFACE_ID,
            ): "paramset_inconsistency",
            f"{mock_config_entry_v2.entry_id}_central_failed": "central_failed",
            get_issue_id(
                entry_id=foreign_entry_id, issue_type=ISSUE_TYPE_CONNECTION, interface_id=self._INTERFACE_ID
            ): "connection_failed",
        }
        for issue_id, translation_key in survivors.items():
            ir.async_create_issue(
                hass=hass,
                domain=HMIP_DOMAIN,
                issue_id=issue_id,
                is_fixable=False,
                severity=ir.IssueSeverity.ERROR,
                translation_key=translation_key,
            )
        swept = self._raise_connection_repair(hass, mock_config_entry_v2)

        _cleanup_stale_issues(hass=hass, entry_id=mock_config_entry_v2.entry_id)

        issue_ids = self._issue_ids(hass)
        assert swept not in issue_ids
        assert set(survivors) <= issue_ids

    def _raise_connection_repair(self, hass: HomeAssistant, entry: MockConfigEntry) -> str:
        """Let a control unit raise the repair, so the id under test is the real one."""
        ControlUnit._handle_connection_state(
            self._control_unit(hass, entry),
            SystemStatusChangedEvent(timestamp=datetime.now(), connection_state=(self._INTERFACE_ID, False)),
        )
        return get_issue_id(entry_id=entry.entry_id, issue_type=ISSUE_TYPE_CONNECTION, interface_id=self._INTERFACE_ID)
