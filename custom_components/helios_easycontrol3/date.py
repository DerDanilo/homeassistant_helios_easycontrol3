"""Date entity: last filter change date (directly settable).

Uses the same device registers as the WebUI and the reset button
(FILTER_CHANGED_DAY/MONTH/YEAR; year stored as real-2000). Allows the
user to CORRECT the date, e.g. after an accidental press of the
"Filter Change - Reset to Today" button.
"""

from __future__ import annotations

import datetime as dt

from homeassistant.components.date import DateEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import addresses as A
from .const import DOMAIN
from .coordinator import EasyControls3Coordinator
from .entity import EasyControlsBaseEntity


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    coordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([_FilterChangedDate(coordinator)])


class _FilterChangedDate(EasyControlsBaseEntity, DateEntity):
    _attr_has_entity_name = True
    _attr_translation_key = "filter_changed_date"
    _attr_icon = "mdi:calendar-edit"
    _attr_entity_category = EntityCategory.CONFIG

    def __init__(self, coordinator: EasyControls3Coordinator):
        super().__init__(coordinator)
        self._attr_unique_id = (
            f"{coordinator.serial_str() or coordinator.host}_filter_changed_date"
        )

    @property
    def native_value(self) -> dt.date | None:
        snap = self.coordinator.data
        return snap.filter_changed_date if snap else None

    async def async_set_value(self, value: dt.date) -> None:
        if value > dt.date.today():
            raise HomeAssistantError(
                "Das Filterwechsel-Datum kann nicht in der Zukunft liegen."
            )
        if value.year < 2000 or value.year > 2255:
            raise HomeAssistantError(
                "Jahr muss zwischen 2000 und 2255 liegen "
                "(Geräte-Format: Jahr minus 2000, ein Byte)."
            )
        # Same coalesce key as the reset button — both write the same
        # registers, latest wins.
        await self.coordinator.queue_write([
            (A.ADDR_FILTER_CHANGED_DAY, value.day),
            (A.ADDR_FILTER_CHANGED_MONTH, value.month),
            (A.ADDR_FILTER_CHANGED_YEAR, value.year - 2000),
        ], coalesce_key="filter_date")
