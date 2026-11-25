# TuneIn Radio for Home Assistant

A Home Assistant custom integration that searches TuneIn (RadioTime OPML API, plus a tunein.com search fallback), keeps a favorites list, and hands station stream URLs to a media player such as OwnTone.

## Favorites entity

`select.tunein_favorites` lists your favorites and updates when you add or remove one. Choosing a station only selects it. To play it, pass its `station_id` attribute to `tunein_radio.play`, for example from an automation (replace `media_player.owntone` with your player):

```yaml
triggers:
  - trigger: state
    entity_id: select.tunein_favorites
    not_to:
      - unknown
      - unavailable
conditions:
  - condition: template
    value_template: >
      {{ trigger.from_state is not none
         and trigger.from_state.state != 'unavailable'
         and trigger.from_state.state != trigger.to_state.state }}
actions:
  - action: tunein_radio.play
    target:
      entity_id: media_player.owntone
    data:
      station_id: "{{ trigger.to_state.attributes.station_id }}"
```

## Install

In HACS, add this repository as a custom repository (category **Integration**), install **TuneIn Radio**, and restart Home Assistant. Or copy `custom_components/tunein_radio` into your HA `config/custom_components/`.

Requires Home Assistant 2026.2 or newer.
