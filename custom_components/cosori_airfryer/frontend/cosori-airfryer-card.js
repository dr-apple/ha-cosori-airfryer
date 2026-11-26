/*
 * Cosori Airfryer Card – a drawing of the fryer with a live, touchable control panel.
 * Shipped and registered by the cosori_airfryer integration.
 *
 *   type: custom:cosori-airfryer-card
 *   device_id: <optional, first Cosori fryer if omitted>
 *   model: <optional: twinfry | turbotower | dualblaze | turboblaze | cs158 | cs358; auto-detected>
 *   image: <optional own picture URL; front view, 4:3>
 *
 * Wide card (>= 640 px): the photo itself is the remote control.
 * Narrow card: the photo shows the live state; a tap opens a large control
 * view (zoomed panel + basket tiles).
 */
const BASE = new URL(".", import.meta.url).pathname; // /cosori_airfryer/
const VER = new URL(import.meta.url).search; // ?v=<integration version>
const COMPACT_BELOW = 640;

const T = {
  de: {
    modes: { airfry: "HEISSLUFT", roast: "BRATEN", bake: "BACKEN", grill: "GRILLEN", reheat: "WÄRMEN", dry: "TROCKNEN" },
    modesLong: { airfry: "Heißluft", roast: "Braten", bake: "Backen", grill: "Grillen", reheat: "Aufwärmen", dry: "Trocknen" },
    zone1: "KORB 1", zone2: "KORB 2", whole: "GANZER KORB", sync: "SYNC", match: "MATCH",
    status: {
      standby: "Bereit", cooking: "Gart", cook_stop: "Pausiert", cook_end: "Fertig", pull_out: "Korb raus",
      heating: "Heizt vor", hold: "Wartet", ready: "Wartet auf Start", preheat_end: "Vorgeheizt",
      preheat_stop: "Pausiert", appointing: "Geplant", completed: "Fertig", unknown: "–",
    },
    basket: "Korb", done: "fertig", offline: "Offline", confirmStart: "Nochmal tippen zum Starten",
    confirmEnd: "Nochmal tippen zum Beenden", confirmAll: "Nochmal tippen: alles aus", close: "Schließen",
    hint: "Tippen zum Bedienen", noLinkWhole: "Sync/Match nur mit zwei Körben",
    plan: "Zeitplan", planTitle: "Start planen", planStartAt: "Start um", planFinishAt: "Fertig um",
    planDo: "Planen", planCancel: "Zeitplan löschen", planStarts: "Startet", planFinishes: "fertig ca.",
    planWill: "Wird gestartet mit", planArmed: "Geplant", planHint: "Einstellungen werden beim Planen übernommen.",
    days: ["So", "Mo", "Di", "Mi", "Do", "Fr", "Sa"], today: "heute", tomorrow: "morgen", whole2: "Ganzer Korb",
  },
  en: {
    modes: { airfry: "AIR FRY", roast: "ROAST", bake: "BAKE", grill: "GRILL", reheat: "REHEAT", dry: "DRY" },
    modesLong: { airfry: "Air fry", roast: "Roast", bake: "Bake", grill: "Grill", reheat: "Reheat", dry: "Dry" },
    zone1: "ZONE 1", zone2: "ZONE 2", whole: "GRANDZONE", sync: "SYNC", match: "MATCH",
    status: {
      standby: "Ready", cooking: "Cooking", cook_stop: "Paused", cook_end: "Done", pull_out: "Basket out",
      heating: "Preheating", hold: "Waiting", ready: "Waiting for start", preheat_end: "Preheated",
      preheat_stop: "Paused", appointing: "Scheduled", completed: "Done", unknown: "–",
    },
    basket: "Basket", done: "done", offline: "Offline", confirmStart: "Tap again to start",
    confirmEnd: "Tap again to stop", confirmAll: "Tap again: all off", close: "Close",
    hint: "Tap to control", noLinkWhole: "Sync/Match needs two baskets",
    plan: "Schedule", planTitle: "Plan a start", planStartAt: "Start at", planFinishAt: "Finish at",
    planDo: "Schedule", planCancel: "Delete schedule", planStarts: "Starts", planFinishes: "done approx.",
    planWill: "Will start with", planArmed: "Scheduled", planHint: "Settings are frozen when scheduling.",
    days: ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"], today: "today", tomorrow: "tomorrow", whole2: "Whole basket",
  },
};

/*
 * Model drawings (own artwork, frontend/models/*.svg, all on a 1081x802 canvas).
 * panel: usable glass area [x, y, w, h] in % where the live control panel goes.
 * chips: basket tile centres [x, y] in %, chipW: tile width in %, plan: schedule button.
 */
const SKINS = {
  twinfry: { name: "Dual Blaze TwinFry (CAF-TF101S / TF102S)", panel: [27.5, 16, 46, 18.5], exact: true,
             chips: [[21.5, 50.5], [78.5, 50.5]], one: [50, 50.5], chipW: 27, plan: [50, 58.5] },
  turbotower: { name: "Turbo Tower Pro (CAF-DC111S)", panel: [32.4, 6.2, 35.3, 20.5],
             chips: [[15, 45], [85, 45]], one: [15, 45], chipW: 26, plan: [85, 66] },
  dualblaze: { name: "Dual Blaze 6.8 Qt (CAF-P583S)", panel: [29.8, 9.6, 40.4, 23],
             chips: [[15, 45], [85, 45]], one: [14.5, 45], chipW: 25, plan: [14.5, 66] },
  turboblaze: { name: "TurboBlaze 6 Qt (CAF-DC601S)", panel: [27.8, 15, 44.4, 22],
             chips: [[11.5, 45], [88.5, 45]], one: [11.5, 45], chipW: 20.5, plan: [11.5, 66] },
  cs158: { name: "Smart / Pro 5.8 Qt (CS158 / CS137)", panel: [31.6, 18, 36.8, 18.5],
           chips: [[14, 45], [86, 45]], one: [14, 45], chipW: 24.5, plan: [14, 66] },
  cs358: { name: "Pro II 5.8 Qt (CS358)", panel: [29.8, 15, 40.4, 22],
           chips: [[13.5, 45], [86.5, 45]], one: [13.5, 45], chipW: 24, plan: [13.5, 66] },
};
const SKIN_BY_MODEL = [
  [/^CAF-TF10/i, "twinfry"], [/^CAF-DC1[0-2]/i, "turbotower"], [/^CAF-P58/i, "dualblaze"],
  [/^CAF-DC60/i, "turboblaze"], [/^CS358/i, "cs358"], [/^CS1[0-9]{2}/i, "cs158"],
];
/* where the TwinFry panel sits on its own drawing: with and without the basket row */
const REF = { two: [27.5, 16, 46, 18.5], one: [27.5, 16, 46, 15] };

