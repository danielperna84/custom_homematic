# Version [2.11.1](https://github.com/SukramJ/homematicip_local/compare/2.11.0...2.11.1) (unreleased)

## What's Changed

### Integration

- Beyond the dependency bumps below, the integration's own changes in this release are openccu-loom backend (Beta) work; its details stay out of scope for this changelog until it leaves Beta

### Dependencies

#### Bump aiohomematic to [2026.9.2](https://github.com/SukramJ/aiohomematic/compare/2026.9.1...2026.9.2)

- **Fix: a cover command was dropped while the cover was moving.** `cover.set_cover_position` with the position the cover had set off from, and `cover.close_cover` while it was opening (mirrored for the other direction), never reached the CCU. Nothing was sent, nothing was logged above DEBUG, and the service call reported success.

  Classic shutter actuators (`HM-LC-Bl1-*` and relatives) re-report the *old* level when they start working and only report the new one once the movement has finished. That echo clears the optimistic value, so for the whole travel the cover reads as if it were still at its starting position — and a command aiming back there compared equal to the current position and was discarded as "no state change". Whether it happened at all depended on a race between the echo and the second command, which made it look intermittent. Commands with any other target were unaffected.

  A running movement counts as a state change now; `DIRECTION` is the only signal left at that point, because the echo has already cleared the optimistic value. While the cover stands still, an identical command is still suppressed as before

- The `NO_STATE_CHANGE` debug line names the data point it belongs to. It logged `name`, which is empty for a primary custom data point whose channel name equals the device name — so the line that tells you a command was suppressed did not say which data point suppressed it

#### Bump openccu-data to `2026.9.0`

`openccu-data` is not imported by this integration. It is pulled in by aiohomematic and pinned in the manifest so a user installs the version this release was tested against. aiohomematic reads it for a channel's translated type name (`aiohomematic/model/device.py:1020`) and for the per-value labels of a parameter's `VALUE_LIST` (`aiohomematic/model/data_point.py:735`).

- **The three `CHANNEL_OPERATION_MODE` enums of the HmIP door-lock drive have labels of their own now.** The parameter appears on three channel types of an HmIP-DLP with a different `VALUE_LIST` on each, and no source carried a label for any of their tokens — not the extract, not the CCU's own `stringtable_de.txt`, not the WebUI language files. Consumers fell back to whatever the unqualified `channel_operation_mode=<index>` entries happened to say, which came from an unrelated device. The curated overlay names all three enums now, keyed by channel type so no other type can borrow them
- **The German channel type of the door-lock drive read "Tüschlossantrieb".** The typo is upstream — `translate.lang.channelDescription.js` carries it while every neighbouring string in the same file spells "Türschlossantrieb" — and the curated overlay corrects it
- The bump also carries `2026.8.1`, whose one breaking change is confined to how `openccu-data` extracts its own data (the local source is an OpenCCU-Base checkout now, `OCCU_PATH` renamed to `OPENCCUBASE_PATH`). The published artifacts and their format are unaffected, so nothing of it reaches a consumer of the package

#### Bump openccu-loom-client to `2026.9.4`

- Bump for the openccu-loom backend (Beta); it has no runtime effect on the direct-CCU backend, where the client is not loaded. It regenerates the wire bindings against daemon api 11.2.0 (openccu-loom 0.76.0) and lets a channel say which side of a direct link it can take. Kept to one line: loom details stay out of scope while the backend is Beta

### Development

- Test framework `pytest-homeassistant-custom-component-framework` `1.0.52` → `1.0.53`. A patch there follows a Home Assistant core release; the package's own structure is unchanged

# Version [2.11.0](https://github.com/SukramJ/homematicip_local/compare/2.10.0...2.11.0) (2026-09-04)

## What's Changed

### Integration

- **The button blueprints only ask the CCU for direct links when something reads the answer.** The lookup is by far the slowest step in these automations — a CCU round trip on every keypress, ahead of the action — and its result feeds nothing but the two direct-link options. It ran unconditionally all the same, so an installation that never enabled either option paid for it on every press, and the action could never be faster than the CCU replied. It now runs only when one of the options is on *and* the pressed button has an action configured; with both off there is no CCU call left in the action's way.

  What that is worth depends entirely on the CCU. On one reporter's installation the integration delivered every keypress in about 6 ms and the seven measurable blueprint runs completed in 16–68 ms, while the same installation's RPC latency averaged 9.8 ms across 9571 calls with a maximum of 6.1 s — so the round trip is usually free and occasionally very expensive. A keypress arriving as a bundle (`PRESS_SHORT` + `PRESS_LONG` + `PRESS_LONG_RELEASE`) used to cost one lookup each.

  Everything reading the answer moved into the same branch as the lookup, because variables set in a nested sequence do not escape it. That the `stop` for the skip option still ends the whole run from in there is asserted rather than assumed, as is the notification path. Reported as aiohomematic#3382, where the delay was attributed to Home Assistant 2026.9 — the lookup has been in these blueprints unchanged since 2026-04-14 and predates both that release and this one

- **Fix: button presses reach automations again on Home Assistant 2026.9.** Every `homematic.keypress` and `homematic.impulse` event stopped being fired, so keypress blueprints, device triggers and any automation listening for a button lost their trigger — silently, with no trace to look at, while the event entity kept updating and the log showed only a DEBUG line per press: `The EVENT could not be validated. ['channel_no'], required key not provided`.

  `CLICK_EVENT_SCHEMA` was derived from `BASE_EVENT_DATA_SCHEMA` and undid the parts a click event does not have — `cleanup_click_event_data` folds `channel_no` and `parameter` into `subtype` and `type` and drops the originals — by extending it with `vol.Remove` markers of the same names. That relies on a `Remove` marker replacing the `Required` one it shadows, which holds for voluptuous, where `Remove("x") == Required("x")` is `True` (measured on 0.13.1, 0.14.2, 0.15.0, 0.15.2 and 0.16.0). Home Assistant 2026.9 installs the probatio shim in voluptuous's place, and there `Remove("x") == Required("x")` is `False` and `Remove` carries its own `__hash__`, so `extend` keeps both markers and the schema went on requiring the `channel_no` the cleanup had just removed (probatio 0.11.3). Only `Remove` is affected — a `Required` replaced by an `Optional` still resolves the way it does under voluptuous.

  The schema is now spelled out instead of derived, so it states what a click event is and depends on no marker-replacement semantics. `subtype` validates through `validate_channel_no`, which returns an `int` in range — blueprints compare the channel numerically. Reported as aiohomematic#3374

- **Diagnostics say which backend an installation runs, and on what.** The dump gained a `deployment` block: the backend in use, the number of CUxD devices, and — on the openccu-loom backend, read from the CCU list the adapter already fetches — how many centrals the daemon mediates. Two questions an architecture review had filed as "not measurable without telemetry" are answered by a dump a user attaches to a bug report; nothing is collected or sent anywhere. The central count is omitted when the backend does not publish it, rather than defaulting to a zero that would read as "one CCU"

- **Fix: switching backends no longer leaves every device behind and builds a second one beside it.** Both backends compose the HA device identifier as `<address>@<central>-<interface>`, but they disagree on the leading component: aiohomematic uses the Home Assistant instance name, the openccu-loom daemon its own CCU name (`OttoDev-HmIP-RF` against `Otto-HmIP-RF`, measured against daemon 0.68.1). Every device therefore re-keyed on a backend switch. The entities moved with it — their unique_ids are migrated — but the `device_id` did not, and that is what an area, a custom device name and every device-based automation hang on. The old entry stayed behind holding whatever had not migrated with it.

  The identifier is now composed by the integration itself, from the instance name and the interface *type* both backends report separately. On the direct-CCU backend that is byte-identical to what aiohomematic produced, so nothing moves there — the migration is a no-op for every installation that never touched the loom backend. A registry keyed the daemon's way is rewritten before the platforms come up, where the target key is still free and the rename is plain. Where a switch already happened and both entries exist, the older one wins: the newer entry's entities and sub-devices move over to it and it is removed, so the `device_id` the automations use is the one that survives.

  Reported from a live installation, where the switch turned 190 device entries into more than 380 — every base device, every sub device and every schedule device got a twin, with the entities on the new one and whatever had not migrated left on the old.

  The identifier also stopped being a routing key. Device actions, device triggers, the device-based services and the device-removal path used to parse the backend's interface id back out of it; they now find the device by its address and read the interface id off the device. Without that they would have failed silently on the openccu-loom backend the moment the identifier stopped carrying the daemon's id

- **Fix: system variable and program entities keep their history when their key moves onto the CCU id.** Both backends used to key these two families on the slug of a renameable name, so a rename in the CCU WebUI re-keyed the entity and took its history, area and every automation with it. Both moved onto the id the CCU already carries — aiohomematic in `2026.8.8`, openccu-loom in `0.68.0` — and without this pass the existing registry entries would have orphaned on that upgrade.

  The old key is reconstructed here rather than transported over the wire: the data point carries `legacy_name`, and the old key was the slug of it. It runs deferred, 60 s after the start and immediately before the orphan cleanup, because it needs loaded hub data — which means the freshly keyed twins already exist. That collision is resolved rather than skipped: the twin is seconds old and holds nothing, the registry entry holds the history, so the twin gives way. But a live entity binds to its registry entry once, at `async_add_entities`, so the historied entry the rename hands the key to has no entity behind it — which is why a migrating pass schedules one config entry reload: the entities re-bind within seconds, with their history, instead of only on the next restart. That reload is asked for once per entry and the record is kept in `hass.data`, which survives it; a second migrating pass logs a warning and leaves the re-bind to the next restart, because reaching it would mean the pass did not converge and reloading again would not converge either. Idempotent, and a no-op on an installation that never carried a slug key.

  The orphan cleanup that follows in the same pass now spares hub entries the migration has yet to take. Should it decline — `get_hub_data_points()` raising, or a data point yielding no old key — the historied entry keeps its slug key, and a hub entry has no device address, so the sweep read it as an orphan and deleted it with its history, name and area. It now rebuilds the pre-id key for every live hub data point and keeps any entry still holding one. The next start retries the migration; deletion has no next start

