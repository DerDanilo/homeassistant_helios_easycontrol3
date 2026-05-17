"""Variable addresses used by this integration, grouped by function.

Conventions:
- Temperatures (raw values and setpoints) are encoded as Kelvin x 100
  (28715 == 14 degC). See helpers at the bottom of this file.
- Schedule slot values: 0=NONE, 1=HOME, 2=AWAY, 3=BOOST, 4=INDIVIDUAL,
  5=STANDBY.
"""

# ---------------------------------------------------------------------------
# WebSocket protocol constants
# ---------------------------------------------------------------------------
WS_CMD_READ_TABLES = 246
WS_CMD_LOG = 247
WS_CMD_WRITE_DATA = 249
WS_CMD_READ_DATA = 250
WS_REPLY_DATA = 248
WS_REPLY_ACK = 245


# ---------------------------------------------------------------------------
# Table 0: standard data block (~addresses 0..250 as buffer)
# ---------------------------------------------------------------------------
# Device identification
ADDR_SERIAL_NUMBER_MSW = 14
ADDR_SERIAL_NUMBER_LSW = 15
ADDR_MACHINE_TYPE = 16
ADDR_MACHINE_MODEL = 17

# Live values (in Table 0)
ADDR_FAN_SPEED = 4353            # Current fan speed in %
ADDR_TEMP_EXTRACT_AIR = 4354
ADDR_TEMP_EXHAUST_AIR = 4355
ADDR_TEMP_OUTDOOR_AIR = 4356
ADDR_TEMP_SUPPLY_CELL_AIR = 4357
ADDR_TEMP_SUPPLY_AIR = 4358
ADDR_RH_VALUE = 4363
ADDR_CO2_VALUE = 4364
ADDR_RH_LEVEL = 4359
ADDR_CO2_LEVEL = 4360

# Fan RPMs
ADDR_EXTR_FAN_SPEED = 4361       # Extract air RPM
ADDR_SUPP_FAN_SPEED = 4362       # Supply air RPM

# Status trio for mode detection
ADDR_STATE = 4609                # 0=HOME, 1=AWAY, 2=BOOST
ADDR_MODE = 4610                 # 0=NORMAL, ..., 5=OFF
ADDR_DEFROSTING = 4611
ADDR_BOOST_TIMER = 4612          # >0 = Boost active, remaining minutes
ADDR_FIREPLACE_TIMER = 4613      # >0 = Individual mode active, remaining minutes
ADDR_EXTRA_TIMER = 4614
ADDR_WEEKLY_TIMER_ENABLED = 4615
ADDR_CELL_STATE = 4616
ADDR_TOTAL_UP_TIME_YEARS = 4617
ADDR_TOTAL_UP_TIME_HOURS = 4618
ADDR_CURRENT_UP_TIME_HOURS = 4619  # hours since last power-on (for last-power-interrupt derivation)
ADDR_ENABLED = 4626              # "Ventilation profiles active"
ADDR_CLOUD_STATUS = 4631

# RH/CO2 sensor slots — value 0xFFFF means not populated
ADDR_RH_SENSORS = (4373, 4374, 4375, 4376, 4377, 4378)
ADDR_CO2_SENSORS = (4379, 4380, 4381, 4382, 4383, 4384)

# Real-time clock (device RTC)
ADDR_MINUTE = 4849
ADDR_HOUR = 4850
ADDR_DAY = 4851
ADDR_MONTH = 4852
ADDR_YEAR = 4853                 # value + 2000
ADDR_WEEKDAY = 4854

# I/O addresses
ADDR_IO_BYPASS = 4870
ADDR_IO_EXTRACT_FAN = 4865
ADDR_IO_SUPPLY_FAN = 4866
ADDR_IO_ERROR = 4867
ADDR_IO_HEATER = 4868
ADDR_IO_EXTRA_HEATER = 4869


# ---------------------------------------------------------------------------
# Higher addresses — must be read individually via READ_DATA
# ---------------------------------------------------------------------------
# Software version: addresses 1..10 (HIGH byte contains Major/Minor/Patch)
# Example: addr 8 high=1, addr 9 high=0, addr 10 high=25 -> "1.0.25"
ADDR_APPL_SW_VERSION_PARTS = tuple(range(1, 11))