/* skin for a card config / device model: explicit choice, else by model id, else by basket count */
function skinFor(choice, modelId, dual) {
  if (choice && SKINS[choice]) return choice;
  for (const [re, id] of SKIN_BY_MODEL) if (re.test(modelId)) return id;
  return dual ? "twinfry" : "cs158";
}

const MODES = ["airfry", "roast", "bake", "grill", "reheat", "dry"];
const MODE_X = [35.3, 41.6, 47.8, 54.1, 60.2, 66.5];
const ACTIVE = ["cooking", "heating", "hold", "cook_stop", "pull_out", "ready", "preheat_end", "preheat_stop", "appointing"];
const RUNNING = ["cooking", "heating", "hold"];

const CSS = `
  :host { display:block; }
  ha-card { overflow:hidden; background: var(--ha-card-background, var(--card-background-color)); }
  .wrap { position:relative; width:100%; aspect-ratio:1081/802; container-type:inline-size; user-select:none; -webkit-user-select:none; }
  .wrap > img { position:absolute; inset:0; width:100%; height:100%; pointer-events:none; transition:filter .4s; }
  .wrap.photo > img { object-fit:cover; }
  .panel { position:absolute; inset:0; transform-origin:0 0; pointer-events:none; }
  .panel > * { pointer-events:auto; }
  .panel > .ico { position:absolute; transform:translate(-50%,-50%); pointer-events:none; fill:none; stroke:#a2a2a8; stroke-width:2;
                  stroke-linecap:round; stroke-linejoin:round; opacity:.9; }
  .panel > .ico.pw { stroke:#d9722f; }
  .panel > .ico .f { fill:#e6e6ea; stroke:none; }
  .wrap.off > img { filter: grayscale(.7) brightness(.6); }
  .compact .wrap { cursor:pointer; }
  .compact .wrap .o, .compact .wrap .disp, .compact .wrap .panel > * { pointer-events:none; }
  .o { position:absolute; transform:translate(-50%,-50%); cursor:pointer; -webkit-tap-highlight-color:transparent; }
  .disp { position:absolute; left:37.9%; top:18.4%; width:25.9%; height:6%; display:flex; align-items:center; justify-content:space-between;
          padding:0 1.2cqw; box-sizing:border-box; cursor:pointer; }
  .seg { font-family: "Share Tech Mono", "SF Mono", "Consolas", "Courier New", monospace; font-weight:700; font-size:3.6cqw;
         color:#dfeaff; letter-spacing:.25cqw; text-shadow:0 0 .6cqw rgba(160,200,255,.85), 0 0 1.6cqw rgba(120,170,255,.35); line-height:1; }
  .seg small { font-size:2.2cqw; margin-left:.2cqw; }
  .tag { position:absolute; left:50%; top:-1.1cqw; transform:translateX(-50%); font:600 1.05cqw/1 system-ui,sans-serif; letter-spacing:.12cqw;
         color:#ff9a3c; text-shadow:0 0 .5cqw rgba(255,140,40,.7); white-space:nowrap; }
  .dot { display:inline-block; width:.7em; height:.7em; border-radius:50%; background:#ff9a3c; box-shadow:0 0 .7em #ff8a20; margin-right:.5em;
         animation: pulse 1.4s infinite; vertical-align:middle; }
  .arr { width:3.6cqw; height:2.6cqw; }
  .btn { width:4.4cqw; height:4.4cqw; border-radius:50%; }
  .btn.on { box-shadow:0 0 1.4cqw rgba(255,150,60,.9), inset 0 0 .8cqw rgba(255,150,60,.6); }
  .lbl { font:600 .98cqw/1 system-ui,-apple-system,sans-serif; letter-spacing:.02cqw; color:#e8e8ea; white-space:nowrap; padding:.6cqw .5cqw;
         transition: color .2s, text-shadow .2s; }
  .lbl.sel { color:#ff9a3c; text-shadow:0 0 .7cqw rgba(255,140,40,.8); }
  .pill { font:600 1.02cqw/1 system-ui,-apple-system,sans-serif; letter-spacing:.08cqw; color:#e8e8ea; border:.14cqw solid #cfcfd2;
          border-radius:2cqw; padding:.35cqw 1.1cqw; white-space:nowrap; transition: all .2s; }
  .pill.filled { background:#f2f2f2; color:#1d1d1f; border-color:#f2f2f2; }
  .pill.sel { color:#ff9a3c; border-color:#ff9a3c; box-shadow:0 0 .9cqw rgba(255,140,40,.6); }
  .pill.filled.sel { background:#ff9a3c; color:#1d1d1f; }
  .pill.run { animation: glow 1.6s infinite; }
  .pill.dim { opacity:.35; cursor:default; }
  .chip { box-sizing:border-box; border-radius:14px; background:rgba(20,20,22,.62); backdrop-filter: blur(6px); -webkit-backdrop-filter: blur(6px);
          border:1px solid rgba(255,255,255,.08); color:#f1f1f3; font: 500 14px/1.3 system-ui,-apple-system,sans-serif; cursor:pointer; padding:10px 12px; }
  .wrap .chip { position:absolute; transform:translate(-50%,-50%); width:27%; padding:1.1cqw 1.4cqw; border-radius:1.6cqw;
                font-size:1.55cqw; border-width:.12cqw; }
  .chip .h { display:flex; justify-content:space-between; align-items:center; font-weight:700; gap:.5em; }
  .chip .s { color:#bdbdc2; font-size:.9em; white-space:nowrap; }
  .chip.act { border-color: rgba(255,154,60,.55); }
  .chip.act .s { color:#ffb36b; }
  .chip .big { font-weight:700; font-size:2em; line-height:1.1; font-variant-numeric: tabular-nums; margin-top:.2em; }
  .chip .sub { font-size:.85em; color:#a9a9ae; }
  .bar { height:.3em; border-radius:.2em; background:rgba(255,255,255,.12); margin-top:.5em; overflow:hidden; }
  .bar i { display:block; height:100%; width:0; background:linear-gradient(90deg,#ff7a1a,#ffb15c); transition: width 1s linear; }
  .hidden { display:none !important; }
  .hint { position:absolute; left:50%; bottom:3%; transform:translateX(-50%); font:500 12px/1 system-ui,sans-serif; color:rgba(255,255,255,.75);
          background:rgba(0,0,0,.45); padding:5px 10px; border-radius:10px; pointer-events:none; }
  .armed { animation: armed .5s infinite alternate; }
  .toast { position:absolute; left:50%; top:4%; transform:translateX(-50%); background:rgba(20,20,22,.9); color:#fff; border-radius:10px;
           padding:7px 12px; font:500 13px/1.2 system-ui,sans-serif; opacity:0; transition:opacity .25s; pointer-events:none; white-space:nowrap; z-index:5; }
  .toast.show { opacity:1; }
  /* popup */
  .pop { position:fixed; inset:0; z-index:9999; background:rgba(0,0,0,.72); display:flex; align-items:center; justify-content:center; padding:12px; box-sizing:border-box; }
  .sheet { position:relative; width:min(1000px, 100%); max-height:100%; overflow:auto; background:#141416; border-radius:18px; padding:12px; box-sizing:border-box;
           box-shadow:0 20px 60px rgba(0,0,0,.6); }
  .zoom { position:relative; width:100%; aspect-ratio:560/185; overflow:hidden; border-radius:12px; }
  .zoom .wrap { position:absolute; width:193.04%; left:-48.2%; top:-56.4%; }
  .chips { display:grid; grid-template-columns:1fr 1fr; gap:10px; margin-top:12px; }
  .chips.one { grid-template-columns:1fr; }
  .chips .chip { font-size:15px; }
  .x { position:absolute; right:10px; top:10px; z-index:6; width:34px; height:34px; border-radius:50%; border:none; background:rgba(255,255,255,.12);
       color:#fff; font:600 18px/34px system-ui; cursor:pointer; }
  .planbtn { position:absolute; left:50%; top:58.5%; transform:translate(-50%,-50%); cursor:pointer; white-space:nowrap;
             font:600 1.35cqw/1 system-ui,-apple-system,sans-serif; color:#e8e8ea; background:rgba(20,20,22,.55);
             border:.12cqw solid rgba(255,255,255,.18); border-radius:3cqw; padding:.8cqw 1.6cqw; backdrop-filter:blur(6px); -webkit-backdrop-filter:blur(6px); }
  .planbtn.on { color:#1d1d1f; background:#ff9a3c; border-color:#ff9a3c; box-shadow:0 0 1.4cqw rgba(255,140,40,.7); }
  .sheet .planbtn { position:static; transform:none; display:block; width:100%; margin-top:10px; font-size:15px; padding:12px; border-radius:12px; text-align:center; box-sizing:border-box; }
  .plan { color:#f1f1f3; font:500 15px/1.4 system-ui,-apple-system,sans-serif; }
  .plan h2 { margin:0 44px 12px 0; font-size:20px; }
  .seg2 { display:flex; background:rgba(255,255,255,.08); border-radius:10px; padding:3px; margin-bottom:12px; }
  .seg2 button { flex:1; border:none; background:none; color:#d8d8dc; font:600 15px system-ui; padding:9px; border-radius:8px; cursor:pointer; }
  .seg2 button.on { background:#ff9a3c; color:#1d1d1f; }
  .plan input { width:100%; box-sizing:border-box; font:600 20px system-ui; padding:10px 12px; border-radius:10px; border:1px solid rgba(255,255,255,.2);
                background:#1f1f22; color:#fff; color-scheme:dark; }
  .plan .res { margin:10px 0; color:#ffb36b; font-weight:600; }
  .plan .will { background:rgba(255,255,255,.05); border-radius:10px; padding:10px 12px; font-size:14px; color:#c9c9ce; }
  .plan .will b { color:#f1f1f3; }
  .plan .muted { color:#8e8e93; font-size:13px; margin-top:6px; }
  .plan .row { display:flex; gap:10px; margin-top:14px; }
  .plan .row button { flex:1; border:none; border-radius:12px; padding:13px; font:700 16px system-ui; cursor:pointer; }
  .plan .go { background:#ff9a3c; color:#1d1d1f; }
  .plan .del { background:rgba(255,80,60,.18); color:#ff8a7a; }
  @keyframes pulse { 0%,100% { opacity:1 } 50% { opacity:.3 } }
  @keyframes glow { 0%,100% { box-shadow:0 0 .4cqw rgba(255,140,40,.4) } 50% { box-shadow:0 0 1.4cqw rgba(255,140,40,.95) } }
  @keyframes armed { from { box-shadow:0 0 .4cqw rgba(255,80,60,.5) } to { box-shadow:0 0 1.8cqw rgba(255,80,60,1) } }
`;