- **Fix: CUxD entities keep their history now that their key carries the central id.** CUxD hands out the same synthetic addresses on every CCU, so two CCUs bridged into one Home Assistant declared byte-identical unique_ids for their CUxD data points and Home Assistant kept only the first. aiohomematic scopes the family by central id from `2026.8.7` on, as the openccu-loom daemon always did — so every entity keyed before that adoption moves once, on both backends, because the loom client rebuilds through aiohomematic the keys the daemon does not stamp (custom data points, week profiles, the combined duration number, the device-update entity, event groups). Without the pass those entities orphan: they keep their history, area and customisations while the platform spawns freshly keyed duplicates beside them, and the orphan sweep eventually deletes the originals. Idempotent, and an installation without CUxD devices sees nothing happen
- **Fix: a sub-device channel without a group master could make its device its own via device.** With sub devices enabled, the via device was moved up to the Homematic device as soon as a channel reported itself as part of a multi-channel group — before the group master, which supplies the sub-device identifier, was resolved. Without a master the identifier stayed on the device, so device and via device were the same. HA used to ignore such a self-reference with a log line; since 2026.9 it raises a `HomeAssistantError` that no platform catches, which would take down the whole platform setup ([device registry follow-up changes](https://developers.home-assistant.io/blog/2026/08/24/device-registry-follow-up-changes/)). The split is now conditional on the group master, so a channel without one simply stays on its device, below the central
- **Fix: setup no longer retries forever against an incompatible openccu-loom daemon.** Only an authentication failure had its own case, so a daemon speaking a contract this build cannot ended up on the generic "not ready" path and was retried indefinitely with nothing saying why. It is reported as a setup error now. openccu-loom backend only

### Development

- Covers and sirens dispatch on aiohomematic's category protocols — `GarageDataPointProtocol`, `TiltCoverDataPointProtocol`, `CoverDataPointProtocol`, `SoundPlayerDataPointProtocol` — instead of on the concrete custom data point classes. Both backends satisfy them structurally, so these two platforms no longer decide which entity a data point becomes from the per-backend class tuples in `backend_types.py`. The one case the protocols do not carry stays explicit: an IP blind configured as a shutter presents no tilt and becomes a plain cover, read from `operation_mode`, which lives on the concrete class
- `backend_types.py` names the loom twin it could not find instead of failing mute, and its docstring no longer claims a mapping the backend surface contract test disproves
- Two test gaps closed. The hub key migration now runs against a real entity registry — two system variables whose names differ only in punctuation slug to one key, and the pass has to hand the history to one entity and leave the other alone — rather than against the key rebuild in isolation. And the hub singletons (alarm and service messages, inbox, connectivity, metrics, install mode), the per-device update data points, the event groups and the alarm panels are covered on spawn: they are announced through `DataPointsCreatedEvent` rather than enumerated in a platform's setup tail, which is why a full green suite said nothing when a change to the setup order dropped all of them mid-release
- Two documentation findings from the implementation review of the architecture memo corrected in `docs/architecture-comparison-aiohomematic-vs-loom.md`: three places still argued from a superseded "~14k LOC thin adapter" figure — including §1's central finding and the §7 evaluation matrix a backend decision gets read from — where the client is 27,312 LOC today (21,730 hand-maintained, 5,587 generated wire types), which drops the footprint score from 9 to 7; and the metaclass claim `backend_types.py` disproved in this repository is gone, so the two no longer assert opposite things about the same settled question
- Two more test gaps closed. The CUxD registry pass had only its key arithmetic covered, never the registry walk — it runs on every start-up, on both backends, and touches *every* CUxD entity on a direct-CCU install; four cases now pin it, including a taken target key being skipped rather than raised. And `_pair`'s warning, the only signal that exists when this integration and `openccu-loom-client` disagree on a type, is pinned by three cases so it cannot be removed again unnoticed
- The click event path is covered end to end now. `cleanup_click_event_data` and `is_valid_event` each had their own test, but nothing validated the cleanup's output against `CLICK_EVENT_SCHEMA`, so a full green suite said nothing while every button press was being rejected. Three cases pin the schema against a payload shaped the way `ControlUnit._on_device_trigger` builds it, and one more asserts the press arrives on Home Assistant's event bus — the entity state and the bus event are independent consumers of the same trigger, and only the bus event drives automations
- The second pair of duplicated dependency pins is guarded now. Five lint tools are pinned twice — as a requirement in `requirements_test_pre_commit.txt` and as a hook `rev` in `.pre-commit-config.yaml` — and nothing tied the two together, because `make upgrade-deps` ran `pur` over the requirements files and never touched the hook revisions. Both had already drifted: codespell ran at `v2.4.2` against a pinned `2.4.3`, python-typing-update at `v0.7.3` against `v0.8.1`, so the hook disagreed with the tool the repository claimed to use. `make upgrade-deps` moves both sides now, and `tests/test_dependency_pins.py` fails by name when they part again — the same guard the manifest/CI pair already had, for the same reason
- Dependabot covers the Python requirements as well, not only GitHub Actions. It skips what it cannot move correctly on its own: the four backend packages, which are ours and get bumped together with the manifest pin, the changelog entry and the code that needs them; and the five tools pinned twice, which `make upgrade-deps` moves on both sides at once. That leaves eight third-party test and lint dependencies to weekly grouped PRs
- Beyond the entries above, the integration's own changes in this release are openccu-loom backend (Beta) work; its details stay out of scope for this changelog until it leaves Beta

### Dependencies

#### Bump aiohomematic to `2026.9.1`

- **A `HmIP-HEATING` group no longer stays frozen at its restored state after a CCU restart** ([aiohomematic#3376](https://github.com/SukramJ/aiohomematic/issues/3376)). The climate entity gated its validity on `SET_POINT_MODE`, which the CCU sends only when the operating mode actually changes — while `ACTUAL_TEMPERATURE` and `SET_POINT_TEMPERATURE` keep arriving. A heating group whose mode had not been touched since the restart therefore kept showing frozen `current_temperature` and `target_temperature`, while its sibling `sensor.*` entities updated from the very same events. Groups on `VirtualDevices` have no second source to fall back on: the ReGa bulk fetch skips the mode data point and there is no per-parameter `getValue` for a virtual group. Validity now follows temperature and setpoint, and `mode` uses its existing `AUTO` fallback until `SET_POINT_MODE` arrives. A group missing `ACTUAL_TEMPERATURE` from the bulk result too still waits for its first event
- **A system variable whose declared type does not match its value is kept as text instead of being dropped** ([aiohomematic#3377](https://github.com/SukramJ/aiohomematic/issues/3377)). `SysVar.getAll` reports a type per variable and it was trusted: a value list holding a single text entry returns that entry rather than its index, `int()` raised, the record was discarded, and no entity ever appeared — with an `ERROR` on every 60 s scan (4075 of them in the submitted log, for one variable). Disabling the entity did not help, because that is resolved before the value is parsed. The variable now falls back to `STRING` and keeps its raw value; it also drops `extended_sysvar`, so a type that could not be verified never yields a writable data point. The log is a `WARNING` now, once per variable per client, naming the declared type

The manifest still pinned `2026.8.7` while CI already ran `2026.8.8` — across the very release that adopts 2026.8.8's re-keying of system variables and programs. The registry migration added for it was therefore tested against a backend that had re-keyed and would have shipped against one that had not.

`tests/test_dependency_pins.py` now pins the two files together, the way the sister client repository does. Bite proof: restoring `2026.8.7` in the manifest fails it by name.


#### Bump openccu-loom-client to `2026.9.3`

openccu-loom backend (Beta) only — on the direct-CCU backend the client is not loaded, so this bump has no runtime effect there.

Three client releases land in this integration release; what follows is the net effect against 2.10.0, because the intermediate ones never shipped from here.

- **A daemon version mismatch no longer refuses the connection.** The client used to demand the same API major and at least the same minor as the version it was generated against, and 2026.9.1 would have rejected an older daemon outright. It reports the difference now and connects; the only condition that still refuses is a daemon missing a capability this integration declares it needs. This matters in both directions, and the second one bit on ordinary releases: HACS updates this integration before you update the daemon, which used to make the daemon *older by a minor* and fail setup for a contract that was fully present. The advice to stay on 2.10.0 when the daemon cannot be updated no longer applies.
- **A daemon that adds a value no longer breaks decoding.** Generated enums accept a value this build has not seen and carry it through as the raw string, instead of rejecting the whole response. Three daemon response shapes also stopped declaring themselves closed to unknown fields, so a field added later no longer does the same.
- **When the two genuinely cannot work together**, the config flow now says so with its own message rather than reporting a connection failure — see the integration entry above.
- **CUxD entities re-key once**; the migration that carries them is the integration entry above.
- **A week profile reported its active profile one index too low.** Regenerated wire bindings (daemon v0.73.0) carry the fix.
- `openccu-loom-types` is no longer a separate dependency — it is folded into the client — so this bump removes a package from the install rather than pinning one.

#### Bump aiohomematic to [2026.8.6](https://github.com/SukramJ/aiohomematic/compare/2026.8.5...2026.8.6)

- One added field, `InboxDeviceData.awaiting_release`, for the openccu-loom backend's onboarding states. It defaults to false and no direct-CCU path sets it

#### Bump aiohomematic-config to [2026.8.1](https://github.com/SukramJ/aiohomematic-config/compare/2026.8.0...2026.8.1)

- Packaging and tooling only, no behaviour change: the package raises its own `aiohomematic` requirement to `>=2026.8.5`, is marked production/stable, and updates its development dependencies

#### Development dependencies

Against 2.10.0: `mypy` `<=2.1.0` → `<=2.3.1`, `prek` `0.5.0` → `0.5.2`, `pylint` `4.0.7` → `4.0.8`,
`pytest-homeassistant-custom-component-framework` `1.0.47` → `1.0.52`, `ruff` `0.16.4` → `0.16.6`, and
`aiohomematic-test-support` `2026.8.5` → `2026.9.1` following the runtime pin. Tooling only, no packaged
behaviour changes.

The `mypy` bump is the first one Dependabot raised here: this release put the Python requirements under it,
having covered only GitHub Actions before.


# Version [2.10.0](https://github.com/SukramJ/homematicip_local/compare/2.9.1...2.10.0) (2026-08-27)

## What's Changed

### Integration

- **Fix: on Home Assistant 2026.9 no entity was added any more** — a startup produced hundreds of `Error adding entity None for domain …` with `RuntimeError: Detected code that calls device_registry.async_get_or_create with a deprecated via_device parameter` ([aiohomematic#3365](https://github.com/SukramJ/aiohomematic/issues/3365)). The deprecation notice promises a warning until 2027.8, but that promise only holds while HA can find the integration in the call stack: the `via_device` of a `DeviceInfo` is passed on by HA's own `entity_platform`, so no integration frame is left, and HA then falls back to its core behaviour — which raises. Devices are now linked by registry id: `ControlUnit.ensure_via_device_exists()` returns the id of the via device it made sure exists, and the central is created on demand so a link never points at an unregistered device
- **Breaking: the minimum Home Assistant version is now 2026.8.0.** The device registry APIs this release moves to (`via_device_id` on `DeviceInfo` and `async_get_or_create`, plus `async_get_device_by_identifier`) do not exist in 2026.7
- **Fix: devices were no longer removed from the device registry when their last entity disappeared.** The removal path tested `device_id in device_registry.devices`, and on HA 2026.9 `devices` iterates device entries instead of being a mapping, so the membership test silently never matched. It now asks the registry directly
- Replace `device_registry.async_get_device(identifiers=…)` with `async_get_device_by_identifier(identifier, config_entry_id)`. Identifiers are no longer unique across config entries, so the lookup is now scoped to this integration's own entry — which is what all three call sites (via-device creation, device-action/-trigger resolution, and the known-device check after a cache clear) meant all along
- Side effect of the id-based links, measured against the full test device set: devices that so far ended up with no via device at all — the virtual remotes among them — now hang off the central like every other device (7 of 439 devices in that run; entity count unchanged at 4705)
- Garage doors (`HmIP-MOD-HO`, `HmIP-MOD-TM`) gain a **Door Mode** select entity that exposes the door's three physical states — closed, open and ventilation position — as a first-class, tappable control. Home Assistant's `cover` platform has no native ventilation state ([architecture#502](https://github.com/home-assistant/architecture/discussions/502)), so ventilation was previously only reachable by setting a cover position inside an undiscoverable range. The data point itself comes with the aiohomematic bump below; the integration contributes the entity name and its state translations. Suggested in [#1252](https://github.com/SukramJ/homematicip_local/pull/1252) by [@ANierbeck](https://github.com/ANierbeck)

### Config Panel

- The climate schedule editor no longer discards unsaved edits when a second weekday is opened ([frontend#95](https://github.com/SukramJ/homematicip-local-frontend/issues/95)). Each weekday now keeps its own draft, including its undo history, so several days can be edited in one dialog session; changed tabs carry a dot and the footer button becomes "Save all". Closing the dialog with unsaved changes asks first, and the inline row button is labelled "Apply" / "Übernehmen" so that "Save" means only the action that writes to the CCU. This affects the config panel and the climate schedule card alike, since both render the same schedule editor

### Development

- Beyond the entries above, the integration's own changes in this release are openccu-loom backend (Beta) work; the direct-CCU backend gains support for two new devices through the aiohomematic bump below. The user-facing details of the loom backend stay out of scope for this changelog until it leaves Beta

### Dependencies

#### Bump aiohomematic to [2026.8.5](https://github.com/SukramJ/aiohomematic/compare/2026.8.2...2026.8.5)

- **Fix: `HM-CC-TC` climate entities stayed frozen at their restored state.** `CustomDpSimpleRfThermostat` gated its validity on `TEMPERATURE` **and** `SETPOINT`, but `HM-CC-TC` reports `SETPOINT` only when the wheel is turned on the device — never periodically. On a device nobody had touched since the last CCU restart, `SETPOINT` therefore stayed unrefreshed forever, which dragged the whole climate data point to `is_valid=False`: the entity kept `value_state=restored` and froze `current_temperature`, `target_temperature` and `hvac_mode`, while the sibling `sensor.*` entities kept updating from the very same `TEMPERATURE` events. Validity now follows `TEMPERATURE` alone, and `target_temperature` stays `None` until a real `SETPOINT` arrives instead of reporting a stale value
- **Fix: classic RF thermostats hung at the restored state while the operating mode stayed untouched.** Same failure class for `CustomDpRfThermostat` (`HM-CC-RT-DN`, `HM-TC-IT-WM-W-EU`, `HM-CC-VG-1`, `BC-RT-TRX-*`, `BC-TC-C-WM`), which gated its validity on `CONTROL_MODE` — a parameter these devices only send when the mode actually changes. After a CCU restart it could stay unrefreshed for as long as nobody switched between AUTO and MANU. Validity now follows `TEMPERATURE` and `SETPOINT`; until `CONTROL_MODE` arrives, `mode` reports its existing `AUTO` fallback
- Expose the garage door's discrete mode as a `SELECT`-category combined data point. `CustomDpGarage` now declares a `CombinedDpGarageDoorMode` that reads `DOOR_STATE` and writes `DOOR_COMMAND` under its own parameter name `DOOR_MODE`, so the integration's generic select dispatch picks it up without any platform-side wiring — and the entity is named after what it does rather than borrowing the identity of either source parameter. While the door is travelling the select keeps reporting the mode the door is heading for instead of dropping to `unknown`; a `STOP` clears that held mode
- Fix `GarageDoorState.POSITION_UNKNOWN`, which carried a stray leading underscore and therefore never matched the `DOOR_STATE` value reported by the CCU
- Add support for the flush-mount switch actuators `HmIP-FS6` and `HmIP-FSI6`. `HmIP-FS6` has no input channel, so it shares the channel layout of `HmIP-FSM` and is now registered as a switch profile on channel 2 — without that registration it only produced generic data points. `OPERATING_VOLTAGE` is ignored for it as well, consistent with the other mains-powered actuators
- Expose `CHANNEL_OPERATION_MODE` on channel 1 of `HmIP-FSI6`. The custom switch data point of that device already worked, but the un-ignore rule was keyed on `HmIP-FSI16` only — model keys are matched with `str.startswith`, and `"hmip-fsi6".startswith("hmip-fsi16")` is `False`, so the operation mode of the push-button input stayed hidden

#### Bump openccu-loom-client to `2026.8.26` (pins `openccu-loom-types==0.5.5`)

- Bump for the openccu-loom backend (Beta); it has no runtime effect on the direct-CCU backend, where the client is not loaded. Advances the bundled loom client from `2026.8.9` to `2026.8.26` and its transitively pinned `openccu-loom-types` from `0.3.10` to `0.5.5`
- **This raises the minimum daemon to openccu-loom 0.65.1 or newer.** The client is generated against the daemon's API 7.13.0 and checks that version at connect time, so it refuses a daemon reporting an older API rather than half-initializing against an incompatible one — an older daemon is rejected outright rather than merely missing newer surface. Installations that cannot update the daemon should stay on 2.9.1

# Version [2.9.1](https://github.com/SukramJ/homematicip_local/compare/2.9.0...2.9.1) (2026-08-10)

## What's Changed

### Development

- The openccu-loom backend (Beta) hands its CCU, diagnostics and configuration surfaces to the daemon, which owns that state and covers it for every CCU it serves: the config panel is no longer registered for loom entries, and their device pages link to the daemon's own Config UI instead. Entries on the direct-CCU backend are unchanged — the panel is registered once for the whole integration, so a mixed installation keeps it. The user-facing details stay out of scope for this changelog until the backend leaves Beta

### Dependencies

#### Bump aiohomematic to [2026.8.2](https://github.com/SukramJ/aiohomematic/compare/2026.8.1...2026.8.2)

- Fix the calculated sensors (`DEW_POINT`, `VAPOR_CONCENTRATION`, `FROST_POINT`, `ENTHALPY`, `DEW_POINT_SPREAD`, `APPARENT_TEMPERATURE`, `OPERATING_VOLTAGE_LEVEL`) freezing on their restored state after the update to 2026.8.1, while the underlying temperature and humidity entities kept updating (#3343). Their source data points were resolved lazily on first value access, which the climate sensors never triggered — and with the stricter validity gating of 2026.8.1 an unresolved source set reported `is_valid=False`. Home Assistant reads validity before the value, so it kept serving the restored state and never performed the read that would have resolved the sources; the per-source update subscription is created during that same resolution, so no source update reached the calculated data point either. Sources are now resolved when the calculated data point is constructed. The regression affects every installation running 2.9.0 — **updating is recommended for all installations**
- The change is backed by a new contract test in aiohomematic that pins source resolution and subscription at construction time, so a calculated data point can report its validity without a prior value read

#### Bump openccu-loom-client to `2026.8.9` (pins `openccu-loom-types==0.3.10`)

- Bump for the openccu-loom backend (Beta); it has no runtime effect on the direct-CCU backend, where the client is not loaded. Advances the bundled loom client from `2026.8.6` to `2026.8.9` and its transitively pinned `openccu-loom-types` from `0.3.3` to `0.3.10`. **It raises the minimum daemon to openccu-loom 0.57.0 or newer** — the client refuses to connect to a lower API minor rather than half-initializing against it

# Version [2.9.0](https://github.com/SukramJ/homematicip_local/compare/2.8.3...2.9.0) (2026-08-07)

## What's Changed

### Integration

- Doorbell event entities (HmIP-DBB, HmIP-DSD-PCB) now expose and fire the standard `ring` event type instead of `press_short` (#3300). Home Assistant requires doorbell event entities to support `ring` (deprecation warning today, mandatory from HA 2027.4) and its new doorbell triggers listen for it. Other event types such as `press_long` are unchanged, as are the device triggers. **Breaking:** automations that trigger on the `press_short` event type of these _event entities_ must be switched to `ring`
- The doorbell device list now comes from openccu-data's curated `device_semantics` extract (via `aiohomematic.device_semantics.DOORBELL_MODELS`) instead of a hardcoded tuple — one source of truth shared with openccu-loom's MQTT discovery. The classic `HM-Sen-DB-PCB` joins `HmIP-DBB` and `HmIP-DSD-PCB`: its short press now fires the standard `ring` event type on its doorbell event entity (#3300 follow-up)
- Event entities now carry the full device identity (name, manufacturer, model, serial number, firmware) in their `DeviceInfo`. Previously they registered only the device identifiers — if an event entity happened to be the device's first registration, the device entry was created without a name and the generated (sticky) entity_id degraded to the config-entry title (e.g. `event.<instance_name>_ch1` instead of `event.<device_name>_ch1`)
- Reauthentication now reloads the config entry exactly once. The flow's entry update schedules a reload only when the registered update listener will not already do so (unloaded entry or unchanged data), replacing `ConfigFlow.async_update_reload_and_abort`, whose extra reload schedule alongside an update listener caused a double reload and is deprecated with HA 2026.12

### Blueprints

- `Show device error` no longer suggests parameters it can never receive. Its "Ignored error parameters" field named `CONFIG_PENDING` and `STICKY_UNREACH` as examples, and its description explained at length how a `CONFIG_PENDING` notification clears after a configuration transfer — but `homematic.device_error` only carries parameters whose name starts with `ERROR` or `SENSOR_ERROR`, so neither can ever reach this blueprint. The examples are now `ERROR_OVERHEAT` and `SENSOR_ERROR`, and the description states which parameters the event covers, that `ERROR_CODE` is excluded, and where CCU service messages are actually available (the `hub_service_messages` sensor). Reported in aiohomematic#3333; behaviour of the blueprint is unchanged

### Documentation

- README links the new [Events Reference](https://sukramj.github.io/aiohomematic/user/features/homeassistant_events/), which documents all seven events the integration fires on the HA event bus with their triggering parameters and payloads, and the Blueprints section now points to it — including the note that CCU service messages are not events

### Development

- Added a `Makefile` as the entry point for all development tasks (`make help` lists every target): setup, code quality (ruff, mypy, pylint, bandit, codespell, yamllint, prettier, translations, prek), tests (incl. coverage, CI mode and the opt-in e2e suite), hassfest/HACS validation, running Home Assistant against `./config`, and housekeeping. Targets run through `script/run-in-env.sh`, so they work with or without an activated virtual environment. `CLAUDE.md` and `CONTRIBUTING.md` document the targets; the broken `cov.sh` (it referenced a non-existent `.coveragerc`) is superseded by `make test-cov-html` and was removed
- Dual-backend parity hardening: a backend surface contract test (`tests/contract/test_backend_surface_contract.py`) inventories the `central.*` member and call surface the integration actually uses from the sources via AST and checks it against both backend classes, the three-way e2e suite gained behavioral parity probes (identical HA service calls, a CCU-side push, the config-surface paramset description) plus an entity-set parity ratchet that lets model coverage only grow, and the new `.github/workflows/e2e-parity.yaml` runs the suite as a gate on dependency-bump PRs and nightly. Test infrastructure only — no runtime effect
- Config flow and diagnostics groundwork for the openccu-loom backend (backend-aware flow titles, in-place backend switch on a matching CCU serial, sub-device toggle, serial-keyed manual setup, diagnostics on the compat adapter). The compile-time master switch `LOOM_BACKEND_SELECTABLE` is replaced by a discovery-based gate — the flow offers the backend when a daemon announces itself via mDNS or a loom entry already exists — and every entry point is marked Beta. A callback-signature fix in the active mDNS browse makes the daemon selection usable — zeroconf fires state changes with keyword arguments only, and it fires them from the browser constructor once the shared cache is warm, so the mismatched parameter names raised synchronously inside the flow step. The user-facing details stay out of scope for this changelog until the backend leaves Beta

### Dependencies

#### Bump aiohomematic to [2026.8.1](https://github.com/SukramJ/aiohomematic/compare/2026.7.6...2026.8.1)

- Fix calculated sensors (`OPERATING_VOLTAGE_LEVEL`, `VAPOR_CONCENTRATION`, `DEW_POINT`, …) staying `unknown` after a Home Assistant restart instead of restoring their previous state (#3332). `CalculatedDataPoint` inherited its validity from `BaseDataPoint`, where `is_valid` only aggregates `is_refreshed` and `is_status_valid` of the source data points — a source that was read at startup but returned no usable value still counts as refreshed, so the calculated data point reported itself valid while its value was `None`. Since a previous state is only restored for data points that report themselves as invalid, the restore path never ran and the entity waited for the physical device to send again. Validity now requires every state-carrying source to be valid itself
- Calculated data point validity is no longer gated by MASTER sources. Applying the ADR-0025 reasoning, only the readable VALUES sources carry state; MASTER paramset entries such as `LOW_BAT_LIMIT` are configuration inputs that a sleeping battery device may never deliver, and previously blocked `is_valid`, `is_refreshed` and `state_uncertain` of the whole calculated data point. A calculated data point without any readable VALUES source is now invalid rather than valid with `None`
- Fix XML-RPC commands hanging forever when a connection goes half-open. The operational XML-RPC proxy is now created with a socket timeout (`rpc_timeout`, 60 s by default), matching backend detection; previously it had none, so a silently dropped or half-open (TLS) keep-alive connection made a `setValue`/`putParamset` block indefinitely in the proxy's single worker thread. Since each interface has exactly one worker, that wedged the interface's entire outgoing command path until Home Assistant was restarted — commands were neither sent nor failed, the only visible symptom being the 30 s optimistic rollback, while incoming events kept arriving over the separate callback path. A stuck request now aborts as a retryable `NoConnectionException`, which frees the worker thread and lets the command retry handler react
- Fix data point names getting a redundant `ch<no>` postfix even when the channel's custom name is already unique (#3313). The postfix for parameters that exist on multiple channels of a device is now only appended when the channel name alone does not identify the channel — device-derived names, names following the `<name>:<no>` scheme, or several same-named channels providing the same parameter. A channel with a unique custom name (e.g. a status channel named `<sub device> Status`) keeps its clean entity name again
- New `aiohomematic.device_semantics` module exposing the curated device-semantics classifications from openccu-data — first classification: `DOORBELL_MODELS`, the basis for the doorbell-model change above (#3304)
- Adds the `ALARM_CONTROL_PANEL` category/type vocabulary — pure vocabulary, no behaviour change on the CCU path
- Raises the minimum `openccu-data` to `2026.7.2`, pulling in the corrected CCU translation and easymode artifacts (see below). The package is a transitive dependency, so the manifest bump is what applies it
- Unhandled task exceptions are logged with an explicit `exc_info` instead of `_LOGGER.exception()`. The handler runs from a task done-callback, i.e. outside an active exception handler, where `exception()` has no ambient traceback to draw on — some task failures previously lost their traceback in the log. Log level and output are otherwise unchanged

#### Bump openccu-data to [2026.7.2](https://github.com/SukramJ/openccu-data/compare/2026.6.1...2026.7.2)

- Adds the curated `device_semantics` extract (doorbell classification) that aiohomematic's new `device_semantics` module reads
- Regenerates the easymode and translation extracts as well as the `BLIND_VIRTUAL_RECEIVER`, `SHUTTER_VIRTUAL_RECEIVER` and `WATER_SWITCH_VIRTUAL_RECEIVER` profiles from the latest OCCU sources: a new `SHORT_OUTPUT_BEHAVIOUR` parameter in the water-switch profiles, `LONG_PROFILE_ACTION_TYPE` narrowed to a fixed value in the blind/shutter profiles, plus revised German/English help texts and value labels
- Fixes HTML character references leaking into display strings: the easymode and profile extractors now decode `&auml;`, `&amp;`, `&nbsp;` and friends, matching what the translation extractor always did. 36 profile files (197 strings) and the easymode archive were regenerated, so German umlauts and ampersands in parameter help texts and value labels render as characters instead of escape sequences

#### Bump aiohomematic-config to `2026.8.0`

- Tracking bump that raises its own `aiohomematic` and `openccu-data` floors to match the versions above. No functional change

#### Bump openccu-loom-client to `2026.8.6` (pins `openccu-loom-types==0.3.3`)

- Groundwork bump for the openccu-loom backend (Beta); it has no runtime effect on the direct-CCU backend. Advances the bundled loom client from `2026.7.6` to `2026.8.6` and its transitively pinned `openccu-loom-types` from `0.1.53` to `0.3.3`

#### homematicip-local-frontend

- Bundled `homematic-config.js` rebuilt. The device list now renders virtualized (new `hm-device-row` element behind `ha-list-virtualized`) once more than 100 filtered devices are shown and Home Assistant provides the element, which keeps large installations responsive; below that threshold the existing grouped rendering is unchanged
- The unsaved-changes warning in the channel and link configuration now also triggers when navigating away or closing the tab (capture-phase `click` interception plus `beforeunload`), not only via the panel's own back button
- The config panel header was restyled to match Home Assistant's standard toolbar/header design ([frontend #73](https://github.com/SukramJ/homematicip-local-frontend/pull/73), [@smoki3](https://github.com/smoki3))
- The device list and interface group headers now use Home Assistant's standard `ha-card` styling for visual consistency with the rest of HA, via a new `<hm-interface-header>` component ([frontend #75](https://github.com/SukramJ/homematicip-local-frontend/pull/75), [@smoki3](https://github.com/smoki3))
- Removed a duplicated view title in the device list ([frontend #76](https://github.com/SukramJ/homematicip-local-frontend/pull/76), [@smoki3](https://github.com/smoki3))

# Version [2.8.3](https://github.com/SukramJ/homematicip_local/compare/2.8.2...2.8.3) (2026-07-10)

## What's Changed

### Integration

- Expose the HmIP-DSD-PCB doorbell sensor's event with the `doorbell` event device class instead of the generic `button` (#3276). Its ring input channel produces an event group that previously fell back to the `button` default; it now matches the doorbell rule alongside the HmIP-DBB
- Expose color temperature for the HmIP-LSC (#3277). `supported_color_modes` now also honours the light's static color capabilities (`capabilities.hs_color`/`capabilities.color_temperature`), so a light that supports both color and color temperature — like the HmIP-LSC, which has no `DEVICE_OPERATION_MODE` and switches between the two at runtime — advertises `{hs, color_temp}` statically while `color_mode` keeps reporting the currently active mode via `has_*`. Lights with a single, mode-based color capability are unaffected
- Fix `light.turn_on` not switching the HmIP-LSC from color to color temperature (#3277). `async_turn_on` treated the two color modes as independent and, when only a color temperature was requested, still forwarded the *current* `hs_color` — so `HUE`/`SATURATION` and `COLOR_TEMPERATURE` were written together in one `putParamset` and the device kept the old color. The modes are now mutually exclusive: an explicit `color_temp_kelvin` or `hs_color` request is sent on its own, and the current value is only restored when no color is requested

### Dependencies

#### Bump aiohomematic to [2026.7.6](https://github.com/SukramJ/aiohomematic/compare/2026.7.2...2026.7.6)

- Fix cover, dimmer, switch, valve, lock, garage, siren and sound-player entities getting stuck in `value_state=restored` after a CCU restart (ADR-0025). Generalises the climate fix (#3255/#3279) to every custom data point class: secondary values (activity/direction readbacks, group-channel readbacks, colors, extra sensors, MASTER config values) that nothing re-polls could stay unrefreshed for hours and previously dragged the whole custom data point to `is_valid=False`. Validity is now gated by a single declarative per-class set of state-carrying fields (cover/blind/dimmer `LEVEL`, switch/valve/access-permission `STATE`, garage `DOOR_STATE`, locks `LOCK_STATE`/`STATE`/`BUTTON_LOCK`, climate `ACTUAL_TEMPERATURE` + setpoint + mode source, sirens' alarm-active states, sound player `ACTIVITY_STATE`); the climate `_validity_irrelevant_data_points` blocklist and the per-class `_relevant_data_points` overrides are replaced by this unified mechanism
- Fix the climate entity for HmIP-WTH-B (and other thermostats) failing to load — staying permanently `unavailable` — when the device's SETPOINT paramset description is incomplete (missing `MAX`, e.g. after a failed `getParamsetDescription`) (#3281). `max_temp` returned `None`, so caching the week profile raised an uncaught `TypeError` out of Home Assistant's entity setup, while an identical device with a complete paramset description worked fine. `max_temp` now falls back to a fixed upper bound (`30.5`) when neither a `TEMPERATURE_MAXIMUM` value nor a SETPOINT `MAX` is available (mirroring the existing `min_temp` guard), and the week-profile conversion now degrades gracefully — the entity loads and only the schedule stays uncached
- Internal aiohomematic simplification (−5,800 LOC) from a consumer-surface audit against this integration: removes the unused `hmcli` console script, the `HomematicAPI` facade, `SysvarStateChangedEvent`, the `tracing` / `logging_context` modules and the Kind/payload property-metadata subsystem, and flattens 37 zero-use interface protocols (120 → 83). Every removed symbol was verified to have zero usage in homematicip_local, so there is no user-facing effect
- Fix valve-only `HmIP-HEATING` groups (built from `HmIP-eTRV` valves without a wall thermostat) freezing `current_temperature` / `current_humidity` at the last-(re)start value (#3279). Follow-up to #3255: these groups always expose `HUMIDITY` and `HEATING_COOLING` on the group channel, but only a group containing a wall thermostat (`HmIP-WTH`/`STHD`) ever receives events for them — in a valve-only group those readable data points never refresh, and since #3228 `VirtualDevices` get no `getValue` fallback, so they dragged the whole custom climate data point to `is_valid=False` (leaving the climate entity in `value_state=restored` with a frozen current temperature) even though `ACTUAL_TEMPERATURE` kept arriving via events. #3255 only excluded the actuator values `LEVEL` / `STATE`; the climate validity check now also ignores `HUMIDITY` / `HEATING_COOLING`, so a group's climate validity follows its aggregated `ACTUAL_TEMPERATURE` regardless of whether a wall thermostat is present
- HmIP-LSC now exposes color temperature in addition to color (#3277): a dedicated `CustomDpIpRGBWColorTempLight` advertises both color modes statically and derives the active mode from the value the device reports

#### Bump openccu-loom-client to `2026.7.6` (pins `openccu-loom-types==0.1.53`)

- Groundwork bump for the still-disabled openccu-loom backend; it has no runtime effect while the backend master switch (`LOOM_BACKEND_SELECTABLE` in `const.py`) stays off. Advances the bundled loom client to `2026.7.6` and its transitively pinned `openccu-loom-types` from `0.1.50` to `0.1.53`

# Version [2.8.2](https://github.com/SukramJ/homematicip_local/compare/2.8.1...2.8.2) (2026-07-08)

## What's Changed

### Integration

- Fix calculated data points on internal / heating-group channels (Taupunkt/dew point, Dampfkonzentration/vapor concentration, Enthalpie/enthalpy, Taupunkt-Spreizung/dew-point spread) being orphan-deleted and re-created disabled under a new, name-doubled `entity_id` after the central-id realign migration (#3272). Their unique_ids carry a `calculated_` marker between the central-id slot and the channel infix (`<central-id>_calculated_int000…`), which `realign_hub_unique_id` did not recognise, so — unlike every other hub/internal key — they were left on the stale anchor, no longer matched the live central id, and were swept away by the orphan cleanup (losing manual enablement and history). The realign now handles the `calculated_` variant; device-anchored calculated DPs (`calculated_<serial>_…`, no central-id slot) stay untouched
- Relax the aiohomematic version gate in `async_setup_entry` from an exact-match check to a minimum-version check. Setup is now only blocked when the installed aiohomematic is **older** than the version this release was built against; a newer (patch) aiohomematic no longer aborts setup. This fixes spurious "requires aiohomematic version X, but found version Y / setup blocked" failures (#3275) that occurred when HA/pip resolved a newer aiohomematic than the manifest pin via transitive, upper-bound-less dependencies

### Dependencies

#### Bump aiohomematic to [2026.7.2](https://github.com/SukramJ/aiohomematic/compare/2026.7.1...2026.7.2)

- Fix CUxD/CCU-Jack devices going unavailable after init (#3228): the per-parameter `getValue` fallback is now disabled for these JSON-RPC interfaces (added to `INTERFACES_SKIPPING_INIT_GETVALUE_FALLBACK`), which previously flooded the CCU session pool during initialization and marked the devices unavailable. Values now arrive via the bulk `get_all_device_data` fetch and MQTT events instead, and a contract test guards the behaviour
- Fix a JSON-RPC session login race on cold start: concurrent login attempts previously created multiple CCU sessions simultaneously, risking "too many sessions" errors. `_login_or_renew` now serializes login/renew with an `asyncio.Lock` (with a lock-free fast path for recently refreshed sessions), so only one session is created at startup

# Version [2.8.1](https://github.com/SukramJ/homematicip_local/compare/2.8.0...2.8.1)

## What's Changed

### Integration

- Fix the startup orphan cleanup permanently deleting entities of devices that are only still loading (e.g. a paramset-cache rebuild on upgrade, when the central reports `RUNNING` before every device is built), which re-created them disabled and under a new `entity_id`. Device entries whose device is not yet loaded are now kept; genuine orphans (device present but data point gone, or device removed) stay sweepable

# Version [2.8.0](https://github.com/SukramJ/homematicip_local/compare/2.7.2...2.8.0) (2026-07-05)

## What's Changed

### Integration

- **Requires Home Assistant 2026.7.0 or newer** (was 2026.6.0): all sensor/number unit constants were migrated from the deprecated top-level constants (`PERCENTAGE`, `CONCENTRATION_PARTS_PER_MILLION`, `CONCENTRATION_GRAMS_PER_CUBIC_METER`, `CONCENTRATION_MICROGRAMS_PER_CUBIC_METER`) to the `UnitOfRatio` / `UnitOfDensity` enums introduced in HA 2026.7 — across the entity-description registry (hub metrics, air-quality, battery, level/valve and duty-cycle/carrier-sense sensors, the percentage-number factory and the unit fallbacks). The rendered units are identical, so there is no user-facing change beyond the raised minimum version (enforced by both `hacs.json` and the integration's startup check)
- Fix hub, system-variable, install-mode, virtual-remote and virtual-remote event-group entities disappearing on upgrade (frontend#63): after the move to serial-anchored hub `unique_id`s, the one-time re-anchor migration only matched registries anchored on the *current* `entry_id[-10:]`. A registry inherited from any other anchor (a prior `entry_id` after a delete + re-add, or a stale serial) fell through, no longer matched the live keys, and was then permanently deleted by the startup orphan cleanup. The migration now realigns whatever value fills the central-id slot onto the live anchor (covering plain hub keys *and* the virtual-remote event groups), runs before entities are recreated, and skips on a `unique_id` collision instead of aborting. As defence-in-depth the orphan cleanup no longer deletes an entry whose data point still exists under a different central-id anchor (it leaves the realign migration to re-anchor it), and no longer deletes the integration-native `create_backup` button (which has no aiohomematic data point and is recreated on every setup)
- Fix permanent mass deletion of entity-registry entries after a transient auth error (aiohomematic#3215): the startup orphan cleanup now refuses to run when it would remove more than half of the integration's registry entries — this guards against the central reporting `RUNNING` (clients connected) while the device descriptions failed to load, which previously wiped hundreds of entities and re-detected devices as new
- Set `EventDeviceClass.DOORBELL` for HmIP-DBB event entities so they work with the new Home Assistant `doorbell` automation trigger; all other event entities continue to use `EventDeviceClass.BUTTON`
- Routed the event entity device class through the `EntityDescriptionRegistry` (new `HmEventEntityDescription`, `event()` factory, `EVENT_RULES`, default for `DataPointCategory.EVENT_GROUP`) instead of hardcoding it on the entity class
- The **openccu-loom backend** (loom client + integration adapter) is bundled as groundwork for a future alternative to the direct-CCU (aiohomematic) backend, but is **not user-selectable in 2.8.0**: the backend master switch (`LOOM_BACKEND_SELECTABLE` in `const.py`) is off, so a fresh setup goes straight to the direct-CCU step and the loom path behaves as if it were absent. No user-facing behaviour change.

### Blueprints

- The **Show device error** blueprint gains two optional filters — a device selector (`target_devices`, empty = all devices) and a comma-separated, case-insensitive ignore list of error parameters (`ignored_parameters`, e.g. `CONFIG_PENDING, STICKY_UNREACH`) — so noisy or expected errors can be suppressed without disabling the automation. The description now also explains that some errors are expected and self-resolve: after deleting a direct link (Direktverknüpfung) in the CCU/OCCU the removal is delivered to the device via a configuration transfer, and until that completes `CONFIG_PENDING` stays true and the link still lives in the device; for battery/RF devices the transfer only runs on the next radio contact (e.g. a button press), after which the notification clears automatically — no factory reset required (aiohomematic#3246)

### Dependencies

#### New bundled dependency: `openccu-loom-client==2026.7.1` (pins `openccu-loom-types==0.1.50`)

- Bundled for the not-yet-enabled openccu-loom backend (see Integration); it has no runtime effect while the backend master switch is off. Pulls `openccu-loom-types==0.1.50` transitively.

#### Bump aiohomematic to [2026.7.1](https://github.com/SukramJ/aiohomematic/compare/2026.5.11...2026.7.1)

- Add per-user access-permission switches for HmIP-DLD (`:2`–`:9`) and HmIP-FWI (`:1`–`:8`), mirroring the `PERMISSION_STATE` switches already added for HmIP-DLP (#3262): unlike the DLP's single read/write `PERMISSION_STATE` parameter, these devices split the permission into a read-only `STATE` and a write-only `ACCESS_AUTHORIZATION` (ENUM `DISABLE`/`ENABLE`), which the new `CustomDpIpAccessPermission` custom data point combines into a single switch (`value` reflects `STATE`; `turn_on` / `turn_off` write `ACCESS_AUTHORIZATION`). The profile keeps the devices' unrelated data points (HmIP-FWI access codes, output switches, week program) via `allow_undefined_generic_data_points`
- Stop BidCos-RF filling not-yet-refreshed `VALUES` with `getValue` defaults (#3260): passive/battery BidCos-RF devices cannot be actively queried, so the per-parameter `getValue` init fallback returned the paramset default (marked valid) instead of a real reading, masking an actually uncertain state for devices that had not reported yet. As already done for VirtualDevices (#3228), the fallback is now skipped for the BidCos-RF interface — readable `VALUES` keep their (unset) `NO_VALUE` state until a real value arrives via event, and the bulk ReGa fetch (which filters placeholders via `LastTimestamp`) remains the trustworthy init source
- Fix heating-group `climate` entities freezing `current_temperature` / `current_humidity` at the last-(re)start value (#3255): for `HmIP-HEATING` groups (VirtualDevices interface) the CCU never sends events for the actuator data points `LEVEL` / `STATE` / `VALVE_STATE`, and after the #3228 fixes the `getValue` fallback returns `NO_VALUE` for VirtualDevices — so those readable data points stayed unrefreshed forever and dragged the whole custom climate data point to `is_valid=False`, leaving the climate entity in `value_state=restored` with frozen current temperature/humidity while the sibling `sensor.*` entities (gated on their own data point) kept updating. The validity check now ignores these actuator/activity data points (`CustomDpIpThermostat` excludes `LEVEL` / `STATE`, `CustomDpRfThermostat` excludes `VALVE_STATE`); the values themselves are unaffected and still arrive via events when the CCU sends them
- Keep the idle value `31` for the HmIP-FWI fingerprint reader's `CODE_ID` (#3238): the CCU declares the parameter maximum as `21`, but the device reports `31` when idle, so the number entity dropped the idle value and could not return to `31`. A paramset patch now expands the `CODE_ID` maximum to `31` for HmIP-FWI; the paramset cache schema is bumped to version 4 so the corrected bounds are rebuilt from the CCU
- Roll back optimistic values immediately on a failed collector send (#3238): a write the CCU rejected (e.g. an XML-RPC `RESPONSE_NAK` after all retries were exhausted) previously left the optimistic value active for the full 30 s `optimistic_update_timeout` on the collector path, so the entity kept displaying a value that never reached the device until the timeout rollback fired. The collector send path now mirrors the direct-send path and rolls back the affected data points' optimistic values immediately on a send error
- Fully fix sensors reporting a spurious `0` after a CCU restart (#3228): the initial `2026.6.3` fix only covered the ReGa bulk-load path, but the placeholder also arrived through the per-parameter `getValue` fallback. Three follow-ups complete it — (a) the paired `*_STATUS` parameter is now loaded on init so a freshly loaded default whose status is `UNKNOWN` no longer overwrites an already known value (#3233), (b) the bulk-load ReGa script was reworked to v2.5 because the earlier `vDPValue == ""` skip also dropped legitimate numeric zeros (an empty string coerces to `0` in ReGa) — it now only coerces genuine string variables and gates `VirtualDevices` on a valid `LastTimestamp()`, and (c) the `getValue` fallback is skipped entirely for `VirtualDevices`, whose aggregated `ACTUAL_TEMPERATURE` has no physical device behind it and could therefore only ever return the CCU default `0`. The gated ReGa bulk fetch is now the single source of truth, and such a data point stays unavailable until a real reading arrives via event. Physical interfaces and real `0` readings are unaffected
- Fix HmIP-RGBW / HmIP-DRG-DALI cannot be switched on (briefly flashes, then turns off again) (#3210)
- Make interrupted device creation observable — `CancelledError` mid-build now logs a clear warning instead of silently abandoning the run with zero entities (#3213)
- Revert the contract/event-type extraction (#3214): public event types stay in `aiohomematic.central.events`, no separate `aiohomematic-contract` runtime dependency

#### Bump openccu-data to [2026.6.1](https://github.com/SukramJ/openccu-data/compare/2026.5.0...2026.6.1)

- Restore the curated device-model labels for `HmIP-DLP`, `HmIP-UDI-SMI55`, `HmIP-SMO230` and `HmIP-SWDO-PL-2`: these models ship only as `device_icons` in the OCCU extract (no `device_models` entry), so without the curated overlay label they fell back to the raw model id in downstream consumers
- Regenerate the bundled `easymode_extract.json.gz` and `translation_extract.json.gz` from the latest OCCU sources

#### aiohomematic-config remains at [2026.5.0](https://github.com/SukramJ/aiohomematic-config/releases/tag/2026.5.0)

- No API or behavior changes for the integration since 2.7.2

#### homematicip-local-frontend

- Bundled `homematic-config.js` rebuilt; the prior 2.7.2 build already covered HA 2026.6 compatibility ("HA 2026.6 Compatibility — `ha-radio` Removal (#60)")

# Version [2.7.2](https://github.com/SukramJ/homematicip_local/compare/2.7.1...2.7.2) (2026-05-29)

## What's Changed

### Integration

- Dependency-bump release; no behavioral changes in the integration itself
- Rebuilt bundled frontend (`homematic-config.js`) against the latest `homematicip-local-frontend` commit for HA 2026.6 compatibility

### Dependencies

#### Bump aiohomematic to [2026.5.11](https://github.com/SukramJ/aiohomematic/compare/2026.5.9...2026.5.11)

- Fix Switch/cover/valve schedule round-trip when the CCU paramset advertises fields the device category doesn't support (#3198): `ramp_time` / `level_2` / `duration` are now cleared for `SWITCH`, `LIGHT`, `COVER`, `VALVE`, `LOCK` so reads no longer emit entries that the subsequent `set_schedule()` rejects
- Fix blocking file I/O in the event loop on first easymode access: the gzip archive (`openccu_data/data/easymode_extract.json.gz`) was loaded lazily via `read_bytes()` on the first `get_*()` call, triggering HA's blocking-call warning during `ws_get_form_schema` — archive is now loaded eagerly at import time, all later lookups are pure dict reads

#### Bump aiohomematic-config to [2026.5.0](https://github.com/SukramJ/aiohomematic-config/compare/2026.4.7...2026.5.0)

- Tracks the `aiohomematic` 2026.5.10 / `openccu-data` 2026.5.0 minimums; no API or behavior changes for the integration

#### homematicip-local-frontend (last commit "HA 2026.6 Compatibility — `ha-radio` Removal")

- Replaces the removed `ha-radio` element (gone in HA 2026.6) in `form-parameter` and `add-link` to keep the config panel working on 2026.6

# Version [2.7.1](https://github.com/SukramJ/homematicip_local/compare/2.7.0...2.7.1) (2026-05-06)

## What's Changed

### Integration

- Fix `homematic.device_availability`/`device_error` events silently dropped when `event.device_name` was empty (fallback to HA device-registry name)
- Auto-remove orphaned entity-registry entries (incl. disabled) on startup (#3176) — replaces the "enable → reload → delete" workaround
- Fix orphan cleanup deleting hub-backed entities (`system_update`, `inbox`, `service/alarm_messages`, `install_mode`, metrics, connectivity, program buttons) on every restart: sweep now aggregates all hub singleton/mapping DPs from `hub_coordinator`; delay reduced 120 s → 60 s

### Dependencies

#### Bump aiohomematic to [2026.5.9](https://github.com/SukramJ/aiohomematic/compare/2026.5.0...2026.5.9)

- Fix climate `activity` reporting `HEAT` in cooling mode (HmIP-WTH-1 + HmIP-FALMOT-C12)
- Fix RF dimmer flicker during ramps — `LEVEL_REAL` is now the authoritative status source
- Fix HM `LOWBAT` not propagated to `MaintenanceData.low_bat`
- Fix `HmIP-RGBW`/`HmIP-DRG-DALI` `turn_off` with `transition` rejected by CCU (regression from 2026.4.7)
- Three follow-up fixes for residual dimmer flicker during/after ramps (#3177): in-flight command tracking, recency-based `_effective_level` fallback
- Fix HmIP dimmer brightness showing state-channel summary instead of commanded value (#3181): #3166 mirror logic restricted to RF dimmers (`LEVEL_REAL`); HmIP falls back to action channel
- Expose `inbox_dp` and `update_dp` as `DelegatedProperty` on `HubCoordinator`
- Fix automatic reconnect after startup failure when the CCU is not yet reachable (#3183): `EventBus.publish()`/`publish_batch()` now merge key-specific and wildcard subscribers instead of short-circuiting — the `ConnectionRecoveryCoordinator`'s heartbeat retry loop now actually runs when HA starts before the CCU is ready
- Fix central stuck in `FAILED` after a startup-failure recovery succeeds (#3183 follow-up): heartbeat recovery path now hops through `RECOVERING` and keeps `_active_recoveries` populated so the final `_transition_to_running()`/`_transition_to_degraded()` actually fires — previously entities stayed unavailable until reload even though every interface reconnected

#### aiohomematic-config remains at [2026.4.7](https://github.com/SukramJ/aiohomematic-config/releases/tag/2026.4.7)

- No API or behavior changes for the integration since 2.7.0

#### homematicip-local-frontend (last commit unchanged since 2.7.0)

- Latest commit "Schedule Card — Valve as Binary, Duration Limits (#57)", already shipped with 2.7.0

# Version [2.7.0](https://github.com/SukramJ/homematicip_local/compare/2.6.0...2.7.0) (2026-04-22)

## What's Changed

### Integration

- Per-channel schedule enable/disable support for non-climate week profiles (WebSocket endpoint + sensor attribute)
- Schedule switch entities are now disabled by default in the entity registry
- Schedule entities (week profile sensor, schedule switch) now consistently use "Zeitplan"/"Schedule" in their name, both with and without sub-devices enabled
- Fixed schedule sub-device naming: schedule devices now correctly include "Schedule"/"Zeitplan" in their name when sub-devices are enabled
- Added configurable `command_retry_max_attempts` setting in advanced config (default: 3, range: 0-10) for the new command retry mechanism
- Added `retry` parameter to `set_device_value`, `put_paramset`, and `put_link_paramset` services (default: true) to leverage the new command retry mechanism in aiohomematic
- Added missing config flow translations (EN/DE) for `command_retry_max_attempts`
- Fixed KeyError when `command_retry_max_attempts` is absent from existing config entries
- Enabled parallel test execution via pytest-xdist (`-n auto --dist loadscope`)
- Internal code quality: aligned linter configuration with aiohomematic / HA core
  - Ruff: bumped target to Python 3.14, modernized `[tool.ruff.lint]` section syntax, enabled rule families `A`, `ASYNC`, `BLE`, `FURB`, `PTH`, full `S` (bandit), `SLF`, `TC`, `TID` and additional `B`/`RUF` checks; lowered mccabe complexity from 25 to 15; added banned-api entries for `async_timeout` and `pytz`; explicit `pep257` docstring convention
  - Mypy: enabled `possibly-undefined` and `unused-awaitable` error codes
  - Pylint: added `pylint_per_file_ignores` plugin, enabled `useless-suppression`, removed deprecated `extension-pkg-whitelist`
  - Pytest: added `log_format`, `asyncio_debug`, custom markers and `filterwarnings`
  - Coverage: enabled branch coverage and extended `exclude_lines` for protocol stubs and abstract methods
  - Pre-commit: bumped `python-typing-update` to `--py314-plus` and included integration sources; bandit no longer scans test fixtures
- Refactored `async_migrate_entry` into a dispatch table of pure data-only migrations (per-version helpers)
- Split `_on_system_status` into per-detail handlers (central / connection / client / callback / issues)
- Moved blocking `Path.mkdir`/`Path.write_bytes` off the event loop in CCU backup paths (button, services, update, websocket_api)

### Blueprints

- Modernized all blueprints: replaced deprecated `service:` with `action:`, simplified condition templates to shorthand syntax
- Added `homeassistant.min_version: "2026.3.0"` to all blueprints
- Added multi-device support to all button blueprints (2, 4, 6, 8-button)
- Added CCU direct-link detection to all button blueprints: optional warning notification and action skip when CCU direct connections exist for the pressed button (based on community contribution by @hosswald)
- Added configurable delay to all reactivate-device blueprints (default: 10 seconds)
- Updated all blueprint versions to v2026-04-14
- Added comprehensive blueprint test suite (171 tests): schema validation, input validation, template substitution, full-flow end-to-end tests including direct-link detection and all button-subtype mappings

### Dependencies

#### Bump aiohomematic to [2026.5.0](https://github.com/SukramJ/aiohomematic/compare/2026.4.6...2026.5.0)

- Added device profile for HmIP-UDI-SMI55
- Added `ScheduleChannelSwitch` data point for per-channel schedule enable/disable
- Per-channel schedule enable/disable via `COMBINED_PARAMETER` (atomic bitmask + mode write)
- Load `WEEK_PROGRAM_CHANNEL_LOCKS` value at startup (fixes delayed `schedule_enabled` attribute)
- Command retry mechanism for transient failures (automatic retry with backoff for temporarily unreachable devices)
- Lock schedule support for HmIP-DLD and HmIP-DLP (door lock mode, user permission mode, domain validation)
- Extract MASTER paramset metadata from CCU WebUI dialog functions
- Support non-climate link roles (HmIP-RCV-50 virtual remote and other non-climate devices now linkable via "Add Direct Link" wizard)
- Added `WeekProfile.supported_schedule_fields` exposing the `ScheduleField`s the device advertises; forwarded as entity attribute so frontends can hide non-functional schedule inputs (e.g. HmIP-DLD)
- Validate schedule writes against paramset description (`check_against_pd=True`) — unsupported `WP_*` parameters now raise a clear `ClientException` instead of being silently rejected
- Schedule duration encoding now uses natural Homematic time bases and promotes to a coarser base only when the factor would overflow the CCU's `factor=30` cap, so requests like `"40min"` no longer get silently clamped to 31 minutes on the device
- `SimpleScheduleEntry` rejects unrepresentable durations (e.g. `"31h"`, `"301s"`, sub-100ms) at validation time with a clear `ValueError` instead of letting the CCU clamp them; use `duration=None` for "permanent"
- Fixed schedule target channels for multi-config lock devices
- Fixed missing DURATION_UNIT/DURATION_VALUE in putParamset for turn_on and turn_off (HmIP-BSL, HmIP-RGBW, HmIPW-WRC6, HmIP-DRG-DALI)
- Fixed RAMP_TIME_TO_OFF usage for RGBW and DRG-DALI lights
- Fixed siren duration always sent on turn_on
- Fixed HmIP-RCV-50 (and similar devices) missing from the panel device list due to empty CHILDREN entries
- Fixed HmIP-DLD silently rejecting schedule updates by filtering unsupported schedule fields before `put_paramset`
- Improved logging for unsupported JSON-RPC methods (warning instead of error) and for devices with failing configurable-channel lookup
- Internal code quality: stricter linter configuration (ruff `S`/`BLE`/`PTH`, lowered mccabe complexity, additional bandit checks, mypy `possibly-undefined`/`unused-awaitable`), migration of filesystem operations to `pathlib`, narrowed broad exception handlers, and refactored complex functions for readability
- Adopt the new [openccu-data](https://github.com/sukramj/openccu-data) package as the source-of-truth for CCU translation and easymode metadata; dropped the vendored `aiohomematic/ccu_data/` tree (public API unchanged)

#### Bump aiohomematic-config to [2026.4.7](https://github.com/SukramJ/aiohomematic-config/compare/2026.4.1...2026.4.7)

- Per-channel `schedule_enabled` field on `DeviceScheduleData`
- Added `supported_schedule_fields` on `DeviceScheduleData` exposing which `ScheduleField`s the device advertises
- Use `get_ui_label_translation()` from aiohomematic
- Fall back to the locale-aware "Other Settings" label for metadata parameter groups without `label_key` or populated `label` mapping (prevents raw group ids like `group_5` from leaking to the UI)
- Tightened code quality tooling (ruff/mypy/pylint/bandit/pytest) in line with aiohomematic and HA core
- Adopt the new [openccu-data](https://github.com/sukramj/openccu-data) package as the source-of-truth for easymode link-profile data; dropped the vendored `aiohomematic_config/profiles/` directory (public API unchanged)

#### Bump homematicip-local-frontend

- Per-channel schedule enable/disable as clickable channel chips
- Added schedule support for lock devices
- Improved the schedule card layout to reduce vertical space usage
- Removed misleading "Update verfügbar" badge from CCU dashboard System Information card
- Device schedule editor now hides unsupported schedule fields (e.g. for HmIP-DLD) based on `supported_schedule_fields`
- Fixed lock schedule editor labels and translations
- Fixed cards showing "Konfigurationsfehler" in Firefox
- Config panel now available for all backends (CCU and Homegear); OpenCCU tab only shown for CCU backends
- Fixed cards showing infinite loading spinner in HA Card Picker and on dashboards
- Fixed device icons invisible or poorly visible in dark mode
- Schedule card: switched the `valve` domain from a 0–100% slider to a binary on/off control to match CCU semantics for water valves (HmIP-WSM / ELV-SH-WSM); selecting <100% no longer accidentally closes the valve
- Schedule editor enforces the CCU's `DURATION_FACTOR`/`RAMP_TIME_FACTOR` cap of 30 per unit (≤30 for `s`/`min`/`h`, ≤3000 in 100 ms steps for `ms`); invalid values are rejected upfront instead of being silently clamped on the device, and switching units clamps to the new unit's max
- Added a "Permanent"/"Dauerhaft" toggle in the device schedule editor that sets `duration=null` (no auto-revert); the schedule list now displays "Permanent"/"Dauerhaft" instead of `-` for these entries

---

# Version [2.6.0](https://github.com/SukramJ/homematicip_local/compare/2.5.2...2.6.0) (2026-04-09)

## What's Changed

### New Frontend Cards

All frontend cards are now delivered directly through the integration — no separate HACS installation required. Cards are automatically available once the integration is loaded. Existing standalone HACS installations are detected and skipped with a console warning.

- **Climate Schedule Card** (`homematicip-local-climate-schedule-card`): Visual weekly thermostat schedule editor with profile switching, copy/paste, and import/export. Edit heating schedules conveniently right from your Home Assistant dashboard.
- **Schedule Card** (`homematicip-local-schedule-card`): Schedule editor for switches, lights, covers, and valves with fixed-time and astronomical conditions (sunrise/sunset). Supports multiple switching points per day with different values.
- **Status Cards** (`homematicip-local-status-card`) — three new cards in one bundle:
  - `homematicip-system-health-card`: System health score, device statistics, Duty Cycle/Carrier Sense levels per radio module, optional incidents list
  - `homematicip-device-status-card`: Device status overview with filtering (all/problems/unreachable/low battery/config pending)
  - `homematicip-messages-card`: Service and alarm messages with acknowledge buttons

### Integration

- **HmIP-DLP support**: Added entity descriptions for door lock panel — door sensor (binary sensor), sabotage sensors, lock state reason (sensor), auto-relock and permission state (switches)
- **Non-admin schedule editing**: Non-admin users can edit device schedules via the schedule cards when enabled in Options Flow. Backend enforces permissions via `@require_scope` decorator (WebSocket) and `check_service_permission()` (service calls). New `get_user_permissions` WebSocket endpoint for frontend permission queries.

### Dependencies

#### Bump aiohomematic to [2026.4.4](https://github.com/SukramJ/aiohomematic/compare/2026.3.1...2026.4.6)

- Additional data points for HmIP-DLP (door state, permission, lock state reason, auto-relock, sabotage)
- Channel name exposed in configurable device channels, device links, and linkable channels
- Multi-channel detection cache for additional data points
- Synthesize missing parameter name translations from value entries
- Clamp schedule level_2 to [0.0, 1.0]
- Always populate unconfirmed value on set (fixes unknown state after setting same value)
- Fixed multi-channel postfix for data point names
- Fixed spurious optimistic rollbacks for CUxD/CCU-Jack devices

#### Bump aiohomematic-config to [2026.4.1](https://github.com/SukramJ/aiohomematic-config/compare/2026.3.1...2026.4.1)

- `operations` field on `FormParameter` exposing the raw OPERATIONS bitfield from the paramset description
- Receiver type alias resolution for shared easymode profiles (e.g. `OPTICAL_SIGNAL_RECEIVER` → `DIMMER_VIRTUAL_RECEIVER`)
- Easymode metadata enrichment: conditional visibility, presets, subset groups
- Cross-validation constraints model and semantic parameter grouping
- Master profile store for MASTER paramset easymode profiles
- HmIP channel type resolution for correct CCU translations

#### Bump homematicip-local-frontend

- Integration-bundled cards: climate schedule card, schedule card, and three new status cards
- Non-admin permissions (Phase 2): backend-enforced permission scopes, read-only mode
- UX Review — Full CCU Parity & Mobile Optimization (57 items resolved)
- Redesigned device schedule list: three-line card layout
- OpenCCU dashboard: Inbox, Service Messages, Alarm Messages
- Easymode support for paramset editor
- Integration dashboard: system health, device statistics, throttle stats, incidents
- HA 2026.3.0+/2026.4.0+ compatibility
- Improved mobile layout across all packages

---

# Version [2.5.2](https://github.com/SukramJ/homematicip_local/compare/2.4.1...2.5.2) (2026-03-30)

## What's Changed

### Breaking Changes

- **Removed SysVar entities for alarm/service messages**: The system variables
  `${sysVarAlarmMessages}` (ID 40) and `${sysVarServiceMessages}` (ID 41) are no
  longer auto-enabled and renamed. These are superseded by the dedicated hub
  sensors `HmAlarmMessagesSensor` and `HmServiceMessagesSensor`. Users who
  have automations referencing the old SysVar-based entity IDs
  (`sensor.*_sysvar_alarm_messages` / `sensor.*_sysvar_service_messages`) must
  update them to use the new hub sensor entities
  (`sensor.*_hub_alarm_messages` / `sensor.*_hub_service_messages`).

### Integration

- **Hub data WebSocket API**: `ws_get_hub_data` now reads alarm/service message
  counts directly from the dedicated hub data points instead of iterating over
  system variable data points
- **SubscriptionGroup**: Event bus subscriptions managed via `SubscriptionGroup` instead of manual callback tracking
- **Device name from events**: Event handlers (`_on_device_trigger`, `_on_optimistic_rollback`, `_fire_device_availability_event`) now use `event.device_name` from aiohomematic, falling back to HA device registry only for user-overridden names
- **DataPointType-based platform routing**: `get_new_data_points()` uses `DataPointType` enum instead of concrete class types, decoupling platform setup from aiohomematic model internals
- **Unified subscription architecture**: Entity-level subscriptions migrated from `subscribe_to_data_point_updated()`/`subscribe_to_device_removed()` to EventBus `SubscriptionGroup.subscribe()` with `DataPointStateChangedEvent`/`DeviceRemovedEvent`. Data point registration via `register()`/`unregister()` replaces `custom_id` ownership
- **State transition handlers**: Central state transitions (RUNNING/RECOVERING) handled via `CentralStateChangedEvent` subscription; DEGRADED/FAILED remain on `SystemStatusChangedEvent` for access to failure details
- **Exclude message attributes from recorder**: `AioHomematicSysvarSensor` excludes `alarm_1`..`alarm_99` and `message_1`..`message_199` attributes from recorder to prevent database bloat

### Config Panel

- Easymode support for paramset editor — conditional visibility, preset dropdowns, and subset groups for context-dependent device configuration forms
- Cross-validation translations (en/de) for min/max, level range, and threshold constraints
- Active climate profile indicator — profile dropdown now shows which profile is active on the device (e.g. "Profil 1 (Aktives Profil)")
- Device detail improvements: RSSI Peer always shown, Duty Cycle and Reachability displayed as Yes/No
- Device icons displayed in device list, device detail, and channel config views (via CCU proxy endpoint)
- Parameter help text with Markdown formatting below each parameter
- MASTER paramset time presets — unit/value parameter pairs displayed as a single preset dropdown (13 standard Homematic presets, 100ms–15 minutes)
- Dropdown and radio options now use translated labels from the backend
- HmIP-specific parameter translations — config panel now resolves HmIP channel types for correct CCU translations (e.g. `SHUTTER_CONTACT` → `SHUTTER_CONTACT_HMIP`)
- OpenCCU dashboard: sub-tab navigation (General, Messages, Signal Quality, Firmware); all table columns sortable; filter bars for Signal Quality and Firmware tables (shown when >10 devices)
- OpenCCU dashboard: Messages tab with Inbox (accept devices with rename and auto-confirm), Service Messages (acknowledge), and Alarm Messages (acknowledge) — badge shows total count
- Climate and device schedule editors now use shared `@hmip/schedule-ui` components
- Semantic parameter grouping from easymode metadata with locale-aware labels
- Cross-parameter validation exposed via `CrossValidationConstraint` model
- Fixed `ha-slider` and `ha-select` event handling in paramset and schedule editors (slider changes not registering, event leaking, dropdown closing dialogs)
- Fixed device schedule entries without target channels not being shown; target channels are now optional
- Fixed UTF-8 link names showing as mojibake (e.g. "KÃ¼chenblock" instead of "Küchenblock")
- Fixed editor dialog closing on save when validation errors exist
- Fixed copy/paste schedule icons overflowing at narrow widths

### Dependencies

#### Bump aiohomematic to [2026.4.0](https://github.com/SukramJ/aiohomematic/compare/2026.3.8...2026.4.0)

- **Fixed forced-to-sensor data points not publishing events**: Data points with `force_to_sensor()` (LEVEL on HmIP-eTRV and HmIP-HEATING) published events with the internal `_unique_id` instead of the `unique_id` property, causing key mismatches and orphaned subscriptions (memory leak)
- **Fixed false channel identification for hub data points**: Renamed `rega_id` to `ise_id` to correctly identify hub data point channels
- **Fixed acknowledge for alarm messages**: ReGa script for acknowledging alarm messages corrected
- **Message enrichment**: `ServiceMessageData` and `AlarmMessageData` include pre-resolved fields (`message_code`, `display_name`, `msg_type_name`) with i18n support (en/de)
- **Individual message attributes**: Message sensors expose each message as individual extra state attribute (`alarm_1`, `message_1`, ...) with human-readable display names
- **ServiceMessageType enum extended**: Added `ALARM`, `UPDATE_PENDING`, and `COMMUNICATION` types
- **DST-safe health checks**: Replaced `datetime.now()` with `time.monotonic()` for callback alive and connection checks, preventing false timeouts during DST transitions
- **Alarm messages fix**: Fixed ReGa script not returning active alarm messages for system alarms with sentinel trigger data points
- **Service messages hub sensor**: New sensor exposing active CCU service messages — count as state, full message details as attribute
- **Alarm messages hub sensor**: New sensor exposing active CCU alarm messages (Alarmmeldungen) — count as state, full message details as attribute
- **Acknowledge messages**: Support for acknowledging service and alarm messages via ReGa scripts
- **CCU data gzip consolidation**: CCU-sourced data (easymode metadata, translations) consolidated into gzip archives — 95% package size reduction (~11 MB → ~516 KB)
- **CCU easymode metadata extraction**: Channel-level easymode metadata for MASTER paramset profile enrichment
- **Hidden/device-level channels in configuration**: Device-level, internal, and invisible channels with MASTER paramset are now included in configurable channels
- **Read-only MASTER parameters**: Read-only configuration values are now displayed in device configuration
- **TLS certifi CA bundle**: TLS context now loads the `certifi` CA bundle when available, ensuring trusted certificates work out-of-the-box in Home Assistant
- **Skip optimistic updates for action data points**: Action data points (ACTION, ACTION_NUMBER, ACTION_SELECT, BUTTON) never receive CCU confirmations — the optimistic timer now skips them, preventing spurious rollback warnings
- **Skip duplicate optimistic sends**: Identical value sends are deduplicated to avoid unnecessary device writes
- **Additional parameter translations**: Extracted more parameter translations for improved config panel localization
- **Connection recovery**: Heartbeat timer now starts correctly after CCU reboots
- **HmIP channel type resolution**: `resolve_channel_type` for HmIP-specific translation lookups
- **New device**: HmIP-DLP (IP Door Lock Pro)
- **SysvarDpSwitch turn_on/turn_off**: Direct `turn_on()`/`turn_off()` methods for system variable switches
- **DataPointType enum**: Canonical data point type for downstream platform routing without isinstance checks
- **SubscriptionGroup**: Collective subscription lifecycle management via `event_bus.create_subscription_group()`
- **Device name in events**: Human-readable device names on `DeviceTriggerEvent`, `DeviceLifecycleEvent`, `OptimisticRollbackEvent`, and `DataPointStateChangedEvent`
- **State transition callbacks**: `central.on_state_transition()` for targeted `CentralState` transition handling
- **Extended query facade**: `get_data_points()` with `data_point_type` filter; `get_devices()` with interface/availability filters; `get_schedule_capable_devices()`
- **System variable creation**: `create_system_variable_bool()`, `_float()`, `_enum()` for creating system variables on the CCU
- **Link info read/write**: `get_link_info()` / `set_link_info()` for link metadata management
- **Service message suppression**: `suppress_service_message()` / `get_suppressed_service_messages()`
- **Quittable flag based on trigger datapoint**: Service message quittable check now uses `OPERATION_WRITE` on the trigger datapoint, matching CCU WebUI behavior
- **Acknowledge only writable messages**: `acknowledge_message` refuses non-quittable messages instead of silently acknowledging them
- **Removed auto-enable of alarm/service SysVars**: `${sysVarAlarmMessages}` and `${sysVarServiceMessages}` no longer force-enabled — superseded by dedicated hub sensors
- **Exposed message DPs on HubCoordinator**: `alarm_messages_dp` and `service_messages_dp` accessible via `HubCoordinator` for direct downstream access
- **Event tier enforcement**: Internal events separated from public API; `__all__` exports only public events
- **Unified subscription architecture**: DataPoint subscriptions routed through EventBus; `subscribe_to_data_point_updated()`/`subscribe_to_device_removed()` and `custom_id` removed; `register()`/`unregister()` for consumer lifecycle; `SubscriptionGroup.add()` replaced by `SubscriptionGroup.subscribe()`; typed `get_data_points_by_type()` query method

#### Bump aiohomematic-config to [2026.3.5](https://github.com/SukramJ/aiohomematic-config/compare/2026.3.2...2026.3.5)

- Easymode metadata enrichment: conditional visibility, option presets, subset groups, and metadata-based parameter ordering
- Cross-parameter validation in config sessions
- `MasterProfileStore` for MASTER paramset easymode profiles
- HmIP channel type resolution via `is_hmip` parameter
- `device_active_profile_index` field for active profile index from device
- `device_icon` field with icon filename from CCU device database
- Parameter `description` field with Markdown-formatted help text
- TCL profile parsing improvements (variable resolution, `subst` handling, `source` includes)
- New receiver profiles (door lock, universal light, RGBW DALI)
- `CrossValidationConstraint` model and `cross_validation` field on `FormSchema`
- Semantic parameter grouping from easymode `parameter_groups` metadata with locale-aware labels

#### Bump homematicip-local-frontend

- HA 2026.3.0+ / 2026.4.0+ compatibility
- Removed frontend message enrichment — display names and message codes now provided by aiohomematic
- OpenCCU Messages tab: Inbox (accept devices), Service Messages (acknowledge), Alarm Messages (acknowledge) with badge counts
- Acknowledge only quittable messages in service and alarm message cards

# Version [2.4.1](https://github.com/SukramJ/homematicip_local/compare/2.4.0...2.4.1) (2026-03-11)

## What's Changed

### Fixed

- **Install mode availability**: The install mode status WebSocket response now includes an `available` field indicating whether each interface (HmIP-RF, BidCos-RF) actually supports install mode. Previously, unavailable interfaces were indistinguishable from inactive ones.

### Config Panel

- Added auto-polling to Integration dashboard — refreshes every 5s during initialization, every 30s once stable
- Added auto-polling to OpenCCU dashboard — refreshes all data (system info, hub/service/alarm messages, signal quality, firmware, install mode) every 30s; loading spinner only shown on initial load

### Dependencies

#### Bump aiohomematic to [2026.3.8](https://github.com/SukramJ/aiohomematic/compare/2026.3.4...2026.3.8)

- **Fix connection recovery after startup failure**: Heartbeat timer now starts correctly after CCU reboots, preventing central from getting stuck in `FAILED` state
- **PayloadProtocol**: New protocol interface for `config_payload`, `info_payload`, and `state_payload` properties across devices, channels, data points, and central
- **Property `alt_name` support**: Property decorators accept optional `alt_name` for alternative payload keys (e.g. `address` → `serial_number`, `firmware` → `sw_version`)
- **Capabilities reclassified**: `capabilities` properties moved from `info_property` to `config_property` (immutable device features)

#### Bump aiohomematic-config to [2026.3.2](https://github.com/SukramJ/aiohomematic-config/compare/2026.2.10...2026.3.2)

- Add `device_active_profile_index` field to `ClimateScheduleData` for active profile index from device
- Python 3.14 minimum, dropped Python 3.13 support

# Version [2.4.0](https://github.com/SukramJ/homematicip_local/compare/2.3.2...2.4.0) (2026-03-05)

## What's Changed

### Added

- **DpActionNumber support**: New `AioHomematicActionNumber` entity for write-only FLOAT/INTEGER data points (`BaseDpActionNumber`). Values are stored locally (not sent to device) and persisted in a dedicated storage file (`homematicip_local.action_number.{entry_id}`), analogous to the existing `DpActionSelect` pattern. Entities are filtered by `DP_ACTION_NUMBER_WHITELIST` (currently empty; `DURATION_VALUE` prepared but commented out).
- **CombinedDataPoint support**: New `AioHomematicCombinedNumber` entity for `CombinedDataPointProtocol` data points (e.g. `CombinedDpTimerAction`). These combined data points merge multiple underlying parameters (e.g. timer value + unit) into a single writable number entity with automatic unit conversion. Exposed as `EntityCategory.CONFIG` number entities with min/max/unit from the combined data point. Sensor platform filters out `CombinedDataPointProtocol` instances to prevent duplicate read-only entities.
- 15 new WebSocket commands for the Integration and OpenCCU panel tabs (`homematicip_local/integration/*` and `homematicip_local/ccu/*`)

### Fixed

- **Fix sensor entities not created for non-DpSensor data points**: The `isinstance(data_point, DpSensor)` filter added to exclude `CombinedDataPointProtocol` instances also excluded `CalculatedDataPoint` instances (e.g. `OperatingVoltageLevel` / Betriebsspannungspegel) and forced-sensor `GenericDataPoint` instances (e.g. `LEVEL` / Ventilöffnungsgrad on HmIP-eTRV). The filter now excludes only `CombinedDataPointProtocol` instead of requiring specific subclasses.
- **Fix CombinedDataPoint number entities not created on dynamic discovery**: The `async_add_combined_number` dispatcher in the number platform listened on `DataPointCategory.SENSOR` but `CombinedDpTimerAction` (e.g. siren duration on HmIP-ASIR-2) has `_category = DataPointCategory.ACTION_NUMBER`. Changed the signal to `ACTION_NUMBER` so combined number entities are correctly created during dynamic device discovery.

### Changed

- **Python 3.14 minimum**: Dropped Python 3.13 support. CI, mypy, pylint, ruff, Dockerfile, and all documentation updated to target Python 3.14+.
- **Minimum Home Assistant version**: Raised from 2025.10.0 to 2026.3.0.

### Config Panel

- **Integration dashboard tab**: New "Integration" tab in the config panel providing a consolidated view of the integration's operational state:
  - System health with central state and health score
  - Device statistics with per-interface breakdown (total, unreachable, firmware-updatable)
  - Command throttle monitor per interface (interval, queue size, throttled/burst counts)
  - Incident log with severity-colored entries and clear action
  - Cache management (clear all cached data)

- **OpenCCU dashboard tab**: New "OpenCCU" tab for CCU-specific information and management:
  - System information (name, model, version, serial, hostname, CCU type, available interfaces)
  - Hub messages (service and alarm message counts)
  - Install mode control for HmIP-RF and BidCos-RF with activation buttons and remaining time display
  - Signal quality table with sortable columns (RSSI, signal strength, battery, reachability per device)
  - Firmware overview table with sortable columns and update-available highlighting
  - CCU backup creation with download to backup directory

- **Tab navigation**: The config panel now features a tab bar (Devices / Integration / OpenCCU) for switching between views. Tab state is persisted in the URL hash.

- **Link config editor fix**: Fixed false dirty state when opening the link config editor without making changes.
- **HA 2026.3 compatibility**: Fixed `ha-select` compatibility with Home Assistant 2026.3.0+.

### Dependencies

#### Bump aiohomematic to [2026.3.4](https://github.com/SukramJ/aiohomematic/compare/2026.3.0...2026.3.4)

- **DpActionNumber data points**: New `DpActionFloat` and `DpActionInteger` for write-only FLOAT/INTEGER parameters with MIN/MAX validation
- **DpActionBoolean and DpActionString data points**: Complete the DpAction hierarchy for write-only BOOL/STRING parameters. `DpAction` now only handles `TYPE=ACTION` parameters
- **Type-correct custom data point fields**: Replaced `DpAction` with specific types (`DpActionFloat`, `DpActionInteger`, `DpActionBoolean`, `DpActionString`) in custom data points based on pydevccu paramset TYPE
- **CombinedDataPoint for timer value+unit pairs**: New `CombinedDpTimerAction` combines timer value + unit into a single writable entity with automatic unit conversion (seconds to S/M/H). Replaces `TimerField`/`TimerAccessor` pattern. Siren duration exposed as visible number entity with automatic unit conversion
- **CombinedDpHsColor for hue+saturation pairs**: Encapsulates HUE + SATURATION into a single `tuple[float, float]` value with automatic saturation scaling. Simplifies RGBW and DALI light custom data points
- **Unified field visibility in profile configs**: Merged 6 field dictionaries into 3 with per-entry visibility via `hidden()`/`visible()` helpers
- **Siren duration fix**: `turn_on()` now properly converts duration with unit conversion and uses stored default when no explicit duration is provided
- **Duration translations**: Added German and English translations for `DURATION_VALUE`
- **Fix scheduler busy-loop at 100% CPU during connection issues**: Skipped jobs now advance their schedule to prevent busy-loop and burst on recovery
- **Security hardening**: ReGa script injection prevention, device address validation, password field protection, authorization header sanitization, ReGa script path traversal prevention, firmware URL scheme validation, restrictive temp file/directory permissions, RPC background task limit (1000 max), cryptographic RNG for address anonymization
- **Fix health tracker central state sync**: `sync_central_state()` synchronizes cached central state after `_evaluate_central_state()` completes
- **Performance**: Pre-sorted EventBus handlers, parallel device finalization/client refresh/interface operations, `weakref.finalize` for subscription cleanup, `slots=True` for dataclasses, optimized multi-channel group check

#### Bump aiohomematic-config to [2026.3.2](https://github.com/SukramJ/aiohomematic-config/compare/2026.2.10...2026.3.2)

- Add `device_active_profile_index` field to `ClimateScheduleData` for active profile index from device
- Add `device_icon` field to `FormSchema` with icon filename from CCU device database
- Add `description` field to `FormParameter` with Markdown-formatted parameter help text
- **Python 3.14 minimum**: Dropped Python 3.13 support

---

# Version [2.3.2](https://github.com/SukramJ/homematicip_local/compare/2.3.1...2.3.2) (2026-03-01)

## What's Changed

### Changed

- **Backup agent stores only CCU backups**: The backup agent no longer inherits from `LocalBackupAgent` and no longer writes the HA backup tar file. It now extends `BackupAgent` directly and only stores the CCU backup (`.sbk`) and metadata (`.json`) in the backup directory. The HA backup tar is managed by HA core. CCU backup failures (unavailable CCU, no data, connection error) now raise `BackupAgentError` instead of being silently logged, allowing HA to properly report per-agent backup failures. Orphaned metadata from previous versions is automatically cleaned up on load.

### Config Panel

- **Device icons**: Device list, device detail, and channel config views now display device images from the CCU via proxy endpoint. Graceful fallback when icon is unavailable.
- **Parameter help texts**: Markdown-formatted help texts for ~165 MASTER paramset parameters (e.g. `BUTTON_LOCK`, `TEMPERATURE_OFFSET`, `VALVE_OFFSET`) are now displayed below each parameter in the configuration panel
- **Device schedule fix**: Schedule entries without target channels are now correctly displayed (dimmed). Removed frontend `target_channels` validation (CCU allows `TARGET_CHANNELS = 0`). Auto-selects first device in schedule view when no matching device is found.
- **Bug fixes**: Fixed `ha-slider` event handling (fires `value-changed` instead of native `change`), fixed `ha-select` event leaking corrupting pending changes state, fixed `ha-select` dropdown closing the device schedule editor dialog, fixed editor dialog closing on save when validation errors exist

### Dependencies

#### Bump aiohomematic to [2026.3.0](https://github.com/SukramJ/aiohomematic/compare/2026.2.27...2026.3.0)

- **Device icons**: Extract device model to icon filename mapping from CCU's `DEVDB.tcl` (525 entries). New `get_device_icon()` in `ccu_translations` and `icon` property on `Device` expose the filename relative to `img/devices/250/` for downstream consumers.
- **Profile-specific parameter translations**: Extract ~550 additional parameter translations from CCU easymode profile localization files (e.g. `COLOR_TEMP`, `MAX_COLOR_TEMP`, `SWITCH_DIRECTION`), merged with lowest priority into the existing parameter translation output.
- **Parameter help texts**: Extract and expose Markdown-formatted help texts for ~165 MASTER paramset parameters from the CCU WebUI. The HTML content is converted to Markdown, template variables are resolved, and the result is available via `get_parameter_help()` and as a `description` property on `BaseParameterDataPoint`.
- **Fix device link encoding**: Fix garbled UTF-8 characters in device link names and descriptions retrieved via XML-RPC. The CCU stores user-defined strings as UTF-8 but the XML-RPC transport decodes them as ISO-8859-1, causing multi-byte characters to be misinterpreted (e.g. `ü` → `Ã¼`). New `fix_xml_rpc_encoding` utility reverses the double-encoding.
- **Fix spurious optimistic update rollbacks**: `apply_optimistic_value()` was called before the `is_state_change()` check in the direct send path. When sending a value identical to the current state (e.g. turning off an already-off switch), the optimistic timer started but no RPC was sent to the CCU, making confirmation impossible. After 30 seconds the timer fired a spurious rollback with warning logs and `OptimisticRollbackEvent`. The state change check now runs first so optimistic tracking is only activated when an RPC call actually occurs.
- **Fix install mode**: Use interface-specific client instead of primary client for install mode buttons. Previously, activating install mode for one interface (e.g. HmIP-RF) could incorrectly target another interface (e.g. BidCos-RF).
- **Fix non-climate schedules with empty target channels**: Schedules without explicit target channels were incorrectly filtered as inactive because `is_schedule_active()` required both weekdays and target channels. The CCU handles default channel assignment when no explicit channels are configured, so the activity check now only requires at least one weekday.

#### Bump aiohomematic-config to [2026.3.1](https://github.com/SukramJ/aiohomematic-config/compare/2026.2.10...2026.3.1)

- Add `device_active_profile_index` field to `ClimateScheduleData` for active profile index from device
- Add `device_icon` field to `FormSchema` with icon filename from CCU device database
- Add `description` field to `FormParameter` with Markdown-formatted parameter help text
- Use `get_parameter_help()` from aiohomematic to populate help texts (locale-aware, with LINK prefix stripping)
- Fix URL-encoded umlauts in profile names and descriptions (`%D6` → `Ö`) by adding `urllib.parse.unquote()` before `html.unescape()`
- Fix profile matching to prefer most specific profile when multiple profiles match (highest fixed-constraint count wins)
- Resolve TCL `$variable` references in easymode profile constraints (e.g. `$NOP`, `$RAMP_ON`)
- Handle TCL `[subst {...}]` wrappers in easymode profile constraint parsing
- Follow TCL `source` includes to resolve profiles defined in shared files (e.g. `profiles.tcl`, `profilesTunableWhite.tcl`)
- Add profiles for new receiver types: `AUTO_RELOCK_TRANSCEIVER`, `DOOR_LOCK_TRANSCEIVER`, `UNIVERSAL_LIGHT_RECEIVER_LSC`, `UNIVERSAL_LIGHT_RECEIVER_RGB(W)`, `UNIVERSAL_LIGHT_RECEIVER_RGBW_DALI`, `UNIVERSAL_LIGHT_RECEIVER_TW`

---

# Version [2.3.1](https://github.com/SukramJ/homematicip_local/compare/2.3.0...2.3.1) (2026-02-26)

## What's Changed

### Fixed

- **Fix panel registration failure on integration reload**: Separated static HTTP route registration from frontend panel registration. The static route (which cannot be removed by aiohttp) is now tracked independently and only registered once per HA process lifetime. Previously, reloading the integration or an automatic retry after a transient error would attempt to re-register the static route, causing a `RuntimeError` that cascaded into all platform setups failing with "has already been setup".

- **Fix entity translations for LEVEL sensors**: LEVEL sensors on thermostats and other devices (e.g. valve opening, cover level, light level, tilt level) now show translated names and correct icons again. The translation_key from entity descriptions was incorrectly filtered by a whitelist, causing both the local translation and the icon mapping from `icons.json` to be lost. Added translations for `pipe_level`, `cover_level`, `light_level`, and `cover_tilt` in all locales.

### Config Panel

- Migrated all UI elements to Home Assistant built-in components
- MASTER paramset: Unit/Value parameter pairs (e.g. `*_UNIT` + `*_VALUE`) are now displayed as a single preset dropdown instead of two separate rows, matching the CCU behavior
- 13 standard Homematic time presets (100ms–15 minutes) with localized labels (EN/DE)
- "Custom value" / "Wert eingeben" option reveals the original unit and value fields for manual entry
- Automatic detection: if current values match a preset, the preset is shown; otherwise custom mode with detail fields

### Dependencies

#### Bump aiohomematic to [2026.2.27](https://github.com/SukramJ/aiohomematic/compare/2026.2.25...2026.2.27)

- **Fix channel-specific translation lookup**: The `channel_type` parameter was not lowercased before lookup, causing channel-specific translations (e.g. `maintenance|low_bat` → "Batterie") to never match when the channel type came from device descriptions in uppercase. Both lookup functions now normalize `channel_type` to lowercase.
- **Option value translations from options.tcl**: ~65 new entries per locale for MASTER paramset dropdown parameters (`POWERUP_JUMPTARGET`, `LOGIC_COMBINATION`, `FLOOR_HEATING_MODE`, `HEATING_MODE_SELECTION`, `MIOB_DIN_CONFIG`, `DALI_EFFECTS`, etc.). Parameters that previously showed raw VALUE_LIST values now display human-readable labels in the UI.

---

# Version [2.3.0](https://github.com/SukramJ/homematicip_local/compare/2.2.4...2.3.0) (2026-02-23)

## What's Changed

### Breaking Changes (Schedule Services)

- All schedule services have been migrated from **entity-based** to **device-based**. Services now use `device_id` or `device_address` instead of targeting entities. **Existing automations using old service names must be updated.**

- **Renamed services:**
  - `get_schedule_simple_profile` → `get_schedule_profile`
  - `get_schedule_simple_schedule` → `get_schedule`
  - `get_schedule_simple_weekday` → `get_schedule_weekday`
  - `set_simple_schedule` → `set_schedule`
  - `set_simple_schedule_profile` → `set_schedule_profile`
  - `set_simple_schedule_weekday` → `set_schedule_weekday`

- **Removed services:**
  - `set_schedule_active_profile` / `set_current_schedule_profile` — use `set_current_schedule_profile` via the configuration panel or update the profile through the `set_schedule_profile` service instead

- **Renamed entity attributes (Climate & Week Profile Sensor):**
  - `active_profile` → `current_schedule_profile`

### Added

- **Week profile sensor entity**: New `AioHomematicWeekProfileSensor` entity for every device with schedule support. Exposes schedule metadata (schedule type, max entries, schedule data) as state attributes. Climate devices additionally expose temperature bounds and available profiles (P1-P6).

- **Device-based schedule services**: All schedule services now use `device_id` or `device_address` for device identification. This replaces the previous domain-specific (entity-based) approach with a unified API that works for all device types.

- **Command throttle interval config option**: Added `command_throttle_interval` to Advanced Options (config flow and options flow). Controls the minimum delay between consecutive device commands per RF interface to ensure smooth operation and prevent packet loss during bulk operations. Default: `0.1`s. Set to `0.0` to disable.

- **Optimistic rollback events**: Added `homematicip_local.optimistic_rollback` event and logbook integration. When an optimistic state update is rolled back (e.g. CCU rejects the value or times out), the event is fired and displayed in the logbook with the parameter name and rollback reason.

- **Command throttle diagnostics**: Added per-interface command throttle statistics to the diagnostics export, including interval, queue size, throttled/critical/burst counts, and burst detection thresholds.

- **Improved error handling**: Extended `handle_homematic_errors` decorator to catch `ValueError` and `pydantic.ValidationError`, converting them to user-friendly `HomeAssistantError` messages

- **`device_active_profile_index` attribute**: Climate and week profile sensor entities now expose the 1-based profile index as reported by the device hardware. This value is automatically synced from the device's `ACTIVE_PROFILE` (IP) or `WEEK_PROGRAM_POINTER` (RF) parameter.

- **`current_schedule_profile` attribute**: Climate and week profile sensor entities expose the currently selected schedule profile (P1–P6). Automatically synchronized with the device's active profile parameter.

- **Climate entity subscribes to week profile changes**: The climate entity now subscribes to `device.week_profile_data_point` updates, ensuring schedule attributes (`schedule_data`, `current_schedule_profile`, `available_profiles`) update in real-time when the schedule changes on the device.

- **Device configuration panel**: New sidebar panel for editing device parameters, managing direct links, and configuring schedules — directly from the Home Assistant UI. Enable via Advanced Options. See [documentation](https://sukramj.github.io/aiohomematic/user/features/config_panel/).

- **Panel translations**: The configuration panel UI (sidebar title, section headers, parameter labels, enum values, toggle labels) is fully translated based on the Home Assistant language setting (German and English). Parameter filtering matches the CCU WebUI easymode behavior — only parameters with known translations are shown.

- **Database recording optimization**: Added `_unrecorded_attributes` to light, cover, switch, valve, siren, and week profile sensor entities. Static metadata attributes (e.g. available colors, channel positions, available soundfiles, schedule metadata) are now excluded from the HA recorder database, reducing storage usage.

- **Paramset inconsistency repair issue**: Displays a Home Assistant repair issue when aiohomematic detects missing parameters on HmIP/HmIPW devices after firmware updates. Informs the user about affected devices and recommends a factory reset via the CCU WebUI.

- **WRC6 Blueprint**: Community blueprint for 6-button wall remote (HmIP-WRC6) now supports multiple devices and includes optional direct connection collision checks. **Not backwards compatible** — existing automations using this blueprint need to be reconfigured.

- **Translated interface display names**: Interface names in config flow error messages and detection info now use translated, user-friendly names (e.g. "Homematic IP" instead of "HmIP-RF") with full German translation support. Warning messages for undetected interfaces are also translated.

- **Configuration panel: Session management**: New server-side `ConfigSession` with undo/redo support. Changes are tracked in-memory before writing to the device, enabling safe editing with validation feedback.

- **Configuration panel: Export/Import**: Export channel paramset configurations as JSON and import them to same-model devices. Enables configuration backup and transfer between identical devices.

- **Configuration panel: Copy paramset**: Copy configuration between same-model device channels. Automatically filters to writable parameters present in the target.

- **Configuration panel: Change history**: Persistent log of all paramset writes (manual, import, copy) with old/new value diffs. Stored via HA `Store` with a 500-entry FIFO limit. Retrievable and clearable per config entry.

- **Configuration panel: Enhanced device list**: Device list now includes cached maintenance data (UNREACH, LOW_BAT, RSSI_DEVICE, RSSI_PEER, DUTYCYCLE, CONFIG_PENDING) from channel 0, enabling the frontend to display device health without additional roundtrips.

- **Configuration panel: Direct links (Direktverknüpfungen)**: Browse, create, configure, and remove direct device-to-device links (peerings) for BidCos-RF, BidCos-Wired, and HmIP-RF interfaces. Includes link overview grouped by channel, link paramset editing via form schema, and a 3-step wizard for creating new links with compatible channel filtering.

- **Configuration panel: Link profiles & UX**: Profile-based link configuration with easymode profiles from CCU (Expert, Dimmer ein/aus, Treppenlicht, etc.). Combined time selector for TIME_BASE/TIME_FACTOR pairs, SHORT/LONG keypress tabs, percent slider for LEVEL parameters with "Last value" support, and hidden jump targets/condition transitions in profile mode. Fully translated panel UI (EN/DE).

- **Configuration panel: Deep-linking**: Navigate directly to a device, channel config, or link view via URL hash parameters. Supports browser back/forward navigation.

- **CCU backup agent**: New `LocalBackupAgent` that appears in the HA backup UI as a backup storage location. HA backups can be stored in the CCU backup directory and managed (list, download, delete) via the standard backup UI. One agent is registered per CCU config entry (multi-CCU capable). Existing CCU `.sbk` pre/post-backup hooks are unchanged.

- **Configuration panel: Schedule management**: Schedule editing integrated into the configuration panel via WebSocket API. List devices with schedule support, read/write climate schedules per profile and weekday, set the active climate profile, and read/write generic device schedules — all from the panel UI.

- **Configuration panel: Reload device config**: New WebSocket command to reload a device's configuration from the CCU without restarting the integration.

- **Device configuration URL deep-link**: When the configuration panel is enabled, each device's `DeviceInfo` now includes a `configuration_url` that links directly to the device detail view in the configuration panel. Clicking the link on a device's page navigates to the panel with the correct entry, device address, and interface preselected.

- **`config_entry_id` attribute**: Climate and week profile sensor entities with schedule support now expose a `config_entry_id` state attribute, enabling automations and frontend cards to identify the associated config entry.

### Changed

- **Schedule WebSocket commands opened to non-admin users**: Removed `@require_admin` restriction from `get_climate_schedule`, `set_climate_active_profile`, and `get_device_schedule` WebSocket commands, allowing non-admin users to read and interact with schedule data.

- **Admin-only restriction for writing Services**: The services `put_link_paramset`, `set_schedule`, `set_schedule_profile`, `copy_schedule`, and `copy_schedule_profile` now require admin privileges (`async_register_admin_service`). Read-only schedule services remain accessible to all users.

- **Entity names from backend translations**: Removed redundant local entity translations (binary_sensor, button, lock, number, select, sensor, switch, valve) from strings.json and translation files. Entity names are now provided by the backend CCU translation system via `translated_name`. Only climate (preset modes) and event (keypress types) translations remain local.

- **Config entry migration v16**: Existing config entries are migrated to include `command_throttle_interval` with the default value

- **Configuration panel: Business logic extraction**: Moved reusable logic from `websocket_api.py` to aiohomematic / aiohomematic-config:
  - Device listing now delegates to `ConfigurationCoordinator.get_configurable_devices()` (was ~70 LOC inline)
  - Paramset copy now delegates to `ConfigurationCoordinator.copy_paramset()` (was ~80 LOC inline)
  - Change history tracking now uses `ConfigChangeLog` from aiohomematic-config (was custom inline implementation)
  - Removed `_LinkLabelResolver` workaround in favor of `FormSchemaGenerator(require_translation=False)`

### Bug Fixes

- **Sub-device entity name deduplication**: Fixed entity_id duplication when sub-devices are enabled. When the HA device name (channel group name) was a prefix of the backend's `translated_name`, the device name appeared twice in the entity_id (e.g. `binary_sensor.atbm_terrasse_atbm_terrasse_schaltausgang`). The device name prefix is now stripped from the entity name, producing the correct entity_id (e.g. `binary_sensor.atbm_terrasse_schaltausgang`).

- **Multi-instance WebSocket registration**: Fixed duplicate WebSocket command registration error when multiple integration instances (config entries) are set up. Commands are now registered only once.

- **Link profile matching on read failure**: Fixed active profile detection when link paramset read fails. Now correctly falls back to Expert (profile 0) instead of vacuously matching the first profile.

- **Configuration panel: Fix delete direct connection**: Fixed deletion of direct device-to-device links (Direktverknüpfungen) not working correctly in the configuration panel frontend.

- **Multi-instance panel registration**: Fixed the configuration panel disappearing when multiple CCU instances are configured and not all have the panel enabled. The panel is now kept registered as long as at least one config entry has it enabled, instead of letting the last-loaded entry's setting override all others.

## Bump aiohomematic to [2026.2.25](https://github.com/SukramJ/aiohomematic/compare/2026.2.0...2026.2.25)

### Documentation (aiohomematic)

- **Comprehensive documentation audit** (2026.2.21): ~20 documentation files updated with corrected class names, API signatures, coordinator access patterns, event types, constant values, exception hierarchy, and sequence diagrams.

### New Features (aiohomematic, continued)

- **Schedule domain property for week profiles** (2026.2.22): `schedule_domain` property on `WeekProfileDataPoint` and `WeekProfileDataPointProtocol` that returns the `DataPointCategory` (switch, light, cover, valve) for non-climate schedule devices. Enables consumers like the Climate Schedule Card to distinguish schedule types and adapt their UI accordingly.

### Architecture (aiohomematic)

- **Architecture cleanup** (2026.2.8): Query methods extracted from `CentralUnit` to `DeviceQueryFacade` (`central.query_facade`). Support module split into submodules (`support.address`, `support.file_ops`, `support.mixins`). Protocol hierarchy reorganized with new `interfaces.central` and `interfaces.model` modules. Optimistic update logic extracted to `model.optimistic`.

### New Features (aiohomematic)

- **CCU translation extraction** (2026.2.10): New script (`script/extract_ccu_translations.py`) that extracts human-readable translations from the OpenCCU/RaspberryMatic WebUI for channel types, device models, parameter names, and parameter enum values. Supports local OCCU checkout and remote CCU fetch. Resolves two-level stringtable indirection, URL-decodes Latin-1 characters, and strips HTML from values. 2500+ translation entries across 8 JSON files (4 categories x 2 locales).

- **CCU translations loader module** (2026.2.10): New module (`aiohomematic/ccu_translations.py`) providing typed lookup functions for CCU-sourced translations: `get_channel_type_translation()`, `get_device_model_description()`, `get_parameter_translation()`, `get_parameter_value_translation()`. All lookups are thread-safe and asyncio event loop safe (lazy initialization, then pure dict reads with zero I/O).

- **Translated data point names** (2026.2.11): Data points now expose translated `name_label` and `name_label_with_index` properties via the CCU translation system. Provides human-readable parameter names (e.g. "Temperature Offset" instead of "TEMPERATURE_OFFSET") for UI rendering.

- **Value-only translation fallback** (2026.2.13): `get_parameter_value_translation` now has a three-tier lookup: channel-specific → parameter-specific → value-only. The new value-only fallback builds an index of standalone enum values mapped to their shortest (most generic) translation, so shared values like weekday names resolve even for unknown parameters.

- **Configurable channel filtering** (2026.2.13): `get_configurable_channels` now applies CCU-compatible filtering rules: channels must have the VISIBLE flag set and must not have the INTERNAL flag. WEEK_PROGRAM channels are excluded as they are handled by schedule cards.

- **On-demand LINK paramset description fetching** (2026.2.19): `get_paramset_description_on_demand` on `InterfaceClient` and `get_link_paramset_description` on `ConfigurationCoordinator` for fetching LINK paramset descriptions directly from the backend when needed. LINK paramsets are not cached during device discovery, so this API enables direct link configuration without requiring a full device reload.

- **LinkCoordinator for device direct link management** (2026.2.20): `LinkCoordinator` as a high-level facade for listing, creating, and removing direct links between device channels. Includes `DeviceLink` and `LinkableChannel` dataclasses for enriched link data with translated channel type labels, device metadata, and link direction. Provides linkable channel discovery with role-based filtering. Exposed via `LinkFacadeProtocol` on `CentralUnit.link`.

- **Dimmer last-level tracking** (2026.2.20): `last_level` property and `set_last_level` method on `CustomDpDimmer` for tracking the last non-default brightness level, enabling restore-to-previous-brightness workflows.

- **Configurable device listing** (2026.2.20): `get_configurable_devices` on `ConfigurationCoordinator` returning `ConfigurableDevice` dataclasses with resolved channel type labels, effective paramset keys (MASTER excluded when no writable visible parameters exist), and `MaintenanceData` from channel 0. Exposed via `ConfigurationFacadeProtocol`.

- **Paramset copy operation** (2026.2.20): `copy_paramset` on `ConfigurationCoordinator` for copying writable paramset values from a source channel to a target channel. Filters non-writable and missing parameters, returns `CopyParamsetResult` with copy/skip counts and old target values for change tracking.

- **`parameter_tools` module** (2026.2.9): New standalone module providing pure-function utilities for working with parameter descriptions, independent of DataPoint instances. Includes `ParameterHelper` (flag/operation checks, enum resolution, step size calculation), `ParameterValidator` (value validation, type coercion), and `ParamsetDiff` (type-aware paramset comparison).

- **`ConfigurationCoordinator`** (2026.2.9): New high-level facade for device configuration operations, exposed as `central.configuration`. Provides `get_paramset_description()`, `get_all_paramset_descriptions()`, `get_paramset()`, `put_paramset()`, `get_configurable_channels()`, and `get_parameter_data()`.

- **Paramset consistency checker** (2026.2.7): Automatically detects missing parameters on HmIP/HmIPW devices after firmware updates. The HmIPServer (crRFD) on the CCU sometimes fails to refresh its stored parameter data, creating a mismatch between `getParamsetDescription()` (schema) and `getParamset()` (actual values). Reports inconsistencies via `IntegrationIssue` events, log warnings, and diagnostics data.

- **WeekProfileDataPoint** (2026.2.6): Device-level data points that serve as the central interface for schedule data — both for climate and non-climate devices. One data point per device exposes schedule metadata, target channel mappings, and delegates read/write operations to the underlying WeekProfile. Schedule access has been removed from custom data points (`BaseCustomDpClimate`, `CustomDataPoint`) and is now exclusively available via `device.week_profile_data_point`.

- **Automatic profile sync from device** (2026.2.6): `ClimateWeekProfileDataPoint` now binds the device's `ACTIVE_PROFILE` (IP) or `WEEK_PROGRAM_POINTER` (RF) generic data point. `current_schedule_profile` updates automatically when the thermostat switches profiles.

- **Climate CDP notification on schedule change** (2026.2.6): When schedule data changes (e.g., after `CONFIG_PENDING=False` reload), the linked Climate CDP is automatically notified via an internal subscription, causing the HA Climate Entity to update.

- **`device_active_profile_index` property** (2026.2.6): Returns the 1-based profile index from the device parameter (`int | None`). RF values are normalised from 0-based to 1-based.

- **Optimistic updates** (2026.2.4): Data points immediately update their state when `send_value()` is called, then rollback if the CCU rejects the value or times out. Fires `OptimisticRollbackEvent` on rollback. Configurable via `TimeoutConfig.optimistic_update_timeout` (default: 30s).

- **Command throttle** (2026.2.4): Configurable per-interface rate limiting for outgoing device commands. Enforces a minimum delay between consecutive commands on the same RF interface to ensure smooth operation and prevent packet loss. Configurable via `TimeoutConfig.command_throttle_interval`.

- **Command priority queue** (2026.2.4): Three-tier priority system for command throttling:
  - **CRITICAL** (priority 0): Security commands (locks, sirens) bypass throttle entirely
  - **HIGH** (priority 1): Interactive user commands use normal throttle
  - **LOW** (priority 2): Burst detection automatically downgrades commands when thresholds are exceeded

- **CRITICAL queue purge** (2026.2.4): When a CRITICAL command arrives (e.g. cover STOP), all pending queued commands for the same channel group are purged from the throttle queue, preventing queued movement commands from overriding STOP.

- **Domain-specific schedule validation** (2026.2.3): Added validation for schedule data based on device category (SWITCH, LIGHT, COVER, VALVE). The validation enforces that only appropriate fields are used for each device type. Backward-compatible: validation is only applied when domain context is provided.

- **Schedule Pydantic Models** (2026.2.1): New validated Pydantic models for automatic validation with clear error messages:

  **Climate devices:**
  - `ClimateSchedulePeriod`: Validates temperature periods with starttime, endtime, temperature
  - `ClimateWeekdaySchedule`: Validates daily schedules with base_temperature and periods
  - `ClimateProfileSchedule`: Validates weekly schedules (MONDAY-SUNDAY)
  - `ClimateSchedule`: Validates complete profiles (P1-P6)

  **Non-climate devices:**
  - `SimpleScheduleEntry`: Validated schedule entry with weekdays, time, condition, target_channels, level, duration, ramp_time
  - `SimpleSchedule`: Container for multiple schedule entries keyed by group number (1-24)

### Improved (aiohomematic)

- **CCU translation loading via pkgutil** (2026.2.12): Replaced `Path.read_text()` with `pkgutil.get_data()` for loading CCU translation files. Avoids blocking file I/O detection in Home Assistant's event loop. Translations are eagerly initialized at import time.

- **Robust JSON parsing with stdlib fallback** (2026.2.11): When `orjson` fails to parse JSON from CCU Rega scripts (e.g., due to non-standard literals like `NaN` or `Infinity`), the parser now falls through to Python's stdlib `json` module. Extended control character sanitization to include DEL (U+007F). Diagnostic logging for JSON parse errors now includes exact codepoint, position, and surrounding context.

- **Extraction script improvements** (2026.2.13): Added PNAME.txt and easymode TCL file parsing, improved HTML entity decoding. Parameters: 841 → 1029 (+188), parameter values: 1256 → 1326 (+70). Removed 17 redundant custom translation entries now covered by improved extraction.

- **Empty parameter translation suppresses parameter name** (2026.2.14): When a CCU parameter translation resolves to an empty string (`""`), the parameter name is now omitted from `translated_name` and `translated_full_name`. This allows translations to explicitly suppress redundant parameter names when the channel name already conveys the meaning. `None` (no translation found) still falls back to the original untranslated name.

- **Custom data point postfix translation** (2026.2.16): Custom data points now translate their `data_point_name_postfix` via the CCU translation system, providing localized names (e.g. translating parameter postfixes like `BUTTON_LOCK`) consistent with generic data points.

### Bug Fixes (aiohomematic)

- **Fix HmIP-HDM2 cover showing "unknown" state** (2026.2.25): Devices without tilt support (e.g. HmIP-HDM2 in plissee mode) sent `LEVEL_2_STATUS = INVALID` from the CCU, which poisoned the cover entity's `is_status_valid` check and caused Home Assistant to show "unknown" state despite position control working. `CustomDpBlind` now excludes `LEVEL_2` from relevant data points when its value is `None`.
- **Use JSON-RPC for HmIP-RF install mode** (2026.2.25): The Java-based HMIPServer does not support the XML-RPC `setInstallMode` method — it throws `IllegalArgumentException: argument type mismatch` and returns an empty response. Install mode for HmIP-RF now uses the dedicated JSON-RPC methods `Interface.setInstallModeHMIP` and `Interface.getInstallMode` instead. BidCos-RF continues to use XML-RPC `setInstallMode` as before.
- **Fix BidCos-RF install mode with device address filter** (2026.2.25): The XML-RPC call for signature (3) `setInstallMode(Boolean, Integer, String)` incorrectly sent 4 arguments `(on, time, mode, address)` instead of the documented 3 arguments `(on, time, address)`.
- **Improve empty XML-RPC response handling** (2026.2.25): Empty HTTP responses from the CCU (e.g. caused by server-side exceptions) are now caught as `ExpatError` with a specific warning log and raised as `ClientException`, instead of falling through to the generic exception handler.
- **Handle empty XML-RPC responses for void CCU methods** (2026.2.24): The CCU's `setInstallMode` method returns an empty HTTP response body instead of a proper XML-RPC response. The XML parser failed with `ExpatError: no element found`. The proxy now detects empty responses and treats them as successful void returns, preventing `ClientException` when activating install mode.
- **Clear deleted schedule entries on CCU** (2026.2.23): `DefaultWeekProfile.convert_dict_to_raw_schedule` now explicitly zeroes out `WEEKDAY` and `TARGET_CHANNELS` for unused groups (1-24) that are not in the schedule. This ensures that deleted schedule entries are properly deactivated on the CCU, since `put_paramset` only updates keys that are sent.
- **LINK paramset parameter translations** (2026.2.18): `get_parameter_translation()` and `get_parameter_value_translation()` now strip `SHORT_`/`LONG_` prefixes and retry the base name, resolving translations for link parameters (e.g. `SHORT_ON_LEVEL` → "Einschalthelligkeit (kurz)"). Added 138 parameter translations and 1158 value translations for link-specific parameters.
- **Fix delayed device creation failing on multi-interface devices** (2026.2.18): When a new HmIP device was paired, the CCU sends `newDevices` on multiple interfaces (e.g. HmIP-RF and VirtualDevices) with the same device address. `_delayed_device_descriptions` was keyed by device address only, causing the first call to consume descriptions from all interfaces. Fixed by making `_delayed_device_descriptions` interface-aware.
- **Preserve channel postfix when translation suppresses parameter name** (2026.2.17): When a parameter translation resolves to an empty string for a multi-channel data point, the channel disambiguation postfix (e.g. `ch13`) was lost because the truthiness check treated `""` the same as `None`. Changed to an identity check (`is not None`) so that an empty translation correctly yields `translated_name="ch13"` instead of removing the name entirely.
- **i18n: Allow multiple CentralUnit instances** (2026.2.15): `set_locale()` is now idempotent — calling it again with the same locale is a no-op. When called with a different locale, it logs a message and keeps the original. Previously, creating a second `CentralUnit` raised `RuntimeError` because `set_locale()` was strictly one-shot.
- **XML-RPC server race condition on multi-hub startup** (2026.2.7): Fixed a race condition in `AsyncXmlRpcServer.start()` that caused "address in use" errors when multiple central units started concurrently. The singleton server is now protected by an `asyncio.Lock`.
- **Optimistic rollback now clears unconfirmed value** (2026.2.7): `_rollback_optimistic_value()` now properly clears the unconfirmed value before restoring the previous confirmed value, preventing the unconfirmed value from undermining the rollback.
- **CallbackDataPoint ownership reset on unsubscribe** (2026.2.6): When the owning `custom_id` fully unsubscribes from a data point, `_custom_id` is now reset to `None`. This allows re-registration with a different `custom_id` (e.g. after an entity_id rename in Home Assistant), preventing `AioHomematicException` on resubscription.
- **i18n format specs** (2026.2.5): Fixed `i18n.tr()` silently dropping format specifiers like `{interval:.3f}`. Placeholders with format specs now render correctly in log messages.
- **JSON control character sanitization** (2026.2.2): Fixed `JSONDecodeError` when ReGa scripts return JSON containing unescaped control characters in device names or values. The sanitization is now selective - it only escapes control characters within JSON string values, preserving structural whitespace.
- **LINK Paramset Validation** (2026.2.1): Fixed `put_paramset` with `check_against_pd=True` for LINK paramsets. Validation is now automatically skipped for LINK calls to prevent "Parameter not found" errors.
- **Schedule Pydantic Models JSON Serialization** (2026.2.1): Added `_JsonSerializableMixin` to all schedule Pydantic models to support orjson/Home Assistant JSON serialization.

### Breaking Changes (aiohomematic)

- **Schedule access moved to WeekProfileDataPoint** (2026.2.6): All schedule methods and properties removed from `BaseCustomDpClimate` and `CustomDataPoint`. Schedule operations are now exclusively available via `device.week_profile_data_point`.

- **Climate profile property renames** (2026.2.6): On `ClimateWeekProfileDataPointProtocol`, `active_profile` → `current_schedule_profile`, `active_schedule` → `current_profile_schedule`, `set_active_profile()` → `set_current_schedule_profile()`. This avoids a naming conflict with the device parameter `ACTIVE_PROFILE`. `copy_schedule` and `copy_schedule_profile` parameter renamed from `target_climate_data_point` to `target_data_point`.

- **HA-Addon renamed to HA-App** (2026.2.6): `SystemInformation.is_ha_addon` renamed to `is_ha_app`.

### Changed (aiohomematic)

- **Climate Schedule API unified to Pydantic models** (2026.2.1): The old dual-format API (TypedDict + Pydantic) has been removed. All schedule methods now use Pydantic models exclusively.
- **Rename `_temporary_value` to `_unconfirmed_value`** (2026.2.7): All internal references renamed to clarify the role of the second value tier in the three-tier resolution model (optimistic → unconfirmed → confirmed).
- **DelegatedProperty expansion** (2026.2.6): Replaced 56 boilerplate `@property` methods with `DelegatedProperty` descriptors across 23 files. Reduces repetitive delegation code while preserving runtime behavior.
- **ClimateWeekProfile**: Simple schedule format now uses Pydantic models for automatic validation. The existing user-facing format remains unchanged, but input validation is now more robust with clear error messages.
- **DefaultWeekProfile**: Refactored schedule cache to use human-readable Pydantic models (`SimpleSchedule`, `SimpleScheduleEntry`) instead of complex dictionary format.

## Bump aiohomematic-config to [2026.2.10](https://github.com/SukramJ/aiohomematic-config/compare/2026.2.1...2026.2.10)

New companion library providing device configuration utilities for the integration.

- **Initial release** (2026.2.1): `FormSchemaGenerator` for UI form schemas, `ParameterGrouper` for logical sections, `LabelResolver` for i18n labels, `ConfigSession` for undo/redo change tracking, `ConfigExporter` for JSON export/import, `WidgetType` mapping.
- **Upstream CCU translations** (2026.2.3): Replaced local translation files with CCU translations from aiohomematic. Added `channel_type` parameter to `LabelResolver.resolve()`, `option_labels` on `FormParameter`, `model_description`/`channel_type_label` on `FormSchema`, `model`/`sub_model` parameters to `FormSchemaGenerator.generate()`.
- **Parameter filtering and section titles** (2026.2.4): Locale-aware section titles in `ParameterGrouper` (German translations). Parameters without CCU translation are filtered (matches CCU WebUI easymode behavior). VALUE_LIST parameters always get `option_labels` with humanized fallback.
- **Link parameter metadata & profiles** (2026.2.5): `link_param_metadata` module for classifying LINK parameters (SHORT/LONG grouping, time pair detection, category classification). `ProfileStore` for loading easymode profile definitions from CCU-extracted JSON. `FormSchemaGenerator` enriches LINK parameters with metadata via `enrich_link_metadata` flag. Time preset tables for on/off, delay, and ramp durations.
- **Change history module** (2026.2.6): `ConfigChangeLog` class with FIFO-capped storage, filtering, and serialization. `ConfigChangeEntry` frozen dataclass for immutable change records. `build_change_diff()` helper for computing old/new value diffs.
- **Async profile loading** (2026.2.7): `ProfileStore.get_profiles()` and `ProfileStore.match_active_profile()` are now async. Fixed blocking `read_text`/`open` calls inside the async event loop (uses `asyncio.to_thread`). **Breaking**: callers must now await these methods.
- **Schedule facade module** (2026.2.8): `schedule_facade` module for schedule management in the configuration panel. `list_schedule_devices()` for discovering devices with schedule support. `get_climate_schedule()` / `set_climate_schedule_weekday()` / `set_climate_active_profile()` for climate schedules. `get_device_schedule()` / `set_device_schedule()` for generic device schedules.
- **Schedule domain from upstream** (2026.2.9): Use `schedule_domain` property from aiohomematic instead of local heuristic. Removed `_get_schedule_domain()` helper and `ScheduleType` import from `schedule_facade`.
- **Device-level change history filtering** (2026.2.10): `ConfigChangeLog.get_entries()` now uses prefix matching for the `channel_address` filter, so querying by device address returns history entries for all channels of that device.

# Version [2.2.4](https://github.com/SukramJ/homematicip_local/compare/2.2.3...2.2.4) (2026-02-01)

## What's Changed

### Bug Fixes

- **Program Button Naming**: Fixed regression where CCU program button entities were named "P Taste" instead of the actual program name. The issue was caused by the `HUB_BUTTON` default entity description using a generic translation key that overwrote the program name.
- **Hub Entity Naming**: Fixed regression where hub entities (sysvars, programs) lost their instance name prefix in entity_id (e.g., `switch.otto_sv_anwesenheit` became `switch.anwesenheit`). The fix ensures hub entities don't use a translation_key, allowing the custom name property to properly add "SV "/"P " prefixes.

### Documentation

- **README**: Added "Companion Cards" section featuring the [Climate Schedule Card](https://github.com/SukramJ/homematicip_local_climate_schedule_card) for visual editing of thermostat week profiles.

## Bump aiohomematic to [2026.2.0](https://github.com/SukramJ/aiohomematic/compare/2026.1.54...2026.2.0)

### Bug Fixes

- **Device Re-Pairing** (2026.2.0): Fixed devices not appearing after factory reset and re-pairing. When a device was reset and re-paired with the same address, channel descriptions were not added to cache because only the parent device address was checked.
- **EventBus Subscription Leak** (2026.2.0): Fixed subscription leak for `DeviceLifecycleEvent` when stopping CentralUnit, eliminating "LEAKED_SUBSCRIPTION" warnings during shutdown.
- **CUxD/CCU-Jack Interface Registration** (2026.1.57): Fixed devices incorrectly assigned to `Interface.BIDCOS_RF` instead of their actual interface (e.g., `Interface.CUXD`). This caused `get_data_points(interface=Interface.CUXD)` to filter out all CUxD devices. Interface is now properly registered during device creation.
- **CUxD/CCU-Jack Data Polling** (2026.1.56): Fixed data not updating after startup for polled interfaces. The `refresh_data_point_data()` method was using hardcoded `CallSource.HM_INIT` which caused data points with `ignore_on_initial_load` to be skipped during periodic polling.
- **OperatingVoltageLevel Battery Calculation** (2026.1.55): Fixed battery percentage calculation to use user-configured `LOW_BAT_LIMIT` value instead of default. This fixes incorrect battery readings when users have customized the low battery threshold.

### Test Infrastructure

- **OpenCCU Test Fixtures** (2026.1.55): Added comprehensive test infrastructure for VirtualCCU with OpenCCU backend mode support, including device lifecycle event handling and full 397-device central unit tests.

# Version [2.2.3](https://github.com/SukramJ/homematicip_local/compare/2.2.2...2.2.3) (2026-01-29)

## What's Changed

### New Features

- **Binary Sensor Entities**: Added entity descriptions for new binary sensors:
  - **HmIP-SRH & HM-Sec-RHS**: Added `WINDOW_OPEN` binary sensor for rotary handle sensors (window open detection)
  - **HmIP-SWSD**: Added `SMOKE_ALARM` and `INTRUSION_ALARM` binary sensors for smoke/intrusion detector

### Documentation

- **README Shortened**: Reduced README.md from ~1960 lines to ~140 lines. Detailed documentation moved to the new documentation site at [sukramj.github.io/aiohomematic](https://sukramj.github.io/aiohomematic/). README now contains quick start links, installation instructions, and references to full documentation.

### Bug Fixes

- **Fix SSDP Import for Home Assistant 2025.2+**: Updated `SsdpServiceInfo` import in tests from deprecated `homeassistant.components.ssdp` to new location `homeassistant.helpers.service_info.ssdp`.

### Internal

- **Type Safety Improvements**: Added `@override` decorator to 100+ methods across all entity platforms to explicitly mark methods overriding parent class methods. Added `Final` annotation to 15 `EVENT_*` constants in `const.py`. These changes improve code clarity and enable better static analysis.

## Bump aiohomematic to [2026.1.54](https://github.com/SukramJ/aiohomematic/compare/2026.1.50...2026.1.54)

### New Features

- **HmIP-WRC6-230 Support** (2026.1.53): Added support for HmIP-WRC6-230 (Wall-mount Remote Control 6-button 230V) as a fixed color light device.
- **Derived Binary Sensors** (2026.1.52): A registry-based system now enables creation of binary sensors derived from enum data points. New calculated parameters include `INTRUSION_ALARM`, `SMOKE_ALARM`, and `WINDOW_OPEN`. Examples: HmIP-SRH/HM-Sec-RHS window handle sensors now provide a `WINDOW_OPEN` binary sensor (activated when TILTED or OPEN), and HmIP-SWSD smoke detectors provide `INTRUSION_ALARM` and `SMOKE_ALARM` binary sensors (activated when alarm active).
- **Enhanced Data Point Validity** (2026.1.52): Comprehensive validation for data points now includes type checking, range validation, and proper None handling. Added `has_valid_value_type` and `is_value_in_range` properties to BaseParameterDataPoint. STATUS parameter events are automatically subscribed and processed. Type-specific validation rules for each parameter type (FLOAT, INTEGER, BOOL, ENUM, etc.) with warning logs for out-of-range values received from CCU.
- **Contract Tests for Regression Prevention** (2026.1.51): Added extensive contract testing infrastructure with 500+ tests specifically designed to prevent regressions during AI-assisted refactoring. Coverage includes backend capabilities, state machines, connection recovery, event systems, lifecycle methods, enums, configuration classes, exception hierarchies, protocol interfaces, hub entities, subscription APIs, and device/channel protocols.

### Changed

- **Reduced Validation Logging** (2026.1.54): Log level for data point validation messages (value range min/max and enum index/value checks) reduced from WARNING to DEBUG to reduce log noise.
- **Pydantic Model Conversions**: Multiple configuration classes migrated to Pydantic `BaseModel` with frozen immutability including `TimeoutConfig`, `InterfaceConfig`, `CentralConfig`, `DeviceConfig`, `ProfileConfig`, and `BackendCapabilities`.
- **Type Safety Improvements**: Added `@unique` decorator to 70+ enum classes to prevent accidental duplicate values, `@override` decorator to explicitly mark overridden methods, and `Final` annotations to key constants.

### Bug Fixes

- **Fix Client Reconnection from INITIALIZED State**: Fixed an issue where clients stuck in INITIALIZED state couldn't be reconnected. The state machine now permits `INITIALIZED → DISCONNECTED` transitions enabling recovery.
- **Fix JSON Parsing Control Characters**: Fixed `JSONDecodeError` by sanitizing JSON-RPC responses, escaping control characters (U+0000 to U+001F) to proper `\uXXXX` sequences.

# Version [2.2.2](https://github.com/SukramJ/homematicip_local/compare/2.2.1...2.2.2) (2026-01-25)

## What's Changed

### Bug Fixes

- **Fix Interface Port Resolution**: Interface ports are now correctly resolved using aiohomematic's default port mapping when no port is explicitly configured. JSON-RPC-only interfaces (CUxD, CCU-Jack) now correctly pass `None` instead of a port number, as they don't use XML-RPC ports.

## Bump aiohomematic to [2026.1.50](https://github.com/SukramJ/aiohomematic/compare/2026.1.48...2026.1.50)

### Changed

- **Port Handling Refactoring for JSON-RPC Interfaces**: `InterfaceConfig.port` changed from `int` to `int | None` for cleaner semantics. JSON-RPC-only interfaces (CUxD, CCU-Jack) now properly use `None` instead of the workaround value `0`. This provides improved type safety and eliminates validation workarounds throughout the codebase.

### Bug Fixes

- **Fix Hub Data Not Refreshing After Reconnection**: Hub data (System Update, Programs, Sysvars) is now refreshed after successful reconnection. Previously, stale information persisted—for example, "Update available" would display even after the CCU completed firmware updates during disconnection.
- **Fix Client Recovery for Secondary Interfaces**: Recovery for CUxD and CCU-Jack clients now succeeds when other clients already exist. The issue stemmed from attempting to create all clients simultaneously; the fix creates the specific failing interface client directly instead of recreating all clients.
- **Fix Clients Stuck in INITIALIZED State**: Clients stuck in `INITIALIZED` state (initialized but never connected) can now recover. The state machine now permits `INITIALIZED → DISCONNECTED` transitions, enabling proper state reset for reconnection attempts.
- **Fix JSON-RPC Port Handling**: TCP pre-flight checks now correctly skip interfaces with `None` port. CUxD and CCU-Jack rely on JSON-RPC via central ports (443/80) rather than individual XML-RPC ports. A new JSON-RPC port pre-flight check verifies service availability before client creation.

# Version [2.2.1](https://github.com/SukramJ/homematicip_local/compare/2.2.0...2.2.1) (2026-01-25)

## What's Changed

## Bump aiohomematic to [2026.1.48](https://github.com/SukramJ/aiohomematic/compare/2026.1.46...2026.1.48)

### Bug Fixes

- **Fix XML-RPC Authentication Headers Not Sent with TLS**: Fixed a critical bug where HTTP Basic Authentication headers were not being sent when TLS was enabled. This caused all XML-RPC calls to fail with `ProtocolError: Unauthorized` when CCU authentication was enabled. The fix passes authentication headers directly to the transport classes.
- **Fix Authentication Check Fails for Non-Admin Users**: Fixed a regression introduced in 2026.1.41 where users without ADMIN rights on the CCU would fail to connect. When `CCU.getAuthEnabled` returns "access denied (ADMIN needed 2)", this proves authentication is enabled (otherwise no permission check would occur). The method now correctly returns `True` instead of propagating the exception.

# Version [2.2.0](https://github.com/SukramJ/homematicip_local/compare/2.1.2...2.2.0) (2026-01-23)

## What's Changed

### Breaking Changes

- **System Update Entity Removed for HA-Addon**: The System Update entity is no longer created for Home Assistant Add-on deployments. Users with existing orphaned entities from previous versions can manually delete them via Home Assistant's entity management.

### Bug Fixes

- **Fix Translation Error When Skipping Backend Detection**: Fixed "The intl string context variable 'detected_interfaces' was not provided" error when using the "Skip automatic backend detection" option in the config flow. The interface step now provides a default placeholder value when detection results are not available.
- **Fix Missing device_class for Update Entities**: Update entities for device firmware and hub updates now correctly report `device_class: firmware`. Previously the device_class was not set despite having an entity description rule defined.

### Internal

- **Remove Unused UpdateEntityDescription Defaults**: Removed `UpdateEntityDescription` entries for `UPDATE` and `HUB_UPDATE` from `defaults.py` since Update entities don't use the generic entity helper system. The `device_class` is now set directly on the entity classes.
- **Migrate Event Platform to ChannelEventGroup**: Migrated the event platform from individual `GenericEvent` subscriptions to the new `ChannelEventGroupProtocol` pattern. Event groups are now virtual data points bound to channels, providing unified subscription management via `subscribe_to_data_point_updated()`. This simplifies subscription handling (single subscription per entity instead of one per event type) and aligns with the standard `CallbackDataPointProtocol` pattern.
- **Config Entry Migration v14**: Added entity registry migration for event entities to update unique_ids from the old channel-based format (`homematicip_local_{channel_unique_id}`) to the new event_group-based format (`homematicip_local_event_group_homematic.keypress_{channel_unique_id}`). This ensures existing event entities are preserved when upgrading from version 2.1.2.
- **Config Entry Migration v15**: Added migration to remove deprecated `OptionalSettings` values from config entry data. Removes `ENABLE_LINKED_ENTITY_CLIMATE_ACTIVITY` (now always enabled) and `USE_INTERFACE_CLIENT` (legacy client removed) that were removed in aiohomematic 2026.1.44.
- **Local Validators**: Implemented local voluptuous validators (`validate_channel_no`, `validate_wait_for`, `validate_device_address`, `validate_channel_address`, `validate_paramset_key`) in `support.py` to replace validators removed from aiohomematic after its migration to Pydantic.

## Bump aiohomematic to [2026.1.46](https://github.com/SukramJ/aiohomematic/compare/2026.1.38...2026.1.46)

### New Features

- **HA-Addon Detection**: Automatically detects when running as a Home Assistant Add-on by checking for `HM_RUNNING_IN_HA` or `SUPERVISOR_TOKEN` environment variables. A new `is_ha_addon` field in `SystemInformation` indicates the backend's execution context.
- **System Update Handling for HA-Addons**: The `has_system_update` property now returns `False` when operating as an HA-Addon, preventing unnecessary system update entities from being created. The `firmware_update_trigger` capability is similarly disabled, since the HA Supervisor manages all updates within that environment.
- **Free-Threaded Python Support**: Added compatibility with Python 3.14 free-threaded builds (no GIL) through a new compatibility module. Includes detection functions and a conditional JSON backend that automatically selects orjson on standard builds while falling back to stdlib json on free-threaded versions.
- **CentralRegistry for Thread-Safe Instance Management**: New thread-safe registry replaces the previous module-level dictionary for managing CentralUnit instances, employing a copy-on-read pattern safe for both GIL-enabled and free-threaded Python environments.
- **orjson Now Optional**: orjson is no longer a required dependency. Install via `pip install aiohomematic[fast]` for enhanced JSON serialization on standard Python builds. All JSON operations now use a compatibility module that automatically selects the best available backend.
- **Paramset Description Patching System**: Added a generic mechanism to correct faulty `paramset_descriptions` from the CCU. The system applies device-specific corrections during data ingestion using declarative patch definitions. Initial patch corrects HM-CC-VG-1 channel 1 `SET_TEMPERATURE` MIN/MAX values (4.5/30.5) instead of the incorrect CCU-provided values.
- **translation_key for Data Points**: All data point types now provide a consistent `translation_key` property for translations. This includes hub sensors, metrics sensors, inbox, install mode, device/system updates, and calculated data points.
- **Startup Resilience for Authentication Errors**: Added a 3-stage validation approach for improved startup reliability: TCP pre-flight check validates port availability, client creation & RPC validation verifies backend communication, and retry with exponential backoff handles transient errors before failing. New `TimeoutConfig` parameters: `startup_max_init_attempts` (default: 5), `startup_init_retry_delay` (default: 3s), and `startup_max_init_retry_delay` (default: 30s).
- **Device Availability Events for Forced Availability**: The `force_device_availability` method now fires `DeviceLifecycleEventType.AVAILABILITY_CHANGED` events, ensuring the integration receives proper notifications when device availability is manually changed.
- **SensorValueMixin**: New mixin class consolidating duplicated value transformation logic between `DpSensor` (generic) and `SysvarDpSensor` (hub). Provides standardized handling for value list lookup, converter functions, and string length validation.

### Changed

- **ChannelEventGroup as Virtual Data Point**: Refactored `ChannelEventGroup` from a helper class to a virtual data point bound to the Channel. Event groups now extend `CallbackDataPoint` and follow the standard subscription pattern with `subscribe_to_data_point_updated()`. See migration guide: `docs/migrations/channel_event_group_migration_2026_01.md`.
- **Replace Voluptuous with Pydantic**: Migrated all validation from voluptuous to Pydantic for improved type safety and validation. Address validation patterns (`DEVICE_ADDRESS_PATTERN`, `CHANNEL_ADDRESS_PATTERN`) remain available as compiled regex patterns in `aiohomematic.const`.
- **Async RPC Server is Now Standard**: The async XML-RPC server (using aiohttp) is now the only RPC server implementation. The legacy thread-based XML-RPC server has been removed along with `OptionalSettings.ASYNC_RPC_SERVER`.
- **InterfaceClient is Now Standard**: The legacy client implementations (`ClientCCU`, `ClientJsonCCU`, `ClientHomegear`) and handler classes have been removed. `InterfaceClient` with the Backend Strategy Pattern is now the only implementation. `OptionalSettings.USE_INTERFACE_CLIENT` has been removed.
- **Linked Entity Climate Activity Always Enabled**: The `OptionalSettings.ENABLE_LINKED_ENTITY_CLIMATE_ACTIVITY` feature flag has been removed - linked entity climate activity is now always enabled.

### Bug Fixes

- **Automatic Reconnection After Startup Failures**: Fixed scenarios where the backend was unavailable during Home Assistant startup. The integration previously remained in FAILED state indefinitely. Now the heartbeat timer automatically activates when central transitions to FAILED state during startup, with recovery attempts every 60 seconds (configurable). Port resolution for TCP checks falls back to interface configuration when client doesn't exist.
- **Cache Schema v3**: Cache schema bumped to v3 with automatic rebuild when the schema version changes.
- **Legacy Cache Migration for Climate Schedules**: Fixed `ValidationException: Time 360 is invalid` error when starting with cached schedule data. The issue was old cached `endtime` values stored as numeric strings (`"360"`) instead of integers or time strings. A new helper handles all three formats.
- **Coordinated Cache Clearing on Version Mismatch**: Fixed issue where only one cache was cleared on schema version change. Now both device and paramset description caches are cleared together, preventing incomplete rebuilds.
- **Sound Player Soundfile Default Handling**: Fixed `turn_on()` to use the entity's current value or default when `soundfile` is not provided, instead of always defaulting to `"INTERNAL_SOUNDFILE"`.
- **Backend Detection Timeout Support**: Fixed `TypeError: ServerProxy.__init__() got an unexpected keyword argument 'timeout'`. Introduced custom transport classes for proper socket timeout handling.

# Version [2.1.2](https://github.com/SukramJ/homematicip_local/compare/2.1.1...2.1.2) (2026-01-14)

## What's Changed

### New Features

- **New Services for Configuration Reload**: Added two new admin services to reload device and channel configurations from the CCU without restarting Home Assistant:
  - `reload_device_config`: Reloads device configuration (accepts device_id or device_address)
  - `reload_channel_config`: Reloads channel configuration (accepts device_id or device_address + channel number)

### Bug Fixes

- **Fix Backend Detection Hanging with Non-Standard Ports**: Fixed issue where backend detection would hang indefinitely when using non-standard HTTP/HTTPS ports (e.g., port 2080 instead of 80). Added 20-second timeout wrapper with graceful degradation - if detection times out or fails, the config flow now proceeds directly to manual interface configuration instead of blocking. Users can also skip backend detection entirely via new checkbox in the connection step (useful when non-standard ports are known upfront). Resolves [#2804](https://github.com/SukramJ/aiohomematic/issues/2804).
- **Fix Translation Error on Duplicate CCU Configuration**: Fixed "The intl string context variable 'serial' was not provided" error when attempting to add a CCU instance that is already configured. The abort message now correctly displays the serial number.
- **Fix Unwanted Integration Reload on Action Select Change**: Action select values (e.g., siren tones, light patterns) are now stored in a separate storage file instead of the config entry. Previously, changing an action select value triggered `async_update_entry()` which caused a full integration reload via the `update_listener`. This fix eliminates unnecessary restarts when selecting different tones or patterns. Existing values are automatically migrated from config entry to the new storage file.
- **Fix Options Flow Not Persisting Changes**: Configuration changes made in the Options Flow (e.g., enabling SysVar scan) were lost after Home Assistant restart. The issue was caused by a shallow copy of config entry data that shared nested dictionary references with the original. Home Assistant's change detection saw no difference and skipped saving. Now uses `deepcopy` to ensure complete independence.
- **Fix `homematic.device_availability` Event Not Fired**: The event was defined but never actually fired when device availability changed. This broke all blueprints that relied on this event (persistent notifications, device reactivation). Now fires `homematic.device_availability` with full event data (device_id, name, address, interface_id, model, unavailable status) when `DeviceLifecycleEventType.AVAILABILITY_CHANGED` is received.
- **Fix Device Services Failing for Sub-Devices**: Services like `force_device_availability` failed with "No device found" for sub-devices (devices with `enable_sub_devices` option). The identifier parser incorrectly included the group suffix (e.g., `-1`) in the interface_id, causing client lookup to fail. Now correctly strips the group suffix when parsing sub-device identifiers.

### Internal

- **Migrate to Capabilities Pattern**: Updated all `supports_*` properties to the new unified Capabilities pattern from aiohomematic. Static capabilities now use `capabilities.*` (e.g., `capabilities.brightness`, `capabilities.open`), while dynamic properties use `has_*` (e.g., `has_hs_color`, `has_effects`). This affects light, lock, siren, and MQTT entities.
- **Config Entry Version 13**: Added migration to remove `action_select_values` from config entry data.
- **Default Entity Descriptions for Update Entities**: Added default descriptions with `UpdateDeviceClass.FIRMWARE` for `UPDATE` and `HUB_UPDATE` data point categories.
- **Interface Connectivity Binary Sensors**: Added entity description rule with `BinarySensorDeviceClass.CONNECTIVITY` for the new hub-level interface connectivity sensors.

## Bump aiohomematic to [2026.1.38](https://github.com/SukramJ/aiohomematic/compare/2026.1.27...2026.1.38)

### New Features

- **Configurable Backend Detection Timeouts**: Backend detection timeouts are now managed centrally through `TimeoutConfig` instead of hardcoded constants. Two new configurable fields:
  - `backend_detection_request: float = 5.0` — Timeout for individual XML-RPC/JSON-RPC requests
  - `backend_detection_total: float = 15.0` — Total timeout for complete detection process
- **Socket-Level Timeout for XML-RPC Connections**: Added `timeout` parameter to XML-RPC connections to prevent indefinite hangs when connecting to unreachable hosts. Default socket timeout of 5s during detection, while normal RPC operations maintain backward compatibility.
- **Smart Early Abort on Fatal Connection Errors**: Backend detection now distinguishes fatal errors (ETIMEDOUT, EHOSTUNREACH, ENETUNREACH) from transient errors (ECONNREFUSED). Fatal errors trigger immediate abort, reducing detection time on unreachable hosts from ~30s to ~5s (6× improvement).
- **Service Methods for Manual Configuration Reload**: New `Device.reload_device_config()` and `Channel.reload_channel_config()` methods enable external cache updates for scenarios where CONFIG_PENDING events are unreliable (particularly for classic BidCos devices).

### Bug Fixes (from 2026.1.37)

- **Fix Schedule Validation Error on Device Initialization**: Fixed `ValidationException: Time 360 is invalid` error occurring when heating group devices (VirtualDevices interface) are initialized. The `identify_base_temperature()` function incorrectly assumed all endtime values in the schedule cache are formatted strings ("06:00"), but during initial cache loading they can be raw integers (360 minutes) directly from the CCU. The function now handles both integer and string formats by checking the type before conversion. This fixes climate entity creation failures and recurring errors on Home Assistant startup.
- **Fix Type Safety for ScheduleSlot**: Updated `ScheduleSlot` TypedDict to correctly declare `endtime: str | int` instead of `endtime: str`. This reflects the actual behavior where the CCU always returns integers (minutes since midnight) while internal conversion may use string format.
- **Fix Schedule Validation Error for HM-CC-VG-1 Heating Groups**: The CCU sometimes returns ENDTIME values as strings ("360") instead of integers (360). The `convert_raw_to_dict_schedule()` function now handles both formats by checking if string values are numeric before conversion.
- **Fix CUxD/CCU-Jack Unnecessary Reconnects via MQTT**: Fixed false positive connection loss detection for CUxD and CCU-Jack interfaces when used with Homematic(IP) Local MQTT bridge. These interfaces use JSON-RPC without ping/pong support and receive events via MQTT, causing callback timeout checks to incorrectly trigger reconnects every ~4 minutes. Both `is_callback_alive()` and `is_connected()` now check `ping_pong` capability to skip callback timeout validation for MQTT-based interfaces.
- **Fix Empty Paramset Descriptions Not Being Cached**: Fixed issue where paramset descriptions that return an empty dict `{}` (valid response) were incorrectly treated as missing. HmIP base device addresses and some channel types return empty MASTER or VALUES paramsets which is valid behavior. The fix uses `is not None` check instead of truthy check, ensuring empty dicts are properly cached.
- **Fix Device Availability Not Reset After CCU Restart**: All devices remained unavailable after CCU restart because the availability reset only triggered when `old_state` was in `(DISCONNECTED, FAILED, RECONNECTING)`, but the final transition has `old_state=CONNECTING`. Added `CONNECTING` to the list of states that trigger availability reset.
- **Fix Race Condition in Client State Event Processing**: Events from the EventBus may be processed out of order (e.g., `disconnected` event processed after `connected` event). Now checks the current client state before marking devices unavailable, preventing incorrect availability changes when the client has already recovered.
- **Fix Connectivity Sensors Not Updating During CCU Restart**: Interface connectivity binary sensors now subscribe to `ClientStateChangedEvent` for immediate reactive updates instead of only updating during scheduled refresh cycles.
- **Fix CuXD Devices Not Created When Paramset Descriptions Missing**: When device_descriptions were already cached but paramset_descriptions were missing (e.g., from a previous interrupted run), devices were skipped. Now properly detects missing paramset_descriptions and ensures both caches stay synchronized.
- **Fix Temperature Parameter Formatting in Schedules**: Temperature values in simple weekly schedules were sent as integers to the CCU, causing them to be silently ignored. The CCU requires temperature parameters as floats. Explicit float conversions are now applied to all schedule temperature values.
- **Fix Cache Persistence Race Condition**: Cache is now automatically persisted when data fetch completes, preventing paramsets from being lost if a shutdown occurs before the scheduled save.
- **Fix Device Creation with Incomplete Data**: Added validation ensuring all required paramsets exist in cache before device creation proceeds. Incomplete data now triggers an `INCOMPLETE_DEVICE_DATA` integration issue event instead of silently creating broken devices.
- **Fix Parameter Type Conversion for HM-CC-VG-1**: Fixed TypeError when calling `put_paramset` on HM-CC-VG-1 device. The device returns MIN/MAX values as strings instead of numbers, which now undergo proper numeric conversion before comparison.

### Changed

- **Schedule Cache Now Uses Pessimistic Update Strategy**: Climate schedule cache (`ClimateWeekProfile` and `DefaultWeekProfile`) is no longer updated optimistically when calling `set_schedule()`, `set_profile()`, or `set_weekday()`. The cache is now updated only after receiving `CONFIG_PENDING = False` from the CCU via `reload_and_cache_schedule()`. This ensures the cache always reflects the actual CCU state, eliminating race conditions and inconsistencies. The cache remains essential for performance (avoiding RPC calls on reads) and event optimization (publishing events only when data changes).

### New Features

- **Faster Connectivity Detection**: Improved connection loss detection from ~240s to ~20s with new `ping_timeout` (10s) and `connectivity_error_threshold` (1). Devices are now marked unavailable immediately when client state changes to DISCONNECTED/FAILED. System health score now correctly shows 0% before connections are established.
- **Interface Connectivity Binary Sensors**: New hub-level binary sensors showing per-interface connectivity status (HmIP-RF, BidCos-RF, etc.). Shows ON when connected and operational, OFF when disconnected or failed. Always available since its purpose is to show the connection state itself.
- **Schedule Support for HM-CC-VG-1**: Enabled schedule functionality for the HM-CC-VG-1 virtual group device.
- **Type Conversion for Read Operations**: New optional `convert_from_pd` parameter across client implementations automatically converts CCU values to correct types (INTEGER, FLOAT, BOOL, ENUM, STRING) based on ParameterDescription.
- **WeekProfile Automatic Type Conversion**: Both `ClimateWeekProfile` and `DefaultWeekProfile` now use `convert_from_pd=True` when fetching schedules, ensuring ENDTIME values return as integers and TEMPERATURE as floats directly from the client layer.

# Version [2.1.1](https://github.com/SukramJ/homematicip_local/compare/2.1.0...2.1.1) (2026-01-09)

## What's Changed

### Bug Fixes

- **Fix Unwanted Config Entry Reloads**: Fixed integration restarting whenever a device's availability changed. The device registry's `disabled_by` field was being updated on availability changes, which Home Assistant interprets as requiring a config entry reload. Entity availability is now handled exclusively through the entity's `available` property, which is the correct approach for transient state changes.
- **Fix False Positive Duplicate Key Warnings**: Entity description validation no longer warns about rules with the same key when they have different filtering criteria (device filters, priorities, etc.). These are valid override patterns, not duplicates.

## Bump aiohomematic to [2026.1.27](https://github.com/SukramJ/aiohomematic/compare/2026.1.20...2026.1.27)

### Bug Fixes

- **Fix State Machine Transition Error on Unload**: Allow transition from `FAILED` to `DISCONNECTED` state. This fixes `InvalidStateTransitionError` when unloading the integration while a client is in failed state
- **Fix Leaked EventBus Subscriptions on Central Stop**: Six internal subscription leaks have been fixed across `HubCoordinator`, `ClientCoordinator`, `CacheCoordinator`, `EventCoordinator`, `CentralUnit`, and various client classes. The number of leaked subscriptions logged at shutdown has been reduced from ~7800 to zero
- **Fix Empty Device List Treated as Error**: The `initialize_proxy()` method now correctly handles empty device lists from interfaces that don't support RPC callbacks. Previously, an empty device list was incorrectly treated as a connection failure
- **Fix Ping/Pong Mismatch Issue Not Clearing**: The `ping_pong_mismatch` repair issue is now correctly removed when the connection recovers (mismatch_count drops to 0). Previously, the issue remained visible even after recovery due to a type comparison mismatch
- **Clear Stale Issues on Startup**: Transient repair issues (`ping_pong_mismatch`, `pending_pong_mismatch`, `unknown_pong_mismatch`, `fetch_data_failed`, `interface_not_reachable`, `xmlrpc_server_receives_no_events`) are now automatically deleted when the integration starts. These issues from previous sessions are no longer relevant after a restart
- **Fix Persistent Repair Issues After CCU Restart**: Fixed central state getting stuck in "recovering" after successful recovery. A race condition in `ConnectionRecoveryCoordinator` caused the state transition check to run before the interface was removed from active recoveries, preventing the transition to "running" state. Also adds immediate connection repair notifications when recovery starts and clears them when recovery succeeds
- **Fix Recovery Stuck in Infinite Retry Loop**: After CCU restart, the XML-RPC proxy's HTTP connection could enter an inconsistent state causing `system.listMethods` calls to fail silently. The proxy transport is now reset before RPC availability checks during recovery

### Internal

- **Migrate to Strongly Typed Events**: Updated to use `IntegrationIssueType` and `IntegrationIssueSeverity` enums instead of string comparisons for better type safety and IDE support

# Version [2.1.0](https://github.com/SukramJ/homematicip_local/compare/2.0.6...2.1.0) (2026-01-08)

## What's Changed

### Bug Fixes

- **Home Assistant 2026.1.0+ Compatibility**: Fixed "Detected blocking call to import_module" error that prevented the integration from loading. All blocking I/O operations during central unit creation now run in a thread pool executor.

### Internal

- **Async Central Creation**: Migrated `ControlConfig.create_central()`, `check_config()`, `create_control_unit()`, and `create_control_unit_temp()` to async methods
- **Factory Pattern for ControlUnit**: Added `BaseControlUnit.async_create()` class method for async instantiation

## Bump aiohomematic to [2026.1.20](https://github.com/SukramJ/aiohomematic/compare/2026.1.17...2026.1.20)

### New Features

- **`old_value` and `new_value` fields in `DataPointStateChangedEvent`**: External consumers can now track what changed without maintaining their own previous state
- **`AvailabilityInfo` dataclass**: New unified view of device availability bundling reachability, battery, and signal information
- **`Device.availability` property**: Returns `AvailabilityInfo` providing a unified view of device connectivity and health status
- **Consumer API documentation**: New `docs/consumer_api.md` guide for external consumers like Matter bridges

### Internal

- **Eliminate all remaining lazy imports**: All `noqa: PLC0415` markers have been removed from production code. Circular imports have been resolved through module restructuring
- **Remove unnecessary delayed imports**: Moved imports to top-level where no circular dependency exists

# Version [2.0.6](https://github.com/SukramJ/homematicip_local/compare/2.0.5...2.0.6) (2026-01-08)

## What's Changed

### Bug Fixes

- **Device Auto-Confirmation After Cache Clear**: Fixed devices not being auto-confirmed after clearing the aiohomematic cache. Previously, all devices were incorrectly shown as repair issues because the wrong device identifier format was used for registry lookups. Devices that already exist in Home Assistant are now correctly recognized and auto-confirmed
- **Device Availability Updates**: Fixed device availability changes not updating the device registry correctly due to the same identifier format mismatch

## Bump aiohomematic to [2026.1.17](https://github.com/SukramJ/aiohomematic/compare/2026.1.13...2026.1.17)

### Bug Fixes

- **VirtualDevices Init Timeout**: Fixed VirtualDevices init() timing out even though the CCU successfully processed the request. On some CCU backends (OpenCCU, RaspberryMatic), the VirtualDevices service processes the init() request correctly but fails to send the response. The initialization is now treated as successful if a listDevices callback was received during the timeout
- **VirtualDevices Connection Failure**: Fixed VirtualDevices failing to connect on OpenCCU/RaspberryMatic. The CCU's XML-RPC parser crashed when receiving device descriptions with empty `CHILDREN` fields. Device descriptions are now normalized to ensure `CHILDREN` is always a list
- **Retry Mechanism Removed**: Removed the retry mechanism that was conflicting with CircuitBreaker pattern, causing cascading failures. This particularly affected slower backends (Virtual Devices on Raspberry Pi 4, OpenCCU systems) where retry attempts counted toward circuit breaker thresholds, triggering premature failures during initialization. Network errors now fail immediately for more predictable behavior
- **Homegear Device Names Not Loading**: Fixed device names not loading for Homegear backends. The InterfaceClient was missing metadata retrieval via `getMetadata()` calls

# Version [2.0.5](https://github.com/SukramJ/homematicip_local/compare/2.0.4...2.0.5) (2026-01-05)

## What's Changed

### New Features

- **Simple Schedule Services**: Added `get_schedule_simple_profile` and `get_schedule_simple_weekday` services. These return schedule data in a simplified format that is easier to read and use.

### Deprecations

- **Schedule Services**: Deprecated `set_schedule_profile`, `set_schedule_weekday`, `get_schedule_profile`, and `get_schedule_weekday` services. These will be removed in April 2026. Use `set_schedule_simple_profile`, `set_schedule_simple_weekday`, `get_schedule_simple_profile`, and `get_schedule_simple_weekday` instead. A warning is now logged when using the deprecated services.

## Bump aiohomematic to [2026.1.13](https://github.com/SukramJ/aiohomematic/compare/2026.1.9...2026.1.13)

### Bug Fixes

- **CUxD/CCU-Jack Recovery Fix**: Fixed recovery mechanism for JSON-RPC-only interfaces (CUxD, CCU-Jack). Recovery now checks the JSON-RPC port (80/443) instead of failing at the TCP check stage. This prevents the central unit from entering a FAILED state when these services are actually available
- **Device Availability Not Updating**: Fixed devices not showing as unavailable when UN_REACH changes. All entity states are now refreshed when device availability changes
- **HmIP-MP3P LED Auto-Off**: Fixed LED turning off after 10 seconds on HmIP-MP3P sound player devices
- **VirtualDevices Init Timeout**: Fixed initialization timeout causing client failure for virtual devices
- **Device Cache After Firmware Updates**: Fixed device structure changes after firmware updates. Cached descriptions are now removed and refreshed from the CCU, preventing errors like "Non-existent Channel 3"
- **Device Replacement/Re-pairing**: Fixed device replacement and re-pairing handlers. Old device entries are now properly removed and recreated with fresh data
- **Hub Entities with Secondary Client Failures**: Fixed system variables and programs not appearing when secondary clients (e.g., CUxD) fail to initialize
- **Connection Recovery Port Detection**: Fixed port detection during connection recovery for all client implementations
- **Channel Names Not Loading**: Fixed channel names not loading when using InterfaceClient (JSON-RPC). The nested channels array from the JSON-RPC response is now processed correctly

# Version [2.0.4](https://github.com/SukramJ/homematicip_local/compare/2.0.3...2.0.4) (2026-01-04)

## What's Changed

### New Features

- **Undetected Interface Warning**: Config flow now shows a warning when enabled interfaces were not detected on the CCU (e.g., CUxD installed but not running)

### Bug Fixes

- **Device Trigger Address Mapping**: Fixed `device_address` to `address` conversion in device triggers. Existing automations using device triggers (e.g., button press events) that failed with "required key not provided @ data['address']" will now work after re-saving
- **Validation Error UX**: Validation errors during interface configuration now stay on the interface page instead of navigating to port configuration. This allows users to disable problematic interfaces (e.g., CUxD not running) directly
- **Interface Availability Pre-Check**: Config flow now validates interface availability BEFORE attempting connection. If an interface is enabled but was not detected on the CCU, a clear error message is shown immediately without unnecessary connection attempts

## Bump aiohomematic to [2026.1.9](https://github.com/SukramJ/aiohomematic/compare/2026.1.8...2026.1.9)

### Improvements

- **Backend Detection Validates Interface Availability**: The backend detection now verifies that each interface process is actually running via `is_present()` check, not just installed
- **Fix CUxD/CCU-Jack JSON-RPC Method Overrides**: `ClientJsonCCU` now properly uses JSON-RPC for all device operations
- 
# Version [2.0.3](https://github.com/SukramJ/homematicip_local/compare/2.0.2...2.0.3) (2026-01-03)

## What's Changed

### New Features

- **Light Last Brightness Option**: Added config option `Restore last brightness for lights` in advanced settings. When enabled, lights will turn on with the last non-zero brightness level instead of default 100%. Default is disabled.

### Improvements

- **Configuration Options**: Improved labels and descriptions for all advanced configuration options in config flow and options flow
- **Documentation**: Updated README.md with corrected descriptions for Device Behavior and Expert Options sections

### Bug Fixes

- **Sensor State Class**: Added unit-based fallback rules for %, bar, °C, and g/m³ units. This restores long-term statistics support for Homebrew devices like HB-UNI sensors
- **Device Model Matching**: Fixed case-insensitive device model matching for entity description rules. Older devices like HmIP-SWDO (reported as `HMIP-SWDO` by CCU) now correctly receive their device_class (e.g., `window`)
- **Service Schema**: Removed invalid `base_temperature` parameter from `set_schedule_simple_profile` service schema (parameter is part of `simple_profile_data`, not a separate field)
- **Service Name**: Fixed incorrect service name `create_backup` → `create_ccu_backup` in release notes

## Bump aiohomematic to [2026.1.8](https://github.com/SukramJ/aiohomematic/compare/2026.1.5...2026.1.8)

### Bug Fixes

- **Fix CuXD/CCU-Jack Device Control**: `ClientJsonCCU` now properly overrides `set_value` and `put_paramset` to use JSON-RPC
- **Fix Sysvar-to-Device Association**: System variables with device references are now correctly associated with their devices/channels
- **Fix Runtime Device Addition**: Fixed `KeyError` when adding new devices during runtime after cache was loaded
- 
### New Features

- **Circuit Breaker Incident Recording**: Circuit breaker state changes are now recorded as incidents
- **CONNECTION_LOST Incident Recording**: Connection loss events are now recorded as incidents
- **CONNECTION_RESTORED Incident Recording**: Connection restoration events are now recorded as incidents
- **RPC_ERROR Incident Recording**: RPC call failures are now recorded as incidents
- **CALLBACK_TIMEOUT Incident Recording**: Callback timeout events are now recorded as incidents
- **Per-Type Incident Storage**: IncidentStore now uses per-IncidentType storage limits

# Version [2.0.2](https://github.com/SukramJ/homematicip_local/compare/2.0.1...2.0.2) (2026-01-02)

## What's Changed

### New Features

- **Confirm All Delayed Devices Service**: New service `confirm_all_delayed_devices` to confirm all pending inbox devices at once

### Bug Fixes

- **Callback Issues Cleanup**: Stale callback repair issues are now cleaned up at startup (fixes leftover issues from PingPong race condition)

## Bump aiohomematic to [2026.1.5](https://github.com/SukramJ/aiohomematic/compare/2026.1.3...2026.1.5)

### New Features

- **Add IncidentStore for Persistent Diagnostic Incidents**: New storage system for tracking and persisting diagnostic incidents
- **PingPong Tracker Incident Recording**: Connection health issues are now recorded as incidents
- **PingPong Diagnostics Journal**: Enhanced diagnostic capabilities for connection monitoring

### Bug Fixes

- **Fix PingPong Unknown Issue Not Cleared**: Unknown PONG mismatch issues are now properly cleared when conditions normalize
- **Fix OperatingVoltageLevel Shows Unknown After Restart** (Issue #2674): Battery parameters now load from cache on startup
- **Fix KeyError for PARENT in Device Descriptions**: Use `.get()` to safely access optional `PARENT` field
- 
# Version [2.0.1](https://github.com/SukramJ/homematicip_local/compare/2.0.0...2.0.1) (2026-01-02)

## What's Changed

### Bug Fixes

- **Select Entities**: Fixed Select entities (e.g., WINDOW_STATE) not being created due to incorrect whitelist filtering

## Bump aiohomematic to [2026.1.3](https://github.com/SukramJ/aiohomematic/compare/2026.1.2...2026.1.3)

### Bug Fixes

- **Fix PingPong Race Condition**: Register ping token in tracker _before_ sending the ping request
- **Fix Week Profile ScheduleCondition**: Extended `ScheduleCondition` enum with all 8 valid values
- **Fix ClientJsonCCU Handler Initialization**: `ClientJsonCCU` (used for CCU-Jack) now properly initializes handlers

# Version [2.0.0](https://github.com/SukramJ/homematicip_local/compare/1.90.2...2.0.0) (2026-01-02)

## What's Changed

### New Features

- **HmIP-WRCD Text Display**: Full support for the wall-mount remote control with display via NotifyEntity, including services for sending text with icons, colors, sounds, and alignment options
- **HmIP-MP3P Sound Player**: Full support for the combination signalling device with services for sound playback (play_sound, stop_sound) and LED control (set_sound_led) with colors, brightness, and timing options
- **Siren Control**: Automatic select entities for siren tone and light pattern selection with full translations (no manual InputHelper setup required)
- **Reauthentication**: Added reauthentication flow to update expired credentials without removing the integration
- **Reconfigure Flow**: Quick reconfiguration of connection settings without full re-setup
- **Air Quality Sensors**: New entity descriptions for DIRT_LEVEL and SMOKE_LEVEL sensors
- **Enhanced Diagnostics**: Comprehensive system metrics in diagnostics including RPC statistics, event bus metrics, cache performance, health status, and service call analytics
- **System Metrics Sensors**: New diagnostic sensors for monitoring system health (%), connection latency (ms), and last event age (s) - providing real-time visibility into CCU communication status
- **Delayed Device Repair**: Devices stuck in the CCU inbox can now be added through Home Assistant's repairs interface with a guided fix flow
- **Restore Last Brightness**: Dimmers now remember their last brightness level and automatically restore it when turned on without specifying brightness (persists across HA restarts)

### Improvements

- **Configuration Experience**: Enhanced config flow with improved error messages, progress indicators (Step X of Y), and menu-based navigation
- **Error Handling**: Reduced log flooding during connection issues with improved error handling decorator for entity actions
- **Translations**: Fixed naming of untranslated entities and improved translation coverage for press events
- **Translations**: Added missing repair issue translations (callback_server_failed, client_failed, connection_failed) and entity translations (button_press)

### Bug Fixes

- **Services**: Fixed `set_schedule_simple_weekday` service
- **Translations**: Fixed translation issues

### Developer Experience

- **Code Quality**: Strict mypy type checking, consistent use of keyword-only arguments, removed legacy code from config flow
- **Testing**: Comprehensive test coverage improvements for config flow, services, lights, and updates
- **Documentation**: Added comprehensive CLAUDE.md for AI assistants with development guidelines and project structure

## Bump aiohomematic to [2026.1.2](https://github.com/SukramJ/aiohomematic/compare/2025.11.7...2026.1.2)

### Storage & Persistence

- **Storage Abstraction Layer**: Unified storage system enabling Home Assistant Store integration
  - Protocol-based architecture allows transparent substitution of storage backends
  - Local implementation uses orjson for fast serialization with atomic writes
  - Supports ZIP archive loading, version migrations, and delayed/debounced saves
- **Device Definition Export**: Export device definitions as single ZIP file for easier sharing and debugging

### RPC Server

- **Async XML-RPC Server** (Experimental): New asyncio-native alternative to thread-based server
  - Enable via `OptionalSettings.ASYNC_RPC_SERVER` in CentralConfig
  - Full `system.multicall` support for batched CCU events
  - Health-check endpoint (`GET /health`) for monitoring
  - Metrics: request count, error count, latency, active background tasks
  - Graceful shutdown with task cancellation

### Connection Recovery

- **Unified Recovery Architecture**: New event-driven connection recovery coordinator
  - Staged recovery process: TCP check → RPC check → Warmup → Stability check → Reconnect
  - Automatic retry with exponential backoff (max 8 attempts)
  - Parallel recovery support for multi-interface setups
- **Fixed Authentication Errors**: JSON-RPC sessions are now cleared when recovery starts
  - Prevents "access denied" errors after CCU restarts
- **Device Inbox at Startup**: Inbox sensor now available immediately after integration start
- **Repair Issues Restored**: Delayed device creation again triggers repair issues in HA

### Observability & Metrics

- **Complete Event-Driven Metrics**: All components now emit metric events to EventBus instead of maintaining local state
  - `MetricsObserver` aggregates latency, counter, gauge, and health metrics in real-time
  - Type-safe `MetricKey` dataclass with `MetricKeys` factory for all known metrics
  - `emit_latency()`, `emit_counter()`, `emit_gauge()`, `emit_health()` functions for easy metric emission
  - Dedicated `aiohomematic/metrics/` module with clean separation of concerns
- **Comprehensive System Events**: New events for complete system observability
  - Connection state changes with reason tracking
  - Cache invalidation and refresh events
  - Circuit breaker state transitions and trip notifications
  - Scheduler task execution and data refresh events
  - Request coalescing events for performance monitoring
- **RPC Server Monitoring**: Track incoming requests from CCU with latency, error rates, and active tasks
- **Generic Serialization**: All metrics and health data now export to JSON-serializable dictionaries
- **Data Point Categories**: View data point counts grouped by type (SWITCH, SENSOR, CLIMATE, etc.)
- **Improved Cache Metrics**: Clear distinction between true caches (with hit/miss) and trackers (size only)
- **Self-Healing Recovery**: Automatic data refresh after circuit breaker recovery
- **Hub Metrics Sensors**: Three HA-visible sensors for real-time system monitoring:
  - System Health (0-100%)
  - Connection Latency (ms)
  - Last Event Age (seconds since last CCU event)
- **RPC Monitoring**: Track success/failure rates, latency, and request coalescing effectiveness

### Connection Reliability

- **Improved Reconnection**: New state machine architecture for faster, more reliable recovery after CCU restarts
- **CircuitBreaker**: Automatic protection against repeated connection failures with staged reconnection
- **Reduced Log Noise**: Less ERROR logging during expected reconnection scenarios

### Device Management

- **Device Inbox**: Accept and rename new devices pending pairing directly from the integration
- **Install Mode**: Separate install mode control per interface (HmIP-RF and BidCos-RF) with countdown timer
- **Backup Support**: Create and download CCU system backups, firmware download and update triggers

### Climate & Schedules

- **Schedule Caching**: Faster schedule operations with intelligent caching
- **Simple Schedule Format**: Easier to read and modify weekly heating schedules
- **Schedule Sync**: Bidirectional get/set schedule operations with filtered data format

### Siren Control

- **Visible Alarm Settings**: Acoustic and optical alarm selection now available as controllable entities
- **Flexible Turn-On**: Siren activation uses entity values as defaults when service parameters omitted

### Bug Fixes

- **Device Creation Race Condition**: Fixed startup crash when CCU callback and initialization code raced
- **Resilient Channel Handling**: Devices remain functional even when some channel descriptions are missing
- **Cover/Dimmer Restart**: Fixed `is_valid` returning False after CCU restart when status is UNKNOWN
- **Empty Numeric Values**: Fixed conversion error when CCU sends empty strings for FLOAT/INTEGER parameters
- **RGBW/LSC Auto-Off**: Fixed lights turning off unexpectedly when using transition times
- **Reconnect Availability**: Entities no longer remain unavailable after CCU reconnect
- **STATUS Parameters**: Fixed handling of integer values from backend for status updates
- **Firmware Updates**: Fixed firmware data not refreshing after update check

### New Device Support

- **HmIP-MP3P Kombisignalgeber**: Sound player with MP3 playback (channel 2) and RGB LED control (channel 6)
- **HmIP-WRCD Text Display**: Wall-mount Remote Control with Display - send text, icons, colors, and sounds to the LCD
- DeviceProfileRegistry for centralized device-to-profile mappings
- DpActionSelect data point type for write-only selection parameters

### Developer Experience

- **Fluent Configuration**: New `CentralConfigBuilder` with method chaining and factory presets for CCU/Homegear
- **Request Tracing**: Context variables pattern for request tracking through async call chains with automatic log prefixing
- **Type Converters**: Extensible `to_homematic_value()` / `from_homematic_value()` using singledispatch pattern

### Internal Improvements

- Protocol-based architecture for better testability and decoupling
- Event bus system replacing legacy callback patterns
- Strict type checking throughout codebase
- Translatable log messages and exceptions
- Generic protocols for improved mypy type inference on data point values
- Declarative field descriptors for custom and calculated data points
- `DelegatedProperty` descriptor for simple property delegation with caching support
- Enhanced linter with DP004 path validation for DelegatedProperty definitions
- Store package restructured into `persistent/` and `dynamic/` subpackages for better maintainability
- Typed dataclasses (`CachedCommand`, `PongTracker`) replace untyped tuples and dicts
- Event-driven test patterns with `EventCapture` fixture for behavior verification through events
- Import standardization with `lint-package-imports` pre-commit hook enforcing package facade usage
- Package structure refactoring: Split large `__init__.py` files into dedicated modules
  - `central/coordinators/` subpackage for CacheCoordinator, ClientCoordinator, ConnectionRecoveryCoordinator, DeviceCoordinator, EventCoordinator, HubCoordinator
  - `central/events/` subpackage for EventBus, event types, and integration events
  - `client/ccu.py`, `client/config.py` for client classes
  - `model/hub/hub.py` for Hub orchestrator
- Export validation with `lint_all_exports.py` ensuring consistent `__all__` exports
- **Semantic Naming**: Renamed classes to reflect actual purpose
  - `CommandCache` → `CommandTracker` (tracks sent commands, not a cache)
  - `PingPongCache` → `PingPongTracker` (tracks connection health)
  - `*DescriptionCache` → `*DescriptionRegistry` (authoritative stores)
  - `ParameterVisibilityCache` → `ParameterVisibilityRegistry`
- **TrackerStatistics**: Dedicated statistics class for trackers (evictions only, no hit/miss)

# Version 1.90.2 (2025-11-05)

## What's Changed
- Bump aiohomematic to 2025.11.7
  - Add post_init_data_point_fields
  - Handle early arrival of pong events
  - Make ping pong handling more robust
  - Move on_link_peer_changed and refresh_link_peer_activity_sources to BaseCustomDpClimate
- Ensure hvac_action is None for devices without activity sources

# Version 1.90.0 (2025-11-04)

## What's Changed
- Bump aiohomematic to 2025.11.5
  - Add 'optional settings' config option
  - Add ELV-SH-PSMCI
  - Add dew point spread and enthalpy to calculated sensors
  - Add fallback to climate.activity to use linked channels, if own dps don't exist
  - Add link peer channel to channel
  - Add link_peer channels to device
  - Add pong_mismatch_allowed to ping pong event
  - Add session recorder
  - Ensure custom_ids are only used for external registrations
  - Fix issue after reconnect
  - Handle ping after ping success
  - Refactor PingPongCache
  - Refactor rpc handling
  - Remove link support for not linkable interfaces
  - Test support: Improve code/test coverage
  - Use enum for internal custom ids
  - Use generic DP DpDummy instead of NoneTypeDataPoint replacement
- Add 'optional settings' to config flow
- Add action for session recorder
- Add config flow migration for parameter renaming
- Adopt changes in friendly name of upnp discovery to OpenCCU
- Display hvac action for climate entities as off if device is off; display idle if no value exists
- Improve test coverage of core modules

# Version 1.89.1 (2025-10-10)

## What's Changed
- Bump aiohomematic to 2025.10.5
  - API cleanup: ensure that kw arguments are passed to the underlying function
  - Add Keyword-only method linter (mypy-style)
  - Add option to delay new device creation
  - Add source of device creation to callback
  - Fix issue with non existing PARENT in device description
- Add unknown_pong_mismatch notification
- Add option to config flow to delay new device creation

# Version 1.88.1 (2025-10-01)

## What's Changed
- Bump aiohomematic to 2025.10.1
  - Add option to cover entities that the current default behaviour can be disabled:
      - The default behaviour is, that the primary cover entity of a group uses the level of the state channel and no its own level to display a correct level.
      - Only HM experts should disable this option, that like to control all three writeable channels of a cover group. 
  - Add option to config flow for cover entities

# Version 1.88.0 (2025-10-01)

# This release requires HA 2025.10.0 or later.

## Info 

There is no longer any need to register Homematic(IP) Local for OpenCCU as a custom repository in HACS, as it is now registered directly with HACS. Existing HACS configurations will be migrated automatically (by HACS), so no further action is required.

## What's Changed
- Bump aiohomematic to 2025.10.0
  - Add CuXD parameters CMD_RETL and CMD_RETS to ignore list, to avoid warnings when reading the value without an appropriate configuration.
    - CMD_RETL warning: use CUX28010xx:16.CMD_QUERY_RET=1 to activate CUX28010xx:16.CMD_RETL command!
    - CMD_RETS warning: use CUX28010xx:16.CMD_QUERY_RET=1 to activate CUX28010xx:16.CMD_RETS command!
    - Add them to unignore if you are able to handle the warnings.
  - Fix device has_sub_devices
  - Fix magic method issue with log_context in xml_rpc client
  - Improve error message if service is not available
  - Re-/Store last manual temperature of climate entity
- Improve config_flow error messages
- Remove deprecation warning (The deprecated argument hass was passed to verify_domain_control) of Home Assistant 2025.10.0 for Homematic(IP local)
- Use of improved API for registering platform entity services from HA 

# Version 1.87.0 (2025-09-24)

## What's Changed
- Bump aiohomematic to 2025.9.4
  - Refactor CDP OperatingVoltageLevel
  - Refactor event method handling
  - Refactor decorators
    - Add log_context to @\*\_property
    - Add overloads to @\*\_property
    - Add overloads to @inspector
  - Add examples to naming documentation
  - Document how device, channel and data point names are created (docs/naming.md)
  - Remove dedicated @cached_property -> use @hm_property(cached=True) instead
  - Use dedicated loggers for event and performance logging
- Add HmIP-STV to tri_state
- Document how devices and entities are named (docs/naming.md); aligned with AIOhomematic docs
- Ignore unconfigured entries

# Version 1.86.0 (2025-09-02)

## What's Changed
- Bump aiohomematic to 2025.8.10
  - Improve documentation
    - Added docs/architecture.md describing high-level components (central, client, model, caches, support) and their interactions
    - Added data flow for XML-RPC/JSON-RPC, event handling, and data point updates
    - Added sequence diagrams for connect, device discovery, state change propagation
  - Add customization for HmIP-LSC
  - Avoid deadlocks within locks (cover)
  - Detailing the central status
  - Improve boundary logging und exception handling
  - Improve decorators
  - Improve fetch_all_device_data
  - Improve lock handling
  - Improve room assignment
  - Shield network I/O against cancellation
  - Validate custom datapoint definition on startup
- Fix area/room assignment with enabled sub devices
- Use greek small letter mu "\u03bc" instead of micro sign "\u00B5" for micro unit prefix

# Version 1.85.2 (2025-08-07)

## What's Changed
- Bump aiohomematic to 2025.8.6
  - Do not send additional parameter in kwargs for events
  - Small performance improvements
  - Rename hahomematic to aiohomematic
- Use parameter from datapoint for events
- Rename custom_homematic to homematicip_local
  
# Version 1.85.1 (2025-08-07)

## What's Changed
- Bump hahomematic to 2025.8.3
  - Simplify should_fire_data_point_updated_callback for calculated data points
  - Use slots

# Version 1.85.0 (2025-08-01)

## What's Changed
- Bump hahomematic to 2025.7.7
  - Add default customization for (Deleting of obsolete entities/device might be required):
    - ELV-SH-SW1-BAT, 
    - HmIP-WGT, HmIP-WGTC
    - HmIP-SMO230
  - Align exception naming
  - Enable OPERATING_VOLTAGE_LEVEL for HM-CC-RT-DN and HM-TC-IT-WM-W-EU
  - Fire updated events for calculated DPs when refreshed within a second
  - Refactor argument extraction from exceptions
  - Rename channel* to group* properties for cover, light and switch
- Check uniqueness of instance name
- Follow HA 2025.8: Use platform_data instead platform to avoid deprecation
- Remove version const for hahomematic dependency check

# Version 1.84.1 (2025-06-27)

## What's Changed
- Categorize diagnostic temperature sensors

# Version 1.84.0 (2025-06-17)

## What's Changed
- Bump hahomematic to 2025.6.0
  - Add CustomDP valve for ELV-SH-WSM / HmIP-WSM
  - Add batteries for ELV-SH-TACO
  - Add button_lock to HmIP-DLD
  - Add operating voltage level to ELV-SH-WSM / HmIP-WSM
  - Add state channel to sub_device_channel mapping
  - Enable ACTUAL_TEMPERATURE on maintenance channel
  - Improve identify ip address
  - Improve sub_device_channel identification
  - Wait with PING/PONG handling until interface is initialized
- Add valve platform
- Add option to use sub devices to config flow/advanced options
- Set suggested_display_precision for OPERATING_VOLTAGE to 1 

# Version 1.83.0 (2025-04-05)

## What's Changed
- Bump hahomematic to 2025.4.1
  - Limit text values to 255 characters
- Add add_link and remove_link to actions
- Add translation for HM-Sec-WDS states
- Add options to all enums

# Version 1.82.1 (2025-04-03)

## What's Changed
- Bump hahomematic to 2025.4.0
  - Create TLS context during module load

# Version 1.82.0 (2025-03-28)

## What's Changed
- Bump hahomematic to 2025.3.0
  - Add HmIP-FCI1 and HmIP-FCI6 to batteries
  - Add vapor concentration and dew point to all device channels that support temperature and humidity
  - Clear session on auth failure
  - Ensure load_data_point_value usage for initial load
  - Fix OperatingVoltageLevel attributes: low_bat_limit, low_bat_limit_default
  - Ignore model on initial load (HmIP-SWSD, HmIP-SWD)
  - Ignore parameters on initial load, if not already fetched by rega script (ERROR*, RSSI*, DUTY_CYCLE, DUTYCYCLE, LOW_BAT, LOWBAT, OPERATING_VOLTAGE)
  - Remove @cache and @lru_cache annotations
  - Use @cached_property for expensive, one time calculated properties
  - Use enums for const parameter values
  
# Version 1.81.2 (2025-02-05)

## What's Changed
- Bump hahomematic to 2025.2.5
  - Use value instead of default for low_bat_limit

# Version 1.81.1 (2025-02-05)

## What's Changed
- Bump hahomematic to 2025.2.3
  - Add calculated data points for HM devices
  - Catch JSONDecodeError on load/save cache files
  - Catch get_metadata XMLRPC fault
  - Ignore devices with unknown battery
  - Remove python 3.12 for github tests and pylint
  - Set battery to UNKNOWN for HmIP-PCBS-BAT
  - Sort battery list for correct wildcard search
  - Use py 3.14 for mypy and pylint
- Fix import from HA

# Version 1.80.0 (2025-01-30)

## What's Changed
- Bump hahomematic to 2025.2.0
  - Add calculated data points: 
    - ApparentTemperature
    - DewPoint
    - FrostPoint
    - OperatingVoltageLevel
    - VaporConcentration
  - Add config option to define the hm_master_poll_after_send_intervals
  - Add LOW_BAT_LIMIT
  - Add WEEK_PROGRAM_POINTER for bidcos climate devices
  - Add climate presets based on WEEK_PROGRAM_POINTER
  - Define schedule_channel_address for HM schedule usage
  - Don't read on unavailable devices
  - Enable schedule on hm thermostat
  - Fix usage of master dps for bidcos climate devices
  - Improve connection error handling
  - Poll master dp values 5s after send for bidcos devices
  - Refactor parameter_visibility
  - Rename paramset_key to paramset_key_or_link_address for put_paramset
  - Use temporary values where push is not supported
- Add support for CalculatedDataPoint
- Add translations to apparent_temperature

# Version 1.79.1 (2025-01-21)

## What's Changed
- Bump hahomematic to 2025.1.11
  - Cleanup cache file clear
  - Delay start of scheduler until devices are created
  - Rename instance_name to central_name
  - Slugify cache file name
- Compare keys against sysvar names with wildcards

# Version 1.79.0 (2025-01-17)

## What's Changed
- Bump hahomematic to 2025.1.10
  - Improve defaultdict usage
  - Load cached files as defaultdicts
  - Use Mapping instead of dict where possible
- Delete cache 
  - Fix a problem with new devices, due to an issue in 1.78.0
  
# Version 1.78.1 (2025-01-14)

## What's Changed
- Bump hahomematic to 2025.1.7
  - Fix KeyError on uninitialised dict

# Version 1.78.0 (2025-01-11)

## What's Changed
- Bump hahomematic to 2025.1.5
  - Consider heating value type when calculating hvac action
  - Fix issue with programs/sysvars on backend restart
  - Identify channel of a system variable if name ends with channel address
  - Refactor create\_\* methods:
  - Speedup wildcard lookup
- Add entity descriptions for (some statistics might be recalculated): 
  - svHmIPRainCounter*, svHmIPRainCounterToday*, svHmIPRainCounterYesterday*
  - svHmIPSunshineCounter*, svHmIPSunshineCounterToday*, vHmIPSunshineCounterYesterday*
  - svEnergyCounter*, svEnergyCounterFeedIn*
- Device related sysvars are now shown under the device instead of the hub

# Version 1.77.0 (2024-12-29)

## What's Changed
- Bump hahomematic to 2025.1.0
  - Remove get-/set_install_mode
- Add switch to toggle the state of CCU programs
- Remove action set_install_mode

# Version 1.76.1 (2024-12-27)

## What's Changed
- Bump hahomematic to 2024.12.13
  - Add program switch
- Fix double prefix for programs

# Version 1.76.0 (2024-12-27)

## Breaking changes

- Remove unignore file import 
  -> Use the UI option
- Rename marker for extended system variables from hahm to HAHM to better align with other markers
  -> Rename the marker in the sysvar description from hahm to HAHM

## What's Changed
- Bump hahomematic to 2024.12.12
  - Add periodic checks for device firmware updates
  - Ensure service and alarm messages are always displayed
  - Extend element_matches_key search
  - Fix remove last sysvar/program
  - Log debug if variable is too long
  - Refactor scheduler to use just one task
  - Remove default markers from description
  - Remove sv prefix from sysvar / p prefix from program
  - Remove unignore file import
  - Rename create methods
  - Rename marker for extended system variables from hahm to HAHM to better align with other markers
  - Start json_rpc client only for ccu
  - Support markers for sysvar/program selection
- Add advanced config options to define markers for programs and sysvars. 
  This means that not all programs/sysvars are retrieved except the internal ones.
- Fix warning `device_registry.async_get_or_create referencing a non existing via_device`
- Move periodic checks for device firmware updates to lib
- Reformat line length to 120
- Use existing config in config flow interface page

# Version 1.75.1 (2024-12-15)

## Noteworthy
- The repositories custom_homematic, hahomematic and pydevccu have been transferred from danielperna84 to sukramj
 - Old urls are automatically redirected

## What's Changed
- Remove danielperna84 from links after repository transfer to sukramj

# Version 1.75.0 (2024-12-15)
## Noteworthy
- Fixes issue with special characters in sysvar/program descriptions

## What's Changed
- Bump hahomematic to 2024.12.5
  - Add method cleanup_text_from_html_tags
  - Add missing encoding to unquote
  - Decode received sysvar/program descriptions
  - Ensure default encoding is ISO-8859-1 where needed
  - Limit number of concurrent mass operations to json api to 3 parallel executions
  - Replace special character replacement by simple UriEncode() method use by @jens-maus
  
# Version 1.74.0 (2024-12-10)

## New Features
- __Experimental__ support for CUxD and CCU-Jack devices
  - The default setup uses a 15s polling interval
  - Optional setup with MQTT for CuXD and CCU-Jack virtual Devices is possible to use push events.
  - Please read the docs for more information.
  - Please use the discussion forum for feedback

## What's Changed
- Bump hahomematic to 2024.12.2
  - Catch orjson.JSONDecodeError on faulthy json script response
  - Use kelvin instead of mireds for color temp
- Enable support for CuXD and CCU-Jack (15s polling interval)
- Enable MQTT support for CuXD, CCU-Jack and system variable refresh (MQTT is needed in CCU description)
- Return color temperature in kelvin

# Version 1.73.0 (2024-12-06)

## What's Changed
- Bump hahomematic to 2024.12.0
  - Add BidCos-Wired to list of primary interface candidates
  - Add TIME_OF_OPERATION to smoke detector
  - Add description to sysvar and program
  - Add description to sysvar and program
  - Enable central link management for HmIP-wired
  - Make sysvars eventable
  - Remove obsolete try/except in homegear client
  - Reset temporary values before write
  - Switch multiplier from int to float
  - Use more constants for cover and light
- Add action get_variable_value
- Add option to receive sysvar changes over mqtt
- Add translations for TIME_OF_OPERATION

# Version 1.72.0 (2024-11-21)

## What's Changed
- Bump hahomematic to 2024.11.8
  - Add missing @service annotations
  - Add performance measurement to @service
  - Don't re-raise exception on internal services
  - Move @service
  - Remove @service from abstract methods
- Expand list of unrecorded attributes

# Version 1.71.0 (2024-11-19)

## What's Changed
- Bump hahomematic to 2024.11.7
  - Add basic support for json clients
  - Add data_point_path event
  - Add getDeviceDescription, getParamsetDescription, listDevices, getValue, setValue, getParamset, putParamset to json_rpc
  - Add get_data_point_path to central
  - Add interface(id) to performance log message
  - Add interfaces_requiring_periodic_refresh to config
  - Add option to refresh data by interface
  - Add periodic data refresh to CentralUnitChecker for some interfaces
  - Add sysvar/program refresh to scheduler
  - Add xml_rpc support flag to client
  - Allow empty port for some interfaces
  - Do reconnect/reload only for affected interfaces
  - Extend DP_KEY with interface_id
  - Fix returned version of client
  - Ignore unknown interfaces
  - Improve store tmp value
  - Maintain data_cache by interface
  - Reduce MAX_CACHE_AGE to 15s
  - Remove clients for not available interfaces
  - Rename event to data_point_event
  - Run periodic tasks with an individual interval
  - Store temporary value for polling client data points
  - Store temporary value for sysvar data points
- Add mqtt support
- Add new option to UI (but disabled)
- Remove sysvar/program refresh from scheduler

# Version 1.70.0 (2024-11-06)

## What's Changed
- Bump hahomematic to 2024.11.0
  - Improve on_time usage
- Fix copy schedule 

# Version 1.69.0 (2024-10-27)

## What's Changed
- Bump hahomematic to 2024.10.17
  - Fire interface event, if data could not be fetched with script from CCU
  - Optimize MASTER data load
  - Rename model to better distinguish from HA
  - Use enum for json/event keys
- Add missing action icons
- Follow backend changes
- Use enum for services

# Version 1.68.1 (2024-10-26)

## What's Changed
- Bump hahomematic to 2024.10.14
  - Use version from module hahomematic
- Add check if Homematic(IP) Local for OpenCCU uses the expected version of hahomematic

# Version 1.68.0 (2024-10-24)

## What's Changed
- Bump hahomematic to 2024.10.13
  - Add central link methods to click event
  - Add create_central_links and remove_central_links to device and central
  - Add operation_mode to channel
  - Add reportValueUsage, addLink, removeLink and getLinks to client
  - Add version to code
  - Align method parameters with CCU
  - Check if channel has programs before deleting links
  - Disable climate temperature validation when turning off
  - Fix wrong channel assignment for HmIP-DRBLI4
  - Use PRESS_SHORT for reportValueUsage
- Add actions to manage central links

# Version 1.67.0 (2024-10-15)

## What's Changed
- Bump hahomematic to 2024.10.8
  - Add MIN_MAX_VALUE_NOT_RELEVANT_FOR_MANU_MODE, OPTIMUM_START_STOP and TEMPERATURE_OFFSET to climate
  - Add basic climate schedule services
  - Add config option for max read workers
  - Add services to copy climate schedules
  - Add simple climate schedule service to store profiles
  - Convert schedule time from minutes to hh:mm
  - Disable collector for stop events
  - Fix rx_mode lazy_config
  - Improve logging when raising exception
  - Improve profile validation
  - Log exception at the most outer service
  - Make DEFAULT and UPDATEABLE optional due to homegear support
  - Make validation for climate schedules optional
  - Move context var to own module
  - Raise exception on set_value, put_paramset
  - Remove command queue
  - Rename climate enums and constants to better distinguish from HA
  - Reuse existing dict types
  - Simplify entity imports
  - Use regex to identify schedule profiles
- Add action to fetch climate device schedule
- Add action to store climate device schedule (experimental)
- Add action to copy climate schedules
- Add option to config flow/advanced to listen on all ip addresses
- Add OPTIMUM_START_STOP and TEMPERATURE_OFFSET to climate attributes
- Fix issue with duplicate device addresses over multiple backends
- Raise HomeAssistantError on service exception
- Remove periodic master entity update
- Rename service to action in README.md

# Version 1.66.0 (2024-09-21)

## Breaking change:
- Use service put_link_paramset to manipulate direct connections
- Use service get_link_paramset to read direct connections
- Remove customization (it's not a pure dimmer) for ELV-SH-WUA / HmIP-WUA. Remove obsolete entities if necessary

## What's Changed
- Bump hahomematic to 2024.9.12
  - Add bind_collector to all relevant methods with option to disable it
  - Add config option for listen ip address and port
  - Add check for link paramsets
  - Add getLinkPeers XmlRPC method
  - Add missing PayloadMixin
  - Add name to channel
  - Add paramset_key to entity_key
  - Adjust payload and path
  - Avoid permanent cache save on remove device
  - Catch bind address errors of xml rpc server
  - Check rx_mode
  - Do not create update entities that are not updatable (manually remove obsolete update entities)
  - Ensure only one load/save of cache file at time
  - Identify bind_collector annotated methods
  - Improve paramset key check
  - Load all paramsets
  - Mark externally accessed services with service_call if bind_collector is not appropriate
  - Mark only level as relevant entity for DALI
  - Only try device update refresh if device is updatable
  - Refactor device/entity to extract channel
  - Refactor get_events, get_new_entities
  - Refactor update entity
  - Remove CED for ELV-SH-WUA / HmIP-WUA
  - Remove unnecessary checks
  - Rename value_property to state_property
  - Replace device_type by model
  - Separate enable/disable sysvar and program scan
  - Shorten names
  - Small definition fix for DALI
  - Switch typing of paramset_key from str to ParamsetKey
  - Use TypedDict for device_description
  - Use TypedDict for parameter_data
  - Use channel instead of channel_addresses
  - Use paramset_description from channel
  - Use validator for local schema
- Add advanced options to config flow
- Add option to enable/disable program scan to advanced options
- Add services get_link_peers, get_link_paramset, put_link_paramset
- Improve german descriptions by @baxxy13
- Use domain alias
- Use select for paramset_key with actions calls
- Use selector for rx_mode in service description

# Version 1.65.0 (2024-08-25)

- Bump hahomematic to 2024.8.13
    - Add CED for ELV-SH-WUA / HmIP-WUA
    - Add UN_IGNORE_WILDCARD to get_parameters
    - Add additional validation on config parameters
    - Avoid excessive memory usage in cache
    - Check/convert values of manual executed put_paramset/set_value
    - Cleanup DeviceDescriptionCache
    - Cleanup ParamsetDescriptionCache
    - Make HEATING_COOLING visible for thermostats
    - Make load only relevant paramset descriptions configurable
    - Refactor directory handling
    - Refactor get_parameters for unignore_candidates
    - Use only relevant IP for XmlRPC Server listening on
- Add HEATING_COOLING translations
- Clear cache on schema migration
- Keep optional values in config flow
- Load al paramset descriptions into cache
- Make unignore configurable in the UI
- Move mapping access to control config
- Refactor config flow. some options are now on the advanced page.
- Use SELECTORs in config flow
- Validate put_paramset/set_value against device descriptions
- Write optional parameters in Config Flow only when filled

# Version 1.64.0 (2024-08-05)

- Bump hahomematic to 2024.8.1
  - Add button lock CE
  - Reduce data load, if only device description is updated
  - Allow undefined generic entities besides CE
- Remove service delete_device. Use delete on the device entry instead
- Fix triggers and action when using meta integrations
- Add translation to button lock
- Add device class to RSSI

# Version 1.63.1 (2024-06-22)

- Use entry.runtime_data instead of hass.data
- Use HassKey for hass.data

# Version 1.63.0 (2024-06-03)

- Bump hahomematic to 2024.6.0
  - Fix address for bidcos wired virtual device
  - Catch TypeError on SysVar import
  - Add time units to HmIP-RGBW calls
- Add entity registry migration for fixed hmw entries

# Version 1.62.0 (2024-05-15)

- Bump hahomematic to 2024.5.4
  - Improve callback register/unregister
  - Move command_queue handling from device to channel
  - Add level sensors to cover/blind
  - Allow changing level or tilt while blind is moving by @sleiner
  - Fix value assignment to lock enums
  - Set open tilt level back to 100%
  - Use PEP 695 typing
  - Enable CE visible entities by default
- Add individual translations for LEVEL
- Adjust entity activation

# Version 1.61.0 (2024-05-05)

- Bump hahomematic to 2024.5.0
  - Make some items from value_property to property
  - Rename callbacks
  - Fix Homegear reconnect
  - Add COLOR_BEHAVIOUR to HmIP-BSL
- Ensure unload of platform services

# Version 1.60.1 (2024-04-26)

- Add missing parameter for set_cover_combined_position

# Version 1.60.0 (2024-04-24)

## Breaking change:

- tilt level is set to 50% to be open instead of 100%

## Changes:

- Bump hahomematic to 2024.4.12
  - Rename loop_safe to loop_check
  - Reduce loop_check to minimum
  - Update ruff rules / requirements
  - Make entity event async
  - Extract looper from central and reuse for json/xml_rpc
  - Move loop_check to async_support
  - Record last value send
  - Decompose combined parameter
  - Return affected entity keys for service calls
  - Add callback to unregister on register return
  - Add option to wait for set_value/put_paramset callback
  - Add wait_for_callback to collector
  - Wait for target value in wait_for_state_change_or_timeout
  - Add command queue
  - Move open/close from IpBlind to Blind
  - Use central_client_factory fixture
  - Ensure central.stop() is called in tests
  - Fix missing param in unregister_entity_updated_callback
  - Set open tilt level to 50%
- Add option to services to wait for set_value/put_paramset callback
- Add wait_for_callback to set_cover_combined_position

# Version 1.59.0 (2024-04-09)

- Bump hahomematic to 2024.4.6
  - Remove support for python 3.11
  - Use more list comprehension
  - Customize HmIP-DRG-DALI
  - Fix register refreshed entity
  - Refactor callback naming
  - Restructure check_connection
  - Make xml_rpc event async
  - Block central stop until tasks are finished
  - Unify entity update/refresh events
  - Remove unused callback from tests
  - Add loop_safe annotation
  - Remove entity_data_event_callback
  - Make system_event_callback loop aware
- Use more list comprehension
- Add icons to services
- Use ConfigFlowResult
- Use thread-safe method schedule_update_ha_state to write ha state
- Add missing callback annotations
- Add async prefix to callback annotated methods
- Move state classes from total to total_increasing

# Version 1.58.0 (2024-03-10)

- Bump hahomematic to 2024.3.1
  - Add additional parameter to HBW-LC4-IN4-DR
- Fix return zero value for sysvar number

# Version 1.57.1 (2024-03-05)

- Fix device_class for GAS_FLOW

# Version 1.57.0 (2024-03-01)

- Bump hahomematic to 2024.3.0
  - Add HBW-LC4-IN4-DR
- Remove unnecessary async
- Add GAS\_\* parameters of HmIP-ESI
- Avoid some HA deprecation warnings

# Version 1.56.0 (2024-02-15)

- Bump hahomematic to 2024.2.4
  - Add option to un ignore mechanism to ignore the automatic creation of custom entities by device type
  - Fix mapping for HBW-LC-RGBWW-IN6-DR
  - Fix mapping of HmIP-HDM
  - Group entities to sub devices / base channels
  - Add mapping for fixed color channel
  - Refactor entity name data

# Version 1.55.0 (2024-02-02)

- Bump hahomematic to 2024.2.1
  - Store old_value in entity model
  - Move product group identification to client
  - Add new pattern for unignore (parameter:paramset_key@device_type:channel_no)
  - Allow all as unignore parameter for device_type and channel_no
  - Remove old complex format for unignore
  - Remove deprecation warnings for py3.12
  - Fix/improve unignore search
  - Accept float as input for int numbers
- Use state_class total instead of total_increasing for sensors
- Add required ClimateEntityFeature TURN_OFF/TURN_ON for HA2024.2
- Replace icon_fn by icon translations for HA 2024.2
- Fix via_device in device_info

# Version 1.54.0 (2024-01-12)

- Bump hahomematic to 2024.1.7
  - Fix unignore doc and improve unignore tests
  - Move unignore check to entity
  - Reload master data after config pending event
  - Allow direct_call without cache wait time
- Remove whitespace from name end

# Version 1.53.0 (2024-01-09)

- Bump hahomematic to 2024.1.5
  - Add duration=111600 when ramp_time used for HmIP-RGBW
  - Allow ordered execution of collector paramsets
  - Only consider relevant entities for HmIP-RGBW
  - Remove effects from HmIP-RGBW when in PWM mode

# Version 1.52.0 (2023-12-19)

- Bump hahomematic to 2023.12.4
  - Add HB-LC-Bl1-Velux to cover
- Avoid mutating entity descriptions

# Version 1.51.0 (2023-12-17)

- Bump hahomematic to 2023.12.3
  - Save all rooms to entity model
  - Set attributes of dataclasses
  - Add another reason to ping pong mismatch
- Fix entity names without translations
- Add some descriptions to config flow

# Version 1.50.0 (2023-12-01)

- Bump hahomematic to 2023.12.1
  - Add support for away_mode and classic Homematic thermostats
  - Collect config validation errors
- Add validator to instance name (@ is not allowed)
- Use collected config validation errors
- Catch more generic connection exceptions

# Version 1.49.0 (2023-11-21)

- Bump hahomematic to 2023.11.4
  - Use last_refreshed for validation check
  - Improve ping/pong mechanism. Fire event, if mismatch is 15 within 5 Minutes

# Version 1.48.0 (2023-11-01)

- Bump hahomematic to 2023.10.14
  - Add class method default_platform
  - Cleanup cover
  - Fix service enable_away_mode_by_calendar
  - Rename fire events
  - Replace last_updated by last_refreshed
  - Switch formatting from black to ruff-format
- Add device address to device info

# Version 1.47.0 (2023-10-11)

- Bump hahomematic to 2023.10.12
  - Add filter options to device.get_entity\*
  - Align method signatures
  - Fix register_update_callback for update
  - Ignore switch to sensor if un ignored
  - Register external sources with custom identifier
  - Remove WrapperEntity
  - Remove get_update_entities
  - Remove subscribed_entity_unique_identifiers
  - Rename custom_identifier to custom_id
  - Rename unique_identifier to unique_id
  - Send relevant entities instead of devices in callback
  - Update un ignore documentation
- Improve typing within async_setup_entry
- Merge dicts to collect active entities
- Move statistics collection to diagnostics module
- Use backend methods instead of local wrappers
- Use filtering backend methods

# Version 1.46.0 (2023-10-10)

- Bump hahomematic to 2023.10.7
  - Adjust typing after move to more enums
  - Add measure_execution_time to writing methods
  - Fix send sysvar #1249
  - Add HmIPW-SCTHD

# Version 1.45.0 (2023-10-07)

- Bump hahomematic to 2023.10.6
  - Add started property to central
  - Rename:
    - value_list -> values
    - effect_list -> effects
  - Add more checks to get/set value from/tp values
  - Use more tuple instead of list
  - Cleanup code
  - Collect subscribed entities in central
  - Add faultCode and faultString to xmlrpc.client.Fault
  - Use Mapping/Set for readonly access
  - Use enum for CE fields
  - Use Parameter for ED
- Follow backend changes

# Version 1.44.1 (2023-10-04)

- Make default values configurable in ControlConfig

# Version 1.44.0 (2023-10-04)

- Bump hahomematic to 2023.10.4
  - Code cleanup
    - Remove Hm prefix from enums
    - Use enum for parameters
    - Use more existing constants
  - Use enum for JsonRPC and XmlRPC methods
  - Get supported JsonRPC and XmlRPC methods and check against used methods
  - Cleanup exception handling
  - Catch 'internal error' on get_auth_enabled. Relevant for for CCU2 users
- Follow backend changes
- Remove recorder platform
- Add test for recorder \_unrecorded_attributes

# Version 1.43.1 (2023-09-30)

- Bump hahomematic to 2023.9.8
  - Improve caching
    - Cleanup cache naming
    - Remove max_age from most method signatures
    - Simplify data cache
    - Rename some cache methods
  - Remove attr prefix

# Version 1.43.0 (2023-09-29)

- Bump hahomematic to 2023.9.7
  - Cleanup light code
  - Use more enums for climate, cover, lock
  - Use TypedDict for light, siren args
  - Update ReGa-Script fetch_all_device_data.fn by @Baxxy13
  - Parameterize call to fetch_all_device_data.fn
  - Simplify json rpc post code
  - Improve for ConnectionProblemIssuer json rpc
  - Improve handle_exception_log
  - Avoid repeated logs
  - Add check to BaseHomematicException
  - Reduce log level to 'warning' for get_all_device_data 'JSONDecodeError' exceptions
- Align isort setup with hass
- Remove recorder platform

# Version 1.42.0 (2023-09-22)

- Bump hahomematic to 2023.9.4
  - Re add channel 7 for HmIPW-WRC6
  - Reduce log level for exceptions in fetch_paramset_description
  - Refactor get_paramset_description
  - Filter SSLErrors by code
  - Cleanup logger
  - Refactor client and central modules
- Adopt changes in HA 2023.9
- Use more shorthand attributes
- Add \_unrecorded_attributes

# Version 1.41.0 (2023-09-03)

- Bump hahomematic to 2023.8.3 - 2023.9.0
  - Add SSLError to XmlRpcProxy and JsonRpcAioHttpClient
  - Add decorator to measure function execution time
  - Add ping pong tests
  - Align sslcontext creation with Home Assistant
  - Convert StrEnum and IntEnum in proxy
  - Extend HmIPW-WRC6 implementation
  - Fix get_all_system_variables return value
  - Improve testing
  - Make integration more robust against json result failures
  - Make start_direct a config option
  - Optimize get readable entities for MASTER
  - Reduce visibility of local constants
  - Refactor cover api
  - Refactor to more enum usage
  - Remove obsolete comments
  - Remove use_caches and load_un_ignore from central config
  - Restructure test helper
  - Update project setup
- Improve custom component testing
  - Add Github flows for pylint and tests
  - Add infrastructure for platform tests
  - Increase config flow coverage
  - Make Homematic entities mockable
- Avoid init_central
- Cleanup scheduler code
- Increase master scan interval to 1h
- Make tilt_postion optional for set_cover_combined_position
- Rename some methods for consistency

# Version 1.40.1 (2023-08-06)

- Bump hahomematic to 2023.8.1
  - Prepare backend for HA issue usage
- Bump hahomematic to 2023.8.2
  - Improve exception and log handling
- Fix DE service name translation
- Use issues instead of persistent notifications for interface events

# Version 1.40.0 (2023-07-29)

- Bump hahomematic to 2023.7.4
  - Add identifier to device
  - Rename ENTITY_NO_CREATE to NO_CREATE
  - Ignore click events on plugs
- Bump hahomematic to 2023.7.5
  - Add SystemInformation to client api
  - Send credentials on XmlRPC api only when authentication is enabled in CCU
- Bump hahomematic to 2023.7.6
  - Refactor Json error handling / logging
  - Use ping pong only for CCU
- Bump hahomematic to 2023.8.0
  - Remove only the starting device name from entity name
  - Remove title from program and sysvar names
- Remove support for python 3.10
- Add available_interfaces to SystemInformation
- Use identifier from device
- Add event entities
- Remove unmaintained NL translation
- Add service translations
- Remove click_events from logbook
- Add SystemInformation to diagnostics

# Version 1.39.2 (2023-07-13)

- Bump hahomematic to 2023.7.3
  - Fire interface event about ping/pong mismatch
  - Add message to fire_interface_event
- Refactor event usage
- Add option to config flow to control system notifications (controls CALLBACK and PINGPONG notifications)

# Version 1.39.1 (2023-07-12)

- Bump hahomematic to 2023.7.1
  - Log an error about the ping/pong count mismatch
- Bump hahomematic to 2023.7.2
  - Add new Events PRESS_LOCK and PRESS_UNLOCK for HmIP-WKP
- Add entity descriptions and translations for HmIP-WKP

# Version 1.39.0 (2023-07-07)

- Bump hahomematic to 2023.7.0
  - Project file maintenance
- Add services that return data:
  - get_device_value
  - get_paramset
- Fix entity state translations

# Version 1.38.0 (2023-07-02)

- Guard against failure due to future HA api changes related to CC specific usage
- Make entity name translation more verbose

# Version 1.37.6 (2023-06-29)

- Fix error with names before HA 2023.7 pt2

# Version 1.37.5 (2023-06-29)

- Fix error with names before HA 2023.7

# Version 1.37.4 (2023-06-23)

- Bump hahomematic to 2023.6.1
  - Fix tunable white support for hmIP-RGBW
  - Avoid creating entities that are not usable in selected device operation mode for hmIP-RGBW
  - Update requirements
- Add missing comma, to fix entity description
- Remove device class from percentage entity description

# Version 1.37.3 (2023-06-02)

- Bump hahomematic to 2023.6.0
  - Update requirements
  - Do not create update entities for virtual remotes
  - Cleanup FIX_UNIT_BY_PARAM
- Fix latest version of update entity
- Use VALVE_STATE entity description only for Bidcos devices

# Version 1.37.1 (2023-05-26)

- Display updates only if update is ready for installation on device

# Version 1.37.0 (2023-05-15)

- Bump hahomematic to 2023.5.2
  - Refactor device description cache handling
  - Add device firmware update handling
- Add device firmware update entity
- Add 'Update device firmware data' service
- Add 6h schedule for device firmware data refresh
- Avoid overriding hostname by ssdp data

# Version 1.36.0 (2023-05-01)

- Bump hahomematic to 2023.5.0
  - Remove unsupported on_time / refactor HmIP-RGBW

# Version 1.35.0 (2023-04-28)

- Bump hahomematic to 2023.4.5
  - Update requirements
  - Add HmIP-RGBW
- Fix supported_color_modes for light

# Version 1.34.2 (2023-04-24)

- Bump hahomematic to 2023.4.2
  - Update requirements
  - Fix cover (HDM2) no longer working

# Version 1.34.1 (2023-04-16)

- Bump hahomematic to 2023.4.0
  - Update requirements
  - Add log message to negative password check
- Use positional args
- Fix `Cannot parse hex-string value`

# Version 1.34.0 (2023-04-05)

### New features

- Add service "set cover combined position"
- Add name translation

### All changes:

- Bump hahomematic to 2023.3.1
  - Add name to tasks
  - Improve typing
  - Move callback calls into exception block
  - Remove avoidable usage of deepcopy
  - Add dependabot
  - Update requirements
  - Drop pyupgrade, autoflake, flake8 in favor of ruff
  - Refactor cover, add set_combined_position
- Update minimum required version
- Add service "set cover combined position"
- Add name translation

# Version 1.33.1 (2023-03-03)

### All changes:

- Bump hahomematic to 2023.3.0
  - Update ruff, adjust module aliases
  - Fix spamming CCU logs with errors (#981)
- Fix import
- Update minimum required version

# Version 1.33.0 (2023-02-26)

### All changes:

- Bump hahomematic to 2023.2.11
  - Update ruff, fix comments
  - Switch to orjson
  - Fix climate: compare set temperature to target temperature

# Version 1.32.0 (2023-02-23)

## Breaking change

-Remove `set_device_value_raw`: use `set_device_value` instead (See changelog release 1.27.1)

### New features

- Enable HmIP-SMSD as siren

### All changes:

- Bump hahomematic to 2023.2.10

  - Use sets for central callbacks
  - Add get_all_entities for device

- Enable HmIP-SMSD as siren
- Add pre-commit checks and cleanup repo
- Remove set_device_value_raw

# Version 1.31.0 (2023-02-18)

### New features

### All changes:

- Bump hahomematic to 2023.2.9
  - Fix property types
  - Ensure modules for platforms are loaded
  - Use local dicts for device lists
  - Clear central data cache if identified as outdated
  - Avoid redundant cache loads within init phase
  - Extract value preparation from send_value
  - Differentiate between input and default parameter type
  - Fix asyncio-dangling-task (RUF006)
- Add typed dict for light and siren
- Bump hahomematic to 2023.2.8
  - Add project setup script
  - Add entity_data event
  - Add payload mixin
  - Cleanup module dependencies
  - Use cache decorators for some high-traffic methods
  - Allow that channel_no could be None
  - Add and use get_channel_address
  - Add `HmIP-SWSD` as siren
- Add device_class to doorbell if binary behavior is set
- Align packages to backend lib
- Align to siren backend changes
- Used typed dicts for light and siren
- Update translation keys

# Version 1.30.2 (2023-02-08)

### All changes:

- Remove `native_precision` for Concentration of HmIP-SCTH230

This change is necessary because `native_precision` has been swapped for `suggested_display_precision` without a deprecation period in the HA core. Before switching to HA 2023.3, **all** CC users who use version 1.28.0 (or greater) must therefore update.
Rounding support for Concentration of HmIP-SCTH230 will be re-added with HA 2023.3

# Version 1.30.1 (2023-02-08)

### New features

### All changes:

- Bump hahomematic to 2023.2.7
  - Disable validation of state change for action and button
  - Check if entity is writable on send

# Version 1.30.0 (2023-02-07)

### New features

### All changes:

- Bump hahomematic to 2023.2.6
  - Add missing bind_collector
  - Add more `Final` typing
  - Add option to collector to disable put_paramset
  - Add on_time Mixin to temporary store on_time
- Align to backend lib

# Version 1.29.0 (2023-02-06)

### New features

- Add virtual channels for HmIP cover/blind

### All changes:

- Bump hahomematic to 2023.2.5
  - Add comments to parameter_visibility
  - Use `put_paramset` only when there is more than one parameter to sent
  - Use only one implementation for garage doors (HO/TM)
  - Avoid backend calls if value/state doesn't change
    - If an entity (e.g. `switch`) has only **one** parameter that represents its state, then a call to the backend will be made,
      if the parameter value sent is not identical to the current state.
    - If an entity (e.g. `cover`, `climate`, `light`) has **multiple** parameters that represent its state, then a call to the backend will be made,
      if one of these parameter values sent is not identical to its current state.
    - Not covered by this approach:
      - platforms: lock and siren.
      - services: `stop_cover`, `stop_cover_tilt`, `enable_away_mode_*`, `disable_away_mode`, `set_on_time_value`
      - system variables
  - Add virtual channels for HmIP cover/blind:
    - Channel no as examples from HmIP-BROLL. The implementation of the first actor channel (4) remains unchanged, which means that this channel (4) shows the correct cover position from sensor channel (3).
      The other actor channels (5+6) are generated as initially deactivated and only use the cover position from their own channel after activation.
- Fix channel 0 not working for put_paramset

# Version 1.28.0 (2023-02-01)

### All changes:

- Bump hahomematic to 2023.2.1
  - Separate check for parameter is un_ignored based on if it should be hidden or not
- Bump hahomematic to 2023.2.0
  - Log validation exceptions in central
  - Add typing to decorators
- Bump hahomematic to 2023.1.8
  - Ensure the signal handler gets called at most once by @mtdcr
  - Fix stop central, if another central is active on the same XmlRPC server
  - JsonRpcAioHttpClient: Allow empty password by @mtdcr
  - Remove `VALVE_STATE` from HmIPW-FALMOT-C12
  - Remove put_paramset from custom_entity
  - Remove set_value, put_paramset from central
  - Remove support for python 3.9
  - Remove to int converter for HmIP-SCTH230 `CONCENTRATION`
  - Replace old-style union syntax
  - Validate password with regex (warning only!)
- Add `native_precision` (=0) for `CONCENTRATION`
- Check password on config flow validation
- Limit services to own integration
- Replace old-style union syntax
- Use exception types from backend
- Use kwargs in callbacks

# Version 1.27.2 (2023-01-26)

### All changes:

- Remove device class `GAS` from GAS_POWER (limitation of HA)
- Replace `async_setup_platforms` by `async_forward_entry_setups` in `__init__.py`
- Fix put_paramset for HM MASTER paramset

# Version 1.27.1 (2023-01-XX)

### New features

- Add additional parameter `device_address` to services

### All changes:

- Bump hahomematic to 2023.1.7
  - Add a new custom entity type for windows drive
  - Return True if sending service calls succeed
  - Aggregate calls to backend
  - Fix HmIP-MOD-TM: inverted direction
- Add additional parameter `device_address` to services:
  - `force_device_availability`
  - `set_device_value`
  - `put_paramset`
- Deprecate service `set_device_value_raw`. Will be removed with HA 2023-03. Seitch to service `set_device_value` instead.
- Follow garage changes from backend

# Version 1.27.0 (2023-01-20)

### New features

- Add LED_STATUS to HM-OU-LED16

### All changes:

- Bump hahomematic to 2023.1.5
  - Remove LOWBAT from HM-LC-Sw1-DR
  - Sort lists in parameter_visibility.py
  - Replace custom entity config data structure by CustomConfig
  - Allow multiple CustomConfigs for a hm device
  - Add ExtendedConfig to custom entities
  - Cleanup test imports
  - Increase the line length to 99
  - Add ExtendedConfig and use for additional_entities
  - Remove obsolete ED_ADDITIONAL_ENTITIES_BY_DEVICE_TYPE from entity_definition
  - Add LED_STATUS to HM-OU-LED16
- Fix: SysVars enabled (should be disabled) on initial setup
- Add model and version to service information
- Remove duplicate logbook entry for device_availability
- Use old value of SYSVAR_SCAN_ENABLED in options flow

# Version 1.26.5 (2023-01-16)

- Fix display of logbook events

# Version 1.26.4 (2023-01-16)

### New features

- Update color_conversion threshold (HmIP-BSL) by @guillempages

### All changes:

- Bump hahomematic to 2023.1.4
  - Remove obsolete parse_ccu_sys_var
  - Add helper, central tests
  - Add more tests and test based refactorings
  - Reduce backend calls and logging during lost connection
  - Update color_conversion threshold by @guillempages
- Fix name in homematic.key_press events

# Version 1.26.2 (2023-01-13)

### New features

- Add device availability and error to logbook

### All changes:

- Bump hahomematic to 2023.1.3
  - Unify event parameters
  - Refactor entity.py for better event support
  - Fix wrong warning after set_system_variable
  - Add validation to event_data
- Reassign event parameters in control_unit
- Add device availability and error to logbook

# Version 1.26.1 (2023-01-09)

### New features

- Remove LOWBAT from HM-LC-Sw1-Pl, HM-LC-Sw2-FM
- Remove OPERATING_VOLTAGE from HmIP-BROLL, HmIP-FROLL
- Use actions and buttons for device actions

### All changes:

- Bump hahomematic to 2023.1.2
  - No longer create ClientSession in json_rpc_client for tests
  - Add backend tests
  - Use mocked local client to check method_calls
  - Remove sleep after connection_checker stops
  - Remove LOWBAT from HM-LC-Sw1-Pl, HM-LC-Sw2-FM
  - Simplify entity de-/registration
  - Refactor add/delete device and add tests
  - Add un_ignore_list to test config
  - Allow unignore for DEVICE_ERROR_EVENTS
  - Remove OPERATING_VOLTAGE from HmIP-BROLL, HmIP-FROLL
  - Remove loop from test signature
  - Cleanup ignore/unignore handling and add tests
- Move delete device logic to central
- Use actions and buttons for device actions

# Version 1.26.0 (2023-01-02)

## This release requires HA >= 2023.1

### Breaking changes

- Rename climate presets from 'Profile _' to 'week*program*_':
  HA now allows translations of custom preset modes. The internal preset mode has been renamed from 'Profile _' to 'week*program*_'.
  If service climate.set_preset_mode was used with values like "Proflle 1", these automations and scripts need to be edited and use "week_program_1" instead.
  This preset mode is now displayed as "WP 1" to better accommodate the available space in the UI.

### New features

- Make sysvar_scan_interval configurable
  The integration can now be reconfigured to use a shorter or longer interval between sysvar scans. The sysvar scan can also be disabled, if not needed.

### All changes:

- Bump hahomematic to 2023.1.0
  - Remove empty unit for numeric sysvars
  - Fix native device units
  - Rename climate presets from 'Profile _' to 'week*program*_'
  - Add un_ignore list to central config
  - Fix entity_definition schema
  - Rename cache_dict to persistent_cache
  - Reduce access to internal complex objects for custom_component
  - Allow to disable cache
  - Allow to disable un_ignore load
  - Add local client
  - Use local client in tests
  - Move event() code to central_unit
  - Move listDevices() code to central_unit
- Align custom_component to HA 2023.01
  - Align translations to new schema
  - Remove wrong device_classes
  - Use more UnitOf enums
  - Add options for enum sensors. Makes state values selectable in triggers.
- Reformat code / check with flake 8
- Add SensorStateClass.TOTAL*INCREASING to svEnergyCounter*\* sysvars
- Add SensorStateClass.MEASUREMENT to numeric sysvars
- Add SwitchDeviceClass.OUTLET to HmIP plugs
- Reorg entity helper
- Make sysvar_scan_interval configurable

# Version 1.25.1 (2022-12-22)

- Bump hahomematic to 2022.12.8
  - Reformat code
  - Refactor entity inheritance
- Follow backend: Refactor entity inheritance
- Add value_list to sensor attributes

# Version 1.25.0 (2022-12-21)

- Bump hahomematic to 2022.12.7
  - Send ERROR\_\* parameters as homematic.device_error event
- Fire homematic.device_error event
- Add blueprint to display device error as persistent notification

# Version 1.24.4 (2022-12-20)

- Bump hahomematic to 2022.12.6
  - Add additional checks for custom entities
- Fix entity_helper for LEVEL

# Version 1.24.3 (2022-12-18)

- Bump hahomematic to 2022.12.5
  - Code Cleanup
  - Remove sub_type from model to simplify code
  - Remove obsolete methods
  - Refactor binary_sensor check
  - Convert value_list to tuple
  - Use tuple for immutable lists
- Remove sub_types for device selection
- Convert frozenset to tuple in entity helper
- Use device class tamper for sabotage parameter

# Version 1.24.2 (2022-12-13)

- Bump hahomematic to 2022.12.4
  - Fix disable away_mode in climate. Now goes back to the origin control_mode.
- Add start date and time for service homematicip_local.enable_away_mode_by_calendar and use date and time pickers

# Version 1.24.1 (2022-12-12)

- Bump hahomematic to 2022.12.3
  - Add separate off_temperature for HM heating group HM-CC-VG-1

# Version 1.24.0 (2022-12-12)

- Bump hahomematic to 2022.12.2
  - Add HM-LC-AO-SM as light
- Change device_class of weather wind speed sensor to new device class wind_speed
- Remove hub sensor

- Breaking Changes:
  - Due to changes in HA, the following services now have to use config entry_id (selectable in UI) instead of hub sensor:
    - clear_cache
    - fetch_system_variables
    - set_variable_value
  - The number of service messages is now a sysvar, due to the removal of the hub sensor
  - Replace bluepring homematicip_local_persistent_notification.yaml by current version
    - selection of hub sensor no longer needed

# Version 1.23.0 (2022-12-01)

- Bump hahomematic to 2022.12.1
  - Improve naming of modules
  - Add new platform for text sysvars
- Remove support for old hub entities with homematicip_local.\*
- Raise min HA # Version to 2022.12
- Use EntityFeature return type for climate/light supported features
- Add text platform for character string sysvars (extended). See docs.

# Version 1.22.0 (2022-12-01)

- Bump hahomematic to 2022.12.0
  - Add transition to light turn_off
  - Remove min brightness of 10 for lights
- Raise hour limit for away mode to 999 hours
- Add multiplier 100 to LEVEL

# Version 1.21.3 (2022-11-13)

- Bump hahomematic to 2022.11.2
  - Generalize some collection helpers
- Rename attribute COLOR_NAME to COLOR

# Version 1.21.2 (2022-11-09)

- Simplify # Version check
- Switch LEVEL sensor on creation from hidden to deactivated

# Version 1.21.1 (2022-11-08)

- hide LEVEL sensor on creation

# Version 1.21.0 (2022-11-08)

- Bump hahomematic to 2022.11.1
  - Use generic property implementation
  - Code cleanup
  - Add option to wrap entities to a different platform
  - Wrap LEVEL of HmIP-TRV\*, HmIP-HEATING to sensor
- Use UnitOf\* enums
- Add EntityDescription for LEVEL of HmIP-TRV\*, HmIP-HEATING as sensor
- Make async_signal_new_hm_entity a function

# Version 1.20.1 (2022-10-25)

- Bump hahomematic to 2022.10.10
  - Refactor central_config
- Allow update of min/max temp of climate device
- Code cleanup

# Version 1.20.0 (2022-10-23)

- Bump hahomematic to 2022.10.9
  - Fix: don't hide unignored parameters
- Refactor MASTER polling

# Version 1.19.9 (2022-10-22)

- Add generic option to modify icon based on state

# Version 1.19.8 (2022-10-21)

- Bump hahomematic to 2022.10.8
  - Add semaphore to fetch sysvar and programs from backend
- Add service to fetch system variables on demand from backend independent from default 30s schedule.

# Version 1.19.7 (2022-10-20)

- Bump hahomematic to 2022.10.7
  - Accept some existing prefix for sysvars and programs to avoid additional prefixing
  - Read min/max temperature for climate devices
  - Min set temperature for thermostats is now 5.0 degree. 4.5. degree is only off

# Version 1.19.6 (2022-10-15)

- Bump hahomematic to 2022.10.6
  - Use HmHvacMode HEAT instead of AUTO for simple thermostats
  - Add HUMIDITY and ACTUAL_TEMPERATURE to heating groups

# Version 1.19.5 (2022-10-11)

- Bump hahomematic to 2022.10.5
  - Set HM Thermostat to manual mode before switching off

# Version 1.19.4 (2022-10-10)

- Bump hahomematic to 2022.10.4
  - Allow entity creation for some internal parameters

# Version 1.19.3 (2022-10-10)

- Bump hahomematic to 2022.10.3
  - Fix HM Blind/Cover custom entity types

# Version 1.19.2 (2022-10-08)

- Bump hahomematic to 2022.10.2
  - Make connection checker more resilient

# Version 1.19.1 (2022-10-07)

- Simplify manufacturer selection

# Version 1.19.0 (2022-10-07)

- Bump hahomematic to 2022.10.1
  - Ignore OPERATING_VOLTAGE for HmIP-PMFS
  - Add ALPHA-IP-RBG
- Differentiate manufacturer in device_info
- Use device_class speed

# Version 1.18.1 (2022-10-04)

- Update state translations
- Add warning if hub sensor is disabled
- Avoid hub sensor update before full initialized

# Version 1.18.0 (2022-10-03)

- Bump hahomematic to 2022.10.0
  - Rename hub event
  - Remove Servicemeldungen from sysvars. It's already included in the hub_entity (sensor.{instance_name}) (See README)
- Split hub between scheduler and entity
- Convert hub entity to sensor
- Reorg device_info for ControlUnit
- Deprecation warning: The entity homematicip_local.{instance_name} must be replaced by sensor.{instance_name} in service calls (set_variable_value) till HA 11.2022.

# Version 1.17.0 (2022-09-20)

- Bump hahomematic to 2022.9.1
  - Improve XmlServer shutdown
  - Add name to threads and executors
  - Improve ThreadPoolExecutor shutdown
- Replace deprecated AutomationActionType

# Version 1.16.5 (2022-09-02)

- Add blueprint for HB-RC-12-EP-C by @djusHa
- Fix sysvar binary_sensors

# Version 1.16.4 (2022-09-02)

- Bump hahomematic to 2022.9.0
  - Exclude value from event_data if None
- Remove unneeded \_attr

# Version 1.16.3 (2022-08-27)

- Bump hahomematic to 2022.8.15
  - Fix select entity detection

# Version 1.16.2 (2022-08-24)

- Fix targets for entity services

# Version 1.16.1 (2022-08-24)

- Bump hahomematic to 2022.8.14
  - Exclude STRING sysvar from extended check
- Improve # Version check

# Version 1.16.0 (2022-08-23)

- Bump hahomematic to 2022.8.13
  - Allow three states for a forced availability of a device
- Fix device availability wording
- Fix wording in homematicip_local_persistent_notification.yaml
- Added blueprints:
  - homematicip_local_reactivate_device_by_type.yaml - Reactivate a device by device type
  - homematicip_local_reactivate_device_full.yaml - Reactivate every device
  - homematicip_local_reactivate_single_device.yaml - Reactivate a single device

# Version 1.15.2 (2022-08-23)

- Bump hahomematic to 2022.8.12
- Add device_type to device availability event

# Version 1.15.1 (2022-08-21)

- Bump hahomematic to 2022.8.11
- Adjust logging (level and message)
- Remove service homematicip_local.update_entity. Use service homeassistant.update_entity instead.

# Version 1.15.0 (2022-08-16)

- Bump hahomematic to 2022.8.10
- Add click events to logbook

# Version 1.14.3 (2022-08-16)

- Bump hahomematic to 2022.8.9
  - Create all XmlRpc server by requested port(s)
- Use a default callback port if not configured
- Restructure hass storage of control units

# Version 1.14.2 (2022-08-12)

- Bump hahomematic to 2022.8.7
  - Fix hs_color for CeColorDimmer(HM-LC-RGBW-WM)

# Version 1.14.1 (2022-08-12)

- Bump hahomematic to 2022.8.6
  - Reduce api calls for light
  - Fix color for HM-LC-RGBW-WM

# Version 1.14.0 (2022-08-11)

- Bump hahomematic to 2022.8.5
  - Add cache for rega script files

# Version 1.13.7 (2022-08-11)

- Cleanup entity_helper

# Version 1.13.6 (2022-08-11)

- Fix entity_helper after #286

# Version 1.13.5 (2022-08-11)

- Refactor service set_device_valueXXX

# Version 1.13.4 (2022-08-09)

- Add entity_description for HB percentage and pressure
- Add service set_device_value_raw

# Version 1.13.3 (2022-08-08)

- Bump hahomematic to 2022.8.4
  - Add platform as field and remove obsolete constructors

# Version 1.13.2 (2022-08-07)

- Bump hahomematic to 2022.8.3
  - Rename HM unique_id to unique_identifier
  - Remove domain from model
  - Remove should_poll from model
- Refactor entity_description handling
- Specify should_poll in CC

# Version 1.13.1 (2022-08-02)

- Bump hahomematic to 2022.8.2
  - Code cleanup
  - Add program buttons
- Add Service to update a single entity's value (only required for edge cases). See README.
- Add CCU programs as buttons

# Version 1.13.0 (2022-08-01)

- Bump hahomematic to 2022.8.0
  - Remove device_info from model
  - Remove attributes from model
  - Code Cleanup
- Refactor DeviceInfo
- Refactor Attributes

# Version 1.12.5 (2022-07-28)

- Bump hahomematic to 2022.7.14
  - Add HmIP-BS2 to custom entities
- Add call_source to load_entity_value calls

# Version 1.12.4 (2022-07-22)

- Bump hahomematic to 2022.7.13
  - Cleanup API
- Clean up accessing event helpers via hass
- Remove empty device_class for binary_sensor STATE

# Version 1.12.3 (2022-07-21)

- Bump hahomematic to 2022.7.12
  - Add ELV-SH-BS2 to custom entities
- Remove unneeded validity check for color_mode

# Version 1.12.2 (2022-07-21)

- Block start of custom component if HA # Version is too old.

# Version 1.12.1 (2022-07-19)

- Bump hahomematic to 2022.7.11
  - Fix \_check_connection for Homegear/CCU
- Add community blueprint for 4-button flush mount device by @andyboeh
- Add HVACAction.IDLE to dict

# Version 1.12.0 (2022-07-17)

- Bump hahomematic to 2022.7.9
  - Remove state_uncertain from default attributes
- Make entity state restorable after HA restart
- Do not use CALLBACK_HOST for XmRPCServer

# Version 1.11.1 (2022-07-13)

- Bump hahomematic to 2022.7.8
  - Fix entity update

# Version 1.11.0 (2022-07-12)

- Bump hahomematic to 2022.7.7
  - Ignore further parameters by device (CURRENT_ILLUMINATION for HmIP-SMI, HmIP-SMO, HmIP-SPI)
  - Align entity naming to HA entity name
- Use new HA entity name:
  The entity name now only represents the entity part, and no longer includes the device name.
  The entity_id is untouched, as long as you don't reinstall the integration.
  The displayed name of an entity might change, depending on the used HA card.
  See [HA dev docs](https://developers.home-assistant.io/docs/core/entity#has_entity_name-true-mandatory-for-new-integrations) for further information
- Fix hub creation
- Use entity is_valid for state
  Entities are now shown as unknown, as long as HA has not received any events from the CCU, or was not able to fetch data initially.
  Old behaviour was to display a DEFAULT value.
  As soon as events have been received from the CCU the state will switch to the correct state.
  This should be relevant, if HA has been restarted shortly after the CCU has been restart.
  See [Readme](https://github.com/sukramj/homematicip_local#noteworthy-about-entity-states) for further information.
- Add attribute state_uncertain
  There is now an extra attribute at each entity, that shows is the state of the entity might be uncertain due to a CCU restart.
  This should be relevant, if the CCU has been restarted and HA is still running.

# Version 1.10.1 (2022-07-08)

- Bump hahomematic to 2022.7.1
  - Better distinguish between NO_CACHE_ENTRY and None

# Version 1.10.0 (2022-07-07)

- Bump hahomematic to 2022.7.0
- Fix/Cleanup Device/Entity/Sysvar removal
- Use new attributes for number entities

# Version 1.9.5 (2022-07-06)

- Revert: Make OPENING the default device_class for binary_sensor STATE (#249)

# Version 1.9.4 (2022-07-03)

- Bump hahomematic to 1.9.4
  - Load MASTER data on initial load
- Make OPENING the default device_class for binary_sensor STATE

# Version 1.9.3 (2022-07-02)

- Bump hahomematic to 1.9.3
  - Fix export of device definitions

# Version 1.9.2 (2022-07-01)

- Bump hahomematic to 1.9.2
  - Use CHANNEL_OPERATION_MODE for devices with MULTI_MODE_INPUT_TRANSMITTER, KEY_TRANSCEIVER channels
  - Re-add HmIPW-FIO6 to custom device handling
- Disable device trigger based on event usage

# Version 1.9.0 (2022-06-29)

- Bump hahomematic to 1.9.1
  - Add button to virtual remote
  - Remove HmIPW-FIO6 from custom device handling
- Remove dummies for unit_of_measurement

# Version 1.8.6 (2022-06-07)

- Bump hahomematic to 1.8.6
  - Code cleanup
- Fix sysvar creation for delayed platform setups on some environments

# Version 1.8.5 (2022-06-05)

- Bump hahomematic to 1.8.5
  - Remove sysvars if deleted from CCU
  - Add check for sysvar type in sensor
  - Remove unused sysvar attributes
- Cleanup HA when deleting sysvars

# Version 1.8.4 (2022-06-04)

- Bump hahomematic to 1.8.4
  - Refactor all sysvar script

# Version 1.8.3 (2022-06-03)

- Bump hahomematic to 1.8.3
  - Refactor sysvar creation eventing
- Adopt sysvar creation eventing

# Version 1.8.2 (2022-06-03)

- Bump hahomematic to 1.8.2
  - Fix build

# Version 1.8.1 (2022-06-03)

- Bump hahomematic to 1.8.1
  - Use Marker in sysvar description for extended sysvars

# Version 1.8.0 (2022-06-02)

- Bump hahomematic to 1.8.0
  - Enable additional sysvar entity types
- Create sysvars with new types. [See](https://github.com/sukramj/homematicip_local#system-variables)

# Version 1.7.3 (2022-06-01)

- Bump hahomematic to 1.7.3
- Add more debug logging

# Version 1.7.2 (2022-06-01)

- Bump hahomematic to 1.7.2
  - Better differentiate between float and int for sysvars
  - Switch from # as unit placeholder for sysvars to ' '

# Version 1.7.1 (2022-05-31)

- Bump hahomematic to 1.7.1
  - Rename parameter channel_address to address for put/get_paramset
- Make channel optional for homematicip_local.put_paramset

# Version 1.7.0 (2022-05-31)

- Bump hahomematic to 1.7.0
  - Refactor system variables
- Align integration to match sysvar refactoring
- Add more types for sysvar entities

# Version 1.6.1 (2022-05-30)

- Bump hahomematic to 1.6.2
  - Add more options for boolean conversions
- Update readme. See new options for homematicip_local.set_variable_value.

# Version 1.6.1 (2022-05-29)

- Bump hahomematic to 1.6.1
  - Fix entity definition for HMIP-HEATING
- Fix config flow: select/deselect interfaces

# Version 1.6.0 (2022-05-29)

- Bump hahomematic to 1.6.0
  - Add impulse event
  - Add LEVEL and STATE to HmIP-Heating group to display hvac_action
  - Add device_type as model to attributes
- Adjust typing to match updated HA defaults
- Exclude model from recorder

# Version 1.5.4 (2022-05-25)

- Bump hahomematic to 1.5.4
  - Add function attribute only if set

# Version 1.5.3 (2022-05-24)

- Bump hahomematic to 1.5.3
  - Rename subsection to function

# Version 1.5.2 (2022-05-24)

- Bump hahomematic to 1.5.2
  - Add subsection to attributes
- Exclude subsection from recorder

# Version 1.5.0 (2022-05-23)

- Bump hahomematic to 1.5.0
  - Limit sysvar length to 255 chars due to HA limitations
- Add name to HA event

# Version 1.4.0 (2022-05-16)

- Bump hahomematic to 1.4.0
  - Block parameters by device_type that should not create entities in HA
- Fix: Strings and enums with custom device class must be lowercase to be translatable

# Version 1.3.3 (2022-05-14)

- Fix entity assignment for service clear_cache

# Version 1.3.2 (2022-05-13)

- Bump hahomematic to 1.3.1
  - Increase connection timeout(30s->60s) and reconnect interval(90s->120s) to better support slower hardware

# Version 1.3.1 (2022-05-06)

- Bump hahomematic to 1.3.0
  - Use unit for vars, if available
  - Remove special handling for pydevccu
  - Remove set boost mode to false, when preset is none for bidcos climate entities
- Fix climate preset

# Version 1.3.0 (2022-05-04)

- Use enums provided by 2022.5
- Add hassfest job for custom components
- Fixes after adding hassfest action

# Version 1.2.2 (2022-05-02)

- Bump hahomematic to 1.2.2
  - Fix light channel for multi dimmer

# Version 1.2.1 (2022-04-26)

- Bump hahomematic to 1.2.1
  - Fix callback alive check
- Add persistent notification for missing callback events
- Add recorder platform to avoid writing static attributes

# Version 1.2.0 (2022-04-26)

- Bump hahomematic to 1.2.0
  - Reorg light attributes
  - Add on_time to light and switch
- Add service `homematicip_local.light_set_on_time`
- Add service `homematicip_local.switch_set_on_time`
- Reload integration on configuration change
- Fix triggers, if device has multiple config_entries from different domains

# Version 1.1.4 (2022-04-21)

- Bump hahomematic to 1.1.4
  - Use min as default if default is unset for parameter_data
- This fixes Homegear support

# Version 1.1.3 (2022-04-21)

- Bump hahomematic to 1.1.3
  - Add CeColorDimmer
- Fix hub_sensor, hub_binary_sensor dispatcher

# Version 1.1.2 (2022-04-11)

- Bump hahomematic to 1.1.2
  - Add set_system_variable with string value

# Version 1.1.1 (2022-04-11)

- Bump hahomematic to 1.1.1
  - Read # Version and serial in get_client

# Version 1.1.0 (2022-04-09)

- Bump hahomematic to 1.1.0
  - Add BATTERY_STATE to DEFAULT_ENTITIES
  - Migrate device_info to dataclass
  - Add rega script (provided by @baxxy13) to get serial from CCU
- Add Entity_Description to BATTERY_STATE
- Make device_info more independent from backend
- Clean up cache dirs on instance removal

# Version 1.0.5 (2022-04-07)

- Bump hahomematic to 1.0.6
  - Revert to XmlRPC getValue and getParamset for CCU
- Use Rf-Modul serial for unique_id in config_flow

- Remove deprecated light const

# Version 1.0.4 (2022-04-04)

- Bump hahomematic to 1.0.5
  - Limit hub_state to ccu only
- Remove deprecated light const
- Remove defaults in OptionsFlow for not optional values (callback_ip, callback_port_xml_rpc, json_port)

# Version 1.0.3 (2022-04-02)

- Fix device_type list in diagnostics overview
- Add blueprint for 4-button device (e.g. HmIP-KRCA)

# Version 1.0.2 (2022-03-30)

- Bump hahomematic to 1.0.4
  - Use max # Version of interfaces for backend version
  - API refactoring
- Split control unit

# Version 1.0.1 (2022-03-30)

- Bump hahomematic to 1.0.3
  - Revert to XmlRPC get# Version for CCU

# Version 1.0.0 (2022-03-29)

- Bump hahomematic to 1.0.2
  - Cleanup json code
- Use previously configured interfaces by default in config flow
- Rename hahm to homematicip_local

# Version 0.38.5 (2022-03-22)

- Bump hahomematic to 0.38.5
  - Add support for color temp dimmer

# Version 0.38.4 (2022-03-21)

- Bump hahomematic to 0.38.4
  - Fix interface name for BidCos-Wired

# Version 0.38.3 (2022-03-21)

- Bump hahomematic to 0.38.3
  - Add check for available API method to identify BidCos Wired

# Version 0.38.2 (2022-03-20)

- Bump hahomematic to 0.38.2
  - Catch SysVar parsing exceptions

# Version 0.38.1 (2022-03-20)

- Bump hahomematic to 0.38.1
  - Fix initial config

# Version 0.38.0 (2022-03-20)

- Bump hahomematic to 0.38.0
  - Add central validation
- Improve validation in config flow

# Version 0.37.5 (2022-03-18)

- Bump hahomematic to 0.37.7
  - Add additional system_listMethods to avoid errors on CCU

# Version 0.37.4 (2022-03-18)

- Bump hahomematic to 0.37.6
  - Add JsonRPC.Session.logout before central stop to avoid warn logs at CCU.

# Version 0.37.3 (2022-03-18)

- Bump hahomematic to 0.37.5
  - Send event if interface is not available
  - Don't block available interfaces, if another interface is no available

# Version 0.37.2 (2022-03-17)

- Bump hahomematic to 0.37.4
  - Fix reload paramset
  - Fix value converter

# Version 0.37.1 (2022-03-17)

- Bump hahomematic to 0.37.3
  - Cleanup caching code
  - Use Homematic script to fetch initial data for CCU/HM

# Version 0.37.0 (2022-03-16)

- Bump hahomematic to 0.37.1
  - Avoid unnecessary prefetches
  - Fix JsonRPC Session handling
  - Rename NamesCache to DeviceDetailsCache
  - Move RoomCache to DeviceDetailsCache
  - Move hm value converter to helpers
  - Use JSON RPC for get_value, get_paramset, get_paramset_description
  - Use default for binary_sensor
  - Add semaphore(1) to improve cache usage (less api calls)
- Update unit for IEC sensor

# Version 0.36.4 (2022-03-09)

- Bump hahomematic to 0.36.3
- Use callback when hub is created

# Version 0.36.3 (2022-03-06)

- Bump hahomematic to 0.36.2
  - Make more devices custom_entities

# Version 0.36.2 (2022-02-27)

- Fix LEVEL display

# Version 0.36.0 (2022-02-24)

- Bump hahomematic to 0.36.0
  - Remove HA constants
  - Use enums own constants
- Use more HA constants based on hahomematic enums

# Version 0.35.3 (2022-02-23)

- Bump hahomematic to 0.35.3
  - Move xmlrpc credentials to header

# Version 0.35.2 (2022-02-22)

- Bump hahomematic to 0.35.2
  - Remove password from Exceptions

# Version 0.35.1 (2022-02-21)

- Bump hahomematic to 0.35.1
  - Fix IpBlind

# Version 0.35.0 (2022-02-19)

- Bump hahomematic to 0.35.0
- Fix CF tests

# Version 0.34.2 (2022-02-16)

- Bump hahomematic to 0.34.2
- Add is_locking/is_unlocking to lock

# Version 0.34.1 (2022-02-16)

- Bump hahomematic to 0.34.1
- Add own service to turn_on a siren (acoustically/optically)

# Version 0.34.0 (2022-02-15)

- Bump hahomematic to 0.34.0
  - Add new platform siren

# Version 0.33.0 (2022-02-14)

- Bump hahomematic to 0.33.0
  - Add hvac_action to IP Thermostats
  - Add hvac_action to some HM Thermostats
- Add hvac_action to climate

# Version 0.32.1 (2022-02-12)

- Bump hahomematic to 0.32.4
  - add opening/closing to IPGarage
- Add translation for DOOR_STATE

# Version 0.32.0 (2022-02-12)

- Bump hahomematic to 0.32.3
  - Prioritize detection of device for custom entities
  - Add HmIPW-FIO6 as CE
  - Fix HmIP-MOD-HO
  - Add state(ch2) to HmIP-MOD-HO
- Fix translations

# Version 0.31.4 (2022-02-08)

- Add diagnostics

# Version 0.31.3 (2022-02-08)

- Add multiplier to sensor and number entities.
  This fixes percentage related sensors
- Add more EntityDefinitions (device_class, state_class, ...)

# Version 0.31.2 (2022-02-07)

- Bump hahomematic to 0.31.2
  - Add HmIP-HDM2 to cover
  - Fix unignore filename

# Version 0.31.1 (2022-02-07)

- Bump hahomematic to 0.31.1
  - Add multiplier to entity
  - Substitute device_type of HB devices for usage in custom_entities
- Aggregate entity_helper

# Version 0.31.0 (2022-02-06)

- Bump hahomematic to 0.31.0
- use should_poll from hahomematic

# Version 0.30.3.beta (2022-02-06)

- Bump hahomematic to 0.30.2
  - Remove INHIBIT from ignore parameter list
  - Add support for unignore file
  - Add DIRECTION & ACTIVITY_STATE to cover (is_opening, is_closing)
- Update translations, device_classes form Win-Matic/Key-Matic

# Version 0.30.2 (2022-02-04)

- replace availability PN by blueprint

# Version 0.30.1 (2022-02-04)

- Bump hahomematic to 0.30.1
  - Start hub earlier
- Add service to clear the caches
- Add event about device availability

# Version 0.30.0 (2022-02-03)

- Bump hahomematic to 0.30.0
  - Add CHANNEL_OPERATION_MODE for HmIP(W)-DRBL4
  - Fix DLD lock_state
  - Add is_jammed to locks
- Re-disable RSSI by default
- React on channel_operation_mode for cover/blind on HmIP(W)-DRBL4

# Version 0.29.3 (2022-02-02)

- Bump hahomematic to 0.29.2
  - Add HmIP-STH to climate custom entities
- Add more HM-Devices to EntityDescription
- Switch device_class of HmIP-SCI from safety to opening
- Enhance entity_helper with sets for entity_descriptions by_param and by_device

# Version 0.29.2 (2022-02-02)

- Add more HM-Devices to EntityDescription

# Version 0.29.1 (2022-02-02)

- Bump hahomematic to 0.29.1
  - Check if interface callback is alive
  - Add class for HomeamaticIP Blinds
- Enhance entity_helper with sets for entity_descriptions
- Fix missing device_id in keypress events

# Version 0.29.0 (2022-02-01)

- Bump hahomematic to 0.29.0
  - Make device availability dependent on the client
  - Fire event about interface availability
- Display persistent notification, if interface is not available

# Version 0.28.8 (2022-01-31)

- Bump hahomematic to 0.28.7
  - Add additional check to reconnect

# Version 0.28.7 (2022-01-30)

- Listen on HA stop event to stop the central

# Version 0.28.6 (2022-01-30)

- Bump hahomematic to 0.28.6
  - Switch value caching from getParamset to getValue
    That should fix loading of VirtualDevices and HmRF

# Version 0.28.4 (2022-01-30)

- Bump hahomematic to 0.28.4
- Limit read proxy workers to 1

# Version 0.28.3 (2022-01-29)

- Bump hahomematic to 0.28.2
  - Make names cache non-persistent.

# Version 0.28.2 (2022-01-28)

- Fix hub init

# Version 0.28.1 (2022-01-28)

- Bump hahomematic to 0.28.1
  - Cleanup central API
  - Use dedicated proxy for mass read operations, to avoid blocking of connection checker
- Fix MyPy

# Version 0.28.0 (2022-01-27)

- Bump hahomematic to 0.28.0
  - Create client after init failure
  - Reduce CCU calls

# Version 0.27.1 (2022-01-25)

- Bump hahomematic to 0.27.2
  - optimize initial data load

# Version 0.27.0 (2022-01-25)

- Bump hahomematic to 0.27.0
  - Add hmcli.py as command line script

# Version 0.26.3 (2022-01-24)

- Add name/host to discovered config flow

# Version 0.26.2 (2022-01-23)

- Add upnp discovery to config flow

# Version 0.26.1 (2022-01-23)

- Fix initial setup: Integration will completely setup after initial config flow.
  A reload of the integration or a restart of HA is no longer necessary.
- Cleanup integration init.

# Version 0.26.0 (2022-01-22)

- Bump hahomematic to 0.26.0
  - Add additional params for HM-SEC-Win and HM-SEC-Key
  - Assign secondary channels for HM dimmers
- Fix spelling bidos -> bidcos in ConfigFlow
- Add translation for new params
- Enable wildcard search for device_type in entity_helper

# Version 0.25.0 (2022-01-19)

- Bump hahomematic to 0.25.0
  - Mark unreachable devices as unavailable on startup

# Version 0.24.3 (2022-01-18)

- Bump hahomematic to 0.24.4
  - Improve logging
  - Generic schema for entities is name(str):channel(int), everything else is custom.

# Version 0.24.2 (2022-01-18)

- Bump hahomematic to 0.24.3
  - improve exception handling
  - fix unique_id for system variables
    This is a breaking change.
    Solution: Activate the old sysvars, restart HA and delete the old sysvars.

# Version 0.24.1 (2022-01-17)

- Bump hahomematic to 0.24.2
  - improve exception handling

# Version 0.24.0 (2022-01-17)

- Bump hahomematic to 0.24.0
  - improve exception handling

# Version 0.23.0 (2022-01-16)

- Bump hahomematic to 0.23.3
  - Make ["DRY", "RAIN"] sensor a binary_sensor
  - Add converter to sensor value
    - HmIP-SCTH230 CONCENTRATION to int
    - Fix RSSI (experimental)
  - raise connection_checker interval to 60s
  - Add sleep interval(120s) to wait with reconnect after successful connection check
- Fix unit of RSSI params
- Add device class to HM-Sen-RD-O

# Version 0.22.2 (2022-01-15)

- Bump hahomematic to 0.22.2

# Version 0.22.1 (2022-01-15)

- Bump hahomematic to 0.22.1
  - Add VALVE_STATE for hm climate
  - Add entity_type to attributes
  - Accept LOWBAT only on channel 0

# Version 0.22.0 (2022-01-14)

- Bump hahomematic to 0.22.0
  - Add rooms to device
- Add area to device_info.
  This works, if a Homematic device is assigned to a single room in CCU. Multiple channels can be assigned to the same room.
  If the device is assigned to multiple rooms, or nothing is set, then the area in HA will stay empty

# Version 0.21.1 (2022-01-13)

- Bump hahomematic to 0.21.1
  - Fix event identification and generation
- Remove Alarm Events (not needed)

# Version 0.21.0 (2022-01-13)

- Bump hahomematic to 0.21.0
  - Don't exclude Servicemeldungen from sysvars
  - Use Servicemeldungen sysvar for hub state

# Version 0.20.0 (2022-01-12)

- Bump hahomematic to 0.20.0
- Fix number entities so they can handle percentages

# Version 0.19.1 (2022-01-11)

- Fix set_variable_value

# Version 0.19.0 (2022-01-11)

- Bump hahomematic to 0.19.0
  - Mark secondary channels name with a V --> Vch
- Remove option to enable virtual channels. Virtual channels are now created but disabled by default.

# Version 0.18.1 (2022-01-11)

- Bump hahomematic to 0.18.1
  - Fix callback to notify un_reach

# Version 0.18.0 (2022-01-10)

- Bump hahomematic to 0.18.0
- Set entity enabled default by entity usage enum
- Remove enable_sensors_for_system_variables from config flow
- Bool SysVars are now binary sensors
- All Sysvars are now disabled by default
- Add instance name to system variable name

# Version 0.17.1 (2022-01-09)

- Bump hahomematic to 0.17.1
  - Fix naming for multi channel custom entities

# Version 0.17.0 (2022-01-09)

- Bump hahomematic to 0.17.0
- Adopt change changes from hahomematic

# Version 0.16.1 (2022-01-08)

- Bump hahomematic to 0.16.1
  - Add logging to show usage of unique_id in name
  - Add HmIPW-WRC6 to custom entities
  - Add HmIP-SCTH230 to custom entities

# Version 0.16.0 (2022-01-08)

- Bump hahomematic to 0.16.0
  - Return unique_id if name is not in cache
  - Remove no longer needed press_virtual_remote_key

# Version 0.15.1 (2022-01-07)

- Bump hahomematic to 0.15.2
  - Identify virtual remote by device type
  - Fix Device Exporter / format output
  - Add devices to CustomEntity
    - HmIP-WGC
    - HmIP-WHS
- Identify virtual remote by device type
- Cleanup DeviceTrigger/Action
- Add more EntityDescriptions

# Version 0.15.0 (2022-01-07)

- Bump hahomematic to 0.15.0
  - Remove Virtual Remotes from buttons (BREAKING CHANGE)
    Solution: obsolete entities (buttons) can be deleted in entities overview.
- Update integration name in comments
- Add device actions to call actions on virtual remotes
- Add device(service) for virtual remote

# Version 0.14.0 (2022-01-06)

- Bump hahomematic to 0.14.0
  - Switch some HM-LC-Bl1 to cover
  - Don't exclude DutyCycle, needed for old rf-modules
  - Don't exclude Watchdog from SV sensor

# Version 0.13.2 (2022-01-05)

- Bump hahomematic to 0.13.3
  - HM cover fix: check level for None
  - Fix: max_temp issue for hm thermostats
  - Fix: hm const are str instead of int
- Fix: duplicate remove exception after delete_device

# Version 0.13.1 (2022-01-04)

- Bump hahomematic to 0.13.2
  - Fix cover state
  - Add method to delete a single device to central
- Add a service to delete a Homematic device from HM (No delete in CCU!)
- Fix read of previous device options

# Version 0.13.0 (2022-01-04)

- Bump hahomematic to 0.13.1
  - Fix unique_id for heating_groups (Breaking Change)
    Solution: remove greyed-put climate entity, rename entity_id of new entity afterwards.
  - Remove dedicated json tls option
  - Use generic climate profiles list
- Adopt changes from hahomematic
- Redesign ConfigFlow and OptionsFlow
  - Username and Password are mandatory
  - OptionsFlow allows Reconfiguration of Setup (requires restart)

# Version 0.12.0 (2022-01-03)

- Bump hahomematic to 0.12.0
  - Split number to integer and float
- Adopt changes from hahomematic
- Rename integration

# Version 0.11.1 (2022-01-02)

- Bump hahomematic to 0.11.2
  - Precise entity definitions
  - Improve detection of multi channel devices

# Version 0.11.0 (2022-01-02)

- Bump hahomematic to 0.11.0
  - Add transition to dimmer
  - Remove channel no, if channel is the only_primary_channel
- Adopt change from hahomematic
- Update docstrings
- Add transition to dimmer

# Version 0.10.0 (2021-12-31)

- Add Github Basics
- Add button entity_description
- Fix unload issue
- Fix device description_strategy

# Version 0.9.2 (2021-12-30)

- Adopt async changes from hahomematic
- Bump hahomematic to 0.9.1:
  - Extend naming strategy to use device name if channel name is not customized

# Version 0.9.1 (2021-12-30)

- Update blueprints

# Version 0.9.0 (2021-12-30)

- Make events translatable
  This is a breaking change for device triggers.
  Please check your automations and fix the device trigger.

# Version 0.8.0 (2021-12-29)

- Add service to export device definition

# Version 0.7.1 (2021-12-28)

- Fix service load

# Version 0.7.0 (2021-12-28)

- Use entity services for climate
- Restart ConfigFlow on Error
- Display error messages in config flow

# Version 0.6.2 (2021-12-27)

- Add selector to service disable_away_mode
- Bump hahomematic to 0.6.1:
  - Display profiles only when hvac_mode auto is enabled
  - Fix binary sensor state update for hmip 2-state sensors

# Version 0.6.1 (2021-12-27)

- Remove away mode start date

# Version 0.6.0 (2021-12-27)

- Add climate services for away mode (experimental)
- Bump hahomematic to 0.6.0:
  - Fix HVAC_MODE_OFF for climate

# Version 0.5.1 (2021-12-26)

- Bump hahomematic to 0.5.1:
  - Fix hm_light turn_off

# Version 0.5.0 (2021-12-25)

- Bump hahomematic to 0.5.0:
  - Separate device_address and channel_address

# Version 0.4.0 (2021-12-24)

- Bump hahomematic to 0.4.0:
  - Add ACTUAL_TEMPERATURE as separate entity by @towo
  - Add HEATING_COOLING to IPThermostat and Group
  - Add (_)HUMIDITY and (_)TEMPERATURE as separate entities for Bidcos thermostats
  - use ACTIVE_PROFILE in climate presets

# Version 0.3.2 (2021-12-23)

- Make HmIP-BSM a switch (only dimable devices should be lights). thanks to @itn3rd77

# Version 0.3.0 (2021-12-23)

- Add EntityDescription for Number: Level, Active Profile

# Version 0.2.1 (2021-12-22)

- Use device selector for services
- Remove virtual_key service
- Update dutch translation

# Version 0.2.0 (2021-12-22)

- Sort and use more enums for EntityCategory
- Cleanup device_info
- Add configuration_url to service device
- Move parameters in internal config
- Fix #80 broken config_flow

Version 0.1.2 (2021-12-21)

- Refactor device_info and identifier handling

Version 0.1.1 (2021-12-21)

- Rename async methods and @callback methods to async\_\*
- Update device identifier with interface_id

# Version 0.1.0 (2021-12-XX)

- Bump # Version to 0.1.0
- Update EntityDescriptions
- Add initial tests for config_flow
- Add Sensor Descriptions

# Version 0.0.22.2 (2021-12-16)

- Add DE translation
- Update NL translation

# Version 0.0.22.1 (2021-12-16)

- Fix resolve names for all given ports incl. tls (update hahomematic)
- Rename attributes to match eQ-3 naming
- Don't use title() for instance_name
- Fix Hub init

# Version 0.0.21 (2021-12-15)

- Add some blueprints for automation in GIT repo
- Simplify light turn_on
- Fix HmIP-BSL
- Use _attr_ for entities

# Version 0.0.20 (2021-12-13)

- Add device name to persistent notification
- rearrange config flow

# Version 0.0.19 (2021-12-12)

- Fix EntityDescriptions
- Fix OptionFlow
- Rename helper to entity_helper
- Add UNREACH to persistent notifications

# Version 0.0.18 (2021-12-11)

- Add type hints based on HA mypy config
- Rename impulse to special event
- Add persistent notification

# Version 0.0.17 (2021-12-05)

- Add translation for HmIP-SRH states

- Code quality:
  - Use Enums from HaHomematic
  - Add more type hints (fix mypy errors)
  - Use assignment expressions
  - Move services to own file

# Version 0.0.16 (2021-12-02)

- Initial release