# UUID: 8 sequential words at 8214..8221
ADDR_UUID = (8214, 8215, 8216, 8217, 8218, 8219, 8220, 8221)

# Network
ADDR_GW_ADDRESS_1 = 8194
ADDR_GW_ADDRESS_2 = 8195
ADDR_MASK_ADDRESS_1 = 8196
ADDR_MASK_ADDRESS_2 = 8197
ADDR_IP_ADDRESS_1 = 8212
ADDR_IP_ADDRESS_2 = 8213
ADDR_ETH_CLOUD_ENABLED = 8211

# Configuration / mode setpoints (20481..20555)
# Air temperature targets are in K×100! (28715 = 14°C)
#
# NOTE: ADDR_*_RH_CTRL_ENABLED and ADDR_*_CO2_CTRL_ENABLED are intentionally
# NOT exposed as switches — they are not visible in the Helios WebUI and
# changing them blindly can produce non-obvious device behavior. Constants
# kept here only for completeness / power-user use of write_variable().
ADDR_AWAY_RH_CTRL_ENABLED = 20499      # NOT exposed — see note above
ADDR_AWAY_CO2_CTRL_ENABLED = 20500     # NOT exposed — see note above
ADDR_AWAY_SPEED_SETTING = 20501
ADDR_AWAY_AIR_TEMP_TARGET = 20502
ADDR_HOME_RH_CTRL_ENABLED = 20505      # NOT exposed — see note above
ADDR_HOME_CO2_CTRL_ENABLED = 20506     # NOT exposed — see note above
ADDR_HOME_SPEED_SETTING = 20507
ADDR_HOME_AIR_TEMP_TARGET = 20508
ADDR_BOOST_RH_CTRL_ENABLED = 20511     # NOT exposed — see note above
ADDR_BOOST_CO2_CTRL_ENABLED = 20512    # NOT exposed — see note above
ADDR_BOOST_SPEED_SETTING = 20513
ADDR_BOOST_AIR_TEMP_TARGET = 20514
ADDR_BOOST_TIME = 20544

# Individual mode (registers retain the upstream "FIREPLACE" naming)
ADDR_FIREPLACE_EXTR_FAN = 20487
ADDR_FIREPLACE_SUPP_FAN = 20488
ADDR_FIREPLACE_AIR_TEMP_TARGET = 20497
ADDR_FIREPLACE_TIME = 20545

# Filter
ADDR_FILTER_REMINDER_DISABLED = 20503
ADDR_FILTER_CHANGE_INTERVAL = 20537   # in days (1 month ~= 30 days)
ADDR_FILTER_CHANGED_DAY = 20546
ADDR_FILTER_CHANGED_MONTH = 20547
ADDR_FILTER_CHANGED_YEAR = 20548      # value + 2000

# Bypass / Relay / Sidedness
ADDR_RELAY_MODE = 20517
ADDR_PARTIAL_BYPASS_DISABLED = 20489
ADDR_PARTIAL_BYPASS = 20551
ADDR_BYPASS_LOCKED = 20552
ADDR_SIDEDNESS = 20542

# Cool recovery (raw value: 0 = off, 1 = on)
ADDR_COOLRECOVERY_DISABLED = 20516

# Weekly schedule: 7 days x 24 hours = 168 slots starting at 40961
ADDR_SCHEDULE_BASE = 40961
ADDR_SCHEDULE_END = 41128

# Timed function (vacation mode)
ADDR_TIMED_FUNCTION_ENABLED = 46021
ADDR_TIMED_FUNCTION_MODE = 46028
ADDR_TIMED_FUNCTION_RETURN_MODE = 46029


# ---------------------------------------------------------------------------
# Buffer offsets for Table 0
# ---------------------------------------------------------------------------
BUF_FAN_SPEED_BYTE = 129
BUF_INTENSIVE_FAN_SPEED_BYTE = 431
BUF_AT_HOME_FAN_SPEED_BYTE = 419
BUF_AWAY_FAN_SPEED_BYTE = 407
BUF_INTENSIVE_DURATION_BYTE = 493
BUF_RH_BYTE = 74 * 2 + 1
BUF_FILTER_INTERVAL_BYTE = 239 * 2 + 1   # low byte only; prefer FILTER_CHANGE_INTERVAL
BUF_FILTER_CHANGED_DAY_BYTE = 248 * 2 + 1
BUF_FILTER_CHANGED_MONTH_BYTE = 249 * 2 + 1
BUF_FILTER_CHANGED_YEAR_BYTE = 250 * 2 + 1
BUF_STATE_BYTE = 107 * 2 + 1
BUF_BOOST_TIMER_BYTE = 110 * 2 + 1
BUF_FIREPLACE_TIMER_BYTE = 111 * 2 + 1
BUF_ON_OFF_BYTE = 217
BUF_CO2_HIGH_BYTE = 182
BUF_CO2_LOW_BYTE = 183


