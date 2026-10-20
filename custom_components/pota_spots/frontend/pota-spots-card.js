// POTA Spots card – lists the spots from a pota_spots "Active spots" sensor.
// Shipped with the pota_spots integration and loaded automatically.

const BAND_COLORS = {
  "160m": "#8e5ea2",
  "80m": "#5b6abf",
  "60m": "#3e95cd",
  "40m": "#1f9e89",
  "30m": "#43a047",
  "20m": "#c0a000",
  "17m": "#e08a00",
  "15m": "#e8590c",
  "12m": "#d6336c",
  "10m": "#c2255c",
  "6m": "#ae3ec9",
  "2m": "#7048e8",
  "70cm": "#495057",
};

const escapeHtml = (value) =>
  String(value ?? "").replace(
    /[&<>"']/g,
    (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]
  );

const formatAge = (spotTime, now) => {
  const t = Date.parse(spotTime);
  if (Number.isNaN(t)) return "";
  const minutes = Math.max(0, Math.floor((now - t) / 60000));
  if (minutes < 1) return "now";
  if (minutes < 60) return `${minutes} min`;
  return `${Math.floor(minutes / 60)} h ${minutes % 60} min`;
};

// "DL/PA1ABC/P" -> "PA1ABC": QRZ only knows the base callsign.
const baseCall = (call) =>
  String(call || "")
    .split("/")
    .reduce((a, b) => (b.length > a.length ? b : a), "");

const formatFreq = (khz) => {
  if (khz === null || khz === undefined || khz === "") return "";
  const n = Number(khz);
  return Number.isInteger(n) ? String(n) : n.toFixed(1);
};

class PotaSpotsCard extends HTMLElement {
  static getStubConfig(hass) {
    const entity = Object.keys(hass.states).find(
      (id) => id.startsWith("sensor.") && Array.isArray(hass.states[id].attributes.spots)
    );
    return { entity: entity || "" };
  }

  static getConfigForm() {
    return {
      schema: [
        { name: "entity", required: true, selector: { entity: { domain: "sensor" } } },
        { name: "title", selector: { text: {} } },
        { name: "max_rows", selector: { number: { min: 1, max: 50, mode: "box" } } },
        { name: "show_comments", selector: { boolean: {} } },
      ],
    };
  }

  setConfig(config) {
    if (!config || !config.entity) {
      throw new Error("Please define an entity (the POTA 'Active spots' sensor).");
    }
    this._config = config;
    this._lastKey = undefined;
    if (!this.shadowRoot) this.attachShadow({ mode: "open" });
    this._render();
  }

  set hass(hass) {
    this._hass = hass;
    this._render();
  }

  connectedCallback() {
    // Re-render periodically so the age column stays current between polls.
    this._timer = setInterval(() => this._render(), 30000);
  }

  disconnectedCallback() {
    clearInterval(this._timer);
  }

  getCardSize() {
    const spots = this._hass?.states[this._config?.entity]?.attributes.spots || [];
    return 1 + Math.min(spots.length, this._config?.max_rows || 50);
  }

  _render() {
    if (!this._config || !this._hass || !this.shadowRoot) return;
    const stateObj = this._hass.states[this._config.entity];
    const now = Date.now();
    const key = `${stateObj?.last_updated}|${Math.floor(now / 60000)}`;
    if (key === this._lastKey) return;
    this._lastKey = key;

    const title = this._config.title ?? stateObj?.attributes.friendly_name ?? "POTA Spots";
    let body;
    if (!stateObj) {
      body = `<div class="empty warning">Entity not found: ${escapeHtml(this._config.entity)}</div>`;
    } else {
      const spots = (stateObj.attributes.spots || []).slice(0, this._config.max_rows || 50);
      body = spots.length ? this._table(spots, now) : `<div class="empty">No active spots.</div>`;
    }

    this.shadowRoot.innerHTML = `
      <style>${PotaSpotsCard.styles}</style>
      <ha-card>
        <div class="header">
          <span>${escapeHtml(title)}</span>
          ${stateObj ? `<span class="count">${escapeHtml(stateObj.state)}</span>` : ""}
        </div>
        ${body}
      </ha-card>`;
  }

  _table(spots, now) {
    const rows = spots
      .map((s) => {
        const color = BAND_COLORS[s.band] || "var(--secondary-text-color)";
        const call = escapeHtml(s.activator);
        const ref = escapeHtml(s.reference);
        const comments =
          this._config.show_comments && s.comments
            ? `<div class="sub">${escapeHtml(s.comments)}</div>`
            : "";
        return `
          <tr>
            <td class="age">${escapeHtml(formatAge(s.spot_time, now))}</td>
            <td>
              <a href="https://www.qrz.com/db/${encodeURIComponent(baseCall(s.activator))}"
                 target="_blank" rel="noreferrer" class="call">${call}</a>
              ${comments}
            </td>
            <td>
              <a href="https://pota.app/#/park/${encodeURIComponent(s.reference || "")}"
                 target="_blank" rel="noreferrer">${ref}</a>
              <div class="sub">${escapeHtml(s.park_name)}</div>
            </td>
            <td class="num">${escapeHtml(formatFreq(s.frequency_khz))}</td>
            <td>
              <span class="mode">${escapeHtml(s.mode)}</span>
              ${s.band ? `<span class="band" style="--band:${color}">${escapeHtml(s.band)}</span>` : ""}
            </td>
          </tr>`;
      })
      .join("");
    return `
      <div class="wrap">
        <table>
          <thead>
            <tr><th>Age</th><th>Activator</th><th>Park</th><th class="num">kHz</th><th>Mode</th></tr>
          </thead>
          <tbody>${rows}</tbody>
        </table>
      </div>`;
  }

  static styles = `
    .header {
      display: flex; justify-content: space-between; align-items: center;
      padding: 16px 16px 8px; font-size: 1.2em; color: var(--primary-text-color);
    }
    .count {
      font-size: 0.8em; padding: 2px 10px; border-radius: 12px;
      background: var(--primary-color); color: var(--text-primary-color, #fff);
    }
    .wrap { overflow-x: auto; padding: 0 8px 12px; }
    table { width: 100%; border-collapse: collapse; font-size: 0.9em; }
    th {
      text-align: left; font-weight: 500; padding: 6px 8px;
      color: var(--secondary-text-color); border-bottom: 1px solid var(--divider-color);
    }
    td {
      padding: 6px 8px; vertical-align: top; color: var(--primary-text-color);
      border-bottom: 1px solid var(--divider-color);
    }
    tr:last-child td { border-bottom: none; }
    .num { text-align: right; font-variant-numeric: tabular-nums; white-space: nowrap; }
    .age { white-space: nowrap; color: var(--secondary-text-color); }
    .sub { font-size: 0.85em; color: var(--secondary-text-color); }
    a { color: var(--primary-color); text-decoration: none; }
    a:hover { text-decoration: underline; }
    .call { font-weight: 600; }
    .mode { white-space: nowrap; }
    .band {
      display: inline-block; margin-left: 4px; padding: 0 6px; border-radius: 8px;
      font-size: 0.8em; white-space: nowrap; color: var(--band);
      border: 1px solid var(--band);
    }
    .empty { padding: 0 16px 16px; color: var(--secondary-text-color); }
    .warning { color: var(--error-color); }
  `;
}

customElements.define("pota-spots-card", PotaSpotsCard);

window.customCards = window.customCards || [];
window.customCards.push({
  type: "pota-spots-card",
  name: "POTA Spots",
  description: "List of currently active POTA spots",
  documentationURL: "https://github.com/nils-a/ha-potaspot",
});
