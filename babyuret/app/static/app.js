/* Babyuret – frontend. Ingen rammeverk, alt relativt til ingress-stien. */
(() => {
  "use strict";

  const $ = (id) => document.getElementById(id);
  const el = (tag, attrs = {}, ...barn) => {
    const e = document.createElement(tag);
    for (const [k, v] of Object.entries(attrs)) {
      if (k === "class") e.className = v;
      else if (k.startsWith("on")) e.addEventListener(k.slice(2), v);
      else if (k === "html") e.innerHTML = v;
      else if (v !== false && v != null) e.setAttribute(k, v === true ? "" : v);
    }
    for (const b of barn.flat()) if (b != null) e.append(b.nodeType ? b : document.createTextNode(b));
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

  let data = null;          // siste svar fra api/status
  let visDag = null;        // null = i dag, ellers "YYYY-MM-DD"
  let toastTimer = null;

  // ---------------------------------------------------------------- API
  async function api(sti, opts = {}) {
    const r = await fetch(sti, {
      method: opts.method || "GET",
      headers: { "Content-Type": "application/json" },
      body: opts.body ? JSON.stringify(opts.body) : undefined,
      credentials: "same-origin",
    });
    const j = await r.json().catch(() => ({}));
    if (!r.ok) throw new Error(j.feil || `Feil ${r.status}`);
    return j;
  }

  async function last() {
    try {
      data = await api("api/status" + (visDag ? `?dag=${visDag}` : ""));
      tegn();
    } catch (e) {
      visToast("Får ikke kontakt med Babyuret", []);
    }
  }

  async function handling(navn, ekstra = {}) {
    vibrer();
    try {
      const res = await api("api/handling", { method: "POST", body: { handling: navn, ...ekstra } });
      await last();
      return res;
    } catch (e) {
      visToast(e.message, []);
      return null;
    }
  }

  // ---------------------------------------------------------------- tid
  const kl = (iso) => new Date(iso).toLocaleTimeString("nb-NO", { hour: "2-digit", minute: "2-digit" });
  const sek = (fra, til = Date.now()) => Math.max(0, (til - new Date(fra).getTime()) / 1000);
  function varighet(s, kort = false) {
    const m = Math.floor(s / 60), t = Math.floor(m / 60), r = m % 60;
    if (t) return r ? `${t} t ${r} min` : `${t} t`;
    return kort ? `${m} min` : `${m} min`;
  }
  /** Stor tidsvisning: «1 t 05 min» eller «25 min» med små sekunder. */
  function stoppeklokke(s) {
    const t = Math.floor(s / 3600), m = Math.floor((s % 3600) / 60), ss = Math.floor(s % 60);
    if (t) return `${t} t ${String(m).padStart(2, "0")} min`;
    return `${m} min<small> ${String(ss).padStart(2, "0")} s</small>`;
  }
  function siden(iso) {
    if (!iso) return "";
    const s = sek(iso);
    if (s < 60) return "akkurat nå";
    return `for ${varighet(s)} siden`;
  }
  const lokalDato = (d = new Date()) =>
    `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
  function flyttDag(iso, n) {
    const [y, m, d] = iso.split("-").map(Number);
    return lokalDato(new Date(y, m - 1, d + n));
  }
  function dagTittel(iso) {
    const i_dag = lokalDato();
    if (iso === i_dag) return "I dag";
    if (iso === flyttDag(i_dag, -1)) return "I går";
    const [y, m, d] = iso.split("-").map(Number);
    return new Date(y, m - 1, d).toLocaleDateString("nb-NO", { weekday: "long", day: "numeric", month: "short" });
  }

  // ---------------------------------------------------------------- nattmodus
  function minutter(hhmm) {
    const [h, m] = (hhmm || "0:0").split(":").map(Number);
    return h * 60 + (m || 0);
  }
  function autoNatt() {
    if (!data) return false;
    const fra = minutter(data.innstillinger.nattmodus_fra), til = minutter(data.innstillinger.nattmodus_til);
    const n = new Date(), naa = n.getHours() * 60 + n.getMinutes();
    return fra > til ? naa >= fra || naa < til : naa >= fra && naa < til;
  }
  function lesOverstyring() {
    try {
      const o = JSON.parse(localStorage.getItem("babyuret-natt") || "null");
      if (o && o.til > Date.now()) return o.verdi;
    } catch (_) { /* privat modus */ }
    return null;
  }
  function settNatt() {
    const o = lesOverstyring();
    const natt = o === null ? autoNatt() : o;
    document.documentElement.dataset.natt = natt ? "1" : "0";
    document.querySelector('meta[name="theme-color"]').content = natt ? "#0A0606" : getComputedStyle(document.documentElement).getPropertyValue("--bg").trim();
  }
  $("natt-knapp").addEventListener("click", () => {
    const naa = document.documentElement.dataset.natt === "1";
    try {
      localStorage.setItem("babyuret-natt", JSON.stringify({ verdi: !naa, til: Date.now() + 6 * 3600e3 }));
    } catch (_) { /* ignorer */ }
    settNatt();
  });

  // ---------------------------------------------------------------- tegning
  function tegn() {
    if (!data) return;
    const { innstillinger: inn, status: st, oppsummering: op } = data;
    $("tittel").textContent = inn.baby_navn || "Babyuret";
    $("alder").textContent = data.alder ? data.alder.tekst : "";
    settNatt();
    tegnHelt();
    tegnFliser();
    tegnDag(op);
  }

  function tegnHelt() {
    const st = data.status;
    const helt = $("helt"), knapper = $("helt-knapper");
    knapper.replaceChildren();
    if (st.amming) {
      const side = st.amming.detaljer.side === "V" ? "venstre" : "høyre";
      helt.dataset.tilstand = "ammer";
      $("helt-merke").textContent = `Ammer · ${side}`;
      $("helt-under").textContent = `Startet ${kl(st.amming.start)}`;
      knapper.append(
        el("button", { class: "knapp sekundaer", onclick: () => handling("amming_bytt").then(r => r && visToast(r.melding, [])) }, ikon("bytt"), "Bytt side"),
        el("button", { class: "knapp", onclick: () => handling("amming_slutt").then(r => r && angreToast(r, "slutt")) }, ikon("stopp"), "Ferdig"),
      );
    } else if (st.tilstand === "sover") {
      helt.dataset.tilstand = "sover";
      $("helt-merke").textContent = "Sover";
      $("helt-under").textContent = `Sovnet ${kl(st.sovn.start)}`;
      knapper.append(el("button", { class: "knapp", onclick: () => veksleSovn() }, ikon("sol"), "Våknet"));
    } else {
      helt.dataset.tilstand = "vaaken";
      $("helt-merke").textContent = "Våken";
      $("helt-under").textContent = st.siden ? `Våknet ${kl(st.siden)}` : "Trykk «Sover» når babyen sovner";
    }
    tikk();
  }

  function tikk() {
    if (!data) return;
    const st = data.status;
    const fra = st.amming ? st.amming.start : st.siden;
    $("helt-tid").innerHTML = fra ? stoppeklokke(sek(fra)) : "–";
    const s = st.siste;
    $("sist-sovn").textContent = st.sovn ? `sovnet ${kl(st.sovn.start)}` : (s.sovn ? `våknet ${siden(s.sovn.slutt)}` : "");
    if (st.amming) $("sist-mat").textContent = `pågår · ${varighet(sek(st.amming.start))}`;
    else $("sist-mat").textContent = s.mat ? siden(s.mat.start) : "";
    $("sist-tiss").textContent = s.tiss ? siden(s.tiss.start) : "";
    $("sist-baesj").textContent = s.baesj ? siden(s.baesj.start) : "";
    oppdaterNaaLinje();
  }

  function tegnFliser() {
    const st = data.status;
    const sovn = $("flis-sovn");
    sovn.classList.toggle("aktiv", st.tilstand === "sover");
    sovn.querySelector(".flis-ikon").replaceChildren(ikon(st.tilstand === "sover" ? "sol" : "maane"));
    $("flis-sovn-navn").textContent = st.tilstand === "sover" ? "Våknet" : "Sover";
    $("flis-mat").classList.toggle("aktiv", !!st.amming);
    const matIkon = data.innstillinger.mating === "amming" ? "hjerte" : "flaske";
    $("flis-mat").querySelector(".flis-ikon").replaceChildren(ikon(matIkon));
  }

  function tegnDag(op) {
    const i_dag = data.i_dag;
    const dag = op.dag;
    $("dag-tittel").textContent = dagTittel(dag);
    $("dag-neste").disabled = dag >= i_dag;

    $("t-sovn").textContent = varighet(op.sovn_sek, true);
    $("t-sovn-under").textContent = `søvn · ${op.lurer} ${op.lurer === 1 ? "økt" : "økter"}`;
    $("t-mat").textContent = op.maltider;
    $("t-mat-under").textContent = (op.maltider === 1 ? "måltid" : "måltider") + (op.ml ? ` · ${op.ml} ml` : "");
    $("t-tiss").textContent = op.tiss;
    $("t-baesj").textContent = op.baesj;

    tegnStripe(op);
    tegnLogg(op);
  }

  function dagStart(iso) {
    const [y, m, d] = iso.split("-").map(Number);
    return new Date(y, m - 1, d).getTime();
  }

  function tegnStripe(op) {
    const stripe = $("stripe");
    stripe.replaceChildren();
    const start = dagStart(op.dag), lengde = dagStart(flyttDag(op.dag, 1)) - start;
    const pos = (t) => Math.min(100, Math.max(0, ((t - start) / lengde) * 100));
    const naa = Date.now();
    for (const h of op.hendelser) {
      const s = new Date(h.start).getTime();
      const e = h.slutt ? new Date(h.slutt).getTime() : naa;
      if (h.kategori === "sovn") {
        stripe.append(el("div", { class: "blokk sovn", style: `left:${pos(s)}%;width:${Math.max(0.4, pos(e) - pos(s))}%` }));
      } else if (h.kategori === "mat") {
        stripe.append(el("div", { class: "blokk mat", style: `left:${pos(s)}%;width:${Math.max(0.6, pos(e) - pos(s))}%` }));
      } else {
        if (h.detaljer.tiss) stripe.append(el("div", { class: "prikk tiss", style: `left:${pos(s)}%` }));
        if (h.detaljer.baesj) stripe.append(el("div", { class: "prikk baesj", style: `left:${pos(s)}%` }));
      }
    }
    if (op.dag === data.i_dag) stripe.append(el("div", { class: "naa", id: "naa-linje", style: `left:${pos(naa)}%` }));
  }

  function oppdaterNaaLinje() {
    const l = $("naa-linje");
    if (!l || !data) return;
    const start = dagStart(data.oppsummering.dag);
    l.style.left = `${Math.min(100, ((Date.now() - start) / 864e5) * 100)}%`;
  }

  function beskriv(h) {
    const d = h.detaljer;
    if (h.kategori === "sovn") {
      const tittel = "Søvn";
      const under = h.slutt ? `${kl(h.start)}–${kl(h.slutt)} · ${varighet(sek(h.start, new Date(h.slutt)))}` : `Sover nå · ${varighet(sek(h.start))}`;
      return { kl: "k-sovn", ikon: "maane", tittel, under };
    }
    if (h.kategori === "mat") {
      if (d.type === "flaske") return { kl: "k-mat", ikon: "flaske", tittel: `Flaske · ${d.ml} ml`, under: "" };
      const side = d.side === "V" ? "venstre" : "høyre";
      const under = h.slutt ? varighet(sek(h.start, new Date(h.slutt))) : `pågår · ${varighet(sek(h.start))}`;
      return { kl: "k-mat", ikon: "hjerte", tittel: `Amming · ${side}`, under };
    }
    if (d.tiss && d.baesj) return { kl: "k-baesj", ikon: "baesj", tittel: "Tiss og bæsj", under: "" };
    if (d.baesj) return { kl: "k-baesj", ikon: "baesj", tittel: "Bæsj", under: "" };
    return { kl: "k-tiss", ikon: "draape", tittel: "Tiss", under: "" };
  }

  function tegnLogg(op) {
    const logg = $("logg");
    logg.replaceChildren();
    const liste = [...op.hendelser].sort((a, b) => b.start.localeCompare(a.start));
    $("logg-tom").hidden = liste.length > 0;
    for (const h of liste) {
      const b = beskriv(h);
      const under = [b.under, h.av].filter(Boolean).join(" · ");
      logg.append(el("li", {},
        el("button", { class: "rad", onclick: () => redigerArk(h) },
          el("span", { class: `rad-ikon ${b.kl}` }, ikon(b.ikon)),
          el("span", { class: "rad-tekst" },
            el("div", { class: "rad-tittel" }, b.tittel),
            under ? el("div", { class: "rad-under" }, under) : null),
          el("span", { class: "rad-tid" }, kl(h.start)),
        )));
    }
  }

  // ---------------------------------------------------------------- små ting
  function vibrer() { try { navigator.vibrate && navigator.vibrate(12); } catch (_) { /* */ } }

  function bekreft(flisId) {
    const f = $(flisId);
    f.classList.remove("bekreftet");
    void f.offsetWidth;
    f.classList.add("bekreftet");
    setTimeout(() => f.classList.remove("bekreftet"), 950);
  }

  function visToast(tekst, knapper, ms = 6000) {
    clearTimeout(toastTimer);
    $("toast-tekst").textContent = tekst;
    const k = $("toast-knapper");
    k.replaceChildren(...knapper.map(([navn, fn]) => el("button", { onclick: () => { skjulToast(); fn(); } }, navn)));
    $("toast").hidden = false;
    toastTimer = setTimeout(skjulToast, ms);
  }
  function skjulToast() { $("toast").hidden = true; }

  /** Toast med «Angre» og «Endre». type: "ny" (slett ved angre) eller "slutt" (gjenåpne). */
  function angreToast(res, type) {
    const h = res.hendelse;
    if (!h) return;
    const angre = async () => {
      try {
        if (type === "ny") await api(`api/hendelser/${h.id}`, { method: "DELETE" });
        else await api(`api/hendelser/${h.id}`, { method: "PATCH", body: { slutt: null } });
        await last();
        visToast("Angret", [], 2000);
      } catch (e) { visToast(e.message, []); }
    };
    visToast(res.melding, [["Angre", angre], ["Endre", () => redigerArk(h)]]);
  }

  // ---------------------------------------------------------------- hovedknapper
  async function veksleSovn() {
    const sover = data && data.status.tilstand === "sover";
    const res = await handling("sovn_veksle");
    if (!res) return;
    bekreft("flis-sovn");
    angreToast(res, sover ? "slutt" : "ny");
  }
  $("flis-sovn").addEventListener("click", veksleSovn);

  async function bleie(navn, flis) {
    const res = await handling(navn);
    if (!res) return;
    bekreft(flis);
    angreToast(res, "ny");
  }
  $("flis-tiss").addEventListener("click", () => bleie("tiss", "flis-tiss"));
  $("flis-baesj").addEventListener("click", () => bleie("baesj", "flis-baesj"));
  $("flis-begge").addEventListener("click", () => bleie("begge", "flis-baesj"));

  $("flis-mat").addEventListener("click", () => matArk());

  $("dag-forrige").addEventListener("click", () => { visDag = flyttDag(data.oppsummering.dag, -1); last(); });
  $("dag-neste").addEventListener("click", () => {
    const ny = flyttDag(data.oppsummering.dag, 1);
    visDag = ny >= data.i_dag ? null : ny;
    last();
  });
  $("legg-til").addEventListener("click", () => leggTilArk());

  // ---------------------------------------------------------------- bunnark
  function aapneArk(...innhold) {
    $("ark-innhold").replaceChildren(...innhold);
    $("ark").hidden = false;
    $("ark-bakgrunn").hidden = false;
  }
  function lukkArk() {
    $("ark").hidden = true;
    $("ark-bakgrunn").hidden = true;
  }
  $("ark-bakgrunn").addEventListener("click", lukkArk);
  document.addEventListener("keydown", (e) => { if (e.key === "Escape") lukkArk(); });

  /** Chips for «når skjedde det» – reduserer behovet for å redigere etterpå. */
  function tidsvalg(state) {
    const valg = [[0, "Nå"], [5, "−5 min"], [10, "−10 min"], [20, "−20 min"]];
    const rad = el("div", { class: "chips jevn" });
    const tegnV = () => rad.replaceChildren(...valg.map(([m, navn]) =>
      el("button", { class: `chip${state.minutter_siden === m ? " valgt" : ""}`, onclick: () => { state.minutter_siden = m; tegnV(); } }, navn)));
    tegnV();
    return [el("div", { class: "ark-etikett" }, "Startet"), rad];
  }

  function matArk() {
    const st = data.status;
    if (st.amming) {
      const side = st.amming.detaljer.side === "V" ? "venstre" : "høyre";
      aapneArk(
        el("h3", {}, `Ammer ${side} side`),
        el("p", { class: "hint" }, `Startet ${kl(st.amming.start)} · ${varighet(sek(st.amming.start))}`),
        el("div", { class: "store-valg" },
          el("button", { class: "stort-valg", onclick: async () => { lukkArk(); const r = await handling("amming_bytt"); r && visToast(r.melding, []); } }, ikon("bytt"), "Bytt side"),
          el("button", { class: "stort-valg", onclick: async () => { lukkArk(); const r = await handling("amming_slutt"); r && angreToast(r, "slutt"); } }, ikon("stopp"), "Ferdig"),
        ),
      );
      return;
    }
    const modus = data.innstillinger.mating;
    if (modus === "flaske") return flaskeArk();
    const state = { minutter_siden: 0 };
    const anbefalt = st.neste_side;
    const sideKnapp = (side) => el("button", {
      class: `stort-valg${side === anbefalt ? " anbefalt" : ""}`,
      onclick: async () => {
        lukkArk();
        const r = await handling("amming_start", { side, minutter_siden: state.minutter_siden });
        if (r) { bekreft("flis-mat"); angreToast(r, "ny"); }
      },
    },
      side === anbefalt ? el("span", { class: "merkelapp" }, "Neste") : null,
      el("span", { class: "bokstav" }, side), side === "V" ? "Venstre" : "Høyre");

    const valg = [sideKnapp("V"), sideKnapp("H")];
    if (modus === "begge") {
      valg.push(el("button", { class: "stort-valg", onclick: () => flaskeArk(state.minutter_siden) }, ikon("flaske"), "Flaske"));
    }
    aapneArk(
      el("h3", {}, modus === "begge" ? "Mat" : "Amming"),
      el("p", { class: "hint" }, "Trykk på siden – tiden starter med en gang."),
      el("div", { class: `store-valg${valg.length === 3 ? " tre" : ""}` }, valg),
      ...tidsvalg(state),
    );
  }

  function flaskeArk(minutter_siden = 0) {
    const state = { ml: data.innstillinger.standard_flaske_ml, minutter_siden };
    const siste = data.status.siste.mat;
    if (siste && siste.detaljer.type === "flaske") state.ml = siste.detaljer.ml;
    const verdi = el("div", { class: "verdi" });
    const chips = el("div", { class: "chips jevn" });
    const forslag = [30, 60, 90, 120, 150, 180];
    const oppdater = () => {
      verdi.replaceChildren(String(state.ml), el("small", {}, " ml"));
      chips.replaceChildren(...forslag.map((ml) =>
        el("button", { class: `chip${state.ml === ml ? " valgt" : ""}`, onclick: () => { state.ml = ml; oppdater(); } }, `${ml}`)));
    };
    oppdater();
    aapneArk(
      el("h3", {}, "Flaske"),
      el("p", { class: "hint" }, "Juster mengden og trykk registrer."),
      el("div", { class: "stepper" },
        el("button", { onclick: () => { state.ml = Math.max(10, state.ml - 10); oppdater(); } }, "−"),
        verdi,
        el("button", { onclick: () => { state.ml = Math.min(400, state.ml + 10); oppdater(); } }, "+"),
      ),
      chips,
      ...tidsvalg(state),
      el("div", { class: "ark-knapper" },
        el("button", { class: "knapp", style: "--aksent: var(--mat)", onclick: async () => {
          lukkArk();
          const r = await handling("flaske", { ml: state.ml, minutter_siden: state.minutter_siden });
          if (r) { bekreft("flis-mat"); angreToast(r, "ny"); }
        } }, "Registrer"),
      ),
    );
  }

  // ---- redigering --------------------------------------------------
  const tilTidInput = (iso) => {
    const d = new Date(iso);
    return `${String(d.getHours()).padStart(2, "0")}:${String(d.getMinutes()).padStart(2, "0")}`;
  };
  /** Bygg en dato fra «HH:MM» med utgangspunkt i en referansedato. */
  function fraTidInput(hhmm, ref) {
    const [h, m] = hhmm.split(":").map(Number);
    const d = new Date(ref);
    d.setHours(h, m, 0, 0);
    return d;
  }

  function tidsfelt(etikett, verdi, ved) {
    const input = el("input", { type: "time", value: verdi });
    input.addEventListener("change", () => ved(input.value));
    const juster = (min) => {
      const [h, m] = input.value.split(":").map(Number);
      const tot = (h * 60 + m + min + 1440) % 1440;
      input.value = `${String(Math.floor(tot / 60)).padStart(2, "0")}:${String(tot % 60).padStart(2, "0")}`;
      ved(input.value);
    };
    return el("label", { class: "felt" },
      el("span", {}, etikett), input,
      el("div", { class: "juster" },
        el("button", { type: "button", onclick: (e) => { e.preventDefault(); juster(-5); } }, "−5"),
        el("button", { type: "button", onclick: (e) => { e.preventDefault(); juster(5); } }, "+5"),
      ));
  }

  function skjema(h, erNy) {
    // h: { kategori, start, slutt, detaljer }
    const state = { start: tilTidInput(h.start), slutt: h.slutt ? tilTidInput(h.slutt) : null, detaljer: { ...h.detaljer } };
    const punkt = h.kategori === "bleie" || (h.kategori === "mat" && h.detaljer.type === "flaske");
    const deler = [];

    const tider = el("div", { class: punkt ? "" : "felt-rad" });
    tider.append(tidsfelt(punkt ? "Tidspunkt" : "Start", state.start, (v) => { state.start = v; }));
    if (!punkt) {
      if (state.slutt === null && !erNy) {
        const pagar = el("div", { class: "felt" }, el("span", {}, "Slutt"),
          el("button", { class: "chip valgt", style: "--aksent: var(--sovn); min-height:52px", onclick: (e) => {
            e.preventDefault();
            state.slutt = tilTidInput(new Date().toISOString());
            pagar.replaceWith(tidsfelt("Slutt", state.slutt, (v) => { state.slutt = v; }));
          } }, "Pågår – sett slutt"));
        tider.append(pagar);
      } else {
        tider.append(tidsfelt("Slutt", state.slutt || state.start, (v) => { state.slutt = v; }));
        if (state.slutt === null) state.slutt = state.start;
      }
    }
    deler.push(tider);

    if (h.kategori === "mat" && h.detaljer.type === "amming") {
      const rad = el("div", { class: "veksle-rad" });
      const tegnS = () => rad.replaceChildren(...["V", "H"].map((s) =>
        el("button", { class: `chip${state.detaljer.side === s ? " valgt" : ""}`, onclick: () => { state.detaljer.side = s; tegnS(); } },
          s === "V" ? "Venstre" : "Høyre")));
      tegnS();
      deler.push(el("div", { class: "ark-etikett" }, "Side"), rad);
    }
    if (h.kategori === "mat" && h.detaljer.type === "flaske") {
      const verdi = el("div", { class: "verdi" });
      const opp = () => verdi.replaceChildren(String(state.detaljer.ml), el("small", {}, " ml"));
      opp();
      deler.push(el("div", { class: "ark-etikett" }, "Mengde"), el("div", { class: "stepper" },
        el("button", { onclick: () => { state.detaljer.ml = Math.max(10, state.detaljer.ml - 10); opp(); } }, "−"), verdi,
        el("button", { onclick: () => { state.detaljer.ml = Math.min(400, state.detaljer.ml + 10); opp(); } }, "+")));
    }
    if (h.kategori === "bleie") {
      const rad = el("div", { class: "veksle-rad" });
      const tegnB = () => rad.replaceChildren(
        el("button", { class: `chip${state.detaljer.tiss ? " valgt" : ""}`, style: "--aksent: var(--tiss)", onclick: () => { state.detaljer.tiss = !state.detaljer.tiss; tegnB(); } }, "Tiss"),
        el("button", { class: `chip${state.detaljer.baesj ? " valgt" : ""}`, style: "--aksent: var(--baesj)", onclick: () => { state.detaljer.baesj = !state.detaljer.baesj; tegnB(); } }, "Bæsj"));
      tegnB();
      deler.push(el("div", { class: "ark-etikett" }, "Bleie"), rad);
    }

    /** Gjør om HH:MM til ISO, med fornuftig dato (i går hvis i fremtiden, neste dag hvis slutt < start). */
    function tilVerdier() {
      const ref = h.start ? new Date(h.start) : new Date();
      let s = fraTidInput(state.start, ref);
      if (s.getTime() > Date.now() + 60e3) s = new Date(s.getTime() - 864e5);
      let e = null;
      if (state.slutt !== null && !punkt) {
        e = fraTidInput(state.slutt, s);
        if (e < s) e = new Date(e.getTime() + 864e5);
      }
      return { start: s.toISOString(), slutt: e ? e.toISOString() : null, detaljer: state.detaljer };
    }
    return { deler, tilVerdier };
  }

  function redigerArk(h) {
    const b = beskriv(h);
    const { deler, tilVerdier } = skjema(h, false);
    let sikker = false;
    const slettKnapp = el("button", { class: "knapp fare", onclick: async () => {
      if (!sikker) { sikker = true; slettKnapp.textContent = "Sikker?"; return; }
      try {
        await api(`api/hendelser/${h.id}`, { method: "DELETE" });
        lukkArk(); await last(); visToast("Slettet", [], 2500);
      } catch (e) { visToast(e.message, []); }
    } }, "Slett");
    const aksent = { sovn: "var(--sovn)", mat: "var(--mat)", bleie: "var(--tiss)" }[h.kategori];
    aapneArk(
      el("h3", {}, b.tittel),
      el("p", { class: "hint" }, h.av ? `Registrert av ${h.av}` : "Endre tidspunkt eller detaljer."),
      ...deler,
      el("div", { class: "ark-knapper" },
        slettKnapp,
        el("button", { class: "knapp", style: `--aksent: ${aksent}`, onclick: async () => {
          const v = tilVerdier();
          const body = { start: v.start, detaljer: v.detaljer };
          if (h.slutt !== null || v.slutt) body.slutt = v.slutt;
          try {
            await api(`api/hendelser/${h.id}`, { method: "PATCH", body });
            lukkArk(); await last(); visToast("Lagret", [], 2000);
          } catch (e) { visToast(e.message, []); }
        } }, "Lagre"),
      ),
    );
  }

  function leggTilArk() {
    const naa = new Date();
    const for30 = new Date(naa.getTime() - 30 * 60e3).toISOString();
    const typer = [
      ["Søvn", { kategori: "sovn", start: new Date(naa.getTime() - 60 * 60e3).toISOString(), slutt: for30, detaljer: {} }, "maane", "k-sovn"],
      ["Amming", { kategori: "mat", start: for30, slutt: new Date(naa.getTime() - 15 * 60e3).toISOString(), detaljer: { type: "amming", side: data.status.neste_side } }, "hjerte", "k-mat"],
      ["Flaske", { kategori: "mat", start: for30, slutt: for30, detaljer: { type: "flaske", ml: data.innstillinger.standard_flaske_ml } }, "flaske", "k-mat"],
      ["Bleie", { kategori: "bleie", start: for30, slutt: for30, detaljer: { tiss: true, baesj: false } }, "draape", "k-tiss"],
    ].filter(([navn]) => {
      const m = data.innstillinger.mating;
      return !(navn === "Amming" && m === "flaske") && !(navn === "Flaske" && m === "amming");
    });
    aapneArk(
      el("h3", {}, "Legg inn tidligere"),
      el("p", { class: "hint" }, "Glemte du å trykke? Velg hva som skjedde."),
      el("div", { class: "store-valg" }, typer.map(([navn, mal, ik, kl_]) =>
        el("button", { class: `stort-valg ${kl_}`, style: "background: var(--lys); color: var(--farge)", onclick: () => nyArk(navn, mal) }, ikon(ik), navn))),
    );
  }

  function nyArk(navn, mal) {
    const { deler, tilVerdier } = skjema(mal, true);
    const aksent = { sovn: "var(--sovn)", mat: "var(--mat)", bleie: "var(--tiss)" }[mal.kategori];
    aapneArk(
      el("h3", {}, navn),
      el("p", { class: "hint" }, "Juster tiden – dagens dato brukes, eller i går hvis tiden ligger frem i tid."),
      ...deler,
      el("div", { class: "ark-knapper" },
        el("button", { class: "knapp", style: `--aksent: ${aksent}`, onclick: async () => {
          const v = tilVerdier();
          try {
            await api("api/hendelser", { method: "POST", body: { kategori: mal.kategori, ...v } });
            lukkArk(); await last(); visToast(`${navn} lagt inn`, [], 2500);
          } catch (e) { visToast(e.message, []); }
        } }, "Lagre"),
      ),
    );
  }

  // ---------------------------------------------------------------- oppstart
  last();
  setInterval(tikk, 1000);
  setInterval(() => { if (!document.hidden) last(); }, 20000);
  setInterval(settNatt, 60000);
  document.addEventListener("visibilitychange", () => { if (!document.hidden) last(); });
})();
