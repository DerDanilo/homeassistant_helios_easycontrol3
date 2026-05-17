"""Fan platform — exposes the KWL as a single HA-native fan entity.

Combines on/off, preset mode (Home/Away/Boost/Individual) and percentage
(per-mode fan power level setpoint) into one entity so voice assistants
and standard fan cards work out of the box.

This is the primary control surface for the unit — there is no separate
Main Power switch or Mode select entity. The per-mode
`number.*_fan_power_level_*` and `number.*_supply_air_target_*` entities
remain available for setting the saved per-mode setpoints precisely
(NumberMode.BOX = text input).
"""

from __future__ import annotations

from typing import Any

from homeassistant.components.fan import FanEntity, FanEntityFeature
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import addresses as A
from .const import DOMAIN
from .coordinator import EasyControls3Coordinator
from .entity import EasyControlsBaseEntity

PRESET_HOME = "Home"
PRESET_AWAY = "Away"
PRESET_BOOST = "Boost"
PRESET_INDIVIDUAL = "Individual"
PRESET_MODES = [PRESET_HOME, PRESET_AWAY, PRESET_BOOST, PRESET_INDIVIDUAL]


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    coordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([_KWLFan(coordinator)])


class _KWLFan(EasyControlsBaseEntity, FanEntity):
    """KWL as a HA fan entity (on/off + preset + percentage)."""

    _attr_has_entity_name = True
    _attr_translation_key = "ventilation_unit"
    _attr_icon = "mdi:hvac"
    _attr_preset_modes = PRESET_MODES
    _attr_supported_features = (
        FanEntityFeature.TURN_ON
        | FanEntityFeature.TURN_OFF
        | FanEntityFeature.SET_SPEED
        | FanEntityFeature.PRESET_MODE
    )

    def __init__(self, coordinator: EasyControls3Coordinator):
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.serial_str() or coordinator.host}_fan"

    # ----- State readers --------------------------------------------------

    @property
    def is_on(self) -> bool | None:
        snap = self.coordinator.data
        return snap.is_on if snap else None

    @property
    def preset_mode(self) -> str | None:
        snap = self.coordinator.data
        if snap is None:
            return None
        if snap.fireplace_timer and snap.fireplace_timer > 0:
            return PRESET_INDIVIDUAL
        if snap.boost_timer and snap.boost_timer > 0:
            return PRESET_BOOST
        if snap.state_code != A.STATE_HOME:
            return PRESET_AWAY
        return PRESET_HOME

    @property
    def percentage(self) -> int | None:
        """Fan power level of the currently active preset (read from saved setpoint)."""
        snap = self.coordinator.data
        if snap is None:
            return None
        pm = self.preset_mode
        if pm == PRESET_HOME:
            return snap.home_speed
        if pm == PRESET_AWAY:
            return snap.away_speed
        if pm == PRESET_BOOST:
            return snap.boost_speed
        if pm == PRESET_INDIVIDUAL:
            # Two independent settings — average them for the single-percentage
            # representation. Use the per-direction Number entities for precise
            # asymmetric control.
            s = snap.individual_supply_speed
            e = snap.individual_extract_speed
            if s is not None and e is not None:
                return round((s + e) / 2)
            return s if s is not None else e
        return snap.current_fan_speed

    # ----- Write actions --------------------------------------------------

    async def async_turn_on(
        self,
        percentage: int | None = None,
        preset_mode: str | None = None,
        **kwargs: Any,
    ) -> None:
        await self.coordinator.client.write_variable(A.ADDR_MODE, A.MODE_NORMAL)
        if preset_mode is not None:
            await self.async_set_preset_mode(preset_mode)
        if percentage is not None:
            await self.async_set_percentage(percentage)
        await self.coordinator.request_refresh_after_write()

    async def async_turn_off(self, **kwargs: Any) -> None:
        await self.coordinator.client.write_variable(A.ADDR_MODE, A.MODE_OFF)
        await self.coordinator.request_refresh_after_write()

    async def async_set_preset_mode(self, preset_mode: str) -> None:
        if preset_mode not in PRESET_MODES:
            return
        snap = self.coordinator.data
        if preset_mode == PRESET_HOME:
            await self.coordinator.client.write_variables([
                (A.ADDR_STATE, A.STATE_HOME),
                (A.ADDR_BOOST_TIMER, 0),
                (A.ADDR_FIREPLACE_TIMER, 0),
            ])
        elif preset_mode == PRESET_AWAY:
            await self.coordinator.client.write_variables([
                (A.ADDR_STATE, A.STATE_AWAY),
                (A.ADDR_BOOST_TIMER, 0),
                (A.ADDR_FIREPLACE_TIMER, 0),
            ])
        elif preset_mode == PRESET_BOOST:
            duration = (snap.intensive_duration_min if snap else None) or 60
            await self.coordinator.client.write_variables([
                (A.ADDR_BOOST_TIMER, duration),
                (A.ADDR_FIREPLACE_TIMER, 0),
            ])
        elif preset_mode == PRESET_INDIVIDUAL:
            duration = (snap.individual_duration_min if snap else None) or 60
            await self.coordinator.client.write_variables([
                (A.ADDR_BOOST_TIMER, 0),
                (A.ADDR_FIREPLACE_TIMER, duration),
            ])
        await self.coordinator.request_refresh_after_write()

    async def async_set_percentage(self, percentage: int) -> None:
        """Write the percentage to the currently active preset's saved setpoint."""
        percentage = max(1, min(100, percentage))
        pm = self.preset_mode
        if pm == PRESET_HOME:
            await self.coordinator.client.write_variable(
                A.ADDR_HOME_SPEED_SETTING, percentage
            )
        elif pm == PRESET_AWAY:
            await self.coordinator.client.write_variable(
                A.ADDR_AWAY_SPEED_SETTING, percentage
            )
        elif pm == PRESET_BOOST:
            await self.coordinator.client.write_variable(
                A.ADDR_BOOST_SPEED_SETTING, percentage
            )
        elif pm == PRESET_INDIVIDUAL:
            # Set both supply and extract to the same percentage.
            await self.coordinator.client.write_variables([
                (A.ADDR_FIREPLACE_SUPP_FAN, percentage),
                (A.ADDR_FIREPLACE_EXTR_FAN, percentage),
            ])
        await self.coordinator.request_refresh_after_write()
