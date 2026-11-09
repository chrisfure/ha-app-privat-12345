"""Spillifisering av forsiden: ukeringer, uke-kjede, XP og nivå, rekorder og merker.

Alt regnes ut fra det som allerede er logget – ingenting lagres. XP gis for det som faktisk bygger
form: fullførte økter, arbeidssett, nye rekorder, nådde ukemål og kondisjonsaktivitet.
"""
from __future__ import annotations

from datetime import timedelta
from typing import TYPE_CHECKING

import program as P
from db import naa, til_iso

if TYPE_CHECKING:
    from logikk import Styrkeboka

XP_OKT, XP_SETT, XP_REKORD, XP_UKEMAAL = 100, 2, 25, 150
MAKS_REKORD_XP_PER_OKT = 3   # nybegynnere setter rekorder nesten hver gang – XP-en skal ikke løpe løpsk
AKTIVITETSMAAL = 150          # minutter per uke (WHO/Helsedirektoratet)
SOVNMAAL_MIN = 7.5 * 60

NIVAANAVN = ["Nybegynner", "Lærling", "Jernvenn", "Stålvilje", "Vektbærer", "Løfter", "Kraftkar",
             "Jernhard", "Stålmester", "Titan", "Legende"]

MERKER = [
    # nøkkel, tittel, beskrivelse, ikon (emoji), felt, terskel
    ("okt1", "Første økt", "Fullfør din første økt", "🎯", "okter", 1),
    ("okt10", "Ti på topp", "10 fullførte økter", "🔟", "okter", 10),
    ("okt25", "Kvartsjef", "25 fullførte økter", "🥉", "okter", 25),
    ("okt50", "Halvsekel", "50 fullførte økter", "🥈", "okter", 50),
    ("okt100", "Hundreklubben", "100 fullførte økter", "🥇", "okter", 100),
    ("rek1", "Ny rekord!", "Sett din første personlige rekord", "⚡", "rekorder", 1),
    ("rek10", "Rekordjeger", "10 personlige rekorder", "🏆", "rekorder", 10),
    ("uke1", "Full uke", "Nå ukemålet for styrkeøkter", "✅", "ukemaal", 1),
    ("rekke4", "Fire på rad", "Nå ukemålet fire uker på rad", "🔥", "beste_rekke", 4),
    ("rekke12", "Vanen sitter", "Nå ukemålet tolv uker på rad", "💎", "beste_rekke", 12),
    ("tonn", "Tonnløfter", "Løft 1 000 kg totalt i én økt", "🏋️", "maks_okt_kg", 1000),
    ("tonn10", "Ti tonn", "Løft 10 000 kg totalt", "🏗️", "totalt_kg", 10000),
    ("tonn100", "Hundre tonn", "Løft 100 000 kg totalt", "🚀", "totalt_kg", 100000),
    ("ringer", "Alle ringer", "Lukk alle ringene i én uke", "⭕", "ringuker", 1),
]


def niva(xp: int) -> dict:
    """Nivå n krever 200·n·(n−1) XP: 0, 400, 1200, 2400, 4000 … (ca. ett nivå i måneden etter de første ukene)."""
    n = 1
    while 200 * (n + 1) * n <= xp:
        n += 1
    fra, til = 200 * n * (n - 1), 200 * (n + 1) * n
    return {"nr": n, "navn": NIVAANAVN[min(n - 1, len(NIVAANAVN) - 1)], "xp": xp, "fra": fra, "til": til,
            "andel": round((xp - fra) / (til - fra), 3)}


def _uke_start(sb: "Styrkeboka", d):
    d = sb.lokal(d)
    return (d - timedelta(days=d.weekday())).replace(hour=0, minute=0, second=0, microsecond=0)


