/*
 * Cosori Airfryer Card – the fryer photo with a live, touchable control panel.
 * Shipped and registered by the cosori_airfryer integration.
 *
 *   type: custom:cosori-airfryer-card
 *   device_id: <optional, first Cosori fryer if omitted>
 *   name: <optional>
 */
const BASE = new URL(".", import.meta.url).pathname; // /cosori_airfryer/

const T = {
  de: {
    modes: { airfry: "HEISSLUFT", roast: "BRATEN", bake: "BACKEN", grill: "GRILLEN", reheat: "WÄRMEN", dry: "TROCKNEN" },
    zone1: "KORB 1", zone2: "KORB 2", whole: "GANZER KORB", sync: "SYNC", match: "MATCH",
    status: {
      standby: "Bereit", cooking: "Gart", cook_stop: "Pausiert", cook_end: "Fertig", pull_out: "Korb raus",
      heating: "Heizt vor", hold: "Wartet", ready: "Wartet auf Start", preheat_end: "Vorgeheizt",
      preheat_stop: "Pausiert", appointing: "Geplant", completed: "Fertig", unknown: "–",
    },
    basket: "Korb", done: "fertig", offline: "Offline", confirmStart: "Start?", confirmEnd: "Stopp?",
    confirmAll: "Alles aus?", locked: "Läuft – Einstellungen gesperrt",
  },
  en: {
    modes: { airfry: "AIR FRY", roast: "ROAST", bake: "BAKE", grill: "GRILL", reheat: "REHEAT", dry: "DRY" },
    zone1: "ZONE 1", zone2: "ZONE 2", whole: "GRANDZONE", sync: "SYNC", match: "MATCH",
    status: {
      standby: "Ready", cooking: "Cooking", cook_stop: "Paused", cook_end: "Done", pull_out: "Basket out",
      heating: "Preheating", hold: "Waiting", ready: "Waiting for start", preheat_end: "Preheated",
      preheat_stop: "Paused", appointing: "Scheduled", completed: "Done", unknown: "–",
    },
    basket: "Basket", done: "done", offline: "Offline", confirmStart: "Start?", confirmEnd: "Stop?",
    confirmAll: "All off?", locked: "Cooking – settings locked",
  },
};

const MODES = ["airfry", "roast", "bake", "grill", "reheat", "dry"];
const MODE_X = [35.3, 41.6, 47.8, 54.1, 60.2, 66.5];
const ACTIVE = ["cooking", "heating", "hold", "cook_stop", "pull_out", "ready", "preheat_end", "preheat_stop", "appointing"];
const RUNNING = ["cooking", "heating", "hold"];

class CosoriAirfryerCard extends HTMLElement {
  setConfig(config) {
    this._config = config || {};
    this._armed = null;
    if (!this.shadowRoot) this.attachShadow({ mode: "open" });
  }

  static getStubConfig() {
    return {};
  }

  getCardSize() {
    return 7;
  }

  getGridOptions() {
    return { columns: 12, rows: "auto", min_columns: 6 };
  }

  set hass(hass) {
    this._hass = hass;
    this._resolve();
    if (!this._built) this._build();
    this._render();
  }

  connectedCallback() {
    this._tick = setInterval(() => this._built && this._render(), 1000);
  }

  disconnectedCallback() {
    clearInterval(this._tick);
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
    this.dispatchEvent(new CustomEvent("hass-more-info", { detail: { entityId: id }, bubbles: true, composed: true }));
  }

