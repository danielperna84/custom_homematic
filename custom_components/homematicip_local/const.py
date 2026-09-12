"""Constants."""

from __future__ import annotations

from enum import StrEnum
from typing import Final

from aiohomematic.const import CATEGORIES
from homeassistant.const import Platform

DOMAIN: Final = "homematicip_local"
HMIP_LOCAL_MIN_HA_VERSION: Final = "2026.8.0"

# The openccu-loom alarm system gets a device registry object of its own
# instead of hanging off a CCU. Alarm zones are daemon-level and may hold
# sensors of several CCUs, so attributing them to one central states a
# belonging that does not exist — which is also why the daemon's MQTT plane
# omits the `<central>` segment from its alarm topics. The identifier is the
# daemon's own (`alarm_discovery.go`, `alarmDeviceBlock`), so an installation
# running both bridges sees one alarm device rather than two; it also matches
# the scope of the panel unique_ids, which the daemon computes daemon-wide
# rather than per central.
ALARM_DEVICE_IDENTIFIER: Final = "openccu-loom_alarm"
ALARM_DEVICE_MANUFACTURER: Final = "OpenCCU-Loom"
ALARM_DEVICE_NAME: Final = "OpenCCU-Loom Alarm"

ENABLE_EXPERIMENTAL_FEATURES: Final = False
CLIMATE_SCHEDULE_API_VERSION: Final = "v2.0"
SCHEDULE_API_VERSION: Final = "v1.0"

DEFAULT_AUTO_CONFIRM_NEW_DEVICES_TIMEOUT: Final = 600  # 10 minutes in seconds
DEFAULT_BACKUP_PATH: Final = "backup"
DEFAULT_ENABLE_DEVICE_FIRMWARE_CHECK: Final = True
DEFAULT_ENABLE_SYSTEM_NOTIFICATIONS: Final = True
DEFAULT_LISTEN_ON_ALL_IP: Final = False
DEFAULT_ENABLE_LIGHT_LAST_BRIGHTNESS: Final = False
DEFAULT_ENABLE_MQTT: Final = False
DEFAULT_MQTT_PREFIX: Final = ""
DEFAULT_DISABLE_CONFIG_PANEL: Final = False
DEFAULT_ENABLE_SUB_DEVICES: Final = False
# The loom backend defaults sub-device entities to enabled in its setup flow.
DEFAULT_LOOM_ENABLE_SUB_DEVICES: Final = True
DEFAULT_COMMAND_RETRY_MAX_ATTEMPTS: Final = 3
DEFAULT_COMMAND_THROTTLE_INTERVAL: Final = 0.1

DEFAULT_SYS_SCAN_INTERVAL: Final = 30

LEARN_MORE_URL_XMLRPC_SERVER_RECEIVES_NO_EVENTS: Final = "https://github.com/sukramj/homematicip_local?tab=readme-ov-file#what-is-the-meaning-of-xmlrpc-server-received-no-events--xmlrpc-server-empf%C3%A4ngt-keine-ereignisse"
LEARN_MORE_URL_PONG_MISMATCH: Final = "https://github.com/sukramj/homematicip_local#what-is-the-meaning-of-pending-pong-mismatch-on-interface--austehende-pong-ereignisse-auf-interface"

# Type component of the repair issue ids the integration composes itself
# (see support.get_issue_id). The issue registry does not persist the
# translation key, so the type has to travel in the id.
ISSUE_TYPE_CALLBACK: Final = "callback"
ISSUE_TYPE_CLIENT: Final = "client"
ISSUE_TYPE_CONNECTION: Final = "connection"

CONF_ADVANCED_CONFIG: Final = "advanced_config"
CONF_COMMAND_RETRY_MAX_ATTEMPTS: Final = "command_retry_max_attempts"
CONF_COMMAND_THROTTLE_INTERVAL: Final = "command_throttle_interval"
CONF_BACKUP_PATH: Final = "backup_path"
CONF_CALLBACK_HOST: Final = "callback_host"
CONF_CALLBACK_PORT_XML_RPC: Final = "callback_port_xml_rpc"
CONF_DELAY_NEW_DEVICE_CREATION: Final = "delay_new_device_creation"
CONF_ENABLE_LIGHT_LAST_BRIGHTNESS: Final = "light_last_brightness_enabled"
CONF_ENABLE_MQTT: Final = "mqtt_enabled"
CONF_ENABLE_PROGRAM_SCAN: Final = "program_scan_enabled"
CONF_ENABLE_SUB_DEVICES: Final = "sub_devices_enabled"
CONF_ENABLE_SYSTEM_NOTIFICATIONS: Final = "enable_system_notifications"
CONF_ENABLE_SYSVAR_SCAN: Final = "sysvar_scan_enabled"
CONF_EVENT_TYPE: Final = "event_type"
CONF_OPTIONAL_SETTINGS: Final = "optional_settings"
CONF_INSTANCE_NAME: Final = "instance_name"
CONF_INTERFACE: Final = "interface"

