"""Select entity that plays favorite stations and shows which one is playing.

Players don't report which TuneIn station they are playing (OwnTone only gives a
queue item number), so this remembers the station that was started and the first
new media_content_id seen afterwards. A different ID later means something else
is playing.
"""

from __future__ import annotations

from collections import Counter
from datetime import datetime
from typing import Any

from homeassistant.components.media_player import (
    ATTR_MEDIA_CONTENT_ID,
    ATTR_MEDIA_CONTENT_TYPE,
    DOMAIN as MEDIA_PLAYER_DOMAIN,
    SERVICE_PLAY_MEDIA,
    MediaPlayerEntityFeature,
    MediaType,
)
from homeassistant.components.select import SelectEntity
from homeassistant.const import ATTR_ENTITY_ID
from homeassistant.core import Event, HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.event import async_call_later, async_track_state_change_event
from homeassistant.helpers.restore_state import RestoredExtraData, RestoreEntity

from . import TuneInConfigEntry, media_source_id
from .api import Station, TuneInError
from .const import ATTR_STATION_ID, CONF_PLAYER, OWNTONE_PLATFORM, PANEL_ICON, SIGNAL_PLAY

# How long to wait for the player to report a new media_content_id.
START_TIMEOUT = 20
ACTIVE_STATES = ("playing", "paused", "buffering", "on")


