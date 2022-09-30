# custom_homematic
Custom Home Assistant Component for HomeMatic

HomematicIP Local requires HA 2022.9 and above.

[Installation](https://github.com/danielperna84/custom_homematic/wiki/Installation)

[State of the integration](https://github.com/danielperna84/custom_homematic/blob/devel/info.md)

# ISSUES
Please report issues in [hahomamatic repo](https://github.com/danielperna84/hahomematic/issues).

# Homematic(IP) Local (WIP documentation)

The [Homematic](https://www.homematic.com/) integration provides bi-directional communication with your HomeMatic hub (CCU, Homegear etc.). It uses an XML-RPC connection to set values on devices and subscribes to receive events the devices and the CCU emit. You can configure this integration multiple times if you want to integrate multiple HomeMatic Hubs into Home Assistant.  
If you are using Homegear with paired [Intertechno](https://intertechno.at/) devices, uni-directional communication is possible as well.

**Please take the time to read the entire documentation before asking for help. It will answer the most common questions that come up while working with this integration.**

## Device support

HomeMatic devices are integrated by automatically detecting the available parameters, for which suitable entities will be added to the corresponding device-object within Home Assistant. However, for more complex devices (thermostats, some cover-devices and more) we perform a custom mapping to better represent the devices features. This is an internal detail you usually don't have to care about. It may become relevant though if new hardware becomes available. In such a case the automatic mode will be active. Therefore f.ex. a new thermostat-model might not include the `climate` entity. In such a case you may report the missing customization in the [hahomematic](https://github.com/danielperna84/hahomematic) repository.

### Deactivated Entities
A lot of additional entities were initially created _deactivated_ and can be _activated_, if necessary, in the `advanced settings` of the entity.

## Requirements

### Hardware

This integration can be used with any CCU-compatible HomeMatic hub that exposes the required XML-RPC interface. This includes:
- CCU2/3
- RaspberryMatic
- Debmatic
- Homegear
- Home Assistant OS / Supervised with a suitable add-on + communication device

Due to a bug in previous version of the CCU2 / CCU3, this integration requires at least the following version for usage with homematic IP devices:

- CCU2: 2.53.27
- CCU3: 3.53.26

### Firewall

To allow communication to your HomeMatic hub, a few ports on the hub have to be accessible from your Home Assistant machine. The relevant default ports are:

- HomeMatic RF (_old_ wireless devices): `2001` / `42001` (with enabled TLS)
- Homematic IP (wireless and wired): `2010` / `42010` (with enabled TLS)
- HomeMatic wired (_old_ wired devices): `2000` / `42000` (with enabled TLS)
- Virtual thermostat groups: `9292` / `49292` (with enabled TLS)
- JSON-RPC (used to get names and rooms): `80` / `443` (with enabled TLS)

### Authentication

This integration always passes credentials to the HomeMatic hub when connecting. 
For CCU and decendants (RaspberryMatic, debmatic) it is recommended to enable authentication for XmlRPC communication (Settings/Control panel/Security/Authentication). JsonRPC communication ia always authenticated.
 
The account used for communication is required to have admin privileges on your HomeMatic hub.
It is imporant to note though, that special characters (like `#`) within your credentials may break the possibility to authenticate. 

If you are using Homegear and have not set up authentication, please enter dummy-data to complete the configuration flow.

# Configuration

Adding Homematic(IP) Local to you Home Assistant instance can be done via the user interface, by using this My button: [ADD INTEGRATION](https://my.home-assistant.io/redirect/config_flow_start?domain=homematicip_local)

## Manual configuration steps
- Browse to your Home Assistant instance.
- In the sidebar click on [Configuration](https://my.home-assistant.io/redirect/config)
- From the configuration menu select: [Integrations](https://my.home-assistant.io/redirect/integrations)
- In the bottom right, click on the [Add Integration](https://my.home-assistant.io/redirect/config_flow_start?domain=homematicip_local) button.
- From the list, search and select "Homematic(IP) Local".
- Follow the instruction on screen to complete the set up.

## Auto-discovery

The integration supports auto-discovery for the CCU and compatible hubs like RaspberryMatic. The Home Assistant User Interface will notify you about the integrationg being available for setup. It will pre-fill the instance-name and IP address of your HomeMatic hub. If you have already set up the integration manually, you can either click the _Ignore_ button or re-configure your existing instance to let Home Assistant know the existing instance is the one it has detected. After re-configuring your instance a HA restart is required.

Autodiscovery uses the last 10-digits of your rf-module's serial to uniquely identify your CCU, but there are rare cases, where the CCU API and the UPNP-Message contains/returns different values. In these cases, where the auto-discovered instance does not disappear after a HA restart, just click on the _Ignore_ button. 
Known cases are in combination with the rf-module `HM-MOD-RPI-PCB`.

### Configuration Variables

#### Central

```yaml
instance_name:
  required: true
  description: Name to identify your HomeMatic hub. This has to be unique for each configured hub. Allowed characters are a-z and 0-9.
  type: string
host:
  required: true
  description: Hostname or IP address of your hub.
  type: string
username:
  required: true
  description: Username of the admin-user on your hub.
  type: string
password:
  required: true
  description: Password of the admin-user on your hub.
  type: string
tls:
  required: true
  description: Enable TLS encryption. This wil change the default for json_port from 80 to 443.
  type: boolean
  default: false
verify_tls:
  required: true
  description: Enable TLS verification.
  type: boolean
  default: false
callback_host:
  required: false
  description: Hostname or IP address for callback-connection (only required in special network conditions).
  type: string
callback_port:
  required: false
  description: Port for callback-connection (only required in special network conditions).
  type: integer
json_port:
  required: false
  description: Port used the access the JSON-RPC API.
  type: integer
```

#### Interface

This page always displays the default values, also when reconfiguring the integration.

```yaml
hmip_rf_enabled:
  required: true
  description: Enable Homematic IP (wiredless and wired).
  type: boolean
  default: true
hmip_rf_port:
  required: false
  description: Port for Homematic IP (wireless and wired).
  type: integer
  default: 2010
bidos_rf_enabled:
  required: true
  description: Enable Homematic (wireless).
  type: boolean
  default: true
bidos_rf_port:
  required: false
  description: Port for Homematic (wireless).
  type: integer
  default: 2001
virtual_devices_enabled:
  required: true
  description: Enable heating groups.
  type: boolean
  default: true
virtual_devices_port:
  required: false
  description: Port for heating groups.
  type: integer
  default: 9292
virtual_devices_path:
  required: false
  description: Path for heating groups
  type: string
  default: /groups
hs485d_enabled:
  required: true
  description: Enable Homematic (wired).
  type: boolean
  default: false
hs485d_port:
  required: false
  description: Port for Homematic (wired).
  type: integer
  default: 2000
```

### JSON-RPC Port

The JSON-RPC Port is used to fetch names and room information from the CCU. The default value is `80`. But if you enable TLS the port `443` will be used. You only have to enter a custom value here if you have set up the JSON-RPC API to be available on a different port.  
If you are using Homegear the names are fetched using metadata available via XML-RPC. Hence the JSON-RPC port is irrelevant for Homegear users.
**This value is always empty when the integration gets reconfigured.**

### callback_host and callback_port

These two options are required for _special_ network environments. If for example Home Assistant is running within a Docker container and detects its own IP to be within the Docker network, the CCU won't be able to establish the connection to Home Assistant. In this case you have to specify which address and port the CCU should connect to. This may require forwarding connections on the Docker host machine to the relevant container.
**These values are always empty when the integration is reconfigured.**

## System variables

System variables are fetched every 30 seconds from backend (CCU/Homegear), and are created initially as **deactived** entity.

The types of system variables in the CCU are:
- character string (Zeichenkette)
- list of values (Werteliste)
- number (Zahl)
- logic value (Logikwert)
- alert (Alarm)

System variables have a description that can be added in the CCU's UI.
If you add the marker `hahm` to the description exteded features for this system variable can be used in HA.
This `hahm` marker is used to control the entity creation in HA.
Switching system variables from DEFAULT -> EXTENDED or EXTENDED -> DEFAULT requires a restart of HA or a reload of the integration.

When using Homegear system variables are handled like the DEFAULT.

### This is how entities are created from system variables:

- all **character strings** are created as `sensor` entity. Don't tag **character strings** with `hahm`.
- DEFAULT: system variables that do **not** have the  **marker** `hahm` in description:
  - value list, number --> `sensor` entity
  - alert, logic value --> `binary_sensor` entity
- EXTENDED: system variables that do have the  **marker** `hahm` in description:
  - value lists --> `select` entity
  - number --> `number` entity
  - alarm, logic value —> `switch` entity

Using `select`, `number` and `switch` results in the following advantages:
- System variables can be changed directly in the UI without additional logic.
- The general services for `select`, `number` and `switch` can be used.
- The service `homematicip_local.set_variable_value` can, but no longer has to, be used to write system variables.
- Use of device based automations (actions) is possile.

## Services

The Homematic(IP) Local integration makes various custom services available.

### `homematicip_local.clear_cache`

Clears the cache for a central unit from Home Assistant. Requires a restart.

### `homematicip_local.delete_device`

Delete a device from Home Assistant.

### `homematicip_local.disable_away_mode`

Disable the away mode for `climate` devices. This only works with Homematic IP devices.

### `homematicip_local.enable_away_mode_by_calendar`

Enable the away mode immediately, and specify the end time by date. This only works with Homematic IP devices.

### `homematicip_local.enable_away_mode_by_duration`

Enable the away mode immediately, and specify the end time by setting a duration. This only works with Homematic IP devices.

### `homematicip_local.export_device_definition`

Exports a device definition (2 files) to 
- 'Your home-assistant config directory'/homematicip_local/export_device_descriptions/{device_type}.json
- 'Your home-assistant config directory'/homematicip_local/export_paramset_descriptions/{device_type}.json

Please create a pull request with both files at [pydevccu](https://github.com/danielperna84/pydevccu), if the device not exists, to support future development of this component.
This data can be used by the developers to add customized entities for new devices.

### `homematicip_local.force_device_availability`

Reactivate a device in Home Assistant, that has been made unavailable by an UNREACH event from CCU.
This service will only override the availability status of a device and all its dependant entities. There is no communication to the backend to enforce a reactivation!

This is not a solution for communication problems with homematic devices. 
Use this only to reactivate devices with flaky communication to gain control again.

### `homematicip_local.put_paramset`

Call to `putParamset` in the XML-RPC interface.

### `homematicip_local.set_device_value`

Set a device parameter via the XML-RPC interface. Preferred when using the UI. Works with device selection.

### `homematicip_local.set_device_value_raw`

Set a device parameter via the XML-RPC interface. Works with channel address.

### `homematicip_local.set_install_mode`

Turn on the install mode on the provided Interface to pair new devices.

### `homematicip_local.set_variable_value`

Set the value of a variable on your HomeMatic hub.

Value lists accept the 0-based list position or the value as input.

For booleans the following values can be used:
- 'true', 'on', '1', 1 -> True
- 'false', 'off', '0', 0 -> False

### `homematicip_local.turn_on_siren`

Turn siren on. Siren can be disabled by siren.turn_off. Useful helpers for siren can be found [here](https://github.com/danielperna84/hahomematic/blob/devel/docs/input_select_helper.md#siren).

### `homematicip_local.light_set_on_time`

Set on time for a light entity. Must be followed by a `light.turn_on`.
Use 0 to reset the on time.

### `homematicip_local.switch_set_on_time`

Set on time for a switch entity. Must be followed by a `switch.turn_on`.
Use 0 to reset the on time.

### `homeassistant.update_entity`

Update an entity's value (Only required for edge cases). An entity can be updated at most every 60 seconds.

This service is not needed to update entities in general, because 99,9% of the entities and values are getting updated by this integration automatically. But with this service, you can manually update the value of an entity - **if you really need this in special cases**, e.g. if the value is not updated or not available, because of design gaps or bugs in the backend or device firmware (e.g. rssi-values of some HM-devices). 

Attention: This service gets the value for the entity via a 'getValue' from the backend, so the values are updated afterwards from the backend cache (for battery devices) or directly from the device (for non-battery devices). So even with using this service, the values are still not guaranteed for the battery devices and there is a negative impact on the duty cycle of the backend for non-battery devices.

## Additional information

### Noteworthy about entity states

The integration fetches the states of all devices on initially startup and on reconnect from the backend (CCU/Homegear).
Afterwards, the state updates will be sent by the CCU as events to HA. We don't fetch states, except for system variables, after initial startup.

After a restart of the backend (esp. CCU), the Backend has initially no state information about its devices. Some devices are actively polled for updates, but many devices, esp. battery driven devices, cannot be polled, so the backend needs to wait for periodic update send by the device.
This could take seconds, minutes and in rare cases hours.

That's why the last state of an entity will be recovered after a HA restart.
If you want to know how assured the displayed value is, there is an attribute `value_state` at each entity with the following values:

- `valid` the value was either loaded from the CCU or received via an event
- `not valid` there is no value. The state of the entity is `unknown`.
- `restored` the value has been restored from the last saved state after an HA restart
- `uncertain` the value could not be updated from the CCU after restarting the CCU, and no events were received either.
- 
If you want to be sure that the state of the entity is as consistent as possible, you should also check the `value_state` attribute for `valid`.

### Devices with buttons

Devices with buttons (e.g. HM-Sen-MDIR-WM55 and other remote controls) may not be fully visible in the UI. This is intended, as buttons don't have a persistent state. An example: The HM-Sen-MDIR-WM55 motion detector will expose entities for motion detection and brightness (among other entities), but none for the two internal buttons. To use these buttons within automations, you can select the device as the trigger-type, and then select the specific trigger (_Button "1" pressed_ etc.).

### Pressing buttons via automation

It is possible to press buttons of devices from Home Assistant. A common usecase is to press a virtual button of your CCU, which on the CCU is configured to perform a specific action. For this you can use the `homematicip_local.set_device_value` service. In YAML-mode the service call to press button `3` on a CCU could look like this:

```yaml
service: homematicip_local.set_device_value
data:
  device_id: abcdefg...
  parameter: PRESS_SHORT
  value: 'true'
  value_type: boolean
  channel: 3
```

### Events for Homematic IP devices

To receive button-press events for some Homematic IP devices like WRC2 / WRC6 (wall switch) or SPDR (passage sensor) or the KRC4 (key ring remote control) you have to temporary create an empty program for each channel in the CCU:

1. In the menu of your CCU's admin panel go to `Programs and connections` > `Programs & CCU connection`
2. Go to `New` in the footer menu
3. Click the plus icon below `Condition: If...` and press the button `Device selection`
4. Select one of the device's channels you need (1-2 / 1-6 for WRC2 / WRC6 and 2-3 for SPDR)
5. Select short or long key press
6. Save the program with the `OK` button
7. Trigger the program by pressing the button as configured in step 5. Your device might indicate success via a green LED or similar. When you select the device in `Status and control` > `Devices` on the CCU, the `Last Modified` field should no longer be empty
8. When your channel is working now, you can edit it to select the other channels one by one
9. At the end, you can delete this program from the CCU

## Examples in YAML

Set boolean variable to true:

```yaml
...
action:
  service: homematicip_local.set_variable_value
  data:
    entity_id: homematicip_local.ccu2
    name: Variablename
    value: '3'
```

Manually turn on a switch actor:

```yaml
...
action:
  service: homematicip_local.set_device_value
  data:
    device_id: abcdefg...
    channel: 1
    parameter: STATE
    value: 'true'
    value_type: boolean
```

Manually set temperature on thermostat:

```yaml
...
action:
  service: homematicip_local.set_device_value
  data:
    device_id: abcdefg...
    channel: 4
    parameter: SET_TEMPERATURE
    value: '23.0'
    value_type: double
```

Set the week program of a wall thermostat:

```yaml
...
action:
  service: homematicip_local.put_paramset
  data:
    device_id: abcdefg...
    paramset_key: MASTER
    paramset:
      WEEK_PROGRAM_POINTER: 1
```

Set the week program of a wall thermostat with explicit `rx_mode` (BidCos-RF only):

```yaml
...
action:
  service: homematicip_local.put_paramset
  data:
    device_id: abcdefg...
    paramset_key: MASTER
    rx_mode: WAKEUP
    paramset:
      WEEK_PROGRAM_POINTER: 1
```

BidCos-RF devices have an optional parameter for put_paramset which defines the way the configuration data is sent to the device.

`rx_mode` `BURST`, which is the default value, will wake up every device when submitting the configuration data and hence makes all devices use some battery. It is instant, i.e. the data is sent almost immediately.

`rx_mode` `WAKEUP` will send the configuration data only after a device submitted updated values to CCU, which usually happens every 3 minutes. It will not wake up every device and thus saves devices battery.

## Available Blueprints

The following blueprints can be used to simplify the usage of Homematic device:
- [Support for 2-button Remotes](https://github.com/danielperna84/custom_homematic/blob/devel/blueprints/automation/homematicip_local-actions-for-2-button.yaml): Support for two button remote like HmIP-WRC2.
- [Support for 4-button Key Ring Remote Control](https://github.com/danielperna84/custom_homematic/blob/devel/blueprints/automation/homematicip_local-actions-for-key_ring_remote_control.yaml): Support for two button remote like HmIP-KRCA.
- [Support for 6-button Remotes](https://github.com/danielperna84/custom_homematic/blob/devel/blueprints/automation/homematicip_local-actions-for-6-button.yaml): Support for two button remote like HmIP-WRC6.
- [Support for 8-button Remotes](https://github.com/danielperna84/custom_homematic/blob/devel/blueprints/automation/homematicip_local-actions-for-8-button.yaml): Support for two button remote like HmIP-RC8.
- [Support for persistent notifications for unavailable devices](https://github.com/danielperna84/custom_homematic/blob/devel/blueprints/automation/homematicip_local_persistent_notification.yaml): Enable persitant notifications about unavailable devices.
- [Reactivate device by type](https://github.com/danielperna84/custom_homematic/blob/devel/blueprints/automation/homematicip_local_reactivate_device_by_type.yaml). Reactivate unavailable devices by device type.
- [Reactivate every device](https://github.com/danielperna84/custom_homematic/blob/devel/blueprints/automation/homematicip_local_reactivate_device_full.yaml). Reactivate all unavailable devices. NOT recommended. Usage of `by device type` or `single device` should be preferred.
- [Reactivate single device](https://github.com/danielperna84/custom_homematic/blob/devel/blueprints/automation/homematicip_local_reactivate_single_device.yaml) Reactivate a unavailable single device.

Feel free to contribute:
- [Community blueprints](https://github.com/danielperna84/custom_homematic/blob/devel/blueprints/community)

I (SukramJ) use these blueprints on my own system and share them with you, but i don't want to investigate in blueprints for devices, that i don't own!
Feel free to copy, improve, enhance these blueprints and adopt them to other devices, and if you like create a PR with a new blueprint.

Just copy these files to "your ha-config_dir"/blueprints/automation
