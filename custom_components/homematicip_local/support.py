"""Helper."""

from __future__ import annotations

from collections.abc import Callable, Coroutine, Mapping
from copy import deepcopy
from functools import wraps
import logging
import re
from typing import Any, Final, TypeAlias, TypeVar

from pydantic import ValidationError
import voluptuous as vol

from aiohomematic.const import (
    CHANNEL_ADDRESS_PATTERN,
    DEVICE_ADDRESS_PATTERN,
    HUB_ADDRESS,
    IDENTIFIER_SEPARATOR,
    INSTALL_MODE_ADDRESS,
    PROGRAM_ADDRESS,
    SYSVAR_ADDRESS,
    VIRTUAL_REMOTE_ADDRESSES,
    Interface,
    ParamsetKey,
)
from aiohomematic.exceptions import BaseHomematicException
from aiohomematic.interfaces import (
    CalculatedDataPointProtocol,
    CombinedDataPointProtocol,
    CustomDataPointProtocol,
    GenericDataPointProtocolAny,
    GenericProgramDataPointProtocol,
    GenericSysvarDataPointProtocol,
    ScheduleChannelSwitchProtocol,
)
from aiohomematic.model.week_profile_data_point import WeekProfileDataPoint
from aiohomematic.support.address import get_device_address
from homeassistant.const import CONF_TYPE
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import issue_registry as ir
from homeassistant.helpers.issue_registry import async_delete_issue
from homeassistant.loader import async_get_integration

from .const import (
    CONF_SUBTYPE,
    DOMAIN,
    EVENT_ADDRESS,
    EVENT_CHANNEL_NO,
    EVENT_DEVICE_ADDRESS,
    EVENT_DEVICE_ID,
    EVENT_ERROR,
    EVENT_ERROR_VALUE,
    EVENT_IDENTIFIER,
    EVENT_INTERFACE_ID,
    EVENT_MESSAGE,
    EVENT_MODEL,
    EVENT_NAME,
    EVENT_PARAMETER,
    EVENT_TITLE,
    EVENT_UNAVAILABLE,
    EVENT_VALUE,
)

_LOGGER = logging.getLogger(__name__)

# Validator constants
_CHANNEL_NO_MIN: Final = 0
_CHANNEL_NO_MAX: Final = 255
_WAIT_FOR_MIN: Final = 0
_WAIT_FOR_MAX: Final = 120

# aiohomematic prefixes only these routing-key kinds with the central id (see
# ``generate_unique_id``); after the central-id slot the key starts with one of
# these infixes. The virtual-remote ones are derived from
# ``VIRTUAL_REMOTE_ADDRESSES`` in the HA unique_id spelling (``:``/``-`` → ``_``,
# lower-cased); ``int000`` matches the ``INT000*`` internal devices (incl. heating
# groups). Keys without one of these carry no central-id slot.
_VIRTUAL_REMOTE_INFIXES: Final[tuple[str, ...]] = tuple(
    f"{address.replace(':', '_').replace('-', '_').lower()}_" for address in VIRTUAL_REMOTE_ADDRESSES
)
_HUB_KEY_INFIXES: Final[tuple[str, ...]] = (
    f"{HUB_ADDRESS}_",
    f"{INSTALL_MODE_ADDRESS}_",
    f"{PROGRAM_ADDRESS}_",
    f"{SYSVAR_ADDRESS}_",
    "int000",
    *_VIRTUAL_REMOTE_INFIXES,
)
_EVENT_GROUP_PREFIX: Final = "event_group_"
# Calculated data points on internal / hub channels insert this marker between the
# central-id slot and the infix: ``<central-id>_calculated_<infix>...``. Device-anchored
# calculated DPs are spelled ``calculated_<serial>_...`` (no central-id slot) instead.
_CALCULATED_MARKER: Final = "calculated_"


