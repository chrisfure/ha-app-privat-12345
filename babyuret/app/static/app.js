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
    $("velkommen").hidden = !!(inn.baby_navn || inn.fodselsdato);
    settNatt();
    tegnHelt();
    tegnLyd();
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
    tegnPrognose();
    tikk();
  }

  // ---------------------------------------------------------------- prognose
  function minTekst(m) {
    m = Math.round(m);
    if (m < 60) return `${m} min`;
    const t = Math.floor(m / 60), r = m % 60;
    return r ? `${t} t ${r} min` : `${t} t`;
  }
  const SIKKERHET = { startestimat: "startestimat", lav: "lite data", middels: "middels sikker", god: "god treff" };

  function tegnPrognose() {
    const p = data.prognose, knapp = $("prognose");
    if (!p || data.status.amming) { knapp.hidden = true; return; }
    knapp.hidden = false;
    if (!p.klar) {
      $("prognose-tittel").textContent = p.type === "vaakner" ? "Når våkner babyen?" : "Neste søvn";
      $("prognose-under").textContent = p.tekst;
      return;
    }
    const merke = el("span", { class: "merke-sikkerhet" }, SIKKERHET[p.sikkerhet] || p.sikkerhet);
    if (p.type === "vaakner") {
      $("prognose-tittel").replaceChildren(`Våkner trolig ${kl(p.fra)}–${kl(p.til)}`, merke);
      $("prognose-under").textContent = "Basert på babyens egne søvnperioder";
    } else if (p.forbi) {
      $("prognose-tittel").replaceChildren("Kan bli trøtt når som helst", merke);
      $("prognose-under").textContent = `Vanligvis sovnet innen ${kl(p.til)}`;
    } else {
      $("prognose-tittel").replaceChildren(`Neste søvn ca. ${kl(p.fra)}–${kl(p.til)}`, merke);
      $("prognose-under").textContent = p.varighet_min
        ? `Varer ofte ${minTekst(p.varighet_min[0])}–${minTekst(p.varighet_min[1])}`
        : "Varighet beregnes når det finnes flere søvnperioder";
    }
  }

  $("prognose").addEventListener("click", () => {
    const p = data.prognose;
    const deler = [
      el("h3", {}, "Om prognosen"),
      el("p", { class: "hint" }, p.klar ? p.grunnlag : p.tekst),
      el("p", { class: "ref-tekst" },
        "Prognosen regnes ut lokalt i appen fra deres egne registreringer de siste 7 dagene. Nyere dager teller mest, ",
        "og dag og natt beregnes hver for seg. Tidsvinduet viser hvor babyen vanligvis havner (midterste halvdel), ",
        "så det vil alltid være dager som avviker."),
      el("p", { class: "ref-tekst" },
        "Helsemyndighetene gir ingen anbefalte våkenperioder utover at nyfødte ofte er våkne 30–60 minutter av gangen. ",
        "Det brukes derfor bare som startestimat de første tre månedene, og babyens eget mønster tar over etter hvert."),
      el("p", { class: "kildeliste" }, "Kilde: ", el("a", { href: "https://www.helsenorge.no/barn/sovn-hos-barn/", target: "_blank", rel: "noopener" }, "Helsenorge – Søvn hos barn 0–2 år")),
    ];
    aapneArk(...deler);
  });

  // ---------------------------------------------------------------- siste døgn
  function tegnDogn() {
    const d = data.siste_dogn;
    if (!d) return;
    $("dogn-sovn").textContent = minTekst(d.sovn_timer * 60);
    const r = d.sovn_referanse;
    const maaler = $("dogn-maaler"), akse = $("dogn-akse");
    if (!r) {
      maaler.hidden = true; akse.hidden = true;
      $("dogn-ref").textContent = data.alder && data.alder.dager < 0
        ? "Når babyen er født, sammenlignes søvnen med det som er vanlig for alderen."
        : "Legg inn fødselsdato i innstillingene for å se hva som er vanlig for alderen.";
    } else {
      maaler.hidden = false; akse.hidden = false;
      const maks = 24, pst = (t) => `${Math.min(100, Math.max(0, (t / maks) * 100))}%`;
      Object.assign($("dogn-normal").style, { left: pst(r.normal[0]), width: `calc(${pst(r.normal[1])} - ${pst(r.normal[0])})` });
      Object.assign($("dogn-vanlig").style, { left: pst(r.vanlig[0]), width: `calc(${pst(r.vanlig[1])} - ${pst(r.vanlig[0])})` });
      $("dogn-merke").style.left = pst(d.sovn_timer);
      akse.replaceChildren(...[0, r.normal[0], r.vanlig[0], r.vanlig[1], r.normal[1], 24]
        .filter((v, i, a) => a.indexOf(v) === i)
        .map((t) => el("span", { style: `left:${pst(t)}` }, `${t}`)));
      const forTidlig = d.antall_dager_med_data < 1 ? " Det trengs minst ett helt døgn med registreringer før sammenligningen blir riktig." : "";
      $("dogn-ref").replaceChildren(`${r.tekst}${forTidlig} `,
        el("a", { href: "https://www.helsenorge.no/barn/sovn-hos-barn/", target: "_blank", rel: "noopener" }, "Kilde: Helsenorge"));
    }
    const am = $("dogn-amming");
    if (d.amming_referanse) {
      am.hidden = false;
      am.textContent = `${d.maltider} måltider siste døgn. ${d.amming_referanse.tekst} (Helsenorge)`;
    } else am.hidden = true;
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
    tegnDogn();
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
      let under = h.slutt ? `${kl(h.start)}–${kl(h.slutt)} · ${varighet(sek(h.start, new Date(h.slutt)))}` : `Sover nå · ${varighet(sek(h.start))}`;
      if (d.slutt_kilde === "auto") under += " · avsluttet automatisk";
      else if (d.slutt_kilde === "lyd") under += " · bekreftet fra lyd";
      if (d.sted && d.sted !== "seng") under += ` · ${SOVN_STED[d.sted] || d.sted}`;
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

  // ---------------------------------------------------------------- uke og måned
  let dagbokModus = "dag";
  let periodeDato = null;      // null = inneværende periode
  const UKEDAG = ["ma", "ti", "on", "to", "fr", "lø", "sø"];

  function settDagbokModus(modus) {
    dagbokModus = modus;
    document.querySelectorAll("#dagbok-valg button").forEach((b) => b.classList.toggle("valgt", b.dataset.modus === modus));
    document.querySelectorAll("#v-dagbok .dag-del").forEach((e) => { e.hidden = modus !== "dag"; });
    $("periode").hidden = modus === "dag";
    if (modus !== "dag") lastPeriode();
  }
  document.querySelectorAll("#dagbok-valg button").forEach((b) =>
    b.addEventListener("click", () => { vibrer(); periodeDato = null; settDagbokModus(b.dataset.modus); }));

  async function lastPeriode() {
    try {
      const p = await api(`api/periode?type=${dagbokModus}` + (periodeDato ? `&dato=${periodeDato}` : ""));
      tegnPeriode(p);
    } catch (e) { visToast(e.message, []); }
  }
  $("p-forrige").addEventListener("click", () => { periodeDato = $("p-forrige").dataset.dato; lastPeriode(); });
  $("p-neste").addEventListener("click", () => { periodeDato = $("p-neste").dataset.dato || null; lastPeriode(); });

  function aapneDag(iso) {
    vibrer();
    visDag = iso >= data.i_dag ? null : iso;
    settDagbokModus("dag");
    last();
  }

  function dagEtikett(p, r, i) {
    const [y, m, d] = r.dag.split("-").map(Number);
    if (p.type === "uke") return UKEDAG[i];
    return (d === 1 || d % 5 === 0) ? String(d) : "";
  }

  function tegnSoyler(boks, p, verdi, tekst, ref) {
    const vist = p.dager.map((r) => (r.framtid || r.for_fodsel ? null : verdi(r)));
    const maks = Math.max(1, ...vist.filter((v) => v != null), ref ? ref.normal[1] : 0);
    const pst = (v) => `${Math.min(100, (v / maks) * 100)}%`;
    const deler = [];
    if (ref) deler.push(el("div", { class: "soyle-omr" },
      el("div", { class: "soyle-band", style: `bottom:${pst(ref.vanlig[0])};height:calc(${pst(ref.vanlig[1])} - ${pst(ref.vanlig[0])})` })));
    const kolonner = el("div", { class: `soyle-rad${p.type === "maaned" ? " tett" : ""}` },
      ...p.dager.map((r, i) => {
        const v = vist[i];
        return el("button", { class: `soyle${r.i_dag ? " i-dag" : ""}`, disabled: v == null, title: v == null ? "" : `${dagTittel(r.dag)}: ${tekst(v)}`,
          onclick: () => aapneDag(r.dag) },
          el("span", { class: "soyle-verdi" }, p.type === "uke" && v ? tekst(v) : ""),
          el("span", { class: "soyle-plass" }, el("span", { class: "soyle-stolpe", style: `height:${v ? pst(v) : "0"}` })),
          el("span", { class: "soyle-dag" }, dagEtikett(p, r, i)));
      }));
    boks.replaceChildren(el("div", { class: "soyle-flate" }, ...deler, kolonner));
  }

  function tegnRytme(p) {
    const rader = p.dager.filter((r) => !r.framtid && !r.for_fodsel).map((r, i) => {
      const start = dagStart(r.dag), lengde = dagStart(flyttDag(r.dag, 1)) - start;
      const pos = (t) => Math.min(100, Math.max(0, ((t - start) / lengde) * 100));
      const naa = Date.now();
      const stripe = el("div", { class: "stripe liten" });
      for (const [kat, s0, e0, tiss, baesj] of r.blokker || []) {
        const s = new Date(s0).getTime(), e = e0 ? new Date(e0).getTime() : naa;
        if (kat === "sovn") stripe.append(el("div", { class: "blokk sovn", style: `left:${pos(s)}%;width:${Math.max(0.5, pos(e) - pos(s))}%` }));
        else if (kat === "mat") stripe.append(el("div", { class: "blokk mat", style: `left:${pos(s)}%;width:${Math.max(0.8, pos(e) - pos(s))}%` }));
        else {
          if (tiss) stripe.append(el("div", { class: "prikk tiss", style: `left:${pos(s)}%` }));
          if (baesj) stripe.append(el("div", { class: "prikk baesj", style: `left:${pos(s)}%` }));
        }
      }
      const [, , d] = r.dag.split("-").map(Number);
      const ukedag = UKEDAG[(new Date(r.dag + "T12:00").getDay() + 6) % 7];
      return el("button", { class: `rytme-rad${r.i_dag ? " i-dag" : ""}`, onclick: () => aapneDag(r.dag) },
        el("span", { class: "rytme-dag" }, `${ukedag} ${d}.`), stripe);
    });
    $("p-rytme").classList.toggle("tett", p.type === "maaned");
    $("p-rytme").replaceChildren(...(rader.length ? rader : [el("p", { class: "tom" }, "Ingen dager å vise ennå.")]));
  }

  function tegnPeriode(p) {
    $("p-tittel").textContent = p.tittel;
    $("p-under").textContent = p.under;
    $("p-forrige").dataset.dato = p.forrige;
    $("p-neste").dataset.dato = p.neste || "";
    $("p-neste").disabled = !p.neste;

    const s = p.snitt, tom = s.sovn_timer == null;
    $("p-sovn").textContent = tom ? "–" : minTekst(s.sovn_timer * 60);
    $("p-mat").textContent = tom ? "–" : String(s.maltider).replace(".", ",");
    $("p-tiss").textContent = tom ? "–" : String(s.tiss).replace(".", ",");
    $("p-baesj").textContent = tom ? "–" : String(s.baesj).replace(".", ",");
    $("p-mat-under").textContent = "måltider per døgn" + (!tom && s.ml ? ` · ${Math.round(s.ml)} ml` : "");
    const t = p.totalt;
    $("p-totalt").textContent = tom
      ? "Ingen registreringer i denne perioden."
      : `Snitt av ${p.dager_i_snitt} ${p.dager_i_snitt === 1 ? "døgn" : "hele døgn"}. Totalt: ${varighet(t.sovn_sek, true)} søvn, ${t.maltider} måltider${t.ml ? ` (${t.ml} ml)` : ""}, ${t.bleier} bleier.`;

    const ref = p.sovn_referanse;
    tegnSoyler($("p-sovn-graf"), p, (r) => (r.har_data ? r.sovn_sek / 3600 : null), (v) => `${v.toFixed(1).replace(".", ",")} t`, ref);
    $("p-sovn-ref").textContent = ref
      ? `Feltet viser det vanlige for ${ref.aldersgruppe}: ${ref.vanlig[0]}–${ref.vanlig[1]} timer i døgnet (Helsenorge).`
      : "";
    tegnSoyler($("p-mat-graf"), p, (r) => (r.har_data ? r.maltider : null), (v) => String(v), null);
    tegnRytme(p);
  }

  $("dag-forrige").addEventListener("click", () => { visDag = flyttDag(data.oppsummering.dag, -1); last(); });
  $("dag-neste").addEventListener("click", () => {
    const ny = flyttDag(data.oppsummering.dag, 1);
    visDag = ny >= data.i_dag ? null : ny;
    last();
  });
  $("legg-til").addEventListener("click", () => leggTilArk());
  // ---------------------------------------------------------------- kalender: hopp til en dag
  const MND_NAVN = ["januar", "februar", "mars", "april", "mai", "juni", "juli", "august",
    "september", "oktober", "november", "desember"];

  function kalenderArk(valgt) {
    const i_dag = data.i_dag;
    valgt = valgt || i_dag;
    let maaned = valgt.slice(0, 8) + "01";
    const tittel = el("h3", { class: "kal-tittel" });
    const forrige = el("button", { class: "ikonknapp liten", "aria-label": "Forrige måned" }, ikon("venstre"));
    const neste = el("button", { class: "ikonknapp liten", "aria-label": "Neste måned" }, ikon("hoyre"));
    const rutenett = el("div", { class: "kal-rutenett" });

    async function tegn() {
      const [y, m] = maaned.split("-").map(Number);
      tittel.textContent = `${MND_NAVN[m - 1][0].toUpperCase()}${MND_NAVN[m - 1].slice(1)} ${y}`;
      let p;
      try { p = await api(`api/periode?type=maaned&dato=${maaned}`); }
      catch (e) { visToast(e.message, []); return; }
      forrige.dataset.dato = p.forrige;
      neste.dataset.dato = p.neste || "";
      neste.disabled = !p.neste;
      forrige.disabled = p.dager[0].for_fodsel;
      const tomme = (new Date(y, m - 1, 1).getDay() + 6) % 7;
      rutenett.replaceChildren(
        ...UKEDAG.map((u) => el("span", { class: "kal-ukedag" }, u)),
        ...Array.from({ length: tomme }, () => el("span")),
        ...p.dager.map((r) => {
          const nr = Number(r.dag.slice(8));
          const av = r.framtid || r.for_fodsel;
          return el("button", {
            class: `kal-dag${r.dag === valgt ? " valgt" : ""}${r.i_dag ? " i-dag" : ""}${r.har_data ? " data" : ""}`,
            disabled: av,
            "aria-label": dagTittel(r.dag),
            onclick: () => { lukkArk(); aapneDag(r.dag); },
          }, String(nr), el("span", { class: "kal-prikk" }));
        }),
      );
    }
    forrige.addEventListener("click", () => { maaned = forrige.dataset.dato; tegn(); });
    neste.addEventListener("click", () => { if (neste.dataset.dato) { maaned = neste.dataset.dato; tegn(); } });

    aapneArk(
      el("div", { class: "kal-hode" }, forrige, tittel, neste),
      rutenett,
      el("p", { class: "hint" }, "Dager med prikk har registreringer. Trykk på en dag for å åpne den."),
      el("div", { class: "ark-knapper" },
        el("button", { class: "knapp sekundaer kal-idag", onclick: () => { lukkArk(); aapneDag(i_dag); } }, "Gå til i dag")),
    );
    tegn();
  }
  $("dag-velg").addEventListener("click", () => { vibrer(); kalenderArk(data.oppsummering.dag); });
  $("p-velg").addEventListener("click", () => {
    vibrer();
    kalenderArk(periodeDato || data.i_dag);
  });


  // ---------------------------------------------------------------- bunnark
  function aapneArk(...innhold) {
    skjulToast();
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
    if (h.kategori === "sovn" && data && data.lyd && data.lyd.aktiv) {
      state.detaljer.sted = state.detaljer.sted || "seng";
      state.detaljer.stoykilde = state.detaljer.stoykilde || "ingen";
      deler.push(el("div", { class: "ark-etikett" }, "Hvor"), velgRad(SOVN_STED, state.detaljer, "sted"),
        el("div", { class: "ark-etikett" }, "Støykilde"), velgRad(STOY, state.detaljer, "stoykilde"));
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

  // ---------------------------------------------------------------- målinger
  const MAAL = {
    vekt:       { navn: "Vekt",        enhet: "g",  steg: 10,  desimaler: 0, hint: "f.eks. 3540" },
    lengde:     { navn: "Lengde",      enhet: "cm", steg: 0.5, desimaler: 1, hint: "f.eks. 51,5" },
    hode:       { navn: "Hodeomkrets", enhet: "cm", steg: 0.5, desimaler: 1, hint: "f.eks. 35" },
    temperatur: { navn: "Temperatur",  enhet: "°C", steg: 0.1, desimaler: 1, hint: "f.eks. 37,4" },
  };
  const P_Z = { 3: -1.8808, 10: -1.2816, 25: -0.6745, 50: 0, 75: 0.6745, 90: 1.2816, 97: 1.8808 };
  let maalData = null, vekstdata = null, valgtGraf = "vekt";

  const tall = (v, des) => Number(v).toLocaleString("nb-NO", { minimumFractionDigits: des, maximumFractionDigits: des });
  const visVerdi = (type, v) => type === "vekt" && v >= 1000
    ? `${tall(v / 1000, 3)} kg`
    : `${tall(v, MAAL[type].desimaler)} ${MAAL[type].enhet}`;
  const datoKort = (iso) => new Date(iso).toLocaleDateString("nb-NO", { day: "numeric", month: "short" });

  async function lastMaalinger() {
    try {
      const [m, v] = await Promise.all([api("api/maalinger"), vekstdata ? Promise.resolve(vekstdata) : fetch("static/vekstdata.json").then((r) => r.json())]);
      maalData = m; vekstdata = v;
      tegnMaalinger();
    } catch (e) { visToast(e.message, []); }
  }

  // LMS-hjelpere (WHO): verdi for z, z for verdi, normalfordeling
  function lms(type, dag) {
    const tab = vekstdata[data.innstillinger.kjonn][type];
    if (dag <= tab[0][0]) return tab[0].slice(1);
    for (let i = 1; i < tab.length; i++) {
      if (dag <= tab[i][0]) {
        const [d0, ...a] = tab[i - 1], [d1, ...b] = tab[i];
        const f = (dag - d0) / (d1 - d0);
        return a.map((x, k) => x + (b[k] - x) * f);
      }
    }
    return tab[tab.length - 1].slice(1);
  }
  const fraZ = ([L, M, S], z) => (L ? M * Math.pow(1 + L * S * z, 1 / L) : M * Math.exp(S * z));
  const tilZ = ([L, M, S], x) => (L ? (Math.pow(x / M, L) - 1) / (L * S) : Math.log(x / M) / S);
  function phi(z) { // standard normalfordeling (Abramowitz–Stegun)
    const t = 1 / (1 + 0.2316419 * Math.abs(z));
    const d = 0.3989423 * Math.exp(-z * z / 2);
    const p = d * t * (0.3193815 + t * (-0.3565638 + t * (1.781478 + t * (-1.821256 + t * 1.330274))));
    return z > 0 ? 1 - p : p;
  }
  function alderDager(iso) {
    const f = data.innstillinger.fodselsdato;
    if (!f) return null;
    const [y, m, d] = f.split("-").map(Number);
    return (new Date(iso).getTime() - new Date(y, m - 1, d).getTime()) / 864e5;
  }
  function persentilTekst(type, verdi, tid) {
    if (type === "temperatur" || !data.innstillinger.kjonn || !vekstdata) return "";
    const a = alderDager(tid);
    if (a === null || a < 0 || a > 731) return "";
    const x = type === "vekt" ? verdi / 1000 : verdi;
    const p = phi(tilZ(lms(type, a), x)) * 100;
    if (p < 3) return "under 3. persentil";
    if (p > 97) return "over 97. persentil";
    return `ca. ${Math.round(p)}. persentil`;
  }

  function tegnMaalinger() {
    if (!maalData) return;
    // vurderinger
    const kilder = maalData.kilder;
    $("vurderinger").replaceChildren(...maalData.vurderinger.map((v) =>
      el("div", { class: `vurdering ${v.niva}` }, ikon("info"),
        el("div", {}, v.tekst, " ", kilder[v.kilde] ? el("a", { href: kilder[v.kilde].url, target: "_blank", rel: "noopener" }, `Kilde: ${kilder[v.kilde].navn.split(":")[0]}`) : null))));
    document.querySelectorAll("#graf-valg button").forEach((b) => b.classList.toggle("valgt", b.dataset.type === valgtGraf));

    const liste = maalData.maalinger.filter((m) => m.type === valgtGraf);
    const siste = liste[liste.length - 1];
    $("graf-siste").replaceChildren(...(siste ? [
      el("div", { class: "stor" }, visVerdi(valgtGraf, siste.verdi)),
      el("div", { class: "liten" }, [datoKort(siste.tid), persentilTekst(valgtGraf, siste.verdi, siste.tid)].filter(Boolean).join(" · ")),
    ] : []));

    $("graf").replaceChildren(valgtGraf === "temperatur" ? tempGraf(liste) : vekstGraf(valgtGraf, liste));
    const note = $("graf-note");
    if (valgtGraf === "temperatur") {
      note.replaceChildren("Feber er 38,0 °C eller mer målt i endetarmen. Kontakt lege hvis et barn som er 3 måneder eller yngre har feber. ",
        el("a", { href: kilder.helsenorge_feber.url, target: "_blank", rel: "noopener" }, "Kilde: Helsenorge"));
    } else if (!data.innstillinger.kjonn || !data.innstillinger.fodselsdato) {
      note.textContent = "Velg kjønn og legg inn fødselsdato i innstillingene for å se vekstkurver.";
    } else {
      const ekstra = valgtGraf === "hode" ? " Helsestasjonen bruker den norske kurven fra Vekststudien i Bergen for hodeomkrets, så tallene kan avvike litt." : "";
      note.replaceChildren(`Linjene viser 3., 10., 25., 50., 75., 90. og 97. persentil fra WHOs vekststandard, som Helsedirektoratet anbefaler for helsestasjonene.${ekstra} Kurvene gjelder barn født til termin. Det viktigste er at barnet følger sin egen kurve. `,
        el("a", { href: kilder.hdir_veiing.url, target: "_blank", rel: "noopener" }, "Kilde: Helsedirektoratet"));
    }

    $("maal-liste").replaceChildren(...[...liste].reverse().map((m) => el("li", {},
      el("button", { class: "rad", onclick: () => maalArk(m.type, m) },
        el("span", { class: "rad-tekst" },
          el("div", { class: "rad-tittel" }, visVerdi(m.type, m.verdi)),
          el("div", { class: "rad-under" }, [persentilTekst(m.type, m.verdi, m.tid), m.notat, m.av].filter(Boolean).join(" · "))),
        el("span", { class: "rad-tid" }, datoKort(m.tid))))));
  }

  const SVG = (tag, attrs = {}) => {
    const e = document.createElementNS(SVGNS, tag);
    for (const [k, v] of Object.entries(attrs)) e.setAttribute(k, v);
    return e;
  };

  function vekstGraf(type, liste) {
    const B = 340, H = 230, pl = 34, pr = 26, pt = 10, pb = 24;
    const kanKurver = data.innstillinger.kjonn && data.innstillinger.fodselsdato && vekstdata;
    const punkter = liste.map((m) => ({ x: alderDager(m.tid), y: type === "vekt" ? m.verdi / 1000 : m.verdi }))
      .filter((p) => p.x !== null && p.x >= -1);
    if (!kanKurver && !punkter.length) return el("div", { class: "graf-tom" }, "Ingen målinger ennå. Trykk på en av knappene over.");
    const naaAlder = data.alder ? Math.max(0, data.alder.dager) : 0;
    const xMaks = Math.min(731, Math.max(91, naaAlder + 30, ...punkter.map((p) => p.x + 14)));
    const steg = xMaks > 200 ? 14 : 7;
    const kurver = {};
    let yMin = Infinity, yMaks = -Infinity;
    if (kanKurver) {
      for (const p of Object.keys(P_Z)) {
        kurver[p] = [];
        for (let d = 0; d <= xMaks; d += steg) {
          const v = fraZ(lms(type, d), P_Z[p]);
          kurver[p].push([d, v]);
          yMin = Math.min(yMin, v); yMaks = Math.max(yMaks, v);
        }
      }
    }
    for (const p of punkter) { yMin = Math.min(yMin, p.y); yMaks = Math.max(yMaks, p.y); }
    const pad = (yMaks - yMin) * 0.06 || 1;
    yMin -= pad; yMaks += pad;
    const X = (d) => pl + (d / xMaks) * (B - pl - pr);
    const Y = (v) => pt + (1 - (v - yMin) / (yMaks - yMin)) * (H - pt - pb);
    const svg = SVG("svg", { viewBox: `0 0 ${B} ${H}`, role: "img", "aria-label": `${MAAL[type].navn} med vekstkurver` });

    // rutenett og akser
    const yTrinn = (yMaks - yMin) > 20 ? 5 : (yMaks - yMin) > 6 ? 2 : (yMaks - yMin) > 3 ? 1 : 0.5;
    for (let v = Math.ceil(yMin / yTrinn) * yTrinn; v <= yMaks; v += yTrinn) {
      svg.append(SVG("line", { class: "rutenett", x1: pl, x2: B - pr, y1: Y(v), y2: Y(v) }));
      const t = SVG("text", { class: "akse-tekst", x: pl - 6, y: Y(v) + 3, "text-anchor": "end" });
      t.textContent = tall(v, yTrinn < 1 ? 1 : 0); svg.append(t);
    }
    const iMnd = xMaks > 120;
    const xTrinn = iMnd ? (xMaks > 400 ? 91.3 : 30.44) : 14;
    for (let d = 0; d <= xMaks + 0.1; d += xTrinn) {
      const t = SVG("text", { class: "akse-tekst", x: X(d), y: H - 6, "text-anchor": "middle" });
      t.textContent = iMnd ? `${Math.round(d / 30.44)} mnd` : `${Math.round(d / 7)} u`;
      svg.append(t);
    }
    const enhet = SVG("text", { class: "akse-tekst", x: pl - 6, y: pt - 1, "text-anchor": "end" });
    enhet.textContent = type === "vekt" ? "kg" : "cm"; svg.append(enhet);

    if (kanKurver) {
      const sti = (pts) => pts.map(([d, v], i) => `${i ? "L" : "M"}${X(d).toFixed(1)},${Y(v).toFixed(1)}`).join("");
      const band = sti(kurver[3]) + [...kurver[97]].reverse().map(([d, v]) => `L${X(d).toFixed(1)},${Y(v).toFixed(1)}`).join("") + "Z";
      svg.append(SVG("path", { class: "p-band", d: band }));
      for (const p of Object.keys(P_Z)) {
        svg.append(SVG("path", { class: `p-linje${p === "50" ? " median" : ""}`, d: sti(kurver[p]) }));
        const siste = kurver[p][kurver[p].length - 1];
        const t = SVG("text", { class: "p-tekst", x: B - pr + 3, y: Y(siste[1]) + 3 });
        t.textContent = p; svg.append(t);
      }
    }
    if (punkter.length > 1) {
      svg.append(SVG("path", { class: "baby-linje", d: punkter.map((p, i) => `${i ? "L" : "M"}${X(p.x).toFixed(1)},${Y(p.y).toFixed(1)}`).join("") }));
    }
    for (const p of punkter) svg.append(SVG("circle", { class: "baby-punkt", cx: X(p.x), cy: Y(p.y), r: 4.5 }));
    return svg;
  }

  function tempGraf(liste) {
    const naa = Date.now(), fra = naa - 7 * 864e5;
    const pts = liste.filter((m) => new Date(m.tid).getTime() >= fra).map((m) => ({ x: new Date(m.tid).getTime(), y: m.verdi }));
    if (!pts.length) return el("div", { class: "graf-tom" }, "Ingen temperaturmålinger siste 7 dager.");
    const B = 340, H = 180, pl = 34, pr = 10, pt = 10, pb = 24;
    const yMin = Math.min(36, ...pts.map((p) => p.y)) - 0.3, yMaks = Math.max(38.6, ...pts.map((p) => p.y)) + 0.3;
    const X = (t) => pl + ((t - fra) / (naa - fra)) * (B - pl - pr);
    const Y = (v) => pt + (1 - (v - yMin) / (yMaks - yMin)) * (H - pt - pb);
    const svg = SVG("svg", { viewBox: `0 0 ${B} ${H}`, role: "img", "aria-label": "Temperatur siste 7 dager" });
    for (let v = Math.ceil(yMin); v <= yMaks; v += 1) {
      svg.append(SVG("line", { class: "rutenett", x1: pl, x2: B - pr, y1: Y(v), y2: Y(v) }));
      const t = SVG("text", { class: "akse-tekst", x: pl - 6, y: Y(v) + 3, "text-anchor": "end" }); t.textContent = `${v}°`; svg.append(t);
    }
    svg.append(SVG("line", { class: "feber-linje", x1: pl, x2: B - pr, y1: Y(38), y2: Y(38) }));
    for (let i = 0; i <= 7; i += 1) {
      const d = new Date(fra + i * 864e5);
      if (i % 2) continue;
      const t = SVG("text", { class: "akse-tekst", x: X(d.getTime()), y: H - 6, "text-anchor": "middle" });
      t.textContent = d.toLocaleDateString("nb-NO", { weekday: "short" }); svg.append(t);
    }
    if (pts.length > 1) svg.append(SVG("path", { class: "temp-linje", d: pts.map((p, i) => `${i ? "L" : "M"}${X(p.x).toFixed(1)},${Y(p.y).toFixed(1)}`).join("") }));
    for (const p of pts) svg.append(SVG("circle", { class: "temp-punkt", cx: X(p.x), cy: Y(p.y), r: 4 }));
    return svg;
  }

  function maalArk(type, eksisterende = null) {
    const def = MAAL[type];
    const listeType = maalData ? maalData.maalinger.filter((m) => m.type === type) : [];
    const forrige = listeType[listeType.length - 1];
    const startVerdi = eksisterende ? eksisterende.verdi : (forrige && type !== "temperatur" ? forrige.verdi : "");
    const input = el("input", { type: "text", inputmode: "decimal", placeholder: def.hint, value: startVerdi === "" ? "" : String(startVerdi).replace(".", ",") });
    const tidIso = eksisterende ? eksisterende.tid : new Date().toISOString();
    const lokal = (iso) => { const d = new Date(iso); d.setMinutes(d.getMinutes() - d.getTimezoneOffset()); return d.toISOString().slice(0, 16); };
    const tid = el("input", { type: "datetime-local", value: lokal(tidIso) });
    const notat = el("input", { type: "text", placeholder: type === "temperatur" ? "f.eks. målt i endetarmen" : "f.eks. helsestasjonen", value: eksisterende && eksisterende.notat ? eksisterende.notat : "", maxlength: "200" });
    const juster = (n) => {
      const v = parseFloat((input.value || String(startVerdi || 0)).replace(",", ".")) || 0;
      input.value = tall(Math.max(0, v + n * def.steg), def.desimaler).replace(/\s/g, "");
    };
    const lagre = async () => {
      const body = { type, verdi: input.value.replace(/\s/g, "").replace(",", "."), tid: new Date(tid.value).toISOString(), notat: notat.value };
      try {
        if (eksisterende) await api(`api/maalinger/${eksisterende.id}`, { method: "PATCH", body });
        else await api("api/maalinger", { method: "POST", body });
        lukkArk();
        valgtGraf = type;
        await lastMaalinger();
        visToast(`${def.navn} lagret`, [], 2500);
      } catch (e) { visToast(e.message, []); }
    };
    let sikker = false;
    const slett = eksisterende ? el("button", { class: "knapp fare", onclick: async (e) => {
      if (!sikker) { sikker = true; e.target.textContent = "Sikker?"; return; }
      try { await api(`api/maalinger/${eksisterende.id}`, { method: "DELETE" }); lukkArk(); await lastMaalinger(); visToast("Slettet", [], 2000); }
      catch (err) { visToast(err.message, []); }
    } }, "Slett") : null;
    aapneArk(
      el("h3", {}, eksisterende ? `Endre ${def.navn.toLowerCase()}` : def.navn),
      el("p", { class: "hint" }, type === "vekt" ? "Skriv inn vekten i gram." : type === "temperatur" ? "Helsenorge anbefaler å måle i endetarmen med digitalt termometer." : `Skriv inn i ${def.enhet}.`),
      el("div", { class: "felt stort-tall-felt" }, el("div", { class: "felt-wrap" }, input, el("span", { class: "enhet" }, def.enhet))),
      el("div", { class: "juster" },
        el("button", { type: "button", onclick: () => juster(-1) }, `−${tall(def.steg, def.desimaler)}`),
        el("button", { type: "button", onclick: () => juster(1) }, `+${tall(def.steg, def.desimaler)}`)),
      el("label", { class: "felt", style: "margin-top:14px" }, el("span", {}, "Tidspunkt"), tid),
      el("label", { class: "felt", style: "margin-top:10px" }, el("span", {}, "Notat (valgfritt)"), notat),
      el("div", { class: "ark-knapper" }, slett, el("button", { class: "knapp", style: "--aksent: var(--tiss)", onclick: lagre }, "Lagre")),
    );
    setTimeout(() => input.focus(), 250);
  }

  document.querySelectorAll(".maal-knapper button").forEach((b) => b.addEventListener("click", () => { vibrer(); maalArk(b.dataset.type); }));
  document.querySelectorAll("#graf-valg button").forEach((b) => b.addEventListener("click", () => { valgtGraf = b.dataset.type; tegnMaalinger(); }));


  // ---------------------------------------------------------------- lydgjenkjenning
  const SOVN_STED = { seng: "Seng", vogn: "Vogn", bil: "Bil", baeresele: "Bæresele" };
  const STOY = { ingen: "Ingen støy", vifte: "Vifte", hvit_stoy: "Hvit støy", annet: "Annen støy" };
  const ROLLER = {
    fast: ["Fast lytter", "Står fast der babyen sover, f.eks. på barnerommet."],
    flyttbar: ["Flyttbar", "Lytter som flyttes med babyen, f.eks. en iPad på reise eller ved vogna."],
    personlig: ["Personlig telefon", "Teller lite hjemme, men fullt når den er valgt som «ved babyen»."],
    motbevis: ["Motbevis (stua)", "Står i stua. Hører den gråt samtidig, er det trolig TV – da trekkes poeng."],
  };
  const STED_TRENGER_MED = ["hjemme_vogn", "ute", "reise", "barnevakt_ute"];

  function tegnLyd() {
    const lyd = data.lyd;
    const aktiv = !!(lyd && lyd.aktiv);
    const stedKnapp = $("sted-knapp");
    stedKnapp.hidden = !aktiv;
    if (aktiv) {
      const navn = Object.fromEntries(lyd.enheter.map((e) => [e.kilde, e.navn]));
      const med = lyd.sted.med.map((k) => navn[k] || k);
      $("sted-tekst").textContent = lyd.sted.navn + (med.length ? ` · ${med.join(", ")}` : "");
      stedKnapp.classList.toggle("varsle", STED_TRENGER_MED.includes(lyd.sted.sted) && !med.length);
    }

    const gj = $("gjennomgang");
    const forslag = aktiv ? lyd.forslag : [];
    gj.hidden = !forslag.length;
    gj.replaceChildren(...forslag.map((f) => el("div", { class: "forslag" },
      el("div", { class: "forslag-tekst" },
        el("b", {}, `Våknet ${kl(f.tid)}?`),
        el("span", {}, "Gråt registrert under søvnen. Bekreft, så lærer appen."),
      ),
      el("div", { class: "forslag-knapper" },
        el("button", { class: "knapp", onclick: () => svarForslag(f, "vaaknet") }, ikon("sol"), "Våknet"),
        el("button", { class: "knapp sekundaer", onclick: () => svarForslag(f, "sovnet_igjen") }, ikon("maane"), "Sovnet igjen"),
        el("button", { class: "knapp sekundaer", onclick: () => svarForslag(f, "feil") }, "Feil"),
      ),
    )));

    const chips = $("sovn-chips");
    const sovn = data.status.sovn;
    chips.hidden = !(aktiv && sovn);
    if (aktiv && sovn) {
      const d = sovn.detaljer || {};
      chips.replaceChildren(
        el("button", { class: "mini-chip", onclick: () => sovnInfoArk(sovn) }, SOVN_STED[d.sted] || "Seng"),
        el("button", { class: "mini-chip", onclick: () => sovnInfoArk(sovn) }, STOY[d.stoykilde] || "Ingen støy"),
      );
    }
  }

  async function svarForslag(f, svar) {
    vibrer();
    try {
      const r = await api(`api/lyd/forslag/${f.id}`, { method: "POST", body: { svar } });
      await last();
      visToast(r.melding, [], 2500);
    } catch (e) { visToast(e.message, []); }
  }

  function velgRad(valg, state, felt, ved) {
    const rad = el("div", { class: "chips" });
    const tegnV = () => rad.replaceChildren(...Object.entries(valg).map(([v, navn]) =>
      el("button", { class: `chip${state[felt] === v ? " valgt" : ""}`, onclick: () => { state[felt] = v; tegnV(); ved && ved(); } }, navn)));
    tegnV();
    return rad;
  }

  function sovnInfoArk(sovn) {
    const d = sovn.detaljer || {};
    const state = { sted: d.sted || "seng", stoykilde: d.stoykilde || "ingen" };
    aapneArk(
      el("h3", {}, "Om søvnen"),
      el("p", { class: "hint" }, "Hjelper appen å tolke lyd riktig. Støykilden huskes til neste gang."),
      el("div", { class: "ark-etikett" }, "Hvor sover babyen"),
      velgRad(SOVN_STED, state, "sted"),
      el("div", { class: "ark-etikett" }, "Støykilde i rommet"),
      velgRad(STOY, state, "stoykilde"),
      el("div", { class: "ark-knapper" },
        el("button", { class: "knapp", style: "--aksent: var(--sovn)", onclick: async () => {
          try {
            await api(`api/hendelser/${sovn.id}`, { method: "PATCH", body: { detaljer: { ...d, ...state } } });
            lukkArk(); await last(); visToast("Lagret", [], 2000);
          } catch (e) { visToast(e.message, []); }
        } }, "Lagre"),
      ),
    );
  }

  function stedArk() {
    const lyd = data.lyd;
    const state = { sted: lyd.sted.sted, med: new Set(lyd.sted.med) };
    const medEtikett = el("div", { class: "ark-etikett" });
    const medHint = el("p", { class: "hint" });
    const medRad = el("div", { class: "chips" });
    const tegnMed = () => {
      const trenger = STED_TRENGER_MED.includes(state.sted);
      medEtikett.textContent = trenger ? "Enheter som er med babyen" : "Enheter ved babyen (valgfritt)";
      medHint.textContent = trenger
        ? "Bare disse teller nå. Velger du ingen, registreres ingen lyd før dere er hjemme igjen."
        : "Den faste lytteren teller alltid. Velg andre enheter her hvis de står ved babyen.";
      medRad.replaceChildren(...lyd.enheter.filter((e) => e.rolle !== "motbevis").map((e) =>
        el("button", { class: `chip${state.med.has(e.kilde) ? " valgt" : ""}`, onclick: () => {
          state.med.has(e.kilde) ? state.med.delete(e.kilde) : state.med.add(e.kilde); tegnMed();
        } }, e.navn)));
    };
    const steder = Object.fromEntries(lyd.steder.map((s) => [s.verdi, s.navn]));
    tegnMed();
    aapneArk(
      el("h3", {}, "Hvor er babyen?"),
      el("p", { class: "hint" }, "Bare enheter der babyen er, teller som lyd. Barnevakt? Velg det her før dere går."),
      velgRad(steder, state, "sted", tegnMed),
      medEtikett, medHint, medRad,
      el("div", { class: "ark-knapper" },
        el("button", { class: "knapp", style: "--aksent: var(--sovn)", onclick: async () => {
          try {
            await api("api/lyd/sted", { method: "PUT", body: { sted: state.sted, med: [...state.med] } });
            lukkArk(); await last(); visToast("Sted lagret", [], 2000);
          } catch (e) { visToast(e.message, []); }
        } }, "Lagre"),
      ),
    );
  }
  $("sted-knapp").addEventListener("click", () => { vibrer(); stedArk(); });

  const TOLKNING = {
    avvist: "Avvist", vaaken: "Gråt mens våken", innsovning: "Urolig innsovning", uro: "Uro i søvne",
    mulig: "Mulig oppvåkning", trolig: "Trolig våknet", motbevis: "Motbevis (stua)",
  };
  const FORSLAG_STATUS = {
    venter: "Venter", vaaknet: "Våknet", sovnet_igjen: "Sovnet igjen", feil: "Feil",
    manuelt_vaaknet: "Våknet (trykket selv)", auto: "Avsluttet automatisk", utlopt: "Utløpt",
  };

  async function lydloggArk() {
    let d;
    try { d = await api("api/lyd/logg"); } catch (e) { visToast(e.message, []); return; }
    const pros = (l) => l.presisjon == null ? "for få svar ennå" : `${Math.round(l.presisjon * 100)} % riktige av ${l.antall} svar`;
    const just = (l) => l.justering ? ` · terskel ${l.justering > 0 ? "+" : ""}${l.justering}` : "";
    aapneArk(
      el("h3", {}, "Lydlogg"),
      el("p", { class: "hint" }, "Alle meldinger fra lytteenhetene, også de som ble avvist, og hvorfor."),
      el("div", { class: "ark-etikett" }, "Treffsikkerhet"),
      el("ul", { class: "liste-enkel" },
        el("li", {}, `Uten støykilde: ${pros(d.laering.uten_stoy)}${just(d.laering.uten_stoy)}`),
        el("li", {}, `Med støykilde: ${pros(d.laering.med_stoy)}${just(d.laering.med_stoy)}`),
      ),
      d.per_enhet.length ? el("div", { class: "ark-etikett" }, "Per enhet, siste 14 dager") : null,
      d.per_enhet.length ? el("ul", { class: "liste-enkel" }, d.per_enhet.map((e) =>
        el("li", {}, `${e.enhet}: ${e.totalt} meldinger, ${e.avvist} avvist`))) : null,
      d.forslag.length ? el("div", { class: "ark-etikett" }, "Siste forslag") : null,
      d.forslag.length ? el("ul", { class: "liste-enkel" }, d.forslag.map((f) =>
        el("li", {}, `${new Date(f.tid).toLocaleString("nb-NO", { weekday: "short", hour: "2-digit", minute: "2-digit" })} · ${FORSLAG_STATUS[f.status] || f.status} · ${f.poeng} p`))) : null,
      el("div", { class: "ark-etikett" }, "Siste meldinger"),
      d.logg.length ? el("ul", { class: "liste-enkel" }, d.logg.map((r) =>
        el("li", {},
          el("b", {}, `${kl(r.tid)} ${r.enhet}`),
          ` · ${r.type === "rop" ? "rop" : "gråt"} · ${TOLKNING[r.tolkning] || r.tolkning}`,
          r.poeng != null ? ` · ${r.poeng} p` : "",
          r.grunn ? el("div", { class: "dempet" }, r.grunn) : null,
        ))) : el("p", { class: "hint" }, "Ingen meldinger ennå. Test fra snarveien på en lytteenhet."),
    );
  }
  $("inn-lydlogg").addEventListener("click", () => lydloggArk());
  function kopiFelt(tekst) {
    const pre = el("pre", { class: "kode" }, tekst);
    const knapp = el("button", { class: "kopier", type: "button", onclick: async () => {
      try { await navigator.clipboard.writeText(tekst); knapp.textContent = "Kopiert"; }
      catch (_) {
        const r = document.createRange(); r.selectNodeContents(pre);
        const sel = getSelection(); sel.removeAllRanges(); sel.addRange(r);
        knapp.textContent = "Merket – kopier";
      }
      setTimeout(() => { knapp.textContent = "Kopier"; }, 2500);
    } }, "Kopier");
    return el("div", { class: "kode-boks" }, pre, knapp);
  }

  function steg(nr, tittel, ...innhold) {
    return el("li", { class: "steg" },
      el("span", { class: "steg-nr" }, String(nr)),
      el("div", { class: "steg-innhold" }, el("b", {}, tittel), ...innhold));
  }

  function lydGuideArk() {
    const enheter = (skjemaState.lyd && skjemaState.lyd.enheter) || (data.innstillinger.lyd.enheter || []);
    const lyttere = enheter;
    const p = (t) => el("p", {}, t);
    const punkt = (...l) => el("ul", { class: "liste-enkel prikker" }, l.map((t) => el("li", {}, t)));

    const perEnhet = lyttere.length ? lyttere.map((e) => el("div", { class: "enhet-guide" },
      el("div", { class: "ark-etikett" }, `${e.navn} (${ROLLER[e.rolle][0].toLowerCase()})`),
      el("p", { class: "dempet" }, "Data for «Baby som gråter»:"),
      kopiFelt(JSON.stringify({ type: "grat", kilde: e.kilde })),
      el("p", { class: "dempet" }, "Data for «Roping»:"),
      kopiFelt(JSON.stringify({ type: "rop", kilde: e.kilde })),
    )) : [el("p", { class: "dempet" }, "Legg til en enhet først (steg 1), så vises ferdig tekst for hver enhet her.")];

    const android = lyttere.length ? lyttere[0].kilde : "android_barnerom";
    const yaml = `alias: Babyuret – lyd fra Android
triggers:
  - trigger: state
    entity_id: sensor.DIN_TELEFON_last_notification
conditions:
  - condition: template
    value_template: >
      {{ 'baby' in (trigger.to_state.state | lower) }}
actions:
  - event: babyuret_lyd
    event_data:
      type: grat
      kilde: ${android}
mode: queued`;

    aapneArk(
      el("h3", {}, "Slik bruker du lydgjenkjenning"),
      el("p", { class: "hint" }, "Gråt og rop blir data til søvnloggen. Appen varsler ikke – bruk babycall til det."),
      el("ol", { class: "steg-liste" },
        steg(1, "Legg inn enhetene her i appen",
          p("Under Lydgjenkjenning: slå på, trykk «Legg til enhet» for hver telefon eller iPad som skal lytte, og trykk Lagre nederst."),
          punkt("Fast lytter: står fast der babyen sover.",
            "Flyttbar: følger babyen, f.eks. iPaden på reise eller ved vogna.",
            "Personlig telefon: teller lite hjemme, fullt når den er valgt som «med babyen».",
            "Motbevis: en enhet i stua som avslører gråt fra TV."),
          p("Kilde-navnet (små bokstaver) er det enheten bruker for å si hvem den er.")),
        steg(2, "Slå på Lydgjenkjenning på iPhone/iPad",
          p("Innstillinger → Tilgjengelighet → Lydgjenkjenning → slå på. Under «Lyder»: slå på «Baby som gråter» og «Roping»."),
          punkt("«Hei Siri» virker ikke mens Lydgjenkjenning er på.", "La enheten stå på lading – den lytter hele tiden.")),
        steg(3, "Lag snarvei-automasjonen",
          p("Snarveier → Automatisering → Ny automatisering → Lydgjenkjenning → velg «Baby som gråter» → «Kjør umiddelbart». Skru av «Varsle når den kjøres»."),
          p("Ny tom snarvei → Legg til handling → søk «Home Assistant» → «Fire Event». Hendelse: babyuret_lyd. Lim inn dataene for enheten under."),
          p("Lag en ny automasjon på samme måte for «Roping» med rop-dataene."),
          ...perEnhet),
        steg(4, "Gammel Android-telefon (valgfritt)",
          p("Slå på Lydvarsler (appen Live Transcribe & Notifications) og velg babylyder. I Home Assistant-appen: slå på sensoren «Last notification». Lag så denne automasjonen i Home Assistant, med riktig sensor og kilde:"),
          kopiFelt(yaml)),
        steg(5, "Test at det virker",
          p("Spill av babygråt (f.eks. fra YouTube) like ved enheten. Åpne «Lydlogg og treffsikkerhet»: meldingen skal dukke opp i løpet av noen sekunder."),
          punkt("«Gråt mens våken» betyr at alt virker – babyen er bare ikke registrert som sovende.",
            "«Avvist» har grunnen skrevet under, f.eks. ukjent enhet eller ikke på hjemmenettet.",
            "Ingen melding? Sjekk at snarveien kjører, og at kilde-navnet er stavet likt.")),
        steg(6, "I hverdagen",
          punkt("Trykk «Sover» som før. Mens babyen sover kan du trykke på «Seng» og «Ingen støy» i statuskortet for å endre sted og støykilde.",
            "Knappen øverst på forsiden viser hvor babyen er. Endre den når dere går ut, reiser eller har barnevakt, og velg hvilke enheter som er med babyen. Blir den oransje, mangler det en enhet.",
            "«Våknet kl. …?» vises øverst når appen tror babyen har våknet. Svar Våknet, Sovnet igjen eller Feil – svarene gjør appen mer treffsikker.",
            "Ubesvart etter 30 minutter avsluttes søvnen automatisk og merkes i dagboken, så du kan rette den.",
            "De første ukene: sjekk lydloggen innimellom og juster ved behov under «Avansert».")),
      ),
    );
  }
  $("inn-lydguide").addEventListener("click", () => { if (!skjemaState.lyd) fyllLyd(data.innstillinger.lyd); lydGuideArk(); });


  function enhetArk(indeks) {
    const liste = skjemaState.lyd.enheter;
    const ny = indeks == null;
    const e = ny ? { kilde: "", navn: "", rolle: "fast", nett_entitet: "" } : { ...liste[indeks] };
    const navn = el("input", { type: "text", maxlength: "40", value: e.navn, placeholder: "f.eks. Barnerommet", autocomplete: "off" });
    const kilde = el("input", { type: "text", maxlength: "30", value: e.kilde, placeholder: "f.eks. barnerom", autocomplete: "off", autocapitalize: "off" });
    const nett = el("input", { type: "text", value: e.nett_entitet, placeholder: "f.eks. sensor.ipad_ssid", autocomplete: "off", autocapitalize: "off" });
    const rolleHint = el("p", { class: "felt-hint" });
    const state = { rolle: e.rolle };
    const tegnRolle = () => { rolleHint.textContent = ROLLER[state.rolle][1]; };
    tegnRolle();
    let sikker = false;
    const slett = ny ? null : el("button", { class: "knapp fare", onclick: () => {
      if (!sikker) { sikker = true; slett.textContent = "Sikker?"; return; }
      liste.splice(indeks, 1); tegnEnheter(); lukkArk();
    } }, "Fjern");
    aapneArk(
      el("h3", {}, ny ? "Ny lytteenhet" : e.navn || e.kilde),
      el("p", { class: "hint" }, "Kilde-navnet skrives inn i snarveien på enheten. Husk å trykke Lagre i innstillingene etterpå."),
      el("label", { class: "felt" }, el("span", {}, "Navn"), navn),
      el("label", { class: "felt" }, el("span", {}, "Kilde (små bokstaver, tall og _)"), kilde),
      el("div", { class: "ark-etikett" }, "Rolle"),
      velgRad(Object.fromEntries(Object.entries(ROLLER).map(([k, v]) => [k, v[0]])), state, "rolle", tegnRolle),
      rolleHint,
      el("label", { class: "felt" }, el("span", {}, "Nett-sensor i Home Assistant (valgfritt)"), nett),
      el("p", { class: "felt-hint" }, "Wi-Fi-sensoren fra Home Assistant-appen, eller en device_tracker fra UniFi. Uten den regnes faste lyttere som hjemme."),
      el("div", { class: "ark-knapper" }, slett,
        el("button", { class: "knapp", style: "--aksent: var(--sovn)", onclick: () => {
          const ut = {
            navn: navn.value.trim() || kilde.value.trim(),
            kilde: kilde.value.trim().toLowerCase(),
            rolle: state.rolle,
            nett_entitet: nett.value.trim(),
          };
          if (!/^[a-z0-9_]{1,30}$/.test(ut.kilde)) { visToast("Kilde kan bare ha a–z, 0–9 og _", []); return; }
          if (liste.some((x, i) => x.kilde === ut.kilde && i !== indeks)) { visToast("Kilden er allerede i bruk", []); return; }
          if (ny) liste.push(ut); else liste[indeks] = ut;
          tegnEnheter(); lukkArk();
        } }, "OK"),
      ),
    );
  }
  $("inn-ny-enhet").addEventListener("click", () => enhetArk(null));

  function tegnEnheter() {
    const l = skjemaState.lyd;
    $("inn-enheter").replaceChildren(...l.enheter.map((e, i) => el("li", {},
      el("button", { class: "rad", type: "button", onclick: () => enhetArk(i) },
        el("span", { class: "rad-ikon k-sovn" }, ikon("ore")),
        el("span", { class: "rad-tekst" },
          el("div", { class: "rad-tittel" }, e.navn || e.kilde),
          el("div", { class: "rad-under" }, `${ROLLER[e.rolle][0]} · kilde: ${e.kilde}`)),
      ))));
    document.querySelectorAll("#inn-lyd-aktiv button").forEach((b) => b.classList.toggle("valgt", (b.dataset.verdi === "paa") === l.aktiv));
    document.querySelectorAll("#inn-lyd-laering button").forEach((b) => b.classList.toggle("valgt", (b.dataset.verdi === "paa") === l.laering));
    $("inn-lyd-detaljer").hidden = !l.aktiv;
  }
  document.querySelectorAll("#inn-lyd-aktiv button").forEach((b) =>
    b.addEventListener("click", () => { skjemaState.lyd.aktiv = b.dataset.verdi === "paa"; tegnEnheter(); }));
  document.querySelectorAll("#inn-lyd-laering button").forEach((b) =>
    b.addEventListener("click", () => { skjemaState.lyd.laering = b.dataset.verdi === "paa"; tegnEnheter(); }));

  const LYD_TALL = [["inn-lyd-innsovning", "innsovning_min"], ["inn-lyd-vindu", "vindu_min"],
    ["inn-lyd-mulig", "terskel_mulig"], ["inn-lyd-trolig", "terskel_trolig"],
    ["inn-lyd-frist", "svarfrist_min"], ["inn-lyd-rop", "rop_vekt"]];
  function fyllLyd(lyd) {
    skjemaState.lyd = JSON.parse(JSON.stringify(lyd));
    $("inn-hjemmenett").value = (lyd.hjemmenett || []).join(", ");
    for (const [id, felt] of LYD_TALL) $(id).value = lyd[felt];
    tegnEnheter();
  }
  function lesLyd() {
    const l = { ...skjemaState.lyd, hjemmenett: $("inn-hjemmenett").value };
    for (const [id, felt] of LYD_TALL) if ($(id).value !== "") l[felt] = Number($(id).value);
    return l;
  }

  // ---------------------------------------------------------------- faner
  const FANER = ["registrer", "dagbok", "maalinger", "innstillinger"];
  function visFane(navn, oppdaterHash = true) {
    if (!FANER.includes(navn)) navn = "registrer";
    skjulToast();
    for (const f of FANER) $(`v-${f}`).hidden = f !== navn;
    document.querySelectorAll("#faner button").forEach((b) => b.classList.toggle("valgt", b.dataset.fane === navn));
    if (oppdaterHash && location.hash !== `#${navn}`) history.replaceState(null, "", `#${navn}`);
    if (navn === "innstillinger") fyllInnstillinger();
    if (navn === "maalinger") lastMaalinger();
    if (navn !== "dagbok" && visDag) { visDag = null; last(); }
    window.scrollTo(0, 0);
  }
  document.querySelectorAll("#faner button").forEach((b) => b.addEventListener("click", () => { vibrer(); visFane(b.dataset.fane); }));
  $("velkommen").addEventListener("click", () => visFane("innstillinger"));

  // ---------------------------------------------------------------- innstillinger
  const skjemaState = { mating: "begge", ml: 90, kjonn: "", lyd: null };
  function tegnMating() {
    document.querySelectorAll("#inn-mating button").forEach((b) => b.classList.toggle("valgt", b.dataset.verdi === skjemaState.mating));
    document.querySelectorAll("#inn-kjonn button").forEach((b) => b.classList.toggle("valgt", b.dataset.verdi === skjemaState.kjonn));
    $("inn-ml-felt").hidden = skjemaState.mating === "amming";
    $("inn-ml").replaceChildren(String(skjemaState.ml), el("small", {}, " ml"));
  }
  function fyllInnstillinger() {
    if (!data) return;
    const inn = data.innstillinger;
    $("inn-navn").value = inn.baby_navn || "";
    $("inn-fodsel").value = inn.fodselsdato || "";
    $("inn-natt-fra").value = inn.nattmodus_fra;
    $("inn-natt-til").value = inn.nattmodus_til;
    skjemaState.mating = inn.mating;
    skjemaState.ml = inn.standard_flaske_ml;
    skjemaState.kjonn = inn.kjonn || "";
    tegnMating();
    fyllLyd(inn.lyd);
    if (!$("kilder").children.length) {
      api("api/kilder").then((k) => $("kilder").replaceChildren(...Object.values(k).map((x) =>
        el("li", {}, el("a", { href: x.url, target: "_blank", rel: "noopener" }, x.navn))))).catch(() => {});
    }
  }
  document.querySelectorAll("#inn-kjonn button").forEach((b) =>
    b.addEventListener("click", () => { skjemaState.kjonn = b.dataset.verdi; tegnMating(); }));
  document.querySelectorAll("#inn-mating button").forEach((b) =>
    b.addEventListener("click", () => { skjemaState.mating = b.dataset.verdi; tegnMating(); }));
  $("inn-ml-minus").addEventListener("click", () => { skjemaState.ml = Math.max(10, skjemaState.ml - 10); tegnMating(); });
  $("inn-ml-pluss").addEventListener("click", () => { skjemaState.ml = Math.min(400, skjemaState.ml + 10); tegnMating(); });
  $("inn-lagre").addEventListener("click", async () => {
    const knapp = $("inn-lagre");
    knapp.disabled = true;
    try {
      await api("api/innstillinger", { method: "PUT", body: {
        baby_navn: $("inn-navn").value.trim(),
        fodselsdato: $("inn-fodsel").value || null,
        mating: skjemaState.mating,
        kjonn: skjemaState.kjonn,
        standard_flaske_ml: skjemaState.ml,
        nattmodus_fra: $("inn-natt-fra").value || "21:00",
        nattmodus_til: $("inn-natt-til").value || "07:00",
        lyd: lesLyd(),
      } });
      await last();
      visToast("Innstillingene er lagret", [], 2500);
    } catch (e) {
      visToast(e.message, []);
    } finally {
      knapp.disabled = false;
    }
  });

  // ---------------------------------------------------------------- oppstart
  visFane(location.hash.slice(1), false);
  last().then(() => { if (!$("v-innstillinger").hidden) fyllInnstillinger(); });
  setInterval(tikk, 1000);
  setInterval(() => { if (!document.hidden) last(); }, 20000);
  setInterval(settNatt, 60000);
  document.addEventListener("visibilitychange", () => { if (!document.hidden) last(); });
})();
