"""Config flow for TuneIn Radio: choose the default media player."""

from __future__ import annotations

import re
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

from .api import STATION_ID_RE
from .const import ATTR_STATION_ID, CONF_PLAYER, CONF_STATION_APIS, DOMAIN, NAME

CONF_URL = "url"
URL_RE = re.compile(r"^https?://\S+$", re.IGNORECASE)


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
    """Change the default media player, or set a station's song API."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Choose what to change."""
        return self.async_show_menu(
            step_id="init", menu_options=["player", "station_api"]
        )

    def _save(self, **changes: Any) -> ConfigFlowResult:
        return self.async_create_entry(data={**self.config_entry.options, **changes})

    async def async_step_player(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Pick the default media player."""
        if user_input is not None:
            return self._save(**user_input)
        return self.async_show_form(
            step_id="player",
            data_schema=self.add_suggested_values_to_schema(
                _player_schema(self.hass), self.config_entry.options
            ),
        )

    async def async_step_station_api(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Set or remove the song API of one station."""
        apis = dict(self.config_entry.options.get(CONF_STATION_APIS, {}))
        errors: dict[str, str] = {}
        if user_input is not None:
            station_id = user_input[ATTR_STATION_ID].strip()
            url = user_input.get(CONF_URL, "").strip()
            if not STATION_ID_RE.match(station_id):
                errors[ATTR_STATION_ID] = "invalid_station"
            elif url and not URL_RE.match(url):
                errors[CONF_URL] = "invalid_url"
            else:
                if url:
                    apis[station_id] = url
                else:
                    apis.pop(station_id, None)
                return self._save(**{CONF_STATION_APIS: apis})

        data = getattr(self.config_entry, "runtime_data", None)
        stations = [
            selector.SelectOptionDict(value=s.id, label=f"{s.name} ({s.id})")
            for s in (data.favorites.stations if data else [])
        ]
        schema = vol.Schema(
            {
                vol.Required(ATTR_STATION_ID): selector.SelectSelector(
                    selector.SelectSelectorConfig(options=stations, custom_value=True)
                ),
                vol.Optional(CONF_URL): selector.TextSelector(
                    selector.TextSelectorConfig(type=selector.TextSelectorType.URL)
                ),
            }
        )
        return self.async_show_form(
            step_id="station_api",
            data_schema=self.add_suggested_values_to_schema(schema, user_input or {}),
            errors=errors,
            description_placeholders={
                "current": "\n".join(f"- {k}: {v}" for k, v in apis.items()) or "- none"
            },
        )
