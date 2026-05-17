# Architecture — helios_easycontrol3 integration

## Module overview

```
custom_components/helios_easycontrol3/
├── __init__.py            # async_setup_entry / async_unload_entry
├── manifest.json          # HACS / HA manifest
├── const.py               # DOMAIN, service names, defaults
├── addresses.py           # All A_CYC_* addresses + conversion helpers
├── device_list.py         # Lookup tables for MACHINE_MODEL / TYPE
├── client.py              # WebSocket client (frame builder, read/write)
├── coordinator.py         # DataUpdateCoordinator + KWLSnapshot + resilience
├── entity.py              # CoordinatorEntity base class
├── config_flow.py         # UI flow for adding a KWL
├── sensor.py              # Sensors (temperatures, RPM, diagnostics, connectivity)
├── binary_sensor.py       # Binary sensors (bypass, defrost, KWL reachable)
├── number.py              # Numeric inputs (fan power levels, supply-air targets, filter interval)
├── switch.py              # Switches (main power, weekly schedule, vacation, cool recovery + plug confirmed)
├── select.py              # KWL operating mode (Home / Away / Boost / Individual)
├── time.py                # Time inputs (Boost / Individual duration)
├── button.py              # Filter-reset button
└── translations/          # de / en JSON for config flow, options flow and entity names
```

## Data flow

```
                 +----------------------+
                 |  Helios KWL (device) |
                 |  ws://<KWL-IP>:80/   |
                 +----------+-----------+
                            | WebSocket binary frames
                 +----------v-----------+
                 |  client.py           |  Frame builder with checksum,
                 |  EasyControls3Client |  Read-Tables / Read-Data /
                 |                      |  Write-Data
                 +----------+-----------+
                            | raw bytes
                 +----------v-----------+
                 |  coordinator.py      |  Parse Table 0,
                 |  DataUpdateCoord.    |  high-address reads,
                 |  +----------------+  |  connectivity tracking,
                 |  |  KWLSnapshot   |  |  snapshot persistence
                 |  |   (dataclass)  |  |
                 |  +----------------+  |
                 +----------+-----------+
                            | snapshot
       +------------+-------+------+------------+
       v            v       v      v            v
   sensor.py   binary_   number  switch     select/time/
                sensor.py .py    .py        button.py
```

## Resilience design

### Snapshot persistence

On an update failure (`UpdateFailed`), the **last successful snapshot is
not overwritten**. Entities keep access to the old values and do not flip
to `unavailable`, unless they have `always_available=False` and there is
no snapshot yet at all.

### Connectivity tracking

The coordinator maintains 4 metrics in the snapshot:

| Metric | Sensor | Meaning |
|---|---|---|
| `is_currently_reachable` | `binary_sensor.kwl_reachable` | Last read succeeded (true/false) |
| `last_successful_update` | `sensor.last_successful_update` | Timestamp |
| `stability_pct` | `sensor.connection_stability` | % success in rolling window (60 slots) |
| `consecutive_failures` | `sensor.consecutive_failures` | Current failure-streak counter |
| `total_failures` | `sensor.total_failures` | Cumulative since HA start |

These sensors are `always_available=True` — they report their own status
even when the KWL is not reachable.

### Rolling window

Default: 60 slots x 60s scan interval = **1 hour** stability window.
Configurable via `STABILITY_WINDOW_SIZE` in `coordinator.py`.

## Polling strategy

Per update cycle (default 60s):

1. **Read Table 0** (1x WebSocket -> ~1410 bytes)
   - Provides: current fan power level %, temperatures, RH, CO2, filter
     date, status flags (state / boost / fireplace timer, on/off).

2. **Read high-address block** (1x WebSocket -> ~30 addresses batched
   into a single READ_DATA)
   - Provides: speed settings per mode, air-temp targets, IO state,
     RPMs, bypass, cell state, uptime, cloud status, schedule-enable,
     filter interval, individual RH / CO2 sensor slot readings.

3. **Static device info** (only once on the first successful update)
   - SW version, UUID, IP / gateway / netmask, sidedness, sensor slot
     presence flags.

-> **One update = 2 WebSocket exchanges**, not one per entity. With ~50
   entities that's a 25x reduction in load on the device.

## Writes

On set actions (number / switch / select):

1. `client.write_variable(addr, value)` sends a WRITE_DATA frame.
2. `coordinator.request_refresh_after_write()` waits 0.4s, then triggers a
   refresh, followed by two more delayed refreshes (2s + 5s in the
   background) to catch slower-confirming state changes.

Air-temperature targets are **converted from Celsius to K x 100 before
writing** (see `addresses.air_temp_celsius_to_k100`).

## Error handling

| Error | Handled in | Effect |
|---|---|---|
| WebSocket connect failed | `coordinator._async_update_data` | UpdateFailed, snapshot kept, connectivity sensor shows offline |
| Frame checksum mismatch | `client._exchange` | EasyControlsProtocolError, then UpdateFailed |
| `WS_REPLY_ACK` missing after WRITE | `client.write_variables` | EasyControlsProtocolError, service call surfaces error in HA UI |
| `asyncio.CancelledError` | `coordinator._async_update_data` | propagated (NEVER swallow — event loop hangs otherwise) |
| Address > 0xFFFF (16-bit overflow) | `client._build_frame` | ValueError at encoding time |

## Extensibility

Add a new variable:

1. Define the address in `addresses.py` (`ADDR_NEW_VAR`).
2. Add a field to `KWLSnapshot` in `coordinator.py`.
3. Include it in `_HIGH_ADDR_POLL` (for periodic reads).
4. Map it in `_apply_high_address_values()`.
5. Define the entity (`_SensorDef` / `_NumberDef` / etc.) in the matching
   platform file.

