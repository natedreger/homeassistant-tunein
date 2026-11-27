"""Config flow for TuneIn Radio: choose the default media player."""

from __future__ import annotations

import json
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

from .api import STATION_ID_RE, TuneInError
from .const import ATTR_STATION_ID, CONF_PLAYER, CONF_STATION_APIS, DOMAIN, NAME
from .favorites import station_labels

CONF_URL = "url"
CONF_BODY = "body"
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


def _is_json(text: str) -> bool:
    try:
        json.loads(text)
    except ValueError:
        return False
    return True


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
    """Change the default media player, or set a station's own API."""

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
        """Set or remove the API of one station."""
        apis = dict(self.config_entry.options.get(CONF_STATION_APIS, {}))
        errors: dict[str, str] = {}
        if user_input is not None:
            station_id = user_input[ATTR_STATION_ID].strip()
            url = user_input.get(CONF_URL, "").strip()
            body = user_input.get(CONF_BODY, "").strip()
            if not STATION_ID_RE.match(station_id):
                errors[ATTR_STATION_ID] = "invalid_station"
            elif url and not URL_RE.match(url):
                errors[CONF_URL] = "invalid_url"
            elif url and body and not _is_json(body):
                errors[CONF_BODY] = "invalid_body"
            else:
                if url:
                    apis[station_id] = {"url": url, "body": body} if body else url
                else:
                    apis.pop(station_id, None)
                return self._save(**{CONF_STATION_APIS: apis})

        data = getattr(self.config_entry, "runtime_data", None)
        favorites = station_labels(data.favorites.stations if data else [])
        stations = [
            selector.SelectOptionDict(value=station_id, label=name)
            for name, station_id in favorites.items()
        ]
        names = {station_id: name for name, station_id in favorites.items()}
        for station_id in apis.keys() - names.keys():  # not a favorite: ask TuneIn
            names[station_id] = station_id
            if data:
                try:
                    names[station_id] = (await data.client.describe(station_id)).name
                except TuneInError:
                    pass  # show the ID
        schema = vol.Schema(
            {
                vol.Required(ATTR_STATION_ID): selector.SelectSelector(
                    selector.SelectSelectorConfig(options=stations, custom_value=True)
                ),
                vol.Optional(CONF_URL): selector.TextSelector(
                    selector.TextSelectorConfig(type=selector.TextSelectorType.URL)
                ),
                vol.Optional(CONF_BODY): selector.TextSelector(
                    selector.TextSelectorConfig(multiline=True)
                ),
            }
        )
        return self.async_show_form(
            step_id="station_api",
            data_schema=self.add_suggested_values_to_schema(schema, user_input or {}),
            errors=errors,
            description_placeholders={
                "current": "\n".join(
                    f"- {names[k]}: {v}"
                    if isinstance(v, str)
                    else f"- {names[k]}: {v['url']} (with body)"
                    for k, v in apis.items()
                )
                or "- none"
            },
        )
