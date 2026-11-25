"""Config flow for TuneIn Radio: choose the default media player."""

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
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import entity_registry as er, selector

from .const import CONF_PLAYER, DOMAIN, NAME


def _player_schema(hass: HomeAssistant) -> vol.Schema:
    """Offer players that can play a stream, except TuneIn's own."""
    own = [
        entry.entity_id
        for entry in er.async_get(hass).entities.values()
        if entry.platform == DOMAIN and entry.domain == MEDIA_PLAYER_DOMAIN
    ]
    return vol.Schema(
        {
            vol.Required(CONF_PLAYER): selector.EntitySelector(
                selector.EntitySelectorConfig(
                    exclude_entities=own,
                    filter=selector.EntityFilterSelectorConfig(
                        domain=MEDIA_PLAYER_DOMAIN,
                        supported_features=[
                            "media_player.MediaPlayerEntityFeature.PLAY_MEDIA"
                        ],
                    ),
                )
            )
        }
    )


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
        """Pick the default media player."""
        if user_input is not None:
            return self.async_create_entry(title=NAME, data={}, options=user_input)
        return self.async_show_form(
            step_id="user", data_schema=_player_schema(self.hass)
        )


class TuneInOptionsFlow(OptionsFlowWithReload):
    """Change the default media player."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Pick the default media player."""
        if user_input is not None:
            return self.async_create_entry(data=user_input)
        return self.async_show_form(
            step_id="init",
            data_schema=self.add_suggested_values_to_schema(
                _player_schema(self.hass), self.config_entry.options
            ),
        )
