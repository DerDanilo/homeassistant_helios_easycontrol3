# Changelog

## v1.1.0 — Fan platform replaces Main Power switch + Mode select

### New

- **`fan` platform entity** — `fan.<device>_ventilation_unit` is now the
  primary control surface for the unit: on/off, preset mode
  (Home/Away/Boost/Individual) and speed (per-mode fan power level
  percentage) all in one entity. Works natively with voice assistants
  (Alexa, Google) and standard Lovelace fan cards.
- **Remaining-time sensors** for time-limited modes:
  - `sensor.<device>_boost_remaining` — minutes left while Boost is active
  - `sensor.<device>_individual_remaining` — minutes left while Individual is active
  - Both show `0` when the mode is not currently running.

### BREAKING

- **`switch.<device>_main_power` removed.** Replaced by the on/off
  behaviour of the new fan entity.
- **`select.<device>_mode` removed.** Replaced by the preset_mode of the
  new fan entity.

If you had automations or dashboard cards referencing either of these
entities, point them at `fan.<device>_ventilation_unit` instead:
- Power on/off: `fan.turn_on` / `fan.turn_off` service calls.
- Mode change: `fan.set_preset_mode` with `preset_mode: Home` / `Away`
  / `Boost` / `Individual`.

The per-mode `number.*_fan_power_level_*` and
`number.*_supply_air_target_*` entities are unchanged and remain the
text-input way to set the saved per-mode setpoints precisely.

## v1.0.0 — First production release

First public release of the `helios_easycontrol3` Home Assistant integration.

### Entities

- Air temperatures: outdoor, supply, extract, exhaust
- Fan RPMs: supply, extract
- Internal + external humidity / CO2 sensor readings (dynamically listed)
- Operating mode select (Home / Away / Boost / Individual)
- Per-mode setpoints: fan power level and supply-air target
- Filter status, change interval (1-12 months), reset button
- Bypass state, heat exchanger state, defrost state
- Cool Recovery with HA-side plug-confirmation safety flow
- IO state diagnostic sensors (bypass position, fan IO, heater IO, error flags)
- Last power interruption timestamp
- Combined operating-time display ("X yr Y d")
- Main Power switch
- Weekly Schedule on/off switch (hour-by-hour programming stays in the
  Helios WebUI)
- Vacation Mode on/off switch (end-date / mode are set in the WebUI)

### Resilience

- Snapshot persistence: entities keep their last good value during outages
- Always-available reachability sensor (`binary_sensor.*_kwl_reachable`)
- Connection-stability % over a rolling 60-minute window
- Failure counters (consecutive + total)

### Multi-language

- English and German for config flow, options flow and all entity names.