/* touch icons printed on the TwinFry glass, drawn for the other models */
const ICONS = (z) => `
  <svg class="ico" style="${z(34.9, 21.1)};width:2.2cqw" viewBox="0 0 20 30"><path d="M3 9 l7 -6 l7 6 M3 21 l7 6 l7 -6"/></svg>
  <svg class="ico" style="${z(66.3, 21.1)};width:2.2cqw" viewBox="0 0 20 30"><path d="M3 9 l7 -6 l7 6 M3 21 l7 6 l7 -6"/></svg>
  <svg class="ico pw" style="${z(30.1, 25.6)};width:2.6cqw" viewBox="0 0 28 28"><circle cx="14" cy="14" r="12"/><path d="M14 8 V14 M9 10 A7 7 0 1 0 19 10"/></svg>
  <svg class="ico" style="${z(71.2, 25.6)};width:2.8cqw" viewBox="0 0 28 28"><circle cx="14" cy="14" r="12.5"/><path class="f" d="M8.5 8 L15 14 L8.5 20 Z M17 8 H19 V20 H17 Z M20.5 8 H22.5 V20 H20.5 Z"/></svg>`;

/* transform that moves the TwinFry panel layout onto the glass area of a skin */
function panelGeom(skin, dual) {
  const ref = dual ? REF.two : REF.one;
  const [px, py, pw, ph] = skin.panel;
  if (skin.exact) return { s: 1, tx: 0, ty: 0, ref, rect: ref };
  const s = Math.min(pw / ref[2], ph / ref[3]);
  const cx = px + pw / 2, cy = py + ph / 2;
  const tx = cx - s * (ref[0] + ref[2] / 2), ty = cy - s * (ref[1] + ref[3] / 2);
  return { s, tx, ty, ref, rect: [tx + s * ref[0], ty + s * ref[1], s * ref[2], s * ref[3]] };
}

