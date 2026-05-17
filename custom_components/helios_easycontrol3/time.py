"""Time entities for mode duration (Boost & Custom)."""

from __future__ import annotations

import datetime as dt
import math
from collections.abc import Callable
from dataclasses import dataclass

from homeassistant.components.time import TimeEntity, TimeEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import addresses as A
from .const import DOMAIN
from .coordinator import EasyControls3Coordinator, KWLSnapshot
from .entity import EasyControlsBaseEntity

MAX_MIN = 24 * 60  # 24 hours


@dataclass(frozen=True, kw_only=True)
class _TimeDef(TimeEntityDescription):
    address: int
    minutes_fn: Callable[[KWLSnapshot], int | None]


TIMES: tuple[_TimeDef, ...] = (
    # Keys use "duration_<mode>" so entity_id slug matches the display name
    # pattern ("Duration (Boost)" -> "duration_boost"). Existing installs
    # may see the old "boost_duration" entity as orphaned after this change.
    _TimeDef(
        key="duration_boost",
        translation_key="duration_boost",
        icon="mdi:timer-outline",
        address=A.ADDR_BOOST_TIME,
        minutes_fn=lambda s: s.intensive_duration_min,
    ),
    _TimeDef(
        key="duration_individual",
        translation_key="duration_individual",
        icon="mdi:timer-outline",
        address=A.ADDR_FIREPLACE_TIME,
        minutes_fn=lambda s: s.individual_duration_min,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    coordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([_GenericTime(coordinator, d) for d in TIMES])


class _GenericTime(EasyControlsBaseEntity, TimeEntity):
    entity_description: _TimeDef

    def __init__(self, coordinator: EasyControls3Coordinator, description: _TimeDef):
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{coordinator.serial_str() or coordinator.host}_{description.key}"

    @property
    def native_value(self) -> dt.time | None:
        if self.coordinator.data is None:
            return None
        m = self.entity_description.minutes_fn(self.coordinator.data)
        if m is None:
            return None
        h = math.floor(m / 60)
        mm = int(m - h * 60)
        try:
            return dt.time(h, mm)
        except ValueError:
            return None

    async def async_set_value(self, value: dt.time) -> None:
        minutes = value.hour * 60 + value.minute
        if minutes < 1:
            minutes = 1
        if minutes > MAX_MIN:
            minutes = MAX_MIN
        await self.coordinator.client.write_variable(
            self.entity_description.address, minutes
        )
        await self.coordinator.request_refresh_after_write()
