"""Fan platform — exposes the KWL as a single HA-native fan entity.

Combines on/off, preset mode (Home/Away/Boost/Individual) and percentage
(per-mode fan power level setpoint) into one entity so voice assistants
and standard fan cards work out of the box.

This is the primary control surface for the unit — there is no separate
Main Power switch or Mode select entity. The per-mode
`number.*_fan_power_level_*` and `number.*_supply_air_target_*` entities
remain available for setting the saved per-mode setpoints precisely
(NumberMode.BOX = text input).

Write path: ALL writes go through coordinator.queue_write() — user
interactions are accepted instantly (optimistic overlay below), but
delivery to the device is rate-limited with latest-wins coalescing per
channel. Rapidly tapping through presets sends only the last one to the
unit — the KWL's embedded webserver can reset the unit under write bursts.
"""

from __future__ import annotations

import logging
import time
from typing import Any

from homeassistant.components.fan import FanEntity, FanEntityFeature
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import addresses as A
from .const import DOMAIN
from .coordinator import EasyControls3Coordinator
from .entity import EasyControlsBaseEntity

LOGGER = logging.getLogger(__name__)

PRESET_HOME = "Home"
PRESET_AWAY = "Away"
PRESET_BOOST = "Boost"
PRESET_INDIVIDUAL = "Individual"
PRESET_MODES = [PRESET_HOME, PRESET_AWAY, PRESET_BOOST, PRESET_INDIVIDUAL]

