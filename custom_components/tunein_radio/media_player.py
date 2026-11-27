"""A TuneIn media player that plays through the default media player."""

from __future__ import annotations

from typing import Any

from homeassistant.components import media_source
from homeassistant.components.media_player import (
    ATTR_MEDIA_VOLUME_LEVEL,
    ATTR_MEDIA_VOLUME_MUTED,
    DOMAIN as MEDIA_PLAYER_DOMAIN,
    BrowseMedia,
    MediaPlayerEntity,
    MediaPlayerEntityFeature,
    MediaPlayerState,
    MediaType,
)
from homeassistant.const import (
    ATTR_ENTITY_ID,
    ATTR_SUPPORTED_FEATURES,
    SERVICE_MEDIA_PAUSE,
    SERVICE_MEDIA_PLAY,
    SERVICE_MEDIA_STOP,
    SERVICE_VOLUME_DOWN,
    SERVICE_VOLUME_MUTE,
    SERVICE_VOLUME_SET,
    SERVICE_VOLUME_UP,
    STATE_UNAVAILABLE,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import TuneInConfigEntry
from .const import ATTR_STATION_ID, DOMAIN, PANEL_ICON, media_source_id
from .favorites import station_labels

# Controls offered only when the default player has them.
PASSTHROUGH = (
    MediaPlayerEntityFeature.PAUSE
    | MediaPlayerEntityFeature.STOP
    | MediaPlayerEntityFeature.VOLUME_SET
    | MediaPlayerEntityFeature.VOLUME_MUTE
    | MediaPlayerEntityFeature.VOLUME_STEP
)
ALWAYS = (
    MediaPlayerEntityFeature.PLAY
    | MediaPlayerEntityFeature.PLAY_MEDIA
    | MediaPlayerEntityFeature.SELECT_SOURCE
    | MediaPlayerEntityFeature.BROWSE_MEDIA
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: TuneInConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Add the TuneIn player."""
    async_add_entities([TuneInPlayer(entry)])


class TuneInPlayer(MediaPlayerEntity):
    """Plays TuneIn stations through the default media player."""

    _attr_name = "TuneIn"
    _attr_icon = PANEL_ICON
    _attr_should_poll = False

    def __init__(self, entry: TuneInConfigEntry) -> None:
        """Initialize."""
        self._favorites = entry.runtime_data.favorites
        self._tracker = entry.runtime_data.tracker
        self._attr_unique_id = f"{entry.entry_id}_player"

    async def async_added_to_hass(self) -> None:
        """Follow the tracker."""
        self.async_on_remove(
            self._tracker.async_add_listener(self.async_write_ha_state)
        )

    def _output(self, attribute: str) -> Any:
        """An attribute of the default player."""
        state = self._tracker.player_state
        return state.attributes.get(attribute) if state else None

    @property
    def available(self) -> bool:
        """Only usable while the default player is."""
        state = self._tracker.player_state
        return state is not None and state.state != STATE_UNAVAILABLE

    @property
    def state(self) -> MediaPlayerState:
        """The default player's state, while it is on a TuneIn station."""
        if not self._tracker.playing:
            return MediaPlayerState.IDLE
        if self._tracker.starting:
            return MediaPlayerState.BUFFERING
        output = self._tracker.player_state.state
        if output == MediaPlayerState.PAUSED:
            return MediaPlayerState.PAUSED
        if output == MediaPlayerState.BUFFERING:
            return MediaPlayerState.BUFFERING
        return MediaPlayerState.PLAYING

    @property
    def supported_features(self) -> MediaPlayerEntityFeature:
        """Add whichever controls the default player has."""
        output = MediaPlayerEntityFeature(self._output(ATTR_SUPPORTED_FEATURES) or 0)
        return ALWAYS | (output & PASSTHROUGH)

    @property
    def volume_level(self) -> float | None:
        """Volume of the default player."""
        return self._output(ATTR_MEDIA_VOLUME_LEVEL)

    @property
    def is_volume_muted(self) -> bool | None:
        """Mute state of the default player."""
        return self._output(ATTR_MEDIA_VOLUME_MUTED)

    @property
    def source_list(self) -> list[str]:
        """Favorite stations."""
        return list(station_labels(self._favorites.stations))

    @property
    def source(self) -> str | None:
        """The favorite playing now."""
        if not (playing := self._tracker.playing):
            return None
        labels = station_labels(self._favorites.stations)
        return next(
            (label for label, sid in labels.items() if sid == playing["station_id"]),
            None,
        )

    @property
    def media_content_type(self) -> MediaType | None:
        """Radio is music."""
        return MediaType.MUSIC if self._tracker.playing else None

    @property
    def media_content_id(self) -> str | None:
        """Media-source URI of the station."""
        playing = self._tracker.playing
        return media_source_id(playing["station_id"]) if playing else None

    @property
    def media_title(self) -> str | None:
        """Station name, with the song on air when known.

        Gives "Station · Song - Artist".
        """
        if not (station := self._station_name):
            return None
        track = self._tracker.track
        song = " - ".join(p for p in (track.song, track.artist) if p)
        return " · ".join(p for p in (station, song) if p)

    @property
    def _station_name(self) -> str | None:
        if not (playing := self._tracker.playing):
            return None
        return playing["name"] or playing["station_id"]

    @property
    def media_artist(self) -> str | None:
        """Artist on air. The default player's own track info is not used."""
        return self._tracker.track.artist

    @property
    def media_album_name(self) -> str | None:
        """Album of the song on air."""
        return self._tracker.track.album

    @property
    def media_image_url(self) -> str | None:
        """Artwork of the song on air, otherwise the station logo."""
        if not (playing := self._tracker.playing):
            return None
        return self._tracker.track.art or playing.get("image") or None

    @property
    def extra_state_attributes(self) -> dict[str, str | None]:
        """The station, show and song playing now, and the player used."""
        playing = self._tracker.playing
        return {
            ATTR_STATION_ID: playing["station_id"] if playing else None,
            "station_name": self._station_name,
            "player": self._tracker.player,
            "media_show": self._tracker.track.show,
            "media_song_name": self._tracker.track.song,
            "media_album_art": self._tracker.track.art,
        }

    async def _async_forward(self, service: str, **data: Any) -> None:
        """Call a media_player action on the default player."""
        await self.hass.services.async_call(
            MEDIA_PLAYER_DOMAIN,
            service,
            {ATTR_ENTITY_ID: self._tracker.player, **data},
            blocking=True,
            context=self._context,
        )

    async def async_media_play(self) -> None:
        """Resume if paused, otherwise start the last station again."""
        if self.state == MediaPlayerState.PAUSED:
            await self._async_forward(SERVICE_MEDIA_PLAY)
            return
        if not (last := self._tracker.last):
            raise HomeAssistantError("No station played yet; choose one first")
        await self._tracker.async_play(last["station_id"], self._context)

    async def async_media_pause(self) -> None:
        """Pause the default player."""
        await self._async_forward(SERVICE_MEDIA_PAUSE)

    async def async_media_stop(self) -> None:
        """Stop the default player."""
        await self._async_forward(SERVICE_MEDIA_STOP)

    async def async_set_volume_level(self, volume: float) -> None:
        """Set the volume."""
        await self._async_forward(
            SERVICE_VOLUME_SET, **{ATTR_MEDIA_VOLUME_LEVEL: volume}
        )

    async def async_mute_volume(self, mute: bool) -> None:
        """Mute or unmute."""
        await self._async_forward(
            SERVICE_VOLUME_MUTE, **{ATTR_MEDIA_VOLUME_MUTED: mute}
        )

    async def async_volume_up(self) -> None:
        """Turn the volume up."""
        await self._async_forward(SERVICE_VOLUME_UP)

    async def async_volume_down(self) -> None:
        """Turn the volume down."""
        await self._async_forward(SERVICE_VOLUME_DOWN)

    async def async_select_source(self, source: str) -> None:
        """Play a favorite."""
        labels = station_labels(self._favorites.stations)
        if source not in labels:
            raise HomeAssistantError(f"Not a TuneIn favorite: {source}")
        await self._tracker.async_play(labels[source], self._context)

    async def async_play_media(
        self, media_type: str, media_id: str, **kwargs: Any
    ) -> None:
        """Play a TuneIn station, for example one picked in the media browser."""
        prefix = media_source_id("")
        if not media_id.startswith(prefix):
            raise HomeAssistantError("The TuneIn player only plays TuneIn stations")
        await self._tracker.async_play(media_id.removeprefix(prefix), self._context)

    async def async_browse_media(
        self,
        media_content_type: MediaType | str | None = None,
        media_content_id: str | None = None,
    ) -> BrowseMedia:
        """Browse TuneIn."""
        return await media_source.async_browse_media(
            self.hass, media_content_id or f"media-source://{DOMAIN}"
        )