function panelHTML(withChips, skin, caps, image) {
  const z = (x, y) => `left:${x}%;top:${y}%`;
  const g = panelGeom(skin, caps.dual);
  const tf = g.s === 1 && !g.tx && !g.ty ? "" : `transform:translate(${g.tx}%,${g.ty}%) scale(${g.s})`;
  const src = image || `${BASE}models/${skin.id}.svg${VER}`;
  const cw = `width:${skin.chipW}%`;
  const [c1, c2] = caps.dual ? skin.chips : [skin.one, skin.chips[1]];
  return `
    <div class="wrap${image ? " photo" : ""}">
      <img src="${src}" alt="${skin.name}">
      <div class="panel" style="${tf}">
      <div class="disp" data-act="disp"><span class="tag" data-k="tag"></span>
        <span class="seg" data-k="temp"></span><span class="seg" data-k="time"></span></div>
      <div class="o arr" style="${z(34.9, 19.3)}" data-act="temp+"></div>
      <div class="o arr" style="${z(34.9, 22.9)}" data-act="temp-"></div>
      <div class="o arr" style="${z(66.3, 19.3)}" data-act="time+"></div>
      <div class="o arr" style="${z(66.3, 22.9)}" data-act="time-"></div>
      ${skin.exact && !image ? "" : ICONS(z)}
      <div class="o btn" data-k="power" style="${z(30.1, 25.6)}" data-act="power"></div>
      <div class="o btn" data-k="play" style="${z(71.2, 25.6)}" data-act="play"></div>
      <div class="o pill filled${caps.dual ? "" : " hidden"}" data-k="p-sync" style="${z(43.9, 25.7)}" data-act="link:sync"></div>
      <div class="o pill filled${caps.dual ? "" : " hidden"}" data-k="p-match" style="${z(57.4, 25.7)}" data-act="link:match"></div>
      ${MODES.map((m, i) => `<div class="o lbl" data-k="m-${m}" style="${z(MODE_X[i], 29.2)}" data-act="mode:${m}"></div>`).join("")}
      <div class="o pill${caps.dual ? "" : " hidden"}" data-k="p-chamber_1" style="${z(30.5, 32.9)}" data-act="zone:chamber_1"></div>
      <div class="o pill${caps.dual && caps.whole ? "" : " hidden"}" data-k="p-whole" style="${z(50.8, 32.9)}" data-act="zone:whole"></div>
      <div class="o pill${caps.dual ? "" : " hidden"}" data-k="p-chamber_2" style="${z(70.9, 32.9)}" data-act="zone:chamber_2"></div>
      </div>
      ${withChips ? `<div class="chip" data-k="c1" style="${z(c1[0], c1[1])};${cw}" data-x="${c1[0]}" data-act="info:1"></div>
      <div class="chip${caps.dual ? "" : " hidden"}" data-k="c2" style="${z(c2[0], c2[1])};${cw}" data-act="info:2"></div>
      <div class="hint hidden" data-k="hint"></div>
      <div class="planbtn" data-k="planbtn" style="${z(skin.plan[0], skin.plan[1])}" data-act="plan"></div>` : ""}
    </div>`;
}

/* popup crop around the control panel: the TwinFry crop, moved like the panel */
function zoomGeom(skin, dual) {
  const g = panelGeom(skin, dual);
  const base = [24.97, 13.01, 51.8, 23.07]; // x, y, w, h in % of the drawing (TwinFry)
  const pad = dual ? 0 : 0.6;
  const x = g.tx + g.s * base[0], y = g.ty + g.s * (base[1] - pad), w = g.s * base[2], h = g.s * (base[3] - (dual ? 0 : 3.2));
  const aspect = (w * 1081) / (h * 802);
  return { width: 10000 / w, left: (-x / w) * 100, top: (-y / h) * 100, aspect };
}

class CosoriAirfryerCard extends HTMLElement {
  setConfig(config) {
    const old = JSON.stringify(this._config || {});
    this._config = config || {};
    this._armed = null;
    if (!this.shadowRoot) this.attachShadow({ mode: "open" });
    if (this._built && old !== JSON.stringify(this._config)) {
      this._built = false;
      this._dev = null;
      if (this._hass) this.hass = this._hass;
    }
  }

  static getConfigElement() {
    return document.createElement("cosori-airfryer-card-editor");
  }

  static getStubConfig() {
    return {};
  }

  getCardSize() {
    return 6;
  }

  getGridOptions() {
    return { columns: "full", rows: "auto", min_columns: 6 };
  }

  set hass(hass) {
    this._hass = hass;
    const skin = this._skinId;
    this._resolve();
    if (this._built && (skin !== this._skinId || this._capsKey !== JSON.stringify(this._caps))) {
      this._ro?.disconnect();
      this._built = false;
    }
    if (!this._built) this._build();
    this._render();
  }

  connectedCallback() {
    this._tick = setInterval(() => this._built && this._render(), 1000);
    if (this._ro && this._card) this._ro.observe(this._card);
  }

  disconnectedCallback() {
    clearInterval(this._tick);
    this._ro?.disconnect();
    this._closePopup();
  }

  get _t() {
    const lang = (this._hass?.locale?.language || this._hass?.language || "en").slice(0, 2);
    return T[lang] || T.en;
  }

  /* map translation_key -> entity_id for one fryer device */
  _resolve() {
    const ents = Object.values(this._hass.entities || {}).filter((e) => e.platform === "cosori_airfryer");
    if (!ents.length) {
      this._e = null;
      return;
    }
    const dev = this._config.device_id || ents[0].device_id;
    if (this._dev === dev && this._e) return;
    this._dev = dev;
    this._e = {};
    for (const e of ents) if (e.device_id === dev && e.translation_key) this._e[e.translation_key] = e.entity_id;
    const modelId = this._hass.devices?.[dev]?.model_id || "";
    this._skinId = skinFor(this._config.model, modelId, !!this._e.status_chamber_2);
  }

