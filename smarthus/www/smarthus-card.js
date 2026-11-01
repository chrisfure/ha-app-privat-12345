/*
 * Smarthus – en app for hele huset, bygget som ett fullskjermkort i Home Assistant.
 *
 * Alt personlig (rom, enheter, hvem som ser hva) ligger i kortets oppsett i
 * Home Assistant og redigeres i appens redigeringsmodus. Koden er generisk.
 */
const VERSION = "0.1.0";

/* ------------------------------------------------------------------ */
/* Hjelpere                                                             */
/* ------------------------------------------------------------------ */

const esc = (s) =>
  String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const clamp = (v, a, b) => Math.min(b, Math.max(a, v));
const clone = (o) => JSON.parse(JSON.stringify(o ?? null));
const domainOf = (id) => String(id || "").split(".")[0];
const uid = () => Math.random().toString(36).slice(2, 8);
const BAD = ["unavailable", "unknown", "none", "", undefined, null];

const NB_MODES = {
  off: "Av", heat: "Varme", cool: "Kjøl", fan_only: "Vifte", heat_cool: "Auto", auto: "Auto", dry: "Tørk",
};
const NB_PRESETS = { off: "Av", keep: "Hold på", dog: "Hund", camp: "Camping", eco: "Eco", away: "Borte", home: "Hjemme", comfort: "Komfort", sleep: "Natt", boost: "Boost" };
const NB_FAN = {
  quiet: "Stille", balanced: "Balansert", turbo: "Turbo", max: "Maks", gentle: "Skånsom", off: "Av",
  standard: "Standard", strong: "Sterk", medium: "Middels", low: "Lav", high: "Høy", silent: "Stille", auto: "Auto",
};
const NB_WEATHER = {
  "clear-night": "Klart", cloudy: "Overskyet", fog: "Tåke", hail: "Hagl", lightning: "Torden",
  "lightning-rainy": "Torden og regn", partlycloudy: "Delvis skyet", pouring: "Kraftig regn", rainy: "Regn",
  snowy: "Snø", "snowy-rainy": "Sludd", sunny: "Sol", windy: "Vind", "windy-variant": "Vind", exceptional: "Ekstremvær",
};
const WEATHER_ICON = {
  "clear-night": "mdi:weather-night", cloudy: "mdi:weather-cloudy", fog: "mdi:weather-fog", hail: "mdi:weather-hail",
  lightning: "mdi:weather-lightning", "lightning-rainy": "mdi:weather-lightning-rainy", partlycloudy: "mdi:weather-partly-cloudy",
  pouring: "mdi:weather-pouring", rainy: "mdi:weather-rainy", snowy: "mdi:weather-snowy", "snowy-rainy": "mdi:weather-snowy-rainy",
  sunny: "mdi:weather-sunny", windy: "mdi:weather-windy", "windy-variant": "mdi:weather-windy-variant", exceptional: "mdi:alert",
};
const DOMAIN_ICON = {
  light: "mdi:lightbulb", switch: "mdi:toggle-switch", input_boolean: "mdi:toggle-switch-outline", automation: "mdi:robot",
  climate: "mdi:thermostat", sensor: "mdi:gauge", binary_sensor: "mdi:checkbox-blank-circle-outline", media_player: "mdi:speaker",
  vacuum: "mdi:robot-vacuum", cover: "mdi:garage", lock: "mdi:lock", camera: "mdi:cctv", scene: "mdi:palette",
  script: "mdi:script-text", button: "mdi:gesture-tap-button", timer: "mdi:timer-outline", todo: "mdi:format-list-checks",
  select: "mdi:format-list-bulleted", input_select: "mdi:format-list-bulleted", number: "mdi:numeric", input_number: "mdi:numeric",
  input_datetime: "mdi:clock-outline", input_text: "mdi:form-textbox", fan: "mdi:fan", weather: "mdi:weather-partly-cloudy",
  update: "mdi:update", calendar: "mdi:calendar", person: "mdi:account", device_tracker: "mdi:map-marker",
};

/* Typene som kan legges til i en fane, med standardbredde (av 6 kolonner) */
const TYPES = {
  light: { label: "Lys med lysstyrke", w: 6, domains: ["light"] },
  toggle: { label: "Av/på-bryter", w: 3, domains: ["switch", "input_boolean", "automation", "light", "fan", "siren"] },
  climate: { label: "Varme / termostat", w: 6, domains: ["climate"] },
  value: { label: "Verdi (sensor)", w: 3, domains: ["sensor", "binary_sensor", "weather", "device_tracker", "person", "event"] },
  button: { label: "Knapp (scene, skript, handling)", w: 2, domains: ["scene", "script", "button", "input_button", "automation"] },
  media: { label: "Høyttaler / TV", w: 6, domains: ["media_player"] },
  vacuum: { label: "Støvsuger", w: 6, domains: ["vacuum"] },
  areaclean: { label: "Støvsug valgte rom", w: 6, domains: ["vacuum"] },
  select: { label: "Valgliste", w: 6, domains: ["select", "input_select"] },
  number: { label: "Tall / glidebryter", w: 6, domains: ["number", "input_number"] },
  time: { label: "Klokkeslett", w: 3, domains: ["input_datetime"] },
  input: { label: "Tekstfelt", w: 6, domains: ["input_text"] },
  cover: { label: "Port / gardin", w: 6, domains: ["cover"] },
  lock: { label: "Lås", w: 3, domains: ["lock"] },
  camera: { label: "Kamera / bilde", w: 6, domains: ["camera", "image"] },
  timer: { label: "Nedtelling (timer)", w: 6, domains: ["timer"] },
  todo: { label: "Liste (handleliste)", w: 6, domains: ["todo"] },
  calendar: { label: "Kalender", w: 6, domains: ["calendar"] },
  weather: { label: "Værmelding", w: 6, domains: ["weather"] },
  graph: { label: "Graf", w: 6, domains: ["sensor", "binary_sensor"] },
  pricechart: { label: "Strømpris (Nord Pool)", w: 6, domains: ["sensor"] },
  text: { label: "Tekst / melding", w: 6, domains: ["input_text", "sensor"] },
  link: { label: "Snarvei", w: 3, domains: [] },
  heading: { label: "Overskrift", w: 6, domains: [] },
  updates: { label: "Oppdateringer klare", w: 6, domains: [] },
  batteries: { label: "Lave batterier", w: 6, domains: [] },
  lightson: { label: "Lys som er på", w: 6, domains: [] },
  card: { label: "Vanlig Home Assistant-kort", w: 6, domains: [] },
};

/* Lite DOM-patch: holder fokus, rulleposisjon og bilder i ro mellom oppdateringer */
function morph(from, to) {
  if (from.nodeType === 1) {
    /* Home Assistants egne elementer (ha-icon o.l.) får beholde attributter de setter selv */
    if (!from.tagName.includes("-")) for (const a of [...from.attributes]) if (!to.hasAttribute(a.name)) from.removeAttribute(a.name);
    for (const a of [...to.attributes]) if (from.getAttribute(a.name) !== a.value) from.setAttribute(a.name, a.value);
    const tag = from.tagName;
    if (tag === "INPUT" || tag === "TEXTAREA" || tag === "SELECT") {
      const focused = from.getRootNode().activeElement === from;
      if (!focused && from.dataset.fresh !== "1") {
        if (to.hasAttribute("value") && from.value !== to.getAttribute("value")) from.value = to.getAttribute("value");
        if (from.type === "checkbox") from.checked = to.hasAttribute("checked");
      }
      if (tag !== "TEXTAREA") return;
    }
  }
  if (from.nodeType === 1 && from.hasAttribute("data-keep")) return;
  const fc = [...from.childNodes];
  const tc = [...to.childNodes];
  for (let i = 0; i < tc.length; i++) {
    const t = tc[i];
    const f = fc[i];
    if (!f) from.appendChild(t);
    else if (
      f.nodeType !== t.nodeType || f.nodeName !== t.nodeName ||
      (f.nodeType === 1 && f.getAttribute("data-k") !== t.getAttribute("data-k"))
    ) from.replaceChild(t, f);
    else if (f.nodeType !== 1) { if (f.nodeValue !== t.nodeValue) f.nodeValue = t.nodeValue; }
    else if (f.tagName === "TEXTAREA") { /* behold det brukeren skriver */ }
    else morph(f, t);
  }
  for (let i = tc.length; i < fc.length; i++) from.removeChild(fc[i]);
}