def realign_hub_unique_id(unique_id: str, *, central_id: str) -> str | None:
    """Rewrite the central-id slot of a hub / virtual-remote ``unique_id`` onto ``central_id``.

    Hub / install-mode / program / sysvar / internal (``INT000*``) and
    virtual-remote entities carry a ``<central-id>_`` slot; the matching
    virtual-remote event groups carry it after their ``event_group_<type>_``
    prefix. This rewrites whatever value currently fills that slot onto
    ``central_id``, independent of the old value, so a registry inherited from any
    earlier anchor (legacy ``entry_id[-10:]``, a prior serial, or a stale slot from
    a delete + re-add) realigns onto the live key instead of orphaning. Devices,
    channels and custom DPs carry no slot, ``loom_`` keys are out of scope and the
    per-central backup button is not a routing key, so all return ``None``. Also
    ``None`` when the slot already holds ``central_id``.
    """
    prefix = f"{DOMAIN}_"
    if not unique_id.startswith(prefix):
        return None
    key = unique_id[len(prefix) :]
    if key.startswith("loom_"):
        return None
    # Virtual-remote event groups: event_group_<type>_<central-id>_<vr-address>_<rest>.
    if key.startswith(_EVENT_GROUP_PREFIX):
        event_type, sep, after = key[len(_EVENT_GROUP_PREFIX) :].partition("_")
        if not sep:
            return None
        _slot, sep2, rest = after.partition("_")
        if not sep2 or not rest.startswith(_VIRTUAL_REMOTE_INFIXES):
            return None
        rebuilt = f"{prefix}{_EVENT_GROUP_PREFIX}{event_type}_{central_id}_{rest}"
        return rebuilt if rebuilt != unique_id else None
    # Standard hub / virtual-remote keys: <central-id>_<infix>...
    # Calculated DPs on internal / hub channels carry an extra ``calculated_`` marker
    # between the central-id slot and the infix (<central-id>_calculated_<infix>...);
    # device-anchored calculated DPs (``calculated_<serial>_...``) have no central-id
    # slot and fall through untouched.
    _slot, sep, rest = key.partition("_")
    if not sep:
        return None
    marker = ""
    if rest.startswith(_CALCULATED_MARKER):
        marker = _CALCULATED_MARKER
        rest = rest[len(_CALCULATED_MARKER) :]
    if not rest.startswith(_HUB_KEY_INFIXES):
        return None
    rebuilt = f"{prefix}{central_id}_{marker}{rest}"
    return rebuilt if rebuilt != unique_id else None


def validate_channel_no(value: Any) -> int:
    """Validate and return channel number."""
    try:
        channel = int(value)
    except (ValueError, TypeError) as err:
        raise vol.Invalid(f"Channel number must be an integer, got {type(value).__name__}") from err

    if not _CHANNEL_NO_MIN <= channel <= _CHANNEL_NO_MAX:
        raise vol.Invalid(f"Channel number must be between {_CHANNEL_NO_MIN} and {_CHANNEL_NO_MAX}")

    return channel


def validate_wait_for(value: Any) -> int:
    """Validate and return wait time in seconds."""
    try:
        wait_time = int(value)
    except (ValueError, TypeError) as err:
        raise vol.Invalid(f"Wait time must be a number, got {type(value).__name__}") from err

    if not _WAIT_FOR_MIN <= wait_time <= _WAIT_FOR_MAX:
        raise vol.Invalid(f"Wait time must be between {_WAIT_FOR_MIN} and {_WAIT_FOR_MAX} seconds")

    return wait_time


def validate_device_address(value: Any) -> str:
    """Validate and return device address. Accept channel addresses and extract the device part."""
    if not isinstance(value, str):
        raise vol.Invalid(f"Device address must be a string, got {type(value).__name__}")

    if DEVICE_ADDRESS_PATTERN.match(value) is not None:
        return value

    if CHANNEL_ADDRESS_PATTERN.match(value) is not None:
        return get_device_address(address=value)

    raise vol.Invalid(f"Invalid device address format: {value}")


def validate_channel_address(value: Any) -> str:
    """Validate and return channel address."""
    if not isinstance(value, str):
        raise vol.Invalid(f"Channel address must be a string, got {type(value).__name__}")

    if CHANNEL_ADDRESS_PATTERN.match(value) is None:
        raise vol.Invalid(f"Invalid channel address format: {value}")

    return value


def validate_paramset_key(value: Any) -> str:
    """Validate and return paramset key."""
    if isinstance(value, ParamsetKey):
        return value.value

    if not isinstance(value, str):
        raise vol.Invalid(f"Paramset key must be a string, got {type(value).__name__}")

    if value not in [pk.value for pk in ParamsetKey]:
        raise vol.Invalid(f"Invalid paramset key: {value}. Must be one of: {[pk.value for pk in ParamsetKey]}")

    return value


# Union for entity types used as base class for data points
HmBaseDataPointProtocol: TypeAlias = (
    CalculatedDataPointProtocol
    | CombinedDataPointProtocol
    | CustomDataPointProtocol
    | GenericDataPointProtocolAny
    | ScheduleChannelSwitchProtocol
    | WeekProfileDataPoint
)
# Generic base type used for data points in Homematic(IP) Local for OpenCCU
HmGenericDataPointProtocol = TypeVar("HmGenericDataPointProtocol", bound=HmBaseDataPointProtocol)
# Generic base type used for sysvar data points in Homematic(IP) Local for OpenCCU
HmGenericProgramDataPointProtocol = TypeVar("HmGenericProgramDataPointProtocol", bound=GenericProgramDataPointProtocol)
# Generic base type used for sysvar data points in Homematic(IP) Local for OpenCCU
HmGenericSysvarDataPointProtocol = TypeVar("HmGenericSysvarDataPointProtocol", bound=GenericSysvarDataPointProtocol)