def status(sb: "Styrkeboka", pid: int) -> dict:
    import kropp
    p = sb.profil(pid)
    plan = int(p.get("dager_per_uke") or 3)
    okter = sb.db.alle("SELECT id, startet FROM okter WHERE profil_id = ? AND status = 'fullfort' ORDER BY startet", (pid,))
    sett = sb.db.alle(
        "SELECT s.okt_id, s.ovelse, s.vekt, s.reps, o.startet FROM sett s JOIN okter o ON o.id = s.okt_id "
        "WHERE o.profil_id = ? AND o.status = 'fullfort' AND s.oppvarming = 0 ORDER BY o.startet, s.tid", (pid,))
    denne_mandag = _uke_start(sb, naa())

    # rekorder: ny beste estimerte 1RM (eller flere reps uten vekt) på en øvelse du har gjort før
    beste: dict[str, float] = {}
    rekorder, rekorder_uka = 0, []
    rekord_xp, rekord_xp_uka = 0, 0
    per_okt: dict[int, dict[str, float]] = {}
    for s in sett:
        verdi = P.e1rm(s["vekt"], s["reps"]) if s["vekt"] else (s["reps"] or 0) / 100
        if verdi:
            m = per_okt.setdefault(s["okt_id"], {})
            m[s["ovelse"]] = max(m.get(s["ovelse"], 0), verdi)
    startet = {o["id"]: o["startet"] for o in okter}
    for oid in sorted(per_okt, key=lambda i: startet.get(i, "")):
        i_okta = 0
        uka = sb.lokal(startet[oid]) >= denne_mandag
        for ov, v in per_okt[oid].items():
            if ov in beste and v > beste[ov] * 1.001:
                rekorder += 1
                i_okta += 1
                if uka:
                    rekorder_uka.append(sb.ovelse(ov)["navn"])
            beste[ov] = max(beste.get(ov, 0), v)
        x = min(i_okta, MAKS_REKORD_XP_PER_OKT) * XP_REKORD
        rekord_xp += x
        rekord_xp_uka += x if uka else 0

    kg_per_okt: dict[int, float] = {}
    for s in sett:
        kg_per_okt[s["okt_id"]] = kg_per_okt.get(s["okt_id"], 0) + (s["vekt"] or 0) * (s["reps"] or 0)
    totalt_kg = sum(kg_per_okt.values())

    # uker: økter per uke siden første økt, for ukemål og rekker
    per_uke: dict[str, int] = {}
    for o in okter:
        k = _uke_start(sb, o["startet"]).date().isoformat()
        per_uke[k] = per_uke.get(k, 0) + 1
    ukemaal = sum(1 for n in per_uke.values() if n >= plan)
    beste_rekke = rekke = 0
    if okter:
        u = _uke_start(sb, okter[0]["startet"])
        while u <= denne_mandag:
            n = per_uke.get(u.date().isoformat(), 0)
            if n >= plan:
                rekke += 1
                beste_rekke = max(beste_rekke, rekke)
            elif u < denne_mandag:
                rekke = 0
            u += timedelta(weeks=1)

    # kondisjon: XP for minutter utenom styrke (1 XP per 2 aktivitetsminutter, maks 60 per aktivitet)
    akt = sb.db.alle("SELECT * FROM aktiviteter WHERE profil_id = ? AND type != 'styrke'", (pid,))
    akt_xp = sum(min(60, round(kropp.aktivitetsminutter(a) / 2)) for a in akt)

    # denne uka: ringene
    uke = kropp.uker(sb, pid, 1)[-1]
    denne = per_uke.get(denne_mandag.date().isoformat(), 0)
    sett_uka = sum(1 for s in sett if sb.lokal(s["startet"]) >= denne_mandag)
    sovn = sb.db.alle("SELECT verdi FROM maalinger WHERE profil_id = ? AND type = 'sovn_min' AND dato >= ?",
                      (pid, denne_mandag.date().isoformat()))
    ringer = [{"nokkel": "styrke", "navn": "Styrke", "verdi": denne, "maal": plan, "enhet": "økter"},
              {"nokkel": "aktivitet", "navn": "Aktivitet", "verdi": uke["minutter"], "maal": AKTIVITETSMAAL, "enhet": "min"}]
    if sovn:
        snitt = sum(r["verdi"] for r in sovn) / len(sovn)
        ringer.append({"nokkel": "sovn", "navn": "Søvn", "verdi": round(snitt / 60, 1), "maal": SOVNMAAL_MIN / 60,
                       "enhet": "t snitt"})
    else:
        ringer.append({"nokkel": "sett", "navn": "Sett", "verdi": sett_uka, "maal": plan * 15, "enhet": "sett"})
    for r in ringer:
        r["andel"] = round(r["verdi"] / r["maal"], 3) if r["maal"] else 0
    alle_lukket = all(r["andel"] >= 1 for r in ringer)

    # uke-kjeden: mandag–søndag
    i_dag = sb.lokal(naa()).date()
    dager = []
    styrkedager = {sb.lokal(o["startet"]).date() for o in okter if sb.lokal(o["startet"]) >= denne_mandag}
    aktdager = {sb.lokal(a["start"]).date() for a in akt if sb.lokal(a["start"]) >= denne_mandag}
    for i in range(7):
        d = denne_mandag.date() + timedelta(days=i)
        dager.append({"dato": d.isoformat(), "styrke": d in styrkedager, "aktivitet": d in aktdager,
                      "i_dag": d == i_dag, "fremtid": d > i_dag})

    xp = len(okter) * XP_OKT + len(sett) * XP_SETT + rekord_xp + ukemaal * XP_UKEMAAL + akt_xp
    xp_uka = (denne * XP_OKT + sett_uka * XP_SETT + rekord_xp_uka + (XP_UKEMAAL if denne >= plan else 0)
              + sum(min(60, round(kropp.aktivitetsminutter(a) / 2)) for a in akt if sb.lokal(a["start"]) >= denne_mandag))

    felt = {"okter": len(okter), "rekorder": rekorder, "ukemaal": ukemaal, "beste_rekke": beste_rekke,
            "maks_okt_kg": max(kg_per_okt.values() or [0]), "totalt_kg": totalt_kg,
            "ringuker": 1 if alle_lukket else 0}
    # merker som er oppnådd én gang beholdes (f.eks. «Alle ringer»), og nye feires på forsiden
    lagret = sb.db.innstillinger().get(f"spill-{pid}") or {}
    hadde = set(lagret.get("merker") or [])
    merker, neste = [], None
    for nokkel, tittel, besk, ikon, f, terskel in MERKER:
        har = felt[f] >= terskel or nokkel in hadde
        m = {"nokkel": nokkel, "tittel": tittel, "beskrivelse": besk, "ikon": ikon, "oppnadd": har,
             "fremdrift": round(min(1, felt[f] / terskel), 3), "verdi": round(felt[f]), "terskel": terskel}
        merker.append(m)
        if not har and (neste is None or m["fremdrift"] > neste["fremdrift"]):
            neste = m
    naa_har = {m["nokkel"] for m in merker if m["oppnadd"]}
    nye = [m for m in merker if m["nokkel"] in naa_har - hadde] if lagret else []   # ikke feire alt første gang
    nv = niva(xp)
    nytt_niva = bool(lagret) and nv["nr"] > int(lagret.get("niva") or nv["nr"])
    if naa_har != hadde or nv["nr"] != lagret.get("niva"):
        sb.db.lagre_innstilling(f"spill-{pid}", {"merker": sorted(naa_har | hadde), "niva": nv["nr"]})
    return {
        "nye_merker": nye, "nytt_niva": nytt_niva,
        "niva": nv, "xp_uka": xp_uka, "ringer": ringer, "alle_lukket": alle_lukket, "dager": dager,
        "rekke": rekke, "beste_rekke": beste_rekke, "rekorder": rekorder, "rekorder_uka": rekorder_uka[:5],
        "okter": len(okter), "totalt_kg": round(totalt_kg), "merker": merker, "neste_merke": neste,
        "oppnadd": sum(1 for m in merker if m["oppnadd"]),
    }
