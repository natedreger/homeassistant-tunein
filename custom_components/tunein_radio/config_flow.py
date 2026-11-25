"""Config flow for TuneIn Radio: one click to add, with an optional speaker."""

from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant.components.media_player import DOMAIN as MEDIA_PLAYER_DOMAIN
from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlowWithReload,
)
from homeassistant.core import callback
from homeassistant.helpers import selector

from .const import CONF_PLAYER, DOMAIN, NAME


class TuneInConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for TuneIn Radio."""

    VERSION = 1

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> TuneInOptionsFlow:
        """Return the options flow."""
        return TuneInOptionsFlow()

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Confirm setup."""
        if user_input is not None:
            return self.async_create_entry(title=NAME, data={})
        return self.async_show_form(step_id="user")


class TuneInOptionsFlow(OptionsFlowWithReload):
    """Choose the speaker for the favorites select."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Pick a media player, or leave empty to use OwnTone."""
        if user_input is not None:
            return self.async_create_entry(data=user_input)
        schema = vol.Schema(
            {
                vol.Optional(CONF_PLAYER): selector.EntitySelector(
                    selector.EntitySelectorConfig(domain=MEDIA_PLAYER_DOMAIN)
                )
            }
        )
        return self.async_show_form(
            step_id="init",
            data_schema=self.add_suggested_values_to_schema(
                schema, self.config_entry.options
            ),
        )
