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
  const VISNINGER = ["trening", "okt", "program", "historikk", "kropp", "detalj", "innstillinger"];
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
    if (f === "kropp") visKropp();
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
    else if (fane === "kropp") visKropp();
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

    if (ov.spill && !ov.aktiv) v.append(spillKort(ov.spill));
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
        profil()?.garmin_eksport?.styrke ? el("p", { class: "forklaring", style: "font-size:13px;text-align:center" }, "⌚ Økta ligger klar i Garmin-kalenderen – start den på klokka og logg settene her.") : null,
        el("button", { class: "knapp", onclick: () => startOkt(n.id) }, ikon("play"), "Start økten")));
      const andre = ov.program.dager.filter((d) => d.id !== n.id);
      v.append(el("div", { class: "chips rull" },
        andre.map((d) => el("button", { class: "chip liten", onclick: () => startOkt(d.id) }, d.navn)),
        el("button", { class: "chip liten", onclick: () => startOkt(null) }, ikon("pluss"), "Fri økt")));
    }

    if (!ov.aktiv) v.append(intervallInngang());
    if (ov.loping) v.append(lopeKort(ov.loping));
    if (ov.mangler_startvekt && !ov.aktiv) {
      v.append(el("div", { class: "ai-kort" },
        el("h3", {}, ikon("manual"), "Hvor tungt skal du løfte?"),
        el("p", {}, `${ov.mangler_startvekt} øvelser i programmet mangler startvekt. Svar på et par spørsmål, så ${aiPaa() ? "foreslår treneren" : "regner appen ut"} vekt på alle.`),
        el("button", { class: "knapp ai", style: "flex:none", onclick: startvekterArk }, ikon("gnist"), "Finn startvekter")));
    }
    if (ov.dagsform && !ov.aktiv) v.append(dagsformKort(ov.dagsform));
    if (ov.spill?.nye_merker?.length || ov.spill?.nytt_niva) feir(ov.spill);
    const knapper = el("div", { class: "knapperad" });
    if (aiPaa()) knapper.append(el("button", { class: "knapp ai-lys", onclick: () => sporTreneren() }, ikon("snakk"), "Spør treneren"));
    if (ov.sist) knapper.append(el("button", { class: "knapp noytral", onclick: () => visOktDetalj(ov.sist.id, "trening") }, ikon("klokke"), "Forrige økt"));
    if (knapper.children.length) v.append(knapper);
    if (ov.ukeplan) v.append(ukeplanKort(ov.ukeplan));
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

    const go = okt.generell_oppvarming;
    if (go && !hent(`oppvarmet-${okt.id}`, false)) {
      const aapen = !okt.nokkeltall.sett;
      v.append(el("details", { class: "oppvarm-kort", ...(aapen ? { open: true } : {}) },
        el("summary", {}, ikon("flamme"), el("span", {}, `Oppvarming · ca. ${go.minutter} min`)),
        el("p", {}, go.puls),
        el("ul", {}, go.bevegelser.map((b) => el("li", {}, b))),
        el("p", { class: "forklaring" }, go.tekst),
        el("button", { class: "knapp sekundaer liten", onclick: () => { lagre(`oppvarmet-${okt.id}`, true); tegnOkt(); } }, ikon("sjekk"), "Ferdig oppvarmet")));
    }
    const df = ov?.dagsform;
    if (df && df.niva !== "god" && !okt.nokkeltall.sett && !okt.lett && !hent(`lettere-${okt.id}`, false)) {
      v.append(el("div", { class: `info-boks ${df.niva === "lav" ? "obs" : ""}` }, ikon("hjerte"),
        el("span", {}, `${df.tittel}: ${df.rad} `, el("button", { class: "lenke", onclick: async () => {
          try { okt = (await post(`api/okter/${okt.id}/lettere`)).okt; lagre(`lettere-${okt.id}`, true); visToast("Økta er gjort lettere"); tegnOkt(); } catch (e) { feil(e); }
        } }, "Gjør økta lettere"))));
    }
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

  // ================================================================ INTERVALLER: HIIT, TABATA, SIRKEL, EMOM, AMRAP
  const TIDSSTYRT = new Set(["hiit", "tabata", "sirkel"]);
  const FORMATFARGE = { hiit: "oransje", tabata: "rosa", sirkel: "blaa", emom: "lilla", amrap: "gronn" };
  let intervallData = null;
  let intervallSted = null;

  function totalSek(o) {
    const n = o.ovelser.length;
    if (TIDSSTYRT.has(o.format)) return o.runder * n * o.arbeid + o.runder * (n - 1) * o.hvile + (o.runder - 1) * o.rundehvile;
    return (o.minutter || 0) * 60;
  }
  const minTekst = (s) => s >= 60 ? `${Math.round(s / 60)} min` : `${s} s`;
  const formatMerke = (f) => el("span", { class: `format-merke farge-${FORMATFARGE[f]}` }, intervallData?.formater?.[f]?.navn || f.toUpperCase());

  function intervallInngang() {
    return el("button", { class: "kort intervall-inngang", onclick: () => intervallMeny() },
      el("span", { class: "ii-ikon" }, ikon("flamme")),
      el("span", { class: "tekst" }, el("b", {}, "Intervalløkt"), el("small", {}, "HIIT · Tabata · Sirkel · EMOM · AMRAP – med klokke")),
      ikon("hoyre"));
  }

  async function intervallMeny() {
    intervallSted = intervallSted || sted();
    const innhold = el("div", { class: "intervall-meny" }, aiLaster("Henter økter …"));
    aapneArk(el("h3", {}, ikon("flamme"), " Intervalløkt"), innhold);
    try {
      intervallData = await api(`api/profiler/${pid}/intervaller?sted=${intervallSted}`);
    } catch (e) { innhold.innerHTML = ""; innhold.append(el("p", { class: "hint" }, e.message)); return; }
    innhold.innerHTML = "";
    const d = intervallData;
    if (S.utstyrsprofiler.length > 1) {
      innhold.append(el("div", { class: "segment" }, S.utstyrsprofiler.map((u) =>
        el("button", { class: u.id === intervallSted ? "valgt" : "", onclick: () => { intervallSted = u.id; intervallMeny(); } }, ikon("sted"), u.navn))));
    }
    innhold.append(el("div", { class: "seksjon-tittel liten" }, "Lag din egen"));
    innhold.append(el("div", { class: "format-grid" }, Object.entries(d.formater).map(([k, f]) =>
      el("button", { class: `format-kort farge-${FORMATFARGE[k]}`, onclick: () => nyIntervall(k) }, el("b", {}, f.navn), el("small", {}, f.kort)))));
    if (aiPaa()) innhold.append(el("button", { class: "knapp ai-lys", style: "width:100%;margin-top:10px", onclick: () => intervallAiArk() }, ikon("gnist"), "La treneren lage en økt"));
    innhold.append(el("div", { class: "seksjon-tittel liten" }, "Ferdige økter"));
    innhold.append(el("ul", { class: "mal-liste" }, d.maler.map((m) => el("li", {},
      el("button", { onclick: () => intervallBygger({ navn: m.navn, oppsett: m.oppsett }) },
        formatMerke(m.format),
        el("span", { class: "tekst" }, el("b", {}, m.navn), el("small", {}, `${minTekst(m.sekunder)} · ${m.beskrivelse}`)),
        ikon("hoyre"))))));
    if (d.historikk.length) {
      innhold.append(el("div", { class: "seksjon-tittel liten" }, "Sist gjort"));
      innhold.append(el("ul", { class: "mal-liste" }, d.historikk.slice(0, 6).map((h) => el("li", {},
        el("button", { onclick: () => intervallBygger({ navn: h.navn, oppsett: h.oppsett }) },
          formatMerke(h.format),
          el("span", { class: "tekst" }, el("b", {}, h.navn), el("small", {}, `${dato(h.startet)} · ${mmss(h.varighet_s)}${h.runder != null ? ` · ${tall(h.runder)} runder` : ""}${h.fullfort ? "" : " · avbrutt"}`)),
          el("span", { class: "gjenta" }, ikon("angre")))))));
    }
  }

  async function nyIntervall(format, fokus = "helkropp") {
    try {
      const r = await post(`api/profiler/${pid}/intervaller/forslag`, { format, fokus, sted: intervallSted });
      intervallBygger({ navn: intervallData.formater[format].navn, oppsett: r.oppsett, fokus });
    } catch (e) { feil(e); }
  }

  function intervallAiArk() {
    let format = "hiit", fokus = "helkropp", minutter = 20;
    const onske = el("textarea", { rows: 2, placeholder: "F.eks. «skånsomt for knærne», «mye sete», «kort og hard»" });
    const formatValg = el("div", { class: "chips" });
    const fokusValg = el("div", { class: "chips" });
    const tegnValg = () => {
      formatValg.innerHTML = ""; fokusValg.innerHTML = "";
      for (const [k, f] of Object.entries(intervallData.formater)) formatValg.append(el("button", { class: `chip liten ${k === format ? "valgt" : ""}`, onclick: () => { format = k; tegnValg(); } }, f.navn));
      for (const [k, n] of Object.entries(intervallData.fokus)) fokusValg.append(el("button", { class: `chip liten ${k === fokus ? "valgt" : ""}`, onclick: () => { fokus = k; tegnValg(); } }, n));
    };
    tegnValg();
    const varighet = stepperCb(minutter, 2, 4, 60, (v) => { minutter = v; }, (v) => `${v} min`);
    const knapp = el("button", { class: "knapp ai", onclick: async () => {
      knapp.disabled = true; knapp.textContent = "Treneren lager økta …";
      try {
        const r = await post(`api/profiler/${pid}/intervaller/ai`, { format, fokus, minutter, onske: onske.value, sted: intervallSted });
        intervallBygger({ navn: r.navn, oppsett: r.oppsett, begrunnelse: r.begrunnelse, tips: r.tips, fokus });
      } catch (e) { feil(e); knapp.disabled = false; knapp.textContent = "Lag økta"; }
    } }, ikon("gnist"), "Lag økta");
    aapneArk(el("h3", {}, ikon("gnist"), " Treneren lager en intervalløkt"),
      el("p", { class: "hint" }, "Treneren tar hensyn til dagsformen, hva du har trent sist og utstyret der du er."),
      felt("Format", formatValg), felt("Fokus", fokusValg), felt("Lengde", varighet), felt("Ønsker (valgfritt)", onske),
      el("div", { class: "ark-knapper" }, el("button", { class: "knapp noytral", onclick: () => intervallMeny() }, "Tilbake"), knapp));
  }

  function stepperCb(start, steg, min, maks, ved_endring, format = String) {
    let verdi = start;
    const vis_ = el("span", { class: "verdi" }, format(verdi));
    const sett = (v) => { verdi = Math.max(min, Math.min(maks, v)); vis_.textContent = format(verdi); ved_endring(verdi); };
    return el("div", { class: "stepper" }, el("button", { type: "button", "aria-label": "Mindre", onclick: () => sett(verdi - steg) }, "−"), vis_,
      el("button", { type: "button", "aria-label": "Mer", onclick: () => sett(verdi + steg) }, "+"));
  }

  function intervallBygger({ navn, oppsett, begrunnelse = "", tips = [], fokus = "helkropp" }) {
    const o = JSON.parse(JSON.stringify(oppsett));
    const f = intervallData.formater[o.format];
    const navnInput = el("input", { type: "text", value: navn, maxlength: 60 });
    const total = el("b", {});
    const liste = el("ul", { class: "iv-ovelser" });
    const oppdaterTotal = () => { total.textContent = mmss(totalSek(o)); };
    const tegnListe = () => {
      liste.innerHTML = "";
      o.ovelser.forEach((x, i) => {
        const reps = ["emom", "amrap"].includes(o.format)
          ? el("input", { type: "text", inputmode: "numeric", class: "reps", value: x.reps ?? "", placeholder: "reps", "aria-label": `Repetisjoner ${x.navn}`,
            oninput: (e) => { x.reps = parseInt(e.target.value, 10) || null; } })
          : null;
        liste.append(el("li", {},
          el("span", { class: "nr" }, o.format === "emom" ? `${i + 1}′` : i + 1),
          el("button", { class: "iv-navn", onclick: () => ovelseInfoArk(x.nokkel, null, { tilbake: () => intervallBygger({ navn: navnInput.value, oppsett: o, begrunnelse, tips, fokus }) }) },
            el("b", {}, x.navn), el("small", {}, ovelse(x.nokkel).tips?.[0] || "")),
          reps,
          el("button", { class: "ikonknapp", "aria-label": `Flytt ${x.navn} opp`, disabled: i === 0, onclick: () => { [o.ovelser[i - 1], o.ovelser[i]] = [o.ovelser[i], o.ovelser[i - 1]]; tegnListe(); } }, ikon("opp")),
          el("button", { class: "ikonknapp", "aria-label": `Fjern ${x.navn}`, onclick: () => { o.ovelser.splice(i, 1); tegnListe(); oppdaterTotal(); } }, ikon("kryss"))));
      });
    };
    const leggTil = () => aapneOvelsevelger({ tittel: "Legg til øvelse", utstyrsprofil_id: intervallSted, ved_valg: (x) => {
      o.ovelser.push({ nokkel: x.nokkel, navn: x.navn, reps: ["emom", "amrap"].includes(o.format) ? 10 : null });
      intervallBygger({ navn: navnInput.value, oppsett: o, begrunnelse, tips, fokus });
    } });
    const nyeOvelser = async () => {
      try {
        const r = await post(`api/profiler/${pid}/intervaller/forslag`, { format: o.format, fokus, antall: o.ovelser.length || null, sted: intervallSted });
        o.ovelser = r.oppsett.ovelser; tegnListe(); oppdaterTotal();
      } catch (e) { feil(e); }
    };
    const param = [];
    if (TIDSSTYRT.has(o.format)) {
      param.push(el("div", { class: "param-grid" },
        felt("Jobb", stepperCb(o.arbeid, 5, 5, 300, (v) => { o.arbeid = v; oppdaterTotal(); }, (v) => `${v} s`)),
        felt("Pause", stepperCb(o.hvile, 5, 0, 300, (v) => { o.hvile = v; oppdaterTotal(); }, (v) => `${v} s`)),
        felt("Runder", stepperCb(o.runder, 1, 1, 20, (v) => { o.runder = v; oppdaterTotal(); })),
        felt("Pause mellom runder", stepperCb(o.rundehvile, 15, 0, 600, (v) => { o.rundehvile = v; oppdaterTotal(); }, (v) => `${v} s`))));
    } else {
      param.push(felt("Lengde", stepperCb(o.minutter, 1, 1, 90, (v) => { o.minutter = v; oppdaterTotal(); }, (v) => `${v} min`)));
    }
    const fokusValg = el("div", { class: "chips rull" }, Object.entries(intervallData.fokus).map(([k, n]) =>
      el("button", { class: `chip liten ${k === fokus ? "valgt" : ""}`, onclick: () => { fokus = k; for (const b of fokusValg.children) b.classList.toggle("valgt", b.textContent === n); nyeOvelser(); } }, n)));
    tegnListe(); oppdaterTotal();
    aapneArk(
      el("div", { class: "iv-hode" }, formatMerke(o.format), el("span", { class: "iv-total" }, ikon("klokke"), total)),
      felt("Navn", navnInput),
      el("p", { class: "hint" }, f.beskrivelse),
      begrunnelse ? el("div", { class: "ai-kort" }, el("p", {}, begrunnelse), tips.length ? el("ul", {}, tips.map((t) => el("li", {}, t))) : null) : null,
      ...param,
      el("div", { class: "seksjon-tittel liten" }, o.format === "emom" ? "Øvelser – én per minutt, på rundgang" : o.format === "amrap" ? "Øvelser i hver runde" : "Øvelser"),
      liste,
      el("div", { class: "chips" },
        el("button", { class: "chip liten", onclick: leggTil }, ikon("pluss"), "Legg til"),
        el("button", { class: "chip liten", onclick: nyeOvelser }, ikon("bytt"), "Nye øvelser")),
      fokusValg,
      el("div", { class: "ark-knapper" },
        el("button", { class: "knapp noytral", onclick: () => intervallMeny() }, "Tilbake"),
        el("button", { class: "knapp", onclick: () => {
          if (!o.ovelser.length) return feil(new Error("Legg til minst én øvelse"));
          lukkArk(); startIntervall(navnInput.value.trim() || f.navn, o);
        } }, ikon("play"), "Start")));
  }

  // ---------------------------------------------------------------- klokka
  let iv = null;
  function lagSegmenter(o) {
    const seg = [{ type: "klar", sek: 10, ov: 0, runde: 1 }];
    const n = o.ovelser.length;
    if (TIDSSTYRT.has(o.format)) {
      for (let r = 1; r <= o.runder; r++) {
        for (let i = 0; i < n; i++) {
          seg.push({ type: "jobb", sek: o.arbeid, ov: i, runde: r });
          if (i < n - 1 && o.hvile > 0) seg.push({ type: "pause", sek: o.hvile, ov: i + 1, runde: r });
        }
        if (r < o.runder && o.rundehvile > 0) seg.push({ type: "rundepause", sek: o.rundehvile, ov: 0, runde: r + 1 });
        else if (r < o.runder && o.hvile > 0) seg.push({ type: "pause", sek: o.hvile, ov: 0, runde: r + 1 });
      }
    } else if (o.format === "emom") {
      for (let m = 0; m < o.minutter; m++) seg.push({ type: "emom", sek: 60, ov: m % n, runde: m + 1 });
    } else {
      seg.push({ type: "amrap", sek: o.minutter * 60, ov: 0, runde: 1 });
    }
    return seg;
  }

  function tone(frekvens, start = 0, lengde = 0.15, styrke = 0.3) {
    if (!S.innstillinger.hviletimer_lyd || !iv?.lyd) return;
    try {
      lydKontekst = lydKontekst || new (window.AudioContext || window.webkitAudioContext)();
      const t = lydKontekst.currentTime + start;
      const osc = lydKontekst.createOscillator(), g = lydKontekst.createGain();
      osc.frequency.value = frekvens; osc.connect(g); g.connect(lydKontekst.destination);
      g.gain.setValueAtTime(0.0001, t); g.gain.exponentialRampToValueAtTime(styrke, t + 0.02); g.gain.exponentialRampToValueAtTime(0.0001, t + lengde);
      osc.start(t); osc.stop(t + lengde + 0.05);
    } catch (_) { /* */ }
  }
  function si(tekst) {
    if (!iv?.lyd || !iv.tale || !("speechSynthesis" in window)) return;
    try {
      speechSynthesis.cancel();
      const u = new SpeechSynthesisUtterance(tekst);
      u.lang = "nb-NO"; u.rate = 1.05;
      const stemme = speechSynthesis.getVoices().find((v) => /^(nb|no|nn)/i.test(v.lang));
      if (stemme) u.voice = stemme;
      speechSynthesis.speak(u);
    } catch (_) { /* */ }
  }

  async function holdSkjermPaa() {
    try { if ("wakeLock" in navigator) iv.vaaken = await navigator.wakeLock.request("screen"); } catch (_) { /* */ }
  }
  document.addEventListener("visibilitychange", () => { if (iv && !iv.ferdig && document.visibilityState === "visible") holdSkjermPaa(); });

  function startIntervall(navn, o) {
    if (S.innstillinger.hviletimer_lyd && !lydKontekst) { try { lydKontekst = new (window.AudioContext || window.webkitAudioContext)(); } catch (_) { /* */ } }
    stoppHvile();
    const seg = lagSegmenter(o);
    iv = { navn, o, seg, i: 0, segStart: Date.now(), pauset: null, startet: new Date().toISOString(), sistSek: null,
      lyd: hent("iv-lyd", true), tale: hent("iv-tale", true), amrapOv: 0, amrapRunder: 0, ferdig: false, jobbet: 0 };
    holdSkjermPaa();
    byggKlokke();
    nyttSegment();
    iv.timer = setInterval(tikk, 200);
  }

  const RING_R = 118, RING_O = 2 * Math.PI * RING_R;
  function byggKlokke() {
    const rot = $("intervall-rot");
    rot.innerHTML = "";
    const e = {};
    e.ring = svgEl("circle", { cx: 130, cy: 130, r: RING_R, class: "iv-ring-bue", "stroke-dasharray": `${RING_O} ${RING_O}`, transform: "rotate(-90 130 130)" });
    e.tid = el("div", { class: "iv-tid" });
    e.fase = el("div", { class: "iv-fase" });
    e.ovNavn = el("div", { class: "iv-ovnavn" });
    e.ovReps = el("div", { class: "iv-reps" });
    e.neste = el("div", { class: "iv-neste" });
    e.info = el("div", { class: "iv-info" });
    e.totalTid = el("span", {});
    e.prog = el("div", { class: "iv-prog" }, el("div", {}));
    e.liste = el("ol", { class: "iv-liste" });
    e.pause = el("button", { class: "iv-kontroll stor", "aria-label": "Pause", onclick: () => pauseIntervall() });
    e.lydKnapp = el("button", { class: "iv-topp-knapp", "aria-label": "Lyd av/på", onclick: () => { iv.lyd = !iv.lyd; lagre("iv-lyd", iv.lyd); tegnLydKnapp(); } });
    e.taleKnapp = el("button", { class: "iv-topp-knapp tekst", "aria-label": "Opplesning av/på", onclick: () => { iv.tale = !iv.tale; lagre("iv-tale", iv.tale); tegnLydKnapp(); } });
    const amrap = iv.o.format === "amrap";
    e.runder = amrap ? el("div", { class: "iv-runder" }) : null;
    iv.e = e;
    const kontroller = amrap
      ? el("div", { class: "iv-kontroller" },
        el("button", { class: "iv-kontroll", "aria-label": "Angre", onclick: () => amrapSteg(-1) }, ikon("angre")),
        e.pause,
        el("button", { class: "iv-kontroll bred", onclick: () => amrapSteg(1) }, "Neste øvelse", ikon("hoyre")))
      : el("div", { class: "iv-kontroller" },
        el("button", { class: "iv-kontroll", "aria-label": "Forrige", onclick: () => hoppTil(iv.i - 1) }, ikon("venstre")),
        e.pause,
        el("button", { class: "iv-kontroll", "aria-label": "Hopp over", onclick: () => hoppTil(iv.i + 1) }, ikon("hoyre")));
    const ring = svgEl("svg", { viewBox: "0 0 260 260", class: "iv-ring" });
    ring.append(svgEl("circle", { cx: 130, cy: 130, r: RING_R, class: "iv-ring-spor" }), e.ring);
    rot.append(el("div", { class: "iv-skjerm", role: "dialog", "aria-modal": "true", "aria-label": `Intervalløkt: ${iv.navn}` },
      el("div", { class: "iv-topp" },
        el("button", { class: "iv-topp-knapp", "aria-label": "Avslutt", onclick: () => avsluttIntervall(false) }, ikon("kryss")),
        el("div", { class: "iv-tittel" }, el("b", {}, iv.navn), el("small", {}, e.totalTid)),
        e.taleKnapp, e.lydKnapp),
      e.prog,
      el("div", { class: "iv-midt" },
        el("div", { class: "iv-ring-boks" }, ring, el("div", { class: "iv-ring-tekst" }, e.fase, e.tid, e.runder)),
        el("div", { class: "iv-ovelse" }, e.ovNavn, e.ovReps, e.neste),
        e.info),
      kontroller,
      el("div", { class: "iv-oversikt" }, el("div", { class: "iv-oversikt-tittel" }, amrap ? "Hver runde" : iv.o.format === "emom" ? "Minutt for minutt" : "Øvelser"), e.liste)));
    document.body.classList.add("har-intervall");
    tegnLydKnapp();
    tegnPause();
  }
  function tegnLydKnapp() {
    const e = iv.e;
    e.lydKnapp.innerHTML = ""; e.lydKnapp.append(el("span", { class: "iv-lyd-ikon" }, iv.lyd ? "🔊" : "🔇"));
    e.taleKnapp.textContent = iv.tale ? "Tale på" : "Tale av";
    e.taleKnapp.classList.toggle("av", !iv.tale || !iv.lyd);
  }

  function tegnListe() {
    const { o, e } = iv;
    const s = iv.seg[iv.i];
    e.liste.innerHTML = "";
    const n = o.ovelser.length;
    o.ovelser.forEach((x, i) => {
      let tilstand = "";
      if (o.format === "amrap") tilstand = i < iv.amrapOv ? "gjort" : i === iv.amrapOv ? "naa" : "";
      else if (s.type === "klar") tilstand = i === 0 ? "neste" : "";
      else if (s.type === "jobb" || s.type === "emom") tilstand = i < s.ov ? "gjort" : i === s.ov ? "naa" : "";
      else tilstand = i < s.ov ? "gjort" : i === s.ov ? "neste" : "";
      if (s.type === "rundepause") tilstand = i === 0 ? "neste" : "";
      if (o.format === "emom" && s.type === "emom") tilstand = i === s.ov ? "naa" : "";
      e.liste.append(el("li", { class: tilstand, onclick: o.format === "amrap" ? () => { iv.amrapOv = i; oppdaterAmrap(); } : null },
        el("span", { class: "iv-l-nr" }, tilstand === "gjort" ? "✓" : o.format === "emom" ? `${i + 1}′` : i + 1),
        el("span", { class: "iv-l-navn" }, x.navn),
        x.reps ? el("span", { class: "iv-l-reps" }, `× ${x.reps}`) : TIDSSTYRT.has(o.format) ? el("span", { class: "iv-l-reps" }, `${o.arbeid} s`) : null));
    });
    if (TIDSSTYRT.has(o.format) && n) {
      const runde = s.runde;
      e.info.textContent = `Runde ${Math.min(runde, o.runder)} av ${o.runder}` + (s.type === "jobb" ? ` · øvelse ${s.ov + 1} av ${n}` : "");
    } else if (o.format === "emom") {
      e.info.textContent = s.type === "emom" ? `Minutt ${s.runde} av ${o.minutter}` : `${o.minutter} minutter · ${n} øvelser på rundgang`;
    } else {
      e.info.textContent = "Trykk «Neste øvelse» når du er ferdig – eller på en øvelse i lista.";
    }
  }

  const FASETEKST = { klar: "Gjør deg klar", jobb: "Jobb!", pause: "Pause", rundepause: "Rundepause", emom: "Gjør reps", amrap: "AMRAP" };
  function nyttSegment() {
    const { o, e } = iv;
    const s = iv.seg[iv.i];
    const ov = o.ovelser[s.ov];
    document.querySelector(".iv-skjerm").dataset.fase = s.type;
    e.fase.textContent = FASETEKST[s.type];
    if (o.format === "amrap" && s.type === "amrap") {
      oppdaterAmrap();
    } else {
      e.ovNavn.textContent = ov.navn;
      e.ovReps.textContent = s.type === "emom" ? `${ov.reps || "?"} repetisjoner – hvil resten av minuttet` : s.type === "jobb" ? (ovelse(ov.nokkel).tips?.[0] || "") : "";
      const nesteSeg = iv.seg.slice(iv.i + 1).find((x) => x.type === "jobb" || x.type === "emom");
      e.neste.textContent = s.type === "jobb" || s.type === "emom"
        ? (nesteSeg ? `Neste: ${o.ovelser[nesteSeg.ov].navn}` : "Siste drag!")
        : s.type === "klar" ? `Første: ${ov.navn}` : `Neste: ${ov.navn}`;
      e.ovNavn.classList.toggle("dempet", !["jobb", "emom"].includes(s.type));
    }
    tegnListe();
    // lyd og tale
    if (s.type === "jobb" || s.type === "emom") { tone(988, 0, 0.35, 0.35); si(ov.navn + (s.type === "emom" && ov.reps ? `, ${ov.reps}` : "")); }
    else if (s.type === "amrap") { tone(988, 0, 0.5, 0.35); si(`Start. ${ov.navn}`); }
    else if (s.type === "pause" || s.type === "rundepause") { tone(523, 0, 0.3); si(`${s.type === "rundepause" ? "Rundepause" : "Pause"}. Neste: ${ov.navn}`); }
    else if (s.type === "klar") si(`Gjør deg klar. ${iv.navn}. Første øvelse: ${ov.navn}`);
    vibrer(s.type === "jobb" || s.type === "emom" || s.type === "amrap" ? [200] : [80]);
  }

  function oppdaterAmrap() {
    const { o, e } = iv;
    const ov = o.ovelser[iv.amrapOv];
    e.ovNavn.textContent = ov.navn;
    e.ovNavn.classList.remove("dempet");
    e.ovReps.textContent = ov.reps ? `${ov.reps} repetisjoner` : "";
    e.neste.textContent = `Neste: ${o.ovelser[(iv.amrapOv + 1) % o.ovelser.length].navn}`;
    if (e.runder) e.runder.textContent = `${iv.amrapRunder} ${iv.amrapRunder === 1 ? "runde" : "runder"}`;
    tegnListe();
  }
  function amrapSteg(retning) {
    if (iv.seg[iv.i].type !== "amrap") return;
    const n = iv.o.ovelser.length;
    let pos = iv.amrapRunder * n + iv.amrapOv + retning;
    pos = Math.max(0, pos);
    const nyRunde = Math.floor(pos / n) > iv.amrapRunder;
    iv.amrapRunder = Math.floor(pos / n); iv.amrapOv = pos % n;
    if (nyRunde) { tone(1318, 0, 0.12); tone(1568, 0.12, 0.2); vibrer([60, 40, 60]); si(`Runde ${iv.amrapRunder} ferdig`); }
    else if (retning > 0) si(iv.o.ovelser[iv.amrapOv].navn);
    oppdaterAmrap();
  }

  function tikk() {
    if (!iv || iv.pauset) return;
    const s = iv.seg[iv.i];
    const brukt = (Date.now() - iv.segStart) / 1000;
    const igjen = s.sek - brukt;
    if (igjen <= 0) {
      if (s.type === "jobb" || s.type === "emom" || s.type === "amrap") iv.jobbet += s.sek;
      if (iv.i + 1 >= iv.seg.length) return avsluttIntervall(true);
      iv.segStart += s.sek * 1000;
      iv.i += 1;
      nyttSegment();
      return tikk();
    }
    const hel = Math.ceil(igjen);
    if (hel !== iv.sistSek) {
      iv.sistSek = hel;
      if (hel <= 3 && s.sek > 5) { tone(784, 0, 0.12, 0.3); }
      if (s.type === "amrap" && [60, 30].includes(hel) && s.sek > hel) si(hel === 60 ? "Ett minutt igjen" : "Tretti sekunder");
      if (s.type === "jobb" && hel === Math.floor(s.sek / 2) && s.sek >= 30) tone(660, 0, 0.08, 0.15);
    }
    const e = iv.e;
    e.tid.textContent = hel >= 60 ? mmss(hel) : String(hel);
    e.ring.setAttribute("stroke-dashoffset", RING_O * (1 - igjen / s.sek));
    const totalt = iv.seg.reduce((a, x) => a + x.sek, 0);
    const forbi = iv.seg.slice(0, iv.i).reduce((a, x) => a + x.sek, 0) + brukt;
    e.prog.firstChild.style.width = `${Math.min(100, (forbi / totalt) * 100)}%`;
    e.totalTid.textContent = `${mmss(Math.max(0, totalt - forbi))} igjen`;
  }

  function pauseIntervall() {
    if (!iv) return;
    if (iv.pauset) { iv.segStart += Date.now() - iv.pauset; iv.pauset = null; }
    else iv.pauset = Date.now();
    tegnPause();
  }
  function tegnPause() {
    const e = iv.e;
    e.pause.innerHTML = "";
    e.pause.append(iv.pauset ? ikon("play") : el("span", { class: "pause-ikon" }, el("i"), el("i")));
    e.pause.setAttribute("aria-label", iv.pauset ? "Fortsett" : "Pause");
    document.querySelector(".iv-skjerm")?.classList.toggle("pauset", !!iv.pauset);
  }
  function hoppTil(i) {
    if (!iv || i < 0) return;
    if (i >= iv.seg.length) return avsluttIntervall(true);
    const s = iv.seg[iv.i];
    if (s.type === "jobb" || s.type === "emom") iv.jobbet += Math.min(s.sek, (Date.now() - iv.segStart) / 1000);
    iv.i = i; iv.segStart = Date.now(); iv.sistSek = null;
    if (iv.pauset) iv.pauset = Date.now();
    nyttSegment(); tikk();
  }

  function stoppKlokke() {
    clearInterval(iv?.timer);
    try { iv?.vaaken?.release(); } catch (_) { /* */ }
    try { speechSynthesis.cancel(); } catch (_) { /* */ }
    $("intervall-rot").innerHTML = "";
    document.body.classList.remove("har-intervall");
  }

  async function avsluttIntervall(ferdig) {
    if (!iv) return;
    if (!ferdig) {
      const varPauset = !!iv.pauset;
      if (!varPauset) pauseIntervall();
      const valg = await new Promise((ok) => {
        let svar = "fortsett";
        aapneArk(el("h3", {}, "Avslutte økta?"),
          el("p", { class: "hint" }, "Du kan lagre det du har gjort så langt, eller forkaste økta."),
          el("div", { class: "ark-knapper loddrett" },
            el("button", { class: "knapp", onclick: () => { svar = "lagre"; lukkArk(); } }, "Lagre det jeg har gjort"),
            el("button", { class: "knapp noytral", onclick: () => { svar = "fortsett"; lukkArk(); } }, "Fortsett økta"),
            el("button", { class: "knapp fare", onclick: () => { svar = "forkast"; lukkArk(); } }, "Forkast")));
        const gammel = arkLukk; arkLukk = () => { gammel(); ok(svar); };
      });
      if (valg === "fortsett") { if (!varPauset) pauseIntervall(); return; }
      if (valg === "forkast") { stoppKlokke(); iv = null; return; }
    }
    const s = iv.seg[iv.i];
    const varighet = Math.round((iv.pauset || Date.now()) - new Date(iv.startet).getTime()) / 1000 - 10;
    const n = iv.o.ovelser.length;
    const runder = iv.o.format === "amrap" ? +(iv.amrapRunder + iv.amrapOv / n).toFixed(2)
      : TIDSSTYRT.has(iv.o.format) ? (ferdig ? iv.o.runder : Math.max(0, s.runde - 1 + (s.type === "jobb" ? s.ov / n : 0))) : null;
    iv.ferdig = true;
    const resultat = { navn: iv.navn, oppsett: iv.o, startet: iv.startet, varighet_s: Math.max(30, varighet), runder, fullfort: ferdig };
    stoppKlokke();
    if (ferdig) { tone(1046, 0, 0.15); tone(1318, 0.15, 0.15); tone(1568, 0.3, 0.4); vibrer([100, 60, 100, 60, 300]); si("Bra jobba! Økta er ferdig."); }
    iv = null;
    intervallFerdigArk(resultat);
  }

  function intervallFerdigArk(r) {
    let opplevd = null;
    const notat = el("textarea", { rows: 2, placeholder: "Notat (valgfritt)" });
    const tyngde = el("div", { class: "chips" });
    const tegnT = () => { tyngde.innerHTML = ""; ["Lett", "Grei", "Passe", "Tung", "Knallhard"].forEach((t, i) => tyngde.append(el("button", { class: `chip liten ${opplevd === i + 1 ? "valgt" : ""}`, onclick: () => { opplevd = i + 1; tegnT(); } }, t))); };
    tegnT();
    const lagreKnapp = el("button", { class: "knapp", onclick: async () => {
      lagreKnapp.disabled = true;
      try {
        const svar = await post(`api/profiler/${pid}/intervaller`, { ...r, opplevd, notat: notat.value });
        lukkArk();
        const fb = svar.forrige_beste;
        if (r.oppsett.format === "amrap" && fb && r.runder > fb.runder) visToast(`🏆 Ny rekord på ${r.navn}: ${tall(r.runder)} runder (forrige beste ${tall(fb.runder)})`, [], 7000);
        else visToast("Økta er lagret – den teller i aktivitetsringen 💪");
        visTrening();
      } catch (e) { feil(e); lagreKnapp.disabled = false; }
    } }, ikon("sjekk"), "Lagre");
    aapneArk(
      el("div", { class: "feiring" }, el("div", { class: "feiring-emoji" }, r.fullfort ? "🔥" : "👍"),
        el("h3", {}, r.fullfort ? "Bra jobba!" : "Godt forsøk!"),
        el("p", {}, `${r.navn} · ${mmss(r.varighet_s)}` + (r.runder != null ? ` · ${tall(r.runder)} runder` : ""))),
      felt("Hvordan kjentes det?", tyngde), felt("Notat", notat),
      el("div", { class: "ark-knapper" }, el("button", { class: "knapp noytral", onclick: () => lukkArk() }, "Forkast"), lagreKnapp));
  }

  // ================================================================ SPILL: RINGER, UKE-KJEDE, NIVÅ OG MERKER
  const RINGFARGE = { styrke: "var(--oransje)", aktivitet: "var(--gronn)", sovn: "var(--blaa)", sett: "var(--gul)" };
  const ringVerdi = (r) => r.nokkel === "sovn" ? `${tall(r.verdi)} av ${tall(r.maal)} t` : `${tusen(r.verdi)} av ${tusen(r.maal)} ${r.enhet}`;

  function ringerSvg(ringer, str = 168) {
    const s = svgEl("svg", { viewBox: "0 0 168 168", width: str, height: str, class: "ringer", role: "img",
      "aria-label": ringer.map((r) => `${r.navn}: ${ringVerdi(r)}`).join(", ") });
    const tykk = 15, mellom = 4;
    const buer = [];
    ringer.forEach((r, i) => {
      const rad = 84 - tykk / 2 - 2 - i * (tykk + mellom);
      const omkrets = 2 * Math.PI * rad;
      const g = svgEl("g", { transform: "rotate(-90 84 84)", style: `--ring:${RINGFARGE[r.nokkel]}` });
      g.append(svgEl("circle", { cx: 84, cy: 84, r: rad, class: "ring-spor", "stroke-width": tykk }));
      const andel = Math.max(0, Math.min(1, r.andel));
      const bue = svgEl("circle", { cx: 84, cy: 84, r: rad, class: `ring-bue ${r.andel >= 1 ? "lukket" : ""}`, "stroke-width": tykk,
        "stroke-dasharray": `${omkrets} ${omkrets}`, "stroke-dashoffset": omkrets });
      g.append(bue);
      // en ekstra runde vises som en lysere bue oppå når du er over målet
      if (r.andel > 1) g.append(svgEl("circle", { cx: 84, cy: 84, r: rad, class: "ring-bue ekstra", "stroke-width": tykk,
        "stroke-dasharray": `${omkrets} ${omkrets}`, "stroke-dashoffset": omkrets * (1 - Math.min(1, r.andel - 1)) }));
      s.append(g);
      buer.push([bue, omkrets * (1 - (andel || 0.0001))]);
    });
    requestAnimationFrame(() => requestAnimationFrame(() => buer.forEach(([b, mål]) => b.setAttribute("stroke-dashoffset", mål))));
    return s;
  }

  function ukeKjede(sp) {
    const plan = new Set((ov.ukeplan?.dager || []).filter((d) => d.okter.some((o) => o.type === "styrke")).map((d) => d.dato));
    const aktiv = (d) => d.styrke || d.aktivitet;
    const rad = el("div", { class: "kjede" });
    sp.dager.forEach((d, i) => {
      if (i) rad.append(el("span", { class: `ledd ${aktiv(d) && aktiv(sp.dager[i - 1]) ? "fylt" : ""}` }));
      const cls = ["ledd-dag", d.styrke ? "styrke" : "", d.aktivitet ? "aktivitet" : "", d.i_dag ? "i-dag" : "",
        d.fremtid && plan.has(d.dato) ? "planlagt" : "", d.fremtid ? "fremtid" : ""].join(" ");
      const navn = new Date(d.dato).toLocaleDateString("nb-NO", { weekday: "short" }).slice(0, 2);
      rad.append(el("span", { class: cls, title: `${ukedag(d.dato)}${d.styrke ? " · styrke" : ""}${d.aktivitet ? " · kondisjon" : ""}${plan.has(d.dato) && d.fremtid ? " · planlagt økt" : ""}` },
        el("span", { class: "sirkel" }, d.styrke ? ikon("manual") : d.aktivitet ? ikon("lop") : null),
        el("small", {}, d.i_dag ? "i dag" : navn)));
    });
    return rad;
  }

  function spillKort(sp) {
    const n = sp.niva;
    const xpBar = el("div", { class: "xp-bar" }, el("div", { style: `width:${Math.round(n.andel * 100)}%` }));
    const nm = sp.neste_merke;
    const kort = el("div", { class: `kort spill ${sp.alle_lukket ? "alle-lukket" : ""}` },
      el("div", { class: "spill-topp" },
        el("div", { class: "niva-sirkel", title: `${tusen(n.xp)} XP totalt` }, el("small", {}, "nivå"), el("b", {}, n.nr)),
        el("div", { class: "niva-tekst" },
          el("div", { class: "niva-navn" }, n.navn),
          xpBar,
          el("small", {}, `${tusen(n.xp - n.fra)} / ${tusen(n.til - n.fra)} XP til nivå ${n.nr + 1}`, sp.xp_uka ? el("span", { class: "xp-uka" }, ` · +${tusen(sp.xp_uka)} denne uka`) : null)),
        sp.rekke ? el("div", { class: "rekke", title: `Ukemålet nådd ${sp.rekke} uker på rad (beste: ${sp.beste_rekke})` }, el("span", {}, "🔥"), el("b", {}, sp.rekke), el("small", {}, sp.rekke === 1 ? "uke" : "uker")) : null),
      el("div", { class: "ring-rad" },
        el("div", { class: "ring-boks" }, ringerSvg(sp.ringer),
          sp.alle_lukket ? el("span", { class: "ring-midt" }, "⭐") : null),
        el("ul", { class: "ring-forklaring" }, sp.ringer.map((r) => el("li", { style: `--ring:${RINGFARGE[r.nokkel]}` },
          el("span", { class: "ring-navn" }, r.navn, r.andel >= 1 ? el("span", { class: "hake" }, "✓") : null),
          el("b", {}, ringVerdi(r)),
          el("small", {}, r.andel >= 1 ? "Ringen er lukket!" : `${Math.round(r.andel * 100)} %`))))),
      ukeKjede(sp),
      sp.rekorder_uka.length ? el("div", { class: "rekord-linje" }, "⚡ ", el("b", {}, `${sp.rekorder_uka.length} ${sp.rekorder_uka.length === 1 ? "ny rekord" : "nye rekorder"} denne uka: `), sp.rekorder_uka.join(", ")) : null,
      el("button", { class: "merke-linje", onclick: () => merkerArk(sp) },
        el("span", { class: "merke-ikoner" }, sp.merker.filter((m) => m.oppnadd).slice(-4).map((m) => el("span", {}, m.ikon))),
        nm ? el("span", { class: "neste-merke" },
          el("small", {}, `Neste merke: ${nm.ikon} ${nm.tittel}`),
          el("span", { class: "minibar" }, el("span", { style: `width:${Math.round(nm.fremdrift * 100)}%` })))
          : el("span", { class: "neste-merke" }, el("small", {}, "Alle merker er tatt – sterkt!")),
        el("span", { class: "merke-antall" }, `${sp.oppnadd}/${sp.merker.length}`)));
    return kort;
  }

  function merkerArk(sp) {
    const n = sp.niva;
    aapneArk(el("h3", {}, "🏅 Merker og nivå"),
      el("p", { class: "hint" }, `Nivå ${n.nr} – ${n.navn} · ${tusen(n.xp)} XP. Du får 100 XP per økt, 2 per arbeidssett, 25 per ny rekord (inntil tre per økt), 150 når du når ukemålet, og litt for løping og gåing.`),
      el("div", { class: "merke-grid" }, sp.merker.map((m) => el("div", { class: `merke-kort ${m.oppnadd ? "har" : ""}` },
        el("span", { class: "merke-emoji" }, m.ikon),
        el("b", {}, m.tittel), el("small", {}, m.beskrivelse),
        m.oppnadd ? el("small", { class: "tatt" }, "Oppnådd") : el("span", { class: "minibar" }, el("span", { style: `width:${Math.round(m.fremdrift * 100)}%` }))))),
      el("p", { class: "forklaring", style: "font-size:13px" }, `${tusen(sp.okter)} økter · ${tusen(sp.totalt_kg)} kg løftet · ${sp.rekorder} rekorder · beste rekke ${sp.beste_rekke} uker`),
      el("div", { class: "ark-knapper" }, el("button", { class: "knapp", onclick: lukkArk }, "Lukk")));
  }

  function feir(sp) {
    const nye = sp.nye_merker || [];
    const rot = el("div", { class: "konfetti", "aria-hidden": "true" });
    for (let i = 0; i < 40; i++) rot.append(el("i", { style: `--x:${Math.random() * 100}vw;--d:${0.6 + Math.random() * 1.4}s;--r:${Math.random() * 720 - 360}deg;--f:${["var(--oransje)", "var(--gronn)", "var(--blaa)", "var(--gul)", "var(--rosa)", "var(--lilla)"][i % 6]}` }));
    document.body.append(rot);
    setTimeout(() => rot.remove(), 2600);
    vibrer([20, 40, 20]);
    aapneArk(el("div", { class: "feiring" },
      el("div", { class: "feiring-emoji" }, nye[0]?.ikon || "⬆️"),
      el("h3", {}, sp.nytt_niva ? `Nivå ${sp.niva.nr}: ${sp.niva.navn}!` : nye.length > 1 ? "Nye merker!" : "Nytt merke!"),
      nye.map((m) => el("p", {}, el("b", {}, `${m.ikon} ${m.tittel}`), ` – ${m.beskrivelse.toLowerCase()}`)),
      sp.nytt_niva && !nye.length ? el("p", {}, "Du har gått opp et nivå. Fortsett sånn!") : null,
      el("button", { class: "knapp", onclick: lukkArk }, "Yes!")));
  }

  // ================================================================ DAGSFORM OG UKEPLAN
  function dagsformKort(d) {
    const v = d.verdier;
    const chip = (verdi, tekst) => verdi == null ? null : el("span", { class: "merkelapp" }, tekst);
    return el("div", { class: `kort dagsform ${d.niva}` },
      el("div", { class: "kort-hode" }, el("h2", {}, d.tittel), el("span", { class: "dagsform-prikk" })),
      el("p", { class: "dagsform-rad" }, d.rad),
      el("div", { class: "chips" },
        chip(v.beredskap, `Beredskap ${v.beredskap}`), chip(v.sovn_score, `Søvn ${v.sovn_score}`),
        chip(v.sovn_min, `${tall(Math.round(v.sovn_min / 6) / 10)} t søvn`), chip(v.hrv, `HRV ${v.hrv}${d.hrv_snitt ? ` (snitt ${d.hrv_snitt})` : ""}`),
        chip(v.body_battery, `Body Battery ${v.body_battery}`), chip(v.stress, `Stress ${v.stress}`), chip(v.restitusjon, `Restitusjon ${v.restitusjon} t`)),
      d.grunner.length ? el("p", { class: "forklaring", style: "font-size:13px" }, `Fordi: ${d.grunner.join(", ")}.`) : null);
  }

  function ukeplanKort(u) {
    const i_dag = new Date().toLocaleDateString("sv-SE");
    const rad = (d) => el("li", { class: `${d.dato === i_dag ? "i-dag" : ""} ${d.borte ? "borte" : ""}` },
      el("span", { class: "uke-dag" }, d.dato === i_dag ? "I dag" : `${d.ukedag.slice(0, 3)} ${+d.dato.slice(8, 10)}.`),
      el("span", { class: "tekst" },
        d.okter.length ? el("span", { class: "chips" }, d.okter.map((o) => el("span", { class: `merkelapp ${o.type === "styrke" ? "aksent" : o.type === "lop" ? "lop" : ""}` },
          o.type === "lop" ? `🏃 ${o.tittel}${o.minutter ? ` ${o.minutter} min` : ""}` : o.navn || o.tittel))) : el("span", { class: "hviledag" }, d.borte ? "Borte" : "Hvile"),
        d.notat ? el("small", {}, d.notat) : null,
        d.kalender?.length ? el("small", { class: "kal" }, d.kalender.slice(0, 2).join(" · ")) : null));
    return el("div", { class: "kort ukeplan" },
      el("div", { class: "kort-hode" }, el("h2", {}, "De neste 7 dagene"), el("span", { class: `merkelapp ${u.kilde === "ai" ? "ai" : ""}` }, u.kilde === "ai" ? ikon("gnist") : null, u.kilde === "ai" ? "AI" : "Forslag")),
      u.oppsummering ? el("p", { class: "forklaring", style: "font-size:13px" }, u.oppsummering) : null,
      el("ul", { class: "uke-liste" }, u.dager.map(rad)),
      el("div", { class: "knapperad" },
        aiPaa() ? el("button", { class: "knapp ai-lys liten", style: "flex:1", onclick: ukeplanAiArk }, ikon("gnist"), u.kilde === "ai" ? "Ny plan med AI" : "Planlegg uka med AI") : null,
        u.kilde === "ai" ? el("button", { class: "knapp noytral liten", onclick: async () => { try { await slett(`api/profiler/${pid}/ukeplan`); visTrening(); } catch (e) { feil(e); } } }, "Appens forslag") : null),
      !Object.keys(profil()?.koblinger?.kalendere || {}).length ? el("p", { class: "forklaring", style: "font-size:12.5px" }, "Tips: velg jobb- og reisekalenderen under Helse → Hent data, så planlegges uka rundt den.") : null);
  }

  function ukeplanAiArk() {
    const onske = el("textarea", { placeholder: "Valgfritt: f.eks. «vil helst trene morgen», «onsdag passer ikke», «vil løpe langtur søndag»", rows: 3 });
    const knapp = el("button", { class: "knapp ai" }, ikon("gnist"), "Lag ukeplan");
    const status = el("div");
    knapp.addEventListener("click", async () => {
      knapp.disabled = true;
      status.innerHTML = ""; status.append(el("div", { style: "margin-top:12px" }, aiLaster("Treneren ser på kalenderen, dagsformen og programmet …")));
      try { await post(`api/profiler/${pid}/ukeplan/ai`, { onske: onske.value }); lukkArk(); visToast("Ukeplanen er klar"); visTrening(); }
      catch (e) { knapp.disabled = false; status.innerHTML = ""; feil(e); }
    });
    aapneArk(el("h3", {}, ikon("kalender"), "Planlegg uka"),
      el("p", { class: "hint" }, "Treneren plasserer styrkeøktene og løpeturene de neste 7 dagene rundt kalenderen din, dagsformen og løpeplanen. Neste styrkeøkt legges også i Garmin-kalenderen på riktig dag."),
      el("div", { class: "skjema" }, el("label", { class: "felt" }, onske)), status,
      el("div", { class: "ark-knapper" }, el("button", { class: "knapp noytral", onclick: lukkArk }, "Avbryt"), knapp));
  }

  // ================================================================ LØPING
  function lopeKort(l) {
    const typeIkon = { rolig: "lop", langtur: "lop", intervall: "flamme", lopgaa: "lop" };
    return el("div", { class: "kort lope-kort" },
      el("div", { class: "kort-hode" }, el("h2", {}, "Løping denne uka"), el("span", { class: "merkelapp aksent" }, `Uke ${l.uke} av ${l.uker}${l.lett_uke ? " · lettere" : ""}`)),
      profil()?.garmin_eksport?.loping ? el("p", { class: "forklaring", style: "font-size:13px;margin-top:-6px" }, "⌚ Turene ligger i Garmin-kalenderen – start dem fra «Treningskalender» på klokka.") : null,
      el("ul", { class: "lope-liste" }, l.plan.map((o, i) => el("li", { class: o.gjort ? "gjort" : i === l.plan.findIndex((x) => !x.gjort) ? "neste" : "" },
        el("span", { class: "lope-ikon" }, ikon(o.gjort ? "sjekk" : typeIkon[o.type] || "lop")),
        el("span", { class: "tekst" }, el("b", {}, o.dag ? `${o.dag[0].toUpperCase()}${o.dag.slice(1)}: ` : "", o.tittel, el("span", { class: "akt-navn" }, ` · ${o.minutter} min`)),
          o.gjort && o.logget ? el("small", {}, `Gjort ${dato(o.logget.start)}${o.logget.km ? ` · ${tall(o.logget.km)} km` : ""}${o.logget.tempo ? ` · ${o.logget.tempo} /km` : ""}`)
            : el("small", {}, o.beskrivelse), !o.gjort ? el("small", { class: "puls" }, `Puls: ${o.puls}`) : null)))),
      l.neste ? el("p", { class: "forklaring", style: "font-size:13px" }, "Turer fra klokka krysses av automatisk. Legg helst intervallene minst en dag før en tung beinøkt.") : el("p", { class: "forklaring" }, "Alle løpeturene denne uka er gjort – bra! 🏃"),
      el("button", { class: "knapp noytral liten", style: "width:100%", onclick: () => aktivitetArk(null, { type: "loping", etter: visTrening }) }, ikon("pluss"), "Registrer løpetur selv"));
  }

  async function lopePerioderKort(rot) {
    let d;
    try { d = await api(`api/profiler/${pid}/loping`); } catch (e) { return; }
    const i_dag = new Date().toLocaleDateString("sv-SE");
    const rad = (x) => {
      const status = x.fra <= i_dag && x.til >= i_dag ? "Pågår" : x.fra > i_dag ? "Kommer" : "Ferdig";
      return el("div", { class: "versjon" },
        el("span", { class: "tekst" }, el("b", {}, `${dato(x.fra)} – ${dato(x.til, true)}`),
          el("small", {}, `${(x.lopedager || []).map((i) => ["man", "tir", "ons", "tor", "fre", "lør", "søn"][i]).join(", ") || `${x.okter_per_uke} turer`} · ${d.nivaa[x.niva]} · mål: ${d.maal[x.maal].toLowerCase()}`)),
        el("span", { class: `merkelapp ${status === "Pågår" ? "opp" : ""}` }, status),
        el("button", { class: "ikonknapp", "aria-label": "Endre", onclick: () => lopeperiodeArk(x, d) }, ikon("blyant")));
    };
    rot.innerHTML = "";
    rot.append(el("div", { class: "kort" },
      el("div", { class: "kort-hode" }, el("h2", {}, "Løping i perioder")),
      d.perioder.length ? el("div", {}, d.perioder.map(rad)) : el("p", { class: "forklaring" }, "Vil du løpe i tillegg i en periode – f.eks. om sommeren – legger appen inn 1–3 løpeturer i uka med gradvis økning, ved siden av styrkeprogrammet."),
      el("button", { class: "knapp sekundaer liten", style: "width:100%", onclick: () => lopeperiodeArk(null, d) }, ikon("lop"), "Legg til løpeperiode")));
  }

  function lopeperiodeArk(x, d) {
    const iso = (dt) => dt.toLocaleDateString("sv-SE");
    const nesteMandag = () => { const t = new Date(); t.setDate(t.getDate() + ((8 - t.getDay()) % 7 || 7)); return t; };
    const v = x ? { ...x } : (() => { const f = nesteMandag(); const t = new Date(f); t.setDate(t.getDate() + 8 * 7 - 1); return { fra: iso(f), til: iso(t), okter_per_uke: 2, niva: "vanlig", maal: "form", juster_styrke: 1 }; })();
    const fra = el("input", { type: "date", value: v.fra, onchange: (e) => { v.fra = e.target.value; } });
    const til = el("input", { type: "date", value: v.til, onchange: (e) => { v.til = e.target.value; } });
    const hurtig = el("div", { class: "chips" },
      el("button", { class: "chip liten", onclick: () => { const f = nesteMandag(); const t = new Date(f); t.setDate(t.getDate() + 55); fra.value = v.fra = iso(f); til.value = v.til = iso(t); } }, "8 uker fra mandag"),
      el("button", { class: "chip liten", onclick: () => { const y = new Date().getMonth() > 7 ? new Date().getFullYear() + 1 : new Date().getFullYear(); fra.value = v.fra = `${y}-06-01`; til.value = v.til = `${y}-08-31`; } }, "Sommer (juni–august)"));
    const seg = (valg, nokkel) => {
      const e = el("div", { class: "segment" }, Object.entries(valg).map(([k, n]) => el("button", { class: String(v[nokkel]) === String(k) ? "valgt" : "", onclick: (ev) => {
        v[nokkel] = isNaN(+k) ? k : +k; for (const b of e.children) b.classList.toggle("valgt", b === ev.currentTarget);
      } }, n)));
      return e;
    };
    v.lopedager = [...(v.lopedager?.length ? v.lopedager : ({ 1: [5], 2: [1, 5], 3: [1, 3, 6] })[v.okter_per_uke || 2])];
    const DAGER = ["Man", "Tir", "Ons", "Tor", "Fre", "Lør", "Søn"];
    const dagvelger = el("div", { class: "chips" }, DAGER.map((n, i) => el("button", { class: `chip liten ${v.lopedager.includes(i) ? "valgt" : ""}`, onclick: (e) => {
      if (v.lopedager.includes(i)) { if (v.lopedager.length > 1) v.lopedager = v.lopedager.filter((x) => x !== i); }
      else if (v.lopedager.length < 3) v.lopedager = [...v.lopedager, i].sort();
      else { visToast("Maks 3 løpedager"); return; }
      for (const [j, b] of [...dagvelger.children].entries()) b.classList.toggle("valgt", v.lopedager.includes(j));
      void e;
    } }, n)));
    const maal = el("div", { class: "chips" }, Object.entries(d.maal).map(([k, n]) => el("button", { class: `chip liten ${v.maal === k ? "valgt" : ""}`, onclick: (ev) => {
      v.maal = k; for (const b of maal.children) b.classList.toggle("valgt", b === ev.currentTarget);
    } }, n)));
    aapneArk(el("h3", {}, ikon("lop"), x ? "Endre løpeperiode" : "Ny løpeperiode"),
      el("p", { class: "hint" }, "I perioden får du en ukeplan for løping på forsiden: rolige turer, én intervalløkt (4×4-metoden) og en langtur, med gradvis økning og en lettere uke hver fjerde uke. Turer fra klokka krysses av automatisk."),
      el("div", { class: "skjema" }, el("div", { class: "felt-rad" }, felt("Fra", fra), felt("Til", til)), hurtig,
        el("div", { class: "felt" }, el("span", {}, "Løpedager (1–3)"), dagvelger),
        el("div", { class: "felt" }, el("span", {}, "Nivå"), seg({ nybegynner: "Ny (løp/gå)", vanlig: "Av og til", erfaren: "Jevnlig" }, "niva")),
        el("div", { class: "felt" }, el("span", {}, "Mål"), maal),
        el("div", { class: "liste-rad", style: "min-height:0;padding:0" }, el("span", { class: "tekst" }, el("b", {}, "Juster styrketreningen"), el("small", {}, "Ett sett mindre på hjelpeøvelser for bein i perioden, så beina tåler løpingen. Hovedøvelsene endres ikke.")),
          bryter(!!v.juster_styrke, (b) => { v.juster_styrke = b ? 1 : 0; }))),
      el("div", { class: "ark-knapper" },
        x ? el("button", { class: "knapp fare", "aria-label": "Slett periode", onclick: async () => {
          if (!(await bekreft("Slette løpeperioden?", "Løpeturene du har gjort beholdes.", "Slett", true))) return;
          try { await slett(`api/loping/${x.id}`); visProgram(); } catch (e) { feil(e); }
        } }, ikon("soppel")) : el("button", { class: "knapp noytral", onclick: lukkArk }, "Avbryt"),
        el("button", { class: "knapp", onclick: async () => {
          try { if (x) await patch(`api/loping/${x.id}`, v); else await post(`api/profiler/${pid}/loping`, v); lukkArk(); visToast("Løpeperioden er lagret"); visProgram(); } catch (e) { feil(e); }
        } }, "Lagre")));
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
    const lopeRot = el("div");
    v.append(lopeRot);
    lopePerioderKort(lopeRot);
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
    const kl_ = o.klokke;
    const koblet = Object.keys(profil()?.koblinger || {}).length > 0;
    if (kl_) {
      const ana = kl_.analyse || {};
      v.append(el("div", { class: "kort" },
        el("div", { class: "kort-hode" }, el("h2", {}, "Puls fra klokka"), el("span", { class: "merkelapp" }, "⌚ Garmin")),
        el("div", { class: "nokkeltall" },
          el("div", { class: "tall-boks" }, el("span", { class: "tall-verdi" }, kl_.snittpuls || ana.snitt || "–"), el("span", { class: "tall-navn" }, "snittpuls")),
          el("div", { class: "tall-boks" }, el("span", { class: "tall-verdi" }, kl_.makspuls || ana.maks || "–"), el("span", { class: "tall-navn" }, "makspuls")),
          el("div", { class: "tall-boks" }, el("span", { class: "tall-verdi" }, kl_.kalorier || "–"), el("span", { class: "tall-navn" }, "kcal"))),
        kl_.puls?.length ? pulsgraf(kl_.puls, { sett: kl_.sett_tider }) : el("button", { class: "knapp noytral liten", style: "width:100%", onclick: async (e) => {
          e.currentTarget.disabled = true; e.currentTarget.textContent = "Henter pulskurve …";
          try { await post(`api/okter/${o.id}/klokke`); visOktDetalj(oid, fra); } catch (er) { feil(er); visOktDetalj(oid, fra); }
        } }, ikon("hjerte"), kl_.puls_hentet ? "Ingen pulskurve i økta fra klokka" : "Hent pulskurve"),
        kl_.puls?.length ? el("p", { class: "forklaring", style: "font-size:12.5px" }, "Streker = sett du logget (gule = oppvarming). Pulsen bør stige i settene og falle i pausene.") : null,
        kl_.soner ? soneStolper(kl_.soner) : null,
        kl_.belastning ? el("p", { class: "forklaring" }, `Treningsbelastning ${Math.round(kl_.belastning)}${kl_.aerob_effekt != null ? ` · aerob effekt ${tall(kl_.aerob_effekt)}` : ""}`) : null));
    } else if (koblet && o.status === "fullfort") {
      v.append(el("div", { class: "info-boks" }, ikon("hjerte"), el("span", {}, "Ingen styrkeøkt fra klokka er koblet til denne økta ennå. Den kobles automatisk når Garmin har synkronisert. ",
        el("button", { class: "lenke", onclick: async (e) => {
          e.currentTarget.disabled = true; e.currentTarget.textContent = "Ser etter …";
          try { const r = await post(`api/okter/${o.id}/klokke`); if (!r.okt.klokke) visToast("Fant ingen styrkeøkt fra klokka på samme tid"); visOktDetalj(oid, fra); } catch (er) { feil(er); }
        } }, "Se etter nå"))));
    }
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
        kl_?.analyse?.per_ovelse?.[oo.ovelse] ? (() => { const pa = kl_.analyse.per_ovelse[oo.ovelse]; return el("div", { class: "puls-linje" }, ikon("hjerte"),
          [pa.topp ? `topp i settene ${pa.topp}` : null, pa.foer_neste ? `før neste sett ${pa.foer_neste}` : null].filter(Boolean).join(" · ")); })() : null,
        oo.notat ? el("div", { class: "ov-notat" }, oo.notat) : null));
    }
    if (!o.ovelser.length) k.append(el("p", { class: "tom" }, "Ingen øvelser registrert."));
    k.append(el("button", { class: "legg-til", onclick: () => aapneOvelsevelger({ tittel: "Legg til øvelse", utstyrsprofil_id: o.utstyrsprofil_id, ved_valg: async (x) => {
      try { await post(`api/okter/${o.id}/ovelser`, { ovelse: x.nokkel }); lukkArk(); visOktDetalj(oid, fra); } catch (e) { feil(e); }
    } }) }, ikon("pluss"), "Legg til øvelse"));
    v.append(k);
    v.append(el("div", { class: "knapperad" },
      el("button", { class: "knapp noytral liten", style: "flex:1", onclick: () => endreOktArk(o, () => visOktDetalj(oid, fra)) }, ikon("blyant"), "Endre dato og notat"),
      Object.keys(profil()?.koblinger || {}).length && o.status === "fullfort" ? (o.garmin_sendt
        ? el("span", { class: "merkelapp opp", style: "align-self:center" }, ikon("sjekk"), "I Garmin")
        : el("button", { class: "knapp noytral liten", onclick: async (e) => {
          e.currentTarget.disabled = true;
          try { await post(`api/okter/${o.id}/garmin`); visToast("Økta er sendt til Garmin Connect"); visOktDetalj(oid, fra); } catch (er) { feil(er); visOktDetalj(oid, fra); }
        } }, "⌚ Send til Garmin")) : null,
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

  function linjegraf(serie, enhet = "", snitt = 0) {
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
    if (snitt && serie.length >= 4) {
      const glatt = serie.map((p, i) => {
        const fra = new Date(p.t).getTime() - (snitt - 1) * 864e5;
        const vindu = serie.filter((q, j) => j <= i && new Date(q.t).getTime() >= fra);
        return { t: p.t, y: vindu.reduce((s_, q) => s_ + q.y, 0) / vindu.length };
      });
      svg.append(svgEl("path", { class: "linje tynn", d }));
      svg.append(svgEl("path", { class: "linje", d: glatt.map((p, i) => `${i ? "L" : "M"}${x(p.t).toFixed(1)},${y(p.y).toFixed(1)}`).join(" ") }));
    } else {
      svg.append(svgEl("path", { class: "linje", d }));
    }
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

  // ================================================================ KROPP
  let kroppData = null;
  let kurveType = hent("kurvetype", "vekt");
  let kurveDager = hent("kurvedager", 90);
  const ENKEL = { vekt: 1, midje: 1, fettprosent: 1, hvilepuls: 0, vo2max: 0, skritt: 0, blodtrykk_sys: 0, blodtrykk_dia: 0 };
  const fmt = (typ, v) => v == null ? "–" : (ENKEL[typ] ? tall(Math.round(v * 10) / 10) : tusen(v));

  async function visKropp() {
    vis("kropp");
    const v = $("v-kropp");
    if (!pid) { v.innerHTML = ""; v.append(el("p", { class: "tom" }, "Lag en profil først.")); return; }
    try { kroppData = await api(`api/profiler/${pid}/kropp`); } catch (e) { feil(e); return; }
    const k = kroppData;
    const koblet = Object.keys(k.koblinger || {}).length > 0;
    settTittel("Helse", koblet ? "Hentes automatisk fra Home Assistant" : "");
    v.innerHTML = "";

    if (!koblet && S.ai_tilgjengelig) {
      v.append(el("div", { class: "velkommen" }, el("h2", {}, "Hent data automatisk"),
        el("p", {}, "Har du klokke eller vekt i Home Assistant (f.eks. Garmin Connect), kan løpeturer, gåturer, vekt, hvilepuls, VO₂max og skritt hentes inn av seg selv."),
        el("button", { class: "knapp", onclick: koblingArk }, ikon("hjerte"), "Velg hva som skal hentes")));
    }

    // nøkkeltall
    const m = k.maalinger, av = k.avledet;
    const boks = (verdi, navn, under) => el("div", { class: "tall-boks" }, el("span", { class: "tall-verdi" }, verdi), el("span", { class: "tall-navn" }, navn), under ? el("span", { class: "tall-under" }, under) : null);
    const endr = (e, enhet, bra = "ned") => e == null || e === 0 ? null : el("span", { class: (e < 0) === (bra === "ned") ? "trend-opp" : "trend-ned" }, `${e > 0 ? "+" : ""}${tall(e)} ${enhet} / 30 d`);
    const tall_ = el("div", { class: "nokkeltall" },
      boks(m.vekt ? `${fmt("vekt", m.vekt.verdi)} kg` : "–", "vekt", m.vekt ? endr(m.vekt.endring_30, "kg") : null),
      av.bmi ? boks(tall(av.bmi), "BMI", av.bmi_kategori) : boks(av.alder ? `${av.alder} år` : "–", "alder"),
      boks(m.hvilepuls ? `${fmt("hvilepuls", m.hvilepuls.verdi)}` : "–", "hvilepuls", m.hvilepuls ? endr(m.hvilepuls.endring_30, "") : null));
    v.append(tall_);
    const ekstra = [];
    if (m.vo2max) ekstra.push(boks(fmt("vo2max", m.vo2max.verdi), "VO₂max"));
    if (m.fettprosent) ekstra.push(boks(`${fmt("fettprosent", m.fettprosent.verdi)} %`, "fettprosent"));
    if (m.midje) ekstra.push(boks(`${fmt("midje", m.midje.verdi)} cm`, "midje", av.midje_hoyde ? `midje/høyde ${tall(av.midje_hoyde)}` : null));
    if (av.makspuls) ekstra.push(boks(`${av.makspuls}`, "makspuls (est.)"));
    if (m.skritt) ekstra.push(boks(tusen(m.skritt.verdi), "skritt", dato(m.skritt.dato)));
    if (ekstra.length) v.append(el("div", { class: "nokkeltall" }, ekstra.slice(0, 6)));

    // kurve
    const kurve = el("div", { class: "kort" });
    v.append(kurve);
    tegnKurve(kurve);

    // aktivitet
    const u = k.denne_uka;
    const pst = Math.min(100, Math.round(100 * u.minutter / 150));
    const typer = Object.entries(u.per_type).map(([t, x]) => el("span", { class: "merkelapp aksent" }, `${k.aktivitetstyper[t]?.navn || t}: ${x.km ? `${tall(x.km)} km` : `${x.minutter} min`}`));
    if (u.styrkeokter) typer.push(el("span", { class: "merkelapp aksent" }, `Styrke: ${u.styrkeokter} ${u.styrkeokter === 1 ? "økt" : "økter"}`));
    v.append(el("div", { class: "kort" },
      el("div", { class: "kort-hode" }, el("h2", {}, "Aktivitet denne uka"), el("span", { class: "merkelapp" }, `${u.minutter} / 150 min`)),
      el("div", { class: "fremdrift" }, el("div", { style: `width:${pst}%` })),
      typer.length ? el("div", { class: "chips" }, typer) : el("p", { class: "forklaring" }, "Ingen aktivitet registrert ennå denne uka."),
      soylegraf(k.uker.map((x) => ({ etikett: `u${x.uke}`, verdi: x.minutter })), 150),
      el("p", { class: "forklaring", style: "font-size:13px" }, "Aktivitetsminutter = moderat + 2 × høy intensitet (WHO/Helsedirektoratet: 150–300 i uka). Løping teller som høy intensitet, gåing og styrke som moderat. Stiplet linje = 150.")));

    // aktiviteter
    const liste = el("div", { class: "kort", style: "padding:12px 16px" },
      el("div", { class: "kort-hode" }, el("h2", {}, "Løping, gåing og annen aktivitet"), koblet ? el("button", { class: "ikonknapp", "aria-label": "Hent nå", onclick: async () => {
        try { const r = await post(`api/profiler/${pid}/synk`, {}); visToast(r.importert || r.maalinger ? `Hentet ${r.importert} aktiviteter og ${r.maalinger} målinger` : "Alt er oppdatert"); visKropp(); } catch (e) { feil(e); }
      } }, ikon("angre")) : null));
    if (!k.aktiviteter.length) liste.append(el("p", { class: "tom" }, "Ingen aktiviteter siste 60 dager."));
    for (const a of k.aktiviteter.slice(0, 15)) {
      const d = new Date(a.start);
      liste.append(el("button", { class: "okt-rad", onclick: () => aktivitetArk(a) },
        el("span", { class: `dato-boks akt-${a.type}` }, el("b", {}, d.getDate()), el("small", {}, d.toLocaleDateString("nb-NO", { month: "short" }).replace(".", ""))),
        el("span", { class: "tekst" }, el("b", {}, a.typenavn, a.navn && a.navn !== a.typenavn ? el("span", { class: "akt-navn" }, ` · ${a.navn}`) : null),
          el("small", {}, [a.km ? `${tall(a.km)} km` : null, `${a.minutter} min`, a.tempo ? `${a.tempo} /km` : a.fart ? `${tall(a.fart)} km/t` : null, a.snittpuls ? `puls ${a.snittpuls}` : null].filter(Boolean).join(" · "))),
        a.kilde === "garmin" ? el("span", { class: "merkelapp" }, "Klokke") : null, ikon("hoyre")));
    }
    liste.append(el("button", { class: "legg-til", style: "margin-top:10px", onclick: () => aktivitetArk(null) }, ikon("pluss"), "Registrer aktivitet"));
    v.append(liste);

    // Garmin Connect
    if (koblet) {
      const g = k.garmin_eksport || {};
      const lagre_ = async (endring) => {
        try {
          const r = await put(`api/profiler/${pid}/garmin`, { ...g, ...endring });
          Object.assign(g, r.garmin_eksport);
          await lastStart();
          const st = r.styrke || {};
          if (st.nye) visToast(`${st.nye} styrkeøkter lagt i Garmin${st.planlagt ? " – neste ligger i kalenderen" : ""}`);
          else if (r.lagt_inn) visToast(`${r.lagt_inn} løpeturer lagt i Garmin-kalenderen`);
          else if (r.fjernet || st.fjernet) visToast("Fjernet fra Garmin");
          visKropp();
        } catch (e) { feil(e); visKropp(); }
      };
      v.append(el("div", { class: "kort" },
        el("h2", {}, "Til Garmin Connect"),
        el("div", { class: "liste-rad", style: "min-height:0;padding:0" }, el("span", { class: "tekst" }, el("b", {}, "Styrkeøkter til klokka"), el("small", {}, "Hver økt i programmet ligger i Garmin med øvelser, sett, reps, kg og hvile – oppdatert med dagens vektforslag. Neste økt legges i kalenderen, så klokka guider deg og Garmin-aktiviteten får øvelser og vekter.")), bryter(g.styrke, (x) => lagre_({ styrke: x }))),
        g.styrke && k.garmin_styrke?.length ? el("p", { class: "forklaring", style: "font-size:13px" }, "I Garmin: " + k.garmin_styrke.map((x) => `${x.navn}${x.schedule_dato ? ` (i kalenderen ${dato(x.schedule_dato)})` : ""}`).join(" · ")) : null,
        el("div", { class: "liste-rad", style: "min-height:0;padding:0" }, el("span", { class: "tekst" }, el("b", {}, "Send fullførte økter som aktivitet"), el("small", {}, "Bare hvis du ikke starter økta på klokka – ellers blir den liggende dobbelt.")), bryter(g.okter, (x) => lagre_({ okter: x }))),
        el("div", { class: "liste-rad", style: "min-height:0;padding:0" }, el("span", { class: "tekst" }, el("b", {}, "Løpeturer til klokka"), el("small", {}, "Turene i løpeplanen legges i Garmin-kalenderen 2 uker fram, med oppvarming, drag og pulssoner – klokka guider deg.")), bryter(g.loping, (x) => lagre_({ loping: x }))),
        g.loping && k.garmin_lagt_inn?.length ? el("p", { class: "forklaring", style: "font-size:13px" }, "I Garmin-kalenderen: " + k.garmin_lagt_inn.map((x) => `${dato(x.dato)} ${x.nokkel.split(":")[2]}`).join(" · ")) : null,
        g.loping && !k.garmin_lagt_inn?.length ? el("p", { class: "forklaring", style: "font-size:13px" }, "Ingen løpeturer å legge inn ennå – legg inn en løpeperiode under Program.") : null,
        g.styrke ? el("p", { class: "forklaring", style: "font-size:13px" }, "På klokka: Trening → Styrke → Treningsøkter / Treningskalender. Juster vekt eller reps på klokka hvis du avviker – men logg settene i appen, den henter ikke settene tilbake.") : null));
    }

    // kroppsprofil og puls
    const p = profil();
    v.append(el("div", { class: "kort" },
      el("div", { class: "kort-hode" }, el("h2", {}, "Kroppsprofil"), el("button", { class: "lenke", onclick: () => profilArk(p) }, ikon("blyant"), "Endre")),
      el("p", { class: "forklaring" }, [av.alder ? `${av.alder} år` : "Alder ikke oppgitt", av.hoyde_cm ? `${tall(av.hoyde_cm)} cm` : "høyde ikke oppgitt", p.kjonn ? p.kjonn : null].filter(Boolean).join(" · ")),
      av.soner ? el("details", {}, el("summary", { class: "lenke", style: "cursor:pointer" }, `Pulssoner (makspuls ${av.makspuls}, estimert)`),
        el("table", { class: "tabell", style: "margin-top:8px" }, el("tbody", {}, av.soner.map((z) => el("tr", {}, el("td", {}, `Sone ${z.sone}`), el("td", {}, `${z.fra}–${z.til} slag/min`), el("td", {}, ["Rolig", "Lett", "Moderat", "Hardt", "Maks"][z.sone - 1]))))),
        el("p", { class: "forklaring", style: "font-size:12.5px;margin-top:6px" }, "Makspuls estimert med HUNT-formelen (211 − 0,64 × alder). Har du målt makspulsen din, er den mer presis.")) : el("p", { class: "forklaring" }, "Legg inn fødselsår for å få estimert makspuls og pulssoner."),
      S.ai_tilgjengelig ? el("button", { class: "knapp noytral liten", style: "width:100%", onclick: koblingArk }, ikon("hjerte"), koblet ? "Endre hva som hentes fra Home Assistant" : "Hent data fra Home Assistant") : null));
  }

  async function tegnKurve(kort) {
    const k = kroppData;
    const harData = Object.keys(k.maalinger);
    const typer = ["vekt", ...Object.keys(k.maaletyper).filter((t) => t !== "vekt" && harData.includes(t))];
    if (!typer.includes(kurveType)) kurveType = "vekt";
    let rader = [];
    try { rader = (await api(`api/profiler/${pid}/maalinger?type=${kurveType}${kurveDager ? `&dager=${kurveDager}` : ""}`)).maalinger; } catch (e) { feil(e); }
    const t = k.maaletyper[kurveType];
    kort.innerHTML = "";
    kort.append(el("div", { class: "kort-hode" }, el("h2", {}, t.navn), el("button", { class: "knapp sekundaer liten", onclick: maalingArk }, ikon("pluss"), "Ny måling")));
    if (typer.length > 1) kort.append(el("div", { class: "chips rull" }, typer.map((x) => el("button", { class: `chip liten ${x === kurveType ? "valgt" : ""}`, onclick: () => { kurveType = x; lagre("kurvetype", x); tegnKurve(kort); } }, k.maaletyper[x].navn))));
    kort.append(el("div", { class: "segment" }, [[30, "1 mnd"], [90, "3 mnd"], [365, "1 år"], [0, "Alt"]].map(([n, navn]) =>
      el("button", { class: n === kurveDager ? "valgt" : "", onclick: () => { kurveDager = n; lagre("kurvedager", n); tegnKurve(kort); } }, navn))));
    if (rader.length >= 2) {
      kort.append(linjegraf(rader.map((r) => ({ t: r.dato, y: r.verdi })), ` ${t.enhet}`, kurveType === "vekt" ? 7 : 0));
      const forste = rader[0].verdi, sist = rader[rader.length - 1].verdi;
      kort.append(el("p", { class: "forklaring", style: "font-size:13px" }, `${rader.length} målinger · fra ${fmt(kurveType, forste)} til ${fmt(kurveType, sist)} ${t.enhet} (${sist - forste > 0 ? "+" : ""}${fmt(kurveType, sist - forste)})${kurveType === "vekt" ? " · tykk linje = 7 dagers snitt" : ""}`));
    } else if (rader.length === 1) {
      kort.append(el("p", { class: "forklaring" }, `Én måling: ${fmt(kurveType, rader[0].verdi)} ${t.enhet} (${dato(rader[0].dato, true)}). Kurven vises fra to målinger.`));
    } else {
      kort.append(el("p", { class: "tom" }, "Ingen målinger i perioden."));
    }
    if (rader.length) {
      kort.append(el("details", {}, el("summary", { class: "lenke", style: "cursor:pointer" }, "Alle målinger"),
        el("div", {}, [...rader].reverse().slice(0, 60).map((r) => el("div", { class: "versjon" },
          el("span", { class: "tekst" }, el("b", {}, `${fmt(kurveType, r.verdi)} ${t.enhet}`), el("small", {}, `${dato(r.dato, true)} · ${r.kilde === "manuell" ? "lagt inn" : "Home Assistant"}`)),
          el("button", { class: "ikonknapp", "aria-label": "Slett måling", onclick: async () => { try { await slett(`api/maalinger/${r.id}`); visKropp(); } catch (e) { feil(e); } } }, ikon("soppel")))))));
    }
  }

  function pulsgraf(serie, { sett = [] } = {}) {
    const B = 320, H = 150, ml = 30, mr = 6, mt = 10, mb = 20;
    const hr = serie.map((p) => p[1]);
    let lo = Math.min(...hr), hi = Math.max(...hr);
    lo = Math.floor((lo - 5) / 10) * 10; hi = Math.ceil((hi + 5) / 10) * 10;
    const tMaks = Math.max(serie[serie.length - 1][0], ...sett.map((s) => s.t), 60);
    const x = (t) => ml + (t / tMaks) * (B - ml - mr);
    const y = (v) => mt + (1 - (v - lo) / (hi - lo)) * (H - mt - mb);
    const svg = svgEl("svg", { viewBox: `0 0 ${B} ${H}`, role: "img", "aria-label": "Pulskurve" });
    for (let v = lo; v <= hi; v += (hi - lo > 60 ? 20 : 10)) {
      svg.append(svgEl("line", { class: "rutenett", x1: ml, x2: B - mr, y1: y(v), y2: y(v) }));
      svg.append(svgEl("text", { class: "akse-tekst", x: ml - 5, y: y(v) + 3, "text-anchor": "end" }, v));
    }
    for (const s of sett) {
      if (s.t < 0 || s.t > tMaks) continue;
      svg.append(svgEl("line", { class: s.oppvarming ? "sett-strek oppv" : "sett-strek", x1: x(s.t), x2: x(s.t), y1: mt, y2: H - mb }));
    }
    const d = serie.map((p, i) => `${i ? "L" : "M"}${x(p[0]).toFixed(1)},${y(p[1]).toFixed(1)}`).join(" ");
    svg.append(svgEl("path", { class: "puls-linje-graf", d }));
    const steg = tMaks > 3600 ? 1200 : tMaks > 1800 ? 600 : 300;
    for (let t = 0; t <= tMaks; t += steg) svg.append(svgEl("text", { class: "akse-tekst", x: x(t), y: H - 5, "text-anchor": t === 0 ? "start" : "middle" }, `${Math.round(t / 60)} min`));
    return el("div", { class: "graf" }, svg);
  }

  function tempograf(serie) {
    // glatt farten over ~30 s og vis tempo (min/km), raskere = høyere
    const punkter = serie.filter((p) => p[2] && p[2] > 0.8).map((p, i, arr) => {
      const vindu = arr.slice(Math.max(0, i - 3), i + 3);
      return [p[0], vindu.reduce((s_, q) => s_ + q[2], 0) / vindu.length];
    });
    if (punkter.length < 2) return null;
    const B = 320, H = 120, ml = 34, mr = 6, mt = 10, mb = 20;
    const tempo = (v) => 1000 / v / 60;
    const ts = punkter.map((p) => tempo(p[1]));
    const lo = Math.min(...ts), hi = Math.min(Math.max(...ts), lo + 6);
    const tMaks = punkter[punkter.length - 1][0];
    const x = (t) => ml + (t / tMaks) * (B - ml - mr);
    const y = (m) => mt + ((Math.min(m, hi) - lo) / Math.max(0.5, hi - lo)) * (H - mt - mb);
    const svg = svgEl("svg", { viewBox: `0 0 ${B} ${H}`, role: "img", "aria-label": "Tempo" });
    for (const m of [lo, (lo + hi) / 2, hi]) {
      svg.append(svgEl("line", { class: "rutenett", x1: ml, x2: B - mr, y1: y(m), y2: y(m) }));
      svg.append(svgEl("text", { class: "akse-tekst", x: ml - 5, y: y(m) + 3, "text-anchor": "end" }, `${Math.floor(m)}:${String(Math.round((m % 1) * 60)).padStart(2, "0")}`));
    }
    svg.append(svgEl("path", { class: "linje", d: punkter.map((p, i) => `${i ? "L" : "M"}${x(p[0]).toFixed(1)},${y(tempo(p[1])).toFixed(1)}`).join(" ") }));
    return el("div", { class: "graf" }, svg);
  }

  function soneStolper(soner) {
    const tot = soner.reduce((a, b) => a + b, 0) || 1;
    const navn = ["Rolig", "Lett", "Moderat", "Hardt", "Maks"];
    return el("div", { class: "soner" }, el("div", { class: "ark-etikett", style: "margin-top:6px" }, "Tid i pulssoner"),
      soner.map((sek, i) => el("div", { class: "sone-rad" }, el("span", {}, `${i + 1} ${navn[i]}`),
        el("span", { class: "muskel-bar" }, el("i", { class: `sone${i + 1}`, style: `width:${(100 * sek / tot).toFixed(1)}%` })),
        el("span", {}, `${Math.round(sek / 60)} min`))));
  }

  function soylegraf(punkter, mal) {
    const B = 320, H = 120, mb = 18, mt = 14;
    const maks = Math.max(mal || 0, ...punkter.map((p) => p.verdi), 1) * 1.08;
    const bw = B / punkter.length;
    const svg = svgEl("svg", { viewBox: `0 0 ${B} ${H}`, role: "img", "aria-label": "Søylediagram" });
    const yv = (n) => mt + (1 - n / maks) * (H - mt - mb);
    if (mal) svg.append(svgEl("line", { class: "maal-linje", x1: 0, x2: B, y1: yv(mal), y2: yv(mal) }));
    punkter.forEach((p, i) => {
      const h = Math.max(3, (H - mt - mb) * p.verdi / maks);
      svg.append(svgEl("rect", { class: `soyle ${p.verdi ? "" : "tom"}`, x: i * bw + 3, y: H - mb - h, width: bw - 6, height: h, rx: 4 }));
      if (i === punkter.length - 1 || i % 2 === 1) svg.append(svgEl("text", { class: "akse-tekst", x: i * bw + bw / 2, y: H - 4, "text-anchor": "middle" }, p.etikett));
    });
    return el("div", { class: "graf" }, svg);
  }

  function maalingArk() {
    const k = kroppData;
    const datoInp = el("input", { type: "date", value: new Date().toLocaleDateString("sv-SE") });
    const felter = {};
    const inp = (typ) => { felter[typ] = el("input", { type: "text", inputmode: "decimal", placeholder: k.maaletyper[typ].enhet }); return felt(k.maaletyper[typ].navn, felter[typ]); };
    aapneArk(el("h3", {}, ikon("vekt"), "Ny måling"), el("p", { class: "hint" }, "Fyll inn det du har målt – resten kan stå tomt. Mål gjerne vekt om morgenen før frokost for jevnest kurve."),
      el("div", { class: "skjema" }, felt("Dato", datoInp), el("div", { class: "felt-rad" }, inp("vekt"), inp("midje")),
        el("div", { class: "felt-rad" }, inp("fettprosent"), inp("hvilepuls")), el("div", { class: "felt-rad" }, inp("blodtrykk_sys"), inp("blodtrykk_dia")), inp("vo2max")),
      el("div", { class: "ark-knapper" }, el("button", { class: "knapp noytral", onclick: lukkArk }, "Avbryt"),
        el("button", { class: "knapp", onclick: async () => {
          const verdier = Object.fromEntries(Object.entries(felter).map(([t, e]) => [t, e.value.trim()]).filter(([, x]) => x));
          try { await post(`api/profiler/${pid}/maalinger`, { verdier, dato: datoInp.value }); lukkArk(); visToast("Måling lagret"); visKropp(); } catch (e) { feil(e); }
        } }, "Lagre")));
    setTimeout(() => felter.vekt.focus(), 250);
  }

  const AKT_TYPER = { loping: { navn: "Løping" }, gaing: { navn: "Gåing" }, tur: { navn: "Fjelltur" }, sykling: { navn: "Sykling" }, ski: { navn: "Ski" }, svomming: { navn: "Svømming" }, annet: { navn: "Annet" } };
  function aktivitetArk(a, { type = null, etter = null } = {}) {
    const k = kroppData || { aktivitetstyper: AKT_TYPER };
    if (a && a.kilde !== "manuell") {
      const pulsRot = el("div", { style: "margin-top:10px" }, el("div", { class: "laster" }, "Henter pulskurve …"));
      const tegnPuls = (serie) => {
        pulsRot.innerHTML = "";
        if (serie.length) {
          pulsRot.append(el("div", { class: "ark-etikett" }, "Puls"), pulsgraf(serie));
          const tg = serie.some((p) => p[2]) && ["loping", "gaing", "tur"].includes(a.type) ? tempograf(serie) : null;
          if (tg) pulsRot.append(el("div", { class: "ark-etikett" }, "Tempo (min/km)"), tg);
        }
      };
      api(`api/aktiviteter/${a.id}`).then(async (r) => {
        if (r.puls.length) { tegnPuls(r.puls); return; }
        if (r.puls_hentet) { pulsRot.innerHTML = ""; return; }
        try { const p = await post(`api/aktiviteter/${a.id}/puls`); tegnPuls(p.puls); }
        catch (e) { pulsRot.innerHTML = ""; pulsRot.append(el("p", { class: "forklaring" }, `Pulskurve: ${e.message}`)); }
      }).catch(() => { pulsRot.innerHTML = ""; });
      aapneArk(el("h3", {}, ikon("lop"), a.navn || a.typenavn), el("p", { class: "hint" }, `${ukedag(a.start)} kl. ${kl(a.start)} · hentet fra klokka`),
        el("div", { class: "nokkeltall" },
          el("div", { class: "tall-boks" }, el("span", { class: "tall-verdi" }, a.km ? tall(a.km) : "–"), el("span", { class: "tall-navn" }, "km")),
          el("div", { class: "tall-boks" }, el("span", { class: "tall-verdi" }, `${a.minutter}`), el("span", { class: "tall-navn" }, "minutter")),
          el("div", { class: "tall-boks" }, el("span", { class: "tall-verdi" }, a.tempo || (a.fart ? tall(a.fart) : "–")), el("span", { class: "tall-navn" }, a.tempo ? "min/km" : "km/t"))),
        el("div", { class: "nokkeltall", style: "margin-top:8px" },
          el("div", { class: "tall-boks" }, el("span", { class: "tall-verdi" }, a.snittpuls || "–"), el("span", { class: "tall-navn" }, "snittpuls")),
          el("div", { class: "tall-boks" }, el("span", { class: "tall-verdi" }, a.makspuls || "–"), el("span", { class: "tall-navn" }, "makspuls")),
          el("div", { class: "tall-boks" }, el("span", { class: "tall-verdi" }, a.hoydemeter ? Math.round(a.hoydemeter) : "–"), el("span", { class: "tall-navn" }, "høydemeter"))),
        el("p", { class: "forklaring", style: "margin-top:10px" }, [a.kalorier ? `${a.kalorier} kcal` : null, a.skritt ? `${tusen(a.skritt)} skritt` : null, a.aerob_effekt != null ? `aerob effekt ${tall(a.aerob_effekt)}` : null, `${Math.round((a.moderate_min || 0) + 2 * (a.hoy_min || 0))} aktivitetsminutter`].filter(Boolean).join(" · ")),
        a.soner ? soneStolper(a.soner) : null,
        pulsRot,
        el("div", { class: "ark-knapper" }, el("button", { class: "knapp fare", onclick: async () => {
          if (!(await bekreft("Fjerne aktiviteten?", "Den hentes ikke inn igjen automatisk.", "Fjern", true))) return;
          try { await slett(`api/aktiviteter/${a.id}`); visKropp(); } catch (e) { feil(e); }
        } }, ikon("soppel")), el("button", { class: "knapp", onclick: lukkArk }, "Lukk")));
      return;
    }
    let typ = a?.type || type || "loping";
    const typer = el("div", { class: "chips" }, Object.entries(k.aktivitetstyper).filter(([t]) => t !== "styrke").map(([t, x]) => el("button", { class: `chip liten ${t === typ ? "valgt" : ""}`, onclick: (e) => {
      typ = t; for (const b of typer.children) b.classList.toggle("valgt", b === e.currentTarget);
    } }, x.navn)));
    const tid = el("input", { type: "datetime-local", value: tilLokalInput(a?.start || Date.now() - 36e5) });
    const min = el("input", { type: "text", inputmode: "numeric", value: a?.minutter || "", placeholder: "min" });
    const km = el("input", { type: "text", inputmode: "decimal", value: a?.km ? tall(a.km) : "", placeholder: "km" });
    const puls = el("input", { type: "text", inputmode: "numeric", value: a?.snittpuls || "", placeholder: "valgfritt" });
    const notat = el("input", { value: a?.notat || "", placeholder: "valgfritt" });
    aapneArk(el("h3", {}, ikon("lop"), a ? "Endre aktivitet" : "Registrer aktivitet"),
      el("div", { class: "ark-etikett" }, "Type"), typer,
      el("div", { class: "skjema", style: "margin-top:12px" }, felt("Når", tid), el("div", { class: "felt-rad tre" }, felt("Minutter", min), felt("Distanse (km)", km), felt("Snittpuls", puls)), felt("Notat", notat)),
      el("div", { class: "ark-knapper" },
        a ? el("button", { class: "knapp fare", onclick: async () => { try { await slett(`api/aktiviteter/${a.id}`); lukkArk(); visKropp(); } catch (e) { feil(e); } } }, ikon("soppel")) : el("button", { class: "knapp noytral", onclick: lukkArk }, "Avbryt"),
        el("button", { class: "knapp", onclick: async () => {
          const body = { type: typ, start: new Date(tid.value).toISOString(), minutter: min.value, km: km.value, snittpuls: puls.value, notat: notat.value };
          try { if (a) await patch(`api/aktiviteter/${a.id}`, body); else await post(`api/profiler/${pid}/aktiviteter`, body); lukkArk(); visToast("Aktivitet lagret"); (etter || visKropp)(); } catch (e) { feil(e); }
        } }, "Lagre")));
  }

  async function koblingArk() {
    let r;
    try { r = await api(`api/profiler/${pid}/ha-kilder`); } catch (e) { feil(e); return; }
    if (r.feil) { visToast(r.feil); return; }
    const naa_ = profil().koblinger || {};
    const valg = { ...r.forslag, ...naa_ };
    const navn = { aktiviteter: "Aktiviteter (løping, gåing m.m.)", vekt: "Vekt", hvilepuls: "Hvilepuls", vo2max: "VO₂max", skritt: "Skritt per dag", fettprosent: "Fettprosent",
      sovn_score: "Søvnscore", sovn_min: "Søvnlengde", hrv: "HRV (natt)", hrv_status: "HRV-status", body_battery: "Body Battery", stress: "Stress",
      beredskap: "Treningsberedskap", restitusjon: "Restitusjonstid", treningsstatus: "Treningsstatus" };
    const felter = Object.entries(navn).map(([typ, tekst]) => {
      const liste = r.kilder[typ] || [];
      const sel = el("select", { onchange: () => { valg[typ] = sel.value; } }, el("option", { value: "" }, liste.length ? "Ikke hent" : "Fant ingen sensor"),
        liste.map((x) => el("option", { value: x.entity_id }, `${x.navn}${x.state && !["unknown", "unavailable"].includes(x.state) && typ !== "aktiviteter" ? ` (${x.state}${x.enhet ? ` ${x.enhet}` : ""})` : ""}`)));
      sel.value = valg[typ] || "";
      if (!liste.length) sel.disabled = true;
      return felt(tekst, sel);
    });
    valg.kalendere = [...(naa_.kalendere || r.forslag.kalendere || [])];
    const kalVelger = el("div", { class: "chips" }, (r.kilder.kalendere || []).map((x) => el("button", { class: `chip liten ${valg.kalendere.includes(x.entity_id) ? "valgt" : ""}`, onclick: (e) => {
      valg.kalendere = valg.kalendere.includes(x.entity_id) ? valg.kalendere.filter((y) => y !== x.entity_id) : [...valg.kalendere, x.entity_id];
      e.currentTarget.classList.toggle("valgt", valg.kalendere.includes(x.entity_id));
    } }, x.navn)));
    const knapp = el("button", { class: "knapp" }, "Lagre og hent");
    knapp.addEventListener("click", async () => {
      knapp.disabled = true;
      knapp.textContent = "Henter historikk …";
      try {
        const res = await put(`api/profiler/${pid}/koblinger`, { koblinger: Object.fromEntries(Object.entries(valg).filter(([, x]) => Array.isArray(x) ? x.length : x)) });
        lukkArk(); await lastStart();
        visToast(`Koblet! Hentet ${res.importert} aktiviteter og ${res.maalinger} målinger.`);
        visKropp();
      } catch (e) { knapp.disabled = false; knapp.textContent = "Lagre og hent"; feil(e); }
    });
    aapneArk(el("h3", {}, ikon("hjerte"), "Hent fra Home Assistant"),
      el("p", { class: "hint" }, `Velg sensorene som hører til ${profil().navn}. Forslagene er gjettet ut fra navnene – sjekk at det stemmer. Data hentes hvert kvarter, og første gang hentes også historikk bakover.`),
      el("div", { class: "skjema" }, felter),
      el("div", { class: "ark-etikett" }, "Kalendere å planlegge rundt"),
      el("p", { class: "forklaring", style: "font-size:13px;margin-bottom:8px" }, "F.eks. jobb og reiser. Tittel, tid og sted brukes til ukeplanen og sendes til AI-treneren når den planlegger."),
      kalVelger,
      el("p", { class: "forklaring", style: "margin-top:10px;font-size:13px" }, "Startposisjon (GPS) lagres ikke."),
      el("div", { class: "ark-knapper" }, el("button", { class: "knapp noytral", onclick: lukkArk }, "Avbryt"), knapp));
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
    const velgPlan = el("select", { onchange: () => lagreInn({ ai_entitet_plan: velgPlan.value }) }, el("option", { value: "" }, "Samme som over"));
    aiKort.append(felt("AI til planlegging", velgPlan, "Brukes når treneren lager eller justerer program, ny blokk, ukeplan og startvekter – oppgavene der en kraftigere modell (f.eks. Sonnet) gir best resultat. Tips, oppsummeringer og spørsmål bruker AI-en over."));
    api("api/ai/entiteter").then((r) => {
      for (const e of r.entiteter) {
        velg.append(el("option", { value: e.entity_id }, `${e.navn} (${e.entity_id})`));
        velgPlan.append(el("option", { value: e.entity_id }, `${e.navn} (${e.entity_id})`));
      }
      velg.value = S.innstillinger.ai_entitet || "";
      velgPlan.value = S.innstillinger.ai_entitet_plan || "";
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
    const fodt = el("input", { type: "text", inputmode: "numeric", placeholder: "f.eks. 1987", value: d.fodselsaar || "", oninput: (e) => { d.fodselsaar = e.target.value; } });
    const hoyde = el("input", { type: "text", inputmode: "decimal", placeholder: "cm", value: d.hoyde_cm ? tall(d.hoyde_cm) : "", oninput: (e) => { d.hoyde_cm = e.target.value; } });
    const kjonn = el("select", { onchange: () => { d.kjonn = kjonn.value || null; } }, el("option", { value: "" }, "Ikke oppgitt"), el("option", { value: "kvinne" }, "Kvinne"), el("option", { value: "mann" }, "Mann"));
    kjonn.value = d.kjonn || "";
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
        el("div", { class: "felt-rad tre" }, felt("Fødselsår", fodt), felt("Høyde", hoyde), felt("Kjønn", kjonn)),
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
