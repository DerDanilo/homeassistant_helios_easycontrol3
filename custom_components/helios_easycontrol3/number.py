"""Number entities for KWL setpoint control.

Important: air temperature targets are stored on the device as K×100 (28715 = 14°C).
We display Celsius and convert transparently on read/write.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from homeassistant.components.number import (
    NumberDeviceClass,
    NumberEntity,
    NumberEntityDescription,
    NumberMode,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import PERCENTAGE, UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import addresses as A
from .const import DOMAIN
from .coordinator import EasyControls3Coordinator, KWLSnapshot
from .entity import EasyControlsBaseEntity


@dataclass(frozen=True, kw_only=True)
class _NumberDef(NumberEntityDescription):
    address: int
    value_fn: Callable[[KWLSnapshot], float | int | None]
    # Encoder: UI value (e.g. °C) -> device value (e.g. K×100)
    encode_fn: Callable[[float], int] = lambda v: int(round(v))


NUMBERS: tuple[_NumberDef, ...] = (
    # --- Fan speeds per mode (in %, direct) ---
    _NumberDef(
        key="home_speed", translation_key="home_speed",
        icon="mdi:home-thermometer",
        native_min_value=1, native_max_value=100, native_step=1,
        native_unit_of_measurement=PERCENTAGE,
        mode=NumberMode.BOX,
        address=A.ADDR_HOME_SPEED_SETTING,
        value_fn=lambda s: s.home_speed,
    ),
    _NumberDef(
        key="away_speed", translation_key="away_speed",
        icon="mdi:home-export-outline",
        native_min_value=1, native_max_value=100, native_step=1,
        native_unit_of_measurement=PERCENTAGE,
        mode=NumberMode.BOX,
        address=A.ADDR_AWAY_SPEED_SETTING,
        value_fn=lambda s: s.away_speed,
    ),
    _NumberDef(
        key="boost_speed", translation_key="boost_speed",
        icon="mdi:fan-plus",
        native_min_value=1, native_max_value=100, native_step=1,
        native_unit_of_measurement=PERCENTAGE,
        mode=NumberMode.BOX,
        address=A.ADDR_BOOST_SPEED_SETTING,
        value_fn=lambda s: s.boost_speed,
    ),
    _NumberDef(
        key="individual_supply_speed",
        translation_key="individual_supply_speed",
        icon="mdi:fan-chevron-up",
        native_min_value=1, native_max_value=100, native_step=1,
        native_unit_of_measurement=PERCENTAGE,
        mode=NumberMode.BOX,
        address=A.ADDR_FIREPLACE_SUPP_FAN,
        value_fn=lambda s: s.individual_supply_speed,
    ),
    _NumberDef(
        key="individual_extract_speed",
        translation_key="individual_extract_speed",
        icon="mdi:fan-chevron-down",
        native_min_value=1, native_max_value=100, native_step=1,
        native_unit_of_measurement=PERCENTAGE,
        mode=NumberMode.BOX,
        address=A.ADDR_FIREPLACE_EXTR_FAN,
        value_fn=lambda s: s.individual_extract_speed,
    ),
    # --- Supply air temperature targets (UI=°C, stored as K×100) ---
    _NumberDef(
        key="home_air_temp", translation_key="home_air_temp",
        device_class=NumberDeviceClass.TEMPERATURE,
        native_min_value=10, native_max_value=25, native_step=1,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        mode=NumberMode.BOX,
        address=A.ADDR_HOME_AIR_TEMP_TARGET,
        value_fn=lambda s: s.home_air_temp_target,    # already Celsius in snapshot
        encode_fn=A.air_temp_celsius_to_k100,
    ),
    _NumberDef(
        key="away_air_temp", translation_key="away_air_temp",
        device_class=NumberDeviceClass.TEMPERATURE,
        native_min_value=10, native_max_value=25, native_step=1,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        mode=NumberMode.BOX,
        address=A.ADDR_AWAY_AIR_TEMP_TARGET,
        value_fn=lambda s: s.away_air_temp_target,
        encode_fn=A.air_temp_celsius_to_k100,
    ),
    _NumberDef(
        key="boost_air_temp", translation_key="boost_air_temp",
        device_class=NumberDeviceClass.TEMPERATURE,
        native_min_value=10, native_max_value=25, native_step=1,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        mode=NumberMode.BOX,
        address=A.ADDR_BOOST_AIR_TEMP_TARGET,
        value_fn=lambda s: s.boost_air_temp_target,
        encode_fn=A.air_temp_celsius_to_k100,
    ),
    _NumberDef(
        key="individual_air_temp", translation_key="individual_air_temp",
        device_class=NumberDeviceClass.TEMPERATURE,
        native_min_value=10, native_max_value=25, native_step=1,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        mode=NumberMode.BOX,
        address=A.ADDR_FIREPLACE_AIR_TEMP_TARGET,
        value_fn=lambda s: s.individual_air_temp_target,
        encode_fn=A.air_temp_celsius_to_k100,
    ),
    # --- Filter ---
    _NumberDef(
        key="filter_change_interval_months", translation_key="filter_change_interval_months",
        icon="mdi:filter-cog",
        native_min_value=1, native_max_value=12, native_step=1,
        native_unit_of_measurement="months",
        mode=NumberMode.BOX,
        address=A.ADDR_FILTER_CHANGE_INTERVAL,
        # Read: days -> months
        value_fn=lambda s: round(s.filter_interval_setting / 30) if s.filter_interval_setting else None,
        # Write: months × 30 = days
        encode_fn=lambda v: int(round(v) * 30),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    coordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([_GenericNumber(coordinator, d) for d in NUMBERS])


class _GenericNumber(EasyControlsBaseEntity, NumberEntity):
    """Generic number entity.

    Forwards numeric attributes explicitly from the description because HA's
    frontend defaults to 1 decimal place when the `step` attribute is missing
    from the entity state (which can happen if dataclass field forwarding
    misbehaves). Also returns int from native_value when step is integral.
    """
    entity_description: _NumberDef
    _attr_suggested_display_precision = 0

    def __init__(self, coordinator: EasyControls3Coordinator, description: _NumberDef):
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{coordinator.serial_str() or coordinator.host}_{description.key}"
        # Explicit forwarding so frontend definitely sees them in the state attrs
        self._attr_native_min_value = description.native_min_value
        self._attr_native_max_value = description.native_max_value
        self._attr_native_step = description.native_step
        self._attr_native_unit_of_measurement = description.native_unit_of_measurement
        self._attr_mode = description.mode
        if description.device_class is not None:
            self._attr_device_class = description.device_class
        if description.icon is not None:
            self._attr_icon = description.icon

    @property
    def native_value(self) -> float | None:
        snap = self.coordinator.data
        if snap is None:
            return None
        v = self.entity_description.value_fn(snap)
        if v is None:
            return None
        # Step is integral (always 1 in this integration) -> round to int so the
        # state attribute is "45" not "45.0", which cooperates with frontend
        # display and Intl.NumberFormat.
        step = self.entity_description.native_step
        if step is not None and float(step).is_integer():
            return int(round(float(v)))
        return float(v)

    async def async_set_native_value(self, value: float) -> None:
        encoded = self.entity_description.encode_fn(value)
        await self.coordinator.client.write_variable(
            self.entity_description.address, encoded
        )
        await self.coordinator.request_refresh_after_write()