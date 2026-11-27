// TuneIn card: Home Assistant's media control card, with more attributes below it.
const LABELS = {
  media_show: "Show",
  media_song_name: "Song",
  media_artist: "Artist",
  media_album_name: "Album",
  station_name: "Station",
  station_id: "Station ID",
  player: "Speaker",
};
const DEFAULT_ATTRIBUTES = ["media_show", "media_song_name"];
// MediaPlayerEntityFeature bits.
const VOLUME_SET = 4;
const VOLUME_MUTE = 8;
const SELECT_SOURCE = 2048;

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
          name: "title_source",
          default: "station_name",
          selector: {
            select: {
              mode: "dropdown",
              options: [
                { value: "station_name", label: "Station name" },
                { value: "media_title", label: "Media title (station, song and artist)" },
              ],
            },
          },
        },
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
        { name: "show_labels", default: true, selector: { boolean: {} } },
        { name: "show_volume", default: true, selector: { boolean: {} } },
        { name: "show_favorites", default: true, selector: { boolean: {} } },
      ],
      computeLabel: ({ name }) =>
        ({
          entity: "Entity",
          title_source: "Card title",
          attributes: "Attributes",
          show_labels: "Show labels",
          show_volume: "Show volume slider",
          show_favorites: "Show favorites button",
        })[name],
    };
  }

  setConfig(config) {
    if (!config.entity?.startsWith("media_player.")) throw new Error("Choose a media player entity");
    this._config = { attributes: DEFAULT_ATTRIBUTES, show_labels: true, show_volume: true, show_favorites: true, title_source: "station_name", ...config };
    if (!this.shadowRoot) this.attachShadow({ mode: "open" });
    this.shadowRoot.innerHTML = `<style>${STYLE}</style><ha-card><div id="player"></div>
      <div id="volume">
        <button id="mute"><ha-icon></ha-icon></button>
        <input type="range" min="0" max="100" step="1" aria-label="Volume">
      </div>
      <dl></dl></ha-card>`;
    this._list = this.shadowRoot.querySelector("dl"); // it moves, so keep hold of it
    this._listenToVolume();
    this._createFavorites();
    this._player = null;
    this._extended = false;
    this._heading = null;
    this._createPlayer();
  }

  async _createPlayer() {
    const config = this._config;
    const helpers = await window.loadCardHelpers();
    if (config !== this._config) return; // reconfigured while loading
    this._player = helpers.createCardElement({ type: "media-control", entity: config.entity });
    this.shadowRoot.querySelector("#player").replaceChildren(this._player);
    this._update();
    this._extendArtwork(this._player, config);
  }

  // Fits our parts into the media control card. Its artwork runs on behind the
  // volume slider (the card is made taller by the slider's height, and the slider
  // is laid over that space), and the attributes can sit under its title. This
  // reaches inside Home Assistant's card, so if that ever stops working they
  // simply stay below it.
  async _extendArtwork(player, config) {
    await customElements.whenDefined("hui-media-control-card");
    await player.updateComplete;
    if (config !== this._config || !player.shadowRoot) return;
    const style = document.createElement("style");
    style.textContent = INSIDE_STYLE;
    player.shadowRoot.append(style);
    this._extended = true;
    this._update();
  }

  // Puts the station name and the attributes into the media control card's title
  // block, or the attributes back below that card while it has none.
  async _placeList() {
    const player = this._player;
    const list = this._list;
    if (!this._extended) return;
    await player.updateComplete; // let it draw its title first
    if (list !== this._list) return; // reconfigured meanwhile
    const home = this.shadowRoot.querySelector("ha-card");
    const info = player.shadowRoot.querySelector(".media-info");
    const place = info || home;
    if (list.parentNode !== place) place.append(list);
    this._placeHeading(info);
    this._placeFavorites(player.shadowRoot);
  }

  // The station name, in place of the media control card's own title. Written
  // here as well as passed to that card, which doesn't always take it from us.
  _placeHeading(info) {
    const station = this._hass.states[this._config.entity]?.attributes.station_name;
    if (!info || !station || this._config.title_source === "media_title") {
      this._heading?.remove(); // the card's own title shows again
      return;
    }
    if (!this._heading) {
      this._heading = document.createElement("div");
      this._heading.className = "heading";
    }
    this._heading.textContent = station;
    if (this._heading.parentNode !== info) info.prepend(this._heading);
  }

  // A star button that drops down the player's sources: for the TuneIn player,
  // the favorites. An invisible native list covers the star, so the card's edges
  // can't cut the open list off.
  _createFavorites() {
    this._favorites = document.createElement("label");
    this._favorites.className = "favorites";
    this._favorites.title = "Favorites";
    const star = document.createElement("ha-icon");
    star.setAttribute("icon", "mdi:star");
    const list = document.createElement("select");
    list.setAttribute("aria-label", "Favorites");
    list.addEventListener("change", () => {
      if (list.value) this._call("select_source", { source: list.value });
    });
    this._favorites.append(star, list);
    this._sourceList = list;
    this._sources = null;
    this.shadowRoot.querySelector("ha-card").append(this._favorites);
  }

  _updateFavorites(state) {
    const sources = state?.attributes.source_list || [];
    this._favorites.hidden =
      this._config.show_favorites === false ||
      !sources.length ||
      state.state === "unavailable" ||
      !(state.attributes.supported_features & SELECT_SOURCE);
    if (this._favorites.hidden) return;

    // Only rebuilt when the favorites change; rebuilding closes an open list.
    const key = JSON.stringify(sources);
    if (key !== this._sources) {
      this._sources = key;
      this._sourceList.replaceChildren(
        ...["", ...sources].map((source) => {
          const option = document.createElement("option");
          option.value = source;
          option.textContent = source || "Favorites";
          option.disabled = !source;
          return option;
        })
      );
    }
    this._sourceList.value = sources.includes(state.attributes.source) ? state.attributes.source : "";
  }

  // Next to the media control card's browse button; failing that, with its
  // other controls, or at the bottom of this card.
  _placeFavorites(root) {
    const button = this._favorites;
    const browse = root.querySelector(".browse-media");
    if (browse) {
      // That button is pinned to the card's edge; sit just inside it.
      const pinned = window.getComputedStyle?.(browse).position === "absolute";
      button.className = pinned ? "favorites pinned" : "favorites";
      if (browse.nextSibling !== button) browse.after(button);
      return;
    }
    button.className = "favorites";
    const place = root.querySelector(".controls") || this.shadowRoot.querySelector("ha-card");
    if (button.parentNode !== place) place.append(button);
  }

  _listenToVolume() {
    const slider = this.shadowRoot.querySelector("#volume input");
    this._dragging = false;
    // Updates from Home Assistant must not move the slider while it is dragged.
    slider.addEventListener("input", () => (this._dragging = true));
    slider.addEventListener("blur", () => (this._dragging = false));
    slider.addEventListener("change", () => {
      this._dragging = false;
      this._call("volume_set", { volume_level: slider.value / 100 });
    });
    this.shadowRoot
      .querySelector("#mute")
      .addEventListener("click", () => this._call("volume_mute", { is_volume_muted: !this._muted }));
  }

  _call(action, data) {
    this._hass.callService("media_player", action, { entity_id: this._config.entity, ...data });
  }

  // The slider row, shown when the speaker lets its volume be set. Returns
  // whether it is shown.
  _updateVolume(state) {
    const find = (selector) => this.shadowRoot.querySelector(selector);
    const features = state?.attributes.supported_features || 0;
    const level = state?.attributes.volume_level;
    const shown =
      this._config.show_volume !== false &&
      state?.state !== "unavailable" &&
      !!(features & VOLUME_SET) &&
      typeof level === "number";
    find("#volume").hidden = !shown;
    if (!shown) return false;

    if (!this._dragging) find("#volume input").value = Math.round(level * 100);
    this._muted = !!state.attributes.is_volume_muted;
    const button = find("#mute");
    button.disabled = !(features & VOLUME_MUTE);
    button.title = this._muted ? "Unmute" : "Mute";
    button.setAttribute("aria-label", button.title);
    find("#mute ha-icon").setAttribute("icon", this._muted ? "mdi:volume-off" : "mdi:volume-high");
    return true;
  }

  set hass(hass) {
    this._hass = hass;
    this._update();
  }

  getCardSize() {
    return 3 + (this._config?.show_volume === false ? 0 : 1) + Math.ceil((this._config?.attributes.length || 0) / 2);
  }

  _update() {
    if (!this._hass || !this._config) return;
    const id = this._config.entity;
    const state = this._hass.states[id];
    const attributes = state?.attributes || {};

    const slider = this._updateVolume(state);
    this._updateFavorites(state);
    const over = slider && this._extended;
    this.shadowRoot.querySelector("ha-card").className = !over
      ? ""
      : attributes.entity_picture
        ? "over picture"
        : "over";
    if (this._player) this._player.hass = this._playerHass(state);

    const rows = this._config.attributes
      .map((name) => [name, attributes[name]])
      .filter(([, value]) => value !== undefined && value !== null && value !== "");
    const list = this._list;
    const labels = this._config.show_labels !== false;
    list.className = labels ? "" : "plain";
    list.replaceChildren(
      ...rows.flatMap(([name, value]) => {
        const term = document.createElement("dt");
        term.textContent = label(name);
        const text = document.createElement("dd");
        text.textContent = Array.isArray(value) ? value.join(", ") : String(value);
        term.className = text.className = name;
        return labels ? [term, text] : [text];
      })
    );
    list.hidden = !rows.length;
    this._placeList();
  }

  // The entity's title also holds the song and artist, for the stock cards.
  // Here those can have their own places, so unless the media title is chosen,
  // the title is just the station, with no artist line under it.
  _playerHass(state) {
    const station = state?.attributes.station_name;
    if (!station || this._config.title_source === "media_title") return this._hass;
    const id = this._config.entity;
    return {
      ...this._hass,
      states: {
        ...this._hass.states,
        [id]: { ...state, attributes: { ...state.attributes, media_title: station, media_artist: undefined } },
      },
    };
  }
}

