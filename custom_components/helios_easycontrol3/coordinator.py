"""
DataUpdateCoordinator for the KWL.

Polls all values centrally (instead of each entity individually). Saves 90% of
WebSocket connections, and on update failures keeps the last successful
snapshot visible (resilience).

Tracked connectivity metrics:
  - last_successful_update     (timestamp of last successful read)
  - consecutive_failures       (current failure streak)
  - stability_pct              (% successful reads in last 60 minutes)
  - is_currently_reachable     (bool — instant status)
"""

from __future__ import annotations

import asyncio
import datetime as dt
import logging
import struct
from collections import deque
from dataclasses import dataclass, field

from dateutil.relativedelta import relativedelta
from homeassistant.core import HomeAssistant
from homeassistant.helpers.storage import Store
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from . import addresses as A
from .client import EasyControls3Client, EasyControlsProtocolError
from .const import DEFAULT_SCAN_INTERVAL_SECONDS, DOMAIN
from .device_list import model_name, type_name

LOGGER = logging.getLogger(__name__)

# Rolling window for stability calculation (60 min @ 60s scan = 60 slots)
STABILITY_WINDOW_SIZE = 60


def _data_to_celsius(buf: bytes, word_index: int) -> float:
    """Word index -> Celsius (Helios K×100 format)."""
    raw = buf[word_index * 2] * 256 + buf[word_index * 2 + 1]
    return round(raw / 100 - 273.15, 1)


@dataclass
class KWLSnapshot:
    """Unified view of the current device state."""

    # --- Device info (cached, loaded once) ---
    serial_number: int | None = None
    machine_model_idx: int | None = None
    machine_type_idx: int | None = None
    sw_version: str | None = None
    uuid: str | None = None
    sidedness: int | None = None
    rh_sensor_count: int = 0
    co2_sensor_count: int = 0
    ip_address: str | None = None
    gateway: str | None = None
    netmask: str | None = None

    # --- Live values (Table 0) ---
    is_on: bool | None = None
    state_code: int = 0
    boost_timer: int = 0
    fireplace_timer: int = 0
    current_fan_speed: int | None = None
    home_speed_buf: int | None = None
    away_speed_buf: int | None = None
    boost_speed_buf: int | None = None
    intensive_duration_min: int | None = None
    outdoor_temp: float | None = None
    supply_temp: float | None = None
    extract_temp: float | None = None
    exhaust_temp: float | None = None
    rh: int | None = None
    co2: int | None = None
    filter_interval_days: int | None = None
    filter_changed_date: dt.date | None = None
    filter_due_date: dt.date | None = None

    # --- High-address values ---
    home_speed: int | None = None
    away_speed: int | None = None
    boost_speed: int | None = None
    individual_supply_speed: int | None = None
    individual_extract_speed: int | None = None
    individual_duration_min: int | None = None
    # Air temp targets stored as Celsius (K×100 conversion already done here)
    home_air_temp_target: float | None = None
    away_air_temp_target: float | None = None
    boost_air_temp_target: float | None = None
    individual_air_temp_target: float | None = None
    # NOTE: per-mode RH/CO2 control toggles are deliberately NOT exposed.
    # They are not visible in the Helios WebUI; flipping them blindly can
    # create non-obvious behavior. Use the global thresholds in the WebUI
    # Konfiguration page instead.
    cool_recovery_enabled: bool | None = None       # raw value of addr 20516
    vacation_active: bool | None = None              # addr 46021 (TIMED_FUNCTION_ENABLED)
    # plug_confirmed mirrors the WebUI safety prompt ("Stopfen entfernt? Ja/Nein"):
    # True = confirmed (cool recovery is unlockable), False = not confirmed yet
    plug_confirmed: bool = False
    filter_interval_setting: int | None = None     # in days (Helios native)
    bypass_locked: bool | None = None
    partial_bypass: bool | None = None
    relay_mode: int | None = None
    measured_supply_rpm: int | None = None
    measured_extract_rpm: int | None = None
    defrosting: bool | None = None
    weekly_timer_enabled: bool | None = None
    cell_state: int | None = None
    total_uptime_years: int | None = None
    total_uptime_hours: int | None = None
    cloud_status: int | None = None
    enabled_state: bool | None = None      # ADDR_ENABLED (4626)
    # New: derived diagnostics
    current_up_time_hours: int | None = None    # hours since last power-on
    last_power_on: dt.datetime | None = None    # derived: now() - current_up_time
    operating_time_str: str | None = None       # formatted "X yr Y d"
    # Individual sensor slot values (populated by periodic poll)
    rh_slot_values: dict[int, int | None] = field(default_factory=dict)
    co2_slot_values: dict[int, int | None] = field(default_factory=dict)
    # IO state values (raw)
    io_bypass: int | None = None
    io_supply_fan: int | None = None
    io_extract_fan: int | None = None
    io_heater: int | None = None
    io_extra_heater: int | None = None
    io_error: int | None = None

    # --- Connectivity / resilience ---
    last_successful_update: dt.datetime | None = None
    consecutive_failures: int = 0
    is_currently_reachable: bool = True
    stability_pct: float = 100.0           # % success in last N attempts
    total_failures: int = 0                # cumulative since start
    total_attempts: int = 0                # cumulative since start

    raw_table0_len: int = 0


