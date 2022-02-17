[HA Homematic Custom Component](https://github.com/danielperna84/custom_homematic) for Home Assistant

This is a custom component to integrate [HA Homematic](https://github.com/danielperna84/hahomematic) into [Home Assistant](https://www.home-assistant.io).

Provides the following:
- ConfigFlow incl. reconfiguration of existing installation.
- Device Discovery (Detect CCUs in the local Network)
- Device Trigger (PRESS_XXX Events are selectable in automations)
- Virtual Remotes can be triggered in HA automations
- The Hub (CCU/Homegear) with all system variables displayed as sensors/binary_sensors.
- Services:
  - Put paramset (Call to putParamset in the RPC XML interface)
  - Set device value (Set the value of a node)
  - Set variable value (Set the value of a system variable)
  - Enable climate away mode by calendar (Dateformat: `2021-12-24 08:00`)
  - Enable climate away mode by duration
  - Disable climate away mode
  - Export device definition (Can be used to support integration of new devices)
  - Delete Device (Deletes a device from HA, but not from CCU). Can be used, if a device has been renamed in CCU.
  - Clear Cache (Clears the cache for a central unit from Home Assistant. Requires a restart)
  - Turn on Siren (Turn siren on. Siren can be disabled by siren.turn_off. Useful helpers for siren can be found [here](https://github.com/danielperna84/hahomematic/blob/devel/docs/input_select_helper.md#siren)
- Supports TLS to CCU/Homegear for Json and XMLRPC
- Assign area in HA, if room in CCU is used.
  This works, if a homematic device is assigned to a single room in CCU. Multiple channels can be assigned to the same room.
  If the device is assigned to multiple rooms, or nothing is set, then the area in HA will stay empty.
  This has no effect on existing area assignements.


Entity Support
- Binary_Sensor
- Button
- Climate
- Cover
- Light
- Lock
- Sensor
- Number
- Select
- Siren
- Switch
