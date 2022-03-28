# custom_homematic
Custom Home Assistant Component for HomeMatic

[Installation](https://github.com/danielperna84/custom_homematic/wiki/Installation)

[State of the integration](https://github.com/danielperna84/custom_homematic/blob/devel/info.md)

# ISSUES
Please report issues in [hahomamatic repo](https://github.com/danielperna84/hahomematic/issues).

# Homematic(IP) Local (WIP documentation)

The [Homematic](https://www.homematic.com/) integration provides bi-directional communication with your HomeMatic hub (CCU, Homegear etc.). It uses an XML-RPC connection to set values on devices and subscribes to receive events the devices and the CCU emit. You can configure this integration multiple times if you want to integrate multiple HomeMatic Hubs into Home Assistant.  
If you are using Homegear with paired [Intertechno](https://intertechno.at/) devices, uni-directional communication is possible as well.

Please take the time to read the entire documentation before asking for help. It will answer the most common questions that come up while working with this integration.

## Device support

HomeMatic devices are integrated by automatically detecting the available parameters, for which suitable entities will be added to the corresponding device-object within Home Assistant. However, for more complex devices (thermostats, some cover-devices and more) we perform a custom mapping to better represent the devices features. This is an internal detail you usually don't have to care about. It may become relevant though if new hardware becomes available. In such a case the automatic mode will be active. Therefore f.ex. a new thermostat-model might not include the `climate` entity. In such a case you may report the missing customization in the [hahomematic](https://github.com/danielperna84/hahomematic) repository.

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

This integration always passes credentials to the HomeMatic hub when connecting. These will be silently ignored if you have not enabled authentication on the hub. It is imporant to note though, that special characters (like `#`) within your credentials may break the possibility to authenticate.  
The account used for communication is required to have admin privileges on your HomeMatic hub.  
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

The integration supports auto-discovery for the CCU and compatible hubs like RaspberryMatic. The Home Assistant User Interface will notify you about the integrationg being available for setup. It will pre-fill the instance-name and IP address of your HomeMatic hub. If you have already set up the integration manually, you can either click the _Ignore_ button or re-configure your existing instance to let Home Assistant know the existing instance is the one it has detected.

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
callback_host:
  required: false
  description: Hostname or IP address for callback-connection (only required in special network conditions).
  type: string
callback_port:
  required: false
  description: Port for callback-connection (only required in special network conditions).
  type: integer
tls:
  required: false
  description: Enable TLS encryption. This wil change the default for json_port from 80 to 443.
  type: boolean
  default: false
verify_tls:
  required: false
  description: Enable TLS verification.
  type: boolean
  default: false
json_port:
  required: false
  description: Port used the access the JSON-RPC API.
  type: integer
  default: 80
```

#### Interface

```yaml
hmip_rf_enabled:
  required: false
  description: Enable Homematic IP (wiredless and wired).
  type: boolean
  default: true
hmip_rf_port:
  required: false
  description: Port for Homematic IP (wireless and wired).
  type: integer
  default: 2010
bidos_rf_enabled:
  required: false
  description: Enable Homematic (wireless).
  type: boolean
  default: true
bidos_rf_port:
  required: false
  description: Port for Homematic (wireless).
  type: integer
  default: 2001
virtual_devices_enabled:
  required: false
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
  required: false
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

### callback_host and callback_port

These two options are required for _special_ network environments. If for example Home Assistant is running within a Docker container and detects its own IP to be within the Docker network, the CCU won't be able to establish the connection to Home Assistant. In this case you have to specify which address and port the CCU should connect to. This may require forwarding connections on the Docker host machine to the relevant container.

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

### `homematicip_local.put_paramset`

Call to `putParamset` in the XML-RPC interface.

### `homematicip_local.set_device_value`

Set a device parameter via the XML-RPC interface.

### `homematicip_local.set_install_mode`

Turn on the install mode on the provided Interface to pair new devices.

### `homematicip_local.set_variable_value`

Set the value of a variable on your HomeMatic hub.

### `homematicip_local.turn_on_siren`

Turn siren on. Siren can be disabled by siren.turn_off. Useful helpers for siren can be found [here](https://github.com/danielperna84/hahomematic/blob/devel/docs/input_select_helper.md#siren).

## Additional information

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
- [Support for 2-button Remotes](https://github.com/danielperna84/custom_homematic/blob/devel/blueprints/automation/homematicip_local-actions-for-2-button.yaml)
- [Support for 6-button Remotes](https://github.com/danielperna84/custom_homematic/blob/devel/blueprints/automation/homematicip_local-actions-for-6-button.yaml)
- [Support for 8-button Remotes](https://github.com/danielperna84/custom_homematic/blob/devel/blueprints/automation/homematicip_local-actions-for-8-button.yaml)
- [Support for persistent notifications for unavailable devices](https://github.com/danielperna84/custom_homematic/blob/devel/blueprints/automation/homematicip_local_persistent_notification.yaml)

Just copy these files to "your ha-config_dir"/blueprints/automation