const LIST_STYLE = `
  dl { display: grid; grid-template-columns: auto minmax(0, 1fr); gap: 4px 16px; align-items: baseline; }
  dl[hidden] { display: none; }
  dl.plain { grid-template-columns: minmax(0, 1fr); }
  /* Stepping down from the station name, which the media control card shows at 1.2em. */
  .media_show { font-size: 1.1em; }
  .media_song_name { font-size: 1em; }
  .media_artist, .media_album_name { font-size: 0.85em; }
`;

const FAVORITES_STYLE = `
  .favorites { position: relative; display: inline-flex; width: 40px; height: 40px; align-items: center; justify-content: center; vertical-align: middle; cursor: pointer; }
  .favorites[hidden] { display: none; }
  .favorites.pinned { position: absolute; right: 52px; }
  .favorites select { position: absolute; inset: 0; width: 100%; opacity: 0; font: inherit; cursor: pointer; }
  .favorites:focus-within { outline: 2px solid currentColor; border-radius: 50%; }
  /* The open list is drawn on its own background, so it needs its own colours. */
  .favorites option { color: #212121; background: #fff; }
`;

// Added inside the media control card, where it takes that card's text colour.
const INSIDE_STYLE = `
  ha-card { padding-bottom: var(--tunein-below, 0px) !important; }
  .heading { font-size: 1.2em; margin: 0 0 4px; overflow: hidden; white-space: nowrap; text-overflow: ellipsis; }
  /* Hides the card's own title while ours is there. */
  .heading ~ :not(dl) { display: none !important; }
  ${FAVORITES_STYLE}
  ${LIST_STYLE}
  dl { margin: 4px 0 0; gap: 2px 8px; font-weight: normal; }
  dt { opacity: 0.75; }
  dd { margin: 0; overflow: hidden; white-space: nowrap; text-overflow: ellipsis; }
`;

const STYLE = `
  ha-card { overflow: hidden; }
  /* The media control card sits inside this one, so it has no frame of its own. */
  #player { --ha-card-border-width: 0; --ha-card-box-shadow: none; --ha-card-border-radius: 0; }
  ${FAVORITES_STYLE}
  ${LIST_STYLE}
  dl { margin: 0; padding: 12px 16px 16px; }
  #volume { display: flex; align-items: center; gap: 8px; padding: 8px 16px 0; }
  #volume[hidden] { display: none; }
  #volume button { display: flex; background: none; border: 0; padding: 4px; color: var(--primary-text-color); cursor: pointer; }
  #volume button:disabled { cursor: default; }
  #volume input { flex: 1; min-width: 0; accent-color: var(--primary-color); }
  /* The slider laid over the bottom of the media control card; the card grows by
     the same 40px, so the overall size doesn't change. */
  .over #player { --tunein-below: 40px; }
  .over #volume { position: relative; z-index: 1; height: 32px; margin: -40px 8px 8px; padding: 0 8px; border-radius: 16px; }
  /* A dark backing keeps it readable on any artwork. */
  .over.picture #volume { background: rgba(0, 0, 0, 0.45); --primary-text-color: #fff; --primary-color: #fff; }
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
