"""Tracks which TuneIn station the default media player is playing.

Players don't report which TuneIn station they are playing, so this remembers
the station that was started and the first new media_content_id seen
afterwards. A different ID later means something else is playing.

While the station is on, the current show and song are looked up too.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime, timedelta
from typing import Any

from homeassistant.components.media_player import (
    ATTR_MEDIA_CONTENT_ID,
    ATTR_MEDIA_CONTENT_TYPE,
    DOMAIN as MEDIA_PLAYER_DOMAIN,
    SERVICE_PLAY_MEDIA,
    MediaType,
)
from homeassistant.const import ATTR_ENTITY_ID
from homeassistant.core import Context, Event, HomeAssistant, State, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.event import (
    async_call_later,
    async_track_state_change_event,
    async_track_time_interval,
)
from homeassistant.helpers.storage import Store

from .api import NowPlaying, TuneInClient, TuneInError
from .const import DOMAIN, SIGNAL_PLAY, media_source_id
from .favorites import Favorites

# How long to wait for the player to report a new media_content_id.
START_TIMEOUT = 20
# How often to look up what is on air.
TRACK_INTERVAL = timedelta(seconds=30)
ACTIVE_STATES = ("playing", "paused", "buffering", "on")
STORAGE_KEY = f"{DOMAIN}.now_playing"


class Tracker:
    """Follows one media player and knows which station is on it."""

    def __init__(
        self,
        hass: HomeAssistant,
        client: TuneInClient,
        favorites: Favorites,
        player: str | None,
        station_apis: dict[str, str] | None = None,
    ) -> None:
        """Initialize."""
        self.hass = hass
        self.player = player
        self._client = client
        self._station_apis = station_apis or {}
        self._favorites = favorites
        self._store: Store[dict[str, Any]] = Store(hass, 1, STORAGE_KEY)
        # The station last started on the player:
        # {"station_id", "name", "image", "before", "content_id"}; content_id is
        # None until the player reports the new stream.
        self._started: dict[str, Any] | None = None
        # The last station played, kept after it stops so it can be replayed.
        self.last: dict[str, Any] | None = None
        # (station_id, what is on air); not saved.
        self._track: tuple[str, NowPlaying] | None = None
        self._listeners: list[Callable[[], None]] = []
        self._unsubscribe: list[Callable[[], None]] = []
        self._cancel_timeout: Callable[[], None] | None = None

    async def async_start(self) -> None:
        """Restore what was playing and follow the player and favorites."""
        saved = await self._store.async_load() or {}
        # Only trust it for the same speaker, once the stream was confirmed.
        if saved.get("player") == self.player:
            started = saved.get("started")
            if started and started.get("content_id"):
                self._started = started
        self.last = saved.get("last")

        self._unsubscribe = [
            self._favorites.async_add_listener(self._changed),
            async_dispatcher_connect(self.hass, SIGNAL_PLAY, self._station_started),
            async_track_time_interval(self.hass, self._async_update_track, TRACK_INTERVAL),
        ]
        if self.player:
            self._unsubscribe.append(
                async_track_state_change_event(
                    self.hass, [self.player], self._player_changed
                )
            )

    async def async_stop(self) -> None:
        """Stop following and save."""
        self._stop_timeout()
        while self._unsubscribe:
            self._unsubscribe.pop()()
        await self._store.async_save(self._data())

    @callback
    def async_add_listener(self, listener: Callable[[], None]) -> Callable[[], None]:
        """Call `listener` after each change. Returns a function that unsubscribes."""
        self._listeners.append(listener)
        return lambda: self._listeners.remove(listener)

    @property
    def player_state(self) -> State | None:
        """State of the followed player."""
        return self.hass.states.get(self.player) if self.player else None

    @property
    def playing(self) -> dict[str, Any] | None:
        """The tracked station, if the player is on it right now."""
        if not (started := self._started):
            return None
        if started["content_id"] is None:  # still starting
            return started
        state = self.player_state
        if not state or state.state not in ACTIVE_STATES:
            return None
        return started if self._content_id() == started["content_id"] else None

    @property
    def starting(self) -> bool:
        """Whether a station was started and the player hasn't reported it yet."""
        return bool(self._started) and self._started["content_id"] is None

    @property
    def track(self) -> NowPlaying:
        """What is on air on the station playing now, as far as known."""
        playing = self.playing
        if not playing or self.starting or not self._track:
            return NowPlaying()
        station_id, track = self._track
        return track if station_id == playing["station_id"] else NowPlaying()

    async def _async_update_track(self, _now: datetime | None = None) -> None:
        """Fetch the show and song while a station is playing."""
        if not (playing := self.playing) or self.starting:
            return
        state = self.player_state
        if not state or state.state == "paused":
            return
        station_id = playing["station_id"]
        track = await self._client.now_playing(
            station_id, self._station_apis.get(station_id)
        )
        if self._track != (station_id, track):
            self._track = (station_id, track)
            self._changed()

    @callback
    def _refresh_track(self) -> None:
        """Fetch them now rather than at the next interval."""
        self.hass.async_create_task(self._async_update_track())

    async def async_play(self, station_id: str, context: Context | None) -> None:
        """Play a station on the player."""
        if not self.player:
            raise HomeAssistantError(
                "No default media player; choose one in the TuneIn Radio options"
            )
        previous = (self._started, self.last)
        try:
            await self.hass.services.async_call(
                MEDIA_PLAYER_DOMAIN,
                SERVICE_PLAY_MEDIA,
                {
                    ATTR_ENTITY_ID: self.player,
                    ATTR_MEDIA_CONTENT_ID: media_source_id(station_id),
                    ATTR_MEDIA_CONTENT_TYPE: MediaType.MUSIC,
                },
                blocking=True,
                context=context,
            )
        except Exception:
            self._started, self.last = previous
            self._stop_timeout()
            self._changed()
            raise

    def _data(self) -> dict[str, Any]:
        return {"player": self.player, "started": self._started, "last": self.last}

    def _content_id(self) -> str | None:
        state = self.player_state
        return state.attributes.get(ATTR_MEDIA_CONTENT_ID) if state else None

    @callback
    def _station_started(self, player: str, station_id: str) -> None:
        """A TuneIn station is about to play on `player`."""
        if player != self.player:
            return
        favorite = self._favorites.get(station_id)
        self._started = {
            "station_id": station_id,
            "name": favorite.name if favorite else None,
            "image": favorite.image if favorite else None,
            "before": self._content_id(),
            "content_id": None,
        }
        self.last = {k: self._started[k] for k in ("station_id", "name", "image")}
        self._track = None
        self._stop_timeout()
        self._cancel_timeout = async_call_later(
            self.hass, START_TIMEOUT, self._timed_out
        )
        if not favorite:
            self.hass.async_create_task(self._async_lookup(station_id))
        self._changed()

    async def _async_lookup(self, station_id: str) -> None:
        """Fill in the name and logo of a station that isn't a favorite."""
        try:
            station = await self._client.describe(station_id)
        except TuneInError:
            return
        for info in (self._started, self.last):
            if info and info["station_id"] == station_id:
                info.update(name=station.name, image=station.image)
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
                        self._refresh_track()
                elif content_id != started["content_id"]:
                    self._started = None  # something else is playing now
        self._changed()

    @callback
    def _timed_out(self, _now: datetime) -> None:
        """No new content ID: the same ID was reused, or playback failed."""
        self._cancel_timeout = None
        if self._started and self._started["content_id"] is None:
            state = self.player_state
            if state and state.state in ACTIVE_STATES and self._content_id():
                self._started["content_id"] = self._content_id()
                self._refresh_track()
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
        """Save soon, then tell listeners."""
        self._store.async_delay_save(self._data, 5)
        for listener in list(self._listeners):
            listener()
