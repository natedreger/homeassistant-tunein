"""Select entity that plays favorite stations and shows which one is playing."""

from __future__ import annotations

from homeassistant.components.select import SelectEntity
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import TuneInConfigEntry
from .const import ATTR_STATION_ID, PANEL_ICON
from .favorites import station_labels

# Shown when no favorite is playing; without it Home Assistant says "Unknown".
BLANK = " "


async def async_setup_entry(
    hass: HomeAssistant,
    entry: TuneInConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Add the favorites select."""
    async_add_entities([FavoritesSelect(entry)])


class FavoritesSelect(SelectEntity):
    """Favorite stations; the current option is what the speaker is playing."""

    _attr_name = "TuneIn favorites"
    _attr_icon = PANEL_ICON
    _attr_should_poll = False

    def __init__(self, entry: TuneInConfigEntry) -> None:
        """Initialize."""
        self._favorites = entry.runtime_data.favorites
        self._tracker = entry.runtime_data.tracker
        self._attr_unique_id = f"{entry.entry_id}_favorites"
        self._ids: dict[str, str] = {}
        self._attr_options = []

    async def async_added_to_hass(self) -> None:
        """Follow the tracker."""
        self.async_on_remove(self._tracker.async_add_listener(self._changed))
        self._refresh()

    @callback
    def _changed(self) -> None:
        self._refresh()
        self.async_write_ha_state()

    def _refresh(self) -> None:
        self._ids = station_labels(self._favorites.stations)
        self._attr_options = [BLANK, *self._ids]
        playing = self._tracker.playing
        station_id = playing["station_id"] if playing else None
        self._attr_current_option = next(
            (label for label, sid in self._ids.items() if sid == station_id), BLANK
        )

    @property
    def extra_state_attributes(self) -> dict[str, str | None]:
        """The station playing now, favorite or not, and the speaker used."""
        playing = self._tracker.playing
        return {
            ATTR_STATION_ID: playing["station_id"] if playing else None,
            "station_name": playing["name"] if playing else None,
            "player": self._tracker.player,
        }

    async def async_select_option(self, option: str) -> None:
        """Play a favorite on the speaker."""
        if option == BLANK:  # nothing to play; show the real state again
            self._changed()
            return
        await self._tracker.async_play(self._ids[option], self._context)