# Periodic polls — high-address variables read on every update cycle
_HIGH_ADDR_POLL: tuple[int, ...] = (
    A.ADDR_HOME_SPEED_SETTING, A.ADDR_AWAY_SPEED_SETTING, A.ADDR_BOOST_SPEED_SETTING,
    A.ADDR_FIREPLACE_SUPP_FAN, A.ADDR_FIREPLACE_EXTR_FAN, A.ADDR_FIREPLACE_TIME,
    A.ADDR_HOME_AIR_TEMP_TARGET, A.ADDR_AWAY_AIR_TEMP_TARGET,
    A.ADDR_BOOST_AIR_TEMP_TARGET, A.ADDR_FIREPLACE_AIR_TEMP_TARGET,
    A.ADDR_FILTER_CHANGE_INTERVAL, A.ADDR_BYPASS_LOCKED, A.ADDR_PARTIAL_BYPASS,
    A.ADDR_COOLRECOVERY_DISABLED,
    A.ADDR_TIMED_FUNCTION_ENABLED,
    A.ADDR_RELAY_MODE,
    # Fan RPMs
    A.ADDR_SUPP_FAN_SPEED, A.ADDR_EXTR_FAN_SPEED,
    A.ADDR_BOOST_TIME,
    # 4xxx diagnostics
    A.ADDR_DEFROSTING, A.ADDR_WEEKLY_TIMER_ENABLED, A.ADDR_CELL_STATE,
    A.ADDR_TOTAL_UP_TIME_YEARS, A.ADDR_TOTAL_UP_TIME_HOURS,
    A.ADDR_CURRENT_UP_TIME_HOURS, A.ADDR_CLOUD_STATUS,
    # External humidity / CO2 sensor slots - polled regularly so values update
    *A.ADDR_RH_SENSORS, *A.ADDR_CO2_SENSORS,
    # IO state addresses (bypass position, fan IO, heater IO, error)
    A.ADDR_IO_BYPASS, A.ADDR_IO_SUPPLY_FAN, A.ADDR_IO_EXTRACT_FAN,
    A.ADDR_IO_HEATER, A.ADDR_IO_EXTRA_HEATER, A.ADDR_IO_ERROR,
    A.ADDR_ENABLED,
)

# Device info — loaded once
_DEVICE_INFO_ADDRS: tuple[int, ...] = (
    *A.ADDR_APPL_SW_VERSION_PARTS,
    *A.ADDR_UUID,
    A.ADDR_SIDEDNESS,
    A.ADDR_IP_ADDRESS_1, A.ADDR_IP_ADDRESS_2,
    A.ADDR_GW_ADDRESS_1, A.ADDR_GW_ADDRESS_2,
    A.ADDR_MASK_ADDRESS_1, A.ADDR_MASK_ADDRESS_2,
    *A.ADDR_RH_SENSORS, *A.ADDR_CO2_SENSORS,
)


def _ip_from_words(w1: int, w2: int) -> str:
    """2 words -> IPv4 dotted decimal (high-low per word)."""
    return f"{(w1>>8)&0xFF}.{w1&0xFF}.{(w2>>8)&0xFF}.{w2&0xFF}"


