"""Sensors for Helios easyControls 3.0."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONCENTRATION_PARTS_PER_MILLION,
    PERCENTAGE,
    REVOLUTIONS_PER_MINUTE,
    UnitOfTemperature,
    UnitOfTime,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import addresses as A
from .const import DOMAIN
from .coordinator import EasyControls3Coordinator, KWLSnapshot
from .entity import EasyControlsBaseEntity


@dataclass(frozen=True, kw_only=True)
class _SensorDef(SensorEntityDescription):
    """Sensor description with value extractor."""
    value_fn: Callable[[KWLSnapshot], Any] = lambda s: None
    always_available: bool = False


SENSORS: tuple[_SensorDef, ...] = (
    # Air Temperatures
    _SensorDef(
        key="outdoor_temp", translation_key="outdoor_temp",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        suggested_display_precision=1,
        value_fn=lambda s: s.outdoor_temp,
    ),
    _SensorDef(
        key="supply_temp", translation_key="supply_temp",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        suggested_display_precision=1,
        value_fn=lambda s: s.supply_temp,
    ),
    _SensorDef(
        key="extract_temp", translation_key="extract_temp",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        suggested_display_precision=1,
        value_fn=lambda s: s.extract_temp,
    ),
    _SensorDef(
        key="exhaust_temp", translation_key="exhaust_temp",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        suggested_display_precision=1,
        value_fn=lambda s: s.exhaust_temp,
    ),
    # Ventilation
    _SensorDef(
        key="current_fan_speed", translation_key="current_fan_speed",
        icon="mdi:fan",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=PERCENTAGE,
        value_fn=lambda s: s.current_fan_speed,
    ),
    _SensorDef(
        key="supply_fan_rpm", translation_key="supply_fan_rpm",
        icon="mdi:fan",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=REVOLUTIONS_PER_MINUTE,
        value_fn=lambda s: s.measured_supply_rpm,
    ),
    _SensorDef(
        key="extract_fan_rpm", translation_key="extract_fan_rpm",
        icon="mdi:fan",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=REVOLUTIONS_PER_MINUTE,
        value_fn=lambda s: s.measured_extract_rpm,
    ),
    # Humidity / CO2 (primary readings)
    _SensorDef(
        key="humidity", translation_key="humidity",
        device_class=SensorDeviceClass.HUMIDITY,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=PERCENTAGE,
        suggested_display_precision=0,
        value_fn=lambda s: s.rh,
    ),
    # Heat exchanger
    _SensorDef(
        key="cell_state", translation_key="cell_state",
        device_class=SensorDeviceClass.ENUM,
        icon="mdi:heat-pump",
        options=list(A.CELL_STATE_LABELS.values()),
        value_fn=lambda s: A.CELL_STATE_LABELS.get(s.cell_state) if s.cell_state is not None else None,
    ),
    # Filter
    _SensorDef(
        key="filter_changed", translation_key="filter_changed",
        device_class=SensorDeviceClass.DATE,
        icon="mdi:filter-check",
        value_fn=lambda s: s.filter_changed_date,
    ),
    _SensorDef(
        key="filter_due", translation_key="filter_due",
        device_class=SensorDeviceClass.DATE,
        icon="mdi:calendar-alert-outline",
        value_fn=lambda s: s.filter_due_date,
    ),
    # Remaining minutes for time-limited modes (0 when not active)
    _SensorDef(
        key="boost_remaining_minutes",
        translation_key="boost_remaining_minutes",
        icon="mdi:timer-sand",
        device_class=SensorDeviceClass.DURATION,
        native_unit_of_measurement=UnitOfTime.MINUTES,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda s: int(s.boost_timer or 0),
    ),
    _SensorDef(
        key="individual_remaining_minutes",
        translation_key="individual_remaining_minutes",
        icon="mdi:timer-sand",
        device_class=SensorDeviceClass.DURATION,
        native_unit_of_measurement=UnitOfTime.MINUTES,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda s: int(s.fireplace_timer or 0),
    ),
    # Device diagnostics
    _SensorDef(
        key="operating_time", translation_key="operating_time",
        entity_category=EntityCategory.DIAGNOSTIC,
        icon="mdi:timer-sand",
        value_fn=lambda s: s.operating_time_str,
    ),
    _SensorDef(
        key="last_power_interruption", translation_key="last_power_interruption",
        device_class=SensorDeviceClass.TIMESTAMP,
        entity_category=EntityCategory.DIAGNOSTIC,
        icon="mdi:power-plug-off",
        value_fn=lambda s: s.last_power_on,
    ),
    _SensorDef(
        key="rh_sensor_count", translation_key="rh_sensor_count",
        entity_category=EntityCategory.DIAGNOSTIC,
        icon="mdi:counter",
        value_fn=lambda s: s.rh_sensor_count,
    ),
    _SensorDef(
        key="co2_sensor_count", translation_key="co2_sensor_count",
        entity_category=EntityCategory.DIAGNOSTIC,
        icon="mdi:counter",
        value_fn=lambda s: s.co2_sensor_count,
    ),
    _SensorDef(
        key="ip_address", translation_key="ip_address",
        entity_category=EntityCategory.DIAGNOSTIC,
        icon="mdi:ip-network",
        value_fn=lambda s: s.ip_address,
    ),
    _SensorDef(
        key="gateway", translation_key="gateway",
        entity_category=EntityCategory.DIAGNOSTIC,
        icon="mdi:router-network",
        value_fn=lambda s: s.gateway,
    ),
    _SensorDef(
        key="netmask", translation_key="netmask",
        entity_category=EntityCategory.DIAGNOSTIC,
        icon="mdi:vector-difference",
        value_fn=lambda s: s.netmask,
    ),
    _SensorDef(
        key="uuid", translation_key="uuid",
        entity_category=EntityCategory.DIAGNOSTIC,
        icon="mdi:identifier",
        value_fn=lambda s: s.uuid,
    ),
    _SensorDef(
        key="sidedness", translation_key="sidedness",
        entity_category=EntityCategory.DIAGNOSTIC,
        device_class=SensorDeviceClass.ENUM,
        options=list(A.SIDEDNESS_LABELS.values()),
        value_fn=lambda s: A.SIDEDNESS_LABELS.get(s.sidedness) if s.sidedness is not None else None,
    ),
    _SensorDef(
        key="relay_mode", translation_key="relay_mode",
        entity_category=EntityCategory.DIAGNOSTIC,
        device_class=SensorDeviceClass.ENUM,
        icon="mdi:electric-switch",
        options=list(A.RELAY_MODE_LABELS.values()),
        value_fn=lambda s: A.RELAY_MODE_LABELS.get(s.relay_mode) if s.relay_mode is not None else None,
    ),
    # ----- IO state sensors (raw values from device IO subsystem) -----
    _SensorDef(
        key="io_bypass", translation_key="io_bypass",
        entity_category=EntityCategory.DIAGNOSTIC,
        icon="mdi:valve",
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda s: s.io_bypass,
    ),
    _SensorDef(
        key="io_supply_fan", translation_key="io_supply_fan",
        entity_category=EntityCategory.DIAGNOSTIC,
        icon="mdi:fan-chevron-up",
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda s: s.io_supply_fan,
    ),
    _SensorDef(
        key="io_extract_fan", translation_key="io_extract_fan",
        entity_category=EntityCategory.DIAGNOSTIC,
        icon="mdi:fan-chevron-down",
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda s: s.io_extract_fan,
    ),
    _SensorDef(
        key="io_heater", translation_key="io_heater",
        entity_category=EntityCategory.DIAGNOSTIC,
        icon="mdi:radiator",
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda s: s.io_heater,
    ),
    _SensorDef(
        key="io_extra_heater", translation_key="io_extra_heater",
        entity_category=EntityCategory.DIAGNOSTIC,
        icon="mdi:radiator-disabled",
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda s: s.io_extra_heater,
    ),
    _SensorDef(
        key="io_error", translation_key="io_error",
        entity_category=EntityCategory.DIAGNOSTIC,
        icon="mdi:alert-outline",
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda s: s.io_error,
    ),
    # ===== Connectivity sensors (always_available=True!) =====
    _SensorDef(
        key="last_successful_update", translation_key="last_successful_update",
        device_class=SensorDeviceClass.TIMESTAMP,
        entity_category=EntityCategory.DIAGNOSTIC,
        icon="mdi:clock-check",
        always_available=True,
        # Disabled by default: timestamp updates on every poll cycle creates
        # lots of recorder/log noise. Enable manually if you need it for
        # debugging poll cadence.
        entity_registry_enabled_default=False,
        value_fn=lambda s: s.last_successful_update,
    ),
    _SensorDef(
        key="connection_stability", translation_key="connection_stability",
        entity_category=EntityCategory.DIAGNOSTIC,
        icon="mdi:lan-pending",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=PERCENTAGE,
        suggested_display_precision=0,
        always_available=True,
        value_fn=lambda s: int(round(s.stability_pct)) if s.stability_pct is not None else None,
    ),
    _SensorDef(
        key="consecutive_failures", translation_key="consecutive_failures",
        entity_category=EntityCategory.DIAGNOSTIC,
        icon="mdi:alert-circle",
        state_class=SensorStateClass.MEASUREMENT,
        always_available=True,
        value_fn=lambda s: s.consecutive_failures,
    ),
    _SensorDef(
        key="total_failures", translation_key="total_failures",
        entity_category=EntityCategory.DIAGNOSTIC,
        icon="mdi:counter",
        state_class=SensorStateClass.TOTAL_INCREASING,
        always_available=True,
        value_fn=lambda s: s.total_failures,
    ),
)


# ---- Per-slot sensor builders (humidity / CO2) ----------------------------
def _make_humidity_slot_sensor(slot_num: int, getter: Callable[[KWLSnapshot], int | None]) -> _SensorDef:
    return _SensorDef(
        key=f"humidity_sensor_{slot_num:02d}",
        translation_key="humidity_sensor_slot",
        translation_placeholders={"slot": str(slot_num)},
        device_class=SensorDeviceClass.HUMIDITY,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=PERCENTAGE,
        suggested_display_precision=0,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=getter,
    )


def _make_co2_slot_sensor(slot_num: int, getter: Callable[[KWLSnapshot], int | None]) -> _SensorDef:
    return _SensorDef(
        key=f"co2_sensor_{slot_num:02d}",
        translation_key="co2_sensor_slot",
        translation_placeholders={"slot": str(slot_num)},
        device_class=SensorDeviceClass.CO2,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=CONCENTRATION_PARTS_PER_MILLION,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=getter,
    )


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    coordinator: EasyControls3Coordinator = hass.data[DOMAIN][entry.entry_id]
    entities: list[_GenericSensor] = [_GenericSensor(coordinator, d) for d in SENSORS]

    # Primary CO2 sensor (the "internal" sensor reading from Table 0).
    # Always shown — WebUI displays "0 ppm" when no external sensor connected.
    entities.append(_GenericSensor(coordinator, _SensorDef(
        key="co2", translation_key="co2",
        device_class=SensorDeviceClass.CO2,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=CONCENTRATION_PARTS_PER_MILLION,
        value_fn=lambda s: s.co2,
    )))

    # --- Individual humidity / CO2 sensor entities --------------------------
    # Numbering matches Helios WebUI "Sensoren" list:
    #   #1 = internal sensor (always present if device has built-in reading)
    #   #2..7 = external slot sensors (only created if populated at startup)
    snap = coordinator.data

    # Humidity Sensor 1 (internal)
    entities.append(_GenericSensor(coordinator,
        _make_humidity_slot_sensor(1, lambda s: s.rh)))
    # Humidity Sensors 2..7 (external slots)
    for i, addr in enumerate(A.ADDR_RH_SENSORS, start=2):
        slot_val = snap.rh_slot_values.get(addr) if snap else None
        if slot_val is not None:   # only register if slot is populated
            entities.append(_GenericSensor(coordinator,
                _make_humidity_slot_sensor(i, lambda s, a=addr: s.rh_slot_values.get(a))))

    # CO2 Sensor 1 (internal) - only create if there's a real reading
    if snap and snap.co2 is not None and snap.co2 > 0:
        entities.append(_GenericSensor(coordinator,
            _make_co2_slot_sensor(1, lambda s: s.co2 if s.co2 and s.co2 > 0 else None)))
    # CO2 Sensors 2..7 (external slots)
    for i, addr in enumerate(A.ADDR_CO2_SENSORS, start=2):
        slot_val = snap.co2_slot_values.get(addr) if snap else None
        if slot_val is not None:
            entities.append(_GenericSensor(coordinator,
                _make_co2_slot_sensor(i, lambda s, a=addr: s.co2_slot_values.get(a))))

    async_add_entities(entities)


class _GenericSensor(EasyControlsBaseEntity, SensorEntity):
    entity_description: _SensorDef

    def __init__(self, coordinator: EasyControls3Coordinator, description: _SensorDef):
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{coordinator.serial_str() or coordinator.host}_{description.key}"

    @property
    def native_value(self) -> Any:
        snap = self.coordinator.data
        if snap is None:
            return None
        return self.entity_description.value_fn(snap)

    @property
    def available(self) -> bool:
        # Connectivity sensors are always available — they reflect their own state
        if self.entity_description.always_available:
            return True
        snap = self.coordinator.data
        if snap is None:
            return False
        return snap.last_successful_update is not None
