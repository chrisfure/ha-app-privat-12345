"""Dagsform: søvn, HRV, Body Battery, stress, treningsberedskap og restitusjon – sammenlignet med ditt eget snitt.

Vurderingen er bevisst enkel og forklarbar: hvert signal gir pluss eller minus ut fra egne grenser og
avvik fra de siste 14 dagene. Den foreslår om du bør kjøre på, justere ned eller ta en rolig dag.
"""
from __future__ import annotations

from datetime import date, timedelta
from typing import TYPE_CHECKING

import kropp

if TYPE_CHECKING:
    from logikk import Styrkeboka

NIVAA = {
    "god": {"tittel": "God dagsform", "rad": "Kjør på – en god dag for en tung økt eller intervaller."},
    "middels": {"tittel": "Middels dagsform", "rad": "Tren som planlagt, men hold igjen litt: ett sett mindre eller en rep ekstra i reserve."},
    "lav": {"tittel": "Lav dagsform", "rad": "Velg en lett økt – færre sett, rolig tur eller mobilitet – eller ta hviledag."},
}


def _dag(sb: "Styrkeboka", pid: int, typ: str, dag: str) -> float | None:
    r = sb.db.en("SELECT verdi FROM maalinger WHERE profil_id = ? AND type = ? AND dato = ?", (pid, typ, dag))
    return r["verdi"] if r else None


def _snitt(sb: "Styrkeboka", pid: int, typ: str, til: str, dager: int = 14) -> float | None:
    fra = (date.fromisoformat(til) - timedelta(days=dager)).isoformat()
    r = sb.db.alle("SELECT verdi FROM maalinger WHERE profil_id = ? AND type = ? AND dato >= ? AND dato < ?", (pid, typ, fra, til))
    return sum(x["verdi"] for x in r) / len(r) if len(r) >= 3 else None


def status(sb: "Styrkeboka", pid: int, dato: str | None = None) -> dict | None:
    dag = dato or kropp.lokal_dato(sb)
    verdier = {t: _dag(sb, pid, t, dag) for t in ("sovn_score", "sovn_min", "hrv", "body_battery", "stress", "beredskap", "restitusjon", "hvilepuls")}
    if not any(v is not None for v in verdier.values()):
        return None
    tekst = sb.db.innstillinger().get(f"status-{pid}") or {}
    poeng = 0.0
    grunner: list[str] = []

    def legg(p: float, grunn: str):
        nonlocal poeng
        poeng += p
        grunner.append(grunn)

    b = verdier["beredskap"]
    if b is not None:
        if b >= 70:
            legg(2, f"høy treningsberedskap ({b:g})")
        elif b < 40:
            legg(-2, f"lav treningsberedskap ({b:g})")
        elif b < 55:
            legg(-0.5, f"treningsberedskap {b:g}")
    s = verdier["sovn_score"]
    if s is not None:
        if s >= 80:
            legg(1, f"god søvn ({s:g})")
        elif s < 60:
            legg(-1.5, f"dårlig søvn ({s:g})")
    m = verdier["sovn_min"]
    if m is not None and m < 360:
        legg(-1, f"kort natt ({m / 60:.1f} t)".replace(".", ","))
    h, hs = verdier["hrv"], _snitt(sb, pid, "hrv", dag)
    if h is not None and hs:
        avvik = (h - hs) / hs
        if avvik < -0.15:
            legg(-1.5, f"HRV {h:g} ms – klart under ditt snitt ({hs:.0f})")
        elif avvik > 0.1:
            legg(0.5, f"HRV over snittet ({h:g} ms)")
    if str(tekst.get("hrv_status") or "").lower() in ("low", "poor", "unbalanced"):
        legg(-0.5, f"HRV-status «{tekst['hrv_status']}»")
    bb = verdier["body_battery"]
    if bb is not None:
        if bb >= 75:
            legg(1, f"Body Battery {bb:g} i morges")
        elif bb < 35:
            legg(-1.5, f"lav Body Battery ({bb:g})")
    hp, hps = verdier["hvilepuls"], _snitt(sb, pid, "hvilepuls", dag)
    if hp is not None and hps and hp - hps >= 5:
        legg(-1, f"hvilepuls {hp:g} – {hp - hps:.0f} over snittet")
    r = verdier["restitusjon"]
    if r is not None and r >= 24:
        legg(-1, f"{r:g} t restitusjonstid igjen")
    st = verdier["stress"]
    if st is not None and st >= 45:
        legg(-0.5, f"høyt stressnivå ({st:g})")
    niva = "god" if poeng >= 1.5 else "lav" if poeng <= -2 else "middels"
    return {"dato": dag, "niva": niva, **NIVAA[niva], "poeng": round(poeng, 1), "grunner": grunner, "verdier": verdier,
            "hrv_snitt": round(hs) if hs else None, "hrv_status": tekst.get("hrv_status"), "treningsstatus": tekst.get("treningsstatus")}


def ai_tekst(sb: "Styrkeboka", pid: int) -> str:
    s = status(sb, pid)
    if not s:
        return ""
    v = s["verdier"]
    deler = []
    navn = {"sovn_score": "søvnscore", "sovn_min": "søvn (min)", "hrv": "HRV ms", "body_battery": "Body Battery morgen",
            "stress": "stress snitt", "beredskap": "treningsberedskap", "restitusjon": "restitusjonstid t", "hvilepuls": "hvilepuls"}
    for k, n in navn.items():
        if v.get(k) is not None:
            deler.append(f"{n} {v[k]:g}")
    if s.get("hrv_snitt"):
        deler.append(f"HRV-snitt 14 d {s['hrv_snitt']}")
    if s.get("hrv_status"):
        deler.append(f"HRV-status {s['hrv_status']}")
    if s.get("treningsstatus"):
        deler.append(f"Garmin treningsstatus {s['treningsstatus']}")
    return f"DAGSFORM I DAG ({s['tittel'].lower()}): " + ", ".join(deler)