  _build() {
    this._built = true;
    const z = (x, y) => `left:${x}%;top:${y}%`;
    this.shadowRoot.innerHTML = `
      <style>
        :host { display:block; }
        ha-card { overflow:hidden; background: var(--ha-card-background, var(--card-background-color)); }
        .wrap { position:relative; width:100%; aspect-ratio:1081/802; container-type:inline-size; user-select:none; -webkit-user-select:none; }
        .wrap img { position:absolute; inset:0; width:100%; height:100%; pointer-events:none; transition:filter .4s; }
        .wrap.off img { filter: grayscale(.7) brightness(.6); }
        .o { position:absolute; transform:translate(-50%,-50%); cursor:pointer; -webkit-tap-highlight-color:transparent; }
        .disp { position:absolute; left:37.9%; top:18.4%; width:25.9%; height:6%; display:flex; align-items:center; justify-content:space-between;
                padding:0 1.2cqw; box-sizing:border-box; cursor:pointer; }
        .seg { font-family: "DSEG7 Classic", "Share Tech Mono", "Consolas", "Courier New", monospace; font-weight:700; font-size:3.6cqw;
               color:#dfeaff; letter-spacing:.25cqw; text-shadow:0 0 .6cqw rgba(160,200,255,.85), 0 0 1.6cqw rgba(120,170,255,.35); line-height:1; }
        .seg small { font-size:2.2cqw; margin-left:.2cqw; }
        .tag { position:absolute; left:50%; top:-1.1cqw; transform:translateX(-50%); font:600 1.05cqw/1 system-ui,sans-serif; letter-spacing:.12cqw;
               color:#ff9a3c; text-shadow:0 0 .5cqw rgba(255,140,40,.7); white-space:nowrap; }
        .dot { display:inline-block; width:.7cqw; height:.7cqw; border-radius:50%; background:#ff9a3c; box-shadow:0 0 .7cqw #ff8a20; margin-right:.6cqw;
               animation: pulse 1.4s infinite; vertical-align:middle; }
        .arr { width:3.6cqw; height:2.6cqw; }
        .btn { width:4.4cqw; height:4.4cqw; border-radius:50%; }
        .btn.on { box-shadow:0 0 1.4cqw rgba(255,150,60,.9), inset 0 0 .8cqw rgba(255,150,60,.6); }
        .lbl { font:600 .98cqw/1 system-ui,-apple-system,sans-serif; letter-spacing:.02cqw; color:#e8e8ea; white-space:nowrap; padding:.6cqw .5cqw;
               transition: color .2s, text-shadow .2s; }
        .lbl.sel { color:#ff9a3c; text-shadow:0 0 .7cqw rgba(255,140,40,.8); }
        .lbl.dim { color:#6f6f73; }
        .pill { font:600 1.02cqw/1 system-ui,-apple-system,sans-serif; letter-spacing:.08cqw; color:#e8e8ea; border:.14cqw solid #cfcfd2;
                border-radius:2cqw; padding:.35cqw 1.1cqw; white-space:nowrap; transition: all .2s; }
        .pill.filled { background:#f2f2f2; color:#1d1d1f; border-color:#f2f2f2; }
        .pill.sel { color:#ff9a3c; border-color:#ff9a3c; box-shadow:0 0 .9cqw rgba(255,140,40,.6); }
        .pill.filled.sel { background:#ff9a3c; color:#1d1d1f; }
        .pill.run { animation: glow 1.6s infinite; }
        .pill.dim { opacity:.35; cursor:default; }
        .chip { position:absolute; transform:translate(-50%,-50%); top:50%; width:27%; padding:1.1cqw 1.4cqw; border-radius:1.6cqw;
                background:rgba(20,20,22,.62); backdrop-filter: blur(6px); -webkit-backdrop-filter: blur(6px); border:.12cqw solid rgba(255,255,255,.08);
                color:#f1f1f3; font: 500 1.55cqw/1.3 system-ui,-apple-system,sans-serif; cursor:pointer; box-sizing:border-box; }
        .chip .h { display:flex; justify-content:space-between; align-items:center; font-weight:700; letter-spacing:.06cqw; }
        .chip .s { color:#bdbdc2; font-size:1.4cqw; }
        .chip.act { border-color: rgba(255,154,60,.55); }
        .chip.act .s { color:#ffb36b; }
        .chip .big { font: 700 3.1cqw/1.1 system-ui,-apple-system,sans-serif; font-variant-numeric: tabular-nums; margin-top:.3cqw; }
        .chip .sub { font-size:1.3cqw; color:#a9a9ae; }
        .bar { height:.45cqw; border-radius:.3cqw; background:rgba(255,255,255,.12); margin-top:.7cqw; overflow:hidden; }
        .bar i { display:block; height:100%; width:0; background:linear-gradient(90deg,#ff7a1a,#ffb15c); transition: width 1s linear; }
        .toast { position:absolute; left:50%; top:9%; transform:translateX(-50%); background:rgba(20,20,22,.85); color:#fff; border-radius:1.4cqw;
                 padding:.8cqw 1.6cqw; font:500 1.5cqw/1.2 system-ui,sans-serif; opacity:0; transition:opacity .25s; pointer-events:none; white-space:nowrap; }
        .toast.show { opacity:1; }
        .armed { animation: armed .5s infinite alternate; }
        .hidden { display:none; }
        @keyframes pulse { 0%,100% { opacity:1 } 50% { opacity:.3 } }
        @keyframes glow { 0%,100% { box-shadow:0 0 .4cqw rgba(255,140,40,.4) } 50% { box-shadow:0 0 1.4cqw rgba(255,140,40,.95) } }
        @keyframes armed { from { box-shadow:0 0 .4cqw rgba(255,80,60,.5) } to { box-shadow:0 0 1.8cqw rgba(255,80,60,1) } }
      </style>
      <ha-card>
        <div class="wrap" id="wrap">
          <img src="${BASE}airfryer.webp" alt="Cosori TwinFry">
          <div class="disp" id="disp"><span class="tag" id="tag"></span>
            <span class="seg" id="temp"></span><span class="seg" id="time"></span></div>
          <div class="o arr" style="${z(34.9, 19.3)}" data-act="temp+"></div>
          <div class="o arr" style="${z(34.9, 22.9)}" data-act="temp-"></div>
          <div class="o arr" style="${z(66.3, 19.3)}" data-act="time+"></div>
          <div class="o arr" style="${z(66.3, 22.9)}" data-act="time-"></div>
          <div class="o btn" id="power" style="${z(30.1, 25.6)}" data-act="power"></div>
          <div class="o btn" id="play" style="${z(71.2, 25.6)}" data-act="play"></div>
          <div class="o pill filled" id="p-both" style="${z(43.9, 25.7)}" data-act="zone:both"></div>
          <div class="o pill filled dim" id="p-match" style="${z(57.4, 25.7)}"></div>
          ${MODES.map((m, i) => `<div class="o lbl" id="m-${m}" style="${z(MODE_X[i], 29.2)}" data-act="mode:${m}"></div>`).join("")}
          <div class="o pill" id="p-chamber_1" style="${z(30.5, 32.9)}" data-act="zone:chamber_1"></div>
          <div class="o pill" id="p-whole" style="${z(50.8, 32.9)}" data-act="zone:whole"></div>
          <div class="o pill" id="p-chamber_2" style="${z(70.9, 32.9)}" data-act="zone:chamber_2"></div>
          <div class="chip" id="c1" style="left:21.5%;top:50.5%" data-act="info:1"></div>
          <div class="chip" id="c2" style="left:78.5%;top:50.5%" data-act="info:2"></div>
          <div class="toast" id="toast"></div>
        </div>
      </ha-card>`;
    this.shadowRoot.getElementById("wrap").addEventListener("click", (ev) => {
      const el = ev.composedPath().find((n) => n.dataset && n.dataset.act);
      if (el) this._act(el.dataset.act, el);
    });
    this.shadowRoot.getElementById("disp").dataset.act = "disp";
  }

