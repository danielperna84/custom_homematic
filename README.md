# Homematic(IP) Local for OpenCCU

[![releasebadge]][release]
[![License][license-shield]](LICENSE)
[![hainstall][hainstallbadge]][hainstall]
[![GitHub Sponsors][sponsorsbadge]][sponsors]
[![hacs][hacsbadge]][hacs]

Homematic(IP) Local for OpenCCU is a custom [integration](https://www.home-assistant.io/getting-started/concepts-terminology/#integrations) for Home Assistant.

## At a Glance

- Local Home Assistant integration for Homematic(IP) hubs (CCU2/3, OpenCCU, Debmatic, Homegear). No cloud required. See [Supported Hardware](#supported-hardware) for the complete, exhaustive list.
- Communication: Local XML-RPC for control and push state updates; JSON-RPC for names and rooms.
- Installation: HACS recommended; manual installation supported.
- Auto-discovery: Supported for CCU and compatible hubs.
- Minimum requirements: Home Assistant 2026.8.0+; for Homematic IP on CCU require at least CCU2 2.61.x / CCU3 3.61.x.

## Quick Start

| Resource | Link |
|----------|------|
| **Full Documentation** | [User Guide](https://sukramj.github.io/aiohomematic/user/homeassistant_integration/) |
| **Installation** | See [Installation](#installation) below |
| **Alternative Setup (OpenCCU)** | [OpenCCU Wiki](https://github.com/OpenCCU/OpenCCU/wiki/HomeAssistant-Integration) |
| **Changelog** | [changelog.md](changelog.md) |
| **Issues** | [GitHub Issues](https://github.com/sukramj/aiohomematic/issues) |
| **Discussions** | [GitHub Discussions](https://github.com/sukramj/aiohomematic/discussions) |

## Related Integrations

| Integration | Use Case |
|-------------|----------|
| **This integration** | Local connection to CCU2/3, OpenCCU, Debmatic, Homegear |
| [Homematic(IP) Cloud](https://www.home-assistant.io/integrations/homematicip_cloud) | Cloud connection via Homematic IP Access Point |
| [Homematic IP Local (HCU)](https://github.com/Ediminator/hacs-homematicip-hcu) | Local connection to HmIP-HCU1 |

## Installation

### HACS (Recommended)

1. In Home Assistant, go to **HACS** > **Integrations** > **Explore & Download Repositories**
2. Search for "Homematic(IP) Local for OpenCCU" and install it
3. Restart Home Assistant when prompted

### Manual Installation

1. Copy the `custom_components/homematicip_local` directory to your Home Assistant `config/custom_components` directory
2. Restart Home Assistant

> **Note:** Manual installation does not support automatic updates.

After installation, add the integration via **Settings** > **Devices & Services** > **Add Integration** or use this button:

[![Add Integration][hainstallbadge]][hainstall]

## Requirements

### Supported Hardware

- CCU2/3
- OpenCCU
- Debmatic
- Homegear
- Home Assistant OS/Supervised with suitable add-on + communication device

> **Note:** This list is exhaustive. Third-party hubs that reimplement the CCU interfaces (XML-RPC, JSON-RPC, ReGa) are not supported, even if they appear to work. Issues reported against such a setup are closed without further assessment.

### Required Ports

| Interface | Purpose | Port | TLS Port |
|-----------|---------|------|----------|
| HomematicIP (HmIP-RF) | Wireless/wired HmIP devices | 2010 | 42010 |
| Homematic (BidCos-RF) | Classic wireless devices | 2001 | 42001 |
| Homematic Wired | Classic wired devices | 2000 | 42000 |
| Virtual Devices | Heating groups | 9292 | 49292 |
| JSON-RPC | Names and rooms | 80 | 443 |

### Authentication

- Admin privileges required on your CCU
- Allowed password characters: `A-Z`, `a-z`, `0-9`, `.!$():;#-`
- XML-RPC authentication recommended (Settings > Control Panel > Security)

For complete requirements and configuration details, see the [Full Documentation](https://sukramj.github.io/aiohomematic/user/homeassistant_integration/).

## Documentation

The complete documentation is available at **[sukramj.github.io/aiohomematic](https://sukramj.github.io/aiohomematic/)**:

| Topic | Link |
|-------|------|
| **Home Assistant Integration** | [User Guide](https://sukramj.github.io/aiohomematic/user/homeassistant_integration/) |
| **Actions Reference** | [Actions](https://sukramj.github.io/aiohomematic/user/features/homeassistant_actions/) |
| **Events Reference** | [Events](https://sukramj.github.io/aiohomematic/user/features/homeassistant_events/) |
| **Troubleshooting** | [Troubleshooting Guide](https://sukramj.github.io/aiohomematic/user/troubleshooting/homeassistant_troubleshooting/) |
| **Week Profiles** | [Week Profiles](https://sukramj.github.io/aiohomematic/user/features/week_profile/) |
| **Naming Conventions** | [Naming](https://sukramj.github.io/aiohomematic/user/advanced/homeassistant_naming/) |
| **Glossary** | [Glossary](https://sukramj.github.io/aiohomematic/reference/glossary/) |

### Additional Resources

- **Contributing Guide**: See [CONTRIBUTING.md](CONTRIBUTING.md) for development setup and contribution guidelines
- **Local Naming Documentation**: See [docs/naming.md](docs/naming.md)

## Device Configuration Panel

A built-in sidebar panel for editing Homematic device **MASTER parameters** directly from the Home Assistant UI.

### Features

- Browse all configurable devices grouped by interface
- View device details including reachability, RSSI, and firmware
- Edit MASTER paramset values per channel with auto-generated forms (sliders, toggles, dropdowns)
- Validate changes before writing to the device
- Reset parameters to factory defaults

### Enabling the Panel

1. Go to **Settings → Devices & Services → Homematic(IP) Local**
2. Click **Configure** on your integration entry
3. Navigate to **Advanced Options**
4. Enable **Device configuration panel**
5. The panel appears in the sidebar as **Homematic Config**

> **Note:** The panel requires admin access and is not visible to non-admin users.

## Blueprints

Ready-to-use automation blueprints are available in the [blueprints/automation](blueprints/automation) directory:

- Support for 2/4/6/8-button remotes
- Persistent notifications for unavailable devices
- Device reactivation helpers
- Error event handlers

Copy the desired blueprint files to your `config/blueprints/automation` directory.

The button blueprints (2/4/6/8-button) react to the selected device's **event entities**
(`event.*`, one per button channel). These are enabled by default; a button whose event
entity you have disabled or hidden cannot trigger the automation. They require Home
Assistant 2026.8 or newer.

The remaining blueprints are driven by the integration's **events** — see the
[Events Reference](https://sukramj.github.io/aiohomematic/user/features/homeassistant_events/)
for which parameters trigger which event. Note that CCU service messages (`CONFIG_PENDING`,
`UPDATE_PENDING`, …) are not events; they are available through the
`sensor.<instance>_hub_service_messages` sensor.

Community blueprints are welcome via pull request in [blueprints/community](blueprints/community).

## Companion Cards

Enhance your Home Assistant dashboard with custom cards designed for this integration:

| Card | Description |
|------|-------------|
| [Climate Schedule Card](https://github.com/SukramJ/homematicip_local_climate_schedule_card) | Visual editor for Homematic thermostat week profiles. Edit heating schedules directly from your dashboard. |

## Support and Contributing

| Resource | Link |
|----------|------|
| **Report Issues** | [GitHub Issues](https://github.com/sukramj/aiohomematic/issues) |
| **Discussions** | [GitHub Discussions](https://github.com/sukramj/aiohomematic/discussions) |
| **Documentation** | [sukramj.github.io/aiohomematic](https://sukramj.github.io/aiohomematic/) |
| **Contributing** | [CONTRIBUTING.md](CONTRIBUTING.md) |
| **AI Contribution Policy** | [AI_POLICY.md](AI_POLICY.md) |
| **Sponsor** | [GitHub Sponsors](https://github.com/sponsors/SukramJ) |

## Development

Parts of Homematic(IP) Local for OpenCCU are developed with agentic AI assistance, primarily [Claude Code](https://www.anthropic.com/claude-code). Submitted issues are also triaged and analysed with agentic help. Every change is still reviewed by a human maintainer and must pass the project's tests before it lands — AI accelerates the work, it does not replace the review gate. The rules for AI use in contributions are documented in [AI_POLICY.md](AI_POLICY.md).

## License

This project is licensed under the MIT License. See [LICENSE](LICENSE) for details.

[license-shield]: https://img.shields.io/github/license/SukramJ/homematicip_local.svg?style=for-the-badge
[release]: https://github.com/SukramJ/homematicip_local/releases
[releasebadge]: https://img.shields.io/github/v/release/SukramJ/homematicip_local?style=for-the-badge
[hainstall]: https://my.home-assistant.io/redirect/config_flow_start/?domain=homematicip_local
[hainstallbadge]: https://img.shields.io/badge/dynamic/json?style=for-the-badge&logo=home-assistant&logoColor=ccc&label=usage&suffix=%20installs&cacheSeconds=15600&url=https://analytics.home-assistant.io/custom_integrations.json&query=$.homematicip_local.total
[sponsorsbadge]: https://img.shields.io/github/sponsors/SukramJ?style=for-the-badge&label=GitHub%20Sponsors&color=green
[sponsors]: https://github.com/sponsors/SukramJ
[hacs]: https://hacs.xyz
[hacsbadge]: https://img.shields.io/badge/HACS-Default-green.svg?style=for-the-badge
