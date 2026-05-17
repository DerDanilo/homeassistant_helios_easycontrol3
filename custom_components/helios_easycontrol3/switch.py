"""Switches: Main Power, Weekly Schedule, Cool Recovery + Plug-Confirmed.

Cool Recovery requires a physical plug ("Stopfen") to be removed first.
The WebUI tracks this confirmation locally (no Modbus register), so we
replicate the same safety logic in HA via a dedicated plug_confirmed switch.

Logic:
  - plug_confirmed=False blocks turn_on of cool_recovery
  - plug_confirmed auto-syncs with cool_recovery state via the coordinator:
      * cool_recovery currently ON  -> infer plug_confirmed=True
      * cool_recovery transitions ON->OFF -> reset plug_confirmed=False
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from homeassistant.components.switch import (
    SwitchEntity,
    SwitchEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import addresses as A
from .const import DOMAIN
from .coordinator import EasyControls3Coordinator, KWLSnapshot
from .entity import EasyControlsBaseEntity


@dataclass(frozen=True, kw_only=True)
class _SwitchDef(SwitchEntityDescription):
    address: int
    is_on_fn: Callable[[KWLSnapshot], bool | None]
    on_value: int = 1
    off_value: int = 0


SWITCHES: tuple[_SwitchDef, ...] = (
    _SwitchDef(
        key="weekly_timer_enabled",
        translation_key="weekly_timer_enabled",
        icon="mdi:calendar-clock",
        entity_category=EntityCategory.CONFIG,
        address=A.ADDR_WEEKLY_TIMER_ENABLED,
        is_on_fn=lambda s: s.weekly_timer_enabled,
    ),
    # Vacation mode on/off. End-date / mode-during-vacation must be set in the
    # Helios WebUI — we only expose the master enable flag here.
    _SwitchDef(
        key="vacation_active",
        translation_key="vacation_active",
        icon="mdi:bag-suitcase",
        entity_category=EntityCategory.CONFIG,
        address=A.ADDR_TIMED_FUNCTION_ENABLED,
        is_on_fn=lambda s: s.vacation_active,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    coordinator = hass.data[DOMAIN][entry.entry_id]
    entities: list[SwitchEntity] = [_GenericSwitch(coordinator, d) for d in SWITCHES]
    entities.append(_OnOffSwitch(coordinator))
    entities.append(_PlugConfirmedSwitch(coordinator))
    entities.append(_CoolRecoverySwitch(coordinator))
    async_add_entities(entities)


class _GenericSwitch(EasyControlsBaseEntity, SwitchEntity):
    entity_description: _SwitchDef

    def __init__(self, coordinator: EasyControls3Coordinator, description: _SwitchDef):
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{coordinator.serial_str() or coordinator.host}_{description.key}"

    @property
    def is_on(self) -> bool | None:
        return self.entity_description.is_on_fn(self.coordinator.data) if self.coordinator.data else None

    async def async_turn_on(self, **kwargs) -> None:
        await self.coordinator.client.write_variable(
            self.entity_description.address, self.entity_description.on_value
        )
        await self.coordinator.request_refresh_after_write()

    async def async_turn_off(self, **kwargs) -> None:
        await self.coordinator.client.write_variable(
            self.entity_description.address, self.entity_description.off_value
        )
        await self.coordinator.request_refresh_after_write()


class _OnOffSwitch(EasyControlsBaseEntity, SwitchEntity):
    """Master switch: turns the entire KWL on/off via MODE variable."""

    _attr_has_entity_name = True
    _attr_translation_key = "main_power"
    _attr_icon = "mdi:power"

    def __init__(self, coordinator: EasyControls3Coordinator):
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.serial_str() or coordinator.host}_kwl_on_off"

    @property
    def is_on(self) -> bool | None:
        return self.coordinator.data.is_on if self.coordinator.data else None

    async def async_turn_on(self, **kwargs) -> None:
        await self.coordinator.client.write_variable(A.ADDR_MODE, A.MODE_NORMAL)
        await self.coordinator.request_refresh_after_write()

    async def async_turn_off(self, **kwargs) -> None:
        await self.coordinator.client.write_variable(A.ADDR_MODE, A.MODE_OFF)
        await self.coordinator.request_refresh_after_write()


class _PlugConfirmedSwitch(EasyControlsBaseEntity, SwitchEntity):
    """HA-internal safety confirmation: 'Wurde der Stopfen entfernt?'.

    Mirrors the WebUI safety prompt that is required before Cool Recovery
    can be activated. State is persisted in HA storage and auto-syncs with
    cool_recovery (see Coordinator._sync_plug_confirmed_with_cool_recovery).
    """

    _attr_has_entity_name = True
    _attr_translation_key = "cool_recovery_plug_confirmed"
    _attr_icon = "mdi:lock-open-check"
    _attr_entity_category = EntityCategory.CONFIG

    def __init__(self, coordinator: EasyControls3Coordinator):
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.serial_str() or coordinator.host}_plug_confirmed"

    @property
    def is_on(self) -> bool | None:
        return self.coordinator.data.plug_confirmed if self.coordinator.data else None

    async def async_turn_on(self, **kwargs) -> None:
        await self.coordinator.set_plug_confirmed(True)

    async def async_turn_off(self, **kwargs) -> None:
        await self.coordinator.set_plug_confirmed(False)


class _CoolRecoverySwitch(EasyControlsBaseEntity, SwitchEntity):
    """Cool Recovery (Kälterückgewinnung).

    Modbus addr 20516. Helios uses the value as a direct enable flag
    (1=on, 0=off) despite the variable's "DISABLED" suffix.

    Turn-on requires plug_confirmed=True (mirrors WebUI safety prompt).
    Turn-off is always allowed.
    """

    _attr_has_entity_name = True
    _attr_translation_key = "cool_recovery_enabled"
    _attr_icon = "mdi:snowflake-thermometer"
    _attr_entity_category = EntityCategory.CONFIG

    def __init__(self, coordinator: EasyControls3Coordinator):
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.serial_str() or coordinator.host}_cool_recovery_enabled"

    @property
    def is_on(self) -> bool | None:
        return self.coordinator.data.cool_recovery_enabled if self.coordinator.data else None

    async def async_turn_on(self, **kwargs) -> None:
        if not (self.coordinator.data and self.coordinator.data.plug_confirmed):
            raise HomeAssistantError(
                "Cool Recovery kann nicht aktiviert werden: bitte zuerst den "
                "Schalter 'Cool Recovery - Plug Confirmed' einschalten "
                "(physische Stopfen-Entfernung am Gerät bestätigen)."
            )
        await self.coordinator.client.write_variable(A.ADDR_COOLRECOVERY_DISABLED, 1)
        await self.coordinator.request_refresh_after_write()

    async def async_turn_off(self, **kwargs) -> None:
        await self.coordinator.client.write_variable(A.ADDR_COOLRECOVERY_DISABLED, 0)
        await self.coordinator.request_refresh_after_write()