# ---------------------------------------------------------------------------
# Enum value sets (C_CYC_*)
# ---------------------------------------------------------------------------
STATE_HOME = 0
STATE_AWAY = 1
STATE_BOOST = 2

MODE_NORMAL = 0
MODE_OFF = 5

SIDEDNESS_LEFT = 0
SIDEDNESS_RIGHT = 1
SIDEDNESS_LABELS = {SIDEDNESS_LEFT: "Left", SIDEDNESS_RIGHT: "Right"}

CELL_STATE_LABELS = {
    0: "Heat Recovery",
    1: "Cool Recovery",
    2: "Bypass",
    3: "Defrost",
    4: "Condensation Protection",
}

RELAY_MODE_LABELS = {
    0: "Service Reminder",
    1: "Error",
    2: "Error / Service",
    3: "Fire Alarm",
    4: "Bypass State",
    5: "MLV",
    6: "Off",
    7: "Air Heater",
    8: "Run State",
}

# Weekly schedule slot values
SCHEDULE_EVENT_NONE = 0     # "No entry — previous mode remains active"
SCHEDULE_EVENT_HOME = 1
SCHEDULE_EVENT_AWAY = 2
SCHEDULE_EVENT_BOOST = 3
SCHEDULE_EVENT_INDIVIDUAL = 4
SCHEDULE_EVENT_STANDBY = 5
SCHEDULE_EVENT_LABELS = {
    SCHEDULE_EVENT_NONE: "none",
    SCHEDULE_EVENT_HOME: "home",
    SCHEDULE_EVENT_AWAY: "away",
    SCHEDULE_EVENT_BOOST: "boost",
    SCHEDULE_EVENT_INDIVIDUAL: "individual",
    SCHEDULE_EVENT_STANDBY: "standby",
}
SCHEDULE_EVENT_NAME_TO_VALUE = {v: k for k, v in SCHEDULE_EVENT_LABELS.items()}

WEEKDAY_NAMES = ("MONDAY", "TUESDAY", "WEDNESDAY", "THURSDAY",
                 "FRIDAY", "SATURDAY", "SUNDAY")


def schedule_addr(weekday: int, hour: int) -> int:
    """Return address for weekly schedule slot. weekday: 0=Mon..6=Sun; hour: 0..23."""
    if not 0 <= weekday < 7:
        raise ValueError(f"weekday must be 0..6, got {weekday}")
    if not 0 <= hour < 24:
        raise ValueError(f"hour must be 0..23, got {hour}")
    return ADDR_SCHEDULE_BASE + weekday * 24 + hour


# ---------------------------------------------------------------------------
# Conversion helpers for Air Temperature (K×100 <-> °C)
# ---------------------------------------------------------------------------
def air_temp_k100_to_celsius(k100: int) -> float:
    """Helios K×100 -> Celsius (e.g. 28715 -> 14.0)."""
    return round(k100 / 100 - 273.15, 1)


def air_temp_celsius_to_k100(celsius: float) -> int:
    """Celsius -> Helios K×100 (e.g. 14 -> 28715)."""
    return int(round((celsius + 273.15) * 100))


# ---------------------------------------------------------------------------
# SW version decoder (high byte of 3 addresses)
# ---------------------------------------------------------------------------
def decode_sw_version(addr_8: int | None, addr_9: int | None, addr_10: int | None) -> str | None:
    """Major.Minor.Patch from high bytes of addresses 8/9/10."""
    if addr_8 is None or addr_9 is None or addr_10 is None:
        return None
    major = (addr_8 >> 8) & 0xFF
    minor = (addr_9 >> 8) & 0xFF
    patch = (addr_10 >> 8) & 0xFF
    return f"{major}.{minor}.{patch}"
