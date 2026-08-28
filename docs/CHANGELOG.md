# Changelog

## v1.1.3 — Example dashboard: no more accidental shutdowns from the mode buttons

### Fixed

- **Example dashboard: tapping the icon of a mode button switched the unit
  off** instead of changing the preset. Cards with an icon action fall back
  to Home Assistant's default action for the entity's domain when
  `icon_tap_action` is not set — and for `fan` that default is `toggle`.
  The icon handler also stops event propagation, so the card's own
  `tap_action` (the preset change) never ran. On the large mode tiles the
  icon is the most likely tap target, which made the unit appear to shut
  down at random on mode changes, while the very same change made from the
  entity's more-info dialog always worked.
  Every card in `examples/dashboard_template.yaml` that is bound to a
  toggleable entity now sets `icon_tap_action` explicitly.
- This was the remaining cause behind the shutdown reports that v1.1.2 did
  not fully resolve. The integration-side guards shipped in v1.1.2 (verify
  the real device state before sending a power command, rate-limited writes)
  are unaffected and stay in place — they simply could not prevent a
  deliberate `fan.toggle` coming from the dashboard.

### New

- Example dashboard: a **"select operating mode"** card directly below the
  four quick-select tiles. It opens the fan entity's more-info dialog, where
  all presets and the fan speed can be set, and shows the currently active
  preset as its subtitle.

### Docs

- README: new section *"Custom cards: always set `icon_tap_action`"* under
  the accidental-shutdown protection notes.
- README: Helios KWL 470 W ET (firmware 1.0.23) added to the tested-hardware
  and compatibility tables — community-confirmed on v1.1.2.

### Notes

- No changes to the integration code in this release; only the bundled
  example dashboard and the documentation. Updating is worthwhile if you
  based your dashboard on the template.

## v1.1.2 — No more spurious unit shutdowns; rate-limited writes; instant UI feedback

### Fixed

- **Unit could physically cycle OFF→ON when switching modes from HA**
  (most visible when switching to Home). Two causes, both fixed:
  - The on/off state was derived incorrectly: the unit reports several
    internal modes (e.g. defrosting) that were misread as "switched
    off". HA then wrapped preset changes into `fan.turn_on`, which
    re-sent the power-on command into the *running* unit — and that
    command resets the unit's state machine (fans audibly cycle
    off/on). On/off is now derived the same way the manufacturer's
    WebUI does it: only the real "off" state counts as off.
  - `fan.turn_on` / `fan.turn_off` now verify the actual device state
    with a fresh read right before sending and skip the power command
    entirely unless the state really has to change.
- **Slow state updates after writes** — the post-write refresh chain
  (0.4 / 1.4 / 3.4 s) was silently swallowed by a coordinator
  debouncer; mode changes could take up to a minute to show in HA.
  Refreshes now run as designed; changes reflect within ~4 s.
- `time` entities: a device value of 1440 min (24:00) showed as
  "unknown"; it is now clamped to 23:59.
- Batch reads are mapped via the echoed register address instead of
  by position (robust against skipped addresses).

### New

- **Write rate limiter** — every UI interaction is accepted instantly;
  delivery to the unit is spaced ≥2 s with latest-wins coalescing per
  control. Rapid taps can no longer stress the unit's embedded
  controller (which could previously reset itself under write bursts).
- **Optimistic fan state** — preset/power flip immediately in the UI
  and only snap back to the device-reported state if the unit hasn't
  confirmed within ~15 s. Buttons never feel "dead" anymore.
- **`date.<device>_filter_change_date`** — the last-filter-change date
  is now directly settable, e.g. to correct an accidental filter reset.
- **Write debug logging** — enable debug logging on the integration to
  trace exactly what is sent to the unit and when.

### Changed

- Example dashboard: filter-reset card hardened — tapping the icon can
  no longer trigger the reset without the confirmation dialog
  (`icon_tap_action: none`); new card for the filter date entity;
  note about entity slugs on renamed devices.

## v1.1.1 — Hotfix

- Fixed a truncated method name in the number platform that broke
  setpoint writes.
- Updated the example dashboard template.

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