  _toast(msg) {
    const t = this.shadowRoot.getElementById("toast");
    t.textContent = msg;
    t.classList.add("show");
    clearTimeout(this._toastT);
    this._toastT = setTimeout(() => t.classList.remove("show"), 1800);
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

  _chState(n) {
    return this._val(`status_chamber_${n}`) || "standby";
  }

  _isActive(n) {
    return ACTIVE.includes(this._chState(n));
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

  _act(act, el) {
    const t = this._t;
    if (!this._e) return;
    const busy = this._isActive(1) || this._isActive(2);
    const [kind, arg] = act.split(":");
    if (kind === "info") return this._moreInfo(`status_chamber_${arg}`);
    if (kind === "disp") return this._moreInfo(this._focus() ? `status_chamber_${this._focus()}` : "mode");
    if (kind === "zone") return this._call("select", "select_option", "chamber", { option: arg });
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
      const runningSel = sel === "both" || sel === "whole" ? busy : this._isActive(target);
      if (runningSel) {
        const endKey = sel === "both" || sel === "whole" ? "end_both" : `end_chamber_${target}`;
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
    const sr = this.shadowRoot;
    if (!sr || !this._hass) return;
    const t = this._t;
    const wrap = sr.getElementById("wrap");
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

    // display
    const tag = sr.getElementById("tag");
    if (!online) {
      sr.getElementById("temp").innerHTML = "OFF";
      sr.getElementById("time").textContent = "";
      tag.textContent = t.offline;
    } else if (focus) {
      const temp = this._val(`set_temperature_chamber_${focus}`);
      sr.getElementById("temp").innerHTML = `${temp && !isNaN(temp) ? Math.round(temp) : "---"}<small>°C</small>`;
      sr.getElementById("time").textContent = this._fmt(this._remaining(focus));
      const zoneLbl = this._val("work_chamber") === "whole" ? t.whole : this._val("work_chamber") === "both" ? t.sync : focus === 1 ? t.zone1 : t.zone2;
      const run = RUNNING.includes(this._chState(focus));
      tag.innerHTML = `${run ? '<span class="dot"></span>' : ""}${zoneLbl} · ${t.status[this._chState(focus)] || ""}`;
    } else {
      const temp = this._val("temperature");
      const dur = Number(this._val("duration"));
      sr.getElementById("temp").innerHTML = `${temp && !isNaN(temp) ? Math.round(temp) : "---"}<small>°C</small>`;
      sr.getElementById("time").textContent = isNaN(dur) ? "--:--" : dur >= 60 ? `${Math.floor(dur / 60)}:${String(dur % 60).padStart(2, "0")}:00` : `${String(dur).padStart(2, "0")}:00`;
      tag.textContent = "";
    }

    // modes: show active program of focused chamber while cooking, else start setting
    const curMode = focus ? this._val(`mode_chamber_${focus}`) : mode;
    MODES.forEach((m) => {
      const el = sr.getElementById(`m-${m}`);
      el.textContent = t.modes[m];
      el.classList.toggle("sel", m === curMode);
    });

    // zones
    const zoneRun = {
      chamber_1: RUNNING.includes(this._chState(1)) && this._val("work_chamber") !== "whole",
      chamber_2: RUNNING.includes(this._chState(2)),
      whole: this._val("work_chamber") === "whole" && busy,
      both: this._val("work_chamber") === "both" && busy,
    };
    for (const [z, label] of [["chamber_1", t.zone1], ["chamber_2", t.zone2], ["whole", t.whole], ["both", t.sync]]) {
      const el = sr.getElementById(`p-${z}`);
      el.textContent = label;
      el.classList.toggle("sel", z === sel);
      el.classList.toggle("run", !!zoneRun[z]);
    }
    sr.getElementById("p-match").textContent = t.match;

    // play / power highlight
    sr.getElementById("play").classList.toggle("on", busy);
    sr.getElementById("play").classList.toggle("armed", this._armed === "play");
    sr.getElementById("power").classList.toggle("armed", this._armed === "power");

    // basket chips
    for (const n of [1, 2]) {
      const c = sr.getElementById(`c${n}`);
      const st = this._chState(n);
      const act = ACTIVE.includes(st);
      const whole = this._val("work_chamber") === "whole";
      if (n === 2 && whole && busy) {
        c.classList.add("hidden");
        continue;
      }
      c.classList.remove("hidden");
      c.classList.toggle("act", act);
      if (n === 1) c.style.left = whole && busy ? "50%" : "21.5%";
      const title = n === 1 && whole && busy ? t.whole : `${t.basket} ${n}`;
      if (!act) {
        c.innerHTML = `<div class="h"><span>${title}</span><span class="s">${t.status[st] || st}</span></div>`;
        continue;
      }
      const rem = this._remaining(n);
      const setT = Number(this._val(`set_time_chamber_${n}`));
      const setSec = isNaN(setT) ? null : Math.round((this._st(`set_time_chamber_${n}`)?.attributes.unit_of_measurement === "min" ? setT * 60 : setT));
      const pct = rem != null && setSec ? Math.min(100, Math.max(0, 100 - (rem / setSec) * 100)) : 0;
      const fin = this._val(`finish_chamber_${n}`);
      const finTxt = fin && !["unknown", "unavailable"].includes(fin)
        ? new Date(fin).toLocaleTimeString(this._hass.locale?.language || "de", { hour: "2-digit", minute: "2-digit" }) : "";
      const m = this._val(`mode_chamber_${n}`);
      const temp = this._val(`set_temperature_chamber_${n}`);
      c.innerHTML = `
        <div class="h"><span>${title}</span><span class="s">${RUNNING.includes(st) ? '<span class="dot"></span>' : ""}${t.status[st] || st}</span></div>
        <div class="big">${this._fmt(rem)}</div>
        <div class="sub">${t.modes[m] || ""}${temp && !isNaN(temp) ? " · " + Math.round(temp) + "°C" : ""}${finTxt ? " · " + t.done + " " + finTxt : ""}</div>
        <div class="bar"><i style="width:${pct}%"></i></div>`;
    }
  }
}

if (!customElements.get("cosori-airfryer-card")) {
  customElements.define("cosori-airfryer-card", CosoriAirfryerCard);
  window.customCards = window.customCards || [];
  window.customCards.push({
    type: "cosori-airfryer-card",
    name: "Cosori Airfryer",
    description: "TwinFry mit Live-Bedienfeld im Foto",
    preview: false,
  });
}
