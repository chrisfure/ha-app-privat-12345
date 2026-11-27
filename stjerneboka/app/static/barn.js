/* Stjerneboka – barnesiden på veggskjermen. Ingen rammeverk, stier relative. */
(() => {
  "use strict";
  const $ = (id) => document.getElementById(id);
  const el = (tag, attrs = {}, ...barn) => {
    const e = document.createElement(tag);
    for (const [k, v] of Object.entries(attrs || {})) {
      if (k === "class") e.className = v;
      else if (k.startsWith("on") && typeof v === "function") e.addEventListener(k.slice(2), v);
      else if (v !== false && v != null) e.setAttribute(k, v === true ? "" : v);
    }
    for (const b of barn.flat(Infinity)) if (b != null && b !== false) e.append(b.nodeType ? b : document.createTextNode(b));
    return e;
  };
  const NS = "http://www.w3.org/2000/svg";
  // Stjernen tegnes direkte i siden (ikke som <img>), så skjermen ikke blander bildene.
  function stjerne(klasse) {
    const s = document.createElementNS(NS, "svg");
    s.setAttribute("viewBox", "0 0 100 100");
    s.setAttribute("class", klasse);
    const p = document.createElementNS(NS, "path");
    p.setAttribute("d", "M50 4 L63 34 L96 37 L71 59 L78 92 L50 75 L22 92 L29 59 L4 37 L37 34 Z");
    p.setAttribute("fill", "#ffd23f");
    p.setAttribute("stroke", "#3a2e5c");
    p.setAttribute("stroke-width", "6");
    p.setAttribute("stroke-linejoin", "round");
    const g = document.createElementNS(NS, "path");
    g.setAttribute("d", "M50 18 L56 32");
    g.setAttribute("stroke", "#fff6c2");
    g.setAttribute("stroke-width", "6");
    g.setAttribute("stroke-linecap", "round");
    s.append(p, g);
    return s;
  }
  const FARGEKODE = { rosa: "#ff5fa2", blaa: "#3d8bff", lilla: "#9b5de5", gronn: "#2ecc71", oransje: "#ff9f1c", gul: "#ffd23f" };
  const OKT_IKON = { morgen: "☀️", dag: "🌤️", kveld: "🌙" };

  let status = null;
  let sett = null;          // feiringer vi allerede har vist
  let opptatt = false;
  let toastTimer = null;
  let feirer = false;
  const feirKo = [];

  async function api(sti, data) {
    const r = await fetch(sti, data ? { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(data) } : {});
    const j = await r.json().catch(() => ({}));
    if (!r.ok) { const e = new Error(j.feil || "Noe gikk galt"); e.sperret = !!j.sperret; throw e; }
    return j;
  }

  function bildeFor(b) {
    const [art, verdi] = [b.split(":")[0], b.slice(b.indexOf(":") + 1)];
    if (art === "emoji") return el("span", { class: "emoji" }, verdi);
    const src = art === "innebygd" ? `static/bilder/${verdi}.png?v=1` : `bilder/${verdi}`;
    return el("img", { src, alt: "", draggable: "false" });
  }

  function flis(barn, o) {
    const knapp = el("button", { class: `flis${o.ferdig ? " ferdig" : ""}${o.venter ? " venter" : ""}`, type: "button",
      onclick: () => trykk(barn, o) },
      el("div", { class: "bilde" }, bildeFor(o.bilde)),
      el("div", { class: "navn" }, o.navn));
    if (o.type !== "rutine") knapp.append(el("div", { class: "poeng" }, "⭐".repeat(o.poeng)));
    if (o.penger && status.ukepenger) knapp.append(el("div", { class: "penger" }, "💰"));
    if (o.fri && o.antall_i_dag) knapp.append(el("div", { class: "antall" }, `×${o.antall_i_dag}`));
    if (o.ferdig) knapp.append(stjerne("stor-stjerne"));
    if (o.venter) knapp.append(el("div", { class: "vent" }, "⏳ Venter på voksen"));
    return knapp;
  }

  function tegn() {
    if (!status) return;
    $("okt").textContent = `${OKT_IKON[status.okt] || "⭐"} ${status.okt_navn}`;
    const boks = $("barn");
    boks.replaceChildren();
    const synlige = status.barn.filter((b) => b.rutiner.length || b.hjelpe.length);
    $("tom").hidden = synlige.length > 0;
    for (const b of synlige) {
      const statustekst = b.alt_ferdig ? "🌟 Alt ferdig – bra jobba!"
        : b.mangler.length ? `👉 Igjen: ${b.mangler.join(", ").toLowerCase()}` : "💪 Vil du hjelpe til?";
      const del = el("section", { class: `barn farge-${b.farge}` },
        el("div", { class: "barn-topp" },
          el("div", { class: "barn-navn" }, `${b.emoji ? b.emoji + " " : ""}${b.navn}`),
          el("div", { class: "barn-stjerner" }, stjerne("stj"), String(b.stjerner_i_dag))),
        el("div", { class: `barn-status${b.alt_ferdig ? " ferdig" : ""}` }, statustekst));
      if (b.rutiner.length) del.append(el("div", { class: "rutenett" }, b.rutiner.map((o) => flis(b, o))));
      if (b.hjelpe.length) {
        del.append(el("div", { class: "seksjon" }, "💪 Hjelpe til"));
        del.append(el("div", { class: "rutenett" }, b.hjelpe.map((o) => flis(b, o))));
      }
      boks.append(del);
    }
  }

  function toast(tekst, angreId) {
    $("toast-tekst").textContent = tekst;
    const k = $("toast-angre");
    k.hidden = !angreId;
    k.onclick = async () => {
      k.hidden = true;
      try { status = (await api("api/angre", { id: angreId })).status; marker(); tegn(); toast("Angret ↩︎"); }
      catch (e) { toast(e.message); }
    };
    $("toast").hidden = false;
    clearTimeout(toastTimer);
    toastTimer = setTimeout(() => { $("toast").hidden = true; }, angreId ? 9000 : 4500);
  }

  async function trykk(barn, o) {
    if (opptatt) return;
    if (o.ferdig || o.venter) {
      toast(o.venter ? "En voksen skal sjekke denne snart ⏳" : `${o.navn} er allerede ferdig ⭐`, o.angre_id);
      return;
    }
    opptatt = true;
    try {
      const res = await api("api/registrer", { barn_id: barn.id, oppgave_id: o.id });
      status = res.status;
      // Vis feiringen med en gang (og ikke en gang til når den dukker opp i statusen)
      const r = res.registrering;
      if (!sett) sett = new Set();
      sett.add(`${r.id}-${r.status[0]}`);
      tegn();
      feir({ barn: barn.navn, farge: barn.farge, tekst: o.navn, poeng: o.poeng, art: r.status === "venter" ? "venter" : "stjerne" });
      setTimeout(() => toast(r.status === "venter" ? "Nå må en voksen sjekke ⏳" : `${o.navn} ⭐`, r.id), 2900);
    } catch (e) {
      toast(e.message);
      if (e.sperret) oppdater();
    } finally {
      setTimeout(() => { opptatt = false; }, 600);
    }
  }

  function feir(f) {
    feirKo.push(f);
    if (!feirer) nesteFeiring();
  }

  function nesteFeiring() {
    const f = feirKo.shift();
    if (!f) { feirer = false; return; }
    feirer = true;
    const boks = $("feiring");
    boks.style.setProperty("--rakett", FARGEKODE[f.farge] || "#ff5fa2");
    $("feiring-linje1").textContent = f.art === "venter" ? "Så flott," : f.art === "godkjent" ? "Godkjent!" : "Bra jobba,";
    $("feiring-linje2").textContent = f.art === "godkjent" ? `${f.barn} +${f.poeng} ⭐` : `${f.barn.toUpperCase()}!`;
    $("feiring-linje3").textContent = f.art === "venter" ? `${f.tekst} – en voksen sjekker ⏳` : `${f.tekst} ⭐`;
    const himmel = $("feiring-himmel");
    himmel.replaceChildren();
    for (let i = 0; i < 22; i++) {
      const s = el("span", {}, "✦");
      s.style.left = `${Math.random() * 100}%`;
      s.style.top = `${Math.random() * 80}%`;
      s.style.fontSize = `${18 + Math.random() * 40}px`;
      s.style.animationDelay = `${Math.random()}s`;
      himmel.append(s);
    }
    // Start animasjonene på nytt
    boks.hidden = true;
    void boks.offsetWidth;
    boks.hidden = false;
    setTimeout(() => { boks.hidden = true; nesteFeiring(); }, 2900);
  }

  function marker() {
    if (!status) return;
    if (!sett) sett = new Set();
    for (const f of status.feiringer || []) sett.add(f.nokkel);
  }

  async function oppdater() {
    try {
      const ny = await api("api/status");
      const forste = !sett;
      if (forste) { status = ny; marker(); }
      else {
        for (const f of ny.feiringer || []) {
          if (!sett.has(f.nokkel)) { sett.add(f.nokkel); feir(f); }
        }
        status = ny;
      }
      tegn();
    } catch (_) { /* prøver igjen */ }
  }

  function klokke() {
    $("klokke").textContent = new Date().toLocaleTimeString("nb-NO", { hour: "2-digit", minute: "2-digit" });
  }

  klokke();
  setInterval(klokke, 10000);
  oppdater();
  setInterval(oppdater, 3000);
  // Hindre zoom og tekstmarkering på veggskjermen
  document.addEventListener("gesturestart", (e) => e.preventDefault());
})();
