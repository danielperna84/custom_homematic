[HA Homematic Custom Component](https://github.com/danielperna84/custom_homematic) for Home Assistant

This is a custom component to integrate [HA Homematic](https://github.com/danielperna84/hahomematic) into [Home Assistant](https://www.home-assistant.io).

### This project is still in early development!

Provides the following:
- basic ConfigFlow
- Optionflow
  - Enable virtual channels of HmIP-Devices
  - Enable sensors for system variables
- Device Trigger (PRESS_XXX Events are selectable in automations)
- Virtual Remotes can be triggered in HA automations
- The Hub (CCU/Homegear) with all system variables
- Supports TLS to CCU/Homegear for Json and XMLRPC

Services:
- Put paramset (Call to putParamset in the RPC XML interface)
- Set device value (Set the value of a node)
- Set install mode (Enable the install mode
- Set variable value (Set the value of a system variable)
- Virtual key (Press a virtual key from CCU/Homegear or simulate keypress) 

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
- Switch