"""Select entity for KWL mode (Home/Away/Boost/Custom)."""

from __future__ import annotations

from homeassistant.components.select import SelectEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import addresses as A
from .const import DOMAIN
from .coordinator import EasyControls3Coordinator
from .entity import EasyControlsBaseEntity

MODE_HOME = "Home"
MODE_AWAY = "Away"
MODE_BOOST = "Boost"
MODE_INDIVIDUAL = "Individual"

OPTIONS = [MODE_HOME, MODE_AWAY, MODE_BOOST, MODE_INDIVIDUAL]


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    coordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([_KWLModeSelect(coordinator)])


class _KWLModeSelect(EasyControlsBaseEntity, SelectEntity):
    _attr_has_entity_name = True
    _attr_translation_key = "mode"
    _attr_icon = "mdi:fan-auto"
    _attr_options = OPTIONS

    def __init__(self, coordinator: EasyControls3Coordinator):
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.serial_str() or coordinator.host}_mode"

    @property
    def current_option(self) -> str | None:
        s = self.coordinator.data
        if s is None:
            return None
        # Priority: individual (fireplace timer) > boost (boost timer) > away/home (state)
        if s.fireplace_timer and s.fireplace_timer > 0:
            return MODE_INDIVIDUAL
        if s.boost_timer and s.boost_timer > 0:
            return MODE_BOOST
        if s.state_code != A.STATE_HOME:
            return MODE_AWAY
        return MODE_HOME

    async def async_select_option(self, option: str) -> None:
        snap = self.coordinator.data
        if option == MODE_HOME:
            await self.coordinator.client.write_variables([
                (A.ADDR_STATE, A.STATE_HOME),
                (A.ADDR_BOOST_TIMER, 0),
                (A.ADDR_FIREPLACE_TIMER, 0),
            ])
        elif option == MODE_AWAY:
            await self.coordinator.client.write_variables([
                (A.ADDR_STATE, A.STATE_AWAY),
                (A.ADDR_BOOST_TIMER, 0),
                (A.ADDR_FIREPLACE_TIMER, 0),
            ])
        elif option == MODE_BOOST:
            duration = (snap.intensive_duration_min if snap else None) or 60
            await self.coordinator.client.write_variables([
                (A.ADDR_BOOST_TIMER, duration),
                (A.ADDR_FIREPLACE_TIMER, 0),
            ])
        elif option == MODE_INDIVIDUAL:
            duration = (snap.individual_duration_min if snap else None) or 60
            await self.coordinator.client.write_variables([
                (A.ADDR_BOOST_TIMER, 0),
                (A.ADDR_FIREPLACE_TIMER, duration),
            ])
        else:
            return
        await self.coordinator.request_refresh_after_write()
