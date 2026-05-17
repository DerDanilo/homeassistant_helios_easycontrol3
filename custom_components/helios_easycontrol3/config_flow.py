"""Config flow for Helios easyControls 3.0."""

from __future__ import annotations

import ipaddress
import logging
from typing import Any

import voluptuous as vol

from homeassistant import config_entries, exceptions
from homeassistant.config_entries import ConfigEntry, OptionsFlow
from homeassistant.core import HomeAssistant, callback

from .const import CONF_HOST, DOMAIN

_LOGGER = logging.getLogger(__name__)

DATA_SCHEMA = vol.Schema({vol.Required(CONF_HOST): str})

OPTIONS_SCHEMA = vol.Schema({
    vol.Optional(
        "scan_interval",
        default=60,
    ): vol.All(vol.Coerce(int), vol.Range(min=5, max=600)),
})


async def _validate_host(hass: HomeAssistant, host: str) -> dict[str, Any]:
    """Validate host format and reachability."""
    # Lazy-import the client so config_flow can be loaded even if the
    # `websockets` requirement isn't installed at module-import time.
    from .client import EasyControls3Client

    try:
        try:
            ipaddress.ip_address(host)
        except ValueError:
            if not host or "/" in host:
                raise InvalidHost
        client = EasyControls3Client(host)
        ok = await client.test_connection()
        if not ok:
            raise CannotConnect
        return {"title": f"easyControls @ {host}"}
    except CannotConnect:
        raise
    except InvalidHost:
        raise
    except Exception as err:  # noqa: BLE001
        _LOGGER.exception("Unexpected error during host validation: %s", err)
        raise CannotConnect from err


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """User-led flow to add a KWL."""

    VERSION = 1

    async def async_step_user(self, user_input: dict[str, Any] | None = None):
        errors: dict[str, str] = {}
        if user_input is not None:
            try:
                info = await _validate_host(self.hass, user_input[CONF_HOST])
                await self.async_set_unique_id(user_input[CONF_HOST])
                self._abort_if_unique_id_configured()
                return self.async_create_entry(title=info["title"], data=user_input)
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except InvalidHost:
                errors[CONF_HOST] = "invalid_host"

        return self.async_show_form(
            step_id="user", data_schema=DATA_SCHEMA, errors=errors
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlow:
        return EasyControls3OptionsFlow(config_entry)


class EasyControls3OptionsFlow(OptionsFlow):
    """Allow the user to change scan_interval after the integration is set up."""

    def __init__(self, config_entry: ConfigEntry):
        self._entry = config_entry

    async def async_step_init(self, user_input=None):
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)
        current = self._entry.options.get("scan_interval", 60)
        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema({
                vol.Optional(
                    "scan_interval",
                    default=current,
                ): vol.All(vol.Coerce(int), vol.Range(min=5, max=600)),
            }),
        )


class CannotConnect(exceptions.HomeAssistantError):
    """Could not connect to the device."""


class InvalidHost(exceptions.HomeAssistantError):
    """Invalid host."""
