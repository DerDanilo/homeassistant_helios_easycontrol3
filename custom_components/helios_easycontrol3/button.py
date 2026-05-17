"""Button entities (filter reset, etc.)."""

from __future__ import annotations

import datetime as dt

from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import addresses as A
from .const import DOMAIN
from .coordinator import EasyControls3Coordinator
from .entity import EasyControlsBaseEntity


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    coordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([_ResetFilterButton(coordinator)])


class _ResetFilterButton(EasyControlsBaseEntity, ButtonEntity):
    _attr_has_entity_name = True
    _attr_translation_key = "reset_filter"
    _attr_icon = "mdi:filter-check"

    def __init__(self, coordinator: EasyControls3Coordinator):
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.serial_str() or coordinator.host}_filter_reset"

    async def async_press(self) -> None:
        today = dt.date.today()
        # Helios stores year as (real - 2000)
        await self.coordinator.client.write_variables([
            (A.ADDR_FILTER_CHANGED_DAY, today.day),
            (A.ADDR_FILTER_CHANGED_MONTH, today.month),
            (A.ADDR_FILTER_CHANGED_YEAR, today.year - 2000),
        ])
        await self.coordinator.request_refresh_after_write()
