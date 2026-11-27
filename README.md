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

| Attribute | What it is |
|---|---|
| `media_show` | Current show |
| `media_artist` | Artist on air |
| `media_songname` | Song on air |

These come from TuneIn, which only has them for some stations. You can override it with a station's own API (see below).

The title (`media_title`) is the station, song and artist ("KCRW · Largate - Kali Uchis"). The station name alone is in the `station_name` attribute.

Track information reported by the default player is not used.

To set a station's own API, use **Configure → Station API** on the integration. Pick a favorite or type a station ID, and enter the address. Leave the address blank to remove it. No addresses are built in.

What the address provides takes precedence over TuneIn; TuneIn fills in the rest.

Some APIs need data sent with a `POST` request. Enter that JSON as the **Request body**; leave it blank otherwise. For example, 88Nine Radio Milwaukee (`s24211`):

- Address: `https://precise-fish-444.convex.cloud/api/query`
- Request body: `{"path":"plays:currentByStation","args":{"stationSlug":"88nine"},"format":"json"}`

The address must return JSON. Fields can be nested, and in a list the newest entry must come first.

- **Show:** `program_title`, `programName`, `program_name`, `show_name`, `showName` or `show`.
- **Song:** an object with both an artist (`artist`, `artist_name` or `artistName`) and a title (`title`, `song`, `track`, `song_title`, `songTitle` or `trackName`).

Anything under `next`, `upNext`, `upcoming` or `playing_next` is skipped. The artist can be a list of names. An object is ignored if it started more than 15 minutes ago, going by `datetime` (with a time zone) or `playedAt` (Unix time).

## Dashboard card

**TuneIn card** is Home Assistant's media control card with more attributes listed below it. Add it from the dashboard's card picker, or in YAML:

```yaml
type: custom:tunein-card
entity: media_player.tunein
attributes:
  - media_show
  - media_songname
```

`attributes` takes any attributes of the media player, in the order to show them. Without it, the card shows the show and song. Empty ones are hidden. The card's title is the station name.

The integration loads the card itself, so there is no dashboard resource to add. Reload the browser after installing or updating.

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