  get _skin() {
    return { id: this._skinId || "twinfry", ...SKINS[this._skinId || "twinfry"] };
  }

  get _caps() {
    const opts = this._st("chamber")?.attributes?.options || [];
    return { dual: !!this._e?.status_chamber_2, whole: opts.includes("whole") };
  }

  _st(key) {
    const id = this._e?.[key];
    return id ? this._hass.states[id] : undefined;
  }

  _val(key) {
    return this._st(key)?.state;
  }

  _call(domain, service, key, data = {}) {
    const id = this._e?.[key];
    if (!id) return;
    this._hass.callService(domain, service, { entity_id: id, ...data });
  }

  _moreInfo(key) {
    const id = this._e?.[key];
    if (!id) return;
    this._closePopup();
    this.dispatchEvent(new CustomEvent("hass-more-info", { detail: { entityId: id }, bubbles: true, composed: true }));
  }

  _bindClicks(root, fromPopup) {
    root.addEventListener("click", (ev) => {
      const path = ev.composedPath();
      if (!fromPopup && this._compact) {
        if (path.some((n) => n.classList?.contains("wrap"))) this._openPopup();
        return;
      }
      const el = path.find((n) => n.dataset && n.dataset.act);
      if (el) this._act(el.dataset.act);
    });
  }

  _build() {
    this._built = true;
    this._capsKey = JSON.stringify(this._caps);
    this.shadowRoot.innerHTML = `<style>${CSS}</style><ha-card><div class="host">${panelHTML(true, this._skin, this._caps, this._config.image)}<div class="toast"></div></div></ha-card>`;
    this._compact = undefined;
    this._card = this.shadowRoot.querySelector(".host");
    this._bindClicks(this._card, false);
    this._ro = new ResizeObserver(() => {
      const compact = this._card.clientWidth < COMPACT_BELOW;
      if (compact !== this._compact) {
        this._compact = compact;
        this._card.classList.toggle("compact", compact);
        this._render();
      }
    });
    this._ro.observe(this._card);
  }

  _openPopup() {
    if (this._pop) return;
    const host = document.createElement("div");
    host.className = "cosori-airfryer-popup";
    const sr = host.attachShadow({ mode: "open" });
    const zg = zoomGeom(this._skin, this._caps.dual);
    sr.innerHTML = `<style>${CSS}</style>
      <div class="pop"><div class="sheet">
        <button class="x" title="${this._t.close}">✕</button>
        <div class="zoom" style="aspect-ratio:${zg.aspect}">${panelHTML(false, this._skin, this._caps, this._config.image).replace('<div class="wrap', `<div style="width:${zg.width}%;left:${zg.left}%;top:${zg.top}%" class="wrap`)}</div>
        <div class="chips"><div class="chip" data-k="c1" data-act="info:1"></div><div class="chip${this._caps.dual ? "" : " hidden"}" data-k="c2" data-act="info:2"></div></div>
        <div class="planbtn" data-k="planbtn" data-act="plan"></div>
        <div class="toast"></div>
      </div></div>`;
    sr.querySelector(".pop").addEventListener("click", (ev) => {
      if (ev.target.classList.contains("pop")) this._closePopup();
    });
    sr.querySelector(".x").addEventListener("click", () => this._closePopup());
    this._bindClicks(sr.querySelector(".sheet"), true);
    this._escHandler = (ev) => ev.key === "Escape" && this._closePopup();
    window.addEventListener("keydown", this._escHandler);
    document.body.appendChild(host);
    this._pop = host;
    this._render();
  }

  _closePopup() {
    if (!this._pop) return;
    this._pop.remove();
    this._pop = null;
    window.removeEventListener("keydown", this._escHandler);
  }

  _roots() {
    const r = [this._card];
    if (this._pop) r.push(this._pop.shadowRoot.querySelector(".sheet"));
    return r.filter((x) => x && x.querySelector(".wrap"));
  }

  _toast(msg) {
    for (const r of this._roots()) {
      const t = r.querySelector(".toast");
      if (!t) continue;
      t.textContent = msg;
      t.classList.add("show");
    }
    clearTimeout(this._toastT);
    this._toastT = setTimeout(() => this._roots().forEach((r) => r.querySelector(".toast")?.classList.remove("show")), 2200);
  }

  _arm(id, msg, fn) {
    if (this._armed === id) {
      this._armed = null;
      clearTimeout(this._armT);
      fn();
      this._render();
      return;
    }
    this._armed = id;
    this._toast(msg);
    clearTimeout(this._armT);
    this._armT = setTimeout(() => {
      this._armed = null;
      this._render();
    }, 3500);
    this._render();
  }

  _link() {
    if (this._val("sync") === "on") return "sync";
    if (this._val("match") === "on") return "match";
    return "off";
  }

  _cfg(n) {
    const a = this._st("start")?.attributes || {};
    return this._link() === "match" ? a.chamber_1 : a[`chamber_${n}`];
  }

  _when(iso) {
    if (!iso) return "";
    const d = new Date(iso);
    const t = this._t;
    const now = new Date();
    const day0 = (x) => new Date(x.getFullYear(), x.getMonth(), x.getDate()).getTime();
    const diff = Math.round((day0(d) - day0(now)) / 86400000);
    const hm = d.toLocaleTimeString(this._hass.locale?.language || "de", { hour: "2-digit", minute: "2-digit" });
    const day = diff === 0 ? t.today : diff === 1 ? t.tomorrow : `${t.days[d.getDay()]} ${d.getDate()}.${d.getMonth() + 1}.`;
    return `${day} ${hm}`;
  }

  _localInput(d) {
    const p = (n) => String(n).padStart(2, "0");
    return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())}T${p(d.getHours())}:${p(d.getMinutes())}`;
  }