def _format_uuid(words: list[int]) -> str:
    """8 words -> UUID 8-4-4-4-12 hex. Empty on error."""
    if len(words) != 8:
        return ""
    raw = b"".join(struct.pack(">H", w) for w in words)
    h = raw.hex().upper()
    return f"{h[0:8]}-{h[8:12]}-{h[12:16]}-{h[16:20]}-{h[20:32]}"


class EasyControls3Coordinator(DataUpdateCoordinator[KWLSnapshot]):
    """Central coordinator per KWL.

    Resilience: on update failures the last successful snapshot is kept and
    returned with updated connectivity metrics.
    """

    def __init__(self, hass: HomeAssistant, host: str,
                 scan_interval: int = DEFAULT_SCAN_INTERVAL_SECONDS):
        super().__init__(
            hass,
            LOGGER,
            name=f"{DOMAIN} {host}",
            update_interval=dt.timedelta(seconds=scan_interval),
        )
        self.client = EasyControls3Client(host)
        self.host = host
        self._device_info_loaded = False
        self._snapshot = KWLSnapshot()
        self._stability_window: deque[bool] = deque(maxlen=STABILITY_WINDOW_SIZE)
        # Persistent storage for HA-internal state (currently: plug_confirmed)
        self._store: Store = Store(hass, version=1, key=f"{DOMAIN}_{host}_state")
        self._storage_loaded = False
        # Track previous cool_recovery state for transition detection
        self._prev_cool_recovery: bool | None = None

    # ----- Persistent storage (plug_confirmed) -----------------------------
    async def _load_storage_once(self) -> None:
        if self._storage_loaded:
            return
        data = await self._store.async_load()
        if data and isinstance(data, dict):
            self._snapshot.plug_confirmed = bool(data.get("plug_confirmed", False))
        self._storage_loaded = True

    async def _save_storage(self) -> None:
        await self._store.async_save({"plug_confirmed": self._snapshot.plug_confirmed})

    async def set_plug_confirmed(self, value: bool) -> None:
        """Set HA-side plug confirmation flag and persist."""
        self._snapshot.plug_confirmed = bool(value)
        await self._save_storage()
        self.async_update_listeners()

    # ----- Connectivity update ----------------------------------------------
    def _record_attempt(self, success: bool) -> None:
        s = self._snapshot
        s.total_attempts += 1
        self._stability_window.append(success)
        if success:
            s.last_successful_update = dt.datetime.now(dt.timezone.utc)
            s.consecutive_failures = 0
            s.is_currently_reachable = True
        else:
            s.consecutive_failures += 1
            s.total_failures += 1
            s.is_currently_reachable = False
        if self._stability_window:
            ok_count = sum(1 for x in self._stability_window if x)
            s.stability_pct = round(100.0 * ok_count / len(self._stability_window), 1)

    # ----- Main loop --------------------------------------------------------
    async def _async_update_data(self) -> KWLSnapshot:
        """Main loop: Table 0 + high-address block.
        On errors: keep old snapshot, update connectivity metrics, raise
        UpdateFailed (HA marks entities as unavailable for non-always_available).
        """
        try:
            await self._load_storage_once()
            if not self._device_info_loaded:
                if await self._load_device_info():
                    self._device_info_loaded = True

            buf = await self.client.read_table(0)
            self._parse_table0(buf)

            high = await self.client.read_variables(list(_HIGH_ADDR_POLL))
            self._apply_high_address_values(high)

            await self._sync_plug_confirmed_with_cool_recovery()

            self._record_attempt(success=True)
            return self._snapshot

        except asyncio.CancelledError:
            raise
        except EasyControlsProtocolError as err:
            self._record_attempt(success=False)
            LOGGER.warning("Protocol error (consecutive_failures=%d): %s",
                           self._snapshot.consecutive_failures, err)
            raise UpdateFailed(f"Protocol error: {err}") from err
        except Exception as err:
            self._record_attempt(success=False)
            LOGGER.warning("Update error (consecutive_failures=%d): %s",
                           self._snapshot.consecutive_failures, err)
            raise UpdateFailed(f"Error: {err}") from err

    # ----- Parse Table 0 ----------------------------------------------------
    def _parse_table0(self, buf: bytes) -> None:
        s = self._snapshot
        s.raw_table0_len = len(buf)

        if s.machine_model_idx is None:
            s.machine_model_idx = buf[A.ADDR_MACHINE_MODEL * 2 + 1]
            s.machine_type_idx = buf[A.ADDR_MACHINE_TYPE * 2 + 1]
            s.serial_number = (
                buf[A.ADDR_SERIAL_NUMBER_MSW * 2] * 16777216
                + buf[A.ADDR_SERIAL_NUMBER_MSW * 2 + 1] * 65536
                + buf[A.ADDR_SERIAL_NUMBER_LSW * 2] * 256
                + buf[A.ADDR_SERIAL_NUMBER_LSW * 2 + 1]
            )

        s.state_code = buf[A.BUF_STATE_BYTE]
        s.boost_timer = buf[A.BUF_BOOST_TIMER_BYTE]
        s.fireplace_timer = buf[A.BUF_FIREPLACE_TIMER_BYTE]
        s.is_on = bool(buf[A.BUF_ON_OFF_BYTE] == 0)

        s.current_fan_speed = buf[A.BUF_FAN_SPEED_BYTE]
        s.home_speed_buf = buf[A.BUF_AT_HOME_FAN_SPEED_BYTE]
        s.away_speed_buf = buf[A.BUF_AWAY_FAN_SPEED_BYTE]
        s.boost_speed_buf = buf[A.BUF_INTENSIVE_FAN_SPEED_BYTE]
        s.intensive_duration_min = buf[A.BUF_INTENSIVE_DURATION_BYTE]

        s.outdoor_temp = _data_to_celsius(buf, 67)
        s.supply_temp = _data_to_celsius(buf, 69)
        s.extract_temp = _data_to_celsius(buf, 65)
        s.exhaust_temp = _data_to_celsius(buf, 66)

        s.rh = buf[A.BUF_RH_BYTE]
        co2 = (buf[A.BUF_CO2_HIGH_BYTE] << 8) | buf[A.BUF_CO2_LOW_BYTE]
        # WebUI shows '0 ppm' when no sensor; match that behavior for HA
        s.co2 = 0 if co2 == 0xFFFF else co2

        # Filter from Table 0 (date works, interval comes from high address)
        try:
            year = 2000 + buf[A.BUF_FILTER_CHANGED_YEAR_BYTE]
            month = buf[A.BUF_FILTER_CHANGED_MONTH_BYTE]
            day = buf[A.BUF_FILTER_CHANGED_DAY_BYTE]
            s.filter_changed_date = dt.date(year, month, day)
        except (ValueError, TypeError):
            s.filter_changed_date = None

        # Sensor count: external slots populated + internal sensor (internal
        # always counts as #1 if plausible value present). External slot values
        # are populated by the periodic high-address poll.
        ext_rh = sum(1 for v in s.rh_slot_values.values() if v is not None)
        internal_rh = 1 if (s.rh is not None and 0 < s.rh <= 100) else 0
        s.rh_sensor_count = ext_rh + internal_rh
        ext_co2 = sum(1 for v in s.co2_slot_values.values() if v is not None)
        # CO2 internal: we set 0 when 0xFFFF, so check explicitly for >0
        internal_co2 = 1 if (s.co2 is not None and 0 < s.co2 < 5000) else 0
        s.co2_sensor_count = ext_co2 + internal_co2

        # filter_interval_days set from high-address read (see _apply_high_address_values)
        if s.filter_changed_date and s.filter_interval_days and s.filter_interval_days > 0:
            s.filter_due_date = s.filter_changed_date + relativedelta(
                days=int(s.filter_interval_days)
            )
        else:
            s.filter_due_date = None

    # ----- Apply high-address reads -----------------------------------------
    def _apply_high_address_values(self, vals: dict[int, int]) -> None:
        """Expects: {addr: value}. None for missing values."""
        s = self._snapshot

        def _b(addr):
            v = vals.get(addr)
            return None if v is None else bool(v)

        def _temp(addr):
            v = vals.get(addr)
            return None if v is None else A.air_temp_k100_to_celsius(v)

        # Setpoints
        s.home_speed = vals.get(A.ADDR_HOME_SPEED_SETTING)
        s.away_speed = vals.get(A.ADDR_AWAY_SPEED_SETTING)
        s.boost_speed = vals.get(A.ADDR_BOOST_SPEED_SETTING)
        s.individual_supply_speed = vals.get(A.ADDR_FIREPLACE_SUPP_FAN)
        s.individual_extract_speed = vals.get(A.ADDR_FIREPLACE_EXTR_FAN)
        s.individual_duration_min = vals.get(A.ADDR_FIREPLACE_TIME)

        # Air temp: K×100 -> Celsius CONVERTED
        s.home_air_temp_target = _temp(A.ADDR_HOME_AIR_TEMP_TARGET)
        s.away_air_temp_target = _temp(A.ADDR_AWAY_AIR_TEMP_TARGET)
        s.boost_air_temp_target = _temp(A.ADDR_BOOST_AIR_TEMP_TARGET)
        s.individual_air_temp_target = _temp(A.ADDR_FIREPLACE_AIR_TEMP_TARGET)

        s.vacation_active = _b(A.ADDR_TIMED_FUNCTION_ENABLED)

        # Cool recovery raw value: 0 = off, 1 = on (no inversion)
        cr_raw = vals.get(A.ADDR_COOLRECOVERY_DISABLED)
        s.cool_recovery_enabled = None if cr_raw is None else bool(cr_raw)

        s.filter_interval_setting = vals.get(A.ADDR_FILTER_CHANGE_INTERVAL)
        s.filter_interval_days = s.filter_interval_setting   # same concept
        s.bypass_locked = _b(A.ADDR_BYPASS_LOCKED)
        s.partial_bypass = _b(A.ADDR_PARTIAL_BYPASS)
        s.relay_mode = vals.get(A.ADDR_RELAY_MODE)

        # RPMs from the correct addresses (4361/4362, NOT 32777/32778!)
        s.measured_supply_rpm = vals.get(A.ADDR_SUPP_FAN_SPEED)
        s.measured_extract_rpm = vals.get(A.ADDR_EXTR_FAN_SPEED)

        s.defrosting = _b(A.ADDR_DEFROSTING)
        s.weekly_timer_enabled = _b(A.ADDR_WEEKLY_TIMER_ENABLED)
        s.cell_state = vals.get(A.ADDR_CELL_STATE)
        s.total_uptime_years = vals.get(A.ADDR_TOTAL_UP_TIME_YEARS)
        s.total_uptime_hours = vals.get(A.ADDR_TOTAL_UP_TIME_HOURS)
        s.cloud_status = vals.get(A.ADDR_CLOUD_STATUS)
        s.enabled_state = _b(A.ADDR_ENABLED)

        # CURRENT_UP_TIME_HOURS = hours since last power-on
        s.current_up_time_hours = vals.get(A.ADDR_CURRENT_UP_TIME_HOURS)
        if s.current_up_time_hours is not None and s.current_up_time_hours >= 0:
            s.last_power_on = dt.datetime.now(dt.timezone.utc) - dt.timedelta(
                hours=int(s.current_up_time_hours)
            )
        else:
            s.last_power_on = None

        # Operating time as "X yr Y d" combining years + (hours within year / 24)
        years = s.total_uptime_years
        hours_this_year = s.total_uptime_hours
        if years is not None and hours_this_year is not None:
            days = int(hours_this_year // 24)
            s.operating_time_str = f"{int(years)} yr {days} d"
        elif years is not None:
            s.operating_time_str = f"{int(years)} yr"
        else:
            s.operating_time_str = None

        # IO state values (raw integers from device IO subsystem)
        s.io_bypass = vals.get(A.ADDR_IO_BYPASS)
        s.io_supply_fan = vals.get(A.ADDR_IO_SUPPLY_FAN)
        s.io_extract_fan = vals.get(A.ADDR_IO_EXTRACT_FAN)
        s.io_heater = vals.get(A.ADDR_IO_HEATER)
        s.io_extra_heater = vals.get(A.ADDR_IO_EXTRA_HEATER)
        s.io_error = vals.get(A.ADDR_IO_ERROR)

        # Individual humidity / CO2 sensor slot values (raw values)
        for addr in A.ADDR_RH_SENSORS:
            v = vals.get(addr)
            s.rh_slot_values[addr] = None if v in (None, 0, 0xFFFF) else v
        for addr in A.ADDR_CO2_SENSORS:
            v = vals.get(addr)
            s.co2_slot_values[addr] = None if v in (None, 0, 0xFFFF) else v

    # ----- Load device info (one-time) --------------------------------------
    async def _load_device_info(self) -> bool:
        s = self._snapshot
        try:
            vals = await self.client.read_variables(list(_DEVICE_INFO_ADDRS))
        except EasyControlsProtocolError as err:
            LOGGER.warning("Could not load device info: %s", err)
            return False

        # SW version: high bytes of addresses 8/9/10 = Major.Minor.Patch
        v8 = vals.get(8)
        v9 = vals.get(9)
        v10 = vals.get(10)
        s.sw_version = A.decode_sw_version(v8, v9, v10)

        # UUID — all 8 sequential words from 8214..8221
        uuid_words = [vals.get(a, 0) for a in A.ADDR_UUID]
        s.uuid = _format_uuid(uuid_words) or None

        s.sidedness = vals.get(A.ADDR_SIDEDNESS)

        ip1 = vals.get(A.ADDR_IP_ADDRESS_1, 0)
        ip2 = vals.get(A.ADDR_IP_ADDRESS_2, 0)
        s.ip_address = _ip_from_words(ip1, ip2)
        gw1 = vals.get(A.ADDR_GW_ADDRESS_1, 0)
        gw2 = vals.get(A.ADDR_GW_ADDRESS_2, 0)
        s.gateway = _ip_from_words(gw1, gw2)
        m1 = vals.get(A.ADDR_MASK_ADDRESS_1, 0)
        m2 = vals.get(A.ADDR_MASK_ADDRESS_2, 0)
        s.netmask = _ip_from_words(m1, m2)

        # NOTE: external sensor counts now computed in _parse_table0 from
        # the rh_slot_values / co2_slot_values dicts which are populated by
        # the periodic poll (not the one-time device_info load).
        return True

    # ----- Helpers ----------------------------------------------------------
    def device_model_str(self) -> str:
        if self._snapshot.machine_model_idx is None:
            return "Helios KWL"
        return model_name(self._snapshot.machine_model_idx)

    def device_type_str(self) -> str:
        if self._snapshot.machine_type_idx is None:
            return ""
        return type_name(self._snapshot.machine_type_idx)

    def serial_str(self) -> str:
        return str(self._snapshot.serial_number) if self._snapshot.serial_number else ""

    async def request_refresh_after_write(self) -> None:
        """After a write: schedule progressive refresh attempts."""
        await asyncio.sleep(0.4)
        await self.async_request_refresh()
        self.hass.async_create_task(self._delayed_refresh_chain([2.0, 5.0]))

    async def _delayed_refresh_chain(self, delays: list[float]) -> None:
        for delay in delays:
            await asyncio.sleep(delay)
            try:
                await self.async_request_refresh()
            except Exception as e:
                LOGGER.debug("Delayed refresh failed: %s", e)

    # ----- Plug confirmation auto-sync --------------------------------------
    async def _sync_plug_confirmed_with_cool_recovery(self) -> None:
        """Mirror the WebUI safety logic in HA-internal state.

        Rules:
        - When cool_recovery is currently ON, the plug must have been
          confirmed at some point (WebUI requires it). Set plug_confirmed=True.
        - When cool_recovery transitions ON -> OFF, reset plug_confirmed=False
          so user must re-confirm before the next turn-on.
        - First poll after restart: only set plug_confirmed=True from
          inferred state, never reset it (storage may already have it set).
        """
        s = self._snapshot
        cur = s.cool_recovery_enabled
        prev = self._prev_cool_recovery
        changed = False
        if cur is True and not s.plug_confirmed:
            s.plug_confirmed = True
            changed = True
        elif prev is True and cur is False and s.plug_confirmed:
            s.plug_confirmed = False
            changed = True
        self._prev_cool_recovery = cur
        if changed:
            await self._save_storage()