# How long an optimistic (locally assumed) state may mask the polled state.
# The button flips immediately on tap and only snaps back to the device's
# reported mode if the unit hasn't confirmed within this window.
OPTIMISTIC_TTL_SECONDS = 15.0


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
        # Optimistic overlays: (value, monotonic_expiry). Shown until the
        # polled snapshot confirms the value or the TTL expires. Needed
        # because the rate limiter may deliver the write with a delay —
        # the UI must reflect the accepted click immediately.
        self._opt_preset: tuple[str, float] | None = None
        self._opt_power: tuple[bool, float] | None = None

    # ----- State readers --------------------------------------------------

    def _real_is_on(self) -> bool | None:
        snap = self.coordinator.data
        if snap is None:
            return None
        # Defensive: any active timer means the unit is running, even if a
        # transient snapshot read misclassifies the MODE byte. This prevents
        # HA from wrapping a `fan.set_preset_mode` call as
        # `fan.turn_on(preset_mode=...)`. (snap.is_on itself is derived as
        # MODE != OFF, so defrost/manual/testing don't read as "off".)
        if (snap.boost_timer and snap.boost_timer > 0) or \
           (snap.fireplace_timer and snap.fireplace_timer > 0):
            return True
        return snap.is_on

    @property
    def is_on(self) -> bool | None:
        if self._opt_power is not None:
            val, until = self._opt_power
            real = self._real_is_on()
            if real == val or time.monotonic() >= until:
                self._opt_power = None  # confirmed by device or expired
            else:
                return val
        return self._real_is_on()

    def _real_preset(self) -> str | None:
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
    def preset_mode(self) -> str | None:
        if self._opt_preset is not None:
            val, until = self._opt_preset
            real = self._real_preset()
            if real == val or time.monotonic() >= until:
                self._opt_preset = None  # confirmed by device or expired
            else:
                return val
        return self._real_preset()

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

    async def _read_mode_fresh(self) -> int | None:
        """Read ADDR_MODE directly from the device, bypassing the snapshot.

        A MODE write into a RUNNING unit resets the KWL state machine and
        physically cycles the fans OFF→ON (~5s). The decision whether to
        write MODE must therefore never rely on the polled snapshot: it can
        be up to scan_interval seconds old, and transient device modes
        (e.g. DEFROST) were previously misclassified as "off" there.
        Returns None when the read fails (state unknown).
        """
        try:
            return await self.coordinator.client.read_variable(A.ADDR_MODE)
        except Exception as err:  # noqa: BLE001 — any failure means "unknown"
            LOGGER.debug("Fresh ADDR_MODE read failed: %s", err)
            return None

    def _set_optimistic(self, *, preset: str | None = None,
                        power: bool | None = None) -> None:
        expiry = time.monotonic() + OPTIMISTIC_TTL_SECONDS
        if preset is not None:
            self._opt_preset = (preset, expiry)
        if power is not None:
            self._opt_power = (power, expiry)
        self.async_write_ha_state()

    async def async_turn_on(
        self,
        percentage: int | None = None,
        preset_mode: str | None = None,
        **kwargs: Any,
    ) -> None:
        # Write MODE=NORMAL only when the unit is REALLY off — verified via
        # a fresh device read. Rationale: HA routes `fan.set_preset_mode`
        # through `fan.turn_on(preset_mode=...)` whenever it believes the
        # entity is off; a MODE write into a running unit physically cycles
        # it OFF→ON (v1.1.1 "shutdown on switch to Home" bug).
        mode = await self._read_mode_fresh()
        really_off = (mode == A.MODE_OFF) or (mode is None and self.is_on is False)
        LOGGER.debug(
            "turn_on(percentage=%s, preset=%s): fresh MODE=%s -> %s",
            percentage, preset_mode, mode,
            "queueing MODE_NORMAL" if really_off else "unit running, no MODE write",
        )
        if really_off:
            self._set_optimistic(power=True)
            await self.coordinator.queue_write(
                [(A.ADDR_MODE, A.MODE_NORMAL)], coalesce_key="power"
            )
        if preset_mode is not None:
            await self.async_set_preset_mode(preset_mode)
        if percentage is not None:
            await self.async_set_percentage(percentage)

    async def async_turn_off(self, **kwargs: Any) -> None:
        # Mirror of async_turn_on: write MODE=OFF only if the unit is not
        # already off (fresh device read). On read failure the explicit
        # user intent ("turn off") wins — writing OFF to an already-off
        # unit does not cycle the fans.
        mode = await self._read_mode_fresh()
        LOGGER.debug(
            "turn_off: fresh MODE=%s -> %s", mode,
            "queueing MODE_OFF" if mode != A.MODE_OFF else "already off, skipping",
        )
        if mode != A.MODE_OFF:
            self._set_optimistic(power=False)
            await self.coordinator.queue_write(
                [(A.ADDR_MODE, A.MODE_OFF)], coalesce_key="power"
            )

    async def async_set_preset_mode(self, preset_mode: str) -> None:
        if preset_mode not in PRESET_MODES:
            return
        snap = self.coordinator.data
        if preset_mode == PRESET_HOME:
            items = [
                (A.ADDR_STATE, A.STATE_HOME),
                (A.ADDR_BOOST_TIMER, 0),
                (A.ADDR_FIREPLACE_TIMER, 0),
            ]
        elif preset_mode == PRESET_AWAY:
            items = [
                (A.ADDR_STATE, A.STATE_AWAY),
                (A.ADDR_BOOST_TIMER, 0),
                (A.ADDR_FIREPLACE_TIMER, 0),
            ]
        elif preset_mode == PRESET_BOOST:
            duration = (snap.intensive_duration_min if snap else None) or 60
            items = [
                (A.ADDR_BOOST_TIMER, duration),
                (A.ADDR_FIREPLACE_TIMER, 0),
            ]
        else:  # PRESET_INDIVIDUAL
            duration = (snap.individual_duration_min if snap else None) or 60
            items = [
                (A.ADDR_BOOST_TIMER, 0),
                (A.ADDR_FIREPLACE_TIMER, duration),
            ]
        # Show the target preset immediately; the rate limiter may deliver
        # the write later (rapid taps: only the LAST preset reaches the unit).
        self._set_optimistic(preset=preset_mode)
        await self.coordinator.queue_write(items, coalesce_key="preset")

    async def async_set_percentage(self, percentage: int) -> None:
        """Write the percentage to the currently active preset's saved setpoint."""
        percentage = max(1, min(100, percentage))
        pm = self.preset_mode
        if pm == PRESET_HOME:
            items = [(A.ADDR_HOME_SPEED_SETTING, percentage)]
        elif pm == PRESET_AWAY:
            items = [(A.ADDR_AWAY_SPEED_SETTING, percentage)]
        elif pm == PRESET_BOOST:
            items = [(A.ADDR_BOOST_SPEED_SETTING, percentage)]
        elif pm == PRESET_INDIVIDUAL:
            # Set both supply and extract to the same percentage.
            items = [
                (A.ADDR_FIREPLACE_SUPP_FAN, percentage),
                (A.ADDR_FIREPLACE_EXTR_FAN, percentage),
            ]
        else:
            return
        await self.coordinator.queue_write(items, coalesce_key="speed")
