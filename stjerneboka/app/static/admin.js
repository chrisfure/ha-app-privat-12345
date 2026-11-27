/* Stjerneboka – administrasjon (ingress). Ingen rammeverk, alle stier relative. */
(() => {
  "use strict";
  const $ = (id) => document.getElementById(id);
  const el = (tag, attrs = {}, ...barn) => {
    const e = document.createElement(tag);
    for (const [k, v] of Object.entries(attrs || {})) {
      if (k === "class") e.className = v;
      else if (k.startsWith("on") && typeof v === "function") e.addEventListener(k.slice(2), v);
      else if (k === "value") e.value = v ?? "";
      else if (k === "checked") e.checked = !!v;
      else if (v !== false && v != null) e.setAttribute(k, v === true ? "" : v);
    }
    for (const b of barn.flat(Infinity)) if (b != null && b !== false) e.append(b.nodeType ? b : document.createTextNode(b));
    return e;
  };
  const kl = (iso) => new Date(iso).toLocaleTimeString("nb-NO", { hour: "2-digit", minute: "2-digit" });
  const dato = (iso) => new Date(iso).toLocaleDateString("nb-NO", { weekday: "short", day: "numeric", month: "short" });
  const kr = (x) => `${Number(x).toLocaleString("nb-NO", { maximumFractionDigits: 2 })} kr`;
  const TYPE_FARGE = { rutine: "", familie: "gronn", ekstra: "gul" };
  const NAR = { morgen: "Morgen", dag: "Dag", kveld: "Kveld", hele_dagen: "Hele dagen" };
  const SPERRE = { okt: "Én gang per morgen/dag/kveld", dag: "Én gang per dag", intervall: "Med pause mellom", fri: "Så ofte de vil" };

  let D = null;
  let fane = "oversikt";

  async function api(metode, sti, data) {
    const r = await fetch(sti, { method: metode, headers: data ? { "Content-Type": "application/json" } : {},
      body: data ? JSON.stringify(data) : undefined });
    const j = await r.json().catch(() => ({}));
    if (!r.ok) throw new Error(j.feil || "Noe gikk galt");
    if (j.oppgaver && j.innstillinger) { D = j; tegn(); }
    return j;
  }
  async function gjor(fn, ok) {
    try { await fn(); if (ok) toast(ok); return true; } catch (e) { toast(e.message); return false; }
  }
  function toast(t) {
    const b = $("toast"); b.textContent = t; b.hidden = false;
    clearTimeout(toast.t); toast.t = setTimeout(() => { b.hidden = true; }, 3500);
  }

  const barnNavn = (id) => (D.barn.find((b) => b.id === id) || {}).navn || "?";
  function thumb(bilde) {
    const art = bilde.split(":")[0], v = bilde.slice(bilde.indexOf(":") + 1);
    if (art === "emoji") return el("div", { class: "thumb" }, v);
    return el("div", { class: "thumb" }, el("img", { src: art === "innebygd" ? `static/bilder/${v}.png?v=1` : `bilder/${v}`, alt: "" }));
  }
  const barneUrl = () => D.innstillinger.barneside_url || `http://${location.hostname}:8097/`;

  // ------------------------------------------------------------ dialog
  function dialog(tittel, innhold, knapper) {
    const f = $("dialog-innhold");
    f.replaceChildren(el("h2", { style: "margin-top:0" }, tittel), ...innhold, el("div", { class: "knapperad" }, ...knapper));
    $("dialog").showModal();
  }
  const lukk = () => $("dialog").close();
  const avbryt = () => el("button", { class: "knapp", type: "button", onclick: lukk }, "Avbryt");

  // ------------------------------------------------------------ oversikt
  function tegnOversikt() {
    const f = $("f-oversikt"); f.replaceChildren();
    if (!D.barn.length) {
      f.append(el("div", { class: "kort" }, el("h2", { style: "margin-top:0" }, "Velkommen til Stjerneboka ⭐"),
        el("p", { class: "hint" }, "Start med å legge inn barna under «Barn», og velg oppgaver under «Oppgaver». Barnesiden viser oppgavene på veggskjermen."),
        el("button", { class: "knapp primar", onclick: () => byttFane("barn") }, "Legg inn barn")));
      return;
    }
    if (D.ventende.length) {
      f.append(el("h2", {}, `⏳ Venter på godkjenning (${D.ventende.length})`));
      const k = el("div", { class: "kort" });
      for (const r of D.ventende) {
        k.append(el("div", { class: "liste-rad" },
          el("div", { class: "vokse" }, el("div", { class: "tittel" }, `${r.barn}: ${r.oppgave_navn}`),
            el("div", { class: "under" }, `${dato(r.tid)} kl. ${kl(r.tid)} · ${r.poeng} poeng`)),
          el("button", { class: "knapp fare liten", onclick: () => gjor(() => api("POST", `api/godkjenn/${r.id}`, { godkjent: false }), "Ikke godkjent") }, "Ikke helt ennå"),
          el("button", { class: "knapp ok liten", onclick: () => gjor(() => api("POST", `api/godkjenn/${r.id}`, { godkjent: true }), "Godkjent ⭐") }, "Godkjenn ⭐")));
      }
      f.append(k);
    }
    const uke = D.uker[0];
    f.append(el("h2", {}, `Denne uka (uke ${uke.nr})`));
    const grid = el("div", { class: "barnekort" });
    for (const b of D.barn.filter((x) => x.aktiv)) {
      const s = uke.barn.find((x) => x.barn_id === b.id) || {};
      const vis = (D.barnevisning.barn.find((x) => x.id === b.id) || {});
      grid.append(el("div", { class: `kort farge-${b.farge}` },
        el("div", { class: "rad" }, el("span", { class: "prikk" }), el("b", {}, `${b.emoji ? b.emoji + " " : ""}${b.navn}`)),
        el("div", { class: "stort" }, `⭐ ${s.stjerner ?? 0}`),
        el("div", { class: "hint" }, `${vis.stjerner_i_dag ?? 0} i dag · ${s.poeng ?? 0} poeng fra hjelp`),
        D.ukepenger ? el("div", { style: "margin-top:6px;font-weight:800" }, `💰 ${kr(s.kroner || 0)}`, s.utbetalt != null ? " · utbetalt ✓" : "") : null,
        vis.mangler && vis.mangler.length ? el("div", { class: "hint", style: "margin-top:6px" }, `Igjen nå: ${vis.mangler.join(", ")}`) : null));
    }
    f.append(grid);

    f.append(el("div", { class: "rad", style: "margin-top:12px" },
      el("button", { class: "knapp", onclick: registrerDialog }, "+ Registrer for et barn")));

    f.append(el("h2", {}, "Siste uker"));
    const tab = el("table", {}, el("tr", {}, el("th", {}, "Uke"), D.barn.filter((x) => x.aktiv).map((b) => el("th", { class: "tall" }, b.navn))));
    for (const u of D.uker) {
      tab.append(el("tr", {}, el("td", {}, `Uke ${u.nr}`), D.barn.filter((x) => x.aktiv).map((b) => {
        const s = u.barn.find((x) => x.barn_id === b.id) || {};
        const celle = el("td", { class: "tall" }, `⭐ ${s.stjerner || 0} · ${s.poeng || 0} p`);
        if (D.ukepenger) {
          celle.append(el("br"), `${kr(s.kroner || 0)} `);
          if (s.utbetalt != null) celle.append(el("button", { class: "knapp liten", title: "Angre utbetalt",
            onclick: () => gjor(() => api("POST", "api/utbetalt", { barn_id: b.id, uke: u.uke, angre: true })) }, "✓ utbetalt"));
          else if (s.kroner) celle.append(el("button", { class: "knapp liten",
            onclick: () => gjor(() => api("POST", "api/utbetalt", { barn_id: b.id, uke: u.uke }), "Markert som utbetalt") }, "Betal ut"));
        }
        return celle;
      })));
    }
    f.append(el("div", { class: "kort" }, tab));

    f.append(el("h2", {}, "Siste registreringer"));
    const liste = el("div", { class: "kort" });
    if (!D.siste.length) liste.append(el("div", { class: "tom" }, "Ingen registreringer de siste 14 dagene."));
    for (const r of D.siste.slice(0, 60)) {
      liste.append(el("div", { class: "liste-rad" },
        el("div", { class: "vokse" },
          el("div", { class: "tittel" }, `${r.barn}: ${r.oppgave_navn}`),
          el("div", { class: "under" }, `${dato(r.tid)} kl. ${kl(r.tid)} · ${({ skjerm: "skjermen", kort: "NFC-kort", ha: "Home Assistant", admin: r.av || "voksen" })[r.kilde] || r.kilde}`,
            r.status !== "godkjent" ? ` · ${r.status === "venter" ? "venter" : "ikke godkjent"}` : "")),
        el("span", { class: `merke ${TYPE_FARGE[r.type] || ""}` }, r.type === "rutine" ? "⭐" : `${r.poeng} p`),
        el("button", { class: "knapp fare liten", onclick: () => { if (confirm("Fjerne denne registreringen?")) gjor(() => api("DELETE", `api/registreringer/${r.id}`), "Fjernet"); } }, "Fjern")));
    }
    f.append(liste);
  }

  function registrerDialog() {
    const barnSel = el("select", {}, D.barn.filter((b) => b.aktiv).map((b) => el("option", { value: b.id }, b.navn)));
    const oppgSel = el("select");
    const fyll = () => oppgSel.replaceChildren(...D.oppgaver.filter((o) => o.barn.includes(+barnSel.value)).map((o) => el("option", { value: o.id }, o.navn)));
    barnSel.onchange = fyll; fyll();
    const tid = el("input", { type: "datetime-local" });
    dialog("Registrer for et barn", [
      el("p", { class: "hint" }, "Gir stjerne uten sperre og uten godkjenning – f.eks. hvis barnet glemte å trykke."),
      el("label", { class: "felt" }, "Barn", barnSel), el("label", { class: "felt" }, "Oppgave", oppgSel),
      el("label", { class: "felt" }, "Tidspunkt (tomt = nå)", tid)],
      [avbryt(), el("button", { class: "knapp primar", type: "button", onclick: async () => {
        if (await gjor(() => api("POST", "api/registreringer", { barn_id: +barnSel.value, oppgave_id: +oppgSel.value,
          tid: tid.value ? new Date(tid.value).toISOString() : null }), "Registrert ⭐")) lukk();
      } }, "Registrer")]);
  }

  // ------------------------------------------------------------ oppgaver
  function oppgaveMerker(o) {
    return [
      el("span", { class: `merke ${TYPE_FARGE[o.type]}` }, D.konstanter.typer.find((t) => t.id === o.type).navn),
      o.type !== "rutine" ? el("span", { class: "merke" }, "⭐".repeat(o.poeng)) : null,
      el("span", { class: "merke" }, o.nar.split(",").map((n) => NAR[n]).join(" + ")),
      o.godkjenning ? el("span", { class: "merke" }, "Godkjennes") : null,
      o.penger ? el("span", { class: "merke gul" }, "💰 Ukepenger") : null,
      !o.aktiv ? el("span", { class: "merke" }, "Av") : null,
    ];
  }

  function tegnOppgaver() {
    const f = $("f-oppgaver"); f.replaceChildren();
    f.append(el("div", { class: "rad" },
      el("button", { class: "knapp primar", onclick: () => oppgaveDialog(null) }, "+ Ny oppgave")));
    f.append(el("p", { class: "hint" }, "Rutiner gir stjerner. Familiebidrag og ekstra innsats gir 1–3 poeng og kan gjøres om til pengeoppgaver når dere vil starte med ukepenger."));
    for (const t of D.konstanter.typer) {
      const oppg = D.oppgaver.filter((o) => o.type === t.id);
      f.append(el("h2", {}, `${t.navn} (${oppg.length})`));
      const k = el("div", { class: "kort" });
      if (!oppg.length) k.append(el("div", { class: "tom" }, "Ingen ennå."));
      oppg.forEach((o) => {
        const alle = D.oppgaver.map((x) => x.id), i = alle.indexOf(o.id);
        k.append(el("div", { class: "liste-rad" }, thumb(o.bilde),
          el("div", { class: "vokse", style: "cursor:pointer", onclick: () => oppgaveDialog(o) },
            el("div", { class: "tittel" }, o.navn),
            el("div", { class: "under" }, ...oppgaveMerker(o)),
            el("div", { class: "under" }, o.barn.length ? o.barn.map(barnNavn).join(", ") : "Ingen barn valgt")),
          el("button", { class: "knapp liten", disabled: i === 0, onclick: () => flytt("oppgaver", alle, i, -1) }, "▲"),
          el("button", { class: "knapp liten", disabled: i === alle.length - 1, onclick: () => flytt("oppgaver", alle, i, 1) }, "▼")));
      });
      f.append(k);
    }
    const brukte = new Set(D.oppgaver.map((o) => o.navn.toLowerCase()));
    const ledige = D.maler.map((m, i) => ({ ...m, i })).filter((m) => !brukte.has(m.navn.toLowerCase()));
    if (ledige.length) {
      f.append(el("h2", {}, "Forslag"));
      const k = el("div", { class: "kort" });
      for (const m of ledige) {
        k.append(el("div", { class: "liste-rad" }, thumb(m.bilde),
          el("div", { class: "vokse" }, el("div", { class: "tittel" }, m.navn), el("div", { class: "under" }, ...oppgaveMerker({ ...m, aktiv: 1, penger: 0 }))),
          el("button", { class: "knapp liten", onclick: () => gjor(() => api("POST", "api/oppgaver/mal", { indeks: m.i, barn: D.barn.filter((b) => b.aktiv).map((b) => b.id) }), `${m.navn} lagt til for alle barna`) }, "Legg til")));
      }
      f.append(k);
    }
  }

  function flytt(tabell, ider, i, retning) {
    const ny = [...ider]; [ny[i], ny[i + retning]] = [ny[i + retning], ny[i]];
    gjor(() => api("PUT", "api/rekkefolge", { tabell, ider: ny }));
  }

  function segment(verdier, verdi, onvalg) {
    const s = el("div", { class: "segment" });
    for (const [v, tekst] of verdier) {
      s.append(el("button", { type: "button", class: String(v) === String(verdi) ? "aktiv" : "", onclick: () => {
        [...s.children].forEach((b) => b.classList.remove("aktiv")); s.children[verdier.findIndex((x) => x[0] === v)].classList.add("aktiv"); onvalg(v);
      } }, tekst));
    }
    return s;
  }

  function oppgaveDialog(o) {
    const ny = !o;
    const s = ny ? { navn: "", bilde: "emoji:⭐", type: "familie", poeng: 1, godkjenning: 0, penger: 0, nar: "hele_dagen",
      sperre: "okt", intervall_min: 30, ros: "", aktiv: 1, barn: D.barn.filter((b) => b.aktiv).map((b) => b.id) } : { ...o, barn: [...o.barn] };
    const navn = el("input", { value: s.navn, maxlength: 40, placeholder: "F.eks. Ta av bordet" });
    const ros = el("input", { value: s.ros, maxlength: 80, placeholder: "F.eks. tatt av bordet" });
    // bilde
    const emojiInn = el("input", { value: s.bilde.startsWith("emoji:") ? s.bilde.slice(6) : "", placeholder: "🍽️", style: "width:90px;font-size:22px;text-align:center" });
    const bildeRute = el("div", { class: "bildevalg" });
    const tegnBilder = () => {
      bildeRute.replaceChildren(...D.konstanter.innebygde.map((b) => el("button", { type: "button", class: s.bilde === `innebygd:${b}` ? "aktiv" : "",
        onclick: () => { s.bilde = `innebygd:${b}`; tegnBilder(); } }, el("img", { src: `static/bilder/${b}.png?v=1`, alt: b }))),
        ...(s.bilde.startsWith("fil:") ? [el("button", { type: "button", class: "aktiv" }, el("img", { src: `bilder/${s.bilde.slice(4)}` }))] : []));
    };
    tegnBilder();
    emojiInn.oninput = () => { if (emojiInn.value.trim()) { s.bilde = `emoji:${emojiInn.value.trim()}`; tegnBilder(); } };
    const fil = el("input", { type: "file", accept: "image/png,image/jpeg,image/webp,image/gif" });
    fil.onchange = async () => {
      if (!fil.files[0]) return;
      const fd = new FormData(); fd.append("fil", fil.files[0]);
      const r = await fetch("api/bilder", { method: "POST", body: fd });
      const j = await r.json().catch(() => ({}));
      if (!r.ok) return toast(j.feil || "Opplasting feilet");
      s.bilde = j.bilde; emojiInn.value = ""; tegnBilder();
    };
    // penger og type
    const pengerBoks = el("input", { type: "checkbox", checked: !!s.penger });
    const pengerRad = el("label", { class: "valg" }, el("label", {}, pengerBoks, "💰 Teller i ukepenger"));
    const oppdaterPenger = () => { pengerBoks.disabled = s.type === "rutine"; if (s.type === "rutine") pengerBoks.checked = false; };
    pengerBoks.onchange = () => { s.penger = pengerBoks.checked ? 1 : 0; };
    oppdaterPenger();
    // når
    const narValg = el("div", { class: "valg" });
    const tegnNar = () => {
      const deler = s.nar.split(",");
      narValg.replaceChildren(...["morgen", "dag", "kveld", "hele_dagen"].map((n) => {
        const c = el("input", { type: "checkbox", checked: deler.includes(n) });
        c.onchange = () => {
          let d = s.nar.split(",").filter((x) => x && x !== "hele_dagen");
          if (n === "hele_dagen") d = c.checked ? ["hele_dagen"] : ["morgen"];
          else if (c.checked) d.push(n); else d = d.filter((x) => x !== n);
          s.nar = d.length ? d.join(",") : "hele_dagen"; tegnNar();
        };
        return el("label", {}, c, NAR[n]);
      }));
    };
    tegnNar();
    // sperre
    const intervall = el("input", { type: "number", min: 1, max: 1440, value: s.intervall_min, style: "width:100px" });
    const intervallRad = el("label", { class: "felt" }, "Minutter mellom hver gang", intervall);
    const sperre = el("select", {}, Object.entries(SPERRE).map(([k, v]) => el("option", { value: k, selected: k === s.sperre }, v)));
    sperre.onchange = () => { intervallRad.hidden = sperre.value !== "intervall"; };
    intervallRad.hidden = s.sperre !== "intervall";
    const godkjenning = el("input", { type: "checkbox", checked: !!s.godkjenning });
    const aktiv = el("input", { type: "checkbox", checked: !!s.aktiv });
    const barnValg = el("div", { class: "valg" }, D.barn.map((b) => {
      const c = el("input", { type: "checkbox", checked: s.barn.includes(b.id) });
      c.onchange = () => { s.barn = c.checked ? [...s.barn, b.id] : s.barn.filter((x) => x !== b.id); };
      return el("label", {}, c, b.navn);
    }));

    dialog(ny ? "Ny oppgave" : o.navn, [
      el("label", { class: "felt" }, "Navn", navn),
      el("div", { class: "felt" }, el("b", { class: "hint" }, "Bilde – velg en tegning, skriv en emoji eller last opp et bilde"),
        bildeRute, el("div", { class: "rad", style: "margin-top:8px" }, emojiInn, fil)),
      el("div", { class: "felt" }, el("b", { class: "hint" }, "Type"), el("div", {}, segment(D.konstanter.typer.map((t) => [t.id, t.navn]), s.type,
        (v) => { s.type = v; oppdaterPenger(); }))),
      el("div", { class: "felt" }, el("b", { class: "hint" }, "Hvor krevende (poeng)"),
        el("div", {}, segment([[1, "⭐ Lett"], [2, "⭐⭐ Middels"], [3, "⭐⭐⭐ Krevende"]], s.poeng, (v) => { s.poeng = v; }))),
      el("div", { class: "felt" }, el("b", { class: "hint" }, "Når vises den"), narValg),
      el("label", { class: "felt" }, "Hvor ofte kan den gjøres", sperre), intervallRad,
      el("div", { class: "valg" }, el("label", {}, godkjenning, "En voksen må godkjenne")),
      pengerRad,
      el("label", { class: "felt" }, "Rosen i stemmen: «Bra jobba! Du har …»", ros),
      el("div", { class: "felt" }, el("b", { class: "hint" }, "Hvem har oppgaven"), barnValg),
      el("div", { class: "valg" }, el("label", {}, aktiv, "Aktiv")),
    ], [
      !ny ? el("button", { class: "knapp fare venstre", type: "button", onclick: async () => {
        if (confirm(`Slette «${o.navn}»? Tidligere stjerner beholdes i historikken.`) && await gjor(() => api("DELETE", `api/oppgaver/${o.id}`), "Slettet")) lukk();
      } }, "Slett") : null,
      avbryt(),
      el("button", { class: "knapp primar", type: "button", onclick: async () => {
        const data = { navn: navn.value, bilde: s.bilde, type: s.type, poeng: s.poeng, nar: s.nar, sperre: sperre.value,
          intervall_min: +intervall.value || 30, godkjenning: godkjenning.checked, penger: s.type === "rutine" ? false : pengerBoks.checked,
          ros: ros.value, aktiv: aktiv.checked, barn: s.barn };
        if (await gjor(() => ny ? api("POST", "api/oppgaver", data) : api("PATCH", `api/oppgaver/${o.id}`, data), "Lagret")) lukk();
      } }, "Lagre"),
    ]);
  }

  // ------------------------------------------------------------ barn
  function tegnBarn() {
    const f = $("f-barn"); f.replaceChildren();
    f.append(el("button", { class: "knapp primar", onclick: () => barnDialog(null) }, "+ Legg til barn"));
    const k = el("div", { class: "kort", style: "margin-top:12px" });
    if (!D.barn.length) k.append(el("div", { class: "tom" }, "Ingen barn ennå."));
    const ider = D.barn.map((b) => b.id);
    D.barn.forEach((b, i) => k.append(el("div", { class: `liste-rad farge-${b.farge}` }, el("span", { class: "prikk" }),
      el("div", { class: "vokse", style: "cursor:pointer", onclick: () => barnDialog(b) },
        el("div", { class: "tittel" }, `${b.emoji ? b.emoji + " " : ""}${b.navn}`),
        el("div", { class: "under" }, `${D.oppgaver.filter((o) => o.barn.includes(b.id)).length} oppgaver${b.aktiv ? "" : " · skjult"}`)),
      el("button", { class: "knapp liten", disabled: i === 0, onclick: () => flytt("barn", ider, i, -1) }, "▲"),
      el("button", { class: "knapp liten", disabled: i === ider.length - 1, onclick: () => flytt("barn", ider, i, 1) }, "▼"))));
    f.append(k);
    f.append(el("p", { class: "hint" }, "Hvert barn får en sensor i Home Assistant (", D.sensorer.filter((s) => !s.endsWith("venter_godkjenning")).join(", ") || "sensor.stjerneboka_<navn>",
      ") med stjerner i dag, uke, poeng, kroner og hva som mangler nå."));
  }

  function barnDialog(b) {
    const ny = !b;
    const s = ny ? { navn: "", farge: "rosa", emoji: "", aktiv: 1 } : { ...b };
    const navn = el("input", { value: s.navn, maxlength: 40 });
    const emoji = el("input", { value: s.emoji, maxlength: 8, placeholder: "💗", style: "width:90px;font-size:22px;text-align:center" });
    const aktiv = el("input", { type: "checkbox", checked: !!s.aktiv });
    const farger = el("div", { class: "valg" }, D.konstanter.farger.map((f) => {
      const r = el("input", { type: "radio", name: "farge", value: f, checked: f === s.farge });
      r.onchange = () => { s.farge = f; };
      return el("label", { class: `farge-${f}` }, r, el("span", { class: "prikk" }));
    }));
    dialog(ny ? "Nytt barn" : b.navn, [
      el("label", { class: "felt" }, "Navn", navn), el("div", { class: "felt" }, el("b", { class: "hint" }, "Farge"), farger),
      el("label", { class: "felt" }, "Emoji (valgfritt)", emoji), el("div", { class: "valg" }, el("label", {}, aktiv, "Vises på barnesiden"))],
    [!ny ? el("button", { class: "knapp fare venstre", type: "button", onclick: async () => {
      if (confirm(`Slette ${b.navn} og alle stjernene til ${b.navn}?`) && await gjor(() => api("DELETE", `api/barn/${b.id}`), "Slettet")) lukk();
    } }, "Slett") : null, avbryt(),
    el("button", { class: "knapp primar", type: "button", onclick: async () => {
      const data = { navn: navn.value, farge: s.farge, emoji: emoji.value, aktiv: aktiv.checked };
      if (await gjor(() => ny ? api("POST", "api/barn", data) : api("PATCH", `api/barn/${b.id}`, data), "Lagret")) lukk();
    } }, "Lagre")]);
  }

  // ------------------------------------------------------------ NFC-kort
  function tegnKort() {
    const f = $("f-kort"); f.replaceChildren();
    f.append(el("div", { class: "kort" }, el("p", { class: "hint", style: "margin:0" },
      "Skann et nytt kort på leseren – det dukker opp under «Nye kort» her. Koble det til et barn og en oppgave. ",
      "Leseren må sende kort-ID-en til hendelsen ", el("code", {}, "stjerneboka_skann"), " med feltet ", el("code", {}, "uid"), " (se dokumentasjonen).")));
    f.append(el("h2", {}, "Nye kort"));
    const nye = el("div", { class: "kort" });
    if (!D.ukjente_kort.length) nye.append(el("div", { class: "tom" }, "Ingen nye kort skannet. Skann et kort, så vises det her (oppdater siden)."));
    for (const u of D.ukjente_kort) {
      nye.append(el("div", { class: "liste-rad" }, el("div", { class: "vokse" }, el("div", { class: "tittel" }, u.uid),
        el("div", { class: "under" }, `Skannet ${dato(u.tid)} kl. ${kl(u.tid)}`)),
        el("button", { class: "knapp primar liten", onclick: () => kortDialog(u.uid) }, "Koble")));
    }
    if (D.ukjente_kort.length) nye.append(el("button", { class: "knapp liten", style: "margin-top:8px", onclick: () => gjor(() => api("DELETE", "api/ukjente_kort")) }, "Tøm listen"));
    f.append(nye);
    f.append(el("div", { class: "rad" }, el("button", { class: "knapp", onclick: () => api("GET", "api/alt") }, "Oppdater"),
      el("button", { class: "knapp", onclick: () => { const uid = prompt("Kort-ID (f.eks. 53-30-5E-B7)"); if (uid) kortDialog(uid.trim().toUpperCase()); } }, "Skriv inn kort-ID")));
    f.append(el("h2", {}, "Koblede kort"));
    const k = el("div", { class: "kort" });
    if (!D.kort.length) k.append(el("div", { class: "tom" }, "Ingen kort koblet ennå."));
    for (const c of D.kort) {
      const o = D.oppgaver.find((x) => x.id === c.oppgave_id);
      k.append(el("div", { class: "liste-rad" }, o ? thumb(o.bilde) : el("div", { class: "thumb" }, "📺"),
        el("div", { class: "vokse" }, el("div", { class: "tittel" }, c.handling === "vis_skjerm" ? "Åpne barnesiden på skjermen" : `${barnNavn(c.barn_id)}: ${o ? o.navn : "?"}`),
          el("div", { class: "under" }, c.uid, c.navn ? ` · ${c.navn}` : "")),
        el("button", { class: "knapp liten", onclick: () => kortDialog(c.uid, c) }, "Endre"),
        el("button", { class: "knapp liten", title: "Late som kortet ble skannet", onclick: () => gjor(async () => {
          const r = await api("POST", "api/kort/test", { uid: c.uid }); toast(r.resultat.melding || "Skannet");
        }) }, "Test"),
        el("button", { class: "knapp fare liten", onclick: () => { if (confirm("Fjerne koblingen?")) gjor(() => api("DELETE", `api/kort/${encodeURIComponent(c.uid)}`)); } }, "Fjern")));
    }
    f.append(k);
  }

  function kortDialog(uid, c) {
    const s = c ? { ...c } : { handling: "oppgave", barn_id: (D.barn[0] || {}).id, oppgave_id: null, navn: "" };
    const handling = el("select", {}, el("option", { value: "oppgave", selected: s.handling === "oppgave" }, "Gi stjerne for en oppgave"),
      el("option", { value: "vis_skjerm", selected: s.handling === "vis_skjerm" }, "Åpne barnesiden på veggskjermen"));
    const barnSel = el("select", {}, D.barn.map((b) => el("option", { value: b.id, selected: b.id === s.barn_id }, b.navn)));
    const oppgSel = el("select");
    const fyll = () => oppgSel.replaceChildren(...D.oppgaver.filter((o) => o.barn.includes(+barnSel.value))
      .map((o) => el("option", { value: o.id, selected: o.id === s.oppgave_id }, o.navn)));
    barnSel.onchange = fyll; fyll();
    const felter = el("div", {}, el("label", { class: "felt" }, "Barn", barnSel), el("label", { class: "felt" }, "Oppgave", oppgSel));
    handling.onchange = () => { felter.hidden = handling.value !== "oppgave"; };
    felter.hidden = s.handling !== "oppgave";
    const navn = el("input", { value: s.navn || "", placeholder: "F.eks. rosa kort med tannbørste" });
    dialog(`Kort ${uid}`, [el("label", { class: "felt" }, "Hva skal kortet gjøre", handling), felter,
      el("label", { class: "felt" }, "Beskrivelse (valgfritt)", navn)],
    [avbryt(), el("button", { class: "knapp primar", type: "button", onclick: async () => {
      if (await gjor(() => api("PUT", `api/kort/${encodeURIComponent(uid)}`, { handling: handling.value, barn_id: +barnSel.value,
        oppgave_id: +oppgSel.value, navn: navn.value }), "Kortet er koblet")) lukk();
    } }, "Lagre")]);
  }

  // ------------------------------------------------------------ innstillinger
  function tegnInnstillinger() {
    const f = $("f-innstillinger"); f.replaceChildren();
    const I = { ...D.innstillinger };
    const inn = (k, attrs = {}) => { const e = el("input", { value: I[k], ...attrs }); e.oninput = () => { I[k] = e.value; }; return e; };
    const sjekk = (k, tekst) => { const c = el("input", { type: "checkbox", checked: I[k] === "1" }); c.onchange = () => { I[k] = c.checked ? "1" : "0"; }; return el("label", {}, c, tekst); };
    const lagre = el("button", { class: "knapp primar", onclick: () => gjor(() => api("PUT", "api/innstillinger", I), "Lagret") }, "Lagre innstillinger");

    f.append(el("h2", {}, "💰 Ukepenger"), el("div", { class: "kort" },
      el("p", { class: "hint", style: "margin-top:0" }, "Slå på når dere er klare. Bare oppgaver merket «Teller i ukepenger» gir penger – rutiner gir aldri penger. Beløpet er poeng × kroner per poeng."),
      el("div", { class: "valg" }, sjekk("ukepenger_aktiv", "Ukepenger er i bruk")),
      el("label", { class: "felt" }, "Kroner per poeng", inn("kr_per_poeng", { inputmode: "decimal", style: "width:120px" }))));

    f.append(el("h2", {}, "🕒 Morgen, dag og kveld"), el("div", { class: "kort" },
      el("p", { class: "hint", style: "margin-top:0" }, "Bestemmer hvilke oppgaver som vises og når «én gang per morgen/dag/kveld» starter på nytt."),
      el("div", { class: "rad" }, el("label", { class: "felt" }, "Morgen fra", inn("morgen_fra", { type: "time" })),
        el("label", { class: "felt" }, "Dag fra", inn("dag_fra", { type: "time" })), el("label", { class: "felt" }, "Kveld fra", inn("kveld_fra", { type: "time" })))));

    const metode = el("select", {}, el("option", { value: "music_assistant", selected: I.lydmetode === "music_assistant" }, "Music Assistant-kunngjøring (fanfare + stemme)"),
      el("option", { value: "tts", selected: I.lydmetode === "tts" }, "Vanlig tekst-til-tale"));
    metode.onchange = () => { I.lydmetode = metode.value; };
    f.append(el("h2", {}, "🔊 Lyd"), el("div", { class: "kort" },
      el("div", { class: "valg" }, sjekk("lyd_aktiv", "Si «Bra jobba!» på høyttaleren")),
      el("label", { class: "felt" }, "Metode", metode),
      el("label", { class: "felt" }, "Høyttaler (media_player)", inn("hoyttaler", { placeholder: "media_player.baderom" })),
      el("label", { class: "felt" }, "Talemotor (tts)", inn("tts", { placeholder: "tts.home_assistant_cloud" })),
      el("div", { class: "rad" }, el("label", { class: "felt" }, "Volum dag (%)", inn("volum_dag", { type: "number", min: 1, max: 100, style: "width:100px" })),
        el("label", { class: "felt" }, "Volum stille tid (%)", inn("volum_kveld", { type: "number", min: 1, max: 100, style: "width:100px" })),
        el("label", { class: "felt" }, "Stille fra", inn("stille_fra", { type: "time" })), el("label", { class: "felt" }, "Stille til", inn("stille_til", { type: "time" }))),
      el("label", { class: "felt" }, "Egen fanfare (adresse til lydfil, valgfritt)", inn("fanfare_url", { placeholder: "http://127.0.0.1:8123/local/stjerner/stjerne.mp3" })),
      el("button", { class: "knapp", onclick: () => gjor(async () => { await api("PUT", "api/innstillinger", I); const r = await api("POST", "api/test/lyd"); toast(r.ok ? "Spiller av …" : "Fikk ikke spilt – sjekk høyttaler og talemotor"); }) }, "Lagre og test lyd")));

    f.append(el("h2", {}, "📺 Veggskjermen"), el("div", { class: "kort" },
      el("p", { class: "hint", style: "margin-top:0" }, "Barnesiden ligger på ", el("a", { href: barneUrl(), target: "_blank" }, barneUrl()),
        " (bare på hjemmenettet). Med Browser Mod kan appen åpne den på veggskjermen når et kort skannes."),
      el("label", { class: "felt" }, "Adressen til barnesiden", inn("barneside_url", { placeholder: barneUrl() })),
      el("label", { class: "felt" }, "Browser Mod-ID for veggskjermen", inn("skjerm_browser", { placeholder: "browser_mod_xxxx_xxxx" })),
      el("div", { class: "valg" }, sjekk("vis_ved_kort", "Åpne barnesiden når et kort skannes")),
      el("label", { class: "felt" }, "Sekunder barna kan angre et trykk", inn("angre_sekunder", { type: "number", min: 0, max: 600, style: "width:100px" })),
      el("button", { class: "knapp", onclick: () => gjor(async () => { await api("PUT", "api/innstillinger", I); const r = await api("POST", "api/test/skjerm"); toast(r.ok ? "Sendt til skjermen" : "Fikk ikke åpnet – sjekk ID og adresse"); }) }, "Lagre og test skjermen")));

    f.append(el("h2", {}, "✅ Godkjenning"), el("div", { class: "kort" },
      el("p", { class: "hint", style: "margin-top:0" }, "Oppgaver som må godkjennes sender et varsel med knappene «Godkjenn» og «Ikke helt ennå». Skriv én eller flere notify-tjenester, adskilt med komma."),
      el("label", { class: "felt" }, "Varsle", inn("varsle_tjeneste", { placeholder: "notify.mobile_app_telefon, notify.mobile_app_telefon_2" }))));

    f.append(el("div", { class: "rad", style: "margin-top:16px" }, lagre));
  }

  // ------------------------------------------------------------ felles
  function tegn() {
    if (!D) return;
    $("barneside-lenke").href = barneUrl();
    ({ oversikt: tegnOversikt, oppgaver: tegnOppgaver, barn: tegnBarn, kort: tegnKort, innstillinger: tegnInnstillinger })[fane]();
  }
  function byttFane(f) {
    fane = f;
    document.querySelectorAll("#faner button").forEach((b) => b.classList.toggle("aktiv", b.dataset.fane === f));
    document.querySelectorAll(".fane").forEach((s) => { s.hidden = s.id !== `f-${f}`; });
    tegn();
  }
  document.querySelectorAll("#faner button").forEach((b) => b.addEventListener("click", () => byttFane(b.dataset.fane)));
  api("GET", "api/alt").catch((e) => toast(e.message));
  // Hold oversikten fersk (ikke mens et skjema er åpent)
  setInterval(() => { if (!$("dialog").open && fane !== "innstillinger") api("GET", "api/alt").catch(() => {}); }, 15000);
})();