async def async_setup_entry(
    hass: HomeAssistant,
    entry: TuneInConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Add the favorites select."""
    async_add_entities([FavoritesSelect(hass, entry)])


def _owntone_player(hass: HomeAssistant) -> str | None:
    """The OwnTone server entity (its output "zones" can't play media)."""
    return next(
        (
            e.entity_id
            for e in er.async_get(hass).entities.values()
            if e.platform == OWNTONE_PLATFORM
            and e.domain == MEDIA_PLAYER_DOMAIN
            and not e.disabled
            and e.supported_features & MediaPlayerEntityFeature.PLAY_MEDIA
        ),
        None,
    )


def _labels(stations: list[Station]) -> dict[str, str]:
    """Map option label -> station ID, adding the ID where names collide."""
    names = Counter(s.name for s in stations)
    return {
        (s.name if names[s.name] == 1 else f"{s.name} [{s.id}]"): s.id
        for s in stations
    }


class FavoritesSelect(SelectEntity, RestoreEntity):
    """Favorite stations; the current option is what the speaker is playing."""

    _attr_name = "TuneIn favorites"
    _attr_icon = PANEL_ICON
    _attr_should_poll = False

    def __init__(self, hass: HomeAssistant, entry: TuneInConfigEntry) -> None:
        """Initialize."""
        self._client = entry.runtime_data.client
        self._favorites = entry.runtime_data.favorites
        self._attr_unique_id = f"{entry.entry_id}_favorites"
        self._player = entry.options.get(CONF_PLAYER) or _owntone_player(hass)
        # The station last started on the player:
        # {"station_id", "name", "before", "content_id"}; content_id is None
        # until the player reports the new stream.
        self._started: dict[str, Any] | None = None
        self._cancel_timeout = None
        self._ids: dict[str, str] = {}
        self._attr_options = []

    async def async_added_to_hass(self) -> None:
        """Restore what was playing and follow the player and favorites."""
        await super().async_added_to_hass()
        if last := await self.async_get_last_extra_data():
            saved = last.as_dict()
            # Only trust it for the same speaker, once the stream was confirmed.
            if saved.get("player") == self._player and saved.get("content_id"):
                self._started = {
                    k: saved.get(k)
                    for k in ("station_id", "name", "before", "content_id")
                }
        self.async_on_remove(self._favorites.async_add_listener(self._changed))
        self.async_on_remove(
            async_dispatcher_connect(self.hass, SIGNAL_PLAY, self._station_started)
        )
        if self._player:
            self.async_on_remove(
                async_track_state_change_event(
                    self.hass, [self._player], self._player_changed
                )
            )
        self.async_on_remove(self._stop_timeout)
        self._refresh()

    @property
    def extra_restore_state_data(self) -> RestoredExtraData:
        """Keep the tracked station across restarts, even while stopped."""
        return RestoredExtraData({"player": self._player, **(self._started or {})})

    def _content_id(self) -> str | None:
        state = self.hass.states.get(self._player) if self._player else None
        return state.attributes.get(ATTR_MEDIA_CONTENT_ID) if state else None

    @callback
    def _station_started(self, player: str, station_id: str) -> None:
        """A TuneIn station is about to play on `player`."""
        if player != self._player:
            return
        favorite = self._favorites.get(station_id)
        self._started = {
            "station_id": station_id,
            "name": favorite.name if favorite else None,
            "before": self._content_id(),
            "content_id": None,
        }
        self._stop_timeout()
        self._cancel_timeout = async_call_later(
            self.hass, START_TIMEOUT, self._timed_out
        )
        if not favorite:
            self.hass.async_create_task(self._async_lookup_name(station_id))
        self._changed()

    async def _async_lookup_name(self, station_id: str) -> None:
        try:
            station = await self._client.describe(station_id)
        except TuneInError:
            return
        if self._started and self._started["station_id"] == station_id:
            self._started["name"] = station.name
            self._changed()

    @callback
    def _player_changed(self, event: Event) -> None:
        if started := self._started:
            content_id = self._content_id()
            if content_id is not None:
                if started["content_id"] is None:
                    if content_id != started["before"]:  # our stream started
                        started["content_id"] = content_id
                        self._stop_timeout()
                elif content_id != started["content_id"]:
                    self._started = None  # something else is playing now
        self._changed()

    @callback
    def _timed_out(self, _now: datetime) -> None:
        """No new content ID: the same ID was reused, or playback failed."""
        self._cancel_timeout = None
        if self._started and self._started["content_id"] is None:
            state = self.hass.states.get(self._player)
            if state and state.state in ACTIVE_STATES and self._content_id():
                self._started["content_id"] = self._content_id()
            else:
                self._started = None
            self._changed()

    @callback
    def _stop_timeout(self) -> None:
        if self._cancel_timeout:
            self._cancel_timeout()
            self._cancel_timeout = None

    @callback
    def _changed(self) -> None:
        self._refresh()
        self.async_write_ha_state()

    def _playing(self) -> dict[str, Any] | None:
        """The tracked station, if the player is on it right now."""
        if not (started := self._started):
            return None
        if started["content_id"] is None:  # still starting
            return started
        state = self.hass.states.get(self._player)
        if not state or state.state not in ACTIVE_STATES:
            return None
        return started if self._content_id() == started["content_id"] else None

    def _refresh(self) -> None:
        self._ids = _labels(self._favorites.stations)
        self._attr_options = list(self._ids)
        playing = self._playing()
        station_id = playing["station_id"] if playing else None
        self._attr_current_option = next(
            (label for label, sid in self._ids.items() if sid == station_id), None
        )

    @property
    def extra_state_attributes(self) -> dict[str, str | None]:
        """The station playing now, favorite or not, and the speaker used."""
        playing = self._playing()
        return {
            ATTR_STATION_ID: playing["station_id"] if playing else None,
            "station_name": playing["name"] if playing else None,
            "player": self._player,
        }

    async def async_select_option(self, option: str) -> None:
        """Play a favorite on the speaker."""
        if not self._player:
            raise HomeAssistantError(
                "No speaker for TuneIn favorites; choose one in the integration options"
            )
        previous = self._started
        try:
            await self.hass.services.async_call(
                MEDIA_PLAYER_DOMAIN,
                SERVICE_PLAY_MEDIA,
                {
                    ATTR_ENTITY_ID: self._player,
                    ATTR_MEDIA_CONTENT_ID: media_source_id(self._ids[option]),
                    ATTR_MEDIA_CONTENT_TYPE: MediaType.MUSIC,
                },
                blocking=True,
                context=self._context,
            )
        except Exception:
            self._started = previous
            self._stop_timeout()
            self._changed()
            raise
