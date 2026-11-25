"""Select entity listing the favorite stations."""

from __future__ import annotations

from collections import Counter

from homeassistant.components.select import SelectEntity
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.restore_state import RestoreEntity

from . import TuneInConfigEntry
from .api import Station
from .const import ATTR_STATION_ID, PANEL_ICON
from .favorites import Favorites


async def async_setup_entry(
    hass: HomeAssistant,
    entry: TuneInConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Add the favorites select."""
    async_add_entities(
        [FavoritesSelect(entry.runtime_data.favorites, f"{entry.entry_id}_favorites")]
    )


def _labels(stations: list[Station]) -> dict[str, str]:
    """Map option label -> station ID, adding the ID where names collide."""
    names = Counter(s.name for s in stations)
    return {
        (s.name if names[s.name] == 1 else f"{s.name} [{s.id}]"): s.id
        for s in stations
    }


class FavoritesSelect(SelectEntity, RestoreEntity):
    """The favorite stations; the choice is remembered by station ID."""

    _attr_name = "TuneIn favorites"
    _attr_icon = PANEL_ICON
    _attr_should_poll = False

    def __init__(self, favorites: Favorites, unique_id: str) -> None:
        """Initialize."""
        self._favorites = favorites
        self._attr_unique_id = unique_id
        self._station_id: str | None = None
        self._ids: dict[str, str] = {}
        self._refresh()

    async def async_added_to_hass(self) -> None:
        """Restore the last choice and follow changes to the favorites."""
        await super().async_added_to_hass()
        if last := await self.async_get_last_state():
            self._station_id = last.attributes.get(ATTR_STATION_ID)
        self._refresh()
        self.async_on_remove(self._favorites.async_add_listener(self._changed))

    @callback
    def _changed(self) -> None:
        self._refresh()
        self.async_write_ha_state()

    def _refresh(self) -> None:
        """Rebuild the options, dropping the choice if it's no longer a favorite."""
        self._ids = _labels(self._favorites.stations)
        self._attr_options = list(self._ids)
        self._attr_current_option = next(
            (label for label, sid in self._ids.items() if sid == self._station_id), None
        )
        if self._attr_current_option is None:
            self._station_id = None

    @property
    def extra_state_attributes(self) -> dict[str, str | None]:
        """Expose the chosen station's ID for use with tunein_radio.play."""
        return {ATTR_STATION_ID: self._station_id}

    async def async_select_option(self, option: str) -> None:
        """Choose a favorite (does not start playback)."""
        self._station_id = self._ids[option]
        self._attr_current_option = option
        self.async_write_ha_state()
