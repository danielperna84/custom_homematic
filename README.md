# custom_homematic
Custom Home Assistant Component for HomeMatic

[Installation](https://github.com/danielperna84/custom_homematic/wiki/Installation)

[State of the integration](https://github.com/danielperna84/custom_homematic/wiki/State-of-the-integration)

# ISSUES
Please report issues in [hahomamatic repo](https://github.com/danielperna84/hahomematic/issues).

# Homematic(IP) Local (WIP documentation)

The [Homematic](https://www.homematic.com/) integration provides bi-directional communication with your HomeMatic hub (CCU, Homegear etc.). It uses an XML-RPC connection to set values on devices and subscribes to receive events the devices and the CCU emit.
If you are using Homegear with paired [Intertechno](https://intertechno.at/) devices, uni-directional communication is possible as well.

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

This integration always passes credentials to the HomeMatic hub when connecting. These will be silently ignored if you have not enabled authentication on the hub. It is imporant to note though, that special characters within your credentials may break the possibility to authenticate.  
The account used for communication is required to have admin privileges on your HomeMatic hub.

# Configuration

Adding Homematic(IP) Local to you Home Assistant instance can be done via the user interface, by using this My button: [ADD INTEGRATION](https://my.home-assistant.io/redirect/config_flow_start?domain=hahm)

## Manual configuration steps
- Browse to your Home Assistant instance.
- In the sidebar click on [Configuration](https://my.home-assistant.io/redirect/config)
- From the configuration menu select: [Integrations](https://my.home-assistant.io/redirect/integrations)
- In the bottom right, click on the [Add Integration](https://my.home-assistant.io/redirect/config_flow_start?domain=hahm) button.
- From the list, search and select "Homematic(IP) Local".
- Follow the instruction on screen to complete the set up.

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

### callback_host and callback_port

These two options are required for _special_ network environments. If for example Home Assistant is running within a Docker container and detects its own IP to be within the Docker network, the CCU won't be able to establish the connection to Home Assistant. In this case you have to specify which address and port the CCU should connect to. This may require forwarding connections on the Docker host machine to the relevant container.
