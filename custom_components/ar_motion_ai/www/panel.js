// AR Motion AI — in-app event viewer.
// Opened from notification taps as /ar-motion-ai?event=<id>.

const esc = (s) =>
  String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));

class ArMotionAiPanel extends HTMLElement {
  constructor() {
    super();
    this.attachShadow({ mode: "open" });
    this._events = null;
    this._error = null;
    this._selected = null;
    this._loading = false;
    this._onLocation = () => this._readSelection();
    this._onVisible = () => document.visibilityState === "visible" && this._load();
  }

  set hass(hass) {
    const first = !this._hass;
    this._hass = hass;
    if (first) this._load();
    const btn = this.shadowRoot.querySelector("ha-menu-button");
    if (btn) btn.hass = hass;
  }

  set narrow(n) {
    this._narrow = n;
    const btn = this.shadowRoot.querySelector("ha-menu-button");
    if (btn) btn.narrow = n;
  }

  set route(_r) {
    this._readSelection();
  }

  connectedCallback() {
    window.addEventListener("location-changed", this._onLocation);
    window.addEventListener("popstate", this._onLocation);
    document.addEventListener("visibilitychange", this._onVisible);
    this._readSelection();
    if (this._hass) this._load();
  }

  disconnectedCallback() {
    window.removeEventListener("location-changed", this._onLocation);
    window.removeEventListener("popstate", this._onLocation);
    document.removeEventListener("visibilitychange", this._onVisible);
  }

  _readSelection() {
    const id = new URLSearchParams(window.location.search).get("event");
    if (id !== this._selected) {
      this._selected = id;
      this._render();
      // a fresh notification tap may point at an event we haven't fetched yet
      if (id && this._events && !this._events.some((e) => e.id === id)) this._load();
    }
  }

  async _load() {
    if (!this._hass || this._loading) return;
    this._loading = true;
    try {
      const res = await this._hass.callWS({ type: "ar_motion_ai/events" });
      this._events = res.events || [];
      this._error = null;
    } catch (err) {
      this._error = err?.message || String(err);
    }
    this._loading = false;
    this._render();
  }

  _select(id) {
    const url = `${window.location.pathname}?event=${encodeURIComponent(id)}`;
    window.history.replaceState(window.history.state, "", url);
    this._selected = id;
    this._render();
    this.shadowRoot.querySelector(".content")?.scrollTo({ top: 0, behavior: "smooth" });
  }

  _fmt(iso) {
    const d = new Date(iso);
    if (isNaN(d)) return "";
    const lang = this._hass?.locale?.language || undefined;
    return d.toLocaleString(lang, { weekday: "short", day: "numeric", month: "short", hour: "2-digit", minute: "2-digit", second: "2-digit" });
  }

  _ago(iso) {
    const s = Math.max(0, (Date.now() - new Date(iso)) / 1000);
    if (s < 60) return "just now";
    if (s < 3600) return `${Math.floor(s / 60)} min ago`;
    if (s < 86400) return `${Math.floor(s / 3600)} h ago`;
    return `${Math.floor(s / 86400)} d ago`;
  }

