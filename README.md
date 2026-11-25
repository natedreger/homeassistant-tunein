# TuneIn Radio for Home Assistant

A Home Assistant custom integration that searches TuneIn, keeps a favorites list, and hands station stream URLs to your media players.

## Setup

Add **TuneIn Radio** under **Settings → Devices & services** and choose a default media player. Any media player that can play media is listed. To change it later, use **Configure** on the integration.

The TuneIn panel selects the default player until you pick another one there.

## Favorites entity

`select.tunein_favorites` lists your favorites. Choosing one plays it on one speaker: the default media player.

It also shows which station that speaker is playing, including one started from the TuneIn panel, the media browser or `tunein_radio.play`. It is blank (a single space) when the speaker is stopped, is playing something else, or is playing a station that isn't a favorite. Choosing the blank entry does nothing. The `station_id` and `station_name` attributes are filled in for non-favorites too.

Stations started outside Home Assistant, for example from the player's own app or web page, aren't recognized.

## Install

In HACS, add this repository as a custom repository (category **Integration**), install **TuneIn Radio**, and restart Home Assistant. Or copy `custom_components/tunein_radio` into your HA `config/custom_components/`.

Requires Home Assistant 2026.2 or newer.

## Disclaimer

This is an unofficial integration. It is not affiliated with, endorsed by or sponsored by TuneIn. The TuneIn name and logo are trademarks of TuneIn, used here only to identify the service.