/* Enkel markdown for tekstkort: ### overskrift, **fet**, linjeskift */
function miniMd(text) {
  return String(text ?? "")
    .split(/\n{2,}/)
    .map((block) => {
      const lines = block.split("\n").map((line) => {
        let l = esc(line).replace(/\*\*(.+?)\*\*/g, "<b>$1</b>");
        if (/^#{1,3} /.test(line)) l = `<span class="md-h">${l.replace(/^#{1,3} /, "")}</span>`;
        return l;
      });
      return `<p>${lines.join("<br>")}</p>`;
    })
    .join("");
}

/* ------------------------------------------------------------------ */
/* Stil                                                                 */
/* ------------------------------------------------------------------ */

const CSS = `
:host {
  --bg:#F4F2EE; --card:#FFFFFF; --card2:#ECE8E1; --line:#E2DED6; --text:#1C1B19; --muted:#5F5B54;
  --accent:#E8902A; --accent-text:#1A1206; --on-bg:#FBE1BC; --on-text:#5A3608; --good:#2E7D4F; --good-bg:#DDEFE2;
  --bad:#B3361F; --bad-bg:#F7DED8; --blue:#2F6FB0; --blue-bg:#DCE8F5; --shadow:0 1px 2px rgba(0,0,0,.05);
  --r:22px; --r-s:14px;
  display:block; height:calc(100dvh - var(--header-height, 56px)); background:var(--bg); color:var(--text);
  font-family:'Manrope', system-ui, -apple-system, 'Segoe UI', sans-serif; -webkit-tap-highlight-color:transparent;
  overflow:hidden; position:relative;
}
:host([data-theme=dark]) {
  --bg:#0F1012; --card:#1C1D21; --card2:#2A2C31; --line:#2E3036; --text:#F3F1EC; --muted:#A9A69F;
  --accent:#F2A541; --accent-text:#1A1206; --on-bg:#3A2C17; --on-text:#F7CD8C; --good:#8FE0A6; --good-bg:#17301F;
  --bad:#FF9C87; --bad-bg:#3A1D17; --blue:#8DB8FF; --blue-bg:#1B2A40; --shadow:none;
}
* { box-sizing:border-box; }
#root { height:100%; }
.app { height:100%; display:flex; flex-direction:column; max-width:680px; margin:0 auto; position:relative; }
.content { flex:1; overflow-y:auto; overflow-x:hidden; padding:18px 16px 24px; overscroll-behavior:contain; }
.content::-webkit-scrollbar { width:0; }
button { font:inherit; color:inherit; border:0; background:none; cursor:pointer; padding:0; }
button:focus-visible, a:focus-visible, input:focus-visible { outline:2px solid var(--blue); outline-offset:2px; }
ha-icon { --mdc-icon-size:22px; display:inline-flex; }
.muted { color:var(--muted); }
.row { display:flex; align-items:center; gap:10px; }
.grow { flex:1; min-width:0; }
.ellip { white-space:nowrap; overflow:hidden; text-overflow:ellipsis; }

/* Topp */
.top { display:flex; align-items:flex-start; justify-content:space-between; gap:12px; margin-bottom:14px; }
.date { font-size:13px; font-weight:600; color:var(--muted); text-transform:capitalize; }
.h1 { font-size:28px; font-weight:800; letter-spacing:-.8px; line-height:1.15; margin:2px 0 0; }
.sub { font-size:14px; color:var(--muted); font-weight:500; margin-top:4px; }
.pill { height:44px; min-width:44px; padding:0 12px; border-radius:22px; background:var(--card); display:inline-flex; align-items:center; justify-content:center; gap:6px; font-weight:700; font-size:15px; box-shadow:var(--shadow); }
.back { width:44px; height:44px; border-radius:22px; background:var(--card); display:inline-flex; align-items:center; justify-content:center; flex:none; box-shadow:var(--shadow); }

/* Brikker */
.chips { display:flex; gap:8px; overflow-x:auto; margin:0 -16px 14px; padding:0 16px; scrollbar-width:none; }
.chips::-webkit-scrollbar { display:none; }
.chip { height:36px; padding:0 13px; border-radius:18px; background:var(--card); font-size:13px; font-weight:700; white-space:nowrap; display:inline-flex; align-items:center; gap:6px; flex:none; box-shadow:var(--shadow); }
.chip ha-icon { --mdc-icon-size:17px; }
.chip.good { background:var(--good-bg); color:var(--good); }
.chip.bad { background:var(--bad-bg); color:var(--bad); }
.chip.warm { background:var(--on-bg); color:var(--on-text); }
.chip.blue { background:var(--blue-bg); color:var(--blue); }

/* Hurtigknapper */
.quick { display:grid; grid-template-columns:repeat(4, minmax(0,1fr)); gap:8px; margin-bottom:16px; }
.qbtn { height:74px; border-radius:20px; background:var(--card); display:flex; flex-direction:column; align-items:center; justify-content:center; gap:5px; font-size:12.5px; font-weight:700; box-shadow:var(--shadow); padding:0 4px; text-align:center; }
.qbtn.primary { background:var(--accent); color:var(--accent-text); }
.qbtn.running { outline:2px solid var(--accent); }

/* Seksjonstittel */
.label { font-size:12px; font-weight:800; letter-spacing:.8px; text-transform:uppercase; color:var(--muted); margin:18px 2px 10px; display:flex; justify-content:space-between; align-items:center; }
.label:first-child { margin-top:2px; }

/* Romruter */
.rooms { display:grid; grid-template-columns:repeat(2, minmax(0,1fr)); gap:10px; }
.room { position:relative; border-radius:var(--r); background:var(--card); padding:14px; min-height:88px; display:flex; flex-direction:column; justify-content:space-between; text-align:left; box-shadow:var(--shadow); }
.room.on { background:var(--on-bg); color:var(--on-text); }
.room .nm { font-size:16px; font-weight:800; letter-spacing:-.2px; padding-right:40px; }
.room .st { font-size:13px; font-weight:600; opacity:.85; }
.room .tg { position:absolute; top:10px; right:10px; width:38px; height:38px; border-radius:19px; background:var(--card2); display:flex; align-items:center; justify-content:center; }
.room.on .tg { background:var(--accent); color:var(--accent-text); }
.room .tg ha-icon { --mdc-icon-size:19px; }
.room.wide { grid-column:span 2; min-height:60px; flex-direction:row; align-items:center; }
.room.wide .st { margin-right:46px; }

/* Faner */
.tabs { display:flex; gap:4px; background:var(--card2); border-radius:16px; padding:4px; margin-bottom:14px; overflow-x:auto; scrollbar-width:none; }
.tabs::-webkit-scrollbar { display:none; }
.tab { flex:1 0 auto; height:40px; padding:0 14px; border-radius:12px; font-size:14px; font-weight:700; color:var(--muted); white-space:nowrap; }
.tab.sel { background:var(--card); color:var(--text); box-shadow:0 1px 3px rgba(0,0,0,.12); }

/* Rutenett for elementer */
.grid { display:grid; grid-template-columns:repeat(6, minmax(0,1fr)); gap:10px; }
.it { grid-column:span 6; min-width:0; position:relative; }
.w2 { grid-column:span 2; } .w3 { grid-column:span 3; } .w4 { grid-column:span 4; } .w6 { grid-column:span 6; }
.card { background:var(--card); border-radius:var(--r); padding:14px 16px; box-shadow:var(--shadow); }
.card.tight { padding:12px 14px; }
.ttl { font-size:15.5px; font-weight:800; letter-spacing:-.2px; }
.small { font-size:13px; font-weight:600; color:var(--muted); }
.heading { font-size:12px; font-weight:800; letter-spacing:.8px; text-transform:uppercase; color:var(--muted); padding:8px 2px 0; display:flex; align-items:center; gap:6px; }
.heading ha-icon { --mdc-icon-size:16px; }

/* Lysstripe */
.strip { position:relative; height:60px; border-radius:18px; background:var(--card); overflow:hidden; touch-action:pan-y; user-select:none; -webkit-user-select:none; box-shadow:var(--shadow); cursor:pointer; }
.strip .fill { position:absolute; inset:0 auto 0 0; background:var(--on-bg); transition:width .18s ease; }
.strip.drag .fill { transition:none; }
.strip .in { position:relative; height:100%; display:flex; align-items:center; gap:12px; padding:0 16px; }
.strip .ic { width:36px; height:36px; border-radius:18px; background:var(--card2); display:flex; align-items:center; justify-content:center; flex:none; }
.strip.on .ic { background:var(--accent); color:var(--accent-text); }
.strip .nm { font-size:15px; font-weight:800; flex:1; min-width:0; white-space:nowrap; overflow:hidden; text-overflow:ellipsis; }
.strip .val { font-size:14px; font-weight:700; color:var(--muted); }
.strip.on .val { color:var(--on-text); }
.strip.off-only .fill { display:none; }

/* Bryter */
.tgl { display:flex; align-items:center; gap:12px; background:var(--card); border-radius:18px; padding:10px 12px 10px 14px; min-height:60px; width:100%; text-align:left; box-shadow:var(--shadow); }
.tgl .ic { width:36px; height:36px; border-radius:18px; background:var(--card2); display:flex; align-items:center; justify-content:center; flex:none; }
.tgl.on .ic { background:var(--accent); color:var(--accent-text); }
.tgl .nm { font-size:14.5px; font-weight:800; line-height:1.2; }
.tgl .st { font-size:12.5px; font-weight:600; color:var(--muted); }
.sw { width:46px; height:28px; border-radius:14px; background:var(--card2); position:relative; flex:none; transition:background .15s; }
.sw::after { content:""; position:absolute; top:3px; left:3px; width:22px; height:22px; border-radius:11px; background:#fff; box-shadow:0 1px 2px rgba(0,0,0,.3); transition:left .15s; }
.on .sw { background:var(--accent); }
.on .sw::after { left:21px; }

/* Verdi */
.val-card { display:flex; flex-direction:column; gap:2px; background:var(--card); border-radius:18px; padding:12px 14px; min-height:60px; width:100%; text-align:left; box-shadow:var(--shadow); }
.val-card .v { font-size:19px; font-weight:800; letter-spacing:-.3px; }
.val-card .n { font-size:12.5px; font-weight:600; color:var(--muted); }
.bar { height:6px; border-radius:3px; background:var(--card2); overflow:hidden; margin-top:6px; }
.bar > div { height:100%; background:var(--accent); border-radius:3px; }
.spark { width:100%; height:34px; margin-top:4px; display:block; }

/* Knapper */
.btn { min-height:48px; border-radius:16px; background:var(--card); font-size:13.5px; font-weight:700; display:flex; align-items:center; justify-content:center; gap:7px; padding:6px 10px; width:100%; text-align:center; box-shadow:var(--shadow); line-height:1.2; }
.btn.tall { min-height:70px; flex-direction:column; gap:4px; }
.btn.dark { background:var(--text); color:var(--bg); }
.btn.accent { background:var(--accent); color:var(--accent-text); }
.btn.blue { background:var(--blue); color:#fff; }
.btn.soft { background:var(--card2); box-shadow:none; }
.btn.danger { color:var(--bad); }
.btn.running { outline:2px solid var(--accent); }
button:disabled { opacity:.45; cursor:default; }
.btns { display:grid; gap:6px; }
.seg { display:flex; gap:4px; background:var(--card2); border-radius:12px; padding:3px; flex-wrap:wrap; }
.seg button { flex:1 0 auto; min-height:38px; padding:0 10px; border-radius:9px; font-size:13px; font-weight:700; color:var(--muted); }
.seg button.sel { background:var(--card); color:var(--text); box-shadow:0 1px 3px rgba(0,0,0,.12); }
.seg.hot button.sel { background:var(--accent); color:var(--accent-text); }

/* Termostat */
.thermo .tv { font-size:24px; font-weight:800; min-width:64px; text-align:center; letter-spacing:-.5px; }
.round { width:46px; height:46px; border-radius:23px; background:var(--card2); display:inline-flex; align-items:center; justify-content:center; flex:none; font-size:22px; font-weight:700; }
.list { background:var(--card); border-radius:var(--r); overflow:hidden; box-shadow:var(--shadow); }
.lrow { display:flex; align-items:center; gap:10px; padding:10px 12px 10px 16px; min-height:62px; border-bottom:1px solid var(--line); }
.lrow:last-child { border-bottom:0; }
.lrow .tv { font-size:18px; min-width:52px; }
.lrow .round { width:44px; height:44px; font-size:20px; }

/* Media */
.media .ctr { display:flex; gap:6px; align-items:center; }
.media input[type=range] { flex:1; }
input[type=range] { -webkit-appearance:none; appearance:none; height:30px; background:transparent; width:100%; }
input[type=range]::-webkit-slider-runnable-track { height:8px; border-radius:4px; background:var(--card2); }
input[type=range]::-moz-range-track { height:8px; border-radius:4px; background:var(--card2); }
input[type=range]::-webkit-slider-thumb { -webkit-appearance:none; width:26px; height:26px; border-radius:13px; background:var(--accent); margin-top:-9px; border:3px solid var(--card); }
input[type=range]::-moz-range-thumb { width:22px; height:22px; border-radius:11px; background:var(--accent); border:3px solid var(--card); }
.vol-row { display:flex; align-items:center; gap:8px; margin-top:6px; }
.vol-row ha-icon { color:var(--muted); --mdc-icon-size:19px; }

/* Valgbrikker */
.opts { display:flex; flex-wrap:wrap; gap:6px; }
.opt { min-height:40px; padding:0 14px; border-radius:20px; background:var(--card2); font-size:13.5px; font-weight:700; }
.opt.sel { background:var(--text); color:var(--bg); }

/* Felter */
.field { width:100%; height:48px; border-radius:14px; border:1.5px solid var(--line); background:var(--card); color:var(--text); font:inherit; font-size:15px; padding:0 14px; }
textarea.field { height:auto; min-height:160px; padding:12px 14px; font-family:ui-monospace, Menlo, monospace; font-size:12.5px; line-height:1.45; }
select.field { appearance:auto; }
.time-field { width:100%; height:48px; border-radius:14px; border:0; background:var(--card2); color:var(--text); font:inherit; font-size:20px; font-weight:800; padding:0 12px; text-align:center; }

/* Liste-kort (handleliste, oppdateringer) */
.check { display:flex; align-items:center; gap:12px; padding:0 4px; min-height:48px; border-bottom:1px solid var(--line); width:100%; text-align:left; font-size:15px; font-weight:600; }
.check:last-child { border-bottom:0; }
.box { width:24px; height:24px; border-radius:8px; border:2px solid var(--muted); flex:none; display:flex; align-items:center; justify-content:center; }
.done .box { background:var(--good); border-color:var(--good); color:#fff; }
.done span.t { text-decoration:line-through; color:var(--muted); }

/* Kalender */
.cal-day { font-size:12px; font-weight:800; letter-spacing:.6px; text-transform:uppercase; color:var(--muted); margin:12px 0 4px; }
.cal-day:first-child { margin-top:0; }
.ev { display:flex; gap:10px; align-items:baseline; padding:5px 0; font-size:14.5px; font-weight:600; }
.ev .tm { min-width:44px; font-variant-numeric:tabular-nums; color:var(--muted); font-weight:700; font-size:13px; }
.dot { width:9px; height:9px; border-radius:5px; flex:none; transform:translateY(-1px); }

/* Pris */
.bars { display:flex; align-items:flex-end; gap:2px; height:70px; margin:10px 0 4px; }
.bars div { flex:1; border-radius:3px 3px 1px 1px; background:var(--card2); min-height:3px; }
.bars div.now { background:var(--accent); }
.bars div.tm { background:var(--blue-bg); }
:host([data-theme=dark]) .bars div.tm { background:#24364F; }
.axis { display:flex; justify-content:space-between; font-size:11px; font-weight:700; color:var(--muted); }

/* Vær */
.fc { display:flex; gap:6px; overflow-x:auto; margin-top:10px; scrollbar-width:none; }
.fc::-webkit-scrollbar { display:none; }
.fc > div { flex:none; width:52px; text-align:center; background:var(--card2); border-radius:14px; padding:8px 0; font-size:12px; font-weight:700; }
.fc ha-icon { --mdc-icon-size:22px; margin:4px 0; }

/* Mer */
.big { display:block; width:100%; text-align:left; background:var(--card); border-radius:var(--r); padding:16px; margin-bottom:10px; box-shadow:var(--shadow); }
.big .hv { font-size:26px; font-weight:800; letter-spacing:-.6px; }
.tiles { display:grid; grid-template-columns:repeat(3, minmax(0,1fr)); gap:8px; }
.tile { height:84px; border-radius:20px; background:var(--card); display:flex; flex-direction:column; align-items:center; justify-content:center; gap:6px; font-size:12.5px; font-weight:700; box-shadow:var(--shadow); padding:0 6px; text-align:center; }
.tile.alert { background:var(--bad-bg); color:var(--bad); }

/* Bunnmeny */
.navwrap { padding:8px 14px calc(12px + env(safe-area-inset-bottom)); background:linear-gradient(to top, var(--bg) 70%, transparent); }
nav.nav { height:64px; border-radius:32px; background:var(--card); display:grid; grid-template-columns:repeat(4, minmax(0,1fr)); align-items:center; padding:0 6px; box-shadow:0 4px 18px rgba(0,0,0,.10); }
nav.nav button { height:52px; border-radius:26px; display:flex; flex-direction:column; align-items:center; justify-content:center; gap:1px; font-size:11.5px; font-weight:700; color:var(--muted); }
nav.nav button ha-icon { --mdc-icon-size:21px; }
nav.nav button.sel { background:var(--text); color:var(--bg); }

/* Redigering */
.editbar { display:flex; align-items:center; gap:8px; padding:10px 14px; background:var(--blue); color:#fff; font-size:14px; font-weight:700; }
.editbar button { height:38px; padding:0 14px; border-radius:19px; background:rgba(255,255,255,.18); font-size:13.5px; font-weight:800; }
.editbar button.save { background:#fff; color:var(--blue); }
.etools { position:absolute; top:-16px; right:-6px; display:flex; gap:3px; z-index:3; }
.etools button { width:32px; height:32px; border-radius:16px; background:var(--blue); color:#fff; display:flex; align-items:center; justify-content:center; box-shadow:0 2px 6px rgba(0,0,0,.25); }
.etools button ha-icon { --mdc-icon-size:17px; }
.editing .it, .editing .room, .editing .qbtn { outline:2px dashed var(--blue); outline-offset:2px; border-radius:var(--r); }
.hiddenfor { opacity:.5; }
.badge { display:inline-block; font-size:11px; font-weight:800; padding:2px 7px; border-radius:8px; background:var(--blue-bg); color:var(--blue); margin-left:6px; vertical-align:middle; }
.add { min-height:52px; width:100%; border-radius:16px; border:2px dashed var(--muted); color:var(--muted); font-size:14px; font-weight:800; display:flex; align-items:center; justify-content:center; gap:6px; margin-top:10px; }
.tabedit { display:flex; flex-wrap:wrap; gap:6px; margin-bottom:12px; }
.tabedit .te { display:flex; align-items:center; gap:2px; background:var(--card); border-radius:14px; padding:4px 4px 4px 12px; font-size:14px; font-weight:700; box-shadow:var(--shadow); }
.tabedit .te.sel { outline:2px solid var(--blue); }
.tabedit .te button { width:34px; height:34px; border-radius:17px; display:inline-flex; align-items:center; justify-content:center; color:var(--blue); }
.tabedit .te button ha-icon { --mdc-icon-size:17px; }

/* Ark (modal) */
.scrim { position:absolute; inset:0; background:rgba(0,0,0,.45); z-index:20; display:flex; align-items:flex-end; justify-content:center; animation:fade .15s ease; }
.sheet { background:var(--bg); width:100%; max-width:680px; max-height:88%; overflow-y:auto; border-radius:26px 26px 0 0; padding:10px 18px calc(22px + env(safe-area-inset-bottom)); animation:up .2s ease; }
.grab { width:40px; height:5px; border-radius:3px; background:var(--line); margin:0 auto 12px; }
.sheet h2 { font-size:20px; font-weight:800; margin:4px 0 14px; letter-spacing:-.3px; }
.frm { display:flex; flex-direction:column; gap:12px; }
.frm label { font-size:12.5px; font-weight:800; color:var(--muted); display:flex; flex-direction:column; gap:6px; }
.cbx { display:flex; flex-wrap:wrap; gap:6px; }
.cbx label { flex-direction:row; align-items:center; gap:8px; background:var(--card); border-radius:12px; padding:0 12px; min-height:44px; color:var(--text); font-size:14px; }
.cbx input { width:20px; height:20px; accent-color:var(--blue); }
details summary { font-size:13px; font-weight:800; color:var(--blue); cursor:pointer; padding:6px 0; }
.sheet-actions { display:grid; grid-template-columns:1fr 1fr; gap:8px; margin-top:16px; }
.toast { position:absolute; left:50%; bottom:96px; transform:translateX(-50%); background:var(--text); color:var(--bg); padding:11px 18px; border-radius:16px; font-size:14px; font-weight:700; z-index:30; max-width:86%; text-align:center; animation:fade .2s ease; }
.empty { text-align:center; padding:26px 10px; color:var(--muted); font-weight:700; font-size:14.5px; }
.cam { width:100%; display:block; border-radius:var(--r); background:var(--card2); aspect-ratio:16/9; object-fit:cover; }
.warn { background:var(--bad-bg); color:var(--bad); border-radius:12px; padding:9px 12px; font-size:13.5px; font-weight:700; margin-top:8px; }
.md p { margin:0 0 8px; font-size:14.5px; line-height:1.45; }
.md p:last-child { margin:0; }
.md .md-h { font-size:16px; font-weight:800; }
.brief { display:flex; gap:12px; align-items:flex-start; }
.brief .ic { width:40px; height:40px; border-radius:14px; background:var(--on-bg); color:var(--accent); display:flex; align-items:center; justify-content:center; flex:none; }
@keyframes fade { from { opacity:0; } to { opacity:1; } }
@keyframes up { from { transform:translateY(40px); opacity:.6; } to { transform:none; opacity:1; } }
@media (min-width: 560px) {
  .rooms { grid-template-columns:repeat(3, minmax(0,1fr)); }
  .room.wide { grid-column:span 3; }
}
`;

/* ------------------------------------------------------------------ */
/* Selve appen                                                          */
/* ------------------------------------------------------------------ */

class SmarthusApp extends HTMLElement {
  constructor() {
    super();
    this.attachShadow({ mode: "open" });
    this._nav = { view: "home" };
    this._tabSel = {};
    this._edit = false;
    this._draft = null;
    this._sheet = null;
    this._h = [];
    this._pend = {};
    this._tpl = {};
    this._hist = {};
    this._cal = {};
    this._todo = {};
    this._fc = {};
    this._sel = {};
    this._lightsMode = "on";
    this._theme = this._readLocalTheme();
    this._suppressUntil = 0;
    this._cards = {};
    this._cardCfg = {};
  }

  /* ---------- Livssyklus ---------- */

  static getStubConfig() {
    return { rooms: [], more: [], home: { chips: [{ type: "lights" }], quick: [] }, heat: { items: [] }, lights: {} };
  }

  setConfig(config) {
    this._config = this._normalize(clone(config) || {});
    if (!this._edit) this._draft = null;
    this._render();
  }

  set hass(hass) {
    const first = !this._hass;
    this._hass = hass;
    if (first) this._init();
    this._schedule();
  }

  get hass() { return this._hass; }

  getCardSize() { return 20; }

  connectedCallback() {
    if (!this._mq) {
      this._mq = window.matchMedia("(prefers-color-scheme: dark)");
      this._mq.addEventListener?.("change", () => this._applyTheme());
    }
    if (this._timer) clearInterval(this._timer);
    this._timer = setInterval(() => this._tick(), 1000);
  }

  disconnectedCallback() {
    clearInterval(this._timer);
    this._timer = null;
  }

  _init() {
    if (!document.getElementById("smarthus-font")) {
      const l = document.createElement("link");
      l.id = "smarthus-font";
      l.rel = "stylesheet";
      l.href = "https://fonts.googleapis.com/css2?family=Manrope:wght@400;500;600;700;800&display=swap";
      document.head.appendChild(l);
    }
    this.shadowRoot.innerHTML = `<style>${CSS}</style><div id="root"></div>`;
    const r = this.shadowRoot;
    r.addEventListener("pointerdown", (e) => this._onDown(e));
    r.addEventListener("pointermove", (e) => this._onMove(e));
    r.addEventListener("pointerup", (e) => this._onUp(e));
    r.addEventListener("pointercancel", (e) => this._onCancel(e));
    r.addEventListener("click", (e) => this._onClick(e), true);
    r.addEventListener("change", (e) => this._onChange(e));
    r.addEventListener("keydown", (e) => this._onKey(e));
    r.addEventListener("contextmenu", (e) => { if (e.target.closest?.("[data-more],[data-slide]")) e.preventDefault(); });
    this._loadTheme();
    this._applyTheme();
  }

  _normalize(c) {
    c.home = c.home || {};
    c.home.chips = c.home.chips || [];
    c.home.quick = c.home.quick || [];
    c.home.before = c.home.before || [];
    c.home.after = c.home.after || [];
    c.rooms = c.rooms || [];
    c.more = c.more || [];
    c.heat = c.heat || {};
    c.heat.items = c.heat.items || [];
    c.lights = c.lights || {};
    c.lights.exclude = c.lights.exclude || [];
    c.lights.actions = c.lights.actions || [];
    c.users = c.users || {};
    for (const p of [...c.rooms, ...c.more]) {
      p.id = p.id || uid();
      p.tabs = p.tabs && p.tabs.length ? p.tabs : [{ name: "Oversikt", items: [] }];
      for (const t of p.tabs) t.items = t.items || [];
    }
    return c;
  }

  get _cfg() { return this._edit && this._draft ? this._draft : this._config; }
  get _uid() { return this._hass?.user?.id; }
  get _canEdit() {
    const ed = this._config?.editors;
    if (ed && ed.length) return ed.includes(this._uid);
    return !!this._hass?.user?.is_admin;
  }

  /* ---------- Tema ---------- */

  _readLocalTheme() {
    try { return localStorage.getItem("smarthus-theme") || "auto"; } catch (e) { return "auto"; }
  }

  async _loadTheme() {
    try {
      const r = await this._hass.callWS({ type: "frontend/get_user_data", key: "smarthus_theme" });
      if (r && r.value) { this._theme = r.value; this._applyTheme(); }
    } catch (e) { /* bruk lokalt valg */ }
  }

  _setTheme(mode) {
    this._theme = mode;
    try { localStorage.setItem("smarthus-theme", mode); } catch (e) { /* ok */ }
    this._hass.callWS({ type: "frontend/set_user_data", key: "smarthus_theme", value: mode }).catch(() => {});
    this._applyTheme();
    this._render();
  }

  _applyTheme() {
    const m = this._theme || "auto";
    let dark;
    if (m === "dark") dark = true;
    else if (m === "light") dark = false;
    else if (this._hass?.themes && typeof this._hass.themes.darkMode === "boolean") dark = this._hass.themes.darkMode;
    else dark = !!this._mq?.matches;
    this.setAttribute("data-theme", dark ? "dark" : "light");
  }

  /* ---------- Rendering ---------- */

  _schedule() {
    if (this._raf) return;
    this._raf = setTimeout(() => { this._raf = null; this._render(); }, 50);
  }

  _tick() {
    if (this._needsTick) this._render();
  }

  _render() {
    if (!this._hass || !this._config || !this.shadowRoot.getElementById("root")) return;
    if (this._drag && this._drag.moved) { this._schedule(); return; }
    this._applyTheme();
    this._h = [];
    this._needsTick = false;
    let html;
    try { html = this._app(); } catch (err) {
      console.error("Smarthus", err);
      html = `<div class="app"><main class="content"><div class="card"><div class="ttl">Noe gikk galt</div><div class="small">${esc(err.message)}</div></div></main></div>`;
    }
    const root = this.shadowRoot.getElementById("root");
    const next = document.createElement("div");
    next.id = "root";
    next.innerHTML = html;
    morph(root, next);
    this._mountCards();
  }

  /* Vanlige Home Assistant-kort inni appen (kart, energi, spesialkort) */
  async _mountCards() {
    const els = this.shadowRoot.querySelectorAll("[data-card]");
    for (const el of els) {
      const key = el.dataset.card;
      let rec = this._cards[key];
      if (!rec) {
        rec = this._cards[key] = { el: null };
        try {
          if (!this._helpers) this._helpers = await window.loadCardHelpers();
          rec.el = this._helpers.createCardElement(this._cardCfg[key]);
        } catch (err) {
          rec.el = document.createElement("div");
          rec.el.className = "small";
          rec.el.textContent = "Kortet kunne ikke vises: " + (err.message || err);
        }
      }
      if (!rec.el) continue;
      if ("hass" in rec.el || rec.el.setConfig) rec.el.hass = this._hass;
      if (rec.el.parentElement !== el) { el.textContent = ""; el.appendChild(rec.el); }
    }
  }

  /* registrerer en klikk-/endringshandler og gir tilbake attributtet */
  h(fn) { return `data-h="${this._h.push(fn) - 1}"`; }
  c(fn) { return `data-c="${this._h.push(fn) - 1}"`; }

  _app() {
    const v = this._nav.view;
    let body;
    let key = v;
    if (v === "home") body = this._home();
    else if (v === "lights") body = this._lightsView();
    else if (v === "heat") body = this._heatView();
    else if (v === "more") body = this._moreView();
    else if (v === "page") { body = this._pageView(); key = "page-" + this._nav.id; }
    else body = this._home();

    const bar = this._edit
      ? `<div class="editbar"><span class="grow">Redigeringsmodus</span>
          <button ${this.h(() => this._openJson())}>Tekst</button>
          <button ${this.h(() => this._cancelEdit())}>Avbryt</button>
          <button class="save" ${this.h(() => this._saveEdit())}>Lagre</button></div>`
      : "";
    return `<div class="app ${this._edit ? "editing" : ""}" data-k="app">
      ${bar}
      <main class="content" data-k="c-${esc(key)}">${body}</main>
      ${this._navBar()}
    </div>
    ${this._sheet ? this._sheetHtml() : ""}
    ${this._toast ? `<div class="toast" data-k="toast">${esc(this._toast)}</div>` : ""}`;
  }

  _navBar() {
    const v = this._nav.view;
    const inMore = v === "more" || (v === "page" && this._nav.from === "more");
    const inHome = v === "home" || (v === "page" && this._nav.from !== "more");
    const b = (id, label, icon, sel) =>
      `<button class="${sel ? "sel" : ""}" aria-label="${label}" ${this.h(() => this._go({ view: id }))}><ha-icon icon="${icon}"></ha-icon>${label}</button>`;
    return `<div class="navwrap"><nav class="nav">
      ${b("home", "Hjem", "mdi:home-variant", inHome)}
      ${b("lights", "Lys", "mdi:lightbulb-group", v === "lights")}
      ${b("heat", "Varme", "mdi:radiator", v === "heat")}
      ${b("more", "Mer", "mdi:dots-grid", inMore)}
    </nav></div>`;
  }

  _go(nav) {
    this._nav = nav;
    this._haptic("light");
    this._render();
  }

  /* ---------- Synlighet ---------- */

  _visible(o, ignoreWhen) {
    if (!o) return false;
    const u = this._uid;
    if (this._edit) return true;
    if (o.hide_for && o.hide_for.includes(u)) return false;
    if (o.show_for && o.show_for.length && !o.show_for.includes(u)) return false;
    if (!ignoreWhen && o.when && !this._cond(o.when)) return false;
    return true;
  }

  _hiddenNote(o) {
    if (!this._edit) return "";
    const names = [];
    for (const id of o.hide_for || []) names.push(this._cfg.users[id] || "en bruker");
    let s = names.length ? `<span class="badge">Skjult for ${esc(names.join(", "))}</span>` : "";
    if (o.show_for && o.show_for.length) s += `<span class="badge">Bare ${esc(o.show_for.map((i) => this._cfg.users[i] || "?").join(", "))}</span>`;
    if (o.when) s += `<span class="badge">Når ${esc(o.when.entity)}</span>`;
    return s;
  }

  _cond(w) {
    const conds = Array.isArray(w) ? w : [w];
    return conds.every((c) => {
      const s = this._hass.states[c.entity];
      const st = s ? s.state : "unavailable";
      if (c.state !== undefined) return [].concat(c.state).includes(st);
      if (c.state_not !== undefined) return ![].concat(c.state_not).includes(st);
      if (c.above !== undefined && !(Number(st) > c.above)) return false;
      if (c.below !== undefined && !(Number(st) < c.below)) return false;
      return true;
    });
  }

  /* ---------- Formatering ---------- */

  _s(id) { return this._hass.states[id]; }

  _fmt(id, attr) {
    const s = this._s(id);
    if (!s) return "–";
    try {
      if (attr) return this._hass.formatEntityAttributeValue ? this._hass.formatEntityAttributeValue(s, attr) : String(s.attributes[attr] ?? "–");
      if (this._hass.formatEntityState) return this._hass.formatEntityState(s);
    } catch (e) { /* faller tilbake */ }
    const u = s.attributes.unit_of_measurement;
    return `${s.state}${u ? " " + u : ""}`;
  }

  _name(id, item) {
    if (item && item.name) return item.name;
    const s = this._s(id);
    return (s && s.attributes.friendly_name) || id || "";
  }

  _icon(id, item, fallback) {
    if (item && item.icon) return item.icon;
    const s = this._s(id);
    if (s && s.attributes.icon) return s.attributes.icon;
    return fallback || DOMAIN_ICON[domainOf(id)] || "mdi:circle-outline";
  }

  _num(id, attr) {
    const s = this._s(id);
    if (!s) return NaN;
    return Number(attr ? s.attributes[attr] : s.state);
  }

  _isOn(id) {
    const s = this._s(id);
    if (!s) return false;
    return ["on", "open", "opening", "playing", "home", "cleaning", "heat", "cool", "heat_cool", "unlocked", "active"].includes(s.state);
  }

  /* ---------- Handlinger ---------- */

  async _call(service, data = {}, target) {
    const [d, s] = service.split(".");
    try {
      await this._hass.callService(d, s, data, target);
      this._haptic("success");
    } catch (err) {
      this._showToast(`Feil: ${err.message || err}`);
      this._haptic("failure");
    }
  }

  _confirm(text, fn) {
    if (!text) return fn();
    this._sheet = { kind: "confirm", text, fn };
    this._render();
  }

  _more(id) {
    if (!id) return;
    this._haptic("medium");
    this.dispatchEvent(new CustomEvent("hass-more-info", { detail: { entityId: id }, bubbles: true, composed: true }));
  }

  _haptic(type) {
    this.dispatchEvent(new CustomEvent("haptic", { detail: type, bubbles: true, composed: true }));
  }

  _navigate(path) {
    if (!path) return;
    if (/^https?:/.test(path)) { window.open(path, "_blank"); return; }
    history.pushState(null, "", path);
    window.dispatchEvent(new CustomEvent("location-changed", { detail: { replace: false } }));
  }

  _showToast(msg) {
    this._toast = msg;
    this._render();
    clearTimeout(this._toastT);
    this._toastT = setTimeout(() => { this._toast = null; this._render(); }, 2600);
  }

  /* Kjører en elementhandling: egen action, eller noe fornuftig ut fra domenet */
  _runItem(it) {
    const go = () => {
      if (it.open) return this._openTarget(it.open);
      if (it.path) return this._navigate(it.path);
      if (it.action) {
        const a = it.action;
        return this._call(a.service, a.data || {}, a.target || (it.entity ? { entity_id: it.entity } : undefined));
      }
      const id = it.entity;
      const d = domainOf(id);
      if (d === "scene") return this._call("scene.turn_on", {}, { entity_id: id });
      if (d === "script") return this._call(this._isOn(id) ? "script.turn_off" : "script.turn_on", {}, { entity_id: id });
      if (d === "button" || d === "input_button") return this._call(`${d}.press`, {}, { entity_id: id });
      if (d === "automation" && it.trigger) return this._call("automation.trigger", { skip_condition: true }, { entity_id: id });
      return this._call("homeassistant.toggle", {}, { entity_id: id });
    };
    this._confirm(it.confirm, go);
  }

  _openTarget(t) {
    if (t === "lights" || t === "heat" || t === "more" || t === "home") return this._go({ view: t });
    if (t.startsWith("room:")) return this._go({ view: "page", id: t.slice(5), from: "home" });
    if (t.startsWith("more:")) return this._go({ view: "page", id: t.slice(5), from: "more" });
    if (t.startsWith("path:")) return this._navigate(t.slice(5));
    if (t.startsWith("info:")) return this._more(t.slice(5));
  }

  /* ---------- Hendelser ---------- */

  _onDown(e) {
    if (e.button && e.button !== 0) return;
    const sl = e.target.closest?.("[data-slide]");
    const mo = e.target.closest?.("[data-more]");
    if (sl && !this._edit) {
      const id = sl.dataset.slide;
      const cur = this._lightPct(id);
      this._drag = { el: sl, id, x0: e.clientX, y0: e.clientY, rect: sl.getBoundingClientRect(), moved: false, pct: cur, pid: e.pointerId };
      this._lp = setTimeout(() => {
        if (this._drag && !this._drag.moved) { this._drag.long = true; this._more(id); }
      }, 550);
      return;
    }
    if (mo && !this._edit) {
      const id = mo.dataset.more;
      this._press = { x0: e.clientX, y0: e.clientY };
      this._lp = setTimeout(() => {
        this._press = null;
        this._suppressUntil = Date.now() + 600;
        this._suppressEl = mo;
        this._more(id);
      }, 550);
    }
  }

  _onMove(e) {
    const d = this._drag;
    if (d) {
      const dx = e.clientX - d.x0;
      const dy = e.clientY - d.y0;
      if (!d.moved && Math.abs(dy) > 10 && Math.abs(dy) > Math.abs(dx)) { this._onCancel(); return; }
      if (!d.moved && Math.abs(dx) > 8) {
        d.moved = true;
        clearTimeout(this._lp);
        try { d.el.setPointerCapture(d.pid); } catch (err) { /* ok */ }
        d.el.classList.add("drag", "on");
      }
      if (d.moved) {
        d.pct = clamp(Math.round(((e.clientX - d.rect.left) / d.rect.width) * 100), 1, 100);
        const f = d.el.querySelector(".fill");
        const v = d.el.querySelector(".val");
        if (f) f.style.width = d.pct + "%";
        if (v) v.textContent = d.pct + " %";
      }
      return;
    }
    if (this._press && (Math.abs(e.clientX - this._press.x0) > 10 || Math.abs(e.clientY - this._press.y0) > 10)) {
      clearTimeout(this._lp);
      this._press = null;
    }
  }

  _onUp() {
    clearTimeout(this._lp);
    this._press = null;
    const d = this._drag;
    if (!d) return;
    this._drag = null;
    this._suppressUntil = Date.now() + 450;
    this._suppressEl = d.el;
    d.el.classList.remove("drag");
    if (d.long) return;
    if (d.moved) {
      this._pend[d.id] = { v: d.pct, t: Date.now() };
      this._call("light.turn_on", { brightness_pct: d.pct }, { entity_id: d.id });
    } else {
      this._call("homeassistant.toggle", {}, { entity_id: d.id });
    }
    this._render();
  }

  _onCancel() {
    clearTimeout(this._lp);
    this._press = null;
    if (this._drag) { this._drag.el.classList.remove("drag"); this._drag = null; this._render(); }
  }

  _onClick(e) {
    if (Date.now() < this._suppressUntil && this._suppressEl && this._suppressEl.contains(e.target)) {
      this._suppressUntil = 0;
      e.stopPropagation();
      e.preventDefault();
      return;
    }
    if (e.target.closest?.("[data-slide]") && !this._edit) return;
    const el = e.target.closest?.("[data-h]");
    if (!el) {
      if (e.target.classList?.contains("scrim")) { this._sheet = null; this._render(); }
      return;
    }
    const fn = this._h[Number(el.dataset.h)];
    if (fn) { e.preventDefault(); fn(el, e); }
  }

  _onChange(e) {
    const el = e.target.closest?.("[data-c]");
    if (!el) return;
    const fn = this._h[Number(el.dataset.c)];
    if (fn) fn(el.type === "checkbox" ? el.checked : el.value, el);
  }

  _onKey(e) {
    if (e.key === "Enter" && e.target.dataset?.enter !== undefined) {
      const fn = this._h[Number(e.target.dataset.enter)];
      if (fn) { e.preventDefault(); fn(e.target.value, e.target); }
    }
    if (e.key === "Escape" && this._sheet) { this._sheet = null; this._render(); }
  }

  /* ------------------------------------------------------------------ */
  /* Skjermer                                                             */
  /* ------------------------------------------------------------------ */

  _home() {
    const c = this._cfg;
    const hass = this._hass;
    const hr = new Date().getHours();
    const hello = hr < 5 ? "God natt" : hr < 10 ? "God morgen" : hr < 17 ? "God dag" : "God kveld";
    const first = String(hass.user?.name || "").split(" ")[0];
    const date = new Date().toLocaleDateString("nb-NO", { weekday: "long", day: "numeric", month: "long" });
    const wid = c.home.weather;
    const w = wid && this._s(wid);
    const subParts = [];
    if (w) subParts.push(`${NB_WEATHER[w.state] || w.state} · ${Math.round(Number(w.attributes.temperature))} °C ute`);
    if (c.home.price && this._s(c.home.price)) {
      const p = this._num(c.home.price);
      subParts.push(`strøm ${Math.round(p * (c.home.price_factor ?? 100))} øre`);
    }
    for (const id of c.home.info || []) if (this._s(id)) subParts.push(this._fmt(id));
    const wPill = w
      ? `<button class="pill" aria-label="Været" ${this.h(() => (c.home.weather_open ? this._openTarget(c.home.weather_open) : this._more(wid)))}>
          <ha-icon icon="${WEATHER_ICON[w.state] || "mdi:weather-partly-cloudy"}"></ha-icon>${Math.round(Number(w.attributes.temperature))}°</button>`
      : "";

    let out = `<div class="top"><div class="grow"><div class="date">${esc(date)}</div>
      <div class="h1">${esc(hello)}${first ? ", " + esc(first) : ""}</div>
      ${subParts.length ? `<div class="sub">${esc(subParts.join(" · "))}</div>` : ""}</div>${wPill}</div>`;

    const before = this._itemsGrid(c.home.before, ["home", "before"], { compact: true });
    if (c.home.before.some((it) => this._visible(it)) || this._edit) out += `<div style="margin-bottom:14px">${before}</div>`;

    /* brikker */
    const chips = c.home.chips.filter((ch) => this._visible(ch)).map((ch, i) => this._chip(ch, i)).filter(Boolean);
    if (chips.length || this._edit) {
      out += `<div class="chips">${chips.join("")}${this._edit ? `<button class="chip blue" ${this.h(() => this._openChipsEditor())}><ha-icon icon="mdi:pencil"></ha-icon>Endre brikker</button>` : ""}</div>`;
    }

    /* hurtigvalg */
    const quick = c.home.quick;
    if (quick.length || this._edit) {
      out += `<div class="quick">`;
      quick.forEach((it, i) => {
        if (!this._visible(it)) return;
        const running = it.entity && domainOf(it.entity) === "script" && this._isOn(it.entity);
        out += `<div class="it ${it.hide_for?.length && this._edit ? "hiddenfor" : ""}" style="grid-column:auto">
          ${this._edit ? this._etools(["home", "quick"], i) : ""}
          <button class="qbtn ${i === 0 ? "primary" : ""} ${running ? "running" : ""}" style="width:100%" ${this.h(() => this._runItem(it))}>
            <ha-icon icon="${esc(it.icon || this._icon(it.entity, it, "mdi:gesture-tap"))}"></ha-icon>${esc(it.name || this._name(it.entity))}</button></div>`;
      });
      out += `</div>`;
      if (this._edit) out += `<button class="add" style="margin-top:-6px;margin-bottom:12px" ${this.h(() => this._openItemEditor(["home", "quick"], -1, "button"))}><ha-icon icon="mdi:plus"></ha-icon>Hurtigknapp</button>`;
    }

    /* rom */
    out += `<div class="label"><span>${esc(c.home.rooms_title || "Rom")}</span></div><div class="rooms">`;
    const rooms = c.rooms.filter((p) => this._visible(p));
    rooms.forEach((p) => {
      const idx = c.rooms.indexOf(p);
      out += this._roomTile(p, idx, rooms.length);
    });
    out += `</div>`;
    if (this._edit) out += `<button class="add" ${this.h(() => this._addPage("rooms"))}><ha-icon icon="mdi:plus"></ha-icon>Nytt rom</button>`;

    if (c.home.after.length || this._edit) {
      out += `<div style="height:14px"></div>` + this._itemsGrid(c.home.after, ["home", "after"]);
    }
    return out;
  }

  _chip(ch, i) {
    let content = "";
    let tone = ch.tone || "";
    let icon = ch.icon;
    if (ch.type === "lights") {
      const n = this._lightsOn().length;
      content = n === 0 ? "Alle lys av" : `${n} lys på`;
      icon = icon || "mdi:lightbulb-group";
      tone = tone || (n ? "warm" : "");
    } else if (ch.type === "entity") {
      if (!this._s(ch.entity)) return "";
      const val = ch.attribute ? this._fmt(ch.entity, ch.attribute) : this._fmt(ch.entity);
      content = ch.label ? ch.label.replace("{}", val) : val;
      icon = icon || this._icon(ch.entity);
    } else {
      content = ch.label || "";
    }
    const open = ch.open || (ch.entity ? "info:" + ch.entity : "");
    return `<button class="chip ${esc(tone)}" ${this.h(() => this._openTarget(open))}>${icon ? `<ha-icon icon="${esc(icon)}"></ha-icon>` : ""}${esc(content)}</button>`;
  }

  _roomTile(p, idx, total) {
    const main = p.main;
    const on = main && this._isOn(main);
    const lightsOn = this._pageLights(p).filter((id) => this._isOn(id)).length;
    const parts = [];
    if (lightsOn) parts.push(`${lightsOn} lys`);
    else if (main && domainOf(main) !== "light" && this._s(main)) parts.push(this._fmt(main));
    else parts.push("Av");
    if (p.temp && this._s(p.temp)) parts.push(this._fmt(p.temp));
    for (const id of p.info || []) if (this._s(id)) parts.push(this._fmt(id));
    const wide = p.wide ? "wide" : "";
    const tg = main && ["light", "switch", "input_boolean", "fan", "cover"].includes(domainOf(main))
      ? `<button class="tg" aria-label="Av/på ${esc(p.name)}" ${this.h(() => this._call(domainOf(main) === "cover" ? "cover.toggle" : "homeassistant.toggle", {}, { entity_id: main }))}><ha-icon icon="${esc(domainOf(main) === "cover" ? "mdi:garage-variant" : "mdi:power")}"></ha-icon></button>`
      : "";
    const tools = this._edit ? this._etools(["rooms"], idx, { page: true }) : "";
    return `<div class="room ${on || lightsOn ? "on" : ""} ${wide} ${this._edit && p.hide_for?.length ? "hiddenfor" : ""}" data-k="room-${esc(p.id)}"
        role="button" tabindex="0" ${this.h(() => this._go({ view: "page", id: p.id, from: "home" }))}>
      ${tools}
      <span class="nm">${p.icon ? `<ha-icon icon="${esc(p.icon)}" style="--mdc-icon-size:18px;margin-right:6px;vertical-align:-3px"></ha-icon>` : ""}${esc(p.name)}${this._hiddenNote(p)}</span>
      <span class="st">${esc(parts.join(" · "))}</span>${tg}</div>`;
  }

  _pageLights(p) {
    const ids = [];
    for (const t of p.tabs || []) for (const it of t.items || []) if (it.entity && domainOf(it.entity) === "light") ids.push(it.entity);
    return ids;
  }

  _lightsOn() {
    const ex = (this._cfg.lights.exclude || []).map((p) => (p.startsWith("/") ? new RegExp(p.slice(1, p.lastIndexOf("/"))) : p));
    return Object.keys(this._hass.states).filter((id) => {
      if (!id.startsWith("light.")) return false;
      const s = this._hass.states[id];
      if (s.state !== "on") return false;
      if (s.attributes.entity_id || s.attributes.is_hue_group) return false;
      const ent = this._hass.entities?.[id];
      if (ent && (ent.hidden || ent.entity_category)) return false;
      return !ex.some((p) => (p instanceof RegExp ? p.test(id) : id.includes(p.replace(/\*/g, ""))));
    });
  }

  _lightsView() {
    const c = this._cfg;
    const on = this._lightsOn();
    let out = `<div class="top"><div class="grow"><div class="h1">Lys</div>
      <div class="sub">${on.length ? `${on.length} lys er på` : "Alle lys er av"}</div></div></div>`;
    if (c.lights.actions.length || this._edit) out += this._itemsGrid(c.lights.actions, ["lights", "actions"]) + `<div style="height:14px"></div>`;
    out += `<div class="seg" style="margin-bottom:14px">
      <button class="${this._lightsMode === "on" ? "sel" : ""}" ${this.h(() => { this._lightsMode = "on"; this._render(); })}>På nå</button>
      <button class="${this._lightsMode === "all" ? "sel" : ""}" ${this.h(() => { this._lightsMode = "all"; this._render(); })}>Alle rom</button></div>`;
    if (this._lightsMode === "on") {
      out += on.length
        ? `<div class="grid">${on.sort((a, b) => this._name(a).localeCompare(this._name(b), "nb")).map((id) => `<div class="it">${this._lightStrip(id, {})}</div>`).join("")}</div>`
        : `<div class="empty"><ha-icon icon="mdi:weather-night" style="--mdc-icon-size:34px"></ha-icon><br>Alle lys er av</div>`;
    } else {
      for (const p of c.rooms.filter((r) => this._visible(r))) {
        const items = [];
        for (const t of p.tabs) for (const it of t.items) if (it.entity && domainOf(it.entity) === "light" && this._visible(it)) items.push(it);
        if (!items.length) continue;
        out += `<div class="label"><span>${esc(p.name)}</span></div><div class="grid">${items.map((it) => `<div class="it">${this._lightStrip(it.entity, it)}</div>`).join("")}</div>`;
      }
    }
    return out;
  }

  _heatView() {
    const c = this._cfg;
    let sub = "";
    if (c.heat.price && this._s(c.heat.price)) {
      sub = this._priceSentence(c.heat.price, c.heat.price_entity_type);
    }
    let out = `<div class="top"><div class="grow"><div class="h1">Varme</div>${sub ? `<div class="sub">${esc(sub)}</div>` : ""}</div></div>`;
    out += this._itemsGrid(c.heat.items, ["heat", "items"], { listClimate: true });
    return out;
  }

  _moreView() {
    const c = this._cfg;
    let out = `<div class="top"><div class="grow"><div class="h1">Mer</div></div></div>`;
    const pages = c.more.filter((p) => this._visible(p));
    const large = pages.filter((p) => p.size === "large");
    const small = pages.filter((p) => p.size !== "large");
    for (const p of large) {
      const idx = c.more.indexOf(p);
      const info = (p.info || []).filter((id) => this._s(id)).map((id) => this._fmt(id)).join(" · ");
      const big = p.big && this._s(p.big) ? this._fmt(p.big) : "";
      const pct = p.big && this._s(p.big) && this._s(p.big).attributes.unit_of_measurement === "%" ? clamp(this._num(p.big), 0, 100) : null;
      out += `<div class="it ${this._edit && p.hide_for?.length ? "hiddenfor" : ""}" data-k="mp-${esc(p.id)}">${this._edit ? this._etools(["more"], idx, { page: true }) : ""}
        <button class="big" ${this.h(() => this._go({ view: "page", id: p.id, from: "more" }))}>
        <div class="row"><div class="grow"><div class="ttl"><ha-icon icon="${esc(p.icon || "mdi:dots-grid")}" style="--mdc-icon-size:19px;margin-right:6px;vertical-align:-4px"></ha-icon>${esc(p.name)}${this._hiddenNote(p)}</div>
        <div class="small ellip" style="margin-top:3px">${esc(info)}</div></div>${big ? `<div class="hv">${esc(big)}</div>` : ""}</div>
        ${pct !== null ? `<div class="bar" style="height:8px;margin-top:10px"><div style="width:${pct}%;background:var(--good)"></div></div>` : ""}
        </button></div>`;
    }
    if (small.length) {
      out += `<div class="tiles">`;
      for (const p of small) {
        const idx = c.more.indexOf(p);
        const alert = p.alert && this._cond(p.alert);
        out += `<div class="it ${this._edit && p.hide_for?.length ? "hiddenfor" : ""}" style="grid-column:auto" data-k="mp-${esc(p.id)}">${this._edit ? this._etools(["more"], idx, { page: true }) : ""}
          <button class="tile ${alert ? "alert" : ""}" style="width:100%" ${this.h(() => (p.path && !this._edit ? this._navigate(p.path) : this._go({ view: "page", id: p.id, from: "more" })))}>
          <ha-icon icon="${esc(p.icon || "mdi:dots-grid")}"></ha-icon>${esc(p.name)}</button></div>`;
      }
      out += `</div>`;
    }
    if (this._edit) out += `<button class="add" ${this.h(() => this._addPage("more"))}><ha-icon icon="mdi:plus"></ha-icon>Ny side under Mer</button>`;

    const t = this._theme || "auto";
    out += `<div class="label"><span>Utseende</span></div>
      <div class="seg" role="radiogroup" aria-label="Utseende">
        <button class="${t === "light" ? "sel" : ""}" ${this.h(() => this._setTheme("light"))}>Lys</button>
        <button class="${t === "dark" ? "sel" : ""}" ${this.h(() => this._setTheme("dark"))}>Mørk</button>
        <button class="${t === "auto" ? "sel" : ""}" ${this.h(() => this._setTheme("auto"))}>Følg telefonen</button>
      </div>`;
    if (this._canEdit && !this._edit) {
      out += `<button class="btn soft" style="margin-top:14px" ${this.h(() => this._startEdit())}><ha-icon icon="mdi:pencil"></ha-icon>Rediger appen</button>`;
    }
    out += `<div class="small" style="text-align:center;margin-top:18px">Smarthus ${VERSION}</div>`;
    return out;
  }

  _findPage(id) {
    const c = this._cfg;
    let list = "rooms";
    let idx = c.rooms.findIndex((p) => p.id === id);
    if (idx < 0) { list = "more"; idx = c.more.findIndex((p) => p.id === id); }
    return idx < 0 ? null : { page: c[list][idx], list, idx };
  }

  _pageView() {
    const f = this._findPage(this._nav.id);
    if (!f) { this._nav = { view: "home" }; return this._home(); }
    const p = f.page;
    const tabs = p.tabs.filter((t) => this._visible(t));
    let sel = this._tabSel[p.id] ?? 0;
    if (sel >= p.tabs.length) sel = 0;
    if (!this._edit && !this._visible(p.tabs[sel])) sel = p.tabs.indexOf(tabs[0]);
    const tab = p.tabs[sel];
    const info = [];
    if (p.temp && this._s(p.temp)) info.push(this._fmt(p.temp));
    for (const id of p.info || []) if (this._s(id)) info.push(this._fmt(id));
    const back = this._nav.from === "more" ? "more" : "home";

    let out = `<div class="top"><button class="back" aria-label="Tilbake" ${this.h(() => this._go({ view: back }))}><ha-icon icon="mdi:chevron-left"></ha-icon></button>
      <div class="grow"><div class="h1" style="font-size:24px">${esc(p.name)}</div>${info.length ? `<div class="sub">${esc(info.join(" · "))}</div>` : ""}</div>
      ${this._edit ? `<button class="pill" aria-label="Sideinnstillinger" ${this.h(() => this._openPageEditor(f.list, f.idx))}><ha-icon icon="mdi:cog"></ha-icon></button>` : ""}</div>`;

    if (this._edit) {
      out += `<div class="tabedit">`;
      p.tabs.forEach((t, i) => {
        out += `<div class="te ${i === sel ? "sel" : ""}"><span ${this.h(() => { this._tabSel[p.id] = i; this._render(); })} style="cursor:pointer;padding-right:4px">${esc(t.name)}</span>
          <button aria-label="Flytt til venstre" ${this.h(() => this._moveTab(f, i, -1))}><ha-icon icon="mdi:chevron-left"></ha-icon></button>
          <button aria-label="Flytt til høyre" ${this.h(() => this._moveTab(f, i, 1))}><ha-icon icon="mdi:chevron-right"></ha-icon></button>
          <button aria-label="Endre fane" ${this.h(() => this._openTabEditor(f, i))}><ha-icon icon="mdi:pencil"></ha-icon></button></div>`;
      });
      out += `<button class="te" style="padding:0 14px;color:var(--blue)" ${this.h(() => this._addTab(f))}>+ Ny fane</button></div>`;
    } else if (tabs.length > 1) {
      out += `<div class="tabs" role="tablist">${tabs
        .map((t) => {
          const i = p.tabs.indexOf(t);
          return `<button class="tab ${i === sel ? "sel" : ""}" role="tab" aria-selected="${i === sel}" ${this.h(() => { this._tabSel[p.id] = i; this._haptic("selection"); this._render(); })}>${esc(t.name)}</button>`;
        })
        .join("")}</div>`;
    }
    if (tab) out += `<div data-k="tab-${sel}">${this._itemsGrid(tab.items, [f.list, f.idx, "tabs", sel, "items"])}</div>`;
    return out;
  }

  /* ------------------------------------------------------------------ */
  /* Elementer                                                            */
  /* ------------------------------------------------------------------ */

  _itemsGrid(items, path, opts = {}) {
    let out = `<div class="grid">`;
    let climateRun = [];
    const flushClimate = () => {
      if (!climateRun.length) return;
      out += `<div class="it w6"><div class="list">${climateRun.map(([it, i]) => this._climateRow(it, path, i)).join("")}</div></div>`;
      climateRun = [];
    };
    items.forEach((it, i) => {
      if (!this._visible(it)) return;
      if (opts.listClimate && it.type === "climate" && !it.modes && !it.presets && !this._edit) { climateRun.push([it, i]); return; }
      flushClimate();
      const w = it.w || TYPES[it.type]?.w || 6;
      let inner;
      try { inner = this._item(it, path, i); } catch (err) { inner = `<div class="card small">Feil i element: ${esc(err.message)}</div>`; }
      out += `<div class="it w${w} ${this._edit && (it.hide_for?.length || it.show_for?.length) ? "hiddenfor" : ""}" data-k="it-${i}-${esc(it.type)}-${esc(it.entity || "")}">
        ${this._edit ? this._etools(path, i) : ""}${inner}</div>`;
    });
    flushClimate();
    out += `</div>`;
    if (this._edit) out += `<button class="add" ${this.h(() => this._openItemEditor(path, -1))}><ha-icon icon="mdi:plus"></ha-icon>Legg til</button>`;
    return out;
  }

  _item(it, path, i) {
    const t = it.type;
    const s = it.entity ? this._s(it.entity) : null;
    if (it.entity && !s && !["link", "heading", "calendar", "text"].includes(t)) {
      return `<div class="val-card"><span class="n">${esc(it.name || it.entity)}</span><span class="v" style="font-size:15px">Finnes ikke</span></div>`;
    }
    const fn = {
      light: () => this._lightStrip(it.entity, it),
      toggle: () => this._toggle(it),
      climate: () => this._climate(it),
      value: () => this._value(it),
      button: () => this._button(it),
      media: () => this._media(it),
      vacuum: () => this._vacuum(it),
      areaclean: () => this._areaClean(it, path, i),
      select: () => this._select(it),
      number: () => this._number(it),
      time: () => this._time(it),
      input: () => this._input(it),
      cover: () => this._cover(it),
      lock: () => this._lock(it),
      camera: () => this._camera(it),
      timer: () => this._timerItem(it),
      todo: () => this._todoItem(it),
      calendar: () => this._calendar(it),
      weather: () => this._weather(it),
      graph: () => this._graph(it),
      pricechart: () => this._priceChart(it),
      text: () => this._text(it),
      link: () => this._link(it),
      heading: () => `<div class="heading">${it.icon ? `<ha-icon icon="${esc(it.icon)}"></ha-icon>` : ""}${esc(it.name || "")}</div>`,
      updates: () => this._updates(it),
      batteries: () => this._batteries(it),
      lightson: () => this._lightsOnItem(it),
      card: () => this._embed(it),
    }[t];
    return fn ? fn() : `<div class="card small">Ukjent type: ${esc(t)}</div>`;
  }

  _lightPct(id) {
    const p = this._pend[id];
    if (p && Date.now() - p.t < 6000) return p.v;
    const s = this._s(id);
    if (!s || s.state !== "on") return 0;
    const b = Number(s.attributes.brightness);
    return isNaN(b) ? 100 : Math.max(1, Math.round((b / 255) * 100));
  }

  _dimmable(id) {
    const s = this._s(id);
    const modes = s?.attributes?.supported_color_modes || [];
    return modes.length && !(modes.length === 1 && modes[0] === "onoff");
  }

  _lightStrip(id, it) {
    const s = this._s(id);
    if (!s) return `<div class="strip"><div class="in"><span class="nm">${esc(it.name || id)}</span><span class="val">Finnes ikke</span></div></div>`;
    const on = s.state === "on";
    const dim = this._dimmable(id);
    const pct = on ? (dim ? this._lightPct(id) : 100) : 0;
    const name = this._name(id, it);
    const val = s.state === "unavailable" ? "Utilgjengelig" : on ? (dim ? `${pct} %` : "På") : "Av";
    const rgb = on && s.attributes.rgb_color ? `rgb(${s.attributes.rgb_color.join(",")})` : "";
    const icon = this._icon(id, it, "mdi:lightbulb");
    if (this._edit) {
      return `<div class="strip ${on ? "on" : ""}"><div class="fill" style="width:${pct}%"></div><div class="in"><span class="ic"><ha-icon icon="${esc(icon)}"></ha-icon></span><span class="nm">${esc(name)}${this._hiddenNote(it)}</span><span class="val">${val}</span></div></div>`;
    }
    return `<div class="strip ${on ? "on" : ""} ${dim ? "" : "off-only"}" data-slide="${esc(id)}" role="slider" tabindex="0" aria-label="${esc(name)}" aria-valuenow="${pct}">
      <div class="fill" style="width:${pct}%"></div>
      <div class="in"><span class="ic" ${rgb ? `style="background:${rgb};color:#1a1206"` : ""}><ha-icon icon="${esc(icon)}"></ha-icon></span>
      <span class="nm">${esc(name)}</span><span class="val">${val}</span></div></div>`;
  }

  _toggle(it) {
    const id = it.entity;
    const on = this._isOn(id);
    const st = it.subtitle !== undefined ? it.subtitle : this._fmt(id);
    return `<button class="tgl ${on ? "on" : ""}" data-more="${esc(id)}" ${this.h(() => this._confirm(it.confirm, () => this._call("homeassistant.toggle", {}, { entity_id: id })))}>
      <span class="ic"><ha-icon icon="${esc(this._icon(id, it))}"></ha-icon></span>
      <span class="grow"><span class="nm" style="display:block">${esc(this._name(id, it))}${this._hiddenNote(it)}</span>${st ? `<span class="st">${esc(st)}</span>` : ""}</span>
      <span class="sw" aria-hidden="true"></span></button>`;
  }

  _target(id) {
    const p = this._pend[id];
    if (p && Date.now() - p.t < 6000) return p.v;
    return this._num(id, "temperature");
  }

  _bump(id, dir) {
    const s = this._s(id);
    const step = Number(s.attributes.target_temp_step) || (s.attributes.temperature_unit === "°F" ? 1 : 0.5);
    let cur = this._target(id);
    if (isNaN(cur)) cur = Number(s.attributes.current_temperature) || 20;
    const min = Number(s.attributes.min_temp ?? 5);
    const max = Number(s.attributes.max_temp ?? 35);
    const nv = clamp(Math.round((cur + dir * step) / step) * step, min, max);
    this._pend[id] = { v: nv, t: Date.now() };
    this._haptic("selection");
    this._render();
    clearTimeout(this._pend[id + "#t"]);
    this._pend[id + "#t"] = setTimeout(() => this._call("climate.set_temperature", { temperature: nv }, { entity_id: id }), 700);
  }

  _climateLine(id) {
    const s = this._s(id);
    const parts = [];
    if (s.attributes.hvac_action) parts.push(this._fmt(id, "hvac_action"));
    else parts.push(NB_MODES[s.state] || this._fmt(id));
    if (s.attributes.current_temperature != null) parts.push(`nå ${String(s.attributes.current_temperature).replace(".", ",")}°`);
    return parts.join(" · ");
  }

  _climateRow(it, path, i) {
    const id = it.entity;
    const s = this._s(id);
    if (!s) return `<div class="lrow"><span class="grow">${esc(it.name || id)} – finnes ikke</span></div>`;
    const t = this._target(id);
    return `<div class="lrow" data-k="cr-${esc(id)}">
      <div class="grow" data-more="${esc(id)}" ${this.h(() => {})}><div class="ttl" style="font-size:15px">${esc(this._name(id, it))}</div><div class="small">${esc(this._climateLine(id))}</div></div>
      <button class="round" aria-label="Lavere" ${this.h(() => this._bump(id, -1))}>−</button>
      <span class="tv thermo" style="font-weight:800;text-align:center">${isNaN(t) ? "–" : String(t).replace(".", ",") + "°"}</span>
      <button class="round" aria-label="Høyere" ${this.h(() => this._bump(id, 1))}>+</button></div>`;
  }

  _climate(it) {
    const id = it.entity;
    const s = this._s(id);
    const t = this._target(id);
    let modes = "";
    const ml = it.modes === true ? s.attributes.hvac_modes : it.modes;
    if (ml && ml.length) {
      modes = `<div class="seg hot" style="margin-top:12px">${ml
        .map((m) => `<button class="${s.state === m ? "sel" : ""}" ${this.h(() => this._call("climate.set_hvac_mode", { hvac_mode: m }, { entity_id: id }))}>${esc(NB_MODES[m] || m)}</button>`)
        .join("")}</div>`;
    }
    let presets = "";
    const pl = it.presets === true ? s.attributes.preset_modes : it.presets;
    if (pl && pl.length) {
      presets = `<div class="opts" style="margin-top:10px">${pl
        .map((m) => `<button class="opt ${s.attributes.preset_mode === m ? "sel" : ""}" ${this.h(() => this._call("climate.set_preset_mode", { preset_mode: m }, { entity_id: id }))}>${esc(NB_PRESETS[m] || m)}</button>`)
        .join("")}</div>`;
    }
    const off = s.state === "off";
    return `<div class="card thermo"><div class="row">
      <div class="grow" data-more="${esc(id)}" ${this.h(() => {})}><div class="ttl">${esc(this._name(id, it))}${this._hiddenNote(it)}</div><div class="small">${esc(this._climateLine(id))}</div></div>
      <button class="round" aria-label="Lavere" ${this.h(() => this._bump(id, -1))}>−</button>
      <span class="tv" style="${off ? "color:var(--muted)" : ""}">${isNaN(t) ? "–" : String(t).replace(".", ",") + "°"}</span>
      <button class="round" aria-label="Høyere" ${this.h(() => this._bump(id, 1))}>+</button></div>${modes}${presets}</div>`;
  }

  _value(it) {
    const id = it.entity;
    const s = this._s(id);
    let v = it.attribute ? this._fmt(id, it.attribute) + (it.suffix ? " " + it.suffix : "") : this._fmt(id);
    if (it.map && it.map[s.state] !== undefined) v = it.map[s.state];
    let extra = "";
    if (it.bar) {
      const min = it.bar.min ?? 0;
      const max = it.bar.max ?? 100;
      const n = clamp(((this._num(id) - min) / (max - min)) * 100, 0, 100);
      extra = `<div class="bar"><div style="width:${isNaN(n) ? 0 : n}%"></div></div>`;
    }
    if (it.graph) extra += this._spark(id, it.graph);
    const warn = it.alert && this._cond(it.alert);
    return `<button class="val-card" style="${warn ? "background:var(--bad-bg);color:var(--bad)" : ""}" data-more="${esc(id)}" ${this.h(() => (it.open ? this._openTarget(it.open) : this._more(id)))}>
      <span class="n">${esc(this._name(id, it))}${this._hiddenNote(it)}</span><span class="v">${esc(v)}</span>${extra}</button>`;
  }

  _button(it) {
    const id = it.entity;
    const running = id && domainOf(id) === "script" && this._isOn(id);
    const style = it.style || "";
    const icon = it.icon || (id ? this._icon(id, it, "mdi:gesture-tap") : "mdi:gesture-tap");
    return `<button class="btn ${it.w === 2 || !it.w ? "tall" : ""} ${esc(style)} ${running ? "running" : ""}" ${id ? `data-more="${esc(id)}"` : ""} ${this.h(() => this._runItem(it))}>
      <ha-icon icon="${esc(icon)}"></ha-icon><span>${esc(it.name || this._name(id))}${this._hiddenNote(it)}</span></button>`;
  }

  _link(it) {
    return `<button class="btn tall" ${this.h(() => (it.open ? this._openTarget(it.open) : this._navigate(it.path)))}>
      <ha-icon icon="${esc(it.icon || "mdi:arrow-right-circle")}"></ha-icon><span>${esc(it.name || "Åpne")}${this._hiddenNote(it)}</span></button>`;
  }

  _media(it) {
    const id = it.entity;
    const s = this._s(id);
    const a = s.attributes;
    const off = ["off", "unavailable", "standby"].includes(s.state);
    const playing = s.state === "playing";
    const title = a.media_title ? [a.media_title, a.media_artist].filter(Boolean).join(" – ") : this._fmt(id);
    const maxv = it.max_volume ?? 100;
    const vol = Math.round((Number(a.volume_level) || 0) * 100);
    const volRow = a.volume_level !== undefined && !off
      ? `<div class="vol-row"><ha-icon icon="mdi:volume-low"></ha-icon><input type="range" min="0" max="${maxv}" value="${Math.min(vol, maxv)}" aria-label="Volum"
          ${this.c((v) => this._call("media_player.volume_set", { volume_level: Number(v) / 100 }, { entity_id: id }))}><span class="small" style="min-width:34px;text-align:right">${vol} %</span></div>`
      : "";
    return `<div class="card media"><div class="row">
      <div class="grow" data-more="${esc(id)}" ${this.h(() => {})}><div class="ttl ellip">${esc(this._name(id, it))}${this._hiddenNote(it)}</div><div class="small ellip">${esc(title)}</div></div>
      <div class="ctr">
        ${!off ? `<button class="round" aria-label="Forrige" ${this.h(() => this._call("media_player.media_previous_track", {}, { entity_id: id }))}><ha-icon icon="mdi:skip-previous"></ha-icon></button>
        <button class="round" style="background:var(--accent);color:var(--accent-text)" aria-label="Spill/pause" ${this.h(() => this._call("media_player.media_play_pause", {}, { entity_id: id }))}><ha-icon icon="${playing ? "mdi:pause" : "mdi:play"}"></ha-icon></button>
        <button class="round" aria-label="Neste" ${this.h(() => this._call("media_player.media_next_track", {}, { entity_id: id }))}><ha-icon icon="mdi:skip-next"></ha-icon></button>` : ""}
        <button class="round" aria-label="Av/på" ${this.h(() => this._call(off ? "media_player.turn_on" : "media_player.turn_off", {}, { entity_id: id }))}><ha-icon icon="mdi:power"></ha-icon></button>
      </div></div>${volRow}</div>`;
  }

  _vacuum(it) {
    const id = it.entity;
    const s = this._s(id);
    const a = s.attributes;
    const cleaning = ["cleaning", "returning"].includes(s.state);
    let status = it.status && this._s(it.status) ? this._fmt(it.status) : this._fmt(id);
    const batt = it.battery && this._s(it.battery) ? this._fmt(it.battery) : a.battery_level != null ? `${a.battery_level} %` : "";
    const lines = [];
    for (const e of it.info || []) if (this._s(e)) lines.push(this._fmt(e));
    const err = it.error && this._s(it.error) && !BAD.includes(this._s(it.error).state) && this._s(it.error).state !== "none" ? this._fmt(it.error) : "";
    const fans = a.fan_speed_list && it.fan !== false
      ? `<div class="label" style="margin:14px 0 8px">Sugekraft</div><div class="opts">${a.fan_speed_list
          .map((f) => `<button class="opt ${a.fan_speed === f ? "sel" : ""}" ${this.h(() => this._call("vacuum.set_fan_speed", { fan_speed: f }, { entity_id: id }))}>${esc(NB_FAN[f] || f)}</button>`)
          .join("")}</div>`
      : "";
    const cmd = (svc, label, icon, cls = "soft") =>
      `<button class="btn tall ${cls}" ${this.h(() => this._call("vacuum." + svc, {}, { entity_id: id }))}><ha-icon icon="${icon}"></ha-icon>${label}</button>`;
    return `<div class="card"><div class="row" data-more="${esc(id)}" ${this.h(() => {})}>
        <div class="grow"><div class="ttl">${esc(this._name(id, it))} · ${esc(status)}${this._hiddenNote(it)}</div>
        ${lines.length ? `<div class="small" style="white-space:pre-line">${esc(lines.join("\n"))}</div>` : ""}</div>
        ${batt ? `<div class="small" style="font-weight:800">${esc(batt)}</div>` : ""}</div>
      ${err ? `<div class="warn">${esc(err)}</div>` : ""}
      <div class="btns" style="grid-template-columns:repeat(4,minmax(0,1fr));margin-top:12px">
        ${cleaning ? cmd("pause", "Pause", "mdi:pause", "dark") : cmd("start", "Start", "mdi:play", "dark")}
        ${cmd("stop", "Stopp", "mdi:stop")}
        ${cmd("return_to_base", "Hjem", "mdi:home-import-outline")}
        ${cmd("locate", "Finn", "mdi:map-marker-question-outline")}
      </div>
      ${it.spot ? `<div style="margin-top:6px">${cmd("clean_spot", "Punktrengjøring", "mdi:target")}</div>` : ""}
      ${fans}</div>`;
  }

  _areaClean(it, path, i) {
    const id = it.entity;
    const key = path.join(".") + "." + i;
    const sel = this._sel[key] || [];
    const areas = it.areas || [];
    const names = sel.map((a) => areas.find((x) => x.area === a)?.name).filter(Boolean);
    return `<div class="card"><div class="ttl" style="margin-bottom:10px">${esc(it.name || "Støvsug valgte rom")}${this._hiddenNote(it)}</div>
      <div class="opts">${areas
        .map((a) => `<button class="opt ${sel.includes(a.area) ? "sel" : ""}" aria-pressed="${sel.includes(a.area)}" ${this.h(() => {
          const cur = this._sel[key] || [];
          this._sel[key] = cur.includes(a.area) ? cur.filter((x) => x !== a.area) : [...cur, a.area];
          this._haptic("selection");
          this._render();
        })}>${esc(a.name)}</button>`)
        .join("")}</div>
      <button class="btn blue" style="margin-top:12px" ${sel.length ? "" : "disabled"} ${this.h(() => {
        if (!sel.length) return;
        this._confirm(`Støvsuge ${names.join(", ")}?`, () => {
          this._call("vacuum.clean_area", { cleaning_area_id: sel }, { entity_id: id });
          this._sel[key] = [];
          this._render();
        });
      })}>${sel.length ? `Start ${sel.length} ${sel.length === 1 ? "rom" : "rom"}` : "Velg rom over"}</button></div>`;
  }

  _select(it) {
    const id = it.entity;
    const s = this._s(id);
    const d = domainOf(id);
    const opts = s.attributes.options || [];
    return `<div class="card tight"><div class="row" style="margin-bottom:10px"><div class="ttl grow">${esc(this._name(id, it))}${this._hiddenNote(it)}</div></div>
      <div class="opts">${opts
        .map((o) => `<button class="opt ${s.state === o ? "sel" : ""}" ${this.h(() => this._call(`${d}.select_option`, { option: o }, { entity_id: id }))}>${esc(this._optLabel(id, o))}</button>`)
        .join("")}</div></div>`;
  }

  _optLabel(id, o) {
    const s = this._s(id);
    try {
      if (this._hass.formatEntityState && domainOf(id) === "select") return this._hass.formatEntityState(s, o);
    } catch (e) { /* ok */ }
    return o;
  }

  _number(it) {
    const id = it.entity;
    const s = this._s(id);
    const d = domainOf(id);
    const a = s.attributes;
    const min = Number(a.min ?? 0);
    const max = Number(a.max ?? 100);
    const step = Number(a.step ?? 1);
    const v = Number(s.state);
    const set = (nv) => this._call(`${d}.set_value`, { value: clamp(nv, min, max) }, { entity_id: id });
    const unit = a.unit_of_measurement ? " " + a.unit_of_measurement : "";
    if (it.style === "slider") {
      return `<div class="card tight"><div class="row"><div class="ttl grow">${esc(this._name(id, it))}${this._hiddenNote(it)}</div><span class="small" style="font-weight:800">${esc(String(v).replace(".", ","))}${esc(unit)}</span></div>
        <input type="range" min="${min}" max="${max}" step="${step}" value="${v}" aria-label="${esc(this._name(id, it))}" ${this.c((nv) => set(Number(nv)))}></div>`;
    }
    return `<div class="card tight"><div class="row"><div class="grow"><div class="ttl">${esc(this._name(id, it))}${this._hiddenNote(it)}</div></div>
      <button class="round" aria-label="Mindre" ${this.h(() => set(v - step))}>−</button>
      <span class="tv" style="font-size:19px;font-weight:800;min-width:70px;text-align:center">${esc(String(v).replace(".", ","))}${esc(unit)}</span>
      <button class="round" aria-label="Mer" ${this.h(() => set(v + step))}>+</button></div></div>`;
  }

  _time(it) {
    const id = it.entity;
    const s = this._s(id);
    const val = String(s.state).slice(0, 5);
    return `<div class="card tight"><div class="small" style="margin-bottom:6px">${esc(this._name(id, it))}${this._hiddenNote(it)}</div>
      <input class="time-field" type="time" value="${esc(val)}" aria-label="${esc(this._name(id, it))}"
        ${this.c((v) => v && this._call("input_datetime.set_datetime", { time: v.length === 5 ? v + ":00" : v }, { entity_id: id }))}></div>`;
  }

  _input(it) {
    const id = it.entity;
    const s = this._s(id);
    return `<div class="card tight"><div class="small" style="margin-bottom:6px">${esc(this._name(id, it))}${this._hiddenNote(it)}</div>
      <input class="field" type="text" value="${esc(s.state === "unknown" ? "" : s.state)}" placeholder="${esc(it.placeholder || "Skriv her")}" aria-label="${esc(this._name(id, it))}"
        ${this.c((v) => this._call("input_text.set_value", { value: v }, { entity_id: id }))}></div>`;
  }

  _cover(it) {
    const id = it.entity;
    const s = this._s(id);
    const open = s.state !== "closed";
    const cmd = (svc, label, icon) =>
      `<button class="btn soft" ${this.h(() => this._confirm(it.confirm, () => this._call("cover." + svc, {}, { entity_id: id })))}><ha-icon icon="${icon}"></ha-icon>${label}</button>`;
    return `<div class="card" style="${open && it.alert_open ? "background:var(--bad-bg)" : ""}"><div class="row" data-more="${esc(id)}" ${this.h(() => {})}>
      <span class="ic" style="width:40px;height:40px;border-radius:20px;background:var(--card2);display:flex;align-items:center;justify-content:center"><ha-icon icon="${esc(this._icon(id, it, open ? "mdi:garage-open-variant" : "mdi:garage-variant"))}"></ha-icon></span>
      <div class="grow"><div class="ttl">${esc(this._name(id, it))}${this._hiddenNote(it)}</div><div class="small">${esc(this._fmt(id))}</div></div></div>
      <div class="btns" style="grid-template-columns:repeat(3,minmax(0,1fr));margin-top:12px">${cmd("open_cover", "Åpne", "mdi:arrow-up")}${cmd("stop_cover", "Stopp", "mdi:stop")}${cmd("close_cover", "Lukk", "mdi:arrow-down")}</div></div>`;
  }

  _lock(it) {
    const id = it.entity;
    const s = this._s(id);
    const locked = s.state === "locked";
    return `<button class="tgl ${locked ? "" : "on"}" data-more="${esc(id)}" ${this.h(() =>
      this._confirm(it.confirm ?? `${locked ? "Låse opp" : "Låse"} ${this._name(id, it)}?`, () => this._call(locked ? "lock.unlock" : "lock.lock", {}, { entity_id: id })))}>
      <span class="ic" style="${locked ? "" : "background:var(--bad);color:#fff"}"><ha-icon icon="${locked ? "mdi:lock" : "mdi:lock-open-variant"}"></ha-icon></span>
      <span class="grow"><span class="nm" style="display:block">${esc(this._name(id, it))}${this._hiddenNote(it)}</span><span class="st">${esc(this._fmt(id))}</span></span></button>`;
  }

  _camera(it) {
    const id = it.entity;
    const s = this._s(id);
    const pic = s.attributes.entity_picture;
    const slot = Math.floor(Date.now() / 10000);
    this._needsTick = true;
    const src = pic ? (this._hass.hassUrl ? this._hass.hassUrl(pic) : pic) + `&t=${slot}` : "";
    return `<div class="card" style="padding:8px"><button style="display:block;width:100%" aria-label="Åpne ${esc(this._name(id, it))}" ${this.h(() => this._more(id))}>
      ${src ? `<img class="cam" src="${esc(src)}" alt="${esc(this._name(id, it))}" loading="lazy">` : `<div class="cam"></div>`}</button>
      <div class="small" style="padding:8px 6px 2px">${esc(this._name(id, it))} · trykk for direkte bilde${this._hiddenNote(it)}</div></div>`;
  }

  _timerItem(it) {
    const id = it.entity;
    const s = this._s(id);
    let rem = "";
    if (s.state === "active" && s.attributes.finishes_at) {
      this._needsTick = true;
      const sec = Math.max(0, Math.round((new Date(s.attributes.finishes_at) - Date.now()) / 1000));
      rem = `${Math.floor(sec / 60)}:${String(sec % 60).padStart(2, "0")}`;
    } else if (s.state === "paused") rem = s.attributes.remaining || "";
    else rem = s.attributes.duration || "";
    const cmd = (svc, label, icon, cls = "soft") =>
      `<button class="btn ${cls}" ${this.h(() => this._call("timer." + svc, {}, { entity_id: id }))}><ha-icon icon="${icon}"></ha-icon>${label}</button>`;
    return `<div class="card"><div class="row"><div class="grow"><div class="ttl">${esc(this._name(id, it))}${this._hiddenNote(it)}</div><div class="small">${esc(this._fmt(id))}</div></div>
      <div class="tv" style="font-size:24px;font-weight:800;font-variant-numeric:tabular-nums">${esc(rem)}</div></div>
      <div class="btns" style="grid-template-columns:repeat(3,minmax(0,1fr));margin-top:12px">
        ${s.state === "active" ? cmd("pause", "Pause", "mdi:pause", "dark") : cmd("start", "Start", "mdi:play", "dark")}
        ${cmd("cancel", "Avbryt", "mdi:close")}${cmd("finish", "Ferdig", "mdi:check")}</div></div>`;
  }

  /* --- handleliste --- */
  async _fetchTodo(id) {
    const st = this._s(id)?.state;
    const cur = this._todo[id];
    if (cur && (cur.loading || (cur.state === st && Date.now() - cur.t < 120000))) return;
    this._todo[id] = { ...(cur || {}), loading: true };
    try {
      const r = await this._hass.callWS({ type: "todo/item/list", entity_id: id });
      this._todo[id] = { items: r.items || [], t: Date.now(), state: st };
    } catch (e) {
      this._todo[id] = { items: [], t: Date.now(), state: st, err: e.message };
    }
    this._render();
  }

  _todoItem(it) {
    const id = it.entity;
    this._fetchTodo(id);
    const d = this._todo[id] || {};
    const items = d.items || [];
    const open = items.filter((x) => x.status !== "completed");
    const done = items.filter((x) => x.status === "completed");
    const showDone = this._sel["todo:" + id];
    const row = (x) => `<button class="check ${x.status === "completed" ? "done" : ""}" ${this.h(async () => {
        x.status = x.status === "completed" ? "needs_action" : "completed";
        this._render();
        await this._call("todo.update_item", { item: x.uid, status: x.status }, { entity_id: id });
        this._todo[id].t = 0;
      })}><span class="box">${x.status === "completed" ? `<ha-icon icon="mdi:check" style="--mdc-icon-size:16px"></ha-icon>` : ""}</span><span class="t grow">${esc(x.summary)}</span></button>`;
    const add = async (v, el) => {
      const txt = String(v || "").trim();
      if (!txt) return;
      el.value = "";
      el.dataset.fresh = "1";
      await this._call("todo.add_item", { item: txt }, { entity_id: id });
      el.dataset.fresh = "";
      this._todo[id].t = 0;
      this._fetchTodo(id);
    };
    const addIdx = this._h.push(add) - 1;
    return `<div class="card"><div class="row" style="margin-bottom:8px"><div class="ttl grow">${esc(this._name(id, it))}${this._hiddenNote(it)}</div><span class="small">${open.length} igjen</span></div>
      <div class="row" style="margin-bottom:6px"><input class="field" type="text" placeholder="Legg til vare" aria-label="Legg til" data-enter="${addIdx}" enterkeyhint="done">
      <button class="round" style="background:var(--accent);color:var(--accent-text)" aria-label="Legg til" ${this.h((el) => { const inp = el.parentElement.querySelector("input"); add(inp.value, inp); })}><ha-icon icon="mdi:plus"></ha-icon></button></div>
      ${d.loading && !items.length ? `<div class="empty">Henter …</div>` : ""}
      ${open.map(row).join("")}
      ${!open.length && !d.loading ? `<div class="empty">Listen er tom</div>` : ""}
      ${done.length ? `<div class="row" style="margin-top:8px"><button class="btn soft" ${this.h(() => { this._sel["todo:" + id] = !showDone; this._render(); })}>${showDone ? "Skjul" : "Vis"} fullførte (${done.length})</button>
        <button class="btn soft" ${this.h(() => this._confirm("Fjerne alle fullførte?", () => { this._call("todo.remove_completed_items", {}, { entity_id: id }); this._todo[id].t = 0; }))}>Fjern fullførte</button></div>` : ""}
      ${showDone ? done.map(row).join("") : ""}</div>`;
  }

  /* --- kalender --- */
  async _fetchCal(key, ents, days) {
    const cur = this._cal[key];
    if (cur && (cur.loading || Date.now() - cur.t < 300000)) return;
    this._cal[key] = { ...(cur || {}), loading: true };
    const start = new Date();
    start.setHours(0, 0, 0, 0);
    const end = new Date(start.getTime() + days * 86400000);
    const all = [];
    await Promise.all(ents.map(async (e) => {
      try {
        const r = await this._hass.callApi("GET", `calendars/${e.entity}?start=${encodeURIComponent(start.toISOString())}&end=${encodeURIComponent(end.toISOString())}`);
        for (const ev of r || []) all.push({ ...ev, color: e.color, label: e.label });
      } catch (err) { /* hopp over */ }
    }));
    const t = (x) => new Date(x.start.dateTime || x.start.date + "T00:00:00");
    all.sort((a, b) => t(a) - t(b));
    this._cal[key] = { events: all, t: Date.now() };
    this._render();
  }

  _calendar(it) {
    const ents = (it.entities || []).map((e) => (typeof e === "string" ? { entity: e } : e));
    const days = it.days || 5;
    const key = JSON.stringify([ents.map((e) => e.entity), days]);
    this._fetchCal(key, ents, days);
    const d = this._cal[key] || {};
    const evs = (d.events || []).filter((ev) => {
      const end = new Date(ev.end?.dateTime || (ev.end?.date ? ev.end.date + "T00:00:00" : ev.start.dateTime));
      return end > new Date();
    }).slice(0, it.max || 12);
    const today = new Date(); today.setHours(0, 0, 0, 0);
    const dayLabel = (dt) => {
      const x = new Date(dt); x.setHours(0, 0, 0, 0);
      const diff = Math.round((x - today) / 86400000);
      if (diff <= 0) return "I dag";
      if (diff === 1) return "I morgen";
      return x.toLocaleDateString("nb-NO", { weekday: "long", day: "numeric", month: "short" });
    };
    let out = `<div class="card">${it.name ? `<div class="ttl" style="margin-bottom:8px">${esc(it.name)}${this._hiddenNote(it)}</div>` : ""}`;
    let last = "";
    for (const ev of evs) {
      const st = new Date(ev.start.dateTime || ev.start.date + "T00:00:00");
      const lbl = dayLabel(st < today ? today : st);
      if (lbl !== last) { out += `<div class="cal-day">${esc(lbl)}</div>`; last = lbl; }
      const time = ev.start.dateTime ? st.toLocaleTimeString("nb-NO", { hour: "2-digit", minute: "2-digit" }) : "Hele";
      out += `<div class="ev"><span class="dot" style="background:${esc(ev.color || "var(--accent)")}"></span><span class="tm">${esc(time)}</span><span class="grow">${esc(ev.label ? ev.label + " " : "")}${esc(ev.summary || "")}</span></div>`;
    }
    if (!evs.length) out += `<div class="empty" style="padding:12px">${d.loading ? "Henter …" : esc(it.empty || "Ingen avtaler de neste dagene")}</div>`;
    return out + `</div>`;
  }

  /* --- vær --- */
  _subForecast(id, type) {
    const key = id + "|" + type;
    if (this._fc[key]) return;
    this._fc[key] = { list: [] };
    try {
      this._hass.connection.subscribeMessage((ev) => {
        this._fc[key].list = ev.forecast || [];
        this._render();
      }, { type: "weather/subscribe_forecast", entity_id: id, forecast_type: type }).then((u) => { this._fc[key].unsub = u; }).catch(() => {});
    } catch (e) { /* ok */ }
  }

  _weather(it) {
    const id = it.entity;
    const s = this._s(id);
    const type = it.forecast || "hourly";
    this._subForecast(id, type);
    const list = (this._fc[id + "|" + type]?.list || []).slice(0, it.count || 10);
    const a = s.attributes;
    return `<div class="card"><div class="row" data-more="${esc(id)}" ${this.h(() => {})}>
      <ha-icon icon="${WEATHER_ICON[s.state] || "mdi:weather-partly-cloudy"}" style="--mdc-icon-size:40px;color:var(--accent)"></ha-icon>
      <div class="grow"><div class="ttl" style="font-size:22px">${Math.round(Number(a.temperature))}°</div><div class="small">${esc(NB_WEATHER[s.state] || s.state)}${a.wind_speed != null ? ` · vind ${Math.round(a.wind_speed)} ${esc(a.wind_speed_unit || "")}` : ""}</div></div></div>
      ${list.length ? `<div class="fc">${list
        .map((f) => {
          const dt = new Date(f.datetime);
          const lbl = type === "hourly" ? dt.toLocaleTimeString("nb-NO", { hour: "2-digit" }) : dt.toLocaleDateString("nb-NO", { weekday: "short" });
          return `<div><div class="muted">${esc(lbl)}</div><ha-icon icon="${WEATHER_ICON[f.condition] || "mdi:weather-partly-cloudy"}"></ha-icon><div>${Math.round(f.temperature)}°</div>${f.precipitation ? `<div class="muted" style="font-size:10.5px">${String(f.precipitation).replace(".", ",")} mm</div>` : ""}</div>`;
        })
        .join("")}</div>` : ""}</div>`;
  }

  /* --- grafer --- */
  async _fetchHist(ids, hours) {
    const key = ids.join(",") + "|" + hours;
    const cur = this._hist[key];
    if (cur && (cur.loading || Date.now() - cur.t < 300000)) return;
    this._hist[key] = { ...(cur || {}), loading: true };
    try {
      const end = new Date();
      const start = new Date(end.getTime() - hours * 3600000);
      const r = await this._hass.callWS({
        type: "history/history_during_period", start_time: start.toISOString(), end_time: end.toISOString(),
        entity_ids: ids, minimal_response: true, no_attributes: true, significant_changes_only: false,
      });
      this._hist[key] = { data: r || {}, t: Date.now(), start: start.getTime(), end: end.getTime() };
    } catch (e) {
      this._hist[key] = { data: {}, t: Date.now(), err: e.message };
    }
    this._render();
  }

  _series(id, hours) {
    const key = id + "|" + hours;
    this._fetchHist([id], hours);
    const h = this._hist[key];
    if (!h || !h.data) return null;
    const pts = (h.data[id] || [])
      .map((p) => [((p.lu ?? p.last_updated) * 1000) || Date.parse(p.last_changed), Number(p.s ?? p.state), p.s ?? p.state])
      .filter((p) => !isNaN(p[0]));
    return { pts, start: h.start, end: h.end };
  }

  _spark(id, hours) {
    const d = this._series(id, hours);
    if (!d || d.pts.length < 2) return `<svg class="spark" aria-hidden="true"></svg>`;
    const num = d.pts.filter((p) => !isNaN(p[1]));
    if (num.length < 2) return `<svg class="spark" aria-hidden="true"></svg>`;
    const min = Math.min(...num.map((p) => p[1]));
    const max = Math.max(...num.map((p) => p[1]));
    const W = 200, H = 34;
    const x = (t) => ((t - d.start) / (d.end - d.start)) * W;
    const y = (v) => H - 3 - ((v - min) / (max - min || 1)) * (H - 6);
    const path = num.map((p, i) => `${i ? "L" : "M"}${x(p[0]).toFixed(1)},${y(p[1]).toFixed(1)}`).join("") + `L${W},${y(num[num.length - 1][1]).toFixed(1)}`;
    return `<svg class="spark" viewBox="0 0 ${W} ${H}" preserveAspectRatio="none" aria-hidden="true"><path d="${path}" fill="none" stroke="var(--accent)" stroke-width="2" vector-effect="non-scaling-stroke"/></svg>`;
  }

  _graph(it) {
    const ents = (it.entities || [it.entity]).filter(Boolean).map((e) => (typeof e === "string" ? { entity: e } : e));
    const hours = it.hours || 24;
    const colors = ["var(--accent)", "var(--blue)", "var(--good)", "var(--bad)"];
    let svg = "";
    let legend = "";
    const W = 300, H = 110;
    ents.forEach((e, k) => {
      const d = this._series(e.entity, hours);
      const col = e.color || colors[k % colors.length];
      legend += `<span style="display:inline-flex;align-items:center;gap:5px;margin-right:12px"><span class="dot" style="background:${esc(col)}"></span>${esc(e.name || this._name(e.entity))}</span>`;
      if (!d || !d.pts.length) return;
      const x = (t) => ((t - d.start) / (d.end - d.start)) * W;
      const numeric = d.pts.some((p) => !isNaN(p[1]));
      if (numeric) {
        const num = d.pts.filter((p) => !isNaN(p[1]));
        const all = ents.length === 1 ? num : num;
        const min = Math.min(...all.map((p) => p[1]));
        const max = Math.max(...all.map((p) => p[1]));
        const y = (v) => H - 6 - ((v - min) / (max - min || 1)) * (H - 14);
        const path = num.map((p, i) => `${i ? "L" : "M"}${Math.max(0, x(p[0])).toFixed(1)},${y(p[1]).toFixed(1)}`).join("") + (num.length ? `L${W},${y(num[num.length - 1][1]).toFixed(1)}` : "");
        svg += `<path d="${path}" fill="none" stroke="${esc(col)}" stroke-width="2" vector-effect="non-scaling-stroke"/>`;
        if (ents.length === 1) legend += `<span class="muted">min ${String(min).replace(".", ",")} · maks ${String(max).replace(".", ",")}</span>`;
      } else {
        const band = 14, top = 8 + k * (band + 6);
        d.pts.forEach((p, i) => {
          const x0 = Math.max(0, x(p[0]));
          const x1 = i + 1 < d.pts.length ? x(d.pts[i + 1][0]) : W;
          if (["on", "open", "detected", "home"].includes(p[2])) svg += `<rect x="${x0.toFixed(1)}" y="${top}" width="${Math.max(1, x1 - x0).toFixed(1)}" height="${band}" rx="3" fill="${esc(col)}"/>`;
        });
        svg += `<rect x="0" y="${top}" width="${W}" height="${band}" rx="3" fill="var(--card2)" opacity=".5"/>`;
      }
    });
    const lbl = hours >= 48 ? `Siste ${Math.round(hours / 24)} døgn` : `Siste ${hours} timer`;
    return `<div class="card"><div class="row"><div class="ttl grow">${esc(it.name || lbl)}${this._hiddenNote(it)}</div>${it.name ? `<span class="small">${esc(lbl)}</span>` : ""}</div>
      <svg viewBox="0 0 ${W} ${H}" preserveAspectRatio="none" style="width:100%;height:${H}px;display:block;margin-top:8px" role="img" aria-label="${esc(it.name || lbl)}">${svg}</svg>
      <div class="small" style="margin-top:6px">${legend}</div></div>`;
  }

  /* --- strømpris --- */
  _priceSeries(id) {
    const s = this._s(id);
    if (!s) return [];
    const raw = [...(s.attributes.raw_today || []), ...(s.attributes.raw_tomorrow || [])];
    const byHour = new Map();
    for (const p of raw) {
      const st = new Date(p.start);
      const k = new Date(st.getFullYear(), st.getMonth(), st.getDate(), st.getHours()).getTime();
      if (!byHour.has(k)) byHour.set(k, []);
      byHour.get(k).push(Number(p.value));
    }
    return [...byHour.entries()].map(([t, vs]) => ({ t, v: vs.reduce((a, b) => a + b, 0) / vs.length }));
  }

  _priceSentence(id) {
    const ser = this._priceSeries(id);
    const nowH = new Date(); nowH.setMinutes(0, 0, 0);
    const cur = ser.find((p) => p.t === nowH.getTime());
    if (!cur) return "";
    const today = ser.filter((p) => new Date(p.t).getDate() === nowH.getDate());
    const avg = today.reduce((a, p) => a + p.v, 0) / (today.length || 1);
    const level = cur.v < avg * 0.85 ? "billig" : cur.v > avg * 1.15 ? "dyr" : "normal";
    const fut = ser.filter((p) => p.t > nowH.getTime());
    const cheaper = fut.find((p) => p.v < cur.v - 0.02);
    const fmtT = (t) => { const d = new Date(t); return (d.getDate() !== nowH.getDate() ? "i morgen " : "") + "kl. " + String(d.getHours()).padStart(2, "0"); };
    return `Strømmen er ${level} nå (${Math.round(cur.v * 100)} øre)` + (cheaper ? `, billigere ${fmtT(cheaper.t)}` : "");
  }

  _priceChart(it) {
    const id = it.entity;
    const ser = this._priceSeries(id);
    const nowH = new Date(); nowH.setMinutes(0, 0, 0);
    const from = nowH.getTime() - 3 * 3600000;
    const show = ser.filter((p) => p.t >= from).slice(0, 36);
    if (!show.length) return `<div class="card small">Ingen prisdata</div>`;
    const max = Math.max(...show.map((p) => p.v));
    const min = Math.min(...show.map((p) => p.v));
    const cur = ser.find((p) => p.t === nowH.getTime());
    const today = ser.filter((p) => new Date(p.t).getDate() === nowH.getDate());
    const avg = today.reduce((a, p) => a + p.v, 0) / (today.length || 1);
    const fut = ser.filter((p) => p.t > nowH.getTime());
    const best = fut.length ? fut.reduce((a, b) => (b.v < a.v ? b : a)) : null;
    const cheaper = cur ? fut.find((p) => p.v < cur.v - 0.02) : null;
    const fmtT = (t) => { const d = new Date(t); return (d.getDate() !== nowH.getDate() ? "i morgen " : "") + "kl. " + String(d.getHours()).padStart(2, "0"); };
    const øre = (v) => Math.round(v * 100);
    let level = "";
    if (cur) level = cur.v < avg * 0.85 ? "Billig akkurat nå – fint tidspunkt for vaskemaskin og lading." : cur.v > avg * 1.15 ? "Dyrt akkurat nå – vent gjerne med storforbruk." : "Normal pris akkurat nå.";
    const tip = cheaper ? `Billigere ${fmtT(cheaper.t)} (${øre(cheaper.v)} øre), billigst ${fmtT(best.t)} (${øre(best.v)} øre).` : "Det blir ikke billigere enn nå.";
    const tmw = (this._s(id)?.attributes.raw_tomorrow || []).length ? "" : " Morgendagens priser kommer ca. kl. 13.";
    const bars = show
      .map((p) => {
        const hgt = 8 + ((p.v - Math.min(min, 0)) / (max - Math.min(min, 0) || 1)) * 92;
        const cls = p.t === nowH.getTime() ? "now" : new Date(p.t).getDate() !== nowH.getDate() ? "tm" : "";
        return `<div class="${cls}" style="height:${hgt.toFixed(0)}%" title="${new Date(p.t).getHours()}:00 ${øre(p.v)} øre"></div>`;
      })
      .join("");
    const first = new Date(show[0].t).getHours();
    return `<div class="card"><div class="row"><div class="grow"><div class="ttl">${esc(it.name || "Strømpris")}${this._hiddenNote(it)}</div>
      <div class="small">i dag: min ${øre(Math.min(...today.map((p) => p.v)))} · snitt ${øre(avg)} · maks ${øre(Math.max(...today.map((p) => p.v)))} øre</div></div>
      ${cur ? `<div class="tv" style="font-size:24px;font-weight:800">${øre(cur.v)}<span class="small"> øre</span></div>` : ""}</div>
      <div class="bars" aria-hidden="true">${bars}</div>
      <div class="axis"><span>${String(first).padStart(2, "0")}</span><span>nå</span><span>${String(new Date(show[show.length - 1].t).getHours()).padStart(2, "0")}</span></div>
      <div class="small" style="margin-top:10px;color:var(--text)">${esc(level)} ${esc(tip)}${esc(tmw)}</div></div>`;
  }

  /* --- tekst (inkl. maler) --- */
  _subTpl(tpl) {
    if (this._tpl[tpl]) return this._tpl[tpl];
    this._tpl[tpl] = { v: "" };
    try {
      this._hass.connection.subscribeMessage((msg) => {
        if (msg.result !== undefined) { this._tpl[tpl].v = String(msg.result); this._render(); }
      }, { type: "render_template", template: tpl, strict: false, report_errors: false }).then((u) => { this._tpl[tpl].unsub = u; })
        .catch(() => { this._tpl[tpl].err = true; });
    } catch (e) { this._tpl[tpl].err = true; }
    return this._tpl[tpl];
  }

  _text(it) {
    let body = "";
    let stamp = "";
    if (it.entity && this._s(it.entity)) {
      const s = this._s(it.entity);
      body = BAD.includes(s.state) ? it.empty || "" : s.state;
      stamp = new Date(s.last_changed).toLocaleTimeString("nb-NO", { hour: "2-digit", minute: "2-digit" });
    }
    if (it.content) body = this._subTpl(it.content).v || body;
    if (!body && !this._edit && it.hide_empty) return "";
    const running = it.busy && this._s(it.busy) && Number(this._s(it.busy).attributes.current || 0) > 0;
    const btn = it.action
      ? `<button class="round" style="width:40px;height:40px" aria-label="${esc(it.action_label || "Oppdater")}" ${this.h(() => this._call(it.action.service, it.action.data || {}, it.action.target))}><ha-icon icon="${running ? "mdi:timer-sand" : esc(it.action_icon || "mdi:refresh")}"></ha-icon></button>`
      : "";
    if (it.style === "brief") {
      return `<div class="card brief"><span class="ic"><ha-icon icon="${esc(it.icon || "mdi:creation")}"></ha-icon></span>
        <div class="grow"><div class="small" style="margin-bottom:3px">${esc(it.name || "")}${stamp ? " · kl. " + esc(stamp) : ""}${running ? " · skriver …" : ""}${this._hiddenNote(it)}</div>
        <div class="md" style="font-size:14.5px">${miniMd(body)}</div></div>${btn}</div>`;
    }
    const tap = it.open || it.path;
    return `<div class="card" ${it.alert ? 'style="background:var(--bad-bg);color:var(--bad)"' : ""} ${tap ? this.h(() => (it.open ? this._openTarget(it.open) : this._navigate(it.path))) : ""} ${tap ? 'role="button" tabindex="0"' : ""}>
      <div class="row">${it.icon ? `<ha-icon icon="${esc(it.icon)}" style="color:var(--accent)"></ha-icon>` : ""}<div class="grow">${it.name ? `<div class="ttl">${esc(it.name)}${this._hiddenNote(it)}</div>` : ""}
      <div class="md small" style="color:inherit;opacity:.9">${miniMd(body)}</div></div>${btn}</div></div>`;
  }

  /* --- systemlister --- */
  _updates(it) {
    const list = Object.values(this._hass.states).filter((s) => s.entity_id.startsWith("update.") && s.state === "on");
    if (!list.length) return `<div class="card"><div class="row"><ha-icon icon="mdi:check-circle" style="color:var(--good)"></ha-icon><span class="ttl">Alt er oppdatert</span></div></div>`;
    return `<div class="card"><div class="ttl" style="margin-bottom:6px">${list.length} oppdatering${list.length > 1 ? "er" : ""} klar${this._hiddenNote(it)}</div>${list
      .map((s) => {
        const busy = s.attributes.in_progress;
        return `<div class="row" style="min-height:52px;border-bottom:1px solid var(--line)"><div class="grow"><div style="font-weight:700;font-size:14.5px">${esc(s.attributes.title || s.attributes.friendly_name)}</div>
          <div class="small">${esc(s.attributes.installed_version || "")} → ${esc(s.attributes.latest_version || "")}</div></div>
          <button class="btn soft" style="width:auto;min-height:40px;padding:0 14px" ${busy ? "disabled" : ""} ${this.h(() => this._confirm(`Installere ${s.attributes.title || s.attributes.friendly_name}?`, () => this._call("update.install", {}, { entity_id: s.entity_id })))}>${busy ? "Installerer …" : "Installer"}</button></div>`;
      })
      .join("")}</div>`;
  }

  _batteries(it) {
    const lim = it.below ?? 20;
    const list = Object.values(this._hass.states)
      .filter((s) => s.attributes.device_class === "battery" && s.entity_id.startsWith("sensor.") && !isNaN(Number(s.state)) && Number(s.state) < lim)
      .sort((a, b) => Number(a.state) - Number(b.state));
    if (!list.length) return `<div class="card"><div class="row"><ha-icon icon="mdi:battery-check" style="color:var(--good)"></ha-icon><span class="ttl">Alle batterier er over ${lim} %</span></div></div>`;
    return `<div class="card"><div class="ttl" style="margin-bottom:6px">Lave batterier${this._hiddenNote(it)}</div>${list
      .map((s) => `<button class="row check" data-more="${esc(s.entity_id)}" ${this.h(() => this._more(s.entity_id))}><ha-icon icon="mdi:battery-alert" style="color:var(--bad)"></ha-icon><span class="grow">${esc(s.attributes.friendly_name)}</span><b>${esc(s.state)} %</b></button>`)
      .join("")}</div>`;
  }

  _embed(it) {
    if (!it.card) return `<div class="card small">Mangler kortoppsett</div>`;
    const json = JSON.stringify(it.card);
    let h = 0;
    for (let i = 0; i < json.length; i++) h = (h * 31 + json.charCodeAt(i)) | 0;
    const key = "k" + (h >>> 0).toString(36);
    this._cardCfg[key] = it.card;
    if (this._edit) return `<div class="card"><div class="ttl">${esc(it.name || it.card.type)}${this._hiddenNote(it)}</div><div class="small">Vanlig kort – endres som tekst</div></div>`;
    return `<div class="embed" data-keep="1" data-card="${key}" data-k="card-${key}"></div>`;
  }

  _lightsOnItem(it) {
    const on = this._lightsOn();
    if (!on.length) return `<div class="empty">Alle lys er av</div>`;
    return `<div class="grid">${on.map((id) => `<div class="it">${this._lightStrip(id, {})}</div>`).join("")}</div>`;
  }

  /* ------------------------------------------------------------------ */
  /* Redigeringsmodus                                                     */
  /* ------------------------------------------------------------------ */

  async _startEdit() {
    this._draft = this._normalize(clone(this._config));
    this._edit = true;
    this._render();
    try {
      const users = await this._hass.callWS({ type: "config/auth/list" });
      for (const u of users || []) {
        if (u.system_generated || !u.is_active) continue;
        this._draft.users[u.id] = u.name;
      }
      this._render();
    } catch (e) { /* ikke admin – bruker lagrede navn */ }
  }

  _cancelEdit() {
    this._edit = false;
    this._draft = null;
    this._sheet = null;
    this._render();
  }

  _dashUrl() {
    const seg = location.pathname.split("/").filter(Boolean)[0];
    return !seg || seg === "lovelace" ? null : seg;
  }

  async _saveEdit() {
    const url = this._dashUrl();
    try {
      const msg = { type: "lovelace/config" };
      if (url) msg.url_path = url;
      const dash = await this._hass.callWS(msg);
      const self = this._draft;
      let done = false;
      const walk = (cards) => {
        if (!Array.isArray(cards)) return;
        for (let i = 0; i < cards.length && !done; i++) {
          if (cards[i] && cards[i].type === "custom:smarthus-app") {
            cards[i] = { ...self, type: "custom:smarthus-app" };
            done = true;
            return;
          }
          if (cards[i] && cards[i].cards) walk(cards[i].cards);
        }
      };
      for (const v of dash.views || []) {
        if (done) break;
        walk(v.cards);
        for (const s of v.sections || []) if (!done) walk(s.cards);
      }
      if (!done) throw new Error("Fant ikke appen i dashbordet");
      const save = { type: "lovelace/config/save", config: dash };
      if (url) save.url_path = url;
      await this._hass.callWS(save);
      this._config = this._normalize(clone(self));
      this._edit = false;
      this._draft = null;
      this._sheet = null;
      this._showToast("Lagret");
    } catch (err) {
      this._showToast("Kunne ikke lagre: " + (err.message || err));
    }
  }

  /* Henter/endrer en liste i utkastet ut fra en sti som ['rooms', 2, 'tabs', 0, 'items'] */
  _at(path) {
    let o = this._draft;
    for (const p of path) {
      if (o[p] === undefined) o[p] = typeof p === "number" ? {} : [];
      o = o[p];
    }
    return o;
  }

  _etools(path, i, opts = {}) {
    const list = this._at(path);
    const up = i > 0;
    const down = i < list.length - 1;
    const edit = opts.page ? () => this._openPageEditor(path[0], i) : () => this._openItemEditor(path, i);
    return `<div class="etools">
      ${up ? `<button aria-label="Flytt opp" ${this.h(() => this._move(path, i, -1))}><ha-icon icon="mdi:arrow-up"></ha-icon></button>` : ""}
      ${down ? `<button aria-label="Flytt ned" ${this.h(() => this._move(path, i, 1))}><ha-icon icon="mdi:arrow-down"></ha-icon></button>` : ""}
      <button aria-label="Endre" ${this.h(edit)}><ha-icon icon="mdi:pencil"></ha-icon></button></div>`;
  }

  _move(path, i, dir) {
    const list = this._at(path);
    const j = i + dir;
    if (j < 0 || j >= list.length) return;
    [list[i], list[j]] = [list[j], list[i]];
    this._render();
  }

  _moveTab(f, i, dir) {
    const tabs = this._draft[f.list][f.idx].tabs;
    const j = i + dir;
    if (j < 0 || j >= tabs.length) return;
    [tabs[i], tabs[j]] = [tabs[j], tabs[i]];
    this._tabSel[f.page.id] = j;
    this._render();
  }

  _addTab(f) {
    const p = this._draft[f.list][f.idx];
    p.tabs.push({ name: "Ny fane", items: [] });
    this._tabSel[p.id] = p.tabs.length - 1;
    this._openTabEditor(f, p.tabs.length - 1);
  }

  _addPage(list) {
    const p = { id: uid(), name: list === "rooms" ? "Nytt rom" : "Ny side", icon: list === "rooms" ? "mdi:door" : "mdi:dots-grid", tabs: [{ name: "Oversikt", items: [] }] };
    this._draft[list].push(p);
    this._openPageEditor(list, this._draft[list].length - 1);
  }

  _usersBoxes(name, selected) {
    const users = Object.entries(this._draft.users || {});
    if (!users.length) return `<div class="small">Ingen brukere funnet</div>`;
    return `<div class="cbx">${users
      .map(([id, n]) => `<label><input type="checkbox" name="${name}" value="${esc(id)}" ${selected?.includes(id) ? "checked" : ""}>${esc(n)}</label>`)
      .join("")}</div>`;
  }

  _readBoxes(name) {
    return [...this.shadowRoot.querySelectorAll(`input[name="${name}"]:checked`)].map((x) => x.value);
  }

  _fval(name) {
    const el = this.shadowRoot.querySelector(`[name="${name}"]`);
    return el ? el.value.trim() : "";
  }

  _entityList(domains) {
    const ids = Object.keys(this._hass.states).sort();
    const list = domains && domains.length ? ids.filter((id) => domains.includes(domainOf(id))) : ids;
    return `<datalist id="ents">${list.map((id) => `<option value="${esc(id)}">${esc(this._name(id))}</option>`).join("")}</datalist>`;
  }

  _openItemEditor(path, i, defType) {
    const list = this._at(path);
    const it = i >= 0 ? clone(list[i]) : { type: defType || "light" };
    this._sheet = { kind: "item", path, i, it, json: JSON.stringify(it, null, 2) };
    this._render();
  }

  _openPageEditor(list, i) {
    const p = this._draft[list][i];
    this._sheet = { kind: "page", list, i, json: JSON.stringify({ ...p, tabs: undefined }, null, 2) };
    this._render();
  }

  _openTabEditor(f, i) {
    this._sheet = { kind: "tab", f, i };
    this._render();
  }

  _openChipsEditor() {
    this._sheet = { kind: "chips", json: JSON.stringify(this._draft.home.chips, null, 2) };
    this._render();
  }

  _openJson() {
    this._sheet = { kind: "json", json: JSON.stringify({ ...this._draft, type: undefined }, null, 2) };
    this._render();
  }

  _sheetHtml() {
    const sh = this._sheet;
    let inner = "";
    const close = this.h(() => { this._sheet = null; this._render(); });
    if (sh.kind === "confirm") {
      inner = `<h2>${esc(sh.text)}</h2><div class="sheet-actions">
        <button class="btn soft" ${close}>Avbryt</button>
        <button class="btn dark" ${this.h(() => { const fn = sh.fn; this._sheet = null; this._render(); fn(); })}>Ja</button></div>`;
    } else if (sh.kind === "item") {
      const it = sh.it;
      const type = it.type || "light";
      const doms = TYPES[type]?.domains || [];
      const typeOpts = Object.entries(TYPES).map(([k, v]) => `<option value="${k}" ${k === type ? "selected" : ""}>${esc(v.label)}</option>`).join("");
      const w = it.w || TYPES[type]?.w || 6;
      inner = `<h2>${sh.i >= 0 ? "Endre element" : "Nytt element"}</h2><div class="frm">
        <label>Type<select class="field" name="type" ${this.c((v) => { sh.it = this._collectItem(); sh.it.type = v; sh.json = JSON.stringify(sh.it, null, 2); this._render(); })}>${typeOpts}</select></label>
        ${!["heading", "link", "updates", "batteries", "lightson", "card"].includes(type) ? `<label>Enhet<input class="field" name="entity" list="ents" value="${esc(it.entity || "")}" placeholder="f.eks. ${esc((doms[0] || "light") + ".kjokken")}" autocomplete="off"></label>${this._entityList(doms)}` : ""}
        <label>Navn (tomt = navnet fra Home Assistant)<input class="field" name="name" value="${esc(it.name || "")}"></label>
        ${type === "link" ? `<label>Åpner adresse (f.eks. /energy)<input class="field" name="path" value="${esc(it.path || "")}"></label>` : ""}
        <label>Ikon (mdi:…)<input class="field" name="icon" value="${esc(it.icon || "")}" placeholder="valgfritt"></label>
        <label>Bredde<div class="seg" role="radiogroup">${[[6, "Hel"], [4, "2/3"], [3, "Halv"], [2, "1/3"]]
          .map(([n, l]) => `<button type="button" class="${w === n ? "sel" : ""}" ${this.h(() => { sh.it = this._collectItem(); sh.it.w = n; sh.json = JSON.stringify(sh.it, null, 2); this._render(); })}>${l}</button>`)
          .join("")}</div></label>
        <label>Spør før handling (tom = nei)<input class="field" name="confirm" value="${esc(it.confirm || "")}" placeholder="f.eks. Slå av alt lys?"></label>
        <label>Skjul for${this._usersBoxes("hide_for", it.hide_for)}</label>
        <details><summary>Avansert (alle innstillinger som tekst)</summary>
          <textarea class="field" name="json" data-k="json-${sh.i}-${esc(type)}" spellcheck="false">${esc(sh.json)}</textarea>
          <div class="small" style="margin-top:6px">Endrer du teksten her, er det den som lagres.</div></details>
        </div>
        <div class="sheet-actions">
          ${sh.i >= 0 ? `<button class="btn soft danger" ${this.h(() => this._confirm("Fjerne elementet?", () => { this._at(sh.path).splice(sh.i, 1); this._sheet = null; this._render(); }))}>Fjern</button>` : `<button class="btn soft" ${close}>Avbryt</button>`}
          <button class="btn dark" ${this.h(() => this._saveItem())}>Bruk</button></div>`;
    } else if (sh.kind === "page") {
      const p = this._draft[sh.list][sh.i];
      const big = sh.list === "more";
      inner = `<h2>${esc(p.name)}</h2><div class="frm">
        <label>Navn<input class="field" name="name" value="${esc(p.name)}"></label>
        <label>Ikon (mdi:…)<input class="field" name="icon" value="${esc(p.icon || "")}"></label>
        <label>Hovedbryter på ruten (lys/bryter)<input class="field" name="main" list="ents" value="${esc(p.main || "")}" autocomplete="off"></label>
        <label>Temperatur som vises<input class="field" name="temp" list="ents" value="${esc(p.temp || "")}" autocomplete="off"></label>
        ${big ? `<label>Stor verdi på kortet<input class="field" name="big" list="ents" value="${esc(p.big || "")}" autocomplete="off"></label>
          <label>Størrelse i Mer<div class="seg"><button type="button" class="${p.size === "large" ? "sel" : ""}" ${this.h(() => { p.size = "large"; this._render(); })}>Stort kort</button><button type="button" class="${p.size !== "large" ? "sel" : ""}" ${this.h(() => { p.size = "small"; this._render(); })}>Liten rute</button></div></label>` : ""}
        ${this._entityList([])}
        <label>Skjul for${this._usersBoxes("hide_for", p.hide_for)}</label>
        <details><summary>Avansert (tekst)</summary><textarea class="field" name="json" spellcheck="false">${esc(sh.json)}</textarea></details>
      </div>
      <div class="sheet-actions">
        <button class="btn soft danger" ${this.h(() => this._confirm(`Slette «${p.name}» med alt innhold?`, () => { this._draft[sh.list].splice(sh.i, 1); this._sheet = null; this._nav = { view: sh.list === "more" ? "more" : "home" }; this._render(); }))}>Slett</button>
        <button class="btn dark" ${this.h(() => this._savePage())}>Bruk</button></div>`;
    } else if (sh.kind === "tab") {
      const p = this._draft[sh.f.list][sh.f.idx];
      const t = p.tabs[sh.i];
      inner = `<h2>Fane</h2><div class="frm">
        <label>Navn<input class="field" name="name" value="${esc(t.name)}"></label>
        <label>Skjul for${this._usersBoxes("hide_for", t.hide_for)}</label></div>
        <div class="sheet-actions">
          <button class="btn soft danger" ${p.tabs.length < 2 ? "disabled" : ""} ${this.h(() => {
            if (p.tabs.length < 2) return;
            this._confirm(`Slette fanen «${t.name}»?`, () => { p.tabs.splice(sh.i, 1); this._tabSel[p.id] = 0; this._sheet = null; this._render(); });
          })}>Slett fane</button>
          <button class="btn dark" ${this.h(() => { t.name = this._fval("name") || t.name; const hf = this._readBoxes("hide_for"); if (hf.length) t.hide_for = hf; else delete t.hide_for; this._sheet = null; this._render(); })}>Bruk</button></div>`;
    } else if (sh.kind === "chips" || sh.kind === "json") {
      const title = sh.kind === "chips" ? "Brikker på forsiden" : "Hele oppsettet som tekst";
      const help = sh.kind === "chips"
        ? `Typer: <b>lights</b> (antall lys på), <b>entity</b> (viser en enhet, «label» med {} for verdien), <b>text</b>. «when» viser brikken bare når en betingelse stemmer. «open» bestemmer hva som åpnes: lights, heat, room:id, more:id eller path:/adresse.`
        : `Alt i appen. Lim inn en sikkerhetskopi eller gjør større endringer her.`;
      inner = `<h2>${title}</h2><div class="small" style="margin-bottom:10px">${help}</div>
        <textarea class="field" name="json" style="min-height:300px" spellcheck="false">${esc(sh.json)}</textarea>
        <div class="sheet-actions"><button class="btn soft" ${close}>Avbryt</button>
        <button class="btn dark" ${this.h(() => {
          try {
            const v = JSON.parse(this.shadowRoot.querySelector('textarea[name="json"]').value);
            if (sh.kind === "chips") this._draft.home.chips = v;
            else this._draft = this._normalize(v);
            this._sheet = null;
            this._render();
          } catch (err) { this._showToast("Ugyldig tekst: " + err.message); }
        })}>Bruk</button></div>`;
    }
    return `<div class="scrim" data-k="scrim-${esc(sh.kind)}"><div class="sheet" role="dialog" aria-modal="true"><div class="grab"></div>${inner}</div></div>`;
  }

  _collectItem() {
    const sh = this._sheet;
    const it = { ...sh.it };
    const set = (k) => {
      const v = this._fval(k);
      if (v) it[k] = v; else delete it[k];
    };
    it.type = this._fval("type") || it.type;
    ["entity", "name", "icon", "confirm", "path"].forEach(set);
    const hf = this._readBoxes("hide_for");
    if (hf.length) it.hide_for = hf; else delete it.hide_for;
    return it;
  }

  _saveItem() {
    const sh = this._sheet;
    let it;
    const ta = this.shadowRoot.querySelector('textarea[name="json"]');
    if (ta && ta.value.trim() !== sh.json.trim()) {
      try { it = JSON.parse(ta.value); } catch (err) { this._showToast("Ugyldig tekst: " + err.message); return; }
    } else it = this._collectItem();
    if (it.w === (TYPES[it.type]?.w || 6)) delete it.w;
    const list = this._at(sh.path);
    if (sh.i >= 0) list[sh.i] = it; else list.push(it);
    this._sheet = null;
    this._render();
  }

  _savePage() {
    const sh = this._sheet;
    const p = this._draft[sh.list][sh.i];
    const ta = this.shadowRoot.querySelector('textarea[name="json"]');
    if (ta && ta.value.trim() !== sh.json.trim()) {
      try { Object.assign(p, JSON.parse(ta.value), { tabs: p.tabs }); } catch (err) { this._showToast("Ugyldig tekst: " + err.message); return; }
    } else {
      for (const k of ["name", "icon", "main", "temp", "big"]) {
        const v = this._fval(k);
        if (v) p[k] = v; else if (k !== "name") delete p[k];
      }
      const hf = this._readBoxes("hide_for");
      if (hf.length) p.hide_for = hf; else delete p.hide_for;
    }
    this._sheet = null;
    this._render();
  }
}

if (!customElements.get("smarthus-app")) customElements.define("smarthus-app", SmarthusApp);
window.customCards = window.customCards || [];
if (!window.customCards.some((c) => c.type === "smarthus-app")) {
  window.customCards.push({ type: "smarthus-app", name: "Smarthus", description: "Hele huset i én app – rom, lys, varme og mer.", preview: false });
}
console.info(`%c SMARTHUS %c ${VERSION} `, "background:#E8902A;color:#1A1206;font-weight:700;border-radius:4px 0 0 4px", "background:#1C1B19;color:#fff;border-radius:0 4px 4px 0");
