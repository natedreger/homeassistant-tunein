// TuneIn card: Home Assistant's media control card, with more attributes below it.
const LABELS = {
  media_show: "Show",
  media_songname: "Song",
  media_artist: "Artist",
  station_name: "Station",
  station_id: "Station ID",
  player: "Speaker",
};
const DEFAULT_ATTRIBUTES = ["media_show", "media_songname"];

const label = (name) =>
  LABELS[name] || name.replace(/_/g, " ").replace(/^./, (c) => c.toUpperCase());

class TuneInCard extends HTMLElement {
  static getStubConfig(hass) {
    const entity = Object.keys(hass.states).find(
      (id) => id.startsWith("media_player.") && "station_name" in hass.states[id].attributes
    );
    return { entity: entity || "media_player.tunein" };
  }

  static getConfigForm() {
    return {
      schema: [
        { name: "entity", required: true, selector: { entity: { domain: "media_player" } } },
        {
          name: "attributes",
          selector: {
            select: {
              multiple: true,
              custom_value: true,
              reorder: true,
              options: Object.entries(LABELS).map(([value, text]) => ({ value, label: text })),
            },
          },
        },
      ],
    };
  }

  setConfig(config) {
    if (!config.entity?.startsWith("media_player.")) throw new Error("Choose a media player entity");
    this._config = { attributes: DEFAULT_ATTRIBUTES, ...config };
    if (!this.shadowRoot) this.attachShadow({ mode: "open" });
    this.shadowRoot.innerHTML = `<style>${STYLE}</style><ha-card><div id="player"></div><dl></dl></ha-card>`;
    this._player = null;
    this._createPlayer();
  }

  async _createPlayer() {
    const config = this._config;
    const helpers = await window.loadCardHelpers();
    if (config !== this._config) return; // reconfigured while loading
    this._player = helpers.createCardElement({ type: "media-control", entity: config.entity });
    this.shadowRoot.querySelector("#player").replaceChildren(this._player);
    this._update();
  }

  set hass(hass) {
    this._hass = hass;
    this._update();
  }

  getCardSize() {
    return 3 + Math.ceil((this._config?.attributes.length || 0) / 2);
  }

  _update() {
    if (!this._hass || !this._config) return;
    const id = this._config.entity;
    const state = this._hass.states[id];
    const attributes = state?.attributes || {};

    if (this._player) this._player.hass = this._playerHass(state);

    const rows = this._config.attributes
      .map((name) => [name, attributes[name]])
      .filter(([, value]) => value !== undefined && value !== null && value !== "");
    const list = this.shadowRoot.querySelector("dl");
    list.replaceChildren(
      ...rows.flatMap(([name, value]) => {
        const term = document.createElement("dt");
        term.textContent = label(name);
        const text = document.createElement("dd");
        text.textContent = Array.isArray(value) ? value.join(", ") : String(value);
        return [term, text];
      })
    );
    list.hidden = !rows.length;
  }

  // The entity's title also holds the song and artist, for the stock cards.
  // Here those have their own places, so the title is just the station.
  _playerHass(state) {
    const station = state?.attributes.station_name;
    if (!station) return this._hass;
    const id = this._config.entity;
    return {
      ...this._hass,
      states: {
        ...this._hass.states,
        [id]: { ...state, attributes: { ...state.attributes, media_title: station } },
      },
    };
  }
}

const STYLE = `
  ha-card { overflow: hidden; }
  /* The media control card sits inside this one, so it has no frame of its own. */
  #player { --ha-card-border-width: 0; --ha-card-box-shadow: none; --ha-card-border-radius: 0; }
  dl { display: grid; grid-template-columns: auto 1fr; gap: 4px 16px; margin: 0; padding: 12px 16px 16px; }
  dl[hidden] { display: none; }
  dt { color: var(--secondary-text-color); }
  dd { margin: 0; color: var(--primary-text-color); overflow-wrap: anywhere; }
`;

if (!customElements.get("tunein-card")) {
  customElements.define("tunein-card", TuneInCard);
  window.customCards = window.customCards || [];
  window.customCards.push({
    type: "tunein-card",
    name: "TuneIn card",
    description: "Media control card with the show, song and other attributes.",
    preview: true,
  });
}
