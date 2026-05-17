<p align="center">
  <img src="images/logo.png" alt="helios_easycontrol3 logo" width="160">
</p>

# Helios easyControls 3.0 — Home Assistant Integration

[![hacs_badge](https://img.shields.io/badge/HACS-Custom-orange.svg)](https://github.com/hacs/integration)

> **Repo:** [derdanilo/homeassistant_helios_easycontrol3](https://github.com/derdanilo/homeassistant_helios_easycontrol3)
> · **Integration domain:** `helios_easycontrol3`
> · **HACS folder name:** `helios_easycontrol3`

Native Home Assistant integration for Helios easyControls 3.0 ventilation
units (e.g. KWL 250 W). Talks directly to the device's local WebSocket
binary protocol — no cloud, no MQTT, no extra hub required.

> [!CAUTION]
> **Community project — please use with reasonable care.**
>
> This is a community-driven open-source project and is **not affiliated with,
> endorsed by, or supported by Helios Ventilatoren GmbH + Co. KG or Vallox**.
>
> The integration has been tested primarily against one hardware / firmware
> combination: **Helios KWL 250 W with easyControls firmware 1.0.25**. Other
> Helios / Vallox MV devices or firmware versions may behave differently.
>
> Please use reasonable caution when installing the integration and when
> enabling write-capable features. Make sure you understand what a setting does
> before changing the behaviour of your ventilation unit from Home Assistant.

> [!WARNING]
> **Take a Home Assistant backup before installing or updating.**
>
> Some entities write settings directly to the ventilation unit, including
> Cool Recovery, Vacation Mode and Main Power. Incorrect configuration can
> affect how your ventilation system operates. Please read the *Usage notes*
> section below before using these controls.

> [!NOTE]
> **AI-assisted development.** Significant parts of this project were developed
> with AI assistance (Anthropic Claude) on top of prior community work. The
> intended behaviour has been tested against real hardware, but edge cases or
> firmware-specific behaviour may still exist. Issues and pull requests are
> very welcome.

## Credits

This integration builds on earlier community work for the same device family:

- **[sanchosk/helios2mqtt](https://github.com/sanchosk/helios2mqtt)** —
  first community project exposing easyControls 3.0 readings over MQTT.
  Thanks to **@sanchosk** for sharing the initial work publicly.
- **[frawe/EasyControls3_homeassistant](https://github.com/frawe/EasyControls3_homeassistant)**
  — first Home Assistant integration on top of that work. Thanks to
  **@frawe** for packaging it up for HA users.

This integration is a hard fork of Frawe's v1.3.0, with the entity
surface significantly expanded and the polling / resilience layer
reworked.

### Existing Vallox integrations

I am aware of the existing Vallox-related work, including
[yozik04/vallox_websocket_api](https://github.com/yozik04/vallox_websocket_api)
and Home Assistant's built-in
[vallox integration](https://github.com/home-assistant/core/tree/dev/homeassistant/components/vallox).
Those integrations are useful and may be perfectly sufficient for basic
monitoring and control use cases.

For my own setup, however, I wanted broader and more explicit control over
the values exposed by the easyControls 3.0 interface than the existing
solutions provided for my use case. That is why I decided to take a closer
look at the local interface myself and build this integration as a more
complete, Home Assistant-native implementation for the controls and
entities I wanted to expose.

## Project notes

### How it was built

The mapping between the device's local interface and Home Assistant
entities was developed iteratively, building on the prior community
projects listed above. Refinement, additional entity coverage, the
resilience layer, the test probes, the documentation and the developer
tooling were worked out in iteration with an AI coding assistant
(Anthropic Claude). The intended behaviour was validated empirically
against a real device before release.

### Helios cooperation

I have reached out to Helios Ventilatoren GmbH + Co. KG and we'll see
what comes of it. Ideally they ship new firmware with a proper
documented local API.

This repository deliberately does not publish lower-level protocol
notes — the source code is the deliverable.

### Tested hardware

The integration has currently been verified against the following device:

- **Helios KWL 250 W**
- **easyControls firmware 1.0.25**

Other Helios / Vallox MV models with easyControls 3.0 use a comparable
local interface and may work as well, but this is not guaranteed. Please
open an issue with your model and firmware version if you try it — I'll
add results to the compatibility table below.

## Features

- **Native HA `fan` entity** as the primary control surface — on/off,
  preset mode (Home / Away / Boost / Individual), and speed (percentage)
  in a single entity. Works natively with voice assistants
  (Alexa, Google) and standard Lovelace fan cards.
- **40+ entities** for monitoring and additional control
  - Air temperatures (outdoor, supply, extract, exhaust)
  - Real fan RPMs (supply / extract)
  - Humidity, CO₂ (when sensor is present)
  - Individual sensor list (per Helios "Sensoren" subsection)
  - Per-mode setpoints as text-input numbers (fan power level %, supply
    air temperature)
  - Boost / Individual remaining-minutes countdown sensors
  - Filter status + change interval (1-12 months matching WebUI)
  - Bypass state, heat exchanger state, defrost state
  - Cool Recovery (with HA-side plug-confirmation safety, mirrors WebUI logic)
  - IO state sensors (bypass position, fan IO, heater IO, error flags)
  - Last power interruption timestamp (derived from current-up-time hours)
  - Operating time as "X yr Y d" combined display
- **Connectivity & resilience**
  - Snapshot persistence — entities keep last value during outages
  - Always-available reachability sensor
  - Connection stability % (rolling 60 min window)
  - Failure counters (consecutive + total)
- **Weekly schedule** — on/off switch in HA; the actual hour-by-hour
  programming is configured in the Helios WebUI.
- **Vacation mode** — on/off switch in HA; end-date and the mode that runs
  during vacation are configured in the Helios WebUI.
- **Filter reset button**
- **Multi-language UI** (English, German) — config flow, options flow and
  all entity names are localised

## Usage notes

### Writes need a moment to land

After changing a value via HA (e.g. setting Fan Power Level, switching Mode,
toggling Weekly Schedule), wait **about 3 seconds** before changing the next
value. The KWL needs time to process the write and our refresh chain
(0.4s + 2s + 5s) needs that time to confirm the new state back. If you
fire off multiple writes faster than that, the device may drop intermediate
values or our coordinator may briefly show stale state.

### Fan entity safety pattern

The native `fan.<device>_ventilation_unit` entity is the primary control
surface — it turns the whole unit on/off and switches preset modes. To
reduce the chance of accidental shutdowns from a stray tap in the
Lovelace UI, the bundled example dashboard
(`examples/dashboard_template.yaml`) configures it as:

```yaml
- type: entity
  entity: fan.<your_device>_ventilation_unit
  tap_action:
    action: more-info        # opens the details popup, no direct toggle
  hold_action:
    action: toggle
    confirmation:
      text: "Really toggle KWL main power?"
```

A normal tap opens the details popup (where you can deliberately toggle,
change preset, change speed), and only a long-press triggers a toggle —
and only after explicit confirmation. The same pattern is applied to
Cool Recovery. Note: this is dashboard-side only — automations and direct
service calls bypass it. If you want integration-side enforcement,
open an issue.

### Diagnostic / debug sensors

Some sensors are useful for debugging integration health but are noisy:

- `sensor.<device>_last_successful_update` — Timestamp of the last successful
  poll, updates **every poll cycle** (default 60s). **Disabled by default**
  because it spams the recorder and history graphs. Enable it manually in the
  entity settings if you need it for diagnosing poll cadence or connectivity
  hiccups.
- `binary_sensor.<device>_kwl_reachable` — **Always available** sensor that
  tracks whether the last poll attempt succeeded. `on` = last WebSocket call
  got a valid response, `off` = timeout or protocol error. Unlike all other
  entities, this one stays available even when the device is offline (that's
  the whole point — otherwise you couldn't tell it's offline). Use this for
  HA notifications about KWL downtime.
- `sensor.<device>_connection_stability` — Rolling % of successful polls in
  the last 60 attempts (1 hour at default 60s interval).
- `sensor.<device>_consecutive_failures` / `_total_failures` — Failure counters
  for monitoring.

## Installation

### Via HACS as a custom repository (recommended)

This integration is not (yet) in the official HACS default list. Add it as
a **custom repository**:

1. Open **HACS** in your Home Assistant sidebar.
2. In the top-right corner click the **three-dot menu (⋮)** → **Custom
   repositories**.
3. Fill in:
   - **Repository:** `https://github.com/derdanilo/homeassistant_helios_easycontrol3`
   - **Type:** `Integration`
   - Click **Add**.
4. Close the dialog. In the HACS list search for **"Helios easyControls 3.0"**.
5. Open it → click **Download** in the bottom-right → confirm the version
   (latest release tag) → **Download**.
6. **Restart Home Assistant** (Settings → System → Restart).
7. In HA: **Settings → Devices & Services → + Add Integration** → search for
   **"Helios easyControls 3.0"** → click it.
8. Enter the KWL's IP address (e.g. `192.168.1.42`) → Submit. Done.

HACS will track the GitHub repo and notify you when a new release is tagged
(see the *Releases* tab on GitHub) — one-click update from then on.

### Manual install (without HACS)

1. Download the latest release from GitHub.
2. Copy the **`custom_components/helios_easycontrol3/`** folder (everything
   below it including `__init__.py`, `manifest.json`, etc.) into your HA
   config directory under `custom_components/`. End result:
   `<config>/custom_components/helios_easycontrol3/__init__.py` etc.
3. Restart Home Assistant.
4. Add the integration via Settings → Devices & Services → + Add Integration
   → "Helios easyControls 3.0" → IP.

## Compatibility

| Device                                   | Status                       | Tested firmware |
| ---------------------------------------- | ---------------------------- | --------------- |
| Helios KWL 250 W                         | ✓ verified                   | 1.0.25          |
| Other Helios KWL with easyControls 3.0   | likely works (same protocol) | —               |
| Vallox MV / MV-E with easyControls cloud | may work, untested           | —               |

## Logo / Brand registration

The artwork in `images/` was adopted from the existing `helios` entry in
the official [home-assistant/brands](https://github.com/home-assistant/brands)
repo (same device family). It renders fine on GitHub (READMEs, repo card),
but **does not show up in the Home Assistant UI for this integration** —
because HA and HACS both look up logos strictly by integration domain
(public CDN at `brands` dot `home-assistant.io`, path `/<domain>/icon.png`),
and the domain `helios_easycontrol3` does not have its own entry there yet.

Anyone who wants the HA UI icon can submit a 5-minute PR to the brands
repo themselves — fork it, add a `custom_integrations/helios_easycontrol3/`
folder with the 4 PNGs from this repo's `images/`, open the PR.

## Documentation

- [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) — Home Assistant module
  layout (config flow, coordinator, entity platforms) and data flow.
- [docs/CHANGELOG.md](docs/CHANGELOG.md) — version history.
- [docs/CONTRIBUTING.md](docs/CONTRIBUTING.md) — how to add new entities.

The full list of entities the integration creates is visible inside Home
Assistant itself once the integration is installed (Settings -> Devices &
Services -> Helios easyControls 3.0 -> Entities).

## Examples

Ready-to-adapt templates in `examples/`:

- **`dashboard_template.yaml`** — full 4-tab Lovelace dashboard (Overview /
  Modes / Schedule / Diagnostics) using Mushroom cards, including the
  Main-Power safety pattern.
- **`automation_cooker_hood_boost.yaml`** — boost ventilation while the
  cooker hood is running, with follow-up ventilation and automatic restore
  of the previous mode. Needs a power sensor on the cooker hood plug and a
  small `input_text` helper to remember the previous mode (see comments in
  the file for setup).

## Privacy when reporting issues

The integration exposes local diagnostic values such as the KWL's IP
address, gateway, subnet mask, UUID and serial number. When opening a
GitHub issue or posting screenshots/logs, **please redact those values**
before sharing — they can identify your network and device.

## Disclaimer

This project is provided in good faith as a community-developed Home
Assistant integration for Helios easyControls 3.0 devices.

It is **not affiliated with, endorsed by, or supported by Helios
Ventilatoren GmbH + Co. KG or Vallox**. All product and company names are
trademarks of their respective holders. Use of any names in this project is
for identification and interoperability purposes only.

The software is provided as-is under the terms of the MIT license. While it
has been tested on real hardware, it may still contain bugs or behave
differently on unsupported devices, firmware versions or local
configurations.

You are responsible for deciding whether this integration is suitable for
your own Home Assistant setup and ventilation unit. Please keep backups and
use extra care with write-capable entities such as Main Power, Vacation Mode
and Cool Recovery.

The integration talks only to the device on your local network — no data
leaves your LAN.

See the *Helios cooperation* section above regarding ongoing outreach to the
manufacturer.

## License

MIT — see [LICENSE](LICENSE).
