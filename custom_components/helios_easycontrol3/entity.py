"""Base entity class with DeviceInfo + Coordinator hook.

Subclasses can override their own `available` property (e.g. connectivity
sensors that should always be considered available).
"""

from __future__ import annotations

from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import EasyControls3Coordinator


def _compose_hw_version(type_str: str | None) -> str | None:
    """Return device type as hw_version display string.

    HA shows the hw_version field with label "Hardware" in the device card.
    On Helios this content is actually the "Typ" (e.g. type code 'KWL 250 W ET').
    UUID is exposed as a separate diagnostic sensor (sensor.uuid).
    """
    return type_str if type_str else None

class EasyControlsBaseEntity(CoordinatorEntity[EasyControls3Coordinator]):
    """Common base."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: EasyControls3Coordinator):
        super().__init__(coordinator)

    @property
    def device_info(self) -> DeviceInfo:
        c = self.coordinator
        snap = c.data
        sw = snap.sw_version if snap and snap.sw_version else None
        ident_value = str(snap.serial_number) if snap and snap.serial_number else c.host
        identifiers = {(DOMAIN, ident_value)}
        return DeviceInfo(
            identifiers=identifiers,
            manufacturer="Helios",
            model=c.device_model_str(),
            name=f"Helios {c.device_model_str()}",
            sw_version=sw,
            # Show UUID alongside type code in hw_version field, so it
            # appears in the device info header (top of device page) and not
            # buried in diagnostic sensors.
            hw_version=_compose_hw_version(c.device_type_str()),
            configuration_url=f"http://{c.host}",
            serial_number=c.serial_str() or None,
        )

    @property
    def available(self) -> bool:
        # Default: available once we ever fetched data (snapshot persists
        # past UpdateFailed — see coordinator). Subclasses can use
        # always_available=True.
        snap = self.coordinator.data
        if snap is None:
            return False
        return snap.last_successful_update is not None