# ---- Backend selection (aiohomematic direct-CCU vs. openccu-loom daemon) ----
# The integration can talk to a CCU directly via aiohomematic, or to an
# openccu-loom daemon via openccu-loom-client's aiohomematic-compatible
# adapter. The backend is chosen once per config entry.
CONF_BACKEND: Final = "backend"
BACKEND_CCU: Final = "ccu"  # aiohomematic, direct XML/JSON-RPC to the CCU
BACKEND_LOOM: Final = "loom"  # openccu-loom daemon via REST/WebSocket
DEFAULT_BACKEND: Final = BACKEND_CCU
# The loom backend needs no master switch: the config flow offers it exactly
# when it is relevant — an mDNS-discovered daemon or an existing loom entry.
# Loom-only connection inputs. Host/TLS reuse CONF_HOST/CONF_TLS; the
# daemon authenticates with a bearer token (or falls back to user/pass).
CONF_LOOM_TOKEN: Final = "loom_token"  # noqa: S105 - config key name, not a secret
CONF_LOOM_PORT: Final = "loom_port"
CONF_INTERFACE_ID: Final = "interface_id"
CONF_JSON_PORT: Final = "json_port"
CONF_LISTEN_ON_ALL_IP: Final = "listen_on_all_ip"
CONF_MQTT_PREFIX: Final = "mqtt_prefix"
CONF_PROGRAM_MARKERS: Final = "program_markers"
CONF_SUBTYPE: Final = "subtype"
CONF_SYSVAR_MARKERS: Final = "sysvar_markers"
CONF_SYS_SCAN_INTERVAL: Final = "sysvar_scan_interval"
CONF_TLS: Final = "tls"
CONF_UN_IGNORES: Final = "un_ignore"
CONF_USE_GROUP_CHANNEL_FOR_COVER_STATE: Final = "use_group_channel_for_cover_state"
CONF_VERIFY_TLS: Final = "verify_tls"

# New constants for simplified config flow (v12)
CONF_DISABLE_CONFIG_PANEL: Final = "disable_config_panel"
CONF_CUSTOM_PORTS: Final = "custom_ports"  # Dict of custom interface ports
CONF_CUSTOM_PORT_CONFIG: Final = "custom_port_config"  # Checkbox for custom port configuration
CONF_SKIP_BACKEND_DETECTION: Final = "skip_backend_detection"  # Checkbox to skip backend detection

# Non-admin permission scopes (stored in config entry options)
CONF_NON_ADMIN_PERMISSIONS: Final = "non_admin_permissions"

EVENT_ADDRESS: Final = "address"
EVENT_CHANNEL_NO: Final = "channel_no"
EVENT_DEVICE_ADDRESS: Final = "device_address"
EVENT_DEVICE_ID: Final = "device_id"
EVENT_ERROR: Final = "error"
EVENT_ERROR_VALUE: Final = "error_value"
EVENT_IDENTIFIER: Final = "identifier"
EVENT_INTERFACE_ID: Final = "interface_id"
EVENT_MESSAGE: Final = "message"
EVENT_MODEL: Final = "model"
EVENT_NAME: Final = "name"
EVENT_PARAMETER: Final = "parameter"
EVENT_TITLE: Final = "title"
EVENT_UNAVAILABLE: Final = "unavailable"
EVENT_VALUE: Final = "value"

# Optimistic rollback event constants
EVENT_AGE_SECONDS: Final = "age_seconds"
EVENT_REASON: Final = "reason"
EVENT_RESTORED_VALUE: Final = "restored_value"
EVENT_ROLLED_BACK_VALUE: Final = "rolled_back_value"