  _describe(a) {
    const t = this._t;
    if (!a) return "";
    const line = (n, c) => c ? `<b>${n}</b>: ${t.modesLong[c.mode] || c.mode} · ${c.temperature}°C · ${c.duration} min` : "";
    if (a.chamber === "whole") return line(t.whole2, a.chamber_1);
    if (a.link === "match") return `${line(`${t.basket} 1 + 2`, a.chamber_1)} <span class="muted">(${t.match})</span>`;
    if (a.link === "sync") return `${line(`${t.basket} 1`, a.chamber_1)}<br>${line(`${t.basket} 2`, a.chamber_2)} <span class="muted">(${t.sync})</span>`;
    const n = a.chamber === "chamber_2" ? 2 : 1;
    return line(`${t.basket} ${n}`, a[`chamber_${n}`]);
  }

  _minutes(a) {
    if (!a) return 0;
    if (a.chamber === "whole" || a.link === "match") return a.chamber_1?.duration || 0;
    if (a.link === "sync") return Math.max(a.chamber_1?.duration || 0, a.chamber_2?.duration || 0);
    return a[a.chamber === "chamber_2" ? "chamber_2" : "chamber_1"]?.duration || 0;
  }

  _openPlan() {
    const t = this._t;
    this._closePopup();
    const armed = this._val("plan") === "on";
    const planAttrs = this._st("plan")?.attributes || {};
    const cur = this._st("start")?.attributes || {};
    let type = this._val("plan_type") || "start";
    const stored = this._val("plan_time");
    let when = stored && !["unknown", "unavailable"].includes(stored) ? new Date(stored) : null;
    if (!when || (!armed && when < new Date())) {
      when = new Date();
      when.setHours(9, 0, 0, 0);
      if (when <= new Date()) when.setDate(when.getDate() + 1);
    }
    const host = document.createElement("div");
    host.className = "cosori-airfryer-popup";
    const sr = host.attachShadow({ mode: "open" });
    sr.innerHTML = `<style>${CSS}</style>
      <div class="pop"><div class="sheet plan" style="width:min(460px,100%)">
        <button class="x" title="${t.close}">✕</button>
        <h2>⏰ ${t.planTitle}</h2>
        <div class="seg2"><button data-type="start">${t.planStartAt}</button><button data-type="finish">${t.planFinishAt}</button></div>
        <input type="datetime-local" step="300">
        <div class="res"></div>
        <div class="will"><div>${armed ? t.planArmed : t.planWill}:</div><div class="desc"></div></div>
        ${armed ? "" : `<div class="muted">${t.planHint}</div>`}
        <div class="row">${armed ? `<button class="del">${t.planCancel}</button>` : ""}<button class="go">${t.planDo}</button></div>
        <div class="toast"></div>
      </div></div>`;
    const inp = sr.querySelector("input");
    inp.value = this._localInput(when);
    const attrs = armed ? planAttrs : cur;
    sr.querySelector(".desc").innerHTML = this._describe(attrs);
    const upd = () => {
      sr.querySelectorAll(".seg2 button").forEach((b) => b.classList.toggle("on", b.dataset.type === type));
      const at = new Date(inp.value);
      const mins = this._minutes(attrs);
      if (isNaN(at)) return;
      const start = type === "finish" ? new Date(at.getTime() - mins * 60000) : at;
      const end = new Date(start.getTime() + mins * 60000);
      sr.querySelector(".res").textContent = `${t.planStarts} ${this._when(start.toISOString())} · ${t.planFinishes} ${this._when(end.toISOString()).split(" ").pop()}`;
    };
    sr.querySelectorAll(".seg2 button").forEach((b) => b.addEventListener("click", () => { type = b.dataset.type; upd(); }));
    inp.addEventListener("input", upd);
    upd();
    const toast = (msg) => {
      const el = sr.querySelector(".toast");
      el.textContent = msg;
      el.classList.add("show");
      setTimeout(() => el.classList.remove("show"), 3500);
    };
    const call = (d, s, key, data = {}) => this._hass.callService(d, s, { entity_id: this._e[key], ...data });
    sr.querySelector(".go").addEventListener("click", async () => {
      try {
        const v = inp.value.replace("T", " ") + ":00";
        if (armed) await call("switch", "turn_off", "plan");
        await call("select", "select_option", "plan_type", { option: type });
        await call("datetime", "set_value", "plan_time", { datetime: v });
        await call("switch", "turn_on", "plan");
        this._closePopup();
      } catch (err) {
        toast(err?.message || String(err));
      }
    });
    sr.querySelector(".del")?.addEventListener("click", async () => {
      await call("switch", "turn_off", "plan");
      this._closePopup();
    });
    sr.querySelector(".pop").addEventListener("click", (ev) => ev.target.classList.contains("pop") && this._closePopup());
    sr.querySelector(".x").addEventListener("click", () => this._closePopup());
    this._escHandler = (ev) => ev.key === "Escape" && this._closePopup();
    window.addEventListener("keydown", this._escHandler);
    document.body.appendChild(host);
    this._pop = host;
  }

  _chState(n) {
    return this._val(`status_chamber_${n}`) || "standby";
  }

  _isActive(n) {
    const st = this._chState(n);
    if (!ACTIVE.includes(st)) return false;
    // One drawer for both baskets: "basket out" also shows for a basket that
    // is not cooking. Only count it with time left.
    if (st === "pull_out") {
      const r = this._remaining(n);
      return r != null && r > 0;
    }
    return true;
  }

  /* chamber whose values the display shows */
  _focus() {
    const sel = this._val("chamber") || "chamber_1";
    const a1 = this._isActive(1), a2 = this._isActive(2);
    if (sel === "chamber_2" && a2) return 2;
    if (sel !== "chamber_2" && a1) return 1;
    if (a1) return 1;
    if (a2) return 2;
    return 0;
  }

  _remaining(n) {
    const fin = this._val(`finish_chamber_${n}`);
    if (fin && fin !== "unknown" && fin !== "unavailable" && RUNNING.includes(this._chState(n))) {
      return Math.max(0, Math.round((new Date(fin) - Date.now()) / 1000));
    }
    const r = this._st(`remaining_chamber_${n}`);
    if (!r || isNaN(parseFloat(r.state))) return null;
    const unit = r.attributes.unit_of_measurement;
    const v = parseFloat(r.state);
    return Math.round(unit === "min" ? v * 60 : unit === "h" ? v * 3600 : v);
  }

