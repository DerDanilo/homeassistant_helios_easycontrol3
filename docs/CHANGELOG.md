# Changelog

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