BASE_EVENT_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(EVENT_DEVICE_ID): str,
        vol.Required(EVENT_NAME): str,
        vol.Required(EVENT_ADDRESS): validate_device_address,
        vol.Required(EVENT_CHANNEL_NO): validate_channel_no,
        vol.Required(EVENT_MODEL): str,
        vol.Required(EVENT_INTERFACE_ID): str,
        vol.Required(EVENT_PARAMETER): str,
        vol.Optional(EVENT_VALUE): vol.Any(bool, int),
    }
)
# Spelled out rather than derived from BASE_EVENT_DATA_SCHEMA, because a click
# event is not that shape: cleanup_click_event_data folds ``channel_no`` and
# ``parameter`` into ``subtype`` and ``type`` and drops the originals. Removing
# them again via ``BASE_EVENT_DATA_SCHEMA.extend({vol.Remove(...): ...})`` relied
# on a ``Remove`` marker replacing the ``Required`` one of the same name — true
# for voluptuous, where ``Remove("x") == Required("x")``, but not for the
# probatio shim Home Assistant 2026.9 installs in its place, which keeps both and
# then rejects every click event for the ``channel_no`` the cleanup just removed.
CLICK_EVENT_SCHEMA = vol.Schema(
    {
        vol.Required(EVENT_DEVICE_ID): str,
        vol.Required(EVENT_NAME): str,
        vol.Required(EVENT_ADDRESS): validate_device_address,
        vol.Required(EVENT_MODEL): str,
        vol.Required(EVENT_INTERFACE_ID): str,
        vol.Required(CONF_TYPE): str,
        vol.Required(CONF_SUBTYPE): validate_channel_no,
    },
    extra=vol.ALLOW_EXTRA,
)
DEVICE_AVAILABILITY_EVENT_SCHEMA = BASE_EVENT_DATA_SCHEMA.extend(
    {
        vol.Required(EVENT_IDENTIFIER): str,
        vol.Required(EVENT_TITLE): str,
        vol.Required(EVENT_MESSAGE): str,
        vol.Required(EVENT_UNAVAILABLE): bool,
    },
    extra=vol.ALLOW_EXTRA,
)
DEVICE_ERROR_EVENT_SCHEMA = BASE_EVENT_DATA_SCHEMA.extend(
    {
        vol.Required(EVENT_IDENTIFIER): str,
        vol.Required(EVENT_TITLE): str,
        vol.Required(EVENT_MESSAGE): str,
        vol.Required(EVENT_ERROR_VALUE): vol.Any(bool, int),
        vol.Required(EVENT_ERROR): bool,
    },
    extra=vol.ALLOW_EXTRA,
)


def handle_homematic_errors[**P, R](
    func: Callable[P, Coroutine[Any, Any, R]],
) -> Callable[P, Coroutine[Any, Any, R]]:
    """
    Handle aiohomematic exceptions and convert to HomeAssistantError.

    This decorator prevents log flooding by converting backend exceptions
    to HomeAssistantError, which Home Assistant displays as a toast notification
    instead of logging repeatedly.
    """

    @wraps(func)
    async def wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
        try:
            return await func(*args, **kwargs)
        except BaseHomematicException as exc:
            raise HomeAssistantError(str(exc)) from exc
        except ValidationError as exc:
            # Pydantic validation errors - format user-friendly message
            errors = "; ".join(e["msg"] for e in exc.errors())
            raise HomeAssistantError(f"Invalid schedule data: {errors}") from exc
        except ValueError as exc:
            # Domain-specific validation errors from aiohomematic
            raise HomeAssistantError(str(exc)) from exc

    return wrapper


def cleanup_click_event_data(event_data: dict[str, Any]) -> dict[str, Any]:
    """Cleanup the click_event."""
    cleand_event_data = deepcopy(event_data)
    cleand_event_data.update(
        {
            CONF_TYPE: cleand_event_data[EVENT_PARAMETER].lower(),
            CONF_SUBTYPE: cleand_event_data[EVENT_CHANNEL_NO],
        }
    )
    del cleand_event_data[EVENT_PARAMETER]
    del cleand_event_data[EVENT_CHANNEL_NO]
    # Rename device_address to address (required by TRIGGER_SCHEMA)
    if EVENT_DEVICE_ADDRESS in cleand_event_data:
        cleand_event_data[EVENT_ADDRESS] = cleand_event_data.pop(EVENT_DEVICE_ADDRESS)
    return cleand_event_data