  _fmt(sec) {
    if (sec == null) return "--:--";
    const h = Math.floor(sec / 3600), m = Math.floor((sec % 3600) / 60), s = sec % 60;
    return h ? `${h}:${String(m).padStart(2, "0")}:${String(s).padStart(2, "0")}` : `${String(m).padStart(2, "0")}:${String(s).padStart(2, "0")}`;
  }

  _act(act) {
    const t = this._t;
    if (!this._e) return;
    const busy = this._isActive(1) || this._isActive(2);
    const [kind, arg] = act.split(":");
    if (kind === "info") return this._moreInfo(`status_chamber_${arg}`);
    if (kind === "disp") return;
    if (kind === "plan") return this._openPlan();
    if (kind === "zone") return this._call("select", "select_option", "chamber", { option: arg });
    if (kind === "link") {
      if (!this._e[arg]) return;
      if ((this._val("chamber") || "chamber_1") === "whole" && this._val(arg) !== "on") return this._toast(t.noLinkWhole);
      return this._call("switch", this._val(arg) === "on" ? "turn_off" : "turn_on", arg);
    }
    if (kind === "mode") return this._call("select", "select_option", "mode", { option: arg });
    if (kind.startsWith("temp") || kind.startsWith("time")) {
      const key = kind.startsWith("temp") ? "temperature" : "duration";
      const st = this._st(key);
      if (!st) return;
      const step = Number(st.attributes.step || 1), min = Number(st.attributes.min), max = Number(st.attributes.max);
      let v = Number(st.state) + (kind.endsWith("+") ? step : -step);
      v = Math.min(max, Math.max(min, v));
      return this._call("number", "set_value", key, { value: v });
    }
    if (kind === "play") {
      const sel = this._val("chamber") || "chamber_1";
      const target = sel === "chamber_2" ? 2 : 1;
      const all = sel === "whole" || this._link() !== "off" || this._val("work_chamber") === "both";
      const runningSel = all ? busy : this._isActive(target);
      if (runningSel) {
        const endKey = all ? "end_both" : `end_chamber_${target}`;
        return this._arm("play", t.confirmEnd, () => this._call("button", "press", endKey));
      }
      return this._arm("play", t.confirmStart, () => this._call("button", "press", "start"));
    }
    if (kind === "power") {
      if (!busy) return this._moreInfo("online");
      return this._arm("power", t.confirmAll, () => this._call("button", "press", "end_both"));
    }
  }

  _render() {
    if (!this._hass || !this._card) return;
    for (const root of this._roots()) this._renderRoot(root);
  }

  _renderRoot(root) {
    const t = this._t;
    const q = (k) => root.querySelector(`[data-k="${k}"]`);
    const wrap = root.querySelector(".wrap");
    if (!this._e) {
      wrap.classList.add("off");
      return;
    }
    const online = this._val("online") === "on";
    wrap.classList.toggle("off", !online);

    const sel = this._val("chamber") || "chamber_1";
    const mode = this._val("mode") || "airfry";
    const focus = this._focus();
    const busy = this._isActive(1) || this._isActive(2);
    const work = this._val("work_chamber");

    // display
    const tag = q("tag");
    if (!online) {
      q("temp").textContent = "OFF";
      q("time").textContent = "";
      tag.textContent = t.offline;
    } else if (focus) {
      const temp = this._val(`set_temperature_chamber_${focus}`);
      q("temp").innerHTML = `${temp && !isNaN(temp) ? Math.round(temp) : "---"}<small>°C</small>`;
      q("time").textContent = this._fmt(this._remaining(focus));
      const zoneLbl = !this._caps.dual ? "" : work === "whole" ? t.whole : work === "both" ? (this._link() === "match" ? t.match : t.sync) : focus === 1 ? t.zone1 : t.zone2;
      const run = RUNNING.includes(this._chState(focus));
      tag.innerHTML = `${run ? '<span class="dot"></span>' : ""}${zoneLbl ? zoneLbl + " · " : ""}${t.status[this._chState(focus)] || ""}`;
    } else {
      const temp = this._val("temperature");
      const dur = Number(this._val("duration"));
      q("temp").innerHTML = `${temp && !isNaN(temp) ? Math.round(temp) : "---"}<small>°C</small>`;
      q("time").textContent = isNaN(dur) ? "--:--" : dur >= 60 ? `${Math.floor(dur / 60)}:${String(dur % 60).padStart(2, "0")}:00` : `${String(dur).padStart(2, "0")}:00`;
      const lk = this._link();
      tag.textContent = !this._caps.dual ? "" : sel === "whole" ? t.whole : lk === "match" ? `${t.zone1} + ${t.zone2} · ${t.match}`
        : `${sel === "chamber_2" ? t.zone2 : t.zone1}${lk === "sync" ? " · " + t.sync : ""}`;
    }

    const curMode = focus ? this._val(`mode_chamber_${focus}`) : mode;
    MODES.forEach((m) => {
      const el = q(`m-${m}`);
      el.textContent = t.modes[m];
      el.classList.toggle("sel", m === curMode);
    });

    const link = this._link();
    const zoneRun = {
      chamber_1: RUNNING.includes(this._chState(1)) && work !== "whole",
      chamber_2: RUNNING.includes(this._chState(2)),
      whole: work === "whole" && busy,
    };
    for (const [z, label] of [["chamber_1", t.zone1], ["chamber_2", t.zone2], ["whole", t.whole]]) {
      const el = q(`p-${z}`);
      el.textContent = label;
      el.classList.toggle("sel", z === sel || (link === "match" && z !== "whole"));
      el.classList.toggle("run", !!zoneRun[z]);
    }
    for (const [k, label] of [["sync", t.sync], ["match", t.match]]) {
      const el = q(`p-${k}`);
      el.textContent = label;
      el.classList.toggle("sel", link === k);
      el.classList.toggle("dim", sel === "whole" || !this._e[k]);
      el.classList.toggle("run", link === k && busy);
    }
    q("play").classList.toggle("on", busy);
    q("play").classList.toggle("armed", this._armed === "play");
    q("power").classList.toggle("armed", this._armed === "power");

    const planOn = this._val("plan") === "on";
    const pb = q("planbtn");
    if (pb) {
      pb.classList.toggle("on", planOn);
      pb.textContent = planOn ? `⏰ ${t.planStarts} ${this._when(this._st("plan")?.attributes.start_time)}` : `⏰ ${t.plan}`;
      pb.classList.toggle("hidden", !this._e.plan);
    }
    if (planOn && !busy && online) tag.textContent = `⏰ ${this._when(this._st("plan")?.attributes.start_time)}`;
    const hint = q("hint");
    if (hint) {
      hint.textContent = t.hint;
      hint.classList.toggle("hidden", !this._compact);
    }

    // basket tiles
    const inWrap = !!q("c1")?.closest(".wrap");
    const wholeBusy = work === "whole" && busy;
    for (const n of [1, 2]) {
      const c = q(`c${n}`);
      if (!c) continue;
      const st = this._chState(n);
      const act = this._isActive(n);
      if (n === 2 && (wholeBusy || !this._caps.dual)) {
        c.classList.add("hidden");
        continue;
      }
      c.classList.remove("hidden");
      c.classList.toggle("act", act);
      if (inWrap && n === 1) c.style.left = `${wholeBusy ? this._skin.one[0] : c.dataset.x}%`;
      const title = n === 1 && wholeBusy ? t.whole : this._caps.dual ? `${t.basket} ${n}` : t.basket;
      if (!act) {
        const cfg = this._cfg(n);
        const lk = this._link();
        const willRun = sel === "whole" ? n === 1 : lk !== "off" || sel === `chamber_${n}`;
        const set = cfg && willRun
          ? `<div class="sub">${t.modesLong[cfg.mode] || ""} · ${cfg.temperature}°C · ${cfg.duration} min</div>` : "";
        c.innerHTML = `<div class="h"><span>${sel === "whole" && n === 1 ? t.whole : title}</span><span class="s">${t.status[st] || st}</span></div>${set}`;
        c.style.opacity = willRun || !cfg ? "1" : ".55";
        if (inWrap && n === 1) c.style.left = `${sel === "whole" ? this._skin.one[0] : c.dataset.x}%`;
        if (n === 2) c.classList.toggle("hidden", sel === "whole" || !this._caps.dual);
        continue;
      }
      c.style.opacity = "1";
      const rem = this._remaining(n);
      const setSt = this._st(`set_time_chamber_${n}`);
      const setT = Number(setSt?.state);
      const setSec = isNaN(setT) ? null : Math.round(setSt.attributes.unit_of_measurement === "min" ? setT * 60 : setT);
      const pct = rem != null && setSec ? Math.min(100, Math.max(0, 100 - (rem / setSec) * 100)) : 0;
      const fin = this._val(`finish_chamber_${n}`);
      const finTxt = fin && !["unknown", "unavailable"].includes(fin)
        ? new Date(fin).toLocaleTimeString(this._hass.locale?.language || "de", { hour: "2-digit", minute: "2-digit" }) : "";
      const m = this._val(`mode_chamber_${n}`);
      const temp = this._val(`set_temperature_chamber_${n}`);
      c.innerHTML = `
        <div class="h"><span>${title}</span><span class="s">${RUNNING.includes(st) ? '<span class="dot"></span>' : ""}${t.status[st] || st}</span></div>
        <div class="big">${this._fmt(rem)}</div>
        <div class="sub">${t.modesLong[m] || ""}${temp && !isNaN(temp) ? " · " + Math.round(temp) + "°C" : ""}${finTxt ? " · " + t.done + " " + finTxt : ""}</div>
        <div class="bar"><i style="width:${pct}%"></i></div>`;
    }
    const chips = root.querySelector(".chips");
    if (chips) chips.classList.toggle("one", !this._caps.dual || wholeBusy || (!busy && sel === "whole"));
  }
}