class HmipLocalServices(StrEnum):
    """Enum with services."""

    ADD_LINK = "add_link"
    CLEAR_CACHE = "clear_cache"
    CONFIRM_ALL_DELAYED_DEVICES = "confirm_all_delayed_devices"
    CLEAR_TEXT_DISPLAY = "clear_text_display"
    COPY_SCHEDULE = "copy_schedule"
    COPY_SCHEDULE_PROFILE = "copy_schedule_profile"
    CREATE_CCU_BACKUP = "create_ccu_backup"
    CREATE_CENTRAL_LINKS = "create_central_links"
    DISABLE_AWAY_MODE = "disable_away_mode"
    ENABLE_AWAY_MODE_BY_CALENDAR = "enable_away_mode_by_calendar"
    ENABLE_AWAY_MODE_BY_DURATION = "enable_away_mode_by_duration"
    EXPORT_DEVICE_DEFINITION = "export_device_definition"
    FETCH_SYSTEM_VARIABLES = "fetch_system_variables"
    FORCE_DEVICE_AVAILABILITY = "force_device_availability"
    GET_DEVICE_VALUE = "get_device_value"
    GET_LINK_PARAMSET = "get_link_paramset"
    GET_LINK_PEERS = "get_link_peers"
    GET_PARAMSET = "get_paramset"
    GET_SCHEDULE = "get_schedule"
    GET_SCHEDULE_PROFILE = "get_schedule_profile"
    GET_SCHEDULE_WEEKDAY = "get_schedule_weekday"
    GET_VARIABLE_VALUE = "get_variable_value"
    LIGHT_SET_ON_TIME = "light_set_on_time"
    PLAY_SOUND = "play_sound"
    PUT_LINK_PARAMSET = "put_link_paramset"
    PUT_PARAMSET = "put_paramset"
    RECORD_SESSION = "record_session"
    RELOAD_CHANNEL_CONFIG = "reload_channel_config"
    RELOAD_DEVICE_CONFIG = "reload_device_config"
    REMOVE_CENTRAL_LINKS = "remove_central_links"
    REMOVE_LINK = "remove_link"
    SEND_TEXT_DISPLAY = "send_text_display"
    SET_COVER_COMBINED_POSITION = "set_cover_combined_position"
    SET_DEVICE_VALUE = "set_device_value"
    SET_SCHEDULE = "set_schedule"
    SET_SCHEDULE_PROFILE = "set_schedule_profile"
    SET_SCHEDULE_WEEKDAY = "set_schedule_weekday"
    SET_SOUND_LED = "set_sound_led"
    SET_VARIABLE_VALUE = "set_variable_value"
    STOP_SOUND = "stop_sound"
    SWITCH_SET_ON_TIME = "switch_set_on_time"
    TURN_ON_SIREN = "turn_on_siren"
    UPDATE_DEVICE_FIRMWARE_DATA = "update_device_firmware_data"
    VALVE_SET_ON_TIME = "valve_set_on_time"


# filter out event error parameters, that should not be displayed in logbook
FILTER_ERROR_EVENT_PARAMETERS: Final[tuple[str, ...]] = ("ERROR_CODE",)


class HmEntityState(StrEnum):
    """Enum with Homematic entity states."""

    NOT_VALID = "not valid"
    RESTORED = "restored"
    UNCERTAIN = "uncertain"
    VALID = "valid"


ENTITY_TRANSLATION_KEYS: Final[frozenset[str]] = frozenset(
    {
        # Empty-name entries → entity_id stability (suppress suffix)
        "state",  # binary_sensor, sensor, switch
        "status",  # sensor
        # Sensor state value translations
        "direction",
        "door_mode",
        "door_state",
        "lock_state",
        "sec_direction",
        "sec_key_error",
        "sec_wds_state",
        "sec_win_error",
        "sec_win_status",
        "smoke_detector_alarm_status",
        "tri_state",
        "wkp_code_state",
        # Select state/option translations
        "acoustic_alarm_selection",
        "heating_cooling",
        "optical_alarm_selection",
        # Hub button translations
        "install_mode_bidcos_button",
        "install_mode_hmip_button",
        # Hub sensor translations (entity descriptions)
        "connection_latency",
        "energy_counter_feed_in_total",
        "energy_counter_total",
        "inbox",
        "install_mode_bidcos",
        "install_mode_hmip",
        "last_event_age",
        "rain_counter_today",
        "rain_counter_total",
        "rain_counter_yesterday",
        "sunshine_counter_today",
        "sunshine_counter_total",
        "sunshine_counter_yesterday",
        "system_health",
    }
)

BLOCKED_CATEGORIES: Final[tuple[str, ...]] = ()

# DpActionSelect whitelist - defines which parameter names should be exposed as InputHelper entities
DP_ACTION_SELECT_WHITELIST: Final[tuple[str, ...]] = (
    "ACOUSTIC_ALARM_SELECTION",  # Siren tone selection
    "OPTICAL_ALARM_SELECTION",  # Siren light pattern selection
)

# Config entry key for storing DpActionSelect values
CONF_ACTION_SELECT_VALUES: Final = "action_select_values"

# DpActionNumber whitelist - defines which parameter names should be exposed as InputHelper entities
DP_ACTION_NUMBER_WHITELIST: Final[tuple[str, ...]] = (
    # "DURATION_VALUE",  # Siren duration value
)

# Config entry key for storing DpActionNumber values (legacy, now in storage file)
CONF_ACTION_NUMBER_VALUES: Final = "action_number_values"


def _get_hmip_local_platforms() -> tuple[Platform, ...]:
    """Return relevant Homematic(IP) Local for OpenCCU platforms."""
    # Get platforms that directly map from DataPointCategory values
    category_platforms = tuple(
        Platform(pf)
        for pf in list(Platform)
        if pf in [category.value for category in CATEGORIES if category not in BLOCKED_CATEGORIES]
    )
    # Add platforms that don't have a direct category mapping
    # TEXT_DISPLAY maps to NOTIFY platform
    additional_platforms = (Platform.NOTIFY,)
    return category_platforms + additional_platforms


HMIP_LOCAL_PLATFORMS: Final[tuple[Platform, ...]] = _get_hmip_local_platforms()
