/* Pengeboka – frontend. Ingen rammeverk, alle stier relative til ingress. */
(() => {
  "use strict";

  // ------------------------------------------------------------ hjelpere
  const $ = (id) => document.getElementById(id);
  const el = (tag, attrs = {}, ...barn) => {
    const e = document.createElement(tag);
    for (const [k, v] of Object.entries(attrs || {})) {
      if (k === "class") e.className = v;
      else if (k.startsWith("on") && typeof v === "function") e.addEventListener(k.slice(2), v);
      else if (k === "value") e.value = v ?? "";
      else if (k === "style") e.setAttribute("style", v);
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
  const kr = (ore, fortegn = false) => {
    const n = Math.round((ore || 0) / 100);
    const s = Math.abs(n).toLocaleString("nb-NO").replace(/\s/g, " ");
    return `${n < 0 ? "−" : fortegn && n > 0 ? "+" : ""}${s} kr`;
  };
  const MND = ["januar", "februar", "mars", "april", "mai", "juni", "juli", "august", "september", "oktober", "november", "desember"];
  const mndNavn = (ym) => { const [y, m] = ym.split("-").map(Number); return `${MND[m - 1]} ${y}`; };
  const dato = (iso, aar = false) => {
    const [y, m, d] = iso.split("-").map(Number);
    return `${d}. ${MND[m - 1].slice(0, 3)}${aar ? ` ${y}` : ""}`;
  };
  const dagHode = (iso) => {
    const d = new Date(`${iso}T12:00:00`);
    const idag = new Date(); idag.setHours(12, 0, 0, 0);
    const diff = Math.round((idag - d) / 864e5);
    if (diff === 0) return "I dag";
    if (diff === 1) return "I går";
    return d.toLocaleDateString("nb-NO", { weekday: "long", day: "numeric", month: "long", ...(d.getFullYear() !== idag.getFullYear() ? { year: "numeric" } : {}) });
  };
  const lagre = (k, v) => { try { localStorage.setItem(`pengeboka-${k}`, JSON.stringify(v)); } catch (_) { /* */ } };
  const hent = (k, std) => { try { const v = JSON.parse(localStorage.getItem(`pengeboka-${k}`)); return v ?? std; } catch (_) { return std; } };
  const debounce = (fn, ms) => { let t; return (...a) => { clearTimeout(t); t = setTimeout(() => fn(...a), ms); }; };

  async function api(sti, { metode = "GET", data, kropp, hoder } = {}) {
    const opts = { method: metode, headers: { ...(hoder || {}) } };
    if (data !== undefined) { opts.body = JSON.stringify(data); opts.headers["Content-Type"] = "application/json"; }
    if (kropp !== undefined) opts.body = kropp;
    let svar;
    try { svar = await fetch(`api/${sti}`, opts); } catch (_) { throw new Error("Får ikke kontakt med appen"); }
    if (!(svar.headers.get("Content-Type") || "").includes("json")) {
      if (!svar.ok) throw new Error(`Feil ${svar.status}`);
      return svar;
    }
    const j = await svar.json();
    if (!svar.ok) throw new Error(j.feil || `Feil ${svar.status}`);
    return j;
  }

  let toastTimer;
  function toast(tekst, ms = 3500) {
    const t = $("toast");
    t.textContent = tekst;
    t.hidden = false;
    clearTimeout(toastTimer);
    toastTimer = setTimeout(() => { t.hidden = true; }, ms);
  }
  const feil = (e) => toast(e.message || String(e), 5000);

  // ------------------------------------------------------------ ark (bunnark)
  function visArk(...innhold) {
    const ark = $("ark");
    ark.replaceChildren(el("div", { class: "ark-handtak" }), ...innhold.flat(Infinity).filter((x) => x != null && x !== false));
    ark.hidden = false;
    $("ark-bakgrunn").hidden = false;
    ark.scrollTop = 0;
  }
  function lukkArk() { $("ark").hidden = true; $("ark-bakgrunn").hidden = true; }
  $("ark-bakgrunn").addEventListener("click", lukkArk);
  document.addEventListener("keydown", (e) => { if (e.key === "Escape") lukkArk(); });

  // ------------------------------------------------------------ tilstand
  const S = {
    fane: "oversikt",
    maned: null,
    oversikt: null,
    kategorier: [],
    filter: hent("filter", { sok: "", maned: "", konto: "", kategori: "", skjulte: false }),
    grense: 300,
  };
  const katMap = () => Object.fromEntries(S.kategorier.map((k) => [k.id, k]));

  function byttFane(fane) {
    S.fane = fane;
    for (const b of document.querySelectorAll("#faner button")) b.classList.toggle("aktiv", b.dataset.fane === fane);
    for (const v of document.querySelectorAll(".visning")) v.hidden = v.id !== `v-${fane}`;
    window.scrollTo(0, 0);
    const vis = { oversikt: visOversikt, transaksjoner: visTransaksjoner, budsjett: visBudsjett, faste: visFaste,
      import: visImport, innstillinger: visInnstillinger }[fane];
    vis().catch(feil);
  }
  for (const b of document.querySelectorAll("#faner button")) b.addEventListener("click", () => byttFane(b.dataset.fane));
  $("til-innstillinger").addEventListener("click", () => byttFane("innstillinger"));

  async function lastKategorier() { S.kategorier = (await api("kategorier")).kategorier; }

  function settPrikk(n) {
    const knapp = document.querySelector('#faner button[data-fane="oversikt"]');
    knapp.querySelector(".prikk")?.remove();
    if (n) knapp.append(el("span", { class: "prikk" }, String(n)));
  }

  // ============================================================ OVERSIKT
  async function visOversikt() {
    const v = $("v-oversikt");
    const o = await api(`oversikt${S.maned ? `?maned=${S.maned}` : ""}`);
    S.oversikt = o;
    S.maned = o.maned.maned;
    $("undertittel").textContent = o.bruker ? `Hei, ${o.bruker.split(" ")[0]}` : "";
    settPrikk(o.trenger.length);
    if (!o.har_data) {
      v.replaceChildren(el("div", { class: "velkommen" },
        el("h2", {}, "Velkommen til Pengeboka"),
        el("p", {}, "Last ned transaksjonene fra nettbanken som en fil, og importer dem her. Appen sorterer alt i kategorier, finner faste trekk og overføringer mellom kontoene deres – uten å sende noe ut av Home Assistant."),
        el("button", { class: "knapp", onclick: () => byttFane("import") }, ikon("opp"), "Importer første fil")));
      return;
    }
    const m = o.maned;
    const idx = o.maneder.indexOf(m.maned);
    const mnd = el("div", { class: "mnd" },
      el("button", { class: "ikonknapp", "aria-label": "Forrige måned", disabled: idx <= 0, onclick: () => { S.maned = o.maneder[idx - 1]; visOversikt().catch(feil); } }, ikon("venstre")),
      el("b", {}, mndNavn(m.maned)),
      el("button", { class: "ikonknapp", "aria-label": "Neste måned", disabled: idx >= o.maneder.length - 1, onclick: () => { S.maned = o.maneder[idx + 1]; visOversikt().catch(feil); } }, ikon("hoyre")));

    // Midt i måneden har lønna ofte ikke kommet ennå – da er «brukt så langt» et ærligere hovedtall enn «igjen».
    const helt = el("div", { class: `helt${!m.pagar && m.igjen < 0 ? " minus" : ""}` },
      el("div", { class: "helt-etikett" }, m.pagar ? "Brukt så langt denne måneden" : (m.igjen < 0 ? "Brukt mer enn dere fikk inn" : "Igjen etter måneden")),
      el("div", { class: "helt-tall tall" }, kr(m.pagar ? m.ut : m.igjen)),
      el("div", { class: "helt-rad" },
        el("div", {}, el("span", {}, "Inn"), el("b", { class: "tall" }, kr(m.inn))),
        el("div", {}, el("span", {}, "Ut"), el("b", { class: "tall" }, kr(m.ut))),
        el("div", {}, el("span", {}, "Spart"), el("b", { class: "tall" }, kr(m.sparing)))),
      m.pagar ? [
        el("div", { class: "helt-under" },
          m.prognose_ut != null ? `Ligger an til ca. ${kr(m.prognose_ut)} i utgifter` : "",
          m.budsjett_sum ? ` · budsjett ${kr(m.budsjett_sum)}` : "",
          m.faste ? ` · ${kr(m.faste)} av utgiftene er faste trekk` : ""),
        el("div", { class: "mnd-fremdrift", title: `Dag ${m.dag} av ${m.dager}` }, el("i", { style: `width:${Math.round(100 * m.dag / m.dager)}%` }))
      ] : el("div", { class: "helt-under" }, m.faste ? `${kr(m.faste)} av utgiftene var faste trekk` : ""));

    v.replaceChildren(mnd, helt, trengerKort(o.trenger), kategoriKort(m));
  }

  function trengerKort(liste) {
    const kort = el("div", { class: "kort" }, el("div", { class: "kort-hode" }, el("h2", {}, "Trenger dere")));
    if (!liste.length) {
      kort.append(el("div", { class: "alt-ok" }, ikon("sjekk"), "Alt i orden – ingenting å se på nå"));
      return kort;
    }
    const symbol = { ukategorisert: "?", pris: "💸", ny_fast: "🔁", avvik: "⚠️", over: "🚨", kurs: "📈", import: "📥" };
    const ul = el("ul", { class: "trenger" });
    for (const t of liste) {
      const knapper = el("div", { class: "t-knapper" });
      const se = (fn) => knapper.append(el("button", { class: "knapp liten sekundaer", onclick: fn }, "Se"));
      if (t.type === "ukategorisert") se(() => { S.filter = { ...S.filter, kategori: "ingen", maned: "", konto: "", sok: "" }; byttFane("transaksjoner"); });
      else if (t.type === "pris" || t.type === "ny_fast") se(() => byttFane("faste"));
      else if (t.type === "avvik") se(() => apneTransaksjon(t.id));
      else if (t.type === "over" || t.type === "kurs") se(() => { S.filter = { ...S.filter, kategori: String(t.kategori_id), maned: S.maned, konto: "", sok: "" }; byttFane("transaksjoner"); });
      else if (t.type === "import") se(() => byttFane("import"));
      if (t.nokkel) knapper.append(el("button", { class: "knapp liten noytral", title: "Sett – skjul dette", onclick: async () => {
        try { await api("avvis", { metode: "POST", data: { nokkel: t.nokkel } }); visOversikt().catch(feil); } catch (e) { feil(e); }
      } }, "OK"));
      ul.append(el("li", {}, el("span", { class: "t-ikon" }, symbol[t.type] || "•"), el("span", { class: "t-tekst" }, t.tekst), knapper));
    }
    kort.append(ul);
    return kort;
  }

  function kategoriKort(m) {
    const kort = el("div", { class: "kort" }, el("div", { class: "kort-hode" }, el("h2", {}, "Kategorier"),
      el("button", { class: "lenke", onclick: () => byttFane("budsjett") }, "Budsjett")));
    const ul = el("ul", { class: "katliste" });
    const rader = m.kategorier.filter((k) => k.brukt || k.budsjett || (m.pagar && k.prognose));
    if (m.ukategorisert.ut) rader.push({ id: "ingen", ikon: "?", navn: "Uten kategori", brukt: m.ukategorisert.ut, ukat: true });
    if (!rader.length) kort.append(el("p", { class: "tom" }, "Ingen utgifter denne måneden ennå."));
    const maks = Math.max(...rader.map((k) => Math.max(k.brukt, k.budsjett || 0, k.prognose || 0)), 1);
    for (const k of rader) {
      const mal = k.budsjett || null;
      const skala = mal ? Math.max(mal, k.brukt, k.prognose || 0) : maks;
      const tilstand = !mal ? "snitt" : k.brukt > mal ? "over" : (k.prognose && k.prognose > mal * 1.05 ? "kurs" : "");
      const stolpe = el("div", { class: `stolpe ${tilstand}` });
      if (m.pagar && k.prognose && k.prognose > k.brukt) stolpe.append(el("i", { class: "prognose", style: `width:${Math.min(100, 100 * k.prognose / skala)}%` }));
      stolpe.append(el("i", { style: `width:${Math.min(100, 100 * k.brukt / skala)}%` }));
      const under = [];
      if (mal) {
        const rest = mal - k.brukt;
        under.push(rest >= 0 ? `${kr(rest)} igjen av ${kr(mal)}` : el("span", { class: "over" }, `${kr(-rest)} over budsjett (${kr(mal)})`));
      } else if (k.snitt) under.push(`Snitt ${kr(k.snitt)} i måneden`);
      if (m.pagar && k.prognose && k.prognose > k.brukt * 1.02) under.push(`${under.length ? " · " : ""}ligger an til ${kr(k.prognose)}`);
      ul.append(el("li", {}, el("button", { class: "katrad", onclick: () => {
        S.filter = { ...S.filter, kategori: String(k.id), maned: m.maned, konto: "", sok: "" };
        byttFane("transaksjoner");
      } },
        el("span", { class: "k-ikon" }, k.ikon),
        el("span", { class: "k-navn" }, k.navn),
        el("span", { class: "k-tall tall" }, kr(k.brukt)),
        stolpe,
        under.length ? el("span", { class: "k-under" }, under) : null)));
    }
    kort.append(ul);
    return kort;
  }

  // ============================================================ TRANSAKSJONER
  async function visTransaksjoner() {
    if (!S.kategorier.length) await lastKategorier();
    if (!S.oversikt) S.oversikt = await api("oversikt");
    const v = $("v-transaksjoner");
    const f = S.filter;
    const sok = el("input", { type: "search", placeholder: "Søk i tekst, mottaker eller notat", value: f.sok, "aria-label": "Søk" });
    sok.addEventListener("input", debounce(() => { f.sok = sok.value; S.grense = 300; lastListe(); }, 250));
    const velg = (navn, valg, verdi) => {
      const s = el("select", { "aria-label": navn }, valg.map(([v, t]) => el("option", { value: v, selected: String(verdi) === String(v) }, t)));
      return s;
    };
    const mndValg = [["", "Måned"], ...S.oversikt.maneder.slice().reverse().map((m) => [m, mndNavn(m)])];
    const kontoValg = [["", "Konto"], ["skjulte", "Alle, også skjulte"], ...S.oversikt.kontoer.map((k) => [String(k.id), k.navn + (k.skjult ? " (skjult)" : "")])];
    const katValg = [["", "Kategori"], ["ingen", "Uten kategori"], ...S.kategorier.map((k) => [String(k.id), `${k.ikon} ${k.navn}`])];
    const sM = velg("Måned", mndValg, f.maned);
    const sK = velg("Konto", kontoValg, f.skjulte && !f.konto ? "skjulte" : f.konto);
    const sC = velg("Kategori", katValg, f.kategori);
    const endret = () => {
      f.maned = sM.value; f.kategori = sC.value;
      f.skjulte = sK.value === "skjulte"; f.konto = sK.value === "skjulte" ? "" : sK.value;
      S.grense = 300; lagre("filter", { ...f, sok: "" }); lastListe();
    };
    [sM, sK, sC].forEach((s) => s.addEventListener("change", endret));
    const liste = el("div", { id: "txliste" });
    v.replaceChildren(
      el("div", { class: "filtre" }, el("div", { class: "sok" }, ikon("sok"), sok), el("div", { class: "filterrad" }, sM, sC, sK)),
      el("div", { class: "kort" }, liste));
    await lastListe();
  }

  async function lastListe() {
    const f = S.filter;
    const q = new URLSearchParams();
    for (const k of ["sok", "maned", "konto", "kategori"]) if (f[k]) q.set(k, f[k]);
    if (f.skjulte) q.set("skjulte", "1");
    if (f.kategori && f.kategori !== "ingen") q.set("overforinger", "1");
    q.set("grense", S.grense);
    const d = await api(`transaksjoner?${q}`);
    const liste = $("txliste");
    if (!liste) return;
    const n = d.transaksjoner.length;
    const innhold = [el("div", { class: "sumlinje" }, el("span", {}, `${n}${d.flere ? "+" : ""} ${n === 1 ? "transaksjon" : "transaksjoner"}`), el("span", { class: "tall" }, `Sum ${kr(d.sum)}`))];
    if (!n) innhold.push(el("p", { class: "tom" }, "Ingen transaksjoner med dette filteret."));
    let dag = null, ul = null;
    for (const t of d.transaksjoner) {
      if (t.dato !== dag) {
        dag = t.dato;
        innhold.push(el("div", { class: "dag-hode" }, dagHode(t.dato)));
        ul = el("ul", { class: "liste" });
        innhold.push(ul);
      }
      ul.append(el("li", {}, txRad(t)));
    }
    if (d.flere) innhold.push(el("button", { class: "vis-mer", onclick: () => { S.grense += 300; lastListe().catch(feil); } }, "Vis flere"));
    liste.replaceChildren(...innhold);
  }

  function txRad(t) {
    const under = [t.konto, t.kategori || "Uten kategori"];
    if (t.notat) under.push(t.notat);
    return el("button", { class: "txrad", onclick: () => apneTransaksjon(t.id) },
      el("span", { class: `k-ikon${t.kategori ? "" : " mangler"}` }, t.ikon || "?"),
      el("span", { class: "tx-tekst" }, el("div", { class: "tx-navn" }, t.motpart), el("div", { class: "tx-under" }, under.join(" · "))),
      el("span", { class: `tx-belop tall${t.belop_ore > 0 ? " inn" : ""}` }, kr(t.belop_ore, true)));
  }

  async function apneTransaksjon(id) {
    try {
      if (!S.kategorier.length) await lastKategorier();
      const t = (await api(`transaksjoner/${id}`)).transaksjon;
      visTxArk(t);
    } catch (e) { feil(e); }
  }

  function visTxArk(t) {
    let alle = !!t.regel_anbefalt;
    const regelBryter = el("span", { class: `bryter${alle ? " paa" : ""}` });
    const regelRad = t.like > 0 ? el("button", { class: "bryter-rad", onclick: () => { alle = !alle; regelBryter.classList.toggle("paa", alle); } },
      el("span", { class: "rad-tekst" }, `Gjelder alle fra «${t.motpart}»`, el("small", {}, `${t.like} til – og nye som kommer`)), regelBryter) : null;
    const notat = el("textarea", { placeholder: "Notat (valgfritt)", rows: 2 }, t.notat || "");
    const velg = async (kid) => {
      try {
        // Samme kategori som appen allerede hadde gitt: ingen grunn til en egen regel
        const regel = alle && kid != null && !(kid === t.kategori_id && t.kilde !== "manuell");
        await api(`transaksjoner/${t.id}`, { metode: "PATCH", data: { kategori_id: kid, regel, notat: notat.value } });
        lukkArk();
        toast(regel ? `Lagret – gjelder alle fra ${t.motpart}` : "Lagret");
        oppdaterGjeldende();
      } catch (e) { feil(e); }
    };
    const grupper = [["utgift", "Utgifter"], ["inntekt", "Inntekter"], ["sparing", "Sparing og overføring"]];
    const valg = grupper.map(([g, navn]) => {
      const kats = S.kategorier.filter((k) => !k.skjult && (k.gruppe === g || (g === "sparing" && k.gruppe === "overforing")));
      return [el("div", { class: "ark-etikett" }, navn), el("div", { class: "katvalg" }, kats.map((k) =>
        el("button", { class: k.id === t.kategori_id ? "valgt" : "", onclick: () => velg(k.id) }, el("span", {}, k.ikon), k.navn)))];
    });
    const info = [];
    if (t.par) info.push(el("div", { class: "infoboks spar" }, `${t.belop_ore < 0 ? "Overført til" : "Overført fra"} ${t.par.konto} ${dato(t.par.dato)} – telles ikke som forbruk`));
    if (t.endret_av) info.push(el("div", { class: "infoboks" }, `Sist endret av ${t.endret_av}`));
    visArk(
      el("div", { class: "hint" }, `${dagHode(t.dato)} · ${t.konto}`),
      el("h3", {}, t.motpart),
      el("div", { class: `stort tall${t.belop_ore > 0 ? " inn" : ""}` }, kr(t.belop_ore, true)),
      el("p", { class: "hint" }, t.tekst),
      info.length ? el("div", { class: "infobokser" }, info) : null,
      regelRad,
      valg,
      el("div", { class: "ark-etikett" }, "Notat"),
      notat,
      el("div", { class: "ark-knapper" },
        t.par ? el("button", { class: "knapp noytral", onclick: async () => {
          try { await api(`transaksjoner/${t.id}`, { metode: "PATCH", data: { ikke_overforing: true } }); lukkArk(); toast("Ikke lenger en overføring"); oppdaterGjeldende(); } catch (e) { feil(e); }
        } }, "Ikke en overføring") : null,
        t.kategori_id && t.kilde === "manuell" ? el("button", { class: "knapp noytral", onclick: () => velg(null) }, "Fjern kategori") : null,
        el("button", { class: "knapp", onclick: async () => {
          try { await api(`transaksjoner/${t.id}`, { metode: "PATCH", data: { notat: notat.value } }); lukkArk(); oppdaterGjeldende(); } catch (e) { feil(e); }
        } }, "Lukk")));
  }

  function oppdaterGjeldende() {
    if (S.fane === "transaksjoner") lastListe().catch(feil);
    else byttFane(S.fane);
    api("oversikt").then((o) => settPrikk(o.trenger.length)).catch(() => {});
  }

  // ============================================================ BUDSJETT
  async function visBudsjett() {
    const v = $("v-budsjett");
    const d = await api("budsjett");
    await lastKategorier();
    const felt = {};
    const utgifter = d.kategorier.filter((k) => k.gruppe === "utgift");
    const sumEl = el("b", { class: "tall" });
    const regnSum = () => {
      let s = 0;
      for (const k of utgifter) { const x = parseFloat(String(felt[k.id].value).replace(/\s/g, "").replace(",", ".")); if (x > 0) s += x * 100; }
      sumEl.textContent = `${kr(s)} i måneden`;
    };
    const rader = utgifter.map((k) => {
      const inp = el("input", { type: "text", inputmode: "numeric", placeholder: "– kr", value: k.budsjett_ore != null ? String(Math.round(k.budsjett_ore / 100)) : "", "aria-label": `Budsjett for ${k.navn}` });
      inp.addEventListener("input", regnSum);
      felt[k.id] = inp;
      return el("div", { class: "budrad" },
        el("span", { class: "k-ikon" }, k.ikon),
        el("button", { class: "b-navn", onclick: () => redigerKategori(k) }, k.navn, k.skjult ? " (skjult)" : "",
          el("small", {}, k.snitt ? `Snitt ${kr(k.snitt)}` : "Ingen utgifter siste 3 mnd")),
        inp);
    });
    regnSum();
    const lagreKnapp = el("button", { class: "knapp", onclick: async () => {
      const budsjett = {};
      for (const k of utgifter) budsjett[k.id] = felt[k.id].value.replace(/\s/g, "") || null;
      try { await api("budsjett", { metode: "PUT", data: { budsjett } }); toast("Budsjettet er lagret"); } catch (e) { feil(e); }
    } }, ikon("sjekk"), "Lagre");
    const forslag = el("button", { class: "knapp sekundaer", disabled: !d.maneder_grunnlag, onclick: async () => {
      try {
        const f = (await api("budsjett/forslag")).forslag;
        for (const k of utgifter) if (f[k.id] != null) felt[k.id].value = String(f[k.id]);
        regnSum();
        toast("Fylt ut fra snittet – se over og trykk Lagre");
      } catch (e) { feil(e); }
    } }, "Foreslå");
    v.replaceChildren(
      el("div", { class: "kort" },
        el("div", { class: "kort-hode" }, el("h2", {}, "Månedsbudsjett")),
        el("p", { class: "forklaring" }, d.maneder_grunnlag
          ? `«Foreslå» fyller ut snittet av de siste ${d.maneder_grunnlag} hele månedene, rundet opp. La felt stå tomme for kategorier dere ikke vil budsjettere.`
          : "Når dere har importert minst én hel måned, kan appen foreslå et budsjett ut fra det dere faktisk bruker."),
        el("div", { style: "margin-top:10px" }, rader),
        el("div", { class: "budsum" }, el("span", {}, "Sum utgifter"), sumEl)),
      el("button", { class: "knapp noytral", onclick: () => redigerKategori(null) }, ikon("pluss"), "Ny kategori"),
      el("div", { class: "lagrelinje" }, forslag, lagreKnapp));
  }

  function redigerKategori(k) {
    const navn = el("input", { value: k?.navn || "", placeholder: "Navn", maxlength: 40 });
    const ikn = el("input", { value: k?.ikon || "📦", maxlength: 4, style: "text-align:center;font-size:22px" });
    let skjult = !!k?.skjult;
    const br = el("span", { class: `bryter${skjult ? " paa" : ""}` });
    visArk(
      el("h3", {}, k ? "Endre kategori" : "Ny kategori"),
      el("div", { class: "skjema" },
        el("div", { class: "felt-rad", style: "grid-template-columns: 80px 1fr" },
          el("label", { class: "felt" }, el("span", {}, "Ikon"), ikn),
          el("label", { class: "felt" }, el("span", {}, "Navn"), navn)),
        k ? el("button", { class: "bryter-rad", onclick: () => { skjult = !skjult; br.classList.toggle("paa", skjult); } },
          el("span", { class: "rad-tekst" }, "Skjul kategorien", el("small", {}, "Vises ikke som valg. Transaksjoner som har den, beholder den.")), br) : null),
      el("div", { class: "ark-knapper" },
        el("button", { class: "knapp noytral", onclick: lukkArk }, "Avbryt"),
        el("button", { class: "knapp", onclick: async () => {
          try {
            const data = { navn: navn.value, ikon: ikn.value, skjult, gruppe: k?.gruppe || "utgift" };
            await api(k ? `kategorier/${k.id}` : "kategorier", { metode: k ? "PATCH" : "POST", data });
            lukkArk(); await lastKategorier(); visBudsjett().catch(feil);
          } catch (e) { feil(e); }
        } }, "Lagre")));
  }

  // ============================================================ FASTE
  async function visFaste() {
    const v = $("v-faste");
    const { faste } = await api("faste");
    const sum = faste.filter((f) => !f.uteblitt).reduce((s, f) => s + f.per_maned, 0);
    const neste = faste.filter((f) => !f.uteblitt).sort((a, b) => a.neste.localeCompare(b.neste));
    const hyp = { "måned": "hver måned", uke: "hver uke", kvartal: "hvert kvartal", "år": "hvert år", uregelmessig: "uregelmessig" };
    const rad = (f) => el("li", {}, el("button", { class: "txrad", onclick: () => fastArk(f) },
      el("span", { class: "k-ikon" }, f.ikon || "🔁"),
      el("span", { class: "tx-tekst" },
        el("div", { class: "tx-navn" }, f.motpart, " ",
          f.endring ? el("span", { class: "merke pris" }, `${kr(f.endring.fra)} → ${kr(f.endring.til)}`) : null,
          f.ny ? el("span", { class: "merke ny" }, "Ny") : null,
          f.uteblitt ? el("span", { class: "merke borte" }, "Uteblitt?") : null),
        el("div", { class: "tx-under" }, `${hyp[f.hyppighet] || f.hyppighet}${f.fast_belop ? "" : " · varierer"} · ${f.uteblitt ? `sist ${dato(f.siste)}` : `neste ca. ${dato(f.neste)}`}`)),
      el("span", { class: "tx-belop tall" }, `${f.fast_belop ? "" : "ca. "}${kr(f.typisk)}`)));
    v.replaceChildren(
      el("div", { class: "kort" },
        el("div", { class: "kort-hode" }, el("h2", {}, "Faste trekk")),
        el("div", { class: "nokkeltall", style: "grid-template-columns: 1fr 1fr" },
          el("div", {}, el("span", {}, "Per måned"), el("b", { class: "tall" }, kr(sum))),
          el("div", {}, el("span", {}, "Per år"), el("b", { class: "tall" }, kr(sum * 12)))),
        el("p", { class: "forklaring", style: "margin-top:10px" }, "Funnet automatisk: samme mottaker, jevne mellomrom og omtrent samme beløp. Trykk på et trekk for å bekrefte eller fjerne det."),
        faste.length ? el("ul", { class: "liste", style: "margin-top:6px" }, neste.map(rad), faste.filter((f) => f.uteblitt).map(rad))
          : el("p", { class: "tom" }, "Ingen faste trekk funnet ennå. Det trengs minst tre trekk fra samme mottaker.")));
  }

  function fastArk(f) {
    const merk = async (valg) => {
      try { await api("faste", { metode: "POST", data: { motpart: f.motpart, valg } }); lukkArk(); visFaste().catch(feil); } catch (e) { feil(e); }
    };
    visArk(
      el("h3", {}, `${f.ikon || "🔁"} ${f.motpart}`),
      el("div", { class: "stort tall" }, `${f.fast_belop ? "" : "ca. "}${kr(f.typisk)}`),
      el("p", { class: "hint" }, `${f.kategori || "Uten kategori"} · ${f.antall} trekk siden ${dato(f.forst, true)} · siste ${dato(f.siste)} (${kr(f.siste_belop)})`),
      el("div", { class: "infobokser" },
        f.endring ? el("div", { class: "infoboks" }, `Beløpet har endret seg fra ${kr(f.endring.fra)} til ${kr(f.endring.til)}.`) : null,
        f.uteblitt ? el("div", { class: "infoboks" }, "Ventet trekk har ikke kommet. Kanskje abonnementet er sagt opp – eller filen er ikke importert ennå.") : null,
        el("div", { class: "infoboks" }, `Omtrent ${kr(f.per_maned)} i måneden – ${kr(f.per_maned * 12)} i året.`)),
      el("div", { class: "ark-knapper" },
        el("button", { class: "knapp noytral", onclick: () => merk("nei") }, "Ikke et fast trekk"),
        f.bekreftet ? el("button", { class: "knapp sekundaer", onclick: () => merk(null) }, "Angre bekreftelse")
          : el("button", { class: "knapp", onclick: () => merk("ja") }, ikon("sjekk"), "Stemmer")),
      el("button", { class: "knapp noytral bred", style: "margin-top:10px", onclick: () => {
        lukkArk(); S.filter = { ...S.filter, sok: f.motpart, maned: "", konto: "", kategori: "" }; byttFane("transaksjoner");
      } }, "Se alle trekkene"));
  }

  // ============================================================ IMPORT
  const imp = { fil: null, data: null, konto: hent("importkonto", ""), oppsett: null, forhand: null };

  async function visImport() {
    const v = $("v-import");
    const k = await api("kontoer");
    const kontoer = k.kontoer;
    if (imp.konto && !kontoer.some((x) => String(x.id) === String(imp.konto))) imp.konto = "";
    const kontoValg = el("select", { "aria-label": "Konto" },
      el("option", { value: "" }, kontoer.length ? "Velg konto …" : "Lag en konto først"),
      kontoer.map((x) => el("option", { value: x.id, selected: String(x.id) === String(imp.konto) }, `${x.navn}${x.navn.toLowerCase() === x.type_navn.toLowerCase() ? "" : ` – ${x.type_navn}`}${x.skjult ? " (skjult)" : ""}`)));
    kontoValg.addEventListener("change", () => { imp.konto = kontoValg.value; lagre("importkonto", imp.konto); if (imp.data) forhandsvis(); });
    const filInput = el("input", { type: "file", accept: ".csv,.txt,.xlsx,text/csv", hidden: true });
    const slipp = el("button", { class: "slipp", onclick: () => filInput.click() }, ikon("fil"),
      el("b", {}, imp.fil ? imp.fil.name : "Velg fil eller slipp den her"),
      el("span", {}, "CSV eller Excel fra nettbanken"));
    const ta = async (fil) => {
      if (!fil) return;
      imp.fil = fil; imp.data = await fil.arrayBuffer(); imp.oppsett = null;
      slipp.querySelector("b").textContent = fil.name;
      forhandsvis();
    };
    filInput.addEventListener("change", () => ta(filInput.files[0]));
    slipp.addEventListener("dragover", (e) => { e.preventDefault(); slipp.classList.add("over"); });
    slipp.addEventListener("dragleave", () => slipp.classList.remove("over"));
    slipp.addEventListener("drop", (e) => { e.preventDefault(); slipp.classList.remove("over"); ta(e.dataTransfer.files[0]); });

    v.replaceChildren(
      el("div", { class: "kort" },
        el("div", { class: "steg" }, el("i", {}, "1"), "Hvilken konto?"),
        el("div", { style: "display:flex;gap:8px" }, kontoValg, el("button", { class: "ikonknapp flat", "aria-label": "Ny konto", title: "Ny konto", onclick: () => kontoArk(null, (ny) => { imp.konto = String(ny.id); lagre("importkonto", imp.konto); visImport().catch(feil); }) }, ikon("pluss"))),
        el("div", { class: "steg", style: "margin-top:18px" }, el("i", {}, "2"), "Velg filen"),
        slipp, filInput,
        el("p", { class: "forklaring", style: "margin-top:10px" }, "I nettbanken: åpne kontoen, velg periode og last ned transaksjonene som CSV eller Excel. Det gjør ingenting om periodene overlapper – det som er importert fra før, hoppes over.")),
      el("div", { id: "forhand" }),
      ...[importHistorikk(k.importer)].filter(Boolean));
    if (imp.data) forhandsvis();
  }

  async function forhandsvis() {
    const boks = $("forhand");
    if (!boks || !imp.data) return;
    const q = new URLSearchParams();
    if (imp.konto) q.set("konto", imp.konto);
    if (imp.oppsett) q.set("oppsett", JSON.stringify(imp.oppsett));
    let d;
    try { d = await api(`import/forhandsvis?${q}`, { metode: "POST", kropp: imp.data, hoder: { "Content-Type": "application/octet-stream" } }); }
    catch (e) { boks.replaceChildren(el("div", { class: "feilmelding" }, e.message)); return; }
    imp.forhand = d;
    const kol = d.oppsett.kolonner || {};
    imp.oppsett = { ...d.oppsett, toKol: imp.oppsett?.toKol ?? ("ut" in kol || "inn" in kol) };
    const valg = (felt, navn, valgfri) => {
      const s = el("select", { "aria-label": navn },
        el("option", { value: "" }, valgfri ? "–" : "Velg …"),
        d.overskrifter.map((h, i) => el("option", { value: i, selected: kol[felt] === i }, h)));
      s.addEventListener("change", () => {
        const k = { ...imp.oppsett.kolonner };
        if (s.value === "") delete k[felt]; else k[felt] = +s.value;
        imp.oppsett = { ...imp.oppsett, kolonner: k };
        forhandsvis();
      });
      return el("label", { class: "felt" }, el("span", {}, navn), s);
    };
    const toKol = imp.oppsett.toKol;
    const bytt = (tilTo) => el("button", { class: "knapp noytral liten", style: "align-self:flex-start", onclick: () => {
      const k = { ...kol }; delete k.belop; delete k.ut; delete k.inn;
      imp.oppsett = { ...imp.oppsett, kolonner: k, toKol: tilTo }; forhandsvis();
    } }, tilTo ? "Ut og inn står i hver sin kolonne" : "Beløpet står i én kolonne");
    const oppsett = el("div", { class: "skjema", style: "margin-top:12px" },
      el("div", { class: "felt-rad" }, valg("dato", "Dato"), valg("tekst", "Tekst")),
      toKol ? el("div", { class: "felt-rad" }, valg("ut", "Penger ut", true), valg("inn", "Penger inn", true))
        : valg("belop", "Beløp (minus = ut)"),
      bytt(!toKol));
    const innhold = [el("div", { class: "steg" }, el("i", {}, "3"), "Sjekk og importer")];
    if (d.feil) {
      innhold.push(el("div", { class: "feilmelding" }, d.feil), oppsett);
      if (d.radeksempel?.length) innhold.push(el("div", { class: "tabell-wrap", style: "margin-top:12px" }, el("table", { class: "eksempel" },
        el("tr", {}, d.overskrifter.map((h) => el("th", {}, h))), d.radeksempel.map((r) => el("tr", {}, r.map((c) => el("td", {}, c)))))));
      boks.replaceChildren(el("div", { class: "kort" }, innhold));
      return;
    }
    innhold.push(
      el("div", { class: "nokkeltall" },
        el("div", {}, el("span", {}, "Nye"), el("b", {}, d.nye)),
        el("div", {}, el("span", {}, "Fra før"), el("b", {}, d.duplikater)),
        el("div", {}, el("span", {}, "Periode"), el("b", { style: "font-size:15px" }, `${dato(d.fra)} – ${dato(d.til, true)}`))),
      el("p", { class: "forklaring", style: "margin-top:8px" }, `Inn ${kr(d.sum_inn)} · ut ${kr(d.sum_ut)}${d.hoppet ? ` · ${d.hoppet} rader uten dato eller beløp hoppes over` : ""}`),
      el("div", { class: "tabell-wrap", style: "margin-top:8px" }, el("table", { class: "eksempel" },
        el("tr", {}, el("th", {}, "Dato"), el("th", {}, "Mottaker"), el("th", { style: "text-align:right" }, "Beløp")),
        d.eksempel.map((t) => el("tr", {}, el("td", {}, dato(t.dato)), el("td", {}, t.motpart), el("td", { class: `b${t.belop_ore > 0 ? " inn" : ""}` }, kr(t.belop_ore, true)))))),
      el("details", { style: "margin-top:10px" }, el("summary", { class: "forklaring", style: "cursor:pointer;font-weight:800" }, "Feil kolonner? Endre her"), oppsett),
      el("button", { class: "knapp bred", style: "margin-top:14px", disabled: !imp.konto || !d.nye, onclick: importer },
        ikon("opp"), !imp.konto ? "Velg konto først" : d.nye ? `Importer ${d.nye} nye` : "Alt er importert fra før"));
    boks.replaceChildren(el("div", { class: "kort" }, innhold));
  }

  async function importer() {
    const q = new URLSearchParams({ konto: imp.konto });
    if (imp.oppsett) q.set("oppsett", JSON.stringify(imp.oppsett));
    try {
      const r = await api(`import?${q}`, { metode: "POST", kropp: imp.data, hoder: { "Content-Type": "application/octet-stream", "X-Filnavn": encodeURIComponent(imp.fil?.name || "") } });
      imp.fil = imp.data = imp.forhand = null;
      toast(`${r.nye} transaksjoner importert${r.ukategorisert ? ` – ${r.ukategorisert} trenger kategori` : ""}`, 5000);
      S.oversikt = null; S.maned = null;
      byttFane("oversikt");
    } catch (e) { feil(e); }
  }

  function importHistorikk(liste) {
    if (!liste.length) return null;
    return el("div", { class: "kort" },
      el("div", { class: "kort-hode" }, el("h2", {}, "Tidligere importer")),
      el("ul", { class: "liste" }, liste.map((i) => el("li", {}, el("div", { class: "txrad" },
        el("span", { class: "k-ikon" }, "📥"),
        el("span", { class: "tx-tekst" }, el("div", { class: "tx-navn" }, `${i.konto}: ${i.nye} nye`),
          el("div", { class: "tx-under" }, `${dato(i.fra)} – ${dato(i.til, true)} · ${new Date(i.tid).toLocaleDateString("nb-NO")}${i.av ? ` · ${i.av}` : ""}`)),
        el("button", { class: "knapp liten noytral", onclick: async () => {
          if (!confirm(`Angre importen? ${i.nye} transaksjoner fra ${i.konto} slettes, også kategoriene dere har satt på dem.`)) return;
          try { const r = await api(`importer/${i.id}`, { metode: "DELETE" }); toast(`${r.slettet} transaksjoner slettet`); visImport().catch(feil); } catch (e) { feil(e); }
        } }, "Angre"))))));
  }

  // ============================================================ INNSTILLINGER
  const TYPER = [["felles", "Felleskonto"], ["bruk", "Brukskonto"], ["kreditt", "Kredittkort"], ["sparing", "Sparekonto"], ["lan", "Lån"], ["annet", "Annet"]];

  function kontoArk(k, ferdig) {
    const navn = el("input", { value: k?.navn || "", placeholder: "F.eks. Felleskonto", maxlength: 60 });
    const type = el("select", {}, TYPER.map(([v, t]) => el("option", { value: v, selected: (k?.type || "felles") === v }, t)));
    let skjult = !!k?.skjult;
    const br = el("span", { class: `bryter${skjult ? " paa" : ""}` });
    visArk(
      el("h3", {}, k ? "Endre konto" : "Ny konto"),
      el("div", { class: "skjema" },
        el("label", { class: "felt" }, el("span", {}, "Navn"), navn),
        el("label", { class: "felt" }, el("span", {}, "Type"), type),
        el("p", { class: "forklaring" }, "Typen styrer overføringer: penger til en sparekonto telles som sparing, og betaling av kredittkort telles ikke dobbelt."),
        el("button", { class: "bryter-rad", onclick: () => { skjult = !skjult; br.classList.toggle("paa", skjult); } },
          el("span", { class: "rad-tekst" }, "Skjul i oversikten", el("small", {}, "Vises ikke i tall og lister, men brukes fortsatt til å kjenne igjen overføringer.")), br)),
      el("div", { class: "ark-knapper" },
        k ? el("button", { class: "knapp fare", onclick: async () => {
          if (!confirm(`Slette ${k.navn} og alle ${k.antall} transaksjonene på kontoen? Dette kan ikke angres.`)) return;
          try { await api(`kontoer/${k.id}`, { metode: "DELETE" }); lukkArk(); toast("Kontoen er slettet"); S.oversikt = null; ferdig?.(); } catch (e) { feil(e); }
        } }, "Slett") : el("button", { class: "knapp noytral", onclick: lukkArk }, "Avbryt"),
        el("button", { class: "knapp", onclick: async () => {
          try {
            const r = await api(k ? `kontoer/${k.id}` : "kontoer", { metode: k ? "PATCH" : "POST", data: { navn: navn.value, type: type.value, skjult } });
            lukkArk(); S.oversikt = null; ferdig?.(r.konto);
          } catch (e) { feil(e); }
        } }, "Lagre")));
    if (!k) setTimeout(() => navn.focus(), 300);
  }

  async function visInnstillinger() {
    for (const b of document.querySelectorAll("#faner button")) b.classList.remove("aktiv");
    const v = $("v-innstillinger");
    const d = await api("kontoer");
    const kontoRad = (k) => el("li", {}, el("button", { class: "txrad", onclick: () => kontoArk(k, () => visInnstillinger().catch(feil)) },
      el("span", { class: "k-ikon" }, { felles: "👨‍👩‍👧", bruk: "💳", kreditt: "💳", sparing: "🐷", lan: "🏦", annet: "📁" }[k.type] || "📁"),
      el("span", { class: "tx-tekst" },
        el("div", { class: "tx-navn" }, k.navn, " ", k.skjult ? el("span", { class: "merke skjult" }, "Skjult") : null),
        el("div", { class: "tx-under" }, `${k.type_navn} · ${k.antall} transaksjoner${k.til ? ` · siste ${dato(k.til, true)}` : ""}`)),
      ikon("hoyre")));
    v.replaceChildren(
      el("div", { class: "kort" },
        el("div", { class: "kort-hode" }, el("h2", {}, "Kontoer")),
        d.kontoer.length ? el("ul", { class: "liste" }, d.kontoer.map(kontoRad)) : el("p", { class: "tom" }, "Ingen kontoer ennå."),
        el("button", { class: "knapp noytral bred", style: "margin-top:10px", onclick: () => kontoArk(null, () => visInnstillinger().catch(feil)) }, ikon("pluss"), "Ny konto")),
      el("div", { class: "kort" },
        el("div", { class: "kort-hode" }, el("h2", {}, "Egne regler")),
        el("p", { class: "forklaring" }, "Laget når dere velger «Gjelder alle fra …» på en transaksjon. Reglene går foran de innebygde."),
        d.regler.length ? el("ul", { class: "liste", style: "margin-top:6px" }, d.regler.map((r) => el("li", {}, el("div", { class: "txrad" },
          el("span", { class: "k-ikon" }, r.ikon),
          el("span", { class: "tx-tekst" }, el("div", { class: "tx-navn" }, `«${r.monster}»`), el("div", { class: "tx-under" }, `${r.kategori} · ${r.treff} treff${r.laget_av ? ` · laget av ${r.laget_av}` : ""}`)),
          el("button", { class: "ikonknapp flat", "aria-label": "Slett regel", onclick: async () => {
            try { await api(`regler/${r.id}`, { metode: "DELETE" }); visInnstillinger().catch(feil); } catch (e) { feil(e); }
          } }, ikon("kryss"))))))
          : el("p", { class: "tom" }, "Ingen egne regler ennå.")),
      el("div", { class: "kort" },
        el("div", { class: "kort-hode" }, el("h2", {}, "Data")),
        el("p", { class: "forklaring" }, "Alt lagres bare i denne appen i Home Assistant. Appen sender ingenting ut, har ingen tilgang til resten av Home Assistant og bruker ingen AI. Husk passord på sikkerhetskopiene."),
        el("a", { class: "knapp noytral bred", style: "margin-top:12px", href: "api/eksport.csv", download: "pengeboka.csv" }, ikon("last-ned"), "Last ned alt som CSV")));
  }

  // ------------------------------------------------------------ start
  byttFane("oversikt");
})();
