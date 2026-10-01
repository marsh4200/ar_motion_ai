// AR Motion AI — in-app event viewer.
// Opened from notification taps as /ar-motion-ai?event=<id>.

const esc = (s) =>
  String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));

const ICON = {
  refresh: "M17.65 6.35A7.95 7.95 0 0 0 12 4a8 8 0 1 0 7.73 10h-2.08A6 6 0 1 1 12 6c1.66 0 3.14.69 4.22 1.78L13 11h7V4l-2.35 2.35z",
  spark: "M12 2l1.9 5.6L19.5 9.5l-5.6 1.9L12 17l-1.9-5.6L4.5 9.5l5.6-1.9L12 2zm7 11l.95 2.55L22.5 16.5l-2.55.95L19 20l-.95-2.55-2.55-.95 2.55-.95L19 13z",
  cam: "M17 10.5V7a1 1 0 0 0-1-1H4a1 1 0 0 0-1 1v10a1 1 0 0 0 1 1h12a1 1 0 0 0 1-1v-3.5l4 4v-11l-4 4z",
  close: "M19 6.41 17.59 5 12 10.59 6.41 5 5 6.41 10.59 12 5 17.59 6.41 19 12 13.41 17.59 19 19 17.59 13.41 12z",
  left: "M15.41 7.41 14 6l-6 6 6 6 1.41-1.41L10.83 12z",
  right: "M8.59 16.59 10 18l6-6-6-6-1.41 1.41L13.17 12z",
  expand: "M7 14H5v5h5v-2H7v-3zm-2-4h2V7h3V5H5v5zm12 7h-3v2h5v-5h-2v3zM14 5v2h3v3h2V5h-5z",
};
const svg = (d, s = 20) => `<svg viewBox="0 0 24 24" width="${s}" height="${s}" aria-hidden="true"><path fill="currentColor" d="${d}"/></svg>`;

class ArMotionAiPanel extends HTMLElement {
  constructor() {
    super();
    this.attachShadow({ mode: "open" });
    this._events = null;
    this._error = null;
    this._selected = null;
    this._filter = "all";
    this._shot = 0;
    this._lightbox = false;
    this._loading = false;
    this._onLocation = () => this._readSelection();
    this._onVisible = () => document.visibilityState === "visible" && this._load();
    this._onKey = (e) => {
      if (!this._lightbox) return;
      if (e.key === "Escape") this._setLightbox(false);
      if (e.key === "ArrowLeft") this._step(-1);
      if (e.key === "ArrowRight") this._step(1);
    };
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
    window.addEventListener("keydown", this._onKey);
    document.addEventListener("visibilitychange", this._onVisible);
    this._readSelection();
    if (this._hass) this._load();
  }

  disconnectedCallback() {
    window.removeEventListener("location-changed", this._onLocation);
    window.removeEventListener("popstate", this._onLocation);
    window.removeEventListener("keydown", this._onKey);
    document.removeEventListener("visibilitychange", this._onVisible);
  }

  _readSelection() {
    const id = new URLSearchParams(window.location.search).get("event");
    if (id !== this._selected) {
      this._selected = id;
      this._shot = 0;
      this._render();
      if (id && this._events && !this._events.some((e) => e.id === id)) this._load();
    }
  }

  async _load() {
    if (!this._hass || this._loading) return;
    this._loading = true;
    this.shadowRoot.querySelector(".refresh")?.classList.add("spin");
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
    this._shot = 0;
    this._render();
    this.shadowRoot.querySelector(".content")?.scrollTo({ top: 0, behavior: "smooth" });
  }

  _current() {
    const ev = this._events || [];
    return ev.find((e) => e.id === this._selected) || (!this._selected ? ev[0] : null);
  }

