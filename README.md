# TuneIn Radio for Home Assistant

A Home Assistant custom integration that searches TuneIn, keeps a favorites list, and hands station stream URLs to a media player such as OwnTone (forked-daaped).

## Favorites entity

`select.tunein_favorites` lists your favorites. Choosing one plays it on one speaker: by default your OwnTone server, or the player you pick in the integration's options (**Settings → Devices & services → TuneIn Radio → Configure**).

It also shows which station that speaker is playing, including one started from the TuneIn panel, the media browser or `tunein_radio.play`. It is `unknown` when the speaker is stopped, is playing something else, or is playing a station that isn't a favorite. The `station_id` and `station_name` attributes are filled in for non-favorites too.

Stations started outside Home Assistant, for example from OwnTone's own web page, aren't recognized.

## Install

In HACS, add this repository as a custom repository (category **Integration**), install **TuneIn Radio**, and restart Home Assistant. Or copy `custom_components/tunein_radio` into your HA `config/custom_components/`.

Requires Home Assistant 2026.2 or newer.

## Disclaimer

This is an unofficial integration. It is not affiliated with, endorsed by or sponsored by TuneIn. The TuneIn name and logo are trademarks of TuneIn, used here only to identify the service.
