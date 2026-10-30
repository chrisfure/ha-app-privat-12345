/* Plasterboka – frontend. Ingen rammeverk, alle stier relative til ingress. */
(() => {
  "use strict";

  // ------------------------------------------------------------ hjelpere
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
  const tall = (x, d) => x == null ? "" : (d != null ? Number(x).toFixed(d) : String(+Number(x).toFixed(2))).replace(".", ",");
  const lesTall = (s) => { const x = parseFloat(String(s ?? "").replace(",", ".")); return Number.isFinite(x) ? x : null; };
  const kl = (iso) => new Date(iso).toLocaleTimeString("nb-NO", { hour: "2-digit", minute: "2-digit" });
  const dato = (iso, aar = false) => new Date(iso).toLocaleDateString("nb-NO", { day: "numeric", month: "short", ...(aar ? { year: "numeric" } : {}) }).replace(".", "");
  const lokalDag = (d) => { d = new Date(d); return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`; };
  function dagTittel(iso) {
    const d = lokalDag(iso), i_dag = lokalDag(new Date()), i_gaar = lokalDag(Date.now() - 864e5);
    if (d === i_dag) return "I dag";
    if (d === i_gaar) return "I går";
    return new Date(iso).toLocaleDateString("nb-NO", { weekday: "long", day: "numeric", month: "long" });
  }
  function siden(iso) {
    const m = Math.max(0, Math.round((Date.now() - new Date(iso)) / 6e4));
    if (m < 1) return "akkurat nå";
    if (m < 60) return `for ${m} min siden`;
    const t = Math.floor(m / 60);
    if (t < 24) return `for ${t} t siden`;
    const d = Math.round(t / 24);
    return d === 1 ? "i går" : `for ${d} dager siden`;
  }
  const tilLokalInput = (d) => { d = new Date(d); return `${lokalDag(d)}T${String(d.getHours()).padStart(2, "0")}:${String(d.getMinutes()).padStart(2, "0")}`; };
  const vibrer = () => { try { navigator.vibrate && navigator.vibrate(12); } catch (_) { /* */ } };
  const lagre = (k, v) => { try { localStorage.setItem(`plasterboka-${k}`, JSON.stringify(v)); } catch (_) { /* */ } };
  const hent = (k, std) => { try { const v = JSON.parse(localStorage.getItem(`plasterboka-${k}`)); return v ?? std; } catch (_) { return std; } };

  const DOSEFARGER = ["var(--med)", "var(--oransje)", "var(--blaa)", "var(--gronn)", "var(--rosa)", "var(--gul)"];

  // ------------------------------------------------------------ tilstand
  let data = null;            // api/oversikt
  let inn = null;             // api/innstillinger
  let valgtBarn = hent("barn", null);
  let fane = "hjem";
  let hist = { barn: null, aar: null };
  let instBarn = null;

  // ------------------------------------------------------------ API
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
      e.status = r.status; e.data = j;
      throw e;
    }
    return j;
  }

  async function last() {
    try {
      data = await api("api/oversikt");
    } catch (e) {
      visToast("Får ikke kontakt med Plasterboka");
      return;
    }
    const tall_ = (data.gjennomgang.ukjent || 0) + (data.gjennomgang.sjekk || 0);
    $("fane-tall").hidden = !tall_;
    $("fane-tall").textContent = tall_ > 99 ? "99+" : tall_;
    if (fane === "hjem") tegnHjem();
  }

  async function hentInn() {
    inn = await api("api/innstillinger");
    return inn;
  }

  const barnFarge = (id) => (data?.alle_barn || inn?.barn || []).find((b) => b.id === id)?.farge || "lilla";
  const barnNavn = (id) => (data?.alle_barn || inn?.barn || []).find((b) => b.id === id)?.navn || "Ukjent";
  const avatar = (b, cls = "") => el("span", { class: `avatar ${cls} farge-${b?.farge || "lilla"}` }, (b?.navn || "?").slice(0, 1).toUpperCase());

  // ------------------------------------------------------------ navigasjon
  const VISNINGER = ["hjem", "historikk", "episode", "gjennomgang", "innstillinger"];
  const FANE_FOR = { hjem: "hjem", historikk: "historikk", episode: "historikk", gjennomgang: "innstillinger", innstillinger: "innstillinger" };
  function vis(navn) {
    fane = navn;
    for (const v of VISNINGER) $(`v-${v}`).hidden = v !== navn;
    for (const b of document.querySelectorAll(".faner button")) b.classList.toggle("valgt", b.dataset.fane === FANE_FOR[navn]);
    window.scrollTo({ top: 0 });
  }
  $("faner").addEventListener("click", (e) => {
    const b = e.target.closest("button[data-fane]");
    if (!b) return;
    const f = b.dataset.fane;
    if (f === "hjem") { vis("hjem"); last(); }
    if (f === "historikk") visHistorikk();
    if (f === "innstillinger") visInnstillinger();
  });

  // ------------------------------------------------------------ toast og bekreftelse
  let toastTimer = null;
  function visToast(tekst, knapper = [], ms = 6000) {
    const rot = $("toast-rot");
    rot.innerHTML = "";
    clearTimeout(toastTimer);
    const t = el("div", { class: "toast", role: "status" }, el("span", {}, tekst),
      knapper.length ? el("div", { class: "toast-knapper" }, knapper.map((k) => el("button", { onclick: () => { rot.innerHTML = ""; k.fn(); } }, k.tekst))) : null);
    rot.append(t);
    toastTimer = setTimeout(() => { rot.innerHTML = ""; }, ms);
  }

  let arkLukk = null;
  function aapneArk(innhold, { ved_lukk } = {}) {
    lukkArk();
    const rot = $("ark-rot");
    const bak = el("div", { class: "ark-bakgrunn", onclick: () => lukkArk() });
    const ark = el("div", { class: "ark", role: "dialog", "aria-modal": "true" }, el("div", { class: "ark-handtak" }), innhold);
    rot.append(bak, ark);
    document.body.style.overflow = "hidden";
    arkLukk = ved_lukk || null;
    return ark;
  }
  function lukkArk() {
    $("ark-rot").innerHTML = "";
    document.body.style.overflow = "";
    if (arkLukk) { const f = arkLukk; arkLukk = null; f(); }
  }
  document.addEventListener("keydown", (e) => { if (e.key === "Escape") lukkArk(); });

  function bekreft(tittel, tekst, knappTekst = "OK", fare = false) {
    return new Promise((ok) => {
      let svar = false;
      aapneArk(el("div", {},
        el("h3", {}, tittel),
        Array.isArray(tekst) ? el("div", { class: "advarsler" }, tekst.map((t) => el("div", { class: "vurdering" }, ikon("advarsel"), el("span", {}, t))))
          : el("p", { class: "hint" }, tekst),
        el("div", { class: "ark-knapper" },
          el("button", { class: "knapp noytral", onclick: () => lukkArk() }, "Avbryt"),
          el("button", { class: `knapp ${fare ? "fare" : ""}`, style: fare ? "flex:1" : "--aksent:var(--med)", onclick: () => { svar = true; lukkArk(); } }, knappTekst))
      ), { ved_lukk: () => ok(svar) });
    });
  }

  // ================================================================ HJEM
  function statusFor(id) {
    if (!data || !data.barn.length) return null;
    return data.barn.find((s) => s.barn.id === id) || data.barn[0];
  }

  function tegnHjem() {
    if (!data) return;
    const ingenBarn = !data.alle_barn.length;
    $("velkommen").hidden = !ingenBarn;
    const g = data.gjennomgang;
    const antall = (g.ukjent || 0) + (g.sjekk || 0);
    const banner = $("gjennomgang-banner");
    banner.hidden = !antall;
    banner.replaceChildren(ikon("advarsel"), el("span", {}, `${antall} importerte registreringer venter på gjennomgang`), ikon("hoyre"));

    const st = statusFor(valgtBarn);
    for (const id of ["helt", "fliser", "doser"]) $(id).hidden = !st;
    $("legg-til-tidligere").closest(".kort").hidden = !st;
    $("undertittel").textContent = data.barn.filter((s) => s.syk).length
      ? `${data.barn.filter((s) => s.syk).map((s) => s.barn.navn).join(" og ")} er syk${data.barn.filter((s) => s.syk).length > 1 ? "e" : ""}`
      : (data.barn.length ? "Alle er friske" : "");
    if (!st) { $("barnvelger").replaceChildren(); $("merknad").replaceChildren(); return; }
    valgtBarn = st.barn.id;

    // barnvelger
    $("barnvelger").replaceChildren(...data.barn.map((s) => {
      const a = avatar(s.barn);
      if (s.syk) a.append(el("span", { class: "syk-prikk" }));
      return el("button", {
        class: `barn-chip farge-${s.barn.farge} ${s.barn.id === valgtBarn ? "valgt" : ""}`, role: "tab",
        onclick: () => { valgtBarn = s.barn.id; lagre("barn", valgtBarn); tegnHjem(); },
      }, a, s.barn.navn);
    }));
    if (data.barn.length < 2) $("barnvelger").replaceChildren();

    // helt
    const helt = $("helt");
    const ufodt = st.alder?.ufodt;
    helt.dataset.tilstand = st.syk ? "syk" : (st.siste_temp || !ufodt ? "frisk" : "tom");
    $("helt-merke").textContent = (data.barn.length < 2 ? `${st.barn.navn} · ` : "") +
      (st.syk ? `Syk · dag ${st.episode.dag}` : ufodt ? st.alder.tekst : "Frisk");
    const tid = $("helt-tid");
    tid.classList.toggle("feber", !!st.siste_temp?.feber);
    if (st.siste_temp && (st.syk || Date.now() - new Date(st.siste_temp.tid) < 3 * 864e5)) {
      tid.innerHTML = `${tall(st.siste_temp.temp, 1)}<small> °C</small>`;
      $("helt-under").textContent = [`Målt kl. ${st.siste_temp.kl}`, st.siste_temp.metode ? `i ${st.siste_temp.metode}` : null].filter(Boolean).join(" ") + ` · ${siden(st.siste_temp.tid)}`;
    } else {
      tid.textContent = st.syk ? "Syk" : "Frisk";
      $("helt-under").textContent = st.syk && st.siste ? `Siste registrering ${siden(st.siste.tid)}` : st.siste_temp ? `Siste måling ${dato(st.siste_temp.tid)}` : "";
    }
    const maks = st.episode?.maks_temp && (!st.siste_temp || st.episode.maks_temp > st.siste_temp.temp)
      ? [el("span", { class: "merkelapp temp" }, `Høyeste ${tall(st.episode.maks_temp, 1)} °C`)] : [];
    $("helt-symptomer").replaceChildren(...maks, ...st.symptomer.map((s) => el("span", { class: "merkelapp" }, s)));
    const knapper = [el("button", { class: "knapp", onclick: () => aapneRegistrering({ barnId: valgtBarn }) }, ikon("pluss"), "Registrer")];
    if (st.syk) knapper.push(el("button", { class: "knapp sekundaer", onclick: () => frisk(st) }, ikon("sol"), "Frisk igjen"));
    $("helt-knapper").replaceChildren(...knapper);

    $("merknad").replaceChildren(...(st.merknad ? [el("div", { class: "vurdering" }, ikon("info"),
      el("span", {}, st.merknad.tekst, " ", el("a", { href: st.merknad.lenke, target: "_blank", rel: "noopener" }, "Les mer")))] : []));

    // fliser
    $("sist-temp").textContent = st.siste_temp ? `${tall(st.siste_temp.temp, 1)} °C kl. ${st.siste_temp.kl}` : "";
    const sisteDose = st.doser.filter((d) => d.siste).sort((a, b) => b.siste.tid.localeCompare(a.siste.tid))[0];
    $("sist-med").textContent = sisteDose ? `${sisteDose.siste.legemiddel || sisteDose.navn} kl. ${sisteDose.siste.kl}` : "";
    $("sist-symp").textContent = st.symptomer.length ? `${st.symptomer.length} siste døgn` : "";
    $("sist-notat").textContent = "";

    tegnDoser(st);
    tegnLogg(st);
  }

  function tegnDoser(st) {
    $("doser").replaceChildren(...st.doser.map((d) => {
      const std = d.standard_mg;
      const venter = !!d.neste_kl;
      const giTekst = std ? (d.mg_per_ml ? `${tall(std / d.mg_per_ml, 1)} ml` : `${tall(std)} mg`) : "Gi";
      const under = d.siste
        ? `Sist kl. ${d.siste.kl}${lokalDag(d.siste.tid) !== lokalDag(new Date()) ? ` ${dato(d.siste.tid)}` : ""} · ${tall(d.siste.mg)} mg${d.siste.legemiddel && d.siste.legemiddel !== d.navn ? ` (${d.siste.legemiddel})` : ""}`
        : "Ikke gitt den siste tiden";
      const deler = [
        el("div", { class: "dose-topp" },
          el("span", { class: "dose-ikon" }, ikon("pille")),
          el("div", { class: "dose-tekst" }, el("div", { class: "dose-navn" }, d.navn), el("div", { class: "dose-under" }, under)),
          el("button", { class: `dose-gi ${venter ? "vent" : ""}`, onclick: () => giDose(st, d) }, ikon("pluss"), giTekst)),
      ];
      if (venter) deler.push(el("div", { class: "dose-status vent" }, ikon("klokke"), `Neste tidligst kl. ${d.neste_kl}`));
      else if (d.siste && d.min_intervall_t) deler.push(el("div", { class: "dose-status ok" }, ikon("sjekk"), "Kan gis nå"));
      if (d.maks_dogn_mg) {
        const pst = Math.min(100, (d.sum_24t / d.maks_dogn_mg) * 100);
        deler.push(el("div", { class: "bar" }, el("div", { class: `bar-fyll ${pst >= 85 ? "hoy" : ""}`, style: `width:${pst}%` })));
        deler.push(el("div", { class: "bar-akse" },
          el("span", {}, "Siste 24 t: ", el("b", {}, `${tall(d.sum_24t)} mg`), d.virkestoff.toLowerCase() !== d.navn.toLowerCase() ? ` ${d.virkestoff.toLowerCase()}` : ""),
          el("span", {}, `maks ${tall(d.maks_dogn_mg)} mg`)));
      } else if (d.sum_24t) {
        deler.push(el("div", { class: "bar-akse" }, el("span", {}, "Siste 24 t: ", el("b", {}, `${tall(d.sum_24t)} mg`), ` · i dag ${tall(d.sum_i_dag)} mg`)));
      }
      if (d.kur) {
        const prikker = el("span", { class: "kur-prikker" });
        for (let i = 0; i < d.kur.doser_dag; i++) prikker.append(el("span", { class: i < d.kur.gitt_i_dag ? "gitt" : "" }));
        deler.push(el("div", { class: "kur" }, prikker,
          `Dose ${Math.min(d.kur.gitt_i_dag, d.kur.doser_dag)} av ${d.kur.doser_dag} i dag`,
          d.kur.til ? ` · kuren varer til ${dato(d.kur.til + "T12:00")}` : ""));
      }
      return el("div", { class: "dose-kort" }, deler);
    }));
  }

  function radIkon(r) {
    if (r.legemiddel_id) return ["med", "pille"];
    if (r.temp != null) return ["temp", "termometer"];
    if (r.symptomer?.length) return ["symp", "symptom"];
    return ["notat", "notat"];
  }

  function logRad(r, { visBarn = false, visDato = false } = {}) {
    const [k, i] = radIkon(r);
    const tittel = el("div", { class: "rad-tittel" });
    if (r.temp != null) {
      tittel.append(el("span", { class: r.feber ? "feber" : "" }, `${tall(r.temp, 1)} °C`));
      if (r.legemiddel_id || r.symptomer?.length) tittel.append(" · ");
    }
    const resten = [];
    if (r.legemiddel_id) resten.push(`${r.legemiddel} ${r.dose_ml ? `${tall(r.dose_ml)} ml` : `${tall(r.dose_mg)} mg`}`);
    if (r.symptomer?.length) resten.push(r.symptomer.join(", "));
    if (resten.length) tittel.append(resten.join(" · "));
    if (!tittel.textContent) tittel.textContent = "Notat";
    const under = [r.notat, r.temp != null && r.metode_navn ? `målt i ${r.metode_navn}` : null, visBarn ? barnNavn(r.barn_id) : null,
      r.status === "antatt" ? "antatt barn (import)" : null, r.merknad].filter(Boolean).join(" · ");
    return el("li", {}, el("button", { class: "rad", onclick: () => aapneRegistrering({ rad: r }) },
      el("span", { class: `rad-ikon k-${k}` }, ikon(i)),
      el("span", { class: "rad-tekst" }, tittel, under ? el("div", { class: "rad-under" }, under) : null),
      r.status === "sjekk" ? (() => { const i = ikon("advarsel"); i.classList.add("rad-merke"); return i; })() : null,
      el("span", { class: "rad-tid" }, visDato ? `${dato(r.tid)} ${r.kl}` : r.kl)));
  }

  function tegnLogg(st) {
    const ul = $("logg");
    ul.replaceChildren();
    if (!st.i_dag.length) { ul.append(el("li", { class: "tom" }, "Ingen registreringer siste døgn")); return; }
    let dag = null;
    for (const r of st.i_dag) {
      const d = lokalDag(r.tid);
      if (d !== dag) { dag = d; ul.append(el("li", { class: "dagskille" }, dagTittel(r.tid))); }
      ul.append(logRad(r));
    }
  }

  $("legg-til-tidligere").addEventListener("click", () => aapneRegistrering({ barnId: valgtBarn, tidligere: true }));
  $("fliser").addEventListener("click", (e) => {
    const f = e.target.closest(".flis");
    if (f) aapneRegistrering({ barnId: valgtBarn, seksjon: f.dataset.seksjon });
  });
  $("velkommen").addEventListener("click", () => visInnstillinger());
  $("gjennomgang-banner").addEventListener("click", () => visGjennomgang());

  async function frisk(st) {
    try {
      await api(`api/barn/${st.barn.id}/frisk`, { method: "POST" });
      visToast(`${st.barn.navn} er registrert frisk igjen 🎉`);
      last();
    } catch (e) { visToast(e.message); }
  }

  async function giDose(st, d) {
    if (!d.standard_mg) { aapneRegistrering({ barnId: st.barn.id, seksjon: "med", legemiddelId: d.legemiddel_id }); return; }
    vibrer();
    await lagreRegistrering({ barn_id: st.barn.id, legemiddel_id: d.legemiddel_id, dose_mg: d.standard_mg });
  }

  /** Lagre ny registrering. Ved advarsel spørres brukeren først. */
  async function lagreRegistrering(body) {
    try {
      const { registrering: r } = await api("api/registreringer", { method: "POST", body });
      visToast(`Registrert: ${r.tittel}`, [
        { tekst: "Angre", fn: async () => { await api(`api/registreringer/${r.id}`, { method: "DELETE" }).catch(() => {}); last(); } },
        { tekst: "Endre", fn: () => aapneRegistrering({ rad: r }) },
      ]);
      await last();
      return r;
    } catch (e) {
      if (e.status === 409 && e.data?.advarsler) {
        const ok = await bekreft("Er du sikker?", e.data.advarsler, "Lagre likevel");
        if (ok) return lagreRegistrering({ ...body, bekreftet: true });
        return null;
      }
      visToast(e.message);
      return null;
    }
  }

  // ================================================================ REGISTRERINGSARK
  function aapneRegistrering({ barnId = null, seksjon = null, rad = null, tidligere = false, legemiddelId = null } = {}) {
    const endre = !!rad;
    const bid = rad ? rad.barn_id : barnId;
    const st = data?.barn.find((s) => s.barn.id === bid);
    const inst = data?.innstillinger || {};
    const s = {
      barn_id: bid,
      tidModus: endre || tidligere ? "egen" : "naa",
      tid: endre ? new Date(rad.tid) : new Date(Date.now() - (tidligere ? 30 * 6e4 : 0)),
      temp: { paa: endre ? rad.temp != null : seksjon === "temp", verdi: rad?.temp ?? st?.siste_temp?.temp ?? 38.0,
              metode: rad?.temp_metode && rad.temp_metode !== "notat" ? rad.temp_metode : (inst.standard_metode || "ore") },
      med: { paa: endre ? !!rad.legemiddel_id : seksjon === "med", lid: rad?.legemiddel_id ?? legemiddelId, mg: rad?.dose_mg ?? null, ml: rad?.dose_ml ?? null, enhet: rad?.dose_ml ? "ml" : null },
      symp: { paa: endre ? !!rad.symptomer?.length : seksjon === "symp", valgt: new Set(rad?.symptomer || []) },
      notat: { paa: endre ? !!rad.notat : seksjon === "notat", tekst: rad?.notat || "" },
      advarsler: [], bekreftet: false,
    };
    if (!endre && !seksjon) { s.temp.paa = true; }
    if (s.temp.verdi < 35) s.temp.verdi = 38.0;
    if (!st && !endre) return;

    // Legemidler som kan velges: aktive for barnet + det som allerede er registrert
    const doseinfo = Object.fromEntries((st?.doser || []).map((d) => [d.legemiddel_id, d]));
    const valgbare = (st?.doser || []).map((d) => ({ id: d.legemiddel_id, navn: d.navn, mg_per_ml: d.mg_per_ml, standard_mg: d.standard_mg, form: d.form }));
    if (rad?.legemiddel_id && !doseinfo[rad.legemiddel_id]) {
      const l = data.legemidler.find((x) => x.id === rad.legemiddel_id);
      if (l) valgbare.push({ id: l.id, navn: l.navn, mg_per_ml: l.mg_per_ml, form: l.form });
    }
    function velgLm(id) {
      s.med.lid = id;
      const l = valgbare.find((x) => x.id === id);
      if (!l) return;
      s.med.enhet = l.mg_per_ml ? "ml" : "mg";
      if (!endre || rad.legemiddel_id !== id) {
        s.med.mg = l.standard_mg ?? null;
        s.med.ml = l.mg_per_ml && l.standard_mg ? +(l.standard_mg / l.mg_per_ml).toFixed(1) : null;
      }
    }
    if (s.med.lid && !endre) velgLm(s.med.lid);
    if (!s.med.lid && valgbare.length === 1) velgLm(valgbare[0].id);
    if (s.med.lid && !s.med.enhet) s.med.enhet = valgbare.find((x) => x.id === s.med.lid)?.mg_per_ml ? "ml" : "mg";

    const symptomListe = [...new Set([...(inst.symptomer || []), ...s.symp.valgt])];
    const barn = data.alle_barn.find((b) => b.id === bid);
    let ark;

    function del(navn, k, ikonNavn, tittel, oppsummering, kropp) {
      const d = el("div", { class: `del k-${k} flis-${k} ${s[navn].paa ? "aapen" : ""}` },
        el("button", { class: "del-hode", type: "button", onclick: () => { s[navn].paa = !s[navn].paa; tegn(); } },
          el("span", { class: `rad-ikon k-${k}` }, ikon(ikonNavn)), tittel,
          el("span", { class: "del-oppsummering" }, s[navn].paa ? oppsummering : "Legg til"),
          s[navn].paa ? ikon("kryss") : ikon("pluss")),
        el("div", { class: "del-kropp" }, s[navn].paa ? kropp() : null));
      return d;
    }

    function tidDel() {
      if (s.tidModus === "naa" && !endre) {
        const valg = [["naa", "Nå"], [15, "15 min siden"], [30, "30 min"], [60, "1 t"], ["egen", "Velg tid"]];
        return el("div", { class: "tid-del" }, el("div", { class: "chips" }, valg.map(([v, t]) =>
          el("button", { type: "button", class: `chip ${v === "naa" ? "valgt" : ""}`, style: "--aksent:var(--blekk)",
            onclick: () => { if (v === "egen") { s.tidModus = "egen"; } else if (v !== "naa") { s.tidModus = "egen"; s.tid = new Date(Date.now() - v * 6e4); } tegn(); } }, t))));
      }
      return el("div", { class: "tid-del" }, el("label", { class: "felt" }, el("span", {}, "Tidspunkt"),
        el("input", { type: "datetime-local", value: tilLokalInput(s.tid), max: tilLokalInput(new Date()),
          onchange: (e) => { if (e.target.value) s.tid = new Date(e.target.value); } })));
    }

    function tempKropp() {
      const verdi = el("div", { class: `verdi ${s.temp.verdi >= (inst.feber_grense || 38) ? "feber" : ""}` });
      const oppdater = () => { verdi.innerHTML = `${tall(s.temp.verdi, 1)}<small> °C</small>`; verdi.classList.toggle("feber", s.temp.verdi >= (inst.feber_grense || 38)); ark.querySelector(".k-temp .del-oppsummering").textContent = `${tall(s.temp.verdi, 1)} °C`; };
      const steg = (d) => { s.temp.verdi = Math.min(43, Math.max(34, Math.round((s.temp.verdi + d) * 10) / 10)); oppdater(); vibrer(); };
      setTimeout(oppdater);
      return [
        el("div", { class: "stepper" }, el("button", { type: "button", onclick: () => steg(-0.1), "aria-label": "Ned" }, "−"), verdi,
          el("button", { type: "button", onclick: () => steg(0.1), "aria-label": "Opp" }, "+")),
        el("div", { class: "chips jevn" }, [37, 37.5, 38, 38.5, 39, 39.5, 40].map((v) =>
          el("button", { type: "button", class: "chip", onclick: () => { s.temp.verdi = v; oppdater(); } }, tall(v, 1)))),
        el("div", { class: "segment" }, (inn?.metoder || [{ id: "ore", navn: "øre" }, { id: "munn", navn: "munn" }, { id: "panne", navn: "panne" }, { id: "endetarm", navn: "endetarm" }, { id: "arm", navn: "armhule" }]).map((m) =>
          el("button", { type: "button", class: s.temp.metode === m.id ? "valgt" : "", onclick: () => { s.temp.metode = m.id; tegn(); } }, m.navn))),
      ];
    }

    function medKropp() {
      if (!valgbare.length) {
        return [el("p", { class: "forklaring" }, `Ingen legemidler er slått på for ${barn?.navn || "barnet"}. Legg dem til under Innstillinger → Legemidler.`)];
      }
      const ut = [el("div", { class: "chips" }, valgbare.map((l) =>
        el("button", { type: "button", class: `chip ${s.med.lid === l.id ? "valgt" : ""}`, onclick: () => { velgLm(l.id); tegn(); } }, l.navn)))];
      const l = valgbare.find((x) => x.id === s.med.lid);
      if (!l) return ut;
      const mgFelt = el("input", { type: "text", inputmode: "decimal", value: tall(s.med.enhet === "ml" ? s.med.ml : s.med.mg),
        oninput: (e) => {
          const v = lesTall(e.target.value);
          if (s.med.enhet === "ml") { s.med.ml = v; s.med.mg = v != null && l.mg_per_ml ? +(v * l.mg_per_ml).toFixed(2) : null; }
          else { s.med.mg = v; s.med.ml = null; }
          regnInfo();
        } });
      if (l.mg_per_ml) {
        ut.push(el("div", { class: "segment" }, ["ml", "mg"].map((e) => el("button", { type: "button", class: s.med.enhet === e ? "valgt" : "",
          onclick: () => { s.med.enhet = e; if (e === "mg") s.med.ml = null; else s.med.ml = s.med.mg != null ? +(s.med.mg / l.mg_per_ml).toFixed(1) : null; tegn(); } }, `Dose i ${e}`))));
      }
      ut.push(el("label", { class: "felt" }, el("span", {}, "Dose"), el("div", { class: "felt-wrap" }, mgFelt, el("span", { class: "enhet" }, s.med.enhet === "ml" ? "ml" : "mg"))));
      const info = el("div", { class: "dose-info" });
      function regnInfo() {
        const d = doseinfo[l.id];
        const linjer = [];
        if (s.med.enhet === "ml" && s.med.mg != null) linjer.push(el("div", {}, "= ", el("b", {}, `${tall(s.med.mg)} mg`), ` (${tall(l.mg_per_ml)} mg/ml)`));
        if (d?.siste) linjer.push(el("div", {}, `Sist gitt kl. ${d.siste.kl} ${lokalDag(d.siste.tid) !== lokalDag(new Date()) ? dato(d.siste.tid) : ""} – ${tall(d.siste.mg)} mg`));
        if (d) {
          const sum = `${tall(d.sum_24t)} mg${d.maks_dogn_mg ? ` av maks ${tall(d.maks_dogn_mg)} mg` : ""}`;
          linjer.push(el("div", {}, `Siste 24 t: ${sum}`));
          if (d.neste_kl && !endre) linjer.push(el("div", {}, el("b", {}, `Neste tidligst kl. ${d.neste_kl}`)));
        }
        info.replaceChildren(...linjer);
        const o = ark?.querySelector(".k-med .del-oppsummering");
        if (o) o.textContent = s.med.mg != null ? `${l.navn} ${tall(s.med.enhet === "ml" ? s.med.ml : s.med.mg)} ${s.med.enhet}` : l.navn;
      }
      regnInfo();
      ut.push(info);
      return ut;
    }

    function sympKropp() {
      return [el("div", { class: "chips" }, symptomListe.map((n) =>
        el("button", { type: "button", class: `chip ${s.symp.valgt.has(n) ? "valgt" : ""}`, onclick: (e) => {
          s.symp.valgt.has(n) ? s.symp.valgt.delete(n) : s.symp.valgt.add(n);
          e.currentTarget.classList.toggle("valgt"); vibrer();
          ark.querySelector(".k-symp .del-oppsummering").textContent = s.symp.valgt.size ? [...s.symp.valgt].join(", ") : "Velg";
        } }, n)))];
    }

    function notatKropp() {
      const t = el("textarea", { placeholder: "Hvordan er formen? F.eks. slapp, sover urolig, drikker godt …", maxlength: 1000,
        oninput: (e) => { s.notat.tekst = e.target.value; } });
      t.value = s.notat.tekst;
      return [el("label", { class: "felt" }, t)];
    }

    function tegn() {
      const scroll = ark ? ark.scrollTop : 0;
      const l = valgbare.find((x) => x.id === s.med.lid);
      const innhold = el("div", {},
        el("h3", {}, barn ? avatar(barn, "liten") : null, endre ? "Endre registrering" : `Registrer for ${barn?.navn || ""}`),
        endre && rad.status === "sjekk" && rad.merknad ? el("div", { class: "vurdering obs" }, ikon("advarsel"), el("span", {}, rad.merknad)) : null,
        endre && rad.barn_id == null ? el("p", { class: "hint" }, "Ukjent barn – tildel under Gjennomgang.") : null,
        tidDel(),
        del("temp", "temp", "termometer", "Temperatur", `${tall(s.temp.verdi, 1)} °C`, tempKropp),
        del("med", "med", "pille", "Medisin", l ? `${l.navn}${s.med.mg != null ? ` ${tall(s.med.enhet === "ml" ? s.med.ml : s.med.mg)} ${s.med.enhet}` : ""}` : "Velg", medKropp),
        del("symp", "symp", "symptom", "Symptomer", s.symp.valgt.size ? [...s.symp.valgt].join(", ") : "Velg", sympKropp),
        del("notat", "notat", "notat", "Notat", s.notat.tekst ? s.notat.tekst.slice(0, 40) : "Skriv", notatKropp),
        el("div", { class: "advarsler" }, s.advarsler.map((a) => el("div", { class: "vurdering" }, ikon("advarsel"), el("span", {}, a)))),
        el("div", { class: "ark-knapper" },
          endre ? el("button", { class: "knapp fare", onclick: slett }, "Slett") : null,
          endre && rad.status === "sjekk" ? el("button", { class: "knapp sekundaer", style: "--aksent-lys:var(--frisk-lys);--aksent-blekk:var(--frisk-blekk)", onclick: () => send(true) }, "Behold") : null,
          el("button", { class: "knapp", style: "--aksent:var(--temp)", onclick: () => send(false) }, s.advarsler.length ? "Lagre likevel" : "Lagre")));
      if (!ark) ark = aapneArk(innhold); else { ark.replaceChildren(el("div", { class: "ark-handtak" }), innhold); ark.scrollTop = scroll; }
    }

    async function send(godkjenn) {
      const body = { barn_id: s.barn_id };
      if (s.tidModus === "egen") body.tid = s.tid.toISOString();
      if (s.temp.paa) { body.temp = s.temp.verdi; body.temp_metode = s.temp.metode; } else if (endre) body.temp = null;
      if (s.med.paa && s.med.lid) {
        if (s.med.mg == null) { visToast("Skriv inn dose"); return; }
        body.legemiddel_id = s.med.lid;
        if (s.med.enhet === "ml" && s.med.ml != null) body.dose_ml = s.med.ml; else body.dose_mg = s.med.mg;
      } else if (endre) body.legemiddel_id = null;
      if (s.symp.paa) body.symptomer = [...s.symp.valgt]; else if (endre) body.symptomer = [];
      if (s.notat.paa) body.notat = s.notat.tekst; else if (endre) body.notat = "";
      if (s.bekreftet) body.bekreftet = true;
      if (godkjenn) body.godkjenn = true;
      if (endre && rad.barn_id == null) delete body.barn_id;
      try {
        let r;
        if (endre) {
          r = (await api(`api/registreringer/${rad.id}`, { method: "PATCH", body })).registrering;
          lukkArk();
          visToast("Endringen er lagret");
        } else {
          r = (await api("api/registreringer", { method: "POST", body })).registrering;
          lukkArk();
          visToast(`Registrert: ${r.tittel}`, [
            { tekst: "Angre", fn: async () => { await api(`api/registreringer/${r.id}`, { method: "DELETE" }).catch(() => {}); oppfrisk(); } },
            { tekst: "Endre", fn: () => aapneRegistrering({ rad: r }) },
          ]);
        }
        vibrer();
        oppfrisk();
      } catch (e) {
        if (e.status === 409 && e.data?.advarsler) {
          s.advarsler = e.data.advarsler; s.bekreftet = true; tegn();
          ark.scrollTop = ark.scrollHeight;
          return;
        }
        visToast(e.message);
      }
    }

    async function slett() {
      try {
        const { slettet } = await api(`api/registreringer/${rad.id}`, { method: "DELETE" });
        lukkArk();
        visToast("Registreringen er slettet", [{ tekst: "Angre", fn: async () => { await api("api/registreringer/gjenopprett", { method: "POST", body: slettet }); oppfrisk(); } }]);
        oppfrisk();
      } catch (e) { visToast(e.message); }
    }

    tegn();
  }

  /** Oppdater det som vises nå. */
  async function oppfrisk() {
    await last();
    if (fane === "historikk") visHistorikk(true);
    if (fane === "episode" && aktivEpisode) visEpisode(aktivEpisode, true);
    if (fane === "gjennomgang") visGjennomgang(true);
  }

  // ================================================================ HISTORIKK
  function episodeTittel(e) {
    if (e.navn) return e.navn;
    const grense = data?.innstillinger?.feber_grense || 38;
    const type = e.maks_temp != null && e.maks_temp >= grense ? "Feber" : e.doser.length ? "Medisin" : "Syk";
    const fra = new Date(e.start_dato + "T12:00"), til = new Date(e.slutt_dato + "T12:00");
    const periode = e.start_dato === e.slutt_dato ? dato(fra) : fra.getMonth() === til.getMonth()
      ? `${fra.getDate()}.–${dato(til)}` : `${dato(fra)} – ${dato(til)}`;
    return `${type} ${periode}`;
  }

  function episodeKort(e, visAvatar) {
    const b = (data?.alle_barn || []).find((x) => x.id === e.barn_id);
    const merker = [];
    if (e.pagar) merker.push(el("span", { class: "merkelapp temp" }, "Pågår"));
    if (e.maks_temp != null) merker.push(el("span", { class: "merkelapp temp" }, ikon("termometer"), `maks ${tall(e.maks_temp, 1)} °C`));
    for (const d of e.doser.slice(0, 3)) merker.push(el("span", { class: "merkelapp med" }, `${d.navn} ×${d.antall}`));
    for (const s of e.symptomer.slice(0, 3)) merker.push(el("span", { class: "merkelapp" }, s));
    if (e.usikker) merker.push(el("span", { class: "merkelapp gra" }, `${e.usikker} usikre`));
    const under = [`${e.dager} ${e.dager === 1 ? "dag" : "dager"}`, e.feberdager ? `${e.feberdager} med feber` : null, `${e.antall} registreringer`].filter(Boolean).join(" · ");
    return el("button", { class: `episode-kort farge-${b?.farge || "lilla"}`, onclick: () => visEpisode(e.id) },
      visAvatar ? avatar(b) : null,
      el("div", { class: "episode-tekst" }, el("div", { class: "episode-tittel" }, episodeTittel(e)), el("div", { class: "episode-under" }, under),
        merker.length ? el("div", { class: "episode-merker" }, merker) : null),
      ikon("hoyre"));
  }

  async function visHistorikk(stille = false) {
    if (!stille) vis("historikk");
    if (!data) await last();
    const q = new URLSearchParams();
    if (hist.barn) q.set("barn", hist.barn);
    if (hist.aar) q.set("aar", hist.aar);
    let h;
    try { h = await api(`api/historikk?${q}`); } catch (e) { visToast(e.message); return; }
    const alle = data.alle_barn;
    $("hist-barn").replaceChildren(...(alle.length > 1 ? [
      el("button", { class: `chip ${!hist.barn ? "valgt" : ""}`, style: "--aksent:var(--blekk)", onclick: () => { hist.barn = null; visHistorikk(true); } }, "Alle"),
      ...alle.map((b) => el("button", { class: `chip farge-${b.farge} ${hist.barn === b.id ? "valgt" : ""}`, style: "--aksent:var(--b)",
        onclick: () => { hist.barn = b.id; hist.aar = null; visHistorikk(true); } }, avatar(b), b.navn)),
    ] : []));
    $("hist-aar").replaceChildren(...(h.aar.length > 1 ? [
      el("button", { class: `chip ${!hist.aar ? "valgt" : ""}`, style: "--aksent:var(--blekk)", onclick: () => { hist.aar = null; visHistorikk(true); } }, "Alle år"),
      ...h.aar.map((a) => el("button", { class: `chip ${hist.aar === a ? "valgt" : ""}`, style: "--aksent:var(--blekk)", onclick: () => { hist.aar = a; visHistorikk(true); } }, String(a))),
    ] : []));
    const liste = $("episoder");
    liste.replaceChildren();
    if (!h.episoder.length) {
      liste.append(el("div", { class: "kort" }, el("p", { class: "tom" }, "Ingen sykdomsepisoder ennå. De dukker opp her så snart dere registrerer noe – eller importerer fra kalenderne under Innstillinger.")));
      return;
    }
    let aar = null;
    for (const e of h.episoder) {
      const a = e.start_dato.slice(0, 4);
      if (a !== aar) { aar = a; liste.append(el("div", { class: "aar-skille" }, a)); }
      liste.append(episodeKort(e, !hist.barn && alle.length > 1));
    }
    liste.append(el("a", { class: "legg-til", href: "api/eksport.csv", download: "plasterboka.csv" }, ikon("last-ned"), "Last ned alt som CSV"));
  }

  // ---- episode ----
  let aktivEpisode = null;
  async function visEpisode(id, stille = false) {
    aktivEpisode = id;
    let d;
    try { d = await api(`api/episoder/${id}`); } catch (e) { visToast(e.message); return; }
    if (!stille) vis("episode");
    const e = d.episode, b = d.barn, regs = d.registreringer;
    const v = $("v-episode");
    const totalDoser = e.doser.reduce((s, x) => s + x.antall, 0);
    v.replaceChildren(...[
      el("button", { class: "tilbake", onclick: () => visHistorikk() }, ikon("venstre"), "Historikk"),
      el("div", { class: `ep-hode farge-${b.farge}` }, avatar(b, "stor"),
        el("div", { class: "tekst" }, el("h2", {}, episodeTittel(e)),
          el("p", {}, `${b.navn} · ${dato(e.start, true)}${e.start_dato !== e.slutt_dato ? ` – ${dato(e.slutt, true)}` : ""} · ${e.dager} ${e.dager === 1 ? "dag" : "dager"}`)),
        el("button", { class: "ikonknapp ikke-utskrift", onclick: () => redigerEpisode(e), "aria-label": "Gi navn" }, ikon("blyant"))),
      el("div", { class: "nokkeltall" },
        el("div", { class: "tall-boks t-temp" }, el("span", { class: "tall-verdi" }, e.maks_temp != null ? `${tall(e.maks_temp, 1)} °C` : "–"), el("span", { class: "tall-navn" }, "Høyeste temp")),
        el("div", { class: "tall-boks t-temp" }, el("span", { class: "tall-verdi" }, String(e.feberdager)), el("span", { class: "tall-navn" }, "Dager med feber")),
        el("div", { class: "tall-boks t-med" }, el("span", { class: "tall-verdi" }, String(totalDoser)), el("span", { class: "tall-navn" }, "Doser gitt"))),
      e.notat ? el("div", { class: "vurdering info" }, ikon("notat"), el("span", {}, e.notat)) : null,
      e.usikker ? el("div", { class: "vurdering obs" }, ikon("advarsel"), el("span", {}, `${e.usikker} registreringer er importert med antatt barn eller bør sjekkes.`)) : null,
      el("section", { class: "kort" }, el("div", { class: "kort-hode" }, el("h2", {}, "Temperatur og doser")), graf(regs, d.feber_grense)),
      el("section", { class: "kort" }, el("div", { class: "kort-hode" }, el("h2", {}, "Per dag")), dagtabell(regs, d.feber_grense)),
      el("section", { class: "kort" }, el("div", { class: "kort-hode" }, el("h2", {}, "Alle registreringer")), episodeLogg(regs)),
      el("div", { class: "helt-knapper ikke-utskrift" },
        el("button", { class: "knapp noytral", onclick: () => window.print() }, ikon("skriver"), "Skriv ut / PDF"),
        e.pagar ? null : el("button", { class: "knapp noytral", onclick: () => redigerEpisode(e) }, ikon("blyant"), "Navn og notat")),
    ].filter(Boolean));
  }

  function redigerEpisode(e) {
    const navn = el("input", { type: "text", maxlength: 60, placeholder: "F.eks. Halsbetennelse", value: e.navn || "" });
    const notat = el("textarea", { maxlength: 2000, placeholder: "Diagnose, legebesøk, prøvesvar …" });
    notat.value = e.notat || "";
    aapneArk(el("div", {},
      el("h3", {}, "Navn og notat"),
      el("p", { class: "hint" }, "Gjør det lettere å finne igjen sykdommen senere."),
      el("div", { class: "skjema" }, el("label", { class: "felt" }, el("span", {}, "Navn"), navn), el("label", { class: "felt" }, el("span", {}, "Notat"), notat)),
      el("div", { class: "ark-knapper" }, el("button", { class: "knapp", style: "--aksent:var(--temp)", onclick: async () => {
        try { await api(`api/episoder/${e.id}`, { method: "PATCH", body: { navn: navn.value, notat: notat.value } }); lukkArk(); visEpisode(e.id, true); }
        catch (x) { visToast(x.message); }
      } }, "Lagre"))));
  }

  function episodeLogg(regs) {
    const ul = el("ul", { class: "logg" });
    let dag = null;
    for (const r of regs) {
      const dd = lokalDag(r.tid);
      if (dd !== dag) { dag = dd; ul.append(el("li", { class: "dagskille" }, dagTittel(r.tid))); }
      ul.append(logRad(r));
    }
    return ul;
  }

  function dagtabell(regs, grense) {
    const lm = [...new Set(regs.filter((r) => r.legemiddel).map((r) => r.legemiddel))];
    const dager = new Map();
    for (const r of regs) {
      const k = lokalDag(r.tid);
      if (!dager.has(k)) dager.set(k, { maks: null, lm: {}, symp: new Set(), tid: r.tid });
      const d = dager.get(k);
      if (r.temp != null) d.maks = d.maks == null ? r.temp : Math.max(d.maks, r.temp);
      if (r.legemiddel) { const x = d.lm[r.legemiddel] || (d.lm[r.legemiddel] = { n: 0, mg: 0 }); x.n++; x.mg += r.dose_mg || 0; }
      r.symptomer.forEach((s) => d.symp.add(s));
    }
    const t = el("table", { class: "dagtabell" },
      el("thead", {}, el("tr", {}, el("th", {}, "Dag"), el("th", {}, "Maks"), lm.map((n) => el("th", {}, n, el("br"), el("small", {}, "antall · mg"))), el("th", {}, "Symptomer"))),
      el("tbody", {}, [...dager.values()].map((d) => el("tr", {},
        el("td", { style: "white-space:nowrap" }, new Date(d.tid).toLocaleDateString("nb-NO", { weekday: "short", day: "numeric" }).replace(".", "")),
        el("td", { class: d.maks != null && d.maks >= grense ? "feber" : "" }, d.maks != null ? `${tall(d.maks, 1)}°` : "–"),
        lm.map((n) => el("td", { style: "white-space:nowrap" }, d.lm[n] ? `${d.lm[n].n} · ${tall(Math.round(d.lm[n].mg))}` : "–")),
        el("td", {}, [...d.symp].join(", ") || "–")))));
    return el("div", { class: "tabell-wrap" }, t);
  }

  function graf(regs, grense) {
    const temps = regs.filter((r) => r.temp != null);
    const doser = regs.filter((r) => r.legemiddel);
    if (!temps.length && !doser.length) return el("p", { class: "tom" }, "Ingen temperaturer eller doser i denne perioden.");
    const lm = [...new Set(doser.map((r) => r.legemiddel))];
    const farge = Object.fromEntries(lm.map((n, i) => [n, DOSEFARGER[i % DOSEFARGER.length]]));
    const t0 = new Date(regs[0].tid).getTime(), t1 = new Date(regs[regs.length - 1].tid).getTime();
    const span = Math.max(t1 - t0, 12 * 36e5);
    const fra = t0 - span * 0.04, til = t0 + span * 1.04;
    const W = 340, venstre = 30, hoyre = 8, topp = 10, TH = 150, baneH = 16;
    const H = topp + TH + 22 + lm.length * baneH + 4;
    const vals = temps.map((r) => r.temp);
    const ymin = Math.min(36, Math.floor(Math.min(...vals, 37) - 0.2)), ymax = Math.max(40, Math.ceil(Math.max(...vals, 38) + 0.2));
    const x = (t) => venstre + ((new Date(t).getTime() - fra) / (til - fra)) * (W - venstre - hoyre);
    const y = (v) => topp + (1 - (v - ymin) / (ymax - ymin)) * TH;
    const svg = svgEl("svg", { viewBox: `0 0 ${W} ${H}`, role: "img", "aria-label": "Temperaturkurve med doser" });
    svg.append(svgEl("rect", { class: "feber-felt", x: venstre, y: y(ymax), width: W - venstre - hoyre, height: y(grense) - y(ymax) }));
    for (let v = ymin; v <= ymax; v++) {
      svg.append(svgEl("line", { class: "rutenett", x1: venstre, x2: W - hoyre, y1: y(v), y2: y(v) }));
      svg.append(svgEl("text", { class: "akse-tekst", x: venstre - 6, y: y(v) + 3, "text-anchor": "end" }, `${v}°`));
    }
    svg.append(svgEl("line", { class: "feber-linje", x1: venstre, x2: W - hoyre, y1: y(grense), y2: y(grense) }));
    // dagsdeling
    const d = new Date(fra); d.setHours(0, 0, 0, 0);
    const dager = Math.ceil((til - fra) / 864e5) + 1;
    const hvert = Math.max(1, Math.ceil(dager / 7));
    let i = 0;
    for (d.setDate(d.getDate() + 1); d.getTime() < til; d.setDate(d.getDate() + 1), i++) {
      const xx = x(d);
      svg.append(svgEl("line", { class: "dagstrek", x1: xx, x2: xx, y1: topp, y2: H - 4 }));
      if (i % hvert === 0) svg.append(svgEl("text", { class: "akse-tekst", x: xx + 3, y: topp + TH + 14 },
        d.toLocaleDateString("nb-NO", { weekday: "short", day: "numeric" }).replace(".", "")));
    }
    if (temps.length > 1) {
      svg.append(svgEl("polyline", { class: "temp-linje", points: temps.map((r) => `${x(r.tid).toFixed(1)},${y(r.temp).toFixed(1)}`).join(" ") }));
    }
    for (const r of temps) {
      svg.append(svgEl("circle", { class: `temp-punkt ${r.temp < grense ? "lav" : ""}`, cx: x(r.tid), cy: y(r.temp), r: 4 }));
    }
    lm.forEach((n, bane) => {
      const yy = topp + TH + 22 + bane * baneH;
      svg.append(svgEl("line", { class: "rutenett", x1: venstre, x2: W - hoyre, y1: yy + 6, y2: yy + 6 }));
      for (const r of doser.filter((q) => q.legemiddel === n)) {
        svg.append(svgEl("rect", { class: "dose-merke", x: x(r.tid) - 3.5, y: yy, width: 7, height: 12, rx: 2.5, fill: farge[n] }));
      }
    });
    const forklaring = el("div", { class: "graf-forklaring" },
      el("span", {}, el("i", { style: "background:var(--temp)" }), "Temperatur"),
      lm.map((n) => el("span", {}, el("i", { style: `background:${farge[n]}` }), n)),
      el("span", {}, el("i", { style: "background:var(--temp-lys)" }), `Feber (≥ ${tall(grense, 1)} °C)`));
    return el("div", {}, el("div", { class: "graf" }, svg), forklaring);
  }

  // ================================================================ GJENNOMGANG
  async function visGjennomgang(stille = false) {
    if (!stille) vis("gjennomgang");
    if (!data) await last();
    let g;
    try { g = await api("api/gjennomgang"); } catch (e) { visToast(e.message); return; }
    const v = $("v-gjennomgang");
    const barn = data.alle_barn;
    const tildel = async (ider, bid, tekst) => {
      try {
        const r = await api("api/gjennomgang/tildel", { method: "POST", body: { ider, barn_id: bid } });
        visToast(tekst.replace("{n}", r.antall));
        await last(); visGjennomgang(true);
      } catch (e) { visToast(e.message); }
    };
    const innhold = [
      el("button", { class: "tilbake", onclick: () => visInnstillinger() }, ikon("venstre"), "Innstillinger"),
      el("div", { class: "ep-hode" }, el("div", { class: "tekst" }, el("h2", {}, "Gjennomgang"),
        el("p", {}, "Det importen ikke kunne avgjøre sikkert."))),
    ];
    if (!g.ukjente.length && !g.sjekk.length) {
      innhold.push(el("div", { class: "kort" }, el("p", { class: "tom" }, "Alt er gjennomgått ✓")));
    }
    const fodtFor = (iso) => barn.filter((b) => !b.fodselsdato || b.fodselsdato <= lokalDag(iso));
    if (g.ukjente.length) {
      const n = g.ukjente.reduce((s, x) => s + x.ider.length, 0);
      innhold.push(el("div", { class: "seksjon-tittel" }, `Hvilket barn? (${g.ukjente.length} sykdomsperioder)`));
      innhold.push(el("p", { class: "forklaring" }, "Disse registreringene står uten navn i kalenderen. De er samlet i sykdomsperioder – velg barnet for hele perioden. Dosestørrelsen kan hjelpe dere å huske."));
      if (g.ukjente.length > 1) {
        innhold.push(el("div", { class: "gj-kort" }, el("div", { class: "gj-tittel" }, `Alle ${g.ukjente.length} perioder på én gang (${n} registreringer)`),
          el("div", { class: "gj-knapper" }, fodtFor(g.ukjente[0].fra).map((b) => el("button", { class: `chip farge-${b.farge}`, onclick: async () => {
            if (await bekreft(`Alle til ${b.navn}?`, `${n} registreringer i ${g.ukjente.length} perioder blir lagt til ${b.navn}.`, "Ja, tildel alle"))
              tildel(g.ukjente.flatMap((x) => x.ider), b.id, `{n} registreringer lagt til ${b.navn}`);
          } }, avatar(b), b.navn)))));
      }
      for (const gr of g.ukjente) {
        const kandidater = fodtFor(gr.til);
        const periode = lokalDag(gr.fra) === lokalDag(gr.til) ? dato(gr.fra, true) : `${dato(gr.fra)} – ${dato(gr.til, true)}`;
        const liste = el("ul", { class: "logg", hidden: true }, gr.registreringer.map((r) => logRad(r, { visDato: true })));
        const merker = [
          ...gr.doser.map((d) => el("span", { class: "merkelapp med" }, `${d.navn} ×${d.antall} · ${d.mg.map((m) => tall(m)).join("/")} mg`)),
          gr.temp_maks != null ? el("span", { class: "merkelapp temp" }, `maks ${tall(gr.temp_maks, 1)} °C`) : null,
        ].filter(Boolean);
        innhold.push(el("div", { class: "gj-kort" },
          el("div", {}, el("div", { class: "gj-tittel" }, periode), el("div", { class: "episode-under" }, `${gr.ider.length} ${gr.ider.length === 1 ? "registrering" : "registreringer"}`)),
          merker.length ? el("div", { class: "episode-merker" }, merker) : null,
          gr.notater.length ? el("ul", { class: "gj-notater" }, gr.notater.map((t) => el("li", {}, t))) : null,
          el("button", { class: "vis-mer", onclick: (e) => { liste.hidden = !liste.hidden; e.target.textContent = liste.hidden ? "Vis registreringene" : "Skjul"; } }, "Vis registreringene"),
          liste,
          el("div", { class: "gj-knapper" },
            kandidater.map((b) => el("button", { class: `chip farge-${b.farge}`, onclick: () => tildel(gr.ider, b.id, `{n} registreringer lagt til ${b.navn}`) }, avatar(b), b.navn)),
            el("button", { class: "chip forkast", onclick: async () => {
              if (await bekreft("Forkast perioden?", "Registreringene slettes fra Plasterboka. Kalenderen er urørt.", "Forkast", true))
                tildel(gr.ider, null, "{n} registreringer forkastet");
            } }, "Forkast"))));
      }
    }
    if (g.sjekk.length) {
      innhold.push(el("div", { class: "seksjon-tittel" }, `Bør sjekkes (${g.sjekk.length})`));
      innhold.push(el("p", { class: "forklaring" }, "Mulige dobbeltregistreringer og doser som skiller seg ut fra de andre dagene. Trykk for å endre, eller behold/slett direkte."));
      for (const r of g.sjekk) {
        const b = barn.find((x) => x.id === r.barn_id);
        innhold.push(el("div", { class: "gj-kort" },
          el("ul", { class: "logg" }, logRad({ ...r, merknad: null, status: "ok" }, { visDato: true })),
          el("div", { class: "vurdering obs" }, ikon("advarsel"), el("span", {}, r.merknad)),
          el("div", { class: "gj-knapper" },
            el("button", { class: "chip", style: "background:var(--frisk-lys);color:var(--frisk-blekk)", onclick: async () => {
              try { await api(`api/registreringer/${r.id}`, { method: "PATCH", body: { godkjenn: true, bekreftet: true } }); visGjennomgang(true); last(); } catch (e) { visToast(e.message); }
            } }, ikon("sjekk"), "Behold"),
            el("button", { class: "chip forkast", onclick: async () => {
              try {
                const { slettet } = await api(`api/registreringer/${r.id}`, { method: "DELETE" });
                visToast("Slettet", [{ tekst: "Angre", fn: async () => { await api("api/registreringer/gjenopprett", { method: "POST", body: slettet }); visGjennomgang(true); } }]);
                visGjennomgang(true); last();
              } catch (e) { visToast(e.message); }
            } }, "Slett"),
            b ? el("span", { class: "episode-under", style: "align-self:center;margin-left:auto" }, b.navn) : null)));
      }
    }
    v.replaceChildren(...innhold);
  }

  // ================================================================ INNSTILLINGER
  async function visInnstillinger(stille = false) {
    if (!stille) vis("innstillinger");
    try { await hentInn(); if (!data) await last(); } catch (e) { visToast(e.message); return; }
    const v = $("v-innstillinger");
    const i = inn.innstillinger;
    const g = data.gjennomgang;
    const antall = (g.ukjent || 0) + (g.sjekk || 0);
    if (!instBarn || !inn.barn.find((b) => b.id === instBarn)) instBarn = inn.barn[0]?.id ?? null;

    const deler = [];
    if (antall) deler.push(el("button", { class: "banner", onclick: () => visGjennomgang() }, ikon("advarsel"),
      el("span", {}, `${antall} importerte registreringer venter på gjennomgang`), ikon("hoyre")));

    // barn
    deler.push(el("div", { class: "seksjon-tittel" }, "Barn"));
    deler.push(el("section", { class: "kort" },
      el("ul", { class: "liste" }, inn.barn.map((b) => {
        const st = data.barn.find((s) => s.barn.id === b.id);
        const under = [st?.alder?.tekst || (b.fodselsdato ? "" : "Ingen fødselsdato"), b.aktiv ? null : "skjult", inn.sensorer[b.id]].filter(Boolean).join(" · ");
        return el("li", {}, el("button", { class: "liste-rad", onclick: () => barnArk(b) }, avatar(b),
          el("span", { class: "rad-tekst" }, el("div", { class: "rad-tittel" }, b.navn), el("div", { class: "rad-under" }, under)), ikon("hoyre")));
      })),
      el("button", { class: "legg-til", onclick: () => barnArk(null) }, ikon("pluss"), "Legg til barn")));

    // legemidler
    deler.push(el("div", { class: "seksjon-tittel" }, "Legemidler"));
    const lmKort = el("section", { class: "kort skjema" });
    if (inn.barn.length) {
      lmKort.append(el("div", { class: "chips" }, inn.barn.map((b) => el("button", { class: `chip farge-${b.farge} ${instBarn === b.id ? "valgt" : ""}`, style: "--aksent:var(--b)",
        onclick: () => { instBarn = b.id; visInnstillinger(true); } }, avatar(b), b.navn))));
      lmKort.append(el("p", { class: "forklaring" }, "Slå på det som skal kunne velges ved registrering. Dose, intervall og maks døgndose legger dere inn selv etter pakningsvedlegg eller resept – appen regner ikke ut doser."));
    }
    const aktiveLm = inn.legemidler.filter((l) => !l.arkivert);
    lmKort.append(el("ul", { class: "liste" }, aktiveLm.length ? aktiveLm.map((l) => {
      const bl = inn.barn_legemidler.find((x) => x.barn_id === instBarn && x.legemiddel_id === l.id);
      const paa = !!bl?.aktiv;
      const under = [l.virkestoff.toLowerCase() !== l.navn.toLowerCase() ? l.virkestoff : null, l.mg_per_ml ? `${tall(l.mg_per_ml)} mg/ml` : null,
        bl?.standard_mg ? `${tall(bl.standard_mg)} mg` : null, bl?.min_intervall_t ? `hver ${tall(bl.min_intervall_t)}. t` : null,
        bl?.maks_dogn_mg ? `maks ${tall(bl.maks_dogn_mg)} mg/døgn` : null, bl?.kur_doser_dag ? `kur ${bl.kur_doser_dag}×/dag` : null].filter(Boolean).join(" · ");
      const bryter = el("button", { class: `bryter ${paa ? "paa" : ""}`, "aria-label": paa ? "Slå av" : "Slå på", onclick: async (e) => {
        e.stopPropagation();
        if (!instBarn) return;
        try { await api(`api/barn/${instBarn}/legemidler/${l.id}`, { method: "PUT", body: { aktiv: !paa } }); await last(); visInnstillinger(true); } catch (x) { visToast(x.message); }
      } });
      return el("li", {}, el("div", { class: "liste-rad" },
        el("button", { class: "rad-tekst", style: "text-align:left", onclick: () => legemiddelArk(l, instBarn) },
          el("div", { class: "rad-tittel" }, l.navn), el("div", { class: "rad-under" }, under || "Trykk for å sette dose og grenser")),
        instBarn ? bryter : null));
    }) : el("li", { class: "tom" }, "Ingen legemidler ennå")));
    lmKort.append(el("button", { class: "legg-til", onclick: () => legemiddelArk(null, instBarn) }, ikon("pluss"), "Nytt legemiddel"));
    const arkiv = inn.legemidler.filter((l) => l.arkivert);
    if (arkiv.length) lmKort.append(el("p", { class: "forklaring" }, `Arkivert (brukt i historikken): ${arkiv.map((l) => l.navn).join(", ")}`));
    deler.push(lmKort);

    // symptomer
    deler.push(el("div", { class: "seksjon-tittel" }, "Symptomer"));
    const nytt = el("input", { type: "text", maxlength: 30, placeholder: "Nytt symptom" });
    const leggTil = async () => {
      const t = nytt.value.trim();
      if (!t) return;
      await lagreInn({ symptomer: [...i.symptomer, t] });
    };
    nytt.addEventListener("keydown", (e) => { if (e.key === "Enter") leggTil(); });
    deler.push(el("section", { class: "kort skjema" },
      el("div", { class: "chips" }, i.symptomer.map((s) => el("span", { class: "chip" }, s,
        el("button", { class: "chip-fjern", "aria-label": `Fjern ${s}`, onclick: () => lagreInn({ symptomer: i.symptomer.filter((x) => x !== s) }) }, ikon("kryss"))))),
      el("div", { class: "felt-rad" }, el("label", { class: "felt" }, nytt), el("button", { class: "knapp noytral", onclick: leggTil }, ikon("pluss"), "Legg til"))));

    // varsling og grenser
    deler.push(el("div", { class: "seksjon-tittel" }, "Varsling og grenser"));
    const varsle = el("input", { type: "text", placeholder: "notify.mobil_app_telefon", value: i.varsle_tjeneste });
    const grense = el("input", { type: "text", inputmode: "decimal", value: tall(i.feber_grense, 1) });
    const pause = el("input", { type: "text", inputmode: "numeric", value: i.episode_pause_t });
    const vindu = el("input", { type: "text", inputmode: "numeric", value: i.syk_vindu_t });
    let metode = i.standard_metode;
    const metodeSeg = el("div", { class: "segment" }, inn.metoder.map((m) => el("button", { class: metode === m.id ? "valgt" : "",
      onclick: (e) => { metode = m.id; metodeSeg.querySelectorAll("button").forEach((b) => b.classList.remove("valgt")); e.target.classList.add("valgt"); } }, m.navn)));
    deler.push(el("section", { class: "kort skjema" },
      el("label", { class: "felt" }, el("span", {}, "Send varsel ved registrering via"), varsle),
      el("p", { class: "forklaring" }, "En notify-tjeneste fra Home Assistant, f.eks. en mobil eller en gruppe. La stå tom for å slå av. Appen sender også hendelsen ", el("code", {}, "plasterboka_hendelse"), " som automasjoner kan bruke."),
      el("div", { class: "felt" }, el("span", {}, "Vanlig målemetode"), metodeSeg),
      el("div", { class: "felt-rad" },
        el("label", { class: "felt" }, el("span", {}, "Feber fra (°C)"), grense),
        el("label", { class: "felt" }, el("span", {}, "Ny sykdom etter (timer)"), pause)),
      el("div", { class: "felt-rad" },
        el("label", { class: "felt" }, el("span", {}, "Frisk etter (timer uten registrering)"), vindu), el("span")),
      el("p", { class: "forklaring" }, "Helsenorge regner 38,0 °C eller mer som feber. ", el("a", { href: "https://www.helsenorge.no/sykdom/barn/feber-hos-barn/", target: "_blank", rel: "noopener" }, "Feber hos barn")),
      el("button", { class: "knapp", style: "--aksent:var(--temp)", onclick: () => lagreInn({
        varsle_tjeneste: varsle.value, feber_grense: grense.value, episode_pause_t: pause.value, syk_vindu_t: vindu.value, standard_metode: metode,
      }, "Lagret") }, "Lagre")));

    // import og eksport
    deler.push(el("div", { class: "seksjon-tittel" }, "Import og eksport"));
    deler.push(el("section", { class: "kort skjema" },
      el("p", { class: "forklaring" }, "Hent inn eldre registreringer fra kalendere i Home Assistant. Duplikater fjernes, og importen kan kjøres flere ganger uten å lage dobbelt opp. Kalenderne endres ikke."),
      el("button", { class: "knapp noytral", onclick: importArk }, ikon("kalender"), "Importer fra kalendere"),
      el("a", { class: "knapp noytral", href: "api/eksport.csv", download: "plasterboka.csv" }, ikon("last-ned"), "Last ned alt som CSV")));

    deler.push(el("p", { class: "forklaring", style: "text-align:center;margin-top:8px" }, "Plasterboka erstatter ikke lege eller helsestasjon. Ved bekymring, ring fastlegen, legevakt (116 117) eller 113."));
    v.replaceChildren(...deler);
  }

  async function lagreInn(d, melding) {
    try { await api("api/innstillinger", { method: "PUT", body: d }); await last(); await visInnstillinger(true); if (melding) visToast(melding); }
    catch (e) { visToast(e.message); }
  }

  function barnArk(b) {
    const ny = !b;
    let farge = b?.farge || inn.farger[inn.barn.length % inn.farger.length];
    let aktiv = b ? !!b.aktiv : true;
    const navn = el("input", { type: "text", maxlength: 30, value: b?.navn || "", placeholder: "Navn" });
    const fd = el("input", { type: "date", value: b?.fodselsdato || "" });
    const vekt = el("input", { type: "text", inputmode: "decimal", value: tall(b?.vekt_kg), placeholder: "Valgfritt" });
    const fargevalg = el("div", { class: "fargevalg" }, inn.farger.map((f) => el("button", { class: `farge-${f} ${farge === f ? "valgt" : ""}`, "aria-label": f,
      onclick: (e) => { farge = f; fargevalg.querySelectorAll("button").forEach((x) => x.classList.remove("valgt")); e.currentTarget.classList.add("valgt"); } })));
    const bryter = el("button", { class: `bryter ${aktiv ? "paa" : ""}`, onclick: (e) => { aktiv = !aktiv; e.currentTarget.classList.toggle("paa", aktiv); } });
    aapneArk(el("div", {},
      el("h3", {}, ny ? "Nytt barn" : b.navn),
      el("p", { class: "hint" }, "Lagres bare lokalt i appen."),
      el("div", { class: "skjema" },
        el("label", { class: "felt" }, el("span", {}, "Navn"), navn),
        el("div", { class: "felt" }, el("span", {}, "Farge"), fargevalg),
        el("div", { class: "felt-rad" },
          el("label", { class: "felt" }, el("span", {}, "Fødselsdato eller termin"), fd),
          el("label", { class: "felt" }, el("span", {}, "Vekt (kg)"), vekt)),
        el("div", { class: "liste-rad" }, el("span", { class: "rad-tekst" }, el("div", { class: "rad-tittel" }, "Vis på forsiden"),
          el("div", { class: "rad-under" }, "Slå av for et barn som ikke er født ennå")), bryter)),
      el("div", { class: "ark-knapper" },
        ny ? null : el("button", { class: "knapp fare", onclick: async () => {
          if (!(await bekreft(`Slette ${b.navn}?`, "Alle registreringer og sykdomsepisoder for barnet slettes for godt. Vil du heller skjule barnet, slå av «Vis på forsiden».", "Slett", true))) return;
          try { await api(`api/barn/${b.id}`, { method: "DELETE" }); await last(); visInnstillinger(true); } catch (e) { visToast(e.message); }
        } }, "Slett"),
        el("button", { class: "knapp", style: "--aksent:var(--temp)", onclick: async () => {
          const body = { navn: navn.value, farge, fodselsdato: fd.value || null, vekt_kg: vekt.value, aktiv };
          try {
            await api(ny ? "api/barn" : `api/barn/${b.id}`, { method: ny ? "POST" : "PATCH", body });
            lukkArk(); await last(); visInnstillinger(true);
          } catch (e) { visToast(e.message); }
        } }, "Lagre"))));
  }

  function legemiddelArk(l, bid) {
    const ny = !l;
    const bl = l ? inn.barn_legemidler.find((x) => x.barn_id === bid && x.legemiddel_id === l.id) : null;
    const b = inn.barn.find((x) => x.id === bid);
    let form = l?.form || "mikstur";
    let aktiv = bl ? !!bl.aktiv : true;
    const navn = el("input", { type: "text", maxlength: 40, value: l?.navn || "", placeholder: "F.eks. Paracet mikstur" });
    const virkestoff = el("input", { type: "text", maxlength: 40, value: l?.virkestoff || "", placeholder: "F.eks. Paracetamol" });
    const styrke = el("input", { type: "text", inputmode: "decimal", value: tall(l?.mg_per_ml), placeholder: "mg per ml" });
    const std = el("input", { type: "text", inputmode: "decimal", value: tall(bl?.standard_mg) });
    const intervall = el("input", { type: "text", inputmode: "decimal", value: tall(bl?.min_intervall_t) });
    const maks = el("input", { type: "text", inputmode: "decimal", value: tall(bl?.maks_dogn_mg) });
    const kurN = el("input", { type: "text", inputmode: "numeric", value: bl?.kur_doser_dag || "" });
    const kurTil = el("input", { type: "date", value: bl?.kur_til || "" });
    const styrkeFelt = el("label", { class: "felt" }, el("span", {}, "Styrke"), el("div", { class: "felt-wrap" }, styrke, el("span", { class: "enhet" }, "mg/ml")));
    styrkeFelt.hidden = form !== "mikstur";
    const formSeg = el("div", { class: "segment" }, inn.former.map((f) => el("button", { class: form === f ? "valgt" : "",
      onclick: (e) => { form = f; formSeg.querySelectorAll("button").forEach((x) => x.classList.remove("valgt")); e.target.classList.add("valgt"); styrkeFelt.hidden = f !== "mikstur"; } }, f)));
    const mgFelt = (navn_, inp, enhet) => el("label", { class: "felt" }, el("span", {}, navn_), el("div", { class: "felt-wrap" }, inp, el("span", { class: "enhet" }, enhet)));
    const bryter = el("button", { class: `bryter ${aktiv ? "paa" : ""}`, onclick: (e) => { aktiv = !aktiv; e.currentTarget.classList.toggle("paa", aktiv); } });
    aapneArk(el("div", {},
      el("h3", {}, ny ? "Nytt legemiddel" : l.navn),
      el("div", { class: "skjema" },
        el("label", { class: "felt" }, el("span", {}, "Navn"), navn),
        el("label", { class: "felt" }, el("span", {}, "Virkestoff"), virkestoff),
        el("p", { class: "forklaring" }, "Døgndosen summeres per virkestoff – så mikstur og stikkpiller med paracetamol telles sammen."),
        el("div", { class: "felt" }, el("span", {}, "Form"), formSeg),
        styrkeFelt,
        b ? el("div", { class: "ark-etikett" }, `For ${b.navn}`) : null,
        b ? el("div", { class: "liste-rad" }, el("span", { class: "rad-tekst" }, el("div", { class: "rad-tittel" }, "Kan velges ved registrering")), bryter) : null,
        b ? el("div", { class: "felt-rad" }, mgFelt("Vanlig dose", std, "mg"), mgFelt("Minste intervall", intervall, "timer")) : null,
        b ? el("div", { class: "felt-rad" }, mgFelt("Maks per døgn", maks, "mg"), el("span")) : null,
        b ? el("p", { class: "forklaring" }, "Fra pakningsvedlegget eller legen. Gir varsel ved for tidlig dose eller for mye per døgn.") : null,
        b ? el("div", { class: "ark-etikett" }, "Kur (valgfritt)") : null,
        b ? el("div", { class: "felt-rad" }, mgFelt("Doser per dag", kurN, "×"), el("label", { class: "felt" }, el("span", {}, "Siste dag"), kurTil)) : null),
      el("div", { class: "ark-knapper" },
        ny ? null : el("button", { class: "knapp fare", onclick: async () => {
          if (!(await bekreft(`Fjerne ${l.navn}?`, "Er legemiddelet brukt i historikken, blir det arkivert i stedet for slettet.", "Fjern", true))) return;
          try { const r = await api(`api/legemidler/${l.id}`, { method: "DELETE" }); visToast(r.resultat === "arkivert" ? "Arkivert" : "Slettet"); await last(); visInnstillinger(true); } catch (e) { visToast(e.message); }
        } }, "Fjern"),
        el("button", { class: "knapp", style: "--aksent:var(--temp)", onclick: async () => {
          try {
            const body = { navn: navn.value, virkestoff: virkestoff.value, form, mg_per_ml: form === "mikstur" ? styrke.value : null };
            const { legemiddel } = await api(ny ? "api/legemidler" : `api/legemidler/${l.id}`, { method: ny ? "POST" : "PATCH", body });
            if (b) {
              await api(`api/barn/${b.id}/legemidler/${legemiddel.id}`, { method: "PUT", body: {
                aktiv, standard_mg: std.value, min_intervall_t: intervall.value, maks_dogn_mg: maks.value,
                kur_doser_dag: kurN.value, kur_til: kurTil.value || null,
              } });
            }
            lukkArk(); await last(); visInnstillinger(true);
          } catch (e) { visToast(e.message); }
        } }, "Lagre"))));
  }

  // ---- import ----
  async function importArk() {
    let kalendere = [];
    try {
      const r = await api("api/import/kalendere");
      kalendere = r.kalendere || [];
      if (r.feil) { visToast(r.feil); return; }
    } catch (e) { visToast(e.message); return; }
    const valg = Object.fromEntries(kalendere.map((k) => [k.entity_id, {
      paa: /medisin|medicine|helse/i.test(`${k.entity_id} ${k.name}`), barn_id: null, modus: "ingen", dato: "",
    }]));
    // Gjett barn fra kalendernavnet
    for (const k of kalendere) for (const b of inn.barn) if (new RegExp(`\\b${b.navn}\\b`, "i").test(k.name || "")) valg[k.entity_id].barn_id = b.id;
    let resultat = null, ark;

    const oppsett = () => kalendere.filter((k) => valg[k.entity_id].paa).map((k) => {
      const v = valg[k.entity_id];
      return { entity_id: k.entity_id, barn_id: v.barn_id, gjennomga_alle: v.modus === "alle" || !v.barn_id || (v.modus === "dato" && !v.dato), gjennomga_for: v.modus === "dato" ? v.dato || null : null };
    });

    function tegn() {
      const innhold = el("div", {},
        el("h3", {}, ikon("kalender"), "Importer fra kalendere"),
        el("p", { class: "hint" }, "Navn i hendelsesteksten avgjør hvilket barn en registrering hører til. For hendelser uten navn velger du hva som skal skje."),
        el("div", { class: "skjema" }, kalendere.length ? kalendere.map((k) => {
          const v = valg[k.entity_id];
          const kropp = [];
          if (v.paa) {
            kropp.push(el("label", { class: "felt" }, el("span", {}, "Hendelser uten navn tilhører"),
              el("select", { onchange: (e) => { v.barn_id = e.target.value ? +e.target.value : null; resultat = null; tegn(); } },
                el("option", { value: "" }, "Vet ikke – gjennomgå alle"),
                inn.barn.map((b) => el("option", { value: b.id, ...(v.barn_id === b.id ? { selected: true } : {}) }, b.navn)))));
            if (v.barn_id) {
              kropp.push(el("div", { class: "segment" }, [["dato", "Gjennomgå før dato"], ["alle", "Gjennomgå alle"], ["ingen", "Ingen gjennomgang"]].map(([m, t]) =>
                el("button", { class: v.modus === m ? "valgt" : "", onclick: () => { v.modus = m; resultat = null; tegn(); } }, t))));
              if (v.modus === "dato") {
                kropp.push(el("label", { class: "felt" }, el("span", {}, `Uten navn før denne datoen er usikre (f.eks. da kalenderen ble tatt i bruk for ${barnNavn(v.barn_id)})`),
                  el("input", { type: "date", value: v.dato, onchange: (e) => { v.dato = e.target.value; resultat = null; } })));
              }
            }
          }
          return el("div", { class: "kal-valg" },
            el("div", { class: "liste-rad" }, el("span", { class: "rad-tekst" }, el("div", { class: "rad-tittel" }, k.name || k.entity_id), el("div", { class: "rad-under" }, k.entity_id)),
              el("button", { class: `bryter ${v.paa ? "paa" : ""}`, onclick: () => { v.paa = !v.paa; resultat = null; tegn(); } })),
            kropp);
        }) : el("p", { class: "tom" }, "Fant ingen kalendere i Home Assistant.")),
        resultat ? oppsummering(resultat) : null,
        el("div", { class: "ark-knapper" },
          el("button", { class: "knapp noytral", onclick: forhandsvis }, "Forhåndsvis"),
          el("button", { class: "knapp", style: "--aksent:var(--temp)", disabled: !resultat || !resultat.registreringer, onclick: kjor },
            resultat ? `Importer ${resultat.registreringer}` : "Importer")));
      if (!ark) ark = aapneArk(innhold); else ark.replaceChildren(el("div", { class: "ark-handtak" }), innhold);
    }

    function oppsummering(o) {
      const rad = (t, v) => [el("span", {}, t), el("b", {}, String(v))];
      return el("div", { class: "oppsummering", style: "margin-top:16px" },
        rad("Kalenderhendelser lest", o.hendelser),
        rad("Duplikater fjernet", o.duplikater),
        rad("Temperatur + dose slått sammen", o.sammenslatt),
        rad("Allerede importert", o.allerede_importert),
        el("span", { class: "skille" }),
        rad("Nye registreringer", o.registreringer),
        ...Object.entries(o.per_barn).flatMap(([n, v]) => rad(` – ${n}`, v)),
        rad("Antatt barn (uten navn)", o.antatt),
        rad("Til gjennomgang: ukjent barn", o.ukjent),
        rad("Til gjennomgang: bør sjekkes", o.sjekk),
        rad("Temperatur hentet fra notat", o.temp_fra_notat),
        el("span", { class: "skille" }),
        o.fra ? rad("Periode", `${dato(o.fra, true)} – ${dato(o.til, true)}`) : null,
        rad("Per år", Object.entries(o.per_aar).map(([a, n]) => `${a}: ${n}`).join(", ") || "–"),
        rad("Legemidler", o.legemidler.join(", ") || "–"));
    }

    async function forhandsvis() {
      const k = oppsett();
      if (!k.length) { visToast("Velg minst én kalender"); return; }
      try { resultat = (await api("api/import/forhandsvis", { method: "POST", body: { kalendere: k } })).oppsummering; tegn(); ark.scrollTop = ark.scrollHeight; }
      catch (e) { visToast(e.message); }
    }

    async function kjor() {
      try {
        const r = await api("api/import/kjor", { method: "POST", body: { kalendere: oppsett() } });
        lukkArk();
        await last();
        const o = r.oppsummering;
        visToast(`${r.importert} registreringer importert${r.nye_legemidler.length ? ` · nye legemidler: ${r.nye_legemidler.join(", ")}` : ""}`, [], 8000);
        if (o.ukjent || o.sjekk) visGjennomgang(); else visHistorikk();
      } catch (e) { visToast(e.message); }
    }
    tegn();
  }

  // ------------------------------------------------------------ oppstart
  last().then(() => { if (data && !data.alle_barn.length) visInnstillinger(); });
  setInterval(() => { if (!document.hidden && fane === "hjem" && !$("ark-rot").children.length) last(); }, 60e3);
  document.addEventListener("visibilitychange", () => { if (!document.hidden) last(); });
})();