  _step(d) {
    const cur = this._current();
    if (!cur || cur.images.length < 2) return;
    this._shot = (this._shot + d + cur.images.length) % cur.images.length;
    const strip = this.shadowRoot.querySelector(".strip");
    strip?.scrollTo({ left: strip.clientWidth * this._shot, behavior: "smooth" });
    this._syncDots();
    const lb = this.shadowRoot.querySelector(".lb img");
    if (lb) lb.src = cur.images[this._shot];
  }

  _syncDots() {
    this.shadowRoot.querySelectorAll(".dot").forEach((d, i) => d.classList.toggle("on", i === this._shot));
    const c = this.shadowRoot.querySelector(".count");
    const cur = this._current();
    if (c && cur) c.textContent = `${this._shot + 1} / ${cur.images.length}`;
  }

  _setLightbox(open) {
    this._lightbox = open;
    this.shadowRoot.querySelector(".lb")?.classList.toggle("open", open);
    const cur = this._current();
    const img = this.shadowRoot.querySelector(".lb img");
    if (open && img && cur) img.src = cur.images[this._shot];
  }

  _lang() {
    return this._hass?.locale?.language || undefined;
  }
  _clock(iso) {
    const d = new Date(iso);
    return isNaN(d) ? "" : d.toLocaleTimeString(this._lang(), { hour: "2-digit", minute: "2-digit" });
  }
  _osd(iso) {
    const d = new Date(iso);
    if (isNaN(d)) return "";
    const p = (n) => String(n).padStart(2, "0");
    return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())}  ${p(d.getHours())}:${p(d.getMinutes())}:${p(d.getSeconds())}`;
  }
  _ago(iso) {
    const s = Math.max(0, (Date.now() - new Date(iso)) / 1000);
    if (s < 60) return "Just now";
    if (s < 3600) return `${Math.floor(s / 60)} min ago`;
    if (s < 86400) return `${Math.floor(s / 3600)} h ago`;
    return `${Math.floor(s / 86400)} d ago`;
  }
  _day(iso) {
    const d = new Date(iso);
    const start = (x) => new Date(x.getFullYear(), x.getMonth(), x.getDate()).getTime();
    const diff = Math.round((start(new Date()) - start(d)) / 86400000);
    if (diff === 0) return "Today";
    if (diff === 1) return "Yesterday";
    return d.toLocaleDateString(this._lang(), { weekday: "long", day: "numeric", month: "long" });
  }

  _hero(cur) {
    const multi = cur.images.length > 1;
    const cam = cur.camera_name || cur.name;
    return `
      <section class="hero">
        <div class="frame">
          <div class="strip">
            ${cur.images
              .map(
                (src, i) => `
              <div class="shot">
                <img src="${esc(src)}" alt="Snapshot ${i + 1}" onerror="this.parentNode.classList.add('gone')">
              </div>`
              )
              .join("")}
          </div>
          <div class="osd top">
            <span class="rec"><i></i>${esc(cam.toUpperCase())}</span>
            <span class="mono">${esc(this._osd(cur.timestamp))}</span>
          </div>
          <button class="expand" title="Full screen">${svg(ICON.expand, 18)}</button>
          ${
            multi
              ? `<button class="nav prev" title="Previous">${svg(ICON.left, 22)}</button>
                 <button class="nav next" title="Next">${svg(ICON.right, 22)}</button>
                 <div class="osd bottom">
                   <span class="dots">${cur.images.map((_, i) => `<i class="dot ${i === this._shot ? "on" : ""}"></i>`).join("")}</span>
                   <span class="count mono">${this._shot + 1} / ${cur.images.length}</span>
                 </div>`
              : ""
          }
        </div>
        <div class="body">
          <div class="title-row">
            <h1>${esc(cam)}</h1>
            <span class="pill ${cur.no_motion ? "muted" : ""}">${cur.no_motion ? "No motion" : esc(cur.trigger || "Motion")}</span>
          </div>
          <div class="sub">${esc(this._day(cur.timestamp))} at ${esc(this._clock(cur.timestamp))} \u00b7 ${esc(this._ago(cur.timestamp))}</div>
          <div class="ai">
            <div class="ai-head">${svg(ICON.spark, 16)}<span>AI analysis</span></div>
            <p>${esc(cur.text)}</p>
          </div>
        </div>
      </section>`;
  }

  _render() {
    const root = this.shadowRoot;
    const all = this._events || [];
    const cur = this._current();
    const missing = this._selected && this._events && !cur;
    const cams = [...new Set(all.map((e) => e.camera_name || e.name))];
    const list = all.filter((e) => this._filter === "all" || (e.camera_name || e.name) === this._filter);

    let body;
    if (this._error) {
      body = `<div class="empty">${svg(ICON.cam, 40)}<b>Couldn't load events</b><span>${esc(this._error)}</span></div>`;
    } else if (!this._events) {
      body = `<div class="skeleton hero-sk"></div><div class="skeleton line"></div><div class="skeleton line short"></div>`;
    } else if (!all.length) {
      body = `<div class="empty">${svg(ICON.cam, 40)}<b>No motion events yet</b><span>Snapshots and AI descriptions will show up here.</span></div>`;
    } else {
      let groups = "";
      let lastDay = null;
      for (const e of list) {
        const day = this._day(e.timestamp);
        if (day !== lastDay) {
          if (lastDay !== null) groups += `</div>`;
          groups += `<div class="day">${esc(day)}</div><div class="timeline">`;
          lastDay = day;
        }
        const active = cur && e.id === cur.id;
        groups += `
          <button class="item ${active ? "active" : ""} ${e.no_motion ? "quiet" : ""}" data-id="${esc(e.id)}">
            <span class="time mono">${esc(this._clock(e.timestamp))}</span>
            <span class="node"></span>
            <span class="card">
              <span class="thumb">
                <img src="${esc(e.images[0] || "")}" alt="" loading="lazy" onerror="this.style.visibility='hidden'">
                ${e.images.length > 1 ? `<span class="badge">${e.images.length}</span>` : ""}
              </span>
              <span class="itxt">
                <b>${esc(e.camera_name || e.name)}</b>
                <span>${esc(e.text)}</span>
              </span>
            </span>
          </button>`;
      }
      if (lastDay !== null) groups += `</div>`;

      body = `
        ${missing ? `<div class="note">That event has been cleaned up. Showing recent history.</div>` : ""}
        ${cur ? this._hero(cur) : ""}
        <div class="hist-head">
          <h2>History</h2>
          <span class="muted">${list.length} event${list.length === 1 ? "" : "s"}</span>
        </div>
        ${
          cams.length > 1
            ? `<div class="filters">
                <button class="chip ${this._filter === "all" ? "on" : ""}" data-f="all">All</button>
                ${cams.map((c) => `<button class="chip ${this._filter === c ? "on" : ""}" data-f="${esc(c)}">${esc(c)}</button>`).join("")}
              </div>`
            : ""
        }
        ${groups || `<div class="empty small">No events for this camera.</div>`}`;
    }

    root.innerHTML = `
      <style>
        :host {
          --accent: var(--primary-color, #03a9f4);
          --bg: var(--primary-background-color, #111);
          --card: var(--card-background-color, #1c1c1c);
          --fg: var(--primary-text-color, #e1e1e1);
          --fg2: var(--secondary-text-color, #9b9b9b);
          --line: var(--divider-color, rgba(127,127,127,.2));
          --radius: var(--ha-card-border-radius, 16px);
          display:block; height:100%; background:var(--bg); color:var(--fg);
          font-family: var(--ha-font-family-body, var(--paper-font-body1_-_font-family, Roboto, system-ui, sans-serif));
          -webkit-font-smoothing: antialiased;
        }
        * { box-sizing:border-box; }
        button { font:inherit; color:inherit; background:none; border:0; padding:0; cursor:pointer; }
        .mono { font-family: ui-monospace, "SF Mono", "Roboto Mono", Menlo, monospace; font-variant-numeric: tabular-nums; }
        .muted { color:var(--fg2); }

        .toolbar { display:flex; align-items:center; gap:4px; height:var(--header-height,56px); padding:0 8px 0 4px;
          background:var(--app-header-background-color, var(--accent)); color:var(--app-header-text-color, #fff);
          border-bottom:var(--app-header-border-bottom, none); }
        .toolbar .title { flex:1; font-size:20px; font-weight:400; margin-left:8px; display:flex; align-items:center; gap:10px; }
        .toolbar .refresh { width:40px; height:40px; border-radius:50%; display:grid; place-items:center; }
        .toolbar .refresh:hover { background:rgba(255,255,255,.1); }
        .spin svg { animation: spin .8s linear infinite; }
        @keyframes spin { to { transform: rotate(360deg); } }

        .content { height:calc(100% - var(--header-height,56px)); overflow:auto; padding:16px 16px 40px; }
        .wrap { max-width:920px; margin:0 auto; }

        /* hero */
        .hero { background:var(--card); border-radius:var(--radius); overflow:hidden; border:1px solid var(--line);
          box-shadow: var(--ha-card-box-shadow, 0 8px 28px rgba(0,0,0,.25)); animation: rise .35s ease-out; }
        @keyframes rise { from { opacity:0; transform:translateY(8px); } }
        .frame { position:relative; background:#000; aspect-ratio:16/9; }
        .strip { display:flex; height:100%; overflow-x:auto; scroll-snap-type:x mandatory; scrollbar-width:none; }
        .strip::-webkit-scrollbar { display:none; }
        .shot { flex:0 0 100%; height:100%; scroll-snap-align:center; position:relative; }
        .shot img { width:100%; height:100%; object-fit:cover; display:block; }
        .shot.gone img { visibility:hidden; }
        .shot.gone::after { content:"Snapshot no longer available"; position:absolute; inset:0; display:grid; place-items:center; color:#888; font-size:14px; }
        .osd { position:absolute; left:0; right:0; display:flex; justify-content:space-between; align-items:center;
          padding:12px 14px; color:#fff; font-size:12px; letter-spacing:.06em; pointer-events:none; text-shadow:0 1px 2px rgba(0,0,0,.6); }
        .osd.top { top:0; background:linear-gradient(rgba(0,0,0,.6), transparent); padding-right:56px; }
        .osd.bottom { bottom:0; background:linear-gradient(transparent, rgba(0,0,0,.6)); }
        .rec { display:flex; align-items:center; gap:8px; font-weight:600; }
        .rec i { width:8px; height:8px; border-radius:50%; background:#ff3b30; box-shadow:0 0 0 3px rgba(255,59,48,.25); animation: blink 1.6s ease-in-out infinite; }
        @keyframes blink { 50% { opacity:.35; } }
        .dots { display:flex; gap:6px; }
        .dot { width:6px; height:6px; border-radius:3px; background:rgba(255,255,255,.45); transition: all .2s; }
        .dot.on { width:18px; background:#fff; }
        .expand, .nav { position:absolute; display:grid; place-items:center; color:#fff;
          background:rgba(0,0,0,.4); backdrop-filter: blur(6px); -webkit-backdrop-filter: blur(6px); border-radius:50%; }
        .expand { top:8px; right:8px; width:36px; height:36px; }
        .nav { top:50%; transform:translateY(-50%); width:36px; height:36px; opacity:.85; }
        .nav.prev { left:10px; } .nav.next { right:10px; }

        .body { padding:18px 18px 20px; }
        .title-row { display:flex; align-items:center; justify-content:space-between; gap:12px; }
        h1 { margin:0; font-size:22px; font-weight:600; letter-spacing:-.01em; }
        .pill { font-size:12px; font-weight:600; padding:5px 11px; border-radius:999px; white-space:nowrap;
          color:var(--accent); background:color-mix(in srgb, var(--accent) 16%, transparent); }
        .pill.muted { color:var(--fg2); background:color-mix(in srgb, var(--fg2) 14%, transparent); }
        .sub { color:var(--fg2); font-size:13px; margin-top:4px; }
        .ai { margin-top:16px; padding:14px 16px; border-radius:12px;
          background:color-mix(in srgb, var(--accent) 7%, transparent);
          border:1px solid color-mix(in srgb, var(--accent) 22%, transparent); }
        .ai-head { display:flex; align-items:center; gap:6px; color:var(--accent); font-size:12px; font-weight:600;
          text-transform:uppercase; letter-spacing:.08em; }
        .ai p { margin:8px 0 0; font-size:15.5px; line-height:1.6; white-space:pre-wrap; }

        /* history */
        .hist-head { display:flex; align-items:baseline; justify-content:space-between; margin:28px 2px 10px; }
        h2 { margin:0; font-size:17px; font-weight:600; }
        .hist-head .muted { font-size:13px; }
        .filters { display:flex; gap:8px; overflow-x:auto; padding:2px 2px 8px; scrollbar-width:none; }
        .filters::-webkit-scrollbar { display:none; }
        .chip { white-space:nowrap; font-size:13px; padding:7px 14px; border-radius:999px; border:1px solid var(--line); background:var(--card); }
        .chip.on { background:var(--accent); border-color:var(--accent); color:var(--text-primary-color, #fff); }
        .day { margin:14px 2px 6px; font-size:12px; font-weight:600; color:var(--fg2); text-transform:uppercase; letter-spacing:.08em; }
        .timeline { position:relative; }
        .timeline::before { content:""; position:absolute; left:55px; top:8px; bottom:8px; width:2px; background:var(--line); border-radius:1px; }
        .item { position:relative; display:grid; grid-template-columns:44px 22px 1fr; align-items:center; width:100%; text-align:left; padding:5px 0; }
        .item .time { font-size:12px; color:var(--fg2); text-align:right; padding-right:2px; }
        .node { justify-self:center; width:10px; height:10px; border-radius:50%; background:var(--bg); border:2px solid var(--accent); z-index:1; }
        .item.quiet .node { border-color:var(--fg2); }
        .item.active .node { background:var(--accent); box-shadow:0 0 0 4px color-mix(in srgb, var(--accent) 25%, transparent); }
        .card { display:flex; gap:12px; align-items:center; padding:8px; border-radius:12px; background:var(--card);
          border:1px solid var(--line); min-width:0; transition: border-color .15s, transform .15s; }
        .item:active .card { transform: scale(.985); }
        .item.active .card { border-color:var(--accent); }
        .item.quiet .card { opacity:.6; }
        .thumb { position:relative; flex:none; width:92px; aspect-ratio:16/9; border-radius:8px; overflow:hidden; background:#000; }
        .thumb img { width:100%; height:100%; object-fit:cover; display:block; }
        .badge { position:absolute; right:4px; bottom:4px; font-size:10px; font-weight:600; color:#fff;
          background:rgba(0,0,0,.65); padding:1px 6px; border-radius:6px; }
        .itxt { min-width:0; display:flex; flex-direction:column; gap:3px; }
        .itxt b { font-size:14px; font-weight:600; }
        .itxt span { font-size:13px; color:var(--fg2); line-height:1.35; display:-webkit-box; -webkit-line-clamp:2; -webkit-box-orient:vertical; overflow:hidden; }

        .empty { display:flex; flex-direction:column; align-items:center; gap:8px; padding:72px 16px; text-align:center; color:var(--fg2); }
        .empty svg { opacity:.5; margin-bottom:4px; }
        .empty b { color:var(--fg); font-size:16px; font-weight:600; }
        .empty.small { padding:24px; }
        .note { margin-bottom:12px; padding:10px 14px; border-radius:10px; background:var(--card); border:1px solid var(--line); color:var(--fg2); font-size:14px; }
        .skeleton { border-radius:var(--radius); background:linear-gradient(90deg, var(--card) 25%, color-mix(in srgb, var(--card) 70%, var(--fg2)) 50%, var(--card) 75%);
          background-size:200% 100%; animation: shimmer 1.2s infinite; }
        .hero-sk { aspect-ratio:16/10; } .line { height:18px; margin-top:16px; border-radius:6px; } .line.short { width:60%; }
        @keyframes shimmer { to { background-position:-200% 0; } }

        /* lightbox */
        .lb { position:fixed; inset:0; z-index:10; background:rgba(0,0,0,.94); display:none; align-items:center; justify-content:center; }
        .lb.open { display:flex; }
        .lb img { max-width:100%; max-height:100%; object-fit:contain; }
        .lb .x { position:absolute; top:12px; right:12px; width:44px; height:44px; border-radius:50%; display:grid; place-items:center; color:#fff; background:rgba(255,255,255,.12); }
        .lb .nav { position:absolute; width:44px; height:44px; }

        @media (min-width: 760px) {
          .hero { display:grid; grid-template-columns: 1.5fr 1fr; }
          .frame { aspect-ratio:auto; min-height:320px; }
          .body { display:flex; flex-direction:column; }
        }
        @media (prefers-reduced-motion: reduce) { * { animation:none !important; transition:none !important; } }
      </style>
      <div class="toolbar">
        <ha-menu-button></ha-menu-button>
        <div class="title">Motion AI</div>
        <button class="refresh ${this._loading ? "spin" : ""}" title="Refresh">${svg(ICON.refresh, 22)}</button>
      </div>
      <div class="content"><div class="wrap">${body}</div></div>
      <div class="lb ${this._lightbox ? "open" : ""}">
        <img alt="">
        <button class="x" title="Close">${svg(ICON.close, 24)}</button>
        ${cur && cur.images.length > 1 ? `<button class="nav prev" title="Previous">${svg(ICON.left, 26)}</button><button class="nav next" title="Next">${svg(ICON.right, 26)}</button>` : ""}
      </div>`;

    const btn = root.querySelector("ha-menu-button");
    if (btn) { btn.hass = this._hass; btn.narrow = this._narrow; }
    root.querySelector(".refresh").addEventListener("click", () => this._load());
    root.querySelectorAll(".item").forEach((el) => el.addEventListener("click", () => this._select(el.dataset.id)));
    root.querySelectorAll(".chip").forEach((el) =>
      el.addEventListener("click", () => { this._filter = el.dataset.f; this._render(); })
    );
    root.querySelectorAll(".prev").forEach((el) => el.addEventListener("click", (e) => { e.stopPropagation(); this._step(-1); }));
    root.querySelectorAll(".next").forEach((el) => el.addEventListener("click", (e) => { e.stopPropagation(); this._step(1); }));
    root.querySelector(".expand")?.addEventListener("click", () => this._setLightbox(true));
    root.querySelectorAll(".shot img").forEach((el) => el.addEventListener("click", () => this._setLightbox(true)));
    root.querySelector(".lb .x")?.addEventListener("click", () => this._setLightbox(false));
    root.querySelector(".lb")?.addEventListener("click", (e) => { if (e.target.classList.contains("lb")) this._setLightbox(false); });

    const strip = root.querySelector(".strip");
    if (strip) {
      if (this._shot) strip.scrollLeft = strip.clientWidth * this._shot;
      strip.addEventListener("scroll", () => {
        const i = Math.round(strip.scrollLeft / Math.max(1, strip.clientWidth));
        if (i !== this._shot) { this._shot = i; this._syncDots(); }
      }, { passive: true });
    }
    if (this._lightbox) this._setLightbox(true);
  }
}

if (!customElements.get("ar-motion-ai-panel")) {
  customElements.define("ar-motion-ai-panel", ArMotionAiPanel);
}
