/* Styrkeboka – frontend. Ingen rammeverk, alle stier relative til ingress. */
(() => {
  "use strict";

  // ================================================================ hjelpere
  const $ = (id) => document.getElementById(id);
  const el = (tag, attrs = {}, ...barn) => {
    const e = document.createElement(tag);
    for (const [k, v] of Object.entries(attrs || {})) {
      if (k === "class") e.className = v;
      else if (k.startsWith("on") && typeof v === "function") e.addEventListener(k.slice(2), v);
      else if (k === "html") e.innerHTML = v;
      else if (k === "value") e.value = v ?? "";
      else if (v !== false && v != null) e.setAttribute(k, v === true ? "" : v);
    }
    for (const b of barn.flat(Infinity)) if (b != null && b !== false) e.append(b.nodeType ? b : document.createTextNode(b));
    return e;
  };
  const SVGNS = "http://www.w3.org/2000/svg";
  const ikon = (navn) => {
    const s = document.createElementNS(SVGNS, "svg");
    const u = document.createElementNS(SVGNS, "use");
    u.setAttribute("href", `#i-${navn}`);
    s.append(u);
    return s;
  };
  const svgEl = (tag, attrs = {}, tekst) => {
    const e = document.createElementNS(SVGNS, tag);
    for (const [k, v] of Object.entries(attrs)) e.setAttribute(k, v);
    if (tekst != null) e.textContent = tekst;
    return e;
  };
  const tall = (x) => x == null || x === "" ? "" : String(+Number(x).toFixed(2)).replace(".", ",");
  const kg = (x) => x == null ? "–" : `${tall(x)} kg`;
  const lesTall = (s) => { const x = parseFloat(String(s ?? "").replace(",", ".")); return Number.isFinite(x) ? x : null; };
  const dato = (iso, aar = false) => new Date(iso).toLocaleDateString("nb-NO", { day: "numeric", month: "short", ...(aar ? { year: "numeric" } : {}) }).replace(".", "");
  const ukedag = (iso) => new Date(iso).toLocaleDateString("nb-NO", { weekday: "long", day: "numeric", month: "long" });
  const kl = (iso) => new Date(iso).toLocaleTimeString("nb-NO", { hour: "2-digit", minute: "2-digit" });
  const mmss = (s) => { s = Math.max(0, Math.round(s)); return `${Math.floor(s / 60)}:${String(s % 60).padStart(2, "0")}`; };
  const hvileTekst = (s) => s >= 60 ? `${mmss(s)} min` : `${s} s`;
  const tusen = (x) => Math.round(x || 0).toLocaleString("nb-NO");
  function siden(iso) {
    const d = Math.round((new Date().setHours(0, 0, 0, 0) - new Date(iso).setHours(0, 0, 0, 0)) / 864e5);
    if (d <= 0) return "i dag";
    if (d === 1) return "i går";
    return `for ${d} dager siden`;
  }
  const tilLokalInput = (d) => { d = new Date(d); const p = (n) => String(n).padStart(2, "0"); return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())}T${p(d.getHours())}:${p(d.getMinutes())}`; };
  const vibrer = (m = 12) => { try { navigator.vibrate && navigator.vibrate(m); } catch (_) { /* */ } };
  const lagre = (k, v) => { try { localStorage.setItem(`styrkeboka-${k}`, JSON.stringify(v)); } catch (_) { /* */ } };
  const hent = (k, std) => { try { const v = JSON.parse(localStorage.getItem(`styrkeboka-${k}`)); return v ?? std; } catch (_) { return std; } };
  const OPPLEVD = ["", "Veldig lett", "Lett", "Passe", "Tungt", "Maks"];

  // ================================================================ tilstand
  let S = null;              // api/start
  let pid = null;            // valgt profil
  let ov = null;             // oversikt for profil
  let okt = null;            // økten som vises
  let aapenOv = null;        // id for åpen øvelse i økten
  let fane = "trening";
  let histFane = hent("histfane", "okter");

  // ================================================================ API
  async function api(sti, opts = {}) {
    const r = await fetch(sti, {
      method: opts.method || "GET",
      headers: { "Content-Type": "application/json" },
      body: opts.body !== undefined ? JSON.stringify(opts.body) : undefined,
      credentials: "same-origin",
    });
    const j = await r.json().catch(() => ({}));
    if (!r.ok) {
      const e = new Error(j.feil || `Feil ${r.status}`);
      e.status = r.status;
      throw e;
    }
    return j;
  }
  const post = (sti, body = {}) => api(sti, { method: "POST", body });
  const patch = (sti, body = {}) => api(sti, { method: "PATCH", body });
  const put = (sti, body = {}) => api(sti, { method: "PUT", body });
  const slett = (sti) => api(sti, { method: "DELETE" });

  const ovelse = (nokkel) => S.ovelser.find((o) => o.nokkel === nokkel) || { nokkel, navn: nokkel, monster: "", utstyr: [], tips: [] };
  const profil = () => S.profiler.find((p) => p.id === pid);
  const aiPaa = () => S.ai_tilgjengelig && S.innstillinger.ai_paa;
  const sted = () => hent(`sted-${pid}`, null) || profil()?.utstyrsprofil_id || S.utstyrsprofiler[0]?.id;

  // ================================================================ toast, ark og bekreftelse
  let toastTimer = null;
  function visToast(tekst, knapper = [], ms = 5000) {
    const rot = $("toast-rot");
    rot.innerHTML = "";
    clearTimeout(toastTimer);
    rot.append(el("div", { class: "toast", role: "status" }, el("span", {}, tekst),
      knapper.length ? el("div", { class: "toast-knapper" }, knapper.map((k) => el("button", { onclick: () => { rot.innerHTML = ""; k.fn(); } }, k.tekst))) : null));
    toastTimer = setTimeout(() => { rot.innerHTML = ""; }, ms);
  }
  const feil = (e) => visToast(e.message || String(e));

  let arkLukk = null;
  function aapneArk(...innhold) {
    lukkArk();
    const rot = $("ark-rot");
    const bak = el("div", { class: "ark-bakgrunn", onclick: () => lukkArk() });
    const ark = el("div", { class: "ark", role: "dialog", "aria-modal": "true" }, el("div", { class: "ark-handtak" }), ...innhold);
    rot.append(bak, ark);
    arkLukk = () => { rot.innerHTML = ""; arkLukk = null; };
    return ark;
  }
  function lukkArk() { if (arkLukk) arkLukk(); }
  document.addEventListener("keydown", (e) => { if (e.key === "Escape") lukkArk(); });

  function bekreft(tittel, tekst, knapp = "OK", fare = false) {
    return new Promise((ok) => {
      let svar = false;
      aapneArk(el("h3", {}, tittel), tekst ? el("p", { class: "hint" }, tekst) : null,
        el("div", { class: "ark-knapper" },
          el("button", { class: "knapp noytral", onclick: () => lukkArk() }, "Avbryt"),
          el("button", { class: `knapp ${fare ? "fare" : ""}`, style: fare ? "flex:1" : "", onclick: () => { svar = true; lukkArk(); } }, knapp)));
      const gammel = arkLukk;
      arkLukk = () => { gammel(); ok(svar); };
    });
  }

  const felt = (navn, input, hjelp) => el("label", { class: "felt" }, el("span", {}, navn), input, hjelp ? el("small", { class: "forklaring" }, hjelp) : null);
  const bryter = (paa, fn) => {
    const b = el("button", { class: `bryter ${paa ? "paa" : ""}`, role: "switch", "aria-checked": String(!!paa) });
    b.addEventListener("click", () => { const ny = !b.classList.contains("paa"); b.classList.toggle("paa", ny); b.setAttribute("aria-checked", String(ny)); fn(ny); });
    return b;
  };
  const avatar = (p, cls = "") => el("span", { class: `avatar ${cls} farge-${p?.farge || "lilla"}` }, (p?.navn || "?").slice(0, 1).toUpperCase());
  const fastMerke = (o) => o.fast ? el("span", { class: "merkelapp fast", title: "Fast hovedøvelse – beholdes ved ny blokk" }, ikon("laas"), "Fast") : null;
  const blokkTekst = (b) => b ? (b.ferdig ? `Blokk ${b.nr} fullført` : `Blokk ${b.nr} · uke ${b.uke} av ${b.uker}${b.lett_naa ? " · lettere uke" : ""}`) : "";
  const aiLaster = (tekst) => el("div", { class: "ai-kort" }, el("div", { class: "laster" }, tekst));

  // ================================================================ navigasjon
  const VISNINGER = ["trening", "okt", "program", "historikk", "detalj", "innstillinger"];
  function vis(navn, fanenavn) {
    for (const v of VISNINGER) $(`v-${v}`).hidden = v !== navn;
    fane = fanenavn || (navn === "okt" ? "trening" : navn);
    for (const b of document.querySelectorAll(".faner button")) b.classList.toggle("valgt", b.dataset.fane === fane);
    window.scrollTo({ top: 0 });
  }
  $("faner").addEventListener("click", (e) => {
    const b = e.target.closest("button[data-fane]");
    if (!b) return;
    const f = b.dataset.fane;
    if (f === "trening") visTrening();
    if (f === "program") visProgram();
    if (f === "historikk") visHistorikk();
    if (f === "innstillinger") visInnstillinger();
  });
  function settTittel(t, under = "") { $("tittel").textContent = t; $("undertittel").textContent = under; }

  // ================================================================ oppstart og profil
  async function lastStart() {
    S = await api("api/start");
    const lagret = hent("profil", null);
    pid = S.profiler.some((p) => p.id === lagret) ? lagret : (S.meg || S.profiler[0]?.id || null);
    if (S.meg && !hent("profil-manuelt", false)) pid = S.meg;
    tegnProfilvelger();
  }

  function velgProfil(id, manuelt = true) {
    pid = id;
    lagre("profil", id);
    if (manuelt) lagre("profil-manuelt", id !== S.meg);
    stoppHvile();
    tegnProfilvelger();
    if (fane === "program") visProgram();
    else if (fane === "historikk") visHistorikk();
    else if (fane === "innstillinger") visInnstillinger();
    else visTrening();
  }

  function tegnProfilvelger() {
    const p = profil();
    document.body.className = document.body.className.replace(/farge-\w+/g, "").trim() + ` farge-${p?.farge || "lilla"}`;
    const rot = $("profilvelger");
    rot.innerHTML = "";
    if (S.profiler.length < 2) return;
    for (const x of S.profiler) {
      rot.append(el("button", { class: x.id === pid ? "valgt" : "", title: x.navn, "aria-label": `Bytt til ${x.navn}`, onclick: () => velgProfil(x.id) }, avatar(x)));
    }
  }

  // ================================================================ TRENING (forside)
  async function visTrening() {
    vis("trening");
    const v = $("v-trening");
    if (!S.profiler.length) {
      settTittel("Styrkeboka");
      v.innerHTML = "";
      v.append(el("div", { class: "velkommen" },
        el("h2", {}, "Velkommen til Styrkeboka"),
        el("p", {}, "Lag en profil med mål, erfaring og hvor du trener. Så setter vi opp et program – med eller uten hjelp fra AI-treneren."),
        el("button", { class: "knapp", onclick: () => profilArk(null) }, ikon("person"), "Lag profil")));
      return;
    }
    try { ov = await api(`api/profiler/${pid}/oversikt?sted=${sted() || ""}`); } catch (e) { feil(e); return; }
    if (ov.aktiv && fane === "trening" && hent("i-okt", false)) { visOkt(ov.aktiv.id); return; }
    tegnTrening();
  }

  function tegnTrening() {
    const p = ov.profil;
    settTittel(`Hei, ${p.navn}`, ov.program ? `${ov.program.navn} · ${blokkTekst(ov.program.blokk)}` : "");
    const v = $("v-trening");
    v.innerHTML = "";
    oppdaterOktPrikk();

    if (ov.aktiv) {
      const a = ov.aktiv;
      const pst = a.nokkeltall.planlagt ? Math.min(100, Math.round(100 * a.nokkeltall.sett / a.nokkeltall.planlagt)) : 0;
      v.append(el("div", { class: "helt" },
        el("div", {}, el("div", { class: "merke puls" }, "Økt pågår"),
          el("div", { class: "helt-tittel" }, a.dag_navn),
          el("div", { class: "helt-under" }, el("span", {}, ikon("klokke"), `${a.nokkeltall.minutter} min`), el("span", {}, `${a.nokkeltall.sett} av ${a.nokkeltall.planlagt} sett`))),
        el("div", { class: "fremdrift" }, el("div", { style: `width:${pst}%` })),
        el("button", { class: "knapp", onclick: () => visOkt(a.id) }, ikon("play"), "Fortsett økten")));
    } else if (!ov.program) {
      v.append(el("div", { class: "velkommen" },
        el("h2", {}, "Sett opp et program"),
        el("p", {}, aiPaa() ? "AI-treneren kan lage et program ut fra målene dine, eller du kan starte med appens eget forslag og justere det." : "Start med appens forslag ut fra målene dine, og juster det som du vil."),
        aiPaa() ? el("button", { class: "knapp", onclick: () => nyttProgramArk(true) }, ikon("gnist"), "Lag program med AI") : null,
        el("button", { class: "knapp", style: "background:rgba(255,255,255,.18);color:#fff", onclick: () => nyttProgramArk(false) }, "Bruk appens forslag")));
      v.append(el("button", { class: "legg-til", onclick: () => startOkt(null) }, ikon("pluss"), "Start en fri økt uten program"));
    } else if (ov.neste) {
      const n = ov.neste;
      const b = ov.program.blokk;
      if (b?.ferdig) v.append(blokkBanner(ov.program.id, b));
      const stedId = sted();
      const valgtSted = S.utstyrsprofiler.find((u) => u.id === stedId);
      v.append(el("div", { class: "helt" },
        el("div", {},
          el("div", { class: "merke" }, b?.lett_naa ? "Lettere uke" : ov.sist ? `Neste økt · sist trent ${siden(ov.sist.startet)}` : "Første økt"),
          el("div", { class: "helt-tittel" }, n.navn),
          el("div", { class: "helt-under" }, el("span", {}, ikon("klokke"), `ca. ${n.minutter} min`), el("span", {}, ikon("manual"), `${n.ovelser.length} øvelser`))),
        b?.lett_naa ? el("p", { class: "forklaring" }, `Siste uke i blokk ${b.nr}: halvparten så mange sett og samme vekt som sist. En lettere uke lar kroppen hente seg inn, så du står sterkere til neste blokk.`) : null,
        el("ul", { class: "plan-liste" }, n.ovelser.map((o) => el("li", { class: o.tilgjengelig || !valgtSted ? "" : "utilgj" },
          el("span", { class: "navn" }, o.navn, el("small", {}, `${o.sett} × ${o.reps_min}–${o.reps_maks}${o.erstatter ? ` · i stedet for ${o.erstatter}` : ""}`)),
          o.kg != null ? el("span", { class: `kg ${o.trend === "opp" ? "trend-opp" : o.trend === "ned" ? "trend-ned" : ""}` },
            o.trend === "opp" ? ikon("opp") : o.trend === "ned" ? ikon("ned") : null, kg(o.kg)) : null))),
        S.utstyrsprofiler.length > 1 ? el("div", { class: "segment" }, S.utstyrsprofiler.map((u) =>
          el("button", { class: u.id === stedId ? "valgt" : "", onclick: () => { lagre(`sted-${pid}`, u.id); visTrening(); } }, ikon("sted"), u.navn))) : null,
        n.ovelser.some((o) => o.erstatter) ? el("p", { class: "forklaring" }, `Øvelser som krever utstyr ${valgtSted?.navn || "stedet"} ikke har, er byttet ut med en tilsvarende øvelse for denne økta.`) : null,
        el("button", { class: "knapp", onclick: () => startOkt(n.id) }, ikon("play"), "Start økten")));
      const andre = ov.program.dager.filter((d) => d.id !== n.id);
      v.append(el("div", { class: "chips rull" },
        andre.map((d) => el("button", { class: "chip liten", onclick: () => startOkt(d.id) }, d.navn)),
        el("button", { class: "chip liten", onclick: () => startOkt(null) }, ikon("pluss"), "Fri økt")));
    }

    if (ov.mangler_startvekt && !ov.aktiv) {
      v.append(el("div", { class: "ai-kort" },
        el("h3", {}, ikon("manual"), "Hvor tungt skal du løfte?"),
        el("p", {}, `${ov.mangler_startvekt} øvelser i programmet mangler startvekt. Svar på et par spørsmål, så ${aiPaa() ? "foreslår treneren" : "regner appen ut"} vekt på alle.`),
        el("button", { class: "knapp ai", style: "flex:none", onclick: startvekterArk }, ikon("gnist"), "Finn startvekter")));
    }
    // uke
    const u = ov.uke;
    v.append(el("div", { class: "kort" },
      el("div", { class: "uke" },
        el("div", { class: "uke-tekst" }, `${u.okter} av ${u.plan} økter denne uka`,
          el("small", {}, u.okter >= u.plan ? "Ukemålet er nådd – sterkt!" : u.okter ? `${u.plan - u.okter} igjen` : "Helsedirektoratet anbefaler styrke minst 2 dager i uka")),
        u.uker_paa_rad > 1 ? el("span", { class: "flamme" }, ikon("flamme"), `${u.uker_paa_rad} uker`) : null),
      el("div", { class: "uke-prikker" }, Array.from({ length: Math.max(u.plan, u.okter) }, (_, i) => el("span", { class: i < u.okter ? "gjort" : "" })))));

    const knapper = el("div", { class: "knapperad" });
    if (aiPaa()) knapper.append(el("button", { class: "knapp ai-lys", onclick: () => sporTreneren() }, ikon("snakk"), "Spør treneren"));
    if (ov.sist) knapper.append(el("button", { class: "knapp noytral", onclick: () => visOktDetalj(ov.sist.id, "trening") }, ikon("klokke"), "Forrige økt"));
    if (knapper.children.length) v.append(knapper);
  }

  function oppdaterOktPrikk() {
    const b = document.querySelector('.faner button[data-fane="trening"]');
    b.querySelector(".prikk")?.remove();
    if (ov?.aktiv) b.append(el("span", { class: "prikk" }));
  }

  async function startOkt(dagId) {
    try {
      const r = await post(`api/profiler/${pid}/okter`, { dag_id: dagId, utstyrsprofil_id: sted() });
      okt = r.okt;
      aapenOv = null;
      vibrer(20);
      visOkt(okt.id, true);
    } catch (e) { feil(e); }
  }

  // ================================================================ ØKT
  let oktTimer = null;
  async function visOkt(id, ny = false) {
    try { okt = (await api(`api/okter/${id}`)).okt; } catch (e) { feil(e); return; }
    if (okt.status !== "pagar") { visOktDetalj(id, "trening"); return; }
    lagre("i-okt", true);
    vis("okt", "trening");
    settTittel("Økt pågår", okt.sted || "");
    tegnOkt();
    clearInterval(oktTimer);
    oktTimer = setInterval(() => { if (!$("v-okt").hidden) oppdaterOktHode(); else clearInterval(oktTimer); }, 15e3);
    if (ny && aiPaa() && S.innstillinger.ai_auto_tips) hentTips(false);
  }

  function forsteUferdige() {
    const u = okt.ovelser.find((o) => !o.ferdig);
    return u ? u.id : null;
  }

  function oppdaterOktHode() {
    const m = Math.round((Date.now() - new Date(okt.startet)) / 6e4);
    const t = $("okt-tid");
    if (t) t.textContent = `${m} min · ${okt.nokkeltall.sett} av ${okt.nokkeltall.planlagt} sett · ${tusen(okt.nokkeltall.volum)} kg løftet`;
  }

  function tegnOkt() {
    const v = $("v-okt");
    v.innerHTML = "";
    if (aapenOv == null || (aapenOv !== -1 && !okt.ovelser.some((o) => o.id === aapenOv))) aapenOv = forsteUferdige() ?? okt.ovelser[0]?.id ?? null;
    const pst = okt.nokkeltall.planlagt ? Math.min(100, Math.round(100 * okt.nokkeltall.sett / okt.nokkeltall.planlagt)) : 0;
    v.append(el("div", { class: "okt-hode" },
      el("button", { class: "ikonknapp", "aria-label": "Til forsiden", onclick: () => { lagre("i-okt", false); visTrening(); } }, ikon("venstre")),
      el("div", { class: "tekst" }, el("h2", {}, okt.dag_navn), el("p", { id: "okt-tid" })),
      el("button", { class: "ikonknapp", "aria-label": "Mer", onclick: oktMeny }, ikon("prikker"))));
    v.append(el("div", { class: "fremdrift" }, el("div", { style: `width:${pst}%` })));
    oppdaterOktHode();

    if (okt.lett) v.append(el("div", { class: "info-boks obs" }, ikon("info"), "Lettere uke: færre sett og samme vekt som sist. Stopp med god margin – denne uka teller ikke i vektforslagene."));
    const tipsRot = el("div", { id: "tips-rot" });
    v.append(tipsRot);
    if (okt.ai_tips) tegnTips(okt.ai_tips);
    else if (aiPaa() && !okt.nokkeltall.sett) {
      tipsRot.append(el("button", { class: "knapp ai-lys", style: "flex:none", onclick: () => hentTips(false) }, ikon("gnist"), "Tips fra treneren før du starter"));
    }

    okt.ovelser.forEach((oo, i) => v.append(ovKort(oo, i)));
    if (!okt.ovelser.length) v.append(el("p", { class: "tom" }, "Legg til øvelsene du vil gjøre."));
    v.append(el("button", { class: "legg-til", onclick: () => aapneOvelsevelger({ tittel: "Legg til øvelse", ved_valg: leggTilOvelse }) }, ikon("pluss"), "Legg til øvelse"));
    v.append(el("button", { class: "knapp", onclick: avsluttArk, disabled: !okt.nokkeltall.sett }, ikon("sjekk"), "Fullfør økten"));
  }

  function ovKort(oo, i) {
    const info = oo.info;
    const arbeid = oo.sett.filter((s) => !s.oppvarming);
    const aapen = oo.id === aapenOv;
    const enhet = info.sekunder ? "sek" : "reps";
    const kort = el("div", { class: `ov-kort ${aapen ? "aapen" : ""} ${oo.ferdig ? "ferdig" : ""}`, id: `ov-${oo.id}` });
    const sistSett = arbeid[arbeid.length - 1];
    const under = oo.ferdig
      ? arbeid.map((s) => info.vektbasert && s.vekt != null ? `${tall(s.vekt)}×${s.reps}` : `${s.reps}`).join(" · ")
      : `${oo.sett_plan} × ${oo.reps_min}–${oo.reps_maks} ${enhet}${oo.forslag_kg != null && info.vektbasert ? ` · ${kg(oo.forslag_kg)}` : ""} · hvile ${hvileTekst(oo.hvile_s)}`;
    kort.append(el("button", { class: "ov-topp", onclick: () => { aapenOv = aapen ? -1 : oo.id; tegnOkt(); if (!aapen) document.getElementById(`ov-${oo.id}`)?.scrollIntoView({ block: "start", behavior: "smooth" }); } },
      el("span", { class: "ov-nr" }, oo.ferdig ? ikon("sjekk") : String(i + 1)),
      el("span", { class: "ov-tittel" }, el("b", {}, info.navn), el("small", {}, under)),
      ikon(aapen ? "opp" : "ned")));
    const kropp = el("div", { class: "ov-kropp" });
    if (oo.erstattet_navn) kropp.append(el("div", { class: "erstattet" }, ikon("bytt"), `I stedet for ${oo.erstattet_navn}`));
    if (oo.forslag_tekst) {
      const f = oo.forslag_tekst;
      const kl_ = /øk til/i.test(f) ? "opp" : /ta ned/i.test(f) ? "ned" : "";
      kropp.append(el("div", { class: `forslag ${kl_}` }, ikon(kl_ === "opp" ? "opp" : kl_ === "ned" ? "ned" : "info"), el("span", {}, f)));
    }
    if (info.type === "manualer") kropp.append(el("p", { class: "forklaring", style: "font-size:13px" }, "Vekt = per manual."));
    if (oo.oppvarming.length) {
      const gjort = oo.sett.filter((s) => s.oppvarming).length;
      kropp.append(el("div", { class: "oppvarming" }, "Oppvarming:",
        oo.oppvarming.map((w, j) => el("button", { class: "chip liten", style: j < gjort ? "opacity:.45" : "",
          onclick: () => loggSett(oo, { vekt: w.kg, reps: w.reps, oppvarming: true }) }, `${tall(w.kg)} × ${w.reps}`))));
    }
    // sett
    const tab = el("div", { class: "sett-tabell" },
      el("div", { class: "sett-hode" }, el("span", {}, "Sett"), el("span", {}, info.vektbasert ? "kg" : "ekstra kg"), el("span", {}, enhet), el("span", {}, "I reserve"), el("span", {})));
    for (const s of oo.sett) {
      tab.append(el("div", { class: `sett-rad logget ${s.oppvarming ? "oppv-rad" : ""}`, role: "button", tabindex: "0", onclick: () => endreSettArk(s, oo) },
        el("span", { class: `sett-nr ${s.oppvarming ? "oppv" : ""}` }, s.oppvarming ? "OPPV" : String(s.settnr)),
        el("span", { class: "verdi" }, s.vekt != null ? tall(s.vekt) : "–"),
        el("span", { class: "verdi" }, String(s.reps)),
        el("span", { class: "verdi", style: "font-size:15px" }, s.rir != null ? (s.rir >= 5 ? "5+" : String(s.rir)) : "–"),
        el("span", { class: "sett-ok" }, ikon("sjekk"))));
    }
    // ny rad
    const kgStd = sistSett?.vekt ?? oo.forslag_kg;
    const repsStd = sistSett?.reps ?? oo.forslag_reps;
    const kgInp = el("input", { type: "text", inputmode: "decimal", "aria-label": "Vekt i kg", placeholder: info.vektbasert ? "kg" : "–", value: kgStd != null ? tall(kgStd) : "" });
    const repsInp = el("input", { type: "text", inputmode: "numeric", "aria-label": enhet, placeholder: enhet, value: repsStd ?? "" });
    const rir = el("select", { "aria-label": "Reps i reserve" }, el("option", { value: "" }, "–"), [0, 1, 2, 3, 4].map((x) => el("option", { value: x }, String(x))), el("option", { value: 5 }, "5+"));
    const ok = el("button", { class: "sett-ok", "aria-label": "Logg sett", onclick: () => {
      const reps = parseInt(repsInp.value, 10);
      if (!Number.isFinite(reps)) { repsInp.focus(); visToast(`Skriv inn ${enhet}`); return; }
      loggSett(oo, { vekt: lesTall(kgInp.value), reps, rir: rir.value === "" ? null : +rir.value });
    } }, ikon("sjekk"));
    tab.append(el("div", { class: "sett-rad" }, el("span", { class: "sett-nr" }, String(arbeid.length + 1)), kgInp, repsInp, rir, ok));
    kropp.append(tab);
    if (oo.notat) kropp.append(el("div", { class: "ov-notat" }, oo.notat));
    kropp.append(el("div", { class: "ov-verktoy" },
      el("button", { class: "chip", onclick: () => ovelseInfoArk(oo.ovelse, oo) }, ikon("info"), "Slik gjør du"),
      el("button", { class: "chip", onclick: () => byttOvelseArk(oo) }, ikon("bytt"), "Bytt"),
      el("button", { class: "chip", onclick: () => ovMeny(oo) }, ikon("prikker"), "Mer")));
    kort.append(kropp);
    return kort;
  }

  async function loggSett(oo, d) {
    try {
      const r = await post(`api/okter/${okt.id}/sett`, { okt_ovelse_id: oo.id, ...d });
      okt = r.okt;
      vibrer(15);
      const ny = okt.ovelser.find((x) => x.id === oo.id);
      if (!d.oppvarming) {
        const sisteTotalt = okt.ovelser.every((x) => x.ferdig);
        if (!sisteTotalt) startHvile(ny.hvile_s, ny.ferdig ? `Neste: ${okt.ovelser.find((x) => !x.ferdig)?.info.navn || ""}` : `${ny.info.navn} – sett ${ny.sett.filter((s) => !s.oppvarming).length + 1}`);
        if (ny.ferdig) aapenOv = forsteUferdige();
      }
      tegnOkt();
      if (!d.oppvarming && okt.ovelser.every((x) => x.ferdig)) visToast("Alle planlagte sett er gjort! 💪", [{ tekst: "Fullfør", fn: avsluttArk }], 8000);
      else if (!d.oppvarming) visToast("Sett logget", [{ tekst: "Angre", fn: async () => { try { okt = (await slett(`api/sett/${r.sett.id}`)).okt; stoppHvile(); tegnOkt(); } catch (e) { feil(e); } } }], 4000);
    } catch (e) { feil(e); }
  }

  function endreSettArk(s, oo, etter) {
    const kgInp = el("input", { type: "text", inputmode: "decimal", value: s.vekt != null ? tall(s.vekt) : "" });
    const repsInp = el("input", { type: "text", inputmode: "numeric", value: s.reps });
    const rir = el("select", {}, el("option", { value: "" }, "–"), [0, 1, 2, 3, 4, 5].map((x) => el("option", { value: x }, x === 5 ? "5+" : String(x))));
    rir.value = s.rir ?? "";
    aapneArk(el("h3", {}, ikon("blyant"), `${oo.info?.navn || ovelse(s.ovelse).navn} – ${s.oppvarming ? "oppvarming" : `sett ${s.settnr}`}`),
      el("div", { class: "skjema" }, el("div", { class: "felt-rad tre" }, felt("Vekt (kg)", kgInp), felt(oo.info?.sekunder ? "Sekunder" : "Reps", repsInp), felt("I reserve", rir))),
      el("div", { class: "ark-knapper" },
        el("button", { class: "knapp fare", onclick: async () => {
          try { const r = await slett(`api/sett/${s.id}`); lukkArk(); if (etter) etter(); else { okt = r.okt; tegnOkt(); } } catch (e) { feil(e); }
        } }, ikon("soppel")),
        el("button", { class: "knapp", onclick: async () => {
          try {
            const r = await patch(`api/sett/${s.id}`, { vekt: lesTall(kgInp.value), reps: parseInt(repsInp.value, 10), rir: rir.value === "" ? null : +rir.value });
            lukkArk();
            if (etter) etter(); else { okt = r.okt; tegnOkt(); }
          } catch (e) { feil(e); }
        } }, "Lagre")));
  }

  function oktMeny() {
    aapneArk(el("h3", {}, okt.dag_navn),
      el("div", { class: "meny" },
        aiPaa() ? el("button", { onclick: () => { lukkArk(); hentTips(!!okt.ai_tips); } }, ikon("gnist"), okt.ai_tips ? "Nye tips fra treneren" : "Tips fra treneren") : null,
        aiPaa() ? el("button", { onclick: () => { lukkArk(); sporTreneren({ okt_id: okt.id }); } }, ikon("snakk"), "Spør treneren") : null,
        el("button", { onclick: () => { lukkArk(); aapneOvelsevelger({ tittel: "Legg til øvelse", ved_valg: leggTilOvelse }); } }, ikon("pluss"), "Legg til øvelse"),
        el("button", { onclick: () => { lukkArk(); startvekterArk(); } }, ikon("manual"), "Finn startvekter"),
        el("button", { onclick: () => { lukkArk(); avsluttArk(); } }, ikon("sjekk"), "Fullfør økten"),
        el("button", { class: "fare", onclick: async () => {
          lukkArk();
          if (!(await bekreft("Avbryte økten?", okt.nokkeltall.sett ? `${okt.nokkeltall.sett} registrerte sett blir slettet.` : "Økten slettes.", "Avbryt økten", true))) return;
          try { await slett(`api/okter/${okt.id}`); stoppHvile(); lagre("i-okt", false); okt = null; visTrening(); } catch (e) { feil(e); }
        } }, ikon("soppel"), "Avbryt og slett økten")));
  }

  function ovMeny(oo) {
    const idx = okt.ovelser.findIndex((x) => x.id === oo.id);
    aapneArk(el("h3", {}, oo.info.navn),
      el("div", { class: "meny" },
        el("button", { onclick: () => { lukkArk(); ovelseInfoArk(oo.ovelse, oo); } }, ikon("info"), "Teknikk og tips"),
        el("button", { onclick: () => { lukkArk(); byttOvelseArk(oo); } }, ikon("bytt"), "Bytt øvelse"),
        el("button", { onclick: () => { lukkArk(); planArk(oo); } }, ikon("blyant"), "Endre mål for i dag (sett, reps, hvile)"),
        el("button", { onclick: () => { lukkArk(); notatArk(oo); } }, ikon("snakk"), oo.notat ? "Endre notat" : "Legg til notat"),
        idx > 0 ? el("button", { onclick: () => flytt(oo, -1) }, ikon("opp"), "Flytt opp") : null,
        idx < okt.ovelser.length - 1 ? el("button", { onclick: () => flytt(oo, 1) }, ikon("ned"), "Flytt ned") : null,
        el("button", { class: "fare", onclick: async () => {
          lukkArk();
          if (oo.sett.length && !(await bekreft("Fjerne øvelsen?", "Settene du har logget på denne øvelsen slettes.", "Fjern", true))) return;
          try { okt = (await slett(`api/okt-ovelser/${oo.id}`)).okt; tegnOkt(); } catch (e) { feil(e); }
        } }, ikon("soppel"), "Fjern fra økten")));
  }

  async function flytt(oo, retning) {
    lukkArk();
    try { okt = (await post(`api/okt-ovelser/${oo.id}/flytt`, { retning })).okt; tegnOkt(); } catch (e) { feil(e); }
  }

  function tallStepper(start, steg, min, maks, format = String) {
    let verdi = start;
    const vis_ = el("span", { class: "verdi" }, format(verdi));
    const sett = (v) => { verdi = Math.max(min, Math.min(maks, v)); vis_.textContent = format(verdi); };
    const e = el("div", { class: "stepper" }, el("button", { type: "button", onclick: () => sett(verdi - steg) }, "−"), vis_, el("button", { type: "button", onclick: () => sett(verdi + steg) }, "+"));
    e.verdi = () => verdi;
    return e;
  }

  function planArk(oo) {
    const sett_ = tallStepper(oo.sett_plan, 1, 1, 10);
    const rmin = el("input", { type: "text", inputmode: "numeric", value: oo.reps_min });
    const rmaks = el("input", { type: "text", inputmode: "numeric", value: oo.reps_maks });
    const hvile = tallStepper(oo.hvile_s, 15, 15, 600, hvileTekst);
    aapneArk(el("h3", {}, ikon("blyant"), oo.info.navn), el("p", { class: "hint" }, "Gjelder bare dagens økt. Programmet endrer du under Program."),
      el("div", { class: "skjema" }, felt("Sett", sett_), el("div", { class: "felt-rad" }, felt("Reps fra", rmin), felt("Reps til", rmaks)), felt("Hvile mellom sett", hvile)),
      el("div", { class: "ark-knapper" }, el("button", { class: "knapp noytral", onclick: lukkArk }, "Avbryt"),
        el("button", { class: "knapp", onclick: async () => {
          try {
            okt = (await patch(`api/okt-ovelser/${oo.id}`, { sett_plan: sett_.verdi(), reps_min: rmin.value, reps_maks: rmaks.value, hvile_s: hvile.verdi() })).okt;
            lukkArk(); tegnOkt();
          } catch (e) { feil(e); }
        } }, "Lagre")));
  }

  function notatArk(oo) {
    const t = el("textarea", { placeholder: "F.eks. «kjente litt i skulderen på siste sett»" }, oo.notat || "");
    aapneArk(el("h3", {}, oo.info.navn), el("div", { class: "skjema" }, felt("Notat", t)),
      el("div", { class: "ark-knapper" }, el("button", { class: "knapp noytral", onclick: lukkArk }, "Avbryt"),
        el("button", { class: "knapp", onclick: async () => { try { okt = (await patch(`api/okt-ovelser/${oo.id}`, { notat: t.value })).okt; lukkArk(); tegnOkt(); } catch (e) { feil(e); } } }, "Lagre")));
    setTimeout(() => t.focus(), 250);
  }

  async function leggTilOvelse(o) {
    try {
      okt = (await post(`api/okter/${okt.id}/ovelser`, { ovelse: o.nokkel })).okt;
      aapenOv = okt.ovelser[okt.ovelser.length - 1].id;
      lukkArk(); tegnOkt();
      document.getElementById(`ov-${aapenOv}`)?.scrollIntoView({ block: "start", behavior: "smooth" });
    } catch (e) { feil(e); }
  }

  async function byttOvelseArk(oo, { utstyrsprofil_id = okt?.utstyrsprofil_id, ved_valg = null, i_program = !!oo.programovelse_id } = {}) {
    let alt = [];
    try { alt = (await post("api/alternativer", { ovelse: oo.ovelse, utstyrsprofil_id })).alternativer; } catch (e) { feil(e); return; }
    let ogsaProgram = false;
    const velg = async (a) => {
      if (ved_valg) { lukkArk(); ved_valg(a); return; }
      try { okt = (await patch(`api/okt-ovelser/${oo.id}`, { ovelse: a.nokkel, ogsa_program: ogsaProgram })).okt; lukkArk(); tegnOkt(); visToast(ogsaProgram ? "Byttet – også i programmet" : "Øvelsen er byttet for i dag"); } catch (e) { feil(e); }
    };
    const rad = (a) => el("div", { class: `velg-rad ${a.tilgjengelig ? "" : "utilgj"}` },
      el("button", { onclick: () => velg(a) },
        el("span", { class: "tekst" }, el("b", {}, a.navn), el("small", {}, [a.skansom ? "Skånsom" : null, (a.utstyr || []).map((u) => S.utstyr[u]).join(", ") || "Kroppsvekt"].filter(Boolean).join(" · "))), ikon("hoyre")),
      el("button", { class: "ikonknapp", "aria-label": `Slik gjør du ${a.navn}`, onclick: () => ovelseInfoArk(a.nokkel, null, { tilbake: () => byttOvelseArk(oo, { utstyrsprofil_id, ved_valg, i_program }) }) }, ikon("info")));
    const ok = alt.filter((a) => a.tilgjengelig), ikke = alt.filter((a) => !a.tilgjengelig);
    aapneArk(el("h3", {}, ikon("bytt"), `Bytt ${ovelse(oo.ovelse).navn}`),
      el("p", { class: "hint" }, `Øvelser med samme bevegelse (${S.monster[ovelse(oo.ovelse).monster] || "lignende"}). Fremgangen følger øvelsen du faktisk gjør.`),
      i_program && !ved_valg ? el("div", { class: "liste-rad", style: "min-height:0;padding:6px 2px" }, el("span", { class: "tekst" }, el("b", {}, "Bytt også i programmet"), el("small", {}, "Ellers gjelder byttet bare i dag")), bryter(false, (v) => { ogsaProgram = v; })) : null,
      el("div", { class: "velg-liste" },
        ok.length ? ok.map(rad) : el("p", { class: "tom" }, "Ingen alternativer med utstyret her."),
        ikke.length ? el("div", { class: "gruppe" }, "Krever annet utstyr") : null, ikke.map(rad)),
      el("button", { class: "legg-til", onclick: () => aapneOvelsevelger({ tittel: "Velg øvelse", utstyrsprofil_id, ved_valg: velg }) }, "Søk blant alle øvelser"));
  }

  function aapneOvelsevelger({ tittel, utstyrsprofil_id = okt?.utstyrsprofil_id ?? sted(), ved_valg, info = false }) {
    const utstyr = new Set(S.utstyrsprofiler.find((u) => u.id === utstyrsprofil_id)?.utstyr || Object.keys(S.utstyr));
    const sok = el("input", { type: "search", placeholder: "Søk etter øvelse", autocomplete: "off" });
    const liste = el("div", { class: "velg-liste" });
    const tegn = () => {
      const q = sok.value.trim().toLowerCase();
      liste.innerHTML = "";
      for (const [m, mNavn] of Object.entries(S.monster)) {
        const ovl = S.ovelser.filter((o) => o.monster === m && !o.arkivert && (!q || o.navn.toLowerCase().includes(q) || mNavn.toLowerCase().includes(q)));
        if (!ovl.length) continue;
        ovl.sort((a, b) => (b.utstyr.every((u) => utstyr.has(u)) - a.utstyr.every((u) => utstyr.has(u))) || a.navn.localeCompare(b.navn, "nb"));
        liste.append(el("div", { class: "gruppe" }, mNavn));
        for (const o of ovl) {
          const tilgj = o.utstyr.every((u) => utstyr.has(u));
          liste.append(el("div", { class: `velg-rad ${tilgj ? "" : "utilgj"}` },
            el("button", { onclick: () => ved_valg(o) },
              el("span", { class: "tekst" }, el("b", {}, o.navn), el("small", {}, o.utstyr.map((u) => S.utstyr[u]).join(", ") || "Kroppsvekt")), ikon(info ? "hoyre" : "pluss")),
            info ? null : el("button", { class: "ikonknapp", "aria-label": `Slik gjør du ${o.navn}`, onclick: () => ovelseInfoArk(o.nokkel, null, { tilbake: () => aapneOvelsevelger({ tittel, utstyrsprofil_id, ved_valg }) }) }, ikon("info"))));
        }
      }
      if (!liste.children.length) liste.append(el("p", { class: "tom" }, "Ingen treff. Du kan lage egne øvelser under Innstillinger."));
    };
    sok.addEventListener("input", tegn);
    aapneArk(el("h3", {}, tittel), el("div", { class: "felt sok" }, sok), liste);
    tegn();
  }

  function instruksjonInnhold(o) {
    const ins = o.instruksjon;
    const deler = [];
    if (ins?.start) deler.push(el("div", { class: "ins-del" }, el("h4", {}, "Utgangsstilling"), el("p", {}, ins.start)));
    if (ins?.steg?.length) deler.push(el("div", { class: "ins-del" }, el("h4", {}, "Slik gjør du"), el("ol", { class: "ins-steg" }, ins.steg.map((t) => el("li", {}, t)))));
    if (o.tips?.length) deler.push(el("div", { class: "ins-del" }, el("h4", {}, "Husk"), el("ul", { class: "tips-liste" }, o.tips.map((t) => el("li", {}, t)))));
    if (ins?.pust) deler.push(el("div", { class: "ins-del" }, el("h4", {}, "Pust"), el("p", {}, ins.pust)));
    if (ins?.feil?.length) deler.push(el("div", { class: "ins-del feil" }, el("h4", {}, ikon("advarsel"), "Vanlige feil"), el("ul", {}, ins.feil.map((t) => el("li", {}, t)))));
    if (!deler.length) deler.push(el("p", { class: "forklaring" }, o.egen ? "Ingen instruksjon ennå – legg den inn under Innstillinger → Egne øvelser." : "Ingen instruksjon for denne øvelsen."));
    return deler;
  }

  const videoLenke = (o) => el("a", { class: "knapp noytral liten", style: "flex:1", target: "_blank", rel: "noopener",
    href: `https://www.youtube.com/results?search_query=${encodeURIComponent(`${o.navn} øvelse teknikk`)}` }, ikon("play"), "Søk etter video");

  function ovelseInfoArk(nokkel, oo = null, { tilbake = null } = {}) {
    const o = ovelse(nokkel);
    const meta = [S.monster[o.monster], (o.muskler || []).map((m) => S.muskler[m]).join(", "), (o.utstyr || []).map((u) => S.utstyr[u]).join(", ") || "Kroppsvekt"].filter(Boolean).join(" · ");
    aapneArk(
      tilbake ? el("button", { class: "tilbake", onclick: tilbake }, ikon("venstre"), "Alle øvelser") : null,
      el("h3", {}, o.navn), el("p", { class: "hint" }, meta),
      el("div", { class: "instruksjon" }, instruksjonInnhold(o)),
      el("div", { class: "knapperad", style: "margin-top:14px" }, videoLenke(o),
        aiPaa() ? el("button", { class: "knapp ai liten", style: "flex:1", onclick: () => { lukkArk(); sporTreneren({ ovelse: nokkel, okt_id: oo ? okt?.id : null, forslag: `Hvordan gjør jeg ${o.navn.toLowerCase()} riktig, og hva bør jeg tenke på?` }); } }, ikon("gnist"), "Spør treneren") : null));
  }

  function ovelsesbibliotek() {
    aapneOvelsevelger({ tittel: "Øvelsesbibliotek", info: true, ved_valg: (o) => ovelseInfoArk(o.nokkel, null, { tilbake: ovelsesbibliotek }) });
  }

  // ---- hviletimer
  let hvile = null, hvileTimer = null, lydKontekst = null;
  function pip() {
    if (!S.innstillinger.hviletimer_lyd) return;
    try {
      lydKontekst = lydKontekst || new (window.AudioContext || window.webkitAudioContext)();
      [0, 0.25].forEach((t) => {
        const o = lydKontekst.createOscillator(), g = lydKontekst.createGain();
        o.frequency.value = 880; o.connect(g); g.connect(lydKontekst.destination);
        g.gain.setValueAtTime(0.0001, lydKontekst.currentTime + t);
        g.gain.exponentialRampToValueAtTime(0.25, lydKontekst.currentTime + t + 0.02);
        g.gain.exponentialRampToValueAtTime(0.0001, lydKontekst.currentTime + t + 0.18);
        o.start(lydKontekst.currentTime + t); o.stop(lydKontekst.currentTime + t + 0.2);
      });
    } catch (_) { /* */ }
  }
  function startHvile(sek, etikett) {
    // lås opp lyd på iOS mens vi er i et brukertrykk
    if (S.innstillinger.hviletimer_lyd && !lydKontekst) { try { lydKontekst = new (window.AudioContext || window.webkitAudioContext)(); } catch (_) { /* */ } }
    hvile = { slutt: Date.now() + sek * 1000, total: sek, etikett, ferdig: false };
    clearInterval(hvileTimer);
    hvileTimer = setInterval(tegnHvile, 500);
    tegnHvile();
  }
  let hvileEl = null;
  function stoppHvile() { hvile = null; hvileEl = null; clearInterval(hvileTimer); $("hvile-rot").innerHTML = ""; document.body.classList.remove("har-hvile"); }
  function byggHvile() {
    // Bygges én gang per hvile – bare tekst og linje oppdateres, så knappene står stille og er lette å treffe.
    const tid = el("span", { class: "tid" });
    const tittel = el("span", {});
    const etikett = el("span", { class: "etikett" }, tittel, el("br"), el("span", { class: "neste" }));
    const minus = el("button", { "aria-label": "15 sekunder kortere", onclick: () => { if (!hvile) return; hvile.slutt -= 15e3; tegnHvile(); } }, "−15");
    const pluss = el("button", { "aria-label": "15 sekunder lengre", onclick: () => { if (!hvile) return; hvile.slutt += 15e3; hvile.total += 15; tegnHvile(); } }, "+15");
    const lukk = el("button", { "aria-label": "Lukk hviletimer", onclick: stoppHvile }, ikon("kryss"));
    const linje = el("span", { class: "linje" });
    const boks = el("div", { class: "hvile", role: "timer" }, tid, etikett, minus, pluss, lukk, linje);
    $("hvile-rot").innerHTML = "";
    $("hvile-rot").append(boks);
    hvileEl = { boks, tid, tittel, neste: etikett.querySelector(".neste"), minus, pluss, linje };
  }
  function tegnHvile() {
    if (!hvile) { stoppHvile(); return; }
    if (!hvileEl || !hvileEl.boks.isConnected) byggHvile();
    const igjen = (hvile.slutt - Date.now()) / 1000;
    if (igjen <= 0 && !hvile.ferdig) {
      hvile.ferdig = true;
      vibrer([200, 100, 200]);
      pip();
      setTimeout(() => { if (hvile?.ferdig) stoppHvile(); }, 8000);
    }
    document.body.classList.add("har-hvile");
    const e = hvileEl;
    e.boks.classList.toggle("ferdig", hvile.ferdig);
    const tekst = hvile.ferdig ? "Klar!" : mmss(igjen);
    if (e.tid.textContent !== tekst) e.tid.textContent = tekst;
    e.tittel.textContent = hvile.ferdig ? "Tid for neste sett" : "Hvile";
    e.neste.textContent = hvile.etikett || "";
    e.minus.hidden = e.pluss.hidden = hvile.ferdig;
    e.linje.style.width = `${Math.max(0, Math.min(100, 100 * igjen / hvile.total))}%`;
  }

  // ---- AI i økta
  async function hentTips(ny) {
    const rot = $("tips-rot");
    if (!rot) return;
    rot.innerHTML = "";
    rot.append(aiLaster("Treneren ser på økta di …"));
    try {
      const r = await post(`api/okter/${okt.id}/ai/tips`, { ny });
      okt.ai_tips = r.tips;
      tegnTips(r.tips);
    } catch (e) { rot.innerHTML = ""; feil(e); }
  }
  function tegnTips(tips) {
    const rot = $("tips-rot");
    if (!rot) return;
    rot.innerHTML = "";
    const skjult = hent(`tips-skjult-${okt.id}`, false);
    rot.append(el("div", { class: "ai-kort" },
      el("div", { class: "kort-hode" }, el("h3", {}, ikon("gnist"), "Tips fra treneren"),
        el("button", { class: "lenke", onclick: () => { lagre(`tips-skjult-${okt.id}`, !skjult); tegnTips(tips); } }, skjult ? "Vis" : "Skjul")),
      skjult ? null : el("ul", {}, tips.map((t) => el("li", {}, t)))));
  }

  async function sporTreneren({ okt_id = null, ovelse: nokkel = null, forslag = "" } = {}) {
    if (!aiPaa()) { visToast("AI-treneren er ikke tilgjengelig"); return; }
    const samtale = el("div", { class: "samtale" });
    const t = el("textarea", { placeholder: "F.eks. «Hvor mye bør jeg øke i knebøy?» eller «Jeg har vondt i kneet, hva kan jeg gjøre i stedet?»", rows: 3 }, forslag);
    const send = el("button", { class: "knapp ai" }, ikon("gnist"), "Spør");
    const tegnBobler = (logg) => {
      samtale.innerHTML = "";
      for (const x of logg) samtale.append(el("div", { class: "boble meg" }, x.sporsmal), el("div", { class: "boble ai" }, x.svar));
    };
    let logg = [];
    try { logg = (await api(`api/profiler/${pid}/ai/logg`)).logg.slice(0, 4).reverse(); } catch (_) { /* */ }
    tegnBobler(logg);
    send.addEventListener("click", async () => {
      const sp = t.value.trim();
      if (!sp) { t.focus(); return; }
      send.disabled = true;
      samtale.append(el("div", { class: "boble meg" }, sp), el("div", { class: "boble ai" }, el("span", { class: "laster" }, "Tenker …")));
      samtale.lastChild.scrollIntoView({ behavior: "smooth", block: "end" });
      try {
        const r = await post(`api/profiler/${pid}/ai/sporsmal`, { sporsmal: sp, okt_id, ovelse: nokkel });
        logg.push(r.svar);
        tegnBobler(logg);
        t.value = "";
        samtale.lastChild.scrollIntoView({ behavior: "smooth", block: "end" });
      } catch (e) { samtale.lastChild.remove(); samtale.lastChild.remove(); feil(e); }
      send.disabled = false;
    });
    aapneArk(el("h3", {}, ikon("snakk"), "Spør treneren"),
      el("p", { class: "hint" }, "Treneren kjenner programmet, målene og de siste øktene dine. Navnet ditt sendes ikke."),
      samtale, el("div", { class: "skjema", style: "margin-top:12px" }, el("label", { class: "felt" }, t)),
      el("div", { class: "ark-knapper" }, el("button", { class: "knapp noytral", onclick: lukkArk }, "Lukk"), send));
  }

  // ---- fullføre
  function avsluttArk() {
    let opplevd = null;
    const igjen = okt.nokkeltall.planlagt - okt.nokkeltall.sett;
    const knapper = el("div", { class: "opplevd" }, [1, 2, 3, 4, 5].map((n) => el("button", { onclick: (e) => {
      opplevd = n;
      for (const b of knapper.children) b.classList.toggle("valgt", b === e.currentTarget);
    } }, el("b", {}, String(n)), OPPLEVD[n])));
    const notat = el("textarea", { placeholder: "Hvordan gikk det? Noe som verket, var lett eller tungt?" }, okt.notat || "");
    aapneArk(el("h3", {}, ikon("sjekk"), "Fullfør økten"),
      igjen > 0 ? el("p", { class: "hint" }, `${igjen} planlagte sett er ikke gjort – helt greit, de telles bare ikke med.`) : null,
      el("div", { class: "ark-etikett" }, "Hvor tung var økta?"), knapper,
      el("div", { class: "skjema", style: "margin-top:14px" }, felt("Notat (valgfritt)", notat)),
      el("div", { class: "ark-knapper" }, el("button", { class: "knapp noytral", onclick: lukkArk }, "Fortsett å trene"),
        el("button", { class: "knapp", onclick: async () => {
          try {
            const r = await post(`api/okter/${okt.id}/avslutt`, { opplevd, notat: notat.value });
            lukkArk(); stoppHvile(); lagre("i-okt", false);
            visOppsummering(r);
          } catch (e) { feil(e); }
        } }, "Fullfør")));
  }

  function visOppsummering(res) {
    vis("detalj", "trening");
    const o = res.okt;
    settTittel("Bra jobba! 💪", `${o.dag_navn} · ${ukedag(o.startet)}`);
    const v = $("v-detalj");
    v.innerHTML = "";
    v.append(el("div", { class: "helt" },
      el("div", {}, el("div", { class: "merke" }, "Økt fullført"), el("div", { class: "helt-tittel" }, o.dag_navn)),
      nokkeltall(o)));
    if (res.rekorder.length) {
      v.append(el("div", { class: "kort" }, el("h2", {}, "Nye rekorder"), res.rekorder.map((r) => el("div", { class: "rekord" }, ikon("trofe"), el("span", {}, el("b", {}, r.ovelse), el("br"), r.tekst)))));
    }
    const aiRot = el("div");
    v.append(aiRot);
    if (aiPaa()) {
      if (S.innstillinger.ai_auto_oppsummering) hentOppsummering(o.id, aiRot);
      else aiRot.append(el("button", { class: "knapp ai-lys", style: "width:100%", onclick: () => hentOppsummering(o.id, aiRot) }, ikon("gnist"), "Få oppsummering fra treneren"));
    }
    v.append(el("div", { class: "knapperad" },
      el("button", { class: "knapp noytral", onclick: () => visOktDetalj(o.id, "trening") }, "Se hele økten"),
      el("button", { class: "knapp", onclick: () => visTrening() }, "Ferdig")));
  }

  function nokkeltall(o) {
    return el("div", { class: "nokkeltall" },
      el("div", { class: "tall-boks" }, el("span", { class: "tall-verdi" }, `${o.nokkeltall.minutter}`), el("span", { class: "tall-navn" }, "minutter")),
      el("div", { class: "tall-boks" }, el("span", { class: "tall-verdi" }, `${o.nokkeltall.sett}`), el("span", { class: "tall-navn" }, "sett")),
      el("div", { class: "tall-boks" }, el("span", { class: "tall-verdi" }, tusen(o.nokkeltall.volum)), el("span", { class: "tall-navn" }, "kg løftet")));
  }

  async function hentOppsummering(oid, rot, ny = false) {
    rot.innerHTML = "";
    rot.append(aiLaster("Treneren oppsummerer økta …"));
    try {
      const r = (await post(`api/okter/${oid}/ai/oppsummering`, { ny })).oppsummering;
      rot.innerHTML = "";
      rot.append(el("div", { class: "ai-kort" }, el("h3", {}, ikon("gnist"), "Treneren sier"), el("p", {}, r.oppsummering),
        r.neste_gang?.length ? el("div", {}, el("b", {}, "Til neste gang:"), el("ul", { style: "margin-top:6px" }, r.neste_gang.map((x) => el("li", {}, x)))) : null));
    } catch (e) {
      rot.innerHTML = "";
      rot.append(el("button", { class: "knapp ai-lys", style: "width:100%", onclick: () => hentOppsummering(oid, rot, ny) }, ikon("gnist"), "Prøv oppsummering på nytt"));
      feil(e);
    }
  }

  // ================================================================ STARTVEKTER
  async function startvekterArk() {
    let d;
    try { d = await api(`api/profiler/${pid}/startvekter`); } catch (e) { feil(e); return; }
    const kandidater = S.kan_anslaas.map((k) => ovelse(k)).sort((a, b) => a.navn.localeCompare(b.navn, "nb"));
    const vanlige = ["benkpress", "benkpress-manualer", "knebøy-stang", "markløft", "skulderpress-manualer", "nedtrekk", "beinpress", "goblet-knebøy"];
    const kjente = (d.kjente?.length ? d.kjente : [{ ovelse: "benkpress", kg: "", reps: "" }]).map((k) => ({ ...k }));
    const kv = el("input", { type: "text", inputmode: "decimal", placeholder: "kg", value: d.kroppsvekt != null ? tall(d.kroppsvekt) : "" });
    const rader = el("div", { class: "kjente" });
    const tegnRader = () => {
      rader.innerHTML = "";
      kjente.forEach((k, i) => {
        const velg = el("select", { onchange: () => { k.ovelse = velg.value; } },
          el("optgroup", { label: "Vanlige" }, vanlige.map((n) => el("option", { value: n }, ovelse(n).navn))),
          el("optgroup", { label: "Alle" }, kandidater.filter((o) => !vanlige.includes(o.nokkel)).map((o) => el("option", { value: o.nokkel }, o.navn))));
        velg.value = k.ovelse;
        rader.append(el("div", { class: "kjent-rad" }, velg,
          el("input", { type: "text", inputmode: "decimal", placeholder: "kg", "aria-label": "kg", value: k.kg !== "" && k.kg != null ? tall(k.kg) : "", oninput: (e) => { k.kg = e.target.value; } }),
          el("span", {}, "×"),
          el("input", { type: "text", inputmode: "numeric", placeholder: "reps", "aria-label": "reps", value: k.reps ?? "", oninput: (e) => { k.reps = e.target.value; } }),
          el("button", { class: "ikonknapp", "aria-label": "Fjern", onclick: () => { kjente.splice(i, 1); tegnRader(); } }, ikon("kryss"))));
      });
    };
    tegnRader();
    const status = el("div");
    const beregn = async (medAI) => {
      status.innerHTML = "";
      if (medAI) status.append(el("div", { style: "margin-top:12px" }, aiLaster("Treneren regner ut startvekter …")));
      try {
        const r = await post(`api/profiler/${pid}/startvekter/beregn`, { ai: medAI, kroppsvekt: kv.value, kjente: kjente.filter((k) => k.kg && k.reps) });
        visResultat(r);
      } catch (e) { status.innerHTML = ""; feil(e); }
    };
    aapneArk(el("h3", {}, ikon("manual"), "Startvekter"),
      el("p", { class: "hint" }, "Fortell hva du klarer i ett eller to løft du kjenner, så anslår treneren vekt på resten av øvelsene i programmet. Har du ikke løftet før, holder det med kroppsvekt."),
      el("div", { class: "skjema" }, felt("Kroppsvekt (valgfritt)", kv)),
      el("div", { class: "ark-etikett" }, "Løft du vet hva du klarer"),
      el("p", { class: "forklaring", style: "font-size:13px;margin-bottom:8px" }, "Vekt og antall reps du klarer med god teknikk, f.eks. benkpress 60 kg × 8. Manualer: vekt per manual."),
      rader,
      el("button", { class: "legg-til", style: "margin-top:8px", onclick: () => { kjente.push({ ovelse: "benkpress-manualer", kg: "", reps: "" }); tegnRader(); } }, ikon("pluss"), "Legg til løft"),
      status,
      el("div", { class: "ark-knapper" },
        el("button", { class: `knapp ${aiPaa() ? "noytral" : ""}`, onclick: () => beregn(false) }, "Beregn"),
        aiPaa() ? el("button", { class: "knapp ai", onclick: () => beregn(true) }, ikon("gnist"), "Anslå med AI") : null));
  }

  function visResultat(r) {
    const vekter = {};
    const liste = el("div", { class: "velg-liste" });
    const ovl = r.forslag;
    for (const f of ovl) {
      vekter[f.ovelse] = f.kg;
      const inp = el("input", { type: "text", inputmode: "decimal", placeholder: "–", value: f.kg != null ? tall(f.kg) : "", oninput: (e) => { vekter[f.ovelse] = lesTall(e.target.value); } });
      liste.append(el("div", { class: "vekt-rad" },
        el("span", { class: "tekst" }, el("b", {}, f.navn),
          el("small", {}, [`${f.reps_min}–${f.reps_maks} reps`, f.type === "manualer" ? "per manual" : null, f.har_historikk ? "har historikk – den brukes først" : f.grunnlag ? `fra ${f.grunnlag}` : "fyll inn selv"].filter(Boolean).join(" · "))),
        el("span", { class: "vekt-inp" }, inp, el("span", {}, "kg"))));
    }
    aapneArk(el("h3", {}, r.kilde === "ai" ? ikon("gnist") : ikon("manual"), "Foreslåtte startvekter"),
      r.kommentar ? el("div", { class: "ai-kort", style: "margin:6px 0" }, el("p", {}, r.kommentar)) : null,
      el("p", { class: "hint" }, "Juster det som ikke stemmer. Vektene brukes som forslag første gang du gjør øvelsen – etter det tar fremgangen din over."),
      ovl.length ? liste : el("p", { class: "tom" }, "Programmet har ingen vektøvelser."),
      el("div", { class: "ark-knapper" }, el("button", { class: "knapp noytral", onclick: startvekterArk }, ikon("venstre"), "Tilbake"),
        el("button", { class: "knapp", onclick: async () => {
          try {
            const n = (await put(`api/profiler/${pid}/startvekter`, { vekter, kilde: r.kilde })).lagret;
            lukkArk(); visToast(`${n} startvekter lagret`);
            if (!$("v-okt").hidden && okt) visOkt(okt.id); else if (fane === "program") visProgram(); else visTrening();
          } catch (e) { feil(e); }
        } }, ikon("sjekk"), "Lagre")));
  }

  // ================================================================ BLOKKER
  function blokkBanner(prid, b) {
    return el("div", { class: "velkommen" },
      el("h2", {}, `Blokk ${b.nr} er fullført 🎉`),
      el("p", {}, "Tid for litt variasjon. Hovedøvelsene står fast så du kan fortsette å måle fremgangen, mens noen av de andre øvelsene byttes ut."),
      el("button", { class: "knapp", onclick: () => nyBlokk(prid, aiPaa()) }, aiPaa() ? ikon("gnist") : ikon("bytt"), "Se forslag til neste blokk"),
      el("button", { class: "knapp", style: "background:rgba(255,255,255,.18);color:#fff", onclick: async () => {
        if (!(await bekreft("Beholde programmet?", "Ny blokk starter med de samme øvelsene.", "Behold"))) return;
        try { await post(`api/programmer/${prid}/ny-blokk`, { beskrivelse: "Ny blokk uten endringer" }); visToast(`Blokk ${b.nr + 1} er i gang`); visTrening(); } catch (e) { feil(e); }
      } }, "Behold som det er"));
  }

  async function nyBlokk(prid, medAI) {
    const ark = aapneArk(el("h3", {}, ikon("bytt"), "Neste blokk"), el("div", { style: "margin-top:8px" },
      medAI ? aiLaster("Treneren ser på fremgangen og setter opp neste blokk …") : el("div", { class: "laster" }, "Lager forslag …")));
    void ark;
    try {
      const r = await post(`api/programmer/${prid}/blokkforslag`, { ai: medAI });
      lukkArk();
      visForslag(r.forslag, { kilde: r.kilde, program_id: prid, blokk: true });
    } catch (e) {
      lukkArk(); feil(e);
      if (medAI) visToast(`${e.message} – prøver uten AI`, [{ tekst: "Uten AI", fn: () => nyBlokk(prid, false) }], 8000);
    }
  }

  function blokkArk(p) {
    const b = p.blokk;
    let uker = b.uker, lett = b.lett_uke;
    const ukeValg = el("div", { class: "chips" }, [4, 5, 6, 8].map((n) => el("button", { class: `chip ${n === uker ? "valgt" : ""}`, onclick: (e) => {
      uker = n; for (const x of ukeValg.children) x.classList.toggle("valgt", x === e.currentTarget);
    } }, `${n} uker${n === 6 ? " (anbefalt)" : ""}`)));
    aapneArk(el("h3", {}, ikon("kalender"), "Treningsblokker"),
      el("p", { class: "hint" }, `Nå: ${blokkTekst(b)}. Blokka startet ${dato(b.start, true)}.`),
      el("div", { class: "info-boks" }, ikon("info"), "Anbefalt: blokker på 4–8 uker. 6 uker er lenge nok til å måle fremgang og kort nok til at variasjonen holder motivasjonen oppe. Hovedøvelsene står fast, og hjelpeøvelsene byttes ved hver ny blokk."),
      el("div", { class: "ark-etikett" }, "Lengde på blokka"), ukeValg,
      el("div", { class: "liste-rad", style: "min-height:0;padding:14px 2px 0" },
        el("span", { class: "tekst" }, el("b", {}, "Lettere uke til slutt"), el("small", {}, "Siste uke: halvparten av settene og samme vekt (deload). Anbefales når du har trent en stund – nybegynnere trenger det sjeldnere.")),
        bryter(lett, (x) => { lett = x; })),
      el("button", { class: "knapp sekundaer liten", style: "width:100%;margin-top:16px", onclick: () => { lukkArk(); nyBlokk(p.id, aiPaa()); } }, ikon("bytt"), "Start ny blokk nå"),
      el("div", { class: "ark-knapper" }, el("button", { class: "knapp noytral", onclick: lukkArk }, "Avbryt"),
        el("button", { class: "knapp", onclick: async () => {
          try { await patch(`api/programmer/${p.id}/blokk`, { blokk_uker: uker, lett_uke: lett }); lukkArk(); visProgram(); } catch (e) { feil(e); }
        } }, "Lagre")));
  }

  // ================================================================ PROGRAM
  async function visProgram() {
    vis("program");
    const v = $("v-program");
    if (!pid) { v.innerHTML = ""; v.append(el("p", { class: "tom" }, "Lag en profil først (Innstillinger).")); return; }
    let d;
    try { d = await api(`api/profiler/${pid}/programmer`); } catch (e) { feil(e); return; }
    v.innerHTML = "";
    const p = d.aktivt;
    settTittel("Program", p ? p.navn : "");
    if (!p) {
      v.append(el("div", { class: "kort" }, el("h2", {}, "Ingen aktivt program"),
        el("p", { class: "forklaring" }, "Et program gjør det enkelt å følge med på fremgang: appen foreslår vekt og reps hver økt, og øker når du er klar."),
        el("div", { class: "knapperad", style: "flex-direction:column" },
          aiPaa() ? el("button", { class: "knapp ai", onclick: () => nyttProgramArk(true) }, ikon("gnist"), "Lag med AI") : null,
          el("button", { class: "knapp sekundaer", onclick: () => nyttProgramArk(false) }, "Appens forslag"),
          el("button", { class: "knapp noytral", onclick: () => redigerProgram(null, { navn: "Mitt program", dager: [{ navn: "Økt A", ovelser: [] }] }) }, "Lag selv"))));
    } else {
      if (p.blokk.ferdig) v.append(blokkBanner(p.id, p.blokk));
      v.append(el("div", { class: "kort" },
        el("div", { class: "kort-hode" }, el("h2", {}, p.navn), el("span", { class: `merkelapp ${p.kilde === "ai" ? "ai" : "aksent"}` }, p.kilde === "ai" ? ikon("gnist") : null, p.kilde === "ai" ? "AI" : p.kilde === "mal" ? "Forslag" : "Egen")),
        p.beskrivelse ? el("p", { class: "forklaring" }, p.beskrivelse) : null,
        el("button", { class: "blokk-linje", onclick: () => blokkArk(p) },
          el("span", { class: "blokk-prikker" }, Array.from({ length: p.blokk.uker }, (_, i) => el("i", { class: `${i < p.blokk.uke - 1 ? "gjort" : i === p.blokk.uke - 1 ? "naa" : ""} ${p.blokk.lett_uke && i === p.blokk.uker - 1 ? "lett" : ""}` }))),
          el("span", { class: "blokk-tekst" }, blokkTekst(p.blokk)), ikon("hoyre")),
        p.begrunnelse ? el("details", {}, el("summary", { class: "lenke", style: "cursor:pointer" }, "Hvorfor dette programmet?"), el("p", { class: "begrunnelse", style: "margin-top:6px" }, p.begrunnelse)) : null,
        el("div", { class: "knapperad" },
          aiPaa() ? el("button", { class: "knapp ai-lys liten", style: "flex:1", onclick: () => justerArk(p) }, ikon("gnist"), "Juster med AI") : null,
          el("button", { class: "knapp noytral liten", style: "flex:1", onclick: () => redigerProgram(p.id, null) }, ikon("blyant"), "Rediger"))));
      for (const dag of p.dager) {
        v.append(el("div", { class: "dag-kort" },
          el("h3", {}, el("span", {}, dag.navn), el("small", {}, `ca. ${dag.minutter} min`)),
          el("ul", { class: "prog-liste" }, dag.ovelser.map((o) => el("li", {},
            el("button", { class: "rad", onclick: () => ovelseInfoArk(o.ovelse) },
              el("span", { class: "navn" }, el("span", { class: "navn-rad" }, o.navn, fastMerke(o)), el("small", {}, [`hvile ${hvileTekst(o.hvile_s)}`, `${o.rir} i reserve`, o.notat].filter(Boolean).join(" · "))),
              el("span", { class: "dose" }, `${o.sett} × ${o.reps_min}–${o.reps_maks}`))))),
          !dag.ovelser.length ? el("p", { class: "tom" }, "Ingen øvelser") : null));
      }
      v.append(el("div", { class: "knapperad" },
        el("button", { class: "knapp noytral liten", style: "flex:1", onclick: () => versjonerArk(p.id) }, ikon("klokke"), "Tidligere versjoner"),
        el("button", { class: "knapp noytral liten", style: "flex:1", onclick: () => nyttProgramArk(aiPaa()) }, ikon("pluss"), "Nytt program")));
      v.append(el("div", { class: "knapperad" },
        el("button", { class: "knapp noytral liten", style: "flex:1", onclick: startvekterArk }, ikon("manual"), "Startvekter"),
        el("button", { class: "knapp noytral liten", style: "flex:1", onclick: ovelsesbibliotek }, ikon("info"), "Øvelsesbibliotek")));
    }
    const andre = d.programmer.filter((x) => !x.aktiv);
    if (andre.length) {
      v.append(el("div", { class: "seksjon-tittel" }, "Andre programmer"));
      v.append(el("div", { class: "kort" }, el("ul", { class: "liste" }, andre.map((x) => el("li", {},
        el("div", { class: "liste-rad" }, el("span", { class: "tekst" }, el("b", {}, x.navn), el("small", {}, `${x.okter} økter · endret ${dato(x.endret, true)}`)),
          el("button", { class: "knapp sekundaer liten", onclick: async () => { try { await post(`api/programmer/${x.id}/aktiver`); visToast(`«${x.navn}» er aktivt`); visProgram(); } catch (e) { feil(e); } } }, "Bruk"),
          el("button", { class: "ikonknapp", "aria-label": "Fjern", onclick: async () => {
            if (!(await bekreft(`Fjerne «${x.navn}»?`, "Øktene du har gjort beholdes i historikken.", "Fjern", true))) return;
            try { await slett(`api/programmer/${x.id}`); visProgram(); } catch (e) { feil(e); }
          } }, ikon("soppel"))))))));
    }
  }

  function nyttProgramArk(medAI) {
    let stedId = sted();
    const onske = el("textarea", { placeholder: "Valgfritt: f.eks. «mest mulig effektivt på 45 min», «mer fokus på rygg og sete», «unngå markløft»" });
    const stedVelger = el("div", { class: "segment" }, S.utstyrsprofiler.map((u) => el("button", { class: u.id === stedId ? "valgt" : "", onclick: (e) => {
      stedId = u.id; for (const b of stedVelger.children) b.classList.toggle("valgt", b === e.currentTarget);
    } }, u.navn)));
    const p = profil();
    const knapp = el("button", { class: `knapp ${medAI ? "ai" : ""}` }, medAI ? ikon("gnist") : null, medAI ? "Lag program" : "Vis forslag");
    const status = el("div");
    knapp.addEventListener("click", async () => {
      knapp.disabled = true;
      status.innerHTML = "";
      if (medAI) status.append(el("div", { style: "margin-top:12px" }, aiLaster("Treneren setter opp programmet ditt … dette kan ta et halvt minutt.")));
      try {
        const r = medAI
          ? await post(`api/profiler/${pid}/ai/program`, { utstyrsprofil_id: stedId, onske: onske.value })
          : await post(`api/profiler/${pid}/forslag`, { utstyrsprofil_id: stedId });
        lukkArk();
        visForslag(r.forslag, { kilde: medAI ? "ai" : "mal" });
      } catch (e) { knapp.disabled = false; status.innerHTML = ""; feil(e); }
    });
    aapneArk(el("h3", {}, medAI ? ikon("gnist") : ikon("liste"), medAI ? "Nytt program med AI" : "Nytt program"),
      el("p", { class: "hint" }, `Bygges ut fra profilen: ${(p.maal || []).map((m) => S.maal[m]).join(", ")} · ${S.erfaring[p.erfaring]} · ${p.dager_per_uke} dager à ${p.okt_minutter} min.`,
        " ", el("button", { class: "lenke", onclick: () => { lukkArk(); profilArk(p); } }, "Endre profil")),
      S.utstyrsprofiler.length > 1 ? el("div", { class: "ark-etikett" }, "Hvor trener du mest?") : null,
      S.utstyrsprofiler.length > 1 ? stedVelger : null,
      medAI ? el("div", { class: "skjema", style: "margin-top:14px" }, felt("Ønsker til treneren", onske)) : null,
      !medAI && aiPaa() ? el("button", { class: "lenke", style: "margin-top:10px", onclick: () => { lukkArk(); nyttProgramArk(true); } }, ikon("gnist"), "Heller lage med AI") : null,
      status,
      el("div", { class: "ark-knapper" }, el("button", { class: "knapp noytral", onclick: lukkArk }, "Avbryt"), knapp));
  }

  function justerArk(p) {
    const onske = el("textarea", { placeholder: "F.eks. «jeg har bare 40 minutter», «vondt i venstre skulder», «jeg vil ha mer beinøvelser», «bytt ut markløft»", rows: 4 });
    const knapp = el("button", { class: "knapp ai" }, ikon("gnist"), "Foreslå endringer");
    const status = el("div");
    knapp.addEventListener("click", async () => {
      if (!onske.value.trim()) { onske.focus(); return; }
      knapp.disabled = true;
      status.innerHTML = "";
      status.append(el("div", { style: "margin-top:12px" }, aiLaster("Treneren ser på programmet …")));
      try {
        const r = await post(`api/profiler/${pid}/ai/program`, { program_id: p.id, onske: onske.value });
        lukkArk();
        visForslag(r.forslag, { kilde: "ai", program_id: p.id, beskrivelse: `AI: ${onske.value.trim().slice(0, 120)}` });
      } catch (e) { knapp.disabled = false; status.innerHTML = ""; feil(e); }
    });
    aapneArk(el("h3", {}, ikon("gnist"), "Juster programmet"),
      el("p", { class: "hint" }, "Fortell hva du vil endre. Du får se forslaget før noe lagres, og den gamle versjonen kan alltid hentes tilbake."),
      el("div", { class: "skjema" }, el("label", { class: "felt" }, onske)), status,
      el("div", { class: "ark-knapper" }, el("button", { class: "knapp noytral", onclick: lukkArk }, "Avbryt"), knapp));
    setTimeout(() => onske.focus(), 250);
  }

  function visForslag(f, { kilde, program_id = null, beskrivelse = "", blokk = false }) {
    vis("detalj", "program");
    settTittel(blokk ? "Forslag til neste blokk" : program_id ? "Forslag til endring" : "Forslag til program", f.navn);
    const v = $("v-detalj");
    v.innerHTML = "";
    v.append(el("button", { class: "tilbake", onclick: visProgram }, ikon("venstre"), "Program"));
    v.append(el("div", { class: kilde === "ai" ? "ai-kort" : "kort" },
      el("h3", { style: "margin:0;font-size:20px;font-weight:900;display:flex;gap:8px;align-items:center" }, kilde === "ai" ? ikon("gnist") : null, f.navn),
      f.beskrivelse ? el("p", {}, f.beskrivelse) : null,
      f.endringer?.length ? el("div", {}, el("b", {}, "Endringer:"), el("ul", { class: "endringer", style: "margin-top:6px" }, f.endringer.map((x) => el("li", {}, x)))) : null,
      f.begrunnelse ? el("p", { style: "font-weight:600;opacity:.9" }, f.begrunnelse) : null));
    for (const dag of f.dager) {
      v.append(el("div", { class: "dag-kort" }, el("h3", {}, el("span", {}, dag.navn), el("small", {}, `ca. ${dag.minutter} min`)),
        el("ul", { class: "prog-liste" }, dag.ovelser.map((o) => el("li", {},
          el("span", { class: "navn" }, el("span", { class: "navn-rad" }, o.navn, fastMerke(o)), el("small", {}, [`hvile ${hvileTekst(o.hvile_s)}`, `${o.rir} i reserve`, o.notat].filter(Boolean).join(" · "))),
          el("span", { class: "dose" }, `${o.sett} × ${o.reps_min}–${o.reps_maks}`))))));
    }
    const data = { navn: f.navn, beskrivelse: f.beskrivelse, begrunnelse: f.begrunnelse, dager: f.dager.map((d) => ({ navn: d.navn, ovelser: d.ovelser.map(({ ovelse: o, sett, reps_min, reps_maks, hvile_s, rir, notat, fast }) => ({ ovelse: o, sett, reps_min, reps_maks, hvile_s, rir, notat, fast })) })) };
    v.append(el("div", { class: "knapperad" },
      el("button", { class: "knapp noytral", onclick: () => redigerProgram(program_id, data, { kilde, beskrivelse, blokk }) }, ikon("blyant"), "Tilpass først"),
      el("button", { class: "knapp", onclick: async () => {
        try {
          if (blokk) { const r = await post(`api/programmer/${program_id}/ny-blokk`, { program: data, kilde, beskrivelse: kilde === "ai" ? "Ny blokk fra AI" : "Ny blokk" }); visToast(`Blokk ${r.program.blokk.nr} er i gang – god trening!`); visTrening(); return; }
          if (program_id) await put(`api/programmer/${program_id}`, { program: data, kilde, beskrivelse: beskrivelse || "Justert" });
          else await post(`api/profiler/${pid}/programmer`, { program: data, kilde, beskrivelse: kilde === "ai" ? "Laget av AI" : "Fra appens forslag" });
          visToast(program_id ? "Programmet er oppdatert" : "Programmet er klart – god trening!");
          visTrening();
        } catch (e) { feil(e); }
      } }, ikon("sjekk"), blokk ? "Start neste blokk" : program_id ? "Bruk endringene" : "Bruk programmet")));
    if (!program_id) v.append(el("p", { class: "forklaring", style: "text-align:center" }, "Et eventuelt eksisterende program blir liggende under «Andre programmer»."));
  }

  async function redigerProgram(prid, data, { kilde = "egen", beskrivelse = "", blokk = false } = {}) {
    if (!data) {
      try { const p = (await api(`api/programmer/${prid}`)).program; data = { navn: p.navn, beskrivelse: p.beskrivelse, begrunnelse: p.begrunnelse, dager: p.dager.map((d) => ({ navn: d.navn, ovelser: d.ovelser.map(({ ovelse: o, sett, reps_min, reps_maks, hvile_s, rir, notat, fast }) => ({ ovelse: o, sett, reps_min, reps_maks, hvile_s, rir, notat, fast })) })) }; } catch (e) { feil(e); return; }
    }
    const kopi = JSON.parse(JSON.stringify(data));
    vis("detalj", "program");
    settTittel(prid ? "Rediger program" : "Nytt program", "");
    const v = $("v-detalj");
    const tegn = () => {
      v.innerHTML = "";
      v.append(el("button", { class: "tilbake", onclick: async () => { if (await bekreft("Forkaste endringene?", "", "Forkast", true)) visProgram(); } }, ikon("venstre"), "Avbryt"));
      const navn = el("input", { value: kopi.navn, oninput: (e) => { kopi.navn = e.target.value; } });
      v.append(el("div", { class: "kort" }, felt("Navn på programmet", navn)));
      kopi.dager.forEach((dag, di) => {
        const dnavn = el("input", { value: dag.navn, oninput: (e) => { dag.navn = e.target.value; }, style: "font-weight:900" });
        v.append(el("div", { class: "dag-kort" },
          el("div", { style: "display:flex;gap:8px;align-items:center" }, el("label", { class: "felt", style: "flex:1" }, dnavn),
            el("button", { class: "ikonknapp", "aria-label": "Fjern økt", onclick: async () => {
              if (dag.ovelser.length && !(await bekreft(`Fjerne «${dag.navn}»?`, "", "Fjern", true))) return;
              kopi.dager.splice(di, 1); tegn();
            } }, ikon("soppel"))),
          el("ul", { class: "prog-liste" }, dag.ovelser.map((o, oi) => el("li", {},
            el("span", { class: "rekkefolge" },
              el("button", { "aria-label": "Flytt opp", disabled: oi === 0, onclick: () => { [dag.ovelser[oi - 1], dag.ovelser[oi]] = [dag.ovelser[oi], dag.ovelser[oi - 1]]; tegn(); } }, ikon("opp")),
              el("button", { "aria-label": "Flytt ned", disabled: oi === dag.ovelser.length - 1, onclick: () => { [dag.ovelser[oi + 1], dag.ovelser[oi]] = [dag.ovelser[oi], dag.ovelser[oi + 1]]; tegn(); } }, ikon("ned"))),
            el("button", { class: "rad", onclick: () => doseArk(o, () => { dag.ovelser.splice(oi, 1); tegn(); }, tegn) },
              el("span", { class: "navn" }, el("span", { class: "navn-rad" }, ovelse(o.ovelse).navn, fastMerke(o)), el("small", {}, [`hvile ${hvileTekst(o.hvile_s)}`, `${o.rir} i reserve`, o.notat].filter(Boolean).join(" · "))),
              el("span", { class: "dose" }, `${o.sett} × ${o.reps_min}–${o.reps_maks}`))))),
          el("button", { class: "legg-til", onclick: () => aapneOvelsevelger({ tittel: `Legg til i ${dag.navn}`, utstyrsprofil_id: sted(), ved_valg: (x) => {
            const stor = ["kne", "hofte", "utfall", "press_hor", "press_vert", "trekk_hor", "trekk_vert", "sete"].includes(x.monster);
            const hoved = ["kne", "hofte", "press_hor", "press_vert", "trekk_hor", "trekk_vert"].includes(x.monster);
            dag.ovelser.push({ ovelse: x.nokkel, sett: 3, reps_min: stor ? 8 : 10, reps_maks: stor ? 12 : 15, hvile_s: stor ? 90 : 60, rir: 2, notat: "", fast: hoved ? 1 : 0 });
            lukkArk(); tegn();
          } }) }, ikon("pluss"), "Legg til øvelse")));
      });
      if (kopi.dager.length < 7) v.append(el("button", { class: "legg-til", onclick: () => { kopi.dager.push({ navn: `Økt ${String.fromCharCode(65 + kopi.dager.length)}`, ovelser: [] }); tegn(); } }, ikon("pluss"), "Legg til økt"));
      v.append(el("button", { class: "knapp", onclick: async () => {
        try {
          if (blokk) await post(`api/programmer/${prid}/ny-blokk`, { program: kopi, kilde, beskrivelse: "Ny blokk (tilpasset)" });
          else if (prid) await put(`api/programmer/${prid}`, { program: kopi, kilde, beskrivelse: beskrivelse || "Redigert" });
          else await post(`api/profiler/${pid}/programmer`, { program: kopi, kilde, beskrivelse: beskrivelse || "Opprettet" });
          visToast("Programmet er lagret");
          visProgram();
        } catch (e) { feil(e); }
      } }, ikon("sjekk"), "Lagre programmet"));
    };
    tegn();
  }

  function doseArk(o, fjern, ferdig) {
    const sett_ = tallStepper(o.sett, 1, 1, 8);
    const rmin = el("input", { type: "text", inputmode: "numeric", value: o.reps_min });
    const rmaks = el("input", { type: "text", inputmode: "numeric", value: o.reps_maks });
    const hvile = tallStepper(o.hvile_s, 15, 15, 600, hvileTekst);
    const rir = tallStepper(o.rir, 1, 0, 5, (x) => `${x} reps`);
    const notat = el("input", { value: o.notat || "", placeholder: "F.eks. «rolig tempo ned»" });
    let fast = !!o.fast;
    aapneArk(el("h3", {}, ovelse(o.ovelse).navn),
      el("div", { class: "skjema" }, felt("Sett", sett_), el("div", { class: "felt-rad" }, felt("Reps fra", rmin), felt("Reps til", rmaks)),
        felt("Hvile mellom sett", hvile), felt("Reps i reserve (hvor nær utmattelse)", rir, "2 = du kunne klart 2 til. Lavere = tyngre."), felt("Notat", notat),
        el("div", { class: "liste-rad", style: "min-height:0;padding:0" }, el("span", { class: "tekst" }, el("b", {}, "Fast hovedøvelse"), el("small", {}, "Beholdes når det lages ny blokk")), bryter(fast, (x) => { fast = x; }))),
      el("div", { class: "knapperad", style: "margin-top:14px" },
        el("button", { class: "knapp noytral liten", style: "flex:1", onclick: () => ovelseInfoArk(o.ovelse, null, { tilbake: () => doseArk(o, fjern, ferdig) }) }, ikon("info"), "Slik gjør du"),
        el("button", { class: "knapp noytral liten", style: "flex:1", onclick: () => byttOvelseArk({ ovelse: o.ovelse }, { utstyrsprofil_id: sted(), ved_valg: (a) => { o.ovelse = a.nokkel; ferdig(); } }) }, ikon("bytt"), "Bytt øvelse"),
        el("button", { class: "knapp fare liten", onclick: () => { lukkArk(); fjern(); } }, ikon("soppel"), "Fjern")),
      el("div", { class: "ark-knapper" }, el("button", { class: "knapp noytral", onclick: lukkArk }, "Avbryt"),
        el("button", { class: "knapp", onclick: () => {
          const a = parseInt(rmin.value, 10), b = parseInt(rmaks.value, 10);
          if (!Number.isFinite(a) || !Number.isFinite(b)) { visToast("Skriv inn reps"); return; }
          Object.assign(o, { sett: sett_.verdi(), reps_min: Math.min(a, b), reps_maks: Math.max(a, b), hvile_s: hvile.verdi(), rir: rir.verdi(), notat: notat.value, fast: fast ? 1 : 0 });
          lukkArk(); ferdig();
        } }, "OK")));
  }

  async function versjonerArk(prid) {
    let vs;
    try { vs = (await api(`api/programmer/${prid}`)).versjoner; } catch (e) { feil(e); return; }
    aapneArk(el("h3", {}, ikon("klokke"), "Tidligere versjoner"),
      el("p", { class: "hint" }, "Hver endring av programmet lagres. Gjenopprett en eldre versjon om du vil tilbake – den nåværende blir også liggende her."),
      el("div", {}, vs.map((x, i) => el("div", { class: "versjon" },
        el("span", { class: "tekst" }, el("b", {}, x.beskrivelse || "Endret"),
          el("small", {}, `${dato(x.tid, true)} kl. ${kl(x.tid)} · ${x.data.dager.length} økter · ${x.data.dager.reduce((s, d) => s + d.ovelser.length, 0)} øvelser`)),
        el("button", { class: "lenke", onclick: () => visVersjon(x) }, "Vis"),
        i > 0 ? el("button", { class: "knapp sekundaer liten", onclick: async () => {
          try { await post(`api/versjoner/${x.id}/gjenopprett`); lukkArk(); visToast("Versjonen er gjenopprettet"); visProgram(); } catch (e) { feil(e); }
        } }, "Gjenopprett") : el("span", { class: "merkelapp opp" }, "Nå")))));
  }

  function visVersjon(x) {
    aapneArk(el("h3", {}, x.data.navn), el("p", { class: "hint" }, `${x.beskrivelse} · ${dato(x.tid, true)}`),
      x.data.dager.map((d) => el("div", { style: "margin-top:12px" }, el("b", {}, d.navn),
        el("ul", { class: "prog-liste" }, d.ovelser.map((o) => el("li", {}, el("span", { class: "navn" }, ovelse(o.ovelse).navn), el("span", { class: "dose" }, `${o.sett} × ${o.reps_min}–${o.reps_maks}`)))))));
  }

  // ================================================================ HISTORIKK
  let histData = null;
  async function visHistorikk() {
    vis("historikk");
    const v = $("v-historikk");
    if (!pid) { v.innerHTML = ""; return; }
    try { histData = await api(`api/profiler/${pid}/historikk`); } catch (e) { feil(e); return; }
    settTittel("Historikk", `${histData.statistikk.totalt} ${histData.statistikk.totalt === 1 ? "økt" : "økter"}${histData.statistikk.forste ? ` siden ${dato(histData.statistikk.forste, true)}` : ""}`);
    tegnHistorikk();
  }

  function tegnHistorikk() {
    const v = $("v-historikk");
    v.innerHTML = "";
    v.append(el("div", { class: "segment" }, [["okter", "Økter"], ["ovelser", "Øvelser"], ["fremgang", "Fremgang"]].map(([k, n]) =>
      el("button", { class: histFane === k ? "valgt" : "", onclick: () => { histFane = k; lagre("histfane", k); tegnHistorikk(); } }, n))));
    if (histFane === "okter") tegnOktListe(v);
    if (histFane === "ovelser") tegnOvelseListe(v);
    if (histFane === "fremgang") tegnFremgang(v);
  }

  function tegnOktListe(v) {
    const okter = histData.okter;
    if (!okter.length) v.append(el("p", { class: "tom" }, "Ingen fullførte økter ennå."));
    let mnd = null, kort = null;
    for (const o of okter) {
      const m = new Date(o.startet).toLocaleDateString("nb-NO", { month: "long", year: "numeric" });
      if (m !== mnd) {
        mnd = m;
        v.append(el("div", { class: "maaned" }, m));
        kort = el("div", { class: "kort", style: "padding:4px 16px" });
        v.append(kort);
      }
      const d = new Date(o.startet);
      kort.append(el("button", { class: "okt-rad", onclick: () => visOktDetalj(o.id, "historikk") },
        el("span", { class: "dato-boks" }, el("b", {}, d.getDate()), el("small", {}, d.toLocaleDateString("nb-NO", { weekday: "short" }).replace(".", ""))),
        el("span", { class: "tekst" }, el("b", {}, o.dag_navn), el("small", {}, `${o.minutter} min · ${o.sett} sett · ${tusen(o.volum)} kg${o.opplevd ? ` · ${OPPLEVD[o.opplevd].toLowerCase()}` : ""}`),
          el("small", {}, o.ovelser.join(", "))),
        o.har_ai ? el("span", { class: "merkelapp ai" }, ikon("gnist")) : null, ikon("hoyre")));
    }
    v.append(el("button", { class: "legg-til", onclick: tidligereOktArk }, ikon("kalender"), "Legg inn en økt du har gjort tidligere"));
    v.append(el("a", { class: "lenke", href: `api/eksport.csv?profil=${pid}`, download: "styrkeboka.csv", style: "align-self:center" }, ikon("last-ned"), "Last ned alt som CSV"));
  }

  function tidligereOktArk() {
    const tid = el("input", { type: "datetime-local", value: tilLokalInput(Date.now() - 864e5) });
    const navn = el("input", { value: "Økt", placeholder: "Navn" });
    const min = el("input", { type: "text", inputmode: "numeric", value: "60" });
    aapneArk(el("h3", {}, ikon("kalender"), "Tidligere økt"), el("p", { class: "hint" }, "Lag økten først, så legger du inn øvelser og sett."),
      el("div", { class: "skjema" }, felt("Når", tid), el("div", { class: "felt-rad" }, felt("Navn", navn), felt("Minutter", min))),
      el("div", { class: "ark-knapper" }, el("button", { class: "knapp noytral", onclick: lukkArk }, "Avbryt"),
        el("button", { class: "knapp", onclick: async () => {
          try { const r = await post(`api/profiler/${pid}/tidligere-okt`, { startet: new Date(tid.value).toISOString(), navn: navn.value, minutter: min.value }); lukkArk(); visOktDetalj(r.okt.id, "historikk"); } catch (e) { feil(e); }
        } }, "Lag økt")));
  }

  async function visOktDetalj(oid, fra = "historikk") {
    let o;
    try { o = (await api(`api/okter/${oid}`)).okt; } catch (e) { feil(e); return; }
    vis("detalj", fra);
    settTittel(o.dag_navn, `${ukedag(o.startet)} kl. ${kl(o.startet)}`);
    const v = $("v-detalj");
    v.innerHTML = "";
    const tilbake = () => fra === "trening" ? visTrening() : visHistorikk();
    v.append(el("button", { class: "tilbake", onclick: tilbake }, ikon("venstre"), fra === "trening" ? "Trening" : "Historikk"));
    v.append(el("div", { class: "kort" }, nokkeltall(o),
      el("div", { class: "chips" },
        o.sted ? el("span", { class: "merkelapp" }, ikon("sted"), o.sted) : null,
        o.opplevd ? el("span", { class: "merkelapp aksent" }, `Opplevd: ${OPPLEVD[o.opplevd]}`) : null,
        o.av ? el("span", { class: "merkelapp" }, `Registrert av ${o.av}`) : null),
      o.notat ? el("p", { class: "forklaring", style: "font-style:italic" }, `«${o.notat}»`) : null));
    const aiRot = el("div");
    v.append(aiRot);
    if (o.ai_oppsummering) {
      aiRot.append(el("div", { class: "ai-kort" }, el("h3", {}, ikon("gnist"), "Treneren sa"), el("p", {}, o.ai_oppsummering.oppsummering),
        o.ai_oppsummering.neste_gang?.length ? el("ul", {}, o.ai_oppsummering.neste_gang.map((x) => el("li", {}, x))) : null));
    } else if (aiPaa() && o.status === "fullfort" && o.nokkeltall.sett) {
      aiRot.append(el("button", { class: "knapp ai-lys", style: "width:100%", onclick: () => hentOppsummering(o.id, aiRot) }, ikon("gnist"), "Få oppsummering fra treneren"));
    }
    const k = el("div", { class: "kort" }, el("div", { class: "kort-hode" }, el("h2", {}, "Øvelser"), el("span", { class: "forklaring", style: "font-size:13px" }, "Trykk på et sett for å endre")));
    for (const oo of o.ovelser) {
      k.append(el("div", { class: "detalj-ov" },
        el("div", { style: "display:flex;align-items:center;gap:8px" }, el("b", { style: "flex:1" }, oo.info.navn),
          el("button", { class: "lenke", onclick: () => visOvelseHistorikk(oo.ovelse, () => visOktDetalj(oid, fra)) }, ikon("graf"))),
        el("div", { class: "sett-chips" },
          oo.sett.map((s) => el("button", { class: s.oppvarming ? "oppv" : "", onclick: () => endreSettArk(s, oo, () => visOktDetalj(oid, fra)) },
            s.vekt != null ? `${tall(s.vekt)} × ${s.reps}` : `${s.reps}${oo.info.sekunder ? " s" : ""}`, s.rir != null ? ` @${s.rir}` : "")),
          el("button", { onclick: () => leggTilSettArk(o, oo, () => visOktDetalj(oid, fra)) }, "+")),
        oo.notat ? el("div", { class: "ov-notat" }, oo.notat) : null));
    }
    if (!o.ovelser.length) k.append(el("p", { class: "tom" }, "Ingen øvelser registrert."));
    k.append(el("button", { class: "legg-til", onclick: () => aapneOvelsevelger({ tittel: "Legg til øvelse", utstyrsprofil_id: o.utstyrsprofil_id, ved_valg: async (x) => {
      try { await post(`api/okter/${o.id}/ovelser`, { ovelse: x.nokkel }); lukkArk(); visOktDetalj(oid, fra); } catch (e) { feil(e); }
    } }) }, ikon("pluss"), "Legg til øvelse"));
    v.append(k);
    v.append(el("div", { class: "knapperad" },
      el("button", { class: "knapp noytral liten", style: "flex:1", onclick: () => endreOktArk(o, () => visOktDetalj(oid, fra)) }, ikon("blyant"), "Endre dato og notat"),
      el("button", { class: "knapp fare liten", onclick: async () => {
        if (!(await bekreft("Slette økten?", "Økten og alle settene slettes for godt.", "Slett", true))) return;
        try { await slett(`api/okter/${o.id}`); tilbake(); } catch (e) { feil(e); }
      } }, ikon("soppel"), "Slett")));
  }

  function leggTilSettArk(o, oo, etter) {
    const siste = oo.sett.filter((s) => !s.oppvarming).slice(-1)[0];
    const kgInp = el("input", { type: "text", inputmode: "decimal", value: siste?.vekt != null ? tall(siste.vekt) : "" });
    const repsInp = el("input", { type: "text", inputmode: "numeric", value: siste?.reps ?? "" });
    aapneArk(el("h3", {}, ikon("pluss"), `Nytt sett – ${oo.info.navn}`),
      el("div", { class: "skjema" }, el("div", { class: "felt-rad" }, felt("Vekt (kg)", kgInp), felt(oo.info.sekunder ? "Sekunder" : "Reps", repsInp))),
      el("div", { class: "ark-knapper" }, el("button", { class: "knapp noytral", onclick: lukkArk }, "Avbryt"),
        el("button", { class: "knapp", onclick: async () => {
          try { await post(`api/okter/${o.id}/sett`, { okt_ovelse_id: oo.id, vekt: lesTall(kgInp.value), reps: parseInt(repsInp.value, 10) }); lukkArk(); etter(); } catch (e) { feil(e); }
        } }, "Legg til")));
  }

  function endreOktArk(o, etter) {
    const tid = el("input", { type: "datetime-local", value: tilLokalInput(o.startet) });
    const notat = el("textarea", {}, o.notat || "");
    let opplevd = o.opplevd;
    const knapper = el("div", { class: "opplevd" }, [1, 2, 3, 4, 5].map((n) => el("button", { class: n === opplevd ? "valgt" : "", onclick: (e) => {
      opplevd = n; for (const b of knapper.children) b.classList.toggle("valgt", b === e.currentTarget);
    } }, el("b", {}, String(n)), OPPLEVD[n])));
    aapneArk(el("h3", {}, ikon("blyant"), "Endre økt"),
      el("div", { class: "skjema" }, felt("Startet", tid)), el("div", { class: "ark-etikett" }, "Opplevd tyngde"), knapper,
      el("div", { class: "skjema", style: "margin-top:12px" }, felt("Notat", notat)),
      el("div", { class: "ark-knapper" }, el("button", { class: "knapp noytral", onclick: lukkArk }, "Avbryt"),
        el("button", { class: "knapp", onclick: async () => {
          try { await patch(`api/okter/${o.id}`, { startet: new Date(tid.value).toISOString(), notat: notat.value, opplevd }); lukkArk(); etter(); } catch (e) { feil(e); }
        } }, "Lagre")));
  }

  function tegnOvelseListe(v) {
    const liste = histData.ovelser;
    if (!liste.length) { v.append(el("p", { class: "tom" }, "Når du har trent, ser du fremgangen per øvelse her.")); return; }
    v.append(el("div", { class: "kort", style: "padding:4px 16px" }, liste.map((o) => el("button", { class: "okt-rad", onclick: () => visOvelseHistorikk(o.ovelse, visHistorikk) },
      el("span", { class: "tekst" }, el("b", {}, o.navn), el("small", {}, `${o.okter} økter · sist ${dato(o.sist)} · ${S.monster[o.monster] || ""}`)), ikon("hoyre")))));
  }

  async function visOvelseHistorikk(nokkel, tilbake) {
    let h;
    try { h = await api(`api/profiler/${pid}/ovelse?nokkel=${encodeURIComponent(nokkel)}`); } catch (e) { feil(e); return; }
    vis("detalj", "historikk");
    settTittel(h.ovelse.navn, S.monster[h.ovelse.monster] || "");
    const v = $("v-detalj");
    v.innerHTML = "";
    v.append(el("button", { class: "tilbake", onclick: tilbake }, ikon("venstre"), "Tilbake"));
    const p = h.punkter;
    const b = h.beste;
    v.append(el("div", { class: "nokkeltall" },
      h.vektbasert ? el("div", { class: "tall-boks" }, el("span", { class: "tall-verdi" }, kg(b.vekt)), el("span", { class: "tall-navn" }, "tyngste vekt")) : null,
      h.vektbasert ? el("div", { class: "tall-boks" }, el("span", { class: "tall-verdi" }, kg(b.e1rm)), el("span", { class: "tall-navn" }, "beste est. 1RM")) : null,
      el("div", { class: "tall-boks" }, el("span", { class: "tall-verdi" }, String(b.reps ?? "–")), el("span", { class: "tall-navn" }, h.sekunder ? "flest sekunder" : "flest reps")),
      !h.vektbasert ? el("div", { class: "tall-boks" }, el("span", { class: "tall-verdi" }, String(p.length)), el("span", { class: "tall-navn" }, "økter")) : null,
      !h.vektbasert ? el("div", { class: "tall-boks" }, el("span", { class: "tall-verdi" }, p.length ? dato(p[p.length - 1].startet) : "–"), el("span", { class: "tall-navn" }, "sist")) : null));
    if (p.length >= 2) {
      const serie = h.vektbasert ? p.map((x) => ({ t: x.startet, y: x.e1rm ?? x.topp_kg })) : p.map((x) => ({ t: x.startet, y: x.maks_reps }));
      v.append(el("div", { class: "kort" }, el("h2", {}, h.vektbasert ? "Estimert 1RM over tid" : (h.sekunder ? "Flest sekunder per økt" : "Flest reps per økt")),
        linjegraf(serie.filter((x) => x.y != null), h.vektbasert ? " kg" : ""),
        h.vektbasert ? el("p", { class: "forklaring", style: "font-size:13px" }, "Estimert 1RM (Epley) regnes fra beste sett hver økt – et mål på styrke som tåler at reps varierer.") : null));
    }
    v.append(el("div", { class: "kort" }, el("h2", {}, "Alle økter"),
      p.length ? el("div", { class: "tabell-wrap" }, el("table", { class: "tabell" },
        el("thead", {}, el("tr", {}, el("th", {}, "Dato"), el("th", {}, "Sett"), h.vektbasert ? el("th", {}, "1RM") : null)),
        el("tbody", {}, [...p].reverse().map((x) => el("tr", {},
          el("td", {}, dato(x.startet, true)),
          el("td", {}, x.sett.map((s) => s.vekt != null ? `${tall(s.vekt)}×${s.reps}` : `${s.reps}`).join(", ")),
          h.vektbasert ? el("td", {}, x.e1rm ? tall(x.e1rm) : "–") : null))))) : el("p", { class: "tom" }, "Ingen data")));
    v.append(el("div", { class: "kort" }, el("h2", {}, "Slik gjør du øvelsen"), el("div", { class: "instruksjon" }, instruksjonInnhold({ ...ovelse(nokkel), ...h.ovelse })),
      el("div", { class: "knapperad" }, videoLenke(h.ovelse))));
  }

  function linjegraf(serie, enhet = "") {
    const B = 320, H = 150, ml = 34, mr = 8, mt = 12, mb = 22;
    const ys = serie.map((p) => p.y);
    let min = Math.min(...ys), maks = Math.max(...ys);
    if (min === maks) { min -= 5; maks += 5; }
    const pad = (maks - min) * 0.15;
    min = Math.max(0, min - pad); maks += pad;
    const t0 = new Date(serie[0].t).getTime(), t1 = new Date(serie[serie.length - 1].t).getTime() || t0 + 1;
    const x = (t) => ml + ((new Date(t).getTime() - t0) / Math.max(1, t1 - t0)) * (B - ml - mr);
    const y = (v) => mt + (1 - (v - min) / (maks - min)) * (H - mt - mb);
    const svg = svgEl("svg", { viewBox: `0 0 ${B} ${H}`, role: "img", "aria-label": "Graf over fremgang" });
    for (let i = 0; i <= 3; i++) {
      const v = min + (maks - min) * i / 3;
      svg.append(svgEl("line", { class: "rutenett", x1: ml, x2: B - mr, y1: y(v), y2: y(v) }));
      svg.append(svgEl("text", { class: "akse-tekst", x: ml - 6, y: y(v) + 3, "text-anchor": "end" }, Math.round(v)));
    }
    const d = serie.map((p, i) => `${i ? "L" : "M"}${x(p.t).toFixed(1)},${y(p.y).toFixed(1)}`).join(" ");
    svg.append(svgEl("path", { class: "felt", d: `${d} L${x(serie[serie.length - 1].t)},${H - mb} L${x(serie[0].t)},${H - mb} Z` }));
    svg.append(svgEl("path", { class: "linje", d }));
    serie.forEach((p) => { const c = svgEl("circle", { class: "punkt", cx: x(p.t), cy: y(p.y), r: 3.5 }); c.append(svgEl("title", {}, `${dato(p.t, true)}: ${tall(p.y)}${enhet}`)); svg.append(c); });
    svg.append(svgEl("text", { class: "akse-tekst", x: ml, y: H - 6 }, dato(serie[0].t)));
    svg.append(svgEl("text", { class: "akse-tekst", x: B - mr, y: H - 6, "text-anchor": "end" }, dato(serie[serie.length - 1].t)));
    return el("div", { class: "graf" }, svg);
  }

  function tegnFremgang(v) {
    const st = histData.statistikk;
    // økter per uke
    const B = 320, H = 130, mb = 20, mt = 14;
    const maks = Math.max(st.plan_per_uke, ...st.uker.map((u) => u.okter), 1);
    const bw = B / st.uker.length;
    const svg = svgEl("svg", { viewBox: `0 0 ${B} ${H}`, role: "img", "aria-label": "Økter per uke" });
    const yv = (n) => mt + (1 - n / maks) * (H - mt - mb);
    svg.append(svgEl("line", { class: "maal-linje", x1: 0, x2: B, y1: yv(st.plan_per_uke), y2: yv(st.plan_per_uke) }));
    st.uker.forEach((u, i) => {
      const h = Math.max(3, (H - mt - mb) * u.okter / maks);
      svg.append(svgEl("rect", { class: `soyle ${u.okter ? "" : "tom"}`, x: i * bw + 4, y: H - mb - h, width: bw - 8, height: h, rx: 4 }));
      if (u.okter) svg.append(svgEl("text", { class: "verdi-tekst", x: i * bw + bw / 2, y: H - mb - h - 3, "text-anchor": "middle" }, u.okter));
      if (i % 2 === 1 || i === st.uker.length - 1) svg.append(svgEl("text", { class: "akse-tekst", x: i * bw + bw / 2, y: H - 5, "text-anchor": "middle" }, `u${u.uke}`));
    });
    v.append(el("div", { class: "kort" }, el("div", { class: "kort-hode" }, el("h2", {}, "Økter per uke"), st.uker_paa_rad > 1 ? el("span", { class: "flamme" }, ikon("flamme"), `${st.uker_paa_rad} uker på rad`) : null),
      el("div", { class: "graf" }, svg), el("p", { class: "forklaring", style: "font-size:13px" }, `Stiplet linje = målet ditt (${st.plan_per_uke} i uka).`)));
    // sett per muskelgruppe
    const maksSett = Math.max(20, ...st.muskler.map((m) => m.uke));
    v.append(el("div", { class: "kort" }, el("h2", {}, "Harde sett per muskelgruppe – siste 7 dager"),
      st.muskler.map((m) => el("div", { class: "muskel-rad" }, el("span", {}, m.navn),
        el("span", { class: "muskel-bar" }, st.muskelvekst ? el("b", { style: `left:${100 * 10 / maksSett}%;width:${100 * 10 / maksSett}%` }) : null, el("i", { style: `width:${100 * m.uke / maksSett}%` })),
        el("span", {}, tall(m.uke)))),
      el("p", { class: "forklaring", style: "font-size:13px" }, st.muskelvekst
        ? "Grønt felt = 10–20 sett i uka, et vanlig mål for muskelvekst. Hovedmuskelen i en øvelse teller ett sett, hjelpemuskler et halvt."
        : "Hovedmuskelen i en øvelse teller ett sett, hjelpemuskler et halvt. For generell styrke holder det godt med noen sett per muskelgruppe 2 dager i uka.")));
  }

  // ================================================================ INNSTILLINGER
  async function visInnstillinger() {
    vis("innstillinger");
    settTittel("Innstillinger", "");
    try { await lastStart(); } catch (e) { feil(e); }
    const v = $("v-innstillinger");
    v.innerHTML = "";

    v.append(el("div", { class: "seksjon-tittel" }, "Profiler"));
    v.append(el("div", { class: "kort", style: "padding:4px 16px" },
      el("ul", { class: "liste" }, S.profiler.map((p) => el("li", {}, el("button", { class: "liste-rad", onclick: () => profilArk(p) }, avatar(p),
        el("span", { class: "tekst" }, el("b", {}, p.navn), el("small", {}, [(p.maal || []).map((m) => S.maal[m]).join(", "), `${p.dager_per_uke} dager`, p.ha_bruker ? `HA: ${p.ha_bruker}` : null].filter(Boolean).join(" · "))), ikon("hoyre"))))),
      el("button", { class: "legg-til", style: "margin:8px 0 12px", onclick: () => profilArk(null) }, ikon("pluss"), "Ny profil")));

    v.append(el("div", { class: "seksjon-tittel" }, "Treningssteder og utstyr"));
    v.append(el("div", { class: "kort", style: "padding:4px 16px" },
      el("ul", { class: "liste" }, S.utstyrsprofiler.map((u) => el("li", {}, el("button", { class: "liste-rad", onclick: () => stedArk(u) }, ikon("sted"),
        el("span", { class: "tekst" }, el("b", {}, u.navn), el("small", {}, u.utstyr.map((x) => S.utstyr[x]).join(", ") || "Bare kroppsvekt")), ikon("hoyre"))))),
      el("button", { class: "legg-til", style: "margin:8px 0 12px", onclick: () => stedArk(null) }, ikon("pluss"), "Nytt sted")));

    v.append(el("div", { class: "seksjon-tittel" }, "AI-treneren"));
    const aiKort = el("div", { class: "kort" });
    v.append(aiKort);
    const lagreInn = async (d) => { try { S.innstillinger = (await put("api/innstillinger", d)).innstillinger; } catch (e) { feil(e); } };
    aiKort.append(el("div", { class: "liste-rad", style: "min-height:0;padding:0" }, el("span", { class: "tekst" }, el("b", {}, "Bruk AI-treneren"), el("small", {}, "Lager og justerer program, gir tips og oppsummerer økter")), bryter(S.innstillinger.ai_paa, (x) => lagreInn({ ai_paa: x }))));
    if (!S.ai_tilgjengelig) aiKort.append(el("div", { class: "info-boks obs" }, ikon("advarsel"), "Ingen kontakt med Home Assistant akkurat nå – AI er ikke tilgjengelig."));
    const velg = el("select", { onchange: () => lagreInn({ ai_entitet: velg.value }) }, el("option", { value: "" }, "Velg automatisk"));
    aiKort.append(felt("Hvilken AI i Home Assistant", velg, "Bruker «AI-oppgave»-entiteter (ai_task) fra f.eks. Anthropic-integrasjonen. Navn sendes aldri – bare mål, utstyr, hensyn og treningsdata."));
    api("api/ai/entiteter").then((r) => {
      for (const e of r.entiteter) velg.append(el("option", { value: e.entity_id }, `${e.navn} (${e.entity_id})`));
      velg.value = S.innstillinger.ai_entitet || "";
    }).catch(() => {});
    aiKort.append(el("div", { class: "liste-rad", style: "min-height:0;padding:0" }, el("span", { class: "tekst" }, el("b", {}, "Oppsummering etter hver økt"), el("small", {}, "Automatisk når du fullfører")), bryter(S.innstillinger.ai_auto_oppsummering, (x) => lagreInn({ ai_auto_oppsummering: x }))));
    aiKort.append(el("div", { class: "liste-rad", style: "min-height:0;padding:0" }, el("span", { class: "tekst" }, el("b", {}, "Tips når økta starter"), el("small", {}, "Ellers trykker du på knappen selv")), bryter(S.innstillinger.ai_auto_tips, (x) => lagreInn({ ai_auto_tips: x }))));

    v.append(el("div", { class: "seksjon-tittel" }, "Økt"));
    v.append(el("div", { class: "kort" }, el("div", { class: "liste-rad", style: "min-height:0;padding:0" }, el("span", { class: "tekst" }, el("b", {}, "Lyd når hvilen er over"), el("small", {}, "Telefonen vibrerer uansett (der det støttes)")), bryter(S.innstillinger.hviletimer_lyd, (x) => lagreInn({ hviletimer_lyd: x })))));

    v.append(el("div", { class: "seksjon-tittel" }, "Egne øvelser"));
    const egne = S.ovelser.filter((o) => o.egen);
    v.append(el("div", { class: "kort", style: "padding:4px 16px" },
      egne.length ? el("ul", { class: "liste" }, egne.map((o) => el("li", {}, el("button", { class: "liste-rad", onclick: () => egenOvelseArk(o) },
        el("span", { class: "tekst" }, el("b", {}, o.navn), el("small", {}, `${S.monster[o.monster]} · ${S.typer[o.type]}${o.arkivert ? " · skjult" : ""}`)), ikon("hoyre"))))) : el("p", { class: "forklaring", style: "padding:12px 0 0" }, `Biblioteket har ${S.ovelser.length} øvelser. Mangler noe, kan du legge det til her.`),
      el("button", { class: "legg-til", style: "margin:8px 0 12px", onclick: () => egenOvelseArk(null) }, ikon("pluss"), "Ny øvelse")));

    v.append(el("div", { class: "seksjon-tittel" }, "Data"));
    v.append(el("div", { class: "kort" },
      el("a", { class: "knapp noytral liten", href: "api/eksport.csv", download: "styrkeboka.csv" }, ikon("last-ned"), "Last ned all trening (CSV)"),
      el("p", { class: "forklaring" }, "Alt lagres lokalt i appen. Home Assistant får en sensor per profil (sensor.styrkeboka_<navn>) og hendelsen styrkeboka_hendelse når en økt startes og fullføres.")));

    v.append(el("div", { class: "seksjon-tittel" }, "Om rådene"));
    v.append(el("div", { class: "kort" }, el("p", { class: "forklaring" },
      "Programforslagene følger etablerte anbefalinger: muskelstyrkende trening minst 2 dager i uka (WHO og Helsedirektoratet), 8–15 reps med 1–3 reps i reserve for generell form og muskelvekst (ACSM), og rundt 10+ sett per muskelgruppe i uka for muskelvekst. Progresjonen er «dobbel progresjon»: flere reps til toppen av intervallet, så mer vekt. Ved rehab og skader: skånsomme øvelsesvalg og lettere belastning.")));
  }

  function profilArk(p) {
    const ny = !p;
    const d = p ? { ...p, maal: [...(p.maal || [])] } : { navn: "", farge: S.farger[S.profiler.length % S.farger.length], maal: ["generell"], erfaring: "noe", dager_per_uke: 3, okt_minutter: 60, hensyn: "", utstyrsprofil_id: S.utstyrsprofiler[0]?.id, ha_bruker: S.profiler.some((x) => x.ha_bruker) ? null : (S.bruker || null) };
    const navn = el("input", { value: d.navn, placeholder: "Navn", oninput: (e) => { d.navn = e.target.value; } });
    const farger = el("div", { class: "fargevalg" }, S.farger.map((f) => el("button", { class: `farge-${f} ${d.farge === f ? "valgt" : ""}`, "aria-label": f, onclick: (e) => {
      d.farge = f; for (const b of farger.children) b.classList.toggle("valgt", b === e.currentTarget);
    } })));
    const maal = el("div", { class: "chips" }, Object.entries(S.maal).map(([k, n]) => el("button", { class: `chip ${d.maal.includes(k) ? "valgt" : ""}`, onclick: (e) => {
      d.maal = d.maal.includes(k) ? d.maal.filter((x) => x !== k) : [...d.maal, k];
      e.currentTarget.classList.toggle("valgt", d.maal.includes(k));
    } }, n)));
    const erf = el("div", { class: "segment" }, Object.entries(S.erfaring).map(([k, n]) => el("button", { class: d.erfaring === k ? "valgt" : "", onclick: (e) => {
      d.erfaring = k; for (const b of erf.children) b.classList.toggle("valgt", b === e.currentTarget);
    } }, n)));
    const dager = tallStepper(d.dager_per_uke, 1, 1, 6, (x) => `${x} dager`);
    const minutter = el("div", { class: "chips" }, [30, 45, 60, 75, 90].map((m) => el("button", { class: `chip ${d.okt_minutter === m ? "valgt" : ""}`, onclick: (e) => {
      d.okt_minutter = m; for (const b of minutter.children) b.classList.toggle("valgt", b === e.currentTarget);
    } }, `${m} min`)));
    const stedV = el("select", { onchange: () => { d.utstyrsprofil_id = +stedV.value; } }, S.utstyrsprofiler.map((u) => el("option", { value: u.id }, u.navn)));
    stedV.value = d.utstyrsprofil_id || "";
    const hensyn = el("textarea", { placeholder: "F.eks. «vond venstre skulder – unngå press over hodet» eller «opptrening etter kneoperasjon»", oninput: (e) => { d.hensyn = e.target.value; } }, d.hensyn || "");
    const haRot = el("div");
    const tegnHA = () => {
      haRot.innerHTML = "";
      if (d.ha_bruker) haRot.append(el("div", { class: "liste-rad", style: "min-height:0;padding:0" }, el("span", { class: "tekst" }, el("b", {}, `Koblet til ${d.ha_bruker}`), el("small", {}, "Profilen velges automatisk når denne brukeren åpner appen")),
        el("button", { class: "lenke", onclick: () => { d.ha_bruker = null; tegnHA(); } }, "Fjern")));
      else if (S.bruker) haRot.append(el("button", { class: "chip", onclick: () => { d.ha_bruker = S.bruker; tegnHA(); } }, ikon("person"), `Koble til meg (${S.bruker})`));
      else haRot.append(el("p", { class: "forklaring" }, "Åpne appen fra Home Assistant for å koble profilen til en bruker."));
    };
    tegnHA();
    aapneArk(el("h3", {}, ikon("person"), ny ? "Ny profil" : p.navn),
      el("div", { class: "skjema" },
        felt("Navn", navn), el("div", { class: "felt" }, el("span", {}, "Farge"), farger),
        el("div", { class: "felt" }, el("span", {}, "Home Assistant-bruker"), haRot),
        el("div", { class: "felt" }, el("span", {}, "Mål (velg ett eller flere)"), maal),
        el("div", { class: "felt" }, el("span", {}, "Erfaring med styrketrening"), erf),
        felt("Økter per uke", dager), el("div", { class: "felt" }, el("span", {}, "Tid per økt"), minutter),
        felt("Trener vanligvis", stedV),
        felt("Skader, plager eller hensyn", hensyn, "Brukes av appen og AI-treneren (uten navn) for å velge skånsomme øvelser.")),
      el("div", { class: "ark-knapper" },
        !ny ? el("button", { class: "knapp fare", "aria-label": "Slett profil", onclick: async () => {
          if (!(await bekreft(`Slette profilen ${p.navn}?`, "Profilen skjules. Treningshistorikken beholdes i databasen og i eksporten.", "Slett", true))) return;
          try { await slett(`api/profiler/${p.id}`); await lastStart(); if (pid === p.id) pid = S.profiler[0]?.id ?? null; tegnProfilvelger(); visInnstillinger(); } catch (e) { feil(e); }
        } }, ikon("soppel")) : el("button", { class: "knapp noytral", onclick: lukkArk }, "Avbryt"),
        el("button", { class: "knapp", onclick: async () => {
          if (!d.navn.trim()) { navn.focus(); visToast("Skriv inn et navn"); return; }
          try {
            const body = { ...d, dager_per_uke: dager.verdi() };
            const r = ny ? await post("api/profiler", body) : await patch(`api/profiler/${p.id}`, body);
            lukkArk();
            await lastStart();
            if (ny) { velgProfil(r.profil.id); visProgram(); setTimeout(() => nyttProgramArk(aiPaa()), 300); }
            else { tegnProfilvelger(); if (fane === "innstillinger") visInnstillinger(); else visTrening(); }
          } catch (e) { feil(e); }
        } }, ny ? "Lag profil" : "Lagre")));
  }

  function stedArk(u) {
    const ny = !u;
    const d = u ? { navn: u.navn, utstyr: [...u.utstyr] } : { navn: "", utstyr: ["manualer"] };
    const navn = el("input", { value: d.navn, placeholder: "F.eks. Hjemme, Jobb-gymmen, Hytta", oninput: (e) => { d.navn = e.target.value; } });
    const utstyr = el("div", { class: "chips" }, Object.entries(S.utstyr).map(([k, n]) => el("button", { class: `chip ${d.utstyr.includes(k) ? "valgt" : ""}`, onclick: (e) => {
      d.utstyr = d.utstyr.includes(k) ? d.utstyr.filter((x) => x !== k) : [...d.utstyr, k];
      e.currentTarget.classList.toggle("valgt", d.utstyr.includes(k));
    } }, n)));
    aapneArk(el("h3", {}, ikon("sted"), ny ? "Nytt treningssted" : u.navn),
      el("p", { class: "hint" }, "Øvelser som krever utstyr stedet ikke har, byttes automatisk ut når du trener her."),
      el("div", { class: "skjema" }, felt("Navn", navn), el("div", { class: "felt" }, el("span", {}, "Utstyr"), utstyr)),
      el("div", { class: "ark-knapper" },
        !ny ? el("button", { class: "knapp fare", "aria-label": "Slett sted", onclick: async () => {
          if (!(await bekreft(`Slette ${u.navn}?`, "", "Slett", true))) return;
          try { await slett(`api/utstyrsprofiler/${u.id}`); visInnstillinger(); } catch (e) { feil(e); }
        } }, ikon("soppel")) : el("button", { class: "knapp noytral", onclick: lukkArk }, "Avbryt"),
        el("button", { class: "knapp", onclick: async () => {
          try { if (ny) await post("api/utstyrsprofiler", d); else await patch(`api/utstyrsprofiler/${u.id}`, d); lukkArk(); visInnstillinger(); } catch (e) { feil(e); }
        } }, "Lagre")));
  }

  function egenOvelseArk(o) {
    const ny = !o;
    const d = o ? { navn: o.navn, monster: o.monster, type: o.type, utstyr: [...o.utstyr], muskler: [...o.muskler], tips: (o.tips || []).join("\n"), instruksjon: (o.instruksjon?.steg || []).join("\n"), arkivert: o.arkivert } : { navn: "", monster: "kne", type: "manualer", utstyr: ["manualer"], muskler: [], tips: "", instruksjon: "", arkivert: false };
    const navn = el("input", { value: d.navn, oninput: (e) => { d.navn = e.target.value; } });
    const monster = el("select", { onchange: () => { d.monster = monster.value; } }, Object.entries(S.monster).map(([k, n]) => el("option", { value: k }, n)));
    monster.value = d.monster;
    const typ = el("select", { onchange: () => { d.type = typ.value; } }, Object.entries(S.typer).map(([k, n]) => el("option", { value: k }, n)));
    typ.value = d.type;
    const utstyr = el("div", { class: "chips" }, Object.entries(S.utstyr).map(([k, n]) => el("button", { class: `chip liten ${d.utstyr.includes(k) ? "valgt" : ""}`, onclick: (e) => {
      d.utstyr = d.utstyr.includes(k) ? d.utstyr.filter((x) => x !== k) : [...d.utstyr, k]; e.currentTarget.classList.toggle("valgt", d.utstyr.includes(k));
    } }, n)));
    const muskler = el("div", { class: "chips" }, Object.entries(S.muskler).map(([k, n]) => el("button", { class: `chip liten ${d.muskler.includes(k) ? "valgt" : ""}`, onclick: (e) => {
      d.muskler = d.muskler.includes(k) ? d.muskler.filter((x) => x !== k) : [...d.muskler, k]; e.currentTarget.classList.toggle("valgt", d.muskler.includes(k));
    } }, n)));
    const tips = el("textarea", { placeholder: "Ett kort punkt per linje", oninput: (e) => { d.tips = e.target.value; } }, d.tips);
    const instruksjon = el("textarea", { rows: 5, placeholder: "Ett steg per linje, f.eks.\nStå med føttene i hoftebredde\nSenk deg rolig ned\nPress opp igjen", oninput: (e) => { d.instruksjon = e.target.value; } }, d.instruksjon);
    aapneArk(el("h3", {}, ny ? "Ny øvelse" : o.navn),
      el("div", { class: "skjema" }, felt("Navn", navn), el("div", { class: "felt-rad" }, felt("Bevegelse", monster), felt("Type (styrer vektsteg)", typ)),
        el("div", { class: "felt" }, el("span", {}, "Utstyr som trengs"), utstyr), el("div", { class: "felt" }, el("span", {}, "Muskler (hovedmuskel først)"), muskler), felt("Slik gjør du (ett steg per linje)", instruksjon), felt("Husk (korte teknikkpunkter)", tips),
        !ny ? el("div", { class: "liste-rad", style: "min-height:0;padding:0" }, el("span", { class: "tekst" }, el("b", {}, "Skjul øvelsen"), el("small", {}, "Historikken beholdes")), bryter(d.arkivert, (x) => { d.arkivert = x; })) : null),
      el("div", { class: "ark-knapper" }, el("button", { class: "knapp noytral", onclick: lukkArk }, "Avbryt"),
        el("button", { class: "knapp", onclick: async () => {
          try { if (ny) await post("api/ovelser", d); else await patch(`api/ovelser/${o.id}`, d); lukkArk(); await lastStart(); visInnstillinger(); } catch (e) { feil(e); }
        } }, "Lagre")));
  }

  // ================================================================ oppstart
  (async () => {
    try { await lastStart(); } catch (e) { visToast("Får ikke kontakt med Styrkeboka"); return; }
    visTrening();
  })();
  document.addEventListener("visibilitychange", () => {
    if (document.hidden) return;
    if (fane === "trening" && !$("v-trening").hidden && !$("ark-rot").children.length) visTrening();
    if (hvile) tegnHvile();
  });
})();