def is_valid_event(event_data: Mapping[str, Any], schema: vol.Schema) -> bool:
    """Validate event_data against a given schema."""
    try:
        schema(event_data)
    except vol.Invalid as err:
        _LOGGER.debug("The EVENT could not be validated. %s, %s", err.path, err.msg)
        return False
    return True


def cleanup_instance_name(*, instance_name: str) -> str:
    """Clean up instance name problematic characters for directories."""
    for char in ("/", "\\"):
        instance_name = instance_name.replace(char, "")
    return instance_name


def get_device_identifier(*, instance_name: str, address: str, interface: str) -> str | None:
    """
    Return the HA device identifier, or ``None`` when it cannot be built.

    The identifier is deliberately built from the HA instance name and the
    interface *type* rather than from a backend's own interface id. Both
    backends carry that type separately — aiohomematic as ``Interface``,
    openccu-loom as the daemon's ``interface`` field — while their interface
    ids differ in the leading component: aiohomematic uses the HA instance
    name, the daemon its own CCU name (``Otto-HmIP-RF`` vs.
    ``OttoDev-HmIP-RF``). Keying devices on the neutral form makes the
    identifier identical on both, so switching backends keeps every device
    registry entry and with it its ``device_id``, area and automations.

    For the direct-CCU backend the result is byte-identical to the previous
    ``Device.identifier``, because that is exactly how aiohomematic composes
    its interface id.

    Returns ``None`` when the interface is not one aiohomematic knows: the
    loom store seeds a freshly paired device with the wire id in that field
    until ``attach_device_detail`` corrects it, and a device keyed off that
    stub would have to move a second time.
    """
    if interface not in tuple(Interface):
        return None
    # The same cleanup the central name goes through, applied here so the
    # identifier is identical whether it is built from the running central or
    # from the raw config entry (the registry migration does the latter).
    return f"{address}{IDENTIFIER_SEPARATOR}{cleanup_instance_name(instance_name=instance_name)}-{interface}"


def get_device_address_from_identifiers(identifiers: set[tuple[str, str]]) -> str | None:
    """
    Return the device address from device_info.identifiers.

    The address is the part before the separator for regular devices, sub
    devices (``address@interface-group_no``) and schedule devices alike, so
    no suffix handling is needed. It is also the only part callers need: an
    address identifies a device within a central, and the interface id — the
    part that differs per backend — is read off the device once it is found.
    """
    for _, identifier in identifiers:
        if IDENTIFIER_SEPARATOR in identifier:
            return identifier.split(IDENTIFIER_SEPARATOR, 1)[0]
    return None


def get_issue_id(*, entry_id: str, issue_type: str, interface_id: str) -> str:
    """
    Return the repair issue id for an interface scoped issue of a config entry.

    The issue registry persists the id but not the translation key, so the
    type has to travel in the id. ``async_delete_issues`` matches on the
    prefix this composes, which is why both live side by side.
    """
    return f"{entry_id}_{issue_type}_{interface_id}"


@callback
def async_delete_issues(*, hass: HomeAssistant, entry_id: str, issue_types: tuple[str, ...]) -> tuple[str, ...]:
    """
    Delete a config entry's repair issues of the given types and return their ids.

    Matches the prefix ``get_issue_id`` composes, so the interface id part is
    irrelevant — which it has to be: it is the XML-RPC interface id for a
    proxy issue and the JSON-RPC url for a session issue.
    """
    # An empty interface id leaves exactly the prefix every id of that type
    # carries, so the match cannot drift away from the composition.
    prefixes = tuple(
        get_issue_id(entry_id=entry_id, issue_type=issue_type, interface_id="") for issue_type in issue_types
    )
    deleted: list[str] = []
    for domain, issue_id in list(ir.async_get(hass).issues):
        if domain == DOMAIN and issue_id.startswith(prefixes):
            async_delete_issue(hass=hass, domain=DOMAIN, issue_id=issue_id)
            deleted.append(issue_id)
    return tuple(deleted)


def get_data_point[DP](data_point: DP) -> DP:
    """Return the Homematic data point. Makes it mockable."""
    return data_point


class InvalidConfig(HomeAssistantError):
    """Error to indicate there is invalid config."""


async def get_aiohomematic_version(hass: HomeAssistant, domain: str, package_name: str) -> str | None:
    """Return the version of a package from manifest.json."""
    integration = await async_get_integration(hass, domain)
    requirements = integration.manifest.get("requirements", [])

    for req in requirements:
        match = re.match(r"^([a-zA-Z0-9_.\-]+)\s*[<>=!~]*\s*([0-9a-zA-Z_.\-]+)?$", req)
        if match:
            name, version = match.groups()
            if name.lower() == package_name.lower():
                return version or "0.0.0"

    return None
