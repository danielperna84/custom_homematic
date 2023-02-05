# Version 1.29.0 (2022-02-06)
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

# Version 1.28.0 (2022-02-01)

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

# Version 1.27.2 (2022-01-26)
### All changes:
- Remove device class `GAS` from GAS_POWER (limitation of HA)
- Replace `async_setup_platforms` by `async_forward_entry_setups` in `__init__.py`
- Fix put_paramset for HM MASTER paramset

# Version 1.27.1 (2022-01-XX)
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

# Version 1.27.0 (2022-01-20)
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

# Version 1.26.5 (2022-01-16)
- Fix display of logbook events

# Version 1.26.4 (2022-01-16)

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

# Version 1.26.2 (2022-01-13)
### New features
- Add device availability and error to logbook

### All changes:
- Bump hahomematic to 2023.1.3
  - Unifiy event parameters
  - Refactor entity.py for better event support
  - Fix wrong warning after set_system_variable
  - Add validation to event_data
- Reassign event parameters in control_unit
- Add device availability and error to logbook

# Version 1.26.1 (2022-01-09)
### New features
- Remove LOWBAT from HM-LC-Sw1-Pl, HM-LC-Sw2-FM
- Remove OPERATING_VOLTAGE from HmIP-BROLL, HmIP-FROLL
- Use actions and buttons for device actions

### All changes:
- Bump hahomematic to 2023.1.2
  - No longer create ClientSession in json_rpc_client for tests
  - Add backend tests
  - Use mocked local client to check  method_calls
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
- Rename climate presets from 'Profile *' to 'week_program_*':
  HA now allows translations of custom preset modes. The internal preset mode has been renamed from 'Profile *' to 'week_program_*'.
  If service climate.set_preset_mode was used with values like "Proflle 1", these automations and scripts need to be edited and use "week_program_1" instead.
  This preset mode is now displayed as "WP 1" to better accommodate the available space in the UI.
### New features
- Make sysvar_scan_interval configurable
  The integration can now be reconfigured to use a shorter or longer interval between sysvar scans. The sysvar scan can also be disabled, if not needed.
### All changes:
- Bump hahomematic to 2023.1.0
  - Remove empty unit for numeric sysvars
  - Fix native device units
  - Rename climate presets from 'Profile *' to 'week_program_*'
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
- Add SensorStateClass.TOTAL_INCREASING to svEnergyCounter_* sysvars
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
  - Send ERROR_* parameters as homematic.device_error event
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
- Remove support for old hub entities with homematicip_local.*
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
  - Wrap LEVEL of HmIP-TRV*, HmIP-HEATING to sensor
- Use UnitOf* enums
- Add EntityDescription for LEVEL of HmIP-TRV*, HmIP-HEATING as sensor
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
  - Make connection checker more resilent

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
- Remove unneeded _attr

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
  - homematicip_local_reactivate_single_device.yaml -  Reactivate a single device

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
  - Fix _check_connection for Homegear/CCU
- Add community blueprint for 4-button flush mount device by @andyboeh
- Add HVACAction.IDLE to dict 

# Version 1.12.0 (2022-07-17)
- Bump hahomematic to 2022.7.9
  - Remove state_uncertain from default attributes
- Make entity state restoreable after HA restart
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
  See [Readme](https://github.com/danielperna84/custom_homematic#noteworthy-about-entity-states) for further information.
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
    - Readd HmIPW-FIO6 to custom device handling
- Disable device trigger based on event usage

# Version 1.9.0 (2022-06-29)
- Bump hahomematic to 1.9.1
  - Add button to virtual remote
  - Remove HmIPW-FIO6 from custom device handling
- Remove dummies for unit_of_measurement

# Version 1.8.6 (2022-06-07)
- Bump hahomematic to 1.8.6
  - Code cleanup
- Fix sysvar creation for delayed plattform setups on some environments

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
- Create sysvars with new types. [See](https://github.com/danielperna84/custom_homematic#system-variables)

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
- Make device_info more independant from backend
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
- Remove defaults in OptionsFlow for not optional values (callback_ip, callback_port, json_port)

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
  - Dont't block available interfaces, if another interface is no available

# Version 0.37.2 (2022-03-17)
- Bump hahomematic to 0.37.4
  - Fix reload paramset
  - Fix value converter

# Version 0.37.1 (2022-03-17)
- Bump hahomematic to 0.37.3
  - Cleanup caching code
  - Use homematic script to fetch initial data for CCU/HM

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
- use  should_poll from hahomematic

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
  This works, if a homematic device is assigned to a single room in CCU. Multiple channels can be assigned to the same room.
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
- Add a service to delete a homematic device from HM (No delete in CCU!)
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
  - Add (*)HUMIDITY and (*)TEMPERATURE as separate entities for Bidcos thermostats
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

Versiom 0.1.2 (2021-12-21)
- Refactor device_info and identifier handling

Versiom 0.1.1 (2021-12-21)
- Rename async methods and @callback methods to async_*
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