/* visual editor: fryer, model drawing, optional own photo */
class CosoriAirfryerCardEditor extends HTMLElement {
  setConfig(config) {
    this._config = { ...(config || {}) };
    this._draw();
  }

  set hass(hass) {
    this._hass = hass;
    this._draw();
  }

  get _de() {
    return (this._hass?.locale?.language || this._hass?.language || "en").startsWith("de");
  }

  _draw() {
    if (!this._hass || !this._config) return;
    const de = this._de;
    if (!this._form) {
      this._form = document.createElement("ha-form");
      this._form.computeLabel = (s) => ({
        device_id: de ? "Fritteuse" : "Air fryer",
        model: de ? "Modell (Bild)" : "Model (drawing)",
        image: de ? "Eigenes Bild (URL, optional)" : "Own picture (URL, optional)",
      })[s.name];
      this._form.computeHelper = (s) => s.name === "model"
        ? (de ? "Automatisch: wird aus dem VeSync-Modell erkannt." : "Automatic: detected from the VeSync model.")
        : s.name === "image" ? (de ? "Frontansicht im Format 4:3, z. B. /local/fritteuse.jpg" : "Front view, 4:3, e.g. /local/fryer.jpg") : undefined;
      this._form.addEventListener("value-changed", (ev) => {
        const cfg = { ...this._config, ...ev.detail.value };
        for (const k of ["device_id", "model", "image"]) if (!cfg[k] || cfg[k] === "auto") delete cfg[k];
        this._config = cfg;
        this.dispatchEvent(new CustomEvent("config-changed", { detail: { config: cfg }, bubbles: true, composed: true }));
      });
      this.appendChild(this._form);
    }
    const options = [{ value: "auto", label: de ? "Automatisch" : "Automatic" },
      ...Object.entries(SKINS).map(([id, sk]) => ({ value: id, label: sk.name }))];
    this._form.hass = this._hass;
    this._form.schema = [
      { name: "device_id", selector: { device: { integration: "cosori_airfryer" } } },
      { name: "model", selector: { select: { mode: "dropdown", options } } },
      { name: "image", selector: { text: {} } },
    ];
    this._form.data = { model: "auto", ...this._config };
  }
}

if (!customElements.get("cosori-airfryer-card-editor")) {
  customElements.define("cosori-airfryer-card-editor", CosoriAirfryerCardEditor);
}

if (!customElements.get("cosori-airfryer-card")) {
  customElements.define("cosori-airfryer-card", CosoriAirfryerCard);
  window.customCards = window.customCards || [];
  window.customCards.push({
    type: "cosori-airfryer-card",
    name: "Cosori Airfryer",
    description: "Cosori air fryer with a live control panel (TwinFry, Turbo Tower, Dual Blaze, TurboBlaze, Smart/Pro)",
    preview: true,
  });
}
