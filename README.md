# TuneIn Radio for Home Assistant

A Home Assistant custom integration that searches TuneIn, keeps a favorites list, and hands station stream URLs to your media players.

## Setup

Add **TuneIn Radio** under **Settings → Devices & services** and choose a default media player. Any media player that can play media is listed. To change it later, use **Configure → Default media player** on the integration.

The TuneIn panel selects the default player until you pick another one there.

## TuneIn media player

`media_player.tunein` plays through the default media player, so dashboards and automations can control the radio without naming the speaker.

- **Source** lists your favorites. You can also pick any station in its media browser.
- **Play** resumes a paused station, or starts the last station again.
- **Pause, stop, volume and mute** are passed to the default player, where it supports them.
- It shows the station name and logo, and what is on air, checked every 30 seconds. See [Show and song](#show-and-song).

It is a remote control for the default player, not a separate audio stream: it shows as idle when that player is playing something else.

### Note

This has only been proven to work with OwnTone (forked-daapd)

## Show and song

While a station plays on the default player, `media_player.tunein` has:

| Attribute | Source |
|---|---|
| `media_show` | TuneIn, for stations it lists a show for |
| `media_artist` | The station's song API |
| `media_songname` | The station's song API |

The title (`media_title`) is the station, song and artist ("KCRW · Largate - Kali Uchis"). The station name alone is in the `station_name` attribute.

Track information reported by the default player is not used.

To set a station's song API, use **Configure → Station song API** on the integration. Pick a favorite or type a station ID, and enter the address. Leave the address blank to remove it. No addresses are built in, so a station has no artist or song until you set one.

The address must return JSON containing an object with both an artist (`artist`, `artist_name` or `artistName`) and a title (`title`, `song`, `track`, `song_title`, `songTitle` or `trackName`). It can be nested. In a list, the newest entry must come first. If the object has a `datetime` with a time zone that is more than 15 minutes old, it is ignored.

## Favorites entity

`select.tunein_favorites` lists your favorites. Choosing one plays it on one speaker: the default media player.

It also shows which station that speaker is playing, including one started from the TuneIn panel, the media browser or `tunein_radio.play`. It is blank (a single space) when the speaker is stopped, is playing something else, or is playing a station that isn't a favorite. Choosing the blank entry does nothing. The `station_id` and `station_name` attributes are filled in for non-favorites too.

Stations started outside Home Assistant, for example from the player's own app or web page, aren't recognized.

## Install

In Marketplace, add this repository as a custom repository (category **Integration**), and restart Home Assistant. Or copy `custom_components/tunein_radio` into your HA `config/custom_components/`.

Requires Home Assistant 2026.2 or newer.

## Find it helpful??

<a href="https://www.buymeacoffee.com/dregsoft"><img src="https://cdn.buymeacoffee.com/buttons/v2/default-yellow.png" alt="Buy me a coffee" height="50"></a>

## Disclaimer

This is an unofficial integration. It is not affiliated with, endorsed by or sponsored by TuneIn. The TuneIn name and logo are trademarks of TuneIn, used here only to identify the service.

