"""Binary sensors for Helios easyControls 3.0 (incl. connectivity)."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .coordinator import EasyControls3Coordinator, KWLSnapshot
from .entity import EasyControlsBaseEntity


@dataclass(frozen=True, kw_only=True)
class _BinaryDef(BinarySensorEntityDescription):
    value_fn: Callable[[KWLSnapshot], bool | None] = lambda s: None
    # always_available=True -> sensor stays visible even on coordinator failures
    always_available: bool = False


BINARY_SENSORS: tuple[_BinaryDef, ...] = (
    _BinaryDef(
        key="defrosting", translation_key="defrosting",
        device_class=BinarySensorDeviceClass.RUNNING,
        icon="mdi:snowflake-melt",
        value_fn=lambda s: s.defrosting,
    ),
    _BinaryDef(
        key="boost_active", translation_key="boost_active",
        icon="mdi:fan-plus",
        value_fn=lambda s: s.boost_timer > 0,
    ),
    _BinaryDef(
        key="individual_mode_active", translation_key="individual_mode_active",
        icon="mdi:account-tie",
        value_fn=lambda s: s.fireplace_timer > 0,
    ),
    _BinaryDef(
        key="partial_bypass", translation_key="partial_bypass",
        icon="mdi:valve",
        value_fn=lambda s: s.partial_bypass,
    ),
    _BinaryDef(
        key="bypass_locked", translation_key="bypass_locked",
        icon="mdi:valve-closed",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda s: s.bypass_locked,
    ),
    _BinaryDef(
        key="weekly_timer_enabled", translation_key="weekly_timer_enabled",
        icon="mdi:calendar-clock",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda s: s.weekly_timer_enabled,
    ),
    _BinaryDef(
        key="cloud_connected", translation_key="cloud_connected",
        device_class=BinarySensorDeviceClass.CONNECTIVITY,
        entity_category=EntityCategory.DIAGNOSTIC,
        icon="mdi:cloud-check",
        value_fn=lambda s: bool(s.cloud_status) if s.cloud_status is not None else None,
    ),
    _BinaryDef(
        key="device_enabled", translation_key="device_enabled",
        device_class=BinarySensorDeviceClass.RUNNING,
        icon="mdi:power-plug",
        value_fn=lambda s: s.enabled_state,
    ),
    # ----- Connectivity (always_available=True) -----
    _BinaryDef(
        key="kwl_reachable", translation_key="kwl_reachable",
        device_class=BinarySensorDeviceClass.CONNECTIVITY,
        entity_category=EntityCategory.DIAGNOSTIC,
        icon="mdi:lan-connect",
        always_available=True,
        value_fn=lambda s: s.is_currently_reachable,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    coordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([_GenericBinary(coordinator, d) for d in BINARY_SENSORS])


class _GenericBinary(EasyControlsBaseEntity, BinarySensorEntity):
    entity_description: _BinaryDef

    def __init__(self, coordinator: EasyControls3Coordinator, description: _BinaryDef):
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{coordinator.serial_str() or coordinator.host}_{description.key}"

    @property
    def is_on(self) -> bool | None:
        # IMPORTANT: connectivity sensors must answer even when
        # coordinator.last_update_success=False — we use the persistent
        # snapshot (NOT overwritten on failures, keeps last known state).
        snapshot = self.coordinator.data
        if snapshot is None:
            return None
        return self.entity_description.value_fn(snapshot)

    @property
    def available(self) -> bool:
        # Connectivity sensors are ALWAYS available - they reflect the
        # connectivity state itself.
        if self.entity_description.always_available:
            return True
        # Other sensors: available as long as we ever got data
        snap = self.coordinator.data
        if snap is None:
            return False
        return snap.last_successful_update is not None