  _render() {
    const root = this.shadowRoot;
    const events = this._events || [];
    const current =
      events.find((e) => e.id === this._selected) || (!this._selected ? events[0] : null);
    const missing = this._selected && this._events && !current;

    let body;
    if (this._error) {
      body = `<div class="empty">Couldn't load events: ${esc(this._error)}</div>`;
    } else if (!this._events) {
      body = `<div class="empty">Loading…</div>`;
    } else if (!events.length) {
      body = `<div class="empty">No motion events yet.</div>`;
    } else {
      const hero = current
        ? `
        <section class="hero">
          <div class="shots ${current.images.length > 1 ? "multi" : ""}">
            ${current.images
              .map(
                (src, i) => `
              <a class="shot" href="${esc(src)}" target="_blank" rel="noopener">
                <img src="${esc(src)}" alt="Snapshot ${i + 1}" loading="eager"
                     onerror="this.closest('.shot').classList.add('gone')">
                ${current.images.length > 1 ? `<span class="idx">${i + 1}/${current.images.length}</span>` : ""}
              </a>`
              )
              .join("")}
          </div>
          <div class="meta">
            <div class="row">
              <h2>${esc(current.camera_name || current.name)}</h2>
              ${current.no_motion ? `<span class="chip quiet">No motion</span>` : `<span class="chip">${esc(current.trigger)}</span>`}
            </div>
            <div class="time">${esc(this._fmt(current.timestamp))} · ${esc(this._ago(current.timestamp))}</div>
            <p class="text">${esc(current.text)}</p>
          </div>
        </section>`
        : "";
      const note = missing
        ? `<div class="note">That event has been cleaned up — showing recent history.</div>`
        : "";
      const list = events
        .map(
          (e) => `
          <button class="item ${current && e.id === current.id ? "active" : ""}" data-id="${esc(e.id)}">
            <img src="${esc(e.images[0] || "")}" alt="" loading="lazy" onerror="this.style.visibility='hidden'">
            <span class="itxt">
              <span class="ihead"><b>${esc(e.camera_name || e.name)}</b><span>${esc(this._ago(e.timestamp))}</span></span>
              <span class="isub">${esc(e.text)}</span>
            </span>
          </button>`
        )
        .join("");
      body = `${note}${hero}<h3>Recent</h3><div class="list">${list}</div>`;
    }

    root.innerHTML = `
      <style>
        :host { display:block; height:100%; background:var(--primary-background-color); color:var(--primary-text-color);
                font-family:var(--paper-font-body1_-_font-family, Roboto, sans-serif); }
        .toolbar { display:flex; align-items:center; gap:4px; height:var(--header-height,56px); padding:0 12px 0 4px;
                   background:var(--app-header-background-color, var(--primary-color)); color:var(--app-header-text-color, #fff);
                   border-bottom:var(--app-header-border-bottom, none); box-sizing:border-box; }
        .toolbar .title { flex:1; font-size:20px; font-weight:400; margin-left:8px; }
        .toolbar button { background:none; border:0; color:inherit; font:inherit; font-size:14px; padding:8px 10px; border-radius:6px; cursor:pointer; }
        .content { height:calc(100% - var(--header-height,56px)); overflow:auto; padding:16px; box-sizing:border-box; }
        .wrap { max-width:900px; margin:0 auto; }
        .hero { background:var(--card-background-color); border-radius:var(--ha-card-border-radius,12px); overflow:hidden;
                box-shadow:var(--ha-card-box-shadow, none); border:1px solid var(--divider-color); }
        .shots { display:flex; overflow-x:auto; scroll-snap-type:x mandatory; background:#000; }
        .shot { position:relative; flex:0 0 100%; scroll-snap-align:start; display:block; }
        .shot img { width:100%; display:block; aspect-ratio:16/9; object-fit:contain; background:#000; }
        .shot.gone::after { content:"Snapshot no longer available"; position:absolute; inset:0; display:grid; place-items:center; color:#aaa; font-size:14px; }
        .shot.gone img { visibility:hidden; }
        .idx { position:absolute; right:10px; bottom:10px; background:rgba(0,0,0,.6); color:#fff; font-size:12px; padding:3px 8px; border-radius:10px; }
        .meta { padding:16px; }
        .row { display:flex; align-items:center; gap:10px; justify-content:space-between; }
        h2 { margin:0; font-size:18px; font-weight:500; }
        .chip { font-size:12px; padding:4px 10px; border-radius:12px; background:var(--primary-color); color:var(--text-primary-color,#fff); white-space:nowrap; }
        .chip.quiet { background:var(--secondary-background-color); color:var(--secondary-text-color); }
        .time { color:var(--secondary-text-color); font-size:13px; margin-top:4px; }
        .text { margin:12px 0 0; font-size:15px; line-height:1.5; white-space:pre-wrap; }
        h3 { margin:24px 4px 8px; font-size:14px; font-weight:500; color:var(--secondary-text-color); text-transform:uppercase; letter-spacing:.05em; }
        .list { display:flex; flex-direction:column; gap:8px; }
        .item { display:flex; gap:12px; align-items:center; text-align:left; width:100%; padding:8px; border-radius:10px; cursor:pointer;
                background:var(--card-background-color); border:1px solid var(--divider-color); color:inherit; font:inherit; }
        .item.active { border-color:var(--primary-color); }
        .item img { width:96px; height:54px; object-fit:cover; border-radius:6px; background:#000; flex:none; }
        .itxt { min-width:0; flex:1; display:flex; flex-direction:column; gap:2px; }
        .ihead { display:flex; justify-content:space-between; gap:8px; font-size:14px; }
        .ihead span { color:var(--secondary-text-color); font-size:12px; white-space:nowrap; }
        .isub { color:var(--secondary-text-color); font-size:13px; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }
        .empty { padding:48px 16px; text-align:center; color:var(--secondary-text-color); }
        .note { margin-bottom:12px; padding:10px 14px; border-radius:8px; background:var(--secondary-background-color); color:var(--secondary-text-color); font-size:14px; }
      </style>
      <div class="toolbar">
        <ha-menu-button></ha-menu-button>
        <div class="title">Motion AI</div>
        <button class="refresh" title="Refresh">Refresh</button>
      </div>
      <div class="content"><div class="wrap">${body}</div></div>`;

    const btn = root.querySelector("ha-menu-button");
    if (btn) { btn.hass = this._hass; btn.narrow = this._narrow; }
    root.querySelector(".refresh").addEventListener("click", () => this._load());
    root.querySelectorAll(".item").forEach((el) =>
      el.addEventListener("click", () => this._select(el.dataset.id))
    );
  }
}

if (!customElements.get("ar-motion-ai-panel")) {
  customElements.define("ar-motion-ai-panel", ArMotionAiPanel);
}
