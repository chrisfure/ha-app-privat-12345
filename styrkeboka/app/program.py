"""Programmaler, progresjon og nøkkeltall – ren logikk uten database.

Prinsipper (se DOCS.md for kilder):
* Muskelstyrkende trening minst 2 dager i uka for alle store muskelgrupper (WHO 2020, Helsedirektoratet).
* Muskelvekst: ca. 10+ harde sett per muskelgruppe per uke, 6–15 reps nær utmattelse (Schoenfeld m.fl.).
* Generell form: 8–15 reps, 2–3 sett, 1–3 reps i reserve (ACSM).
* Rehab/forebygging: lettere belastning, 12–15 reps, rolig tempo, smertefritt – stopp ved smerte.
* Progresjon: «dobbel progresjon» – flere reps innen et intervall, deretter mer vekt.
"""
from __future__ import annotations

import math
from typing import Iterable

from ovelser import MONSTER, sekunder, steg_for, tilgjengelig, vektbasert

MAAL = {
    "generell": "Generell form",
    "muskelvekst": "Muskelvekst",
    "styrke": "Bli sterkere",
    "rehab": "Rehab / skadeforebygging",
}
ERFARING = {"nybegynner": "Nybegynner", "noe": "Litt erfaring", "erfaren": "Erfaren"}

# Øvelsesplasser per dagtype. Første del er kjernen, resten tas med når tiden strekker til.
DAGMALER = {
    "helkropp_a": ("Helkropp A", ["kne", "press_hor", "trekk_hor", "hofte", "kjerne", "skulderhelse", "triceps", "legger"]),
    "helkropp_b": ("Helkropp B", ["hofte", "press_vert", "trekk_vert", "utfall", "kjerne", "biceps", "skuldre_iso", "bakside_iso"]),
    "helkropp_c": ("Helkropp C", ["utfall", "press_hor", "trekk_vert", "sete", "kjerne", "skulderhelse", "biceps", "triceps"]),
    "overkropp_a": ("Overkropp A", ["press_hor", "trekk_hor", "press_vert", "trekk_vert", "skulderhelse", "biceps", "triceps", "skuldre_iso"]),
    "underkropp_a": ("Underkropp A", ["kne", "hofte", "utfall", "kjerne", "bakside_iso", "legger", "sete"]),
    "overkropp_b": ("Overkropp B", ["press_vert", "trekk_vert", "press_hor", "trekk_hor", "skuldre_iso", "triceps", "biceps", "bryst_iso"]),
    "underkropp_b": ("Underkropp B", ["hofte", "kne", "sete", "kjerne", "forside_iso", "utfall", "legger"]),
}
OPPSETT = {
    1: ["helkropp_a"],
    2: ["helkropp_a", "helkropp_b"],
    3: ["helkropp_a", "helkropp_b", "helkropp_c"],
    4: ["overkropp_a", "underkropp_a", "overkropp_b", "underkropp_b"],
    5: ["overkropp_a", "underkropp_a", "helkropp_c", "overkropp_b", "underkropp_b"],
    6: ["overkropp_a", "underkropp_a", "helkropp_a", "overkropp_b", "underkropp_b", "helkropp_b"],
}
STORE = {"kne", "hofte", "utfall", "press_hor", "press_vert", "trekk_hor", "trekk_vert", "sete"}


def antall_ovelser(minutter: int) -> int:
    if minutter <= 30:
        return 4
    if minutter <= 45:
        return 5
    if minutter <= 60:
        return 6
    if minutter <= 75:
        return 7
    return 8


def doseringsregler(maal: Iterable[str], erfaring: str) -> dict:
    """Sett, reps, hvile og reps-i-reserve for store og små øvelser ut fra mål."""
    m = set(maal) or {"generell"}
    rehab = "rehab" in m
    if "styrke" in m:
        stor = dict(sett=4, reps_min=5, reps_maks=8, hvile_s=150, rir=2)
    elif "muskelvekst" in m:
        stor = dict(sett=3, reps_min=8, reps_maks=12, hvile_s=120, rir=2)
    else:
        stor = dict(sett=3, reps_min=8, reps_maks=12, hvile_s=90, rir=2)
    liten = dict(sett=3, reps_min=10, reps_maks=15, hvile_s=60, rir=2)
    if "muskelvekst" in m and erfaring == "erfaren":
        stor["sett"] = 4
    if rehab:
        stor.update(sett=min(stor["sett"], 3), reps_min=max(stor["reps_min"], 10), reps_maks=max(stor["reps_maks"], 15),
                    hvile_s=min(stor["hvile_s"], 90), rir=3)
        liten.update(sett=min(liten["sett"], 3), reps_min=12, reps_maks=15, rir=3)
    if erfaring == "nybegynner":
        stor["sett"] = min(stor["sett"], 3)
        liten["sett"] = 2
        stor["rir"] = max(stor["rir"], 2)
        liten["rir"] = max(liten["rir"], 2)
    return {"stor": stor, "liten": liten}


def _poeng(o: dict, erfaring: str, rehab: bool, brukt: set[str]) -> float:
    p = 0.0
    if o["nokkel"] in brukt:
        p -= 10
    niva = o.get("niva", 1)
    if erfaring == "nybegynner":
        p -= (niva - 1) * 3
    elif erfaring == "noe":
        p -= max(0, niva - 2) * 2
    else:
        p += (niva - 1) * 0.5
    if rehab:
        p += 4 if o.get("skansom") else -6
    if o.get("sammensatt"):
        p += 1
    if o.get("type") in ("stang", "manualer", "maskin", "kabel"):
        p += 1.5  # lettere å måle fremgang
    if o.get("type") == "strikk":
        p -= 1
    if o.get("type") == "stang" and erfaring != "nybegynner" and not rehab:
        p += 0.75  # mest effektivt for progresjon når teknikken sitter
    return p


def velg_ovelse(monster: str, ovelser: list[dict], utstyr: set[str] | None, erfaring: str, rehab: bool,
                brukt: set[str], unnta: set[str] | None = None) -> dict | None:
    kandidater = [o for o in ovelser if o["monster"] == monster and tilgjengelig(o, utstyr) and not o.get("arkivert")
                  and o["nokkel"] not in (unnta or set())]
    if not kandidater:
        return None
    return max(kandidater, key=lambda o: (_poeng(o, erfaring, rehab, brukt), -len(o["utstyr"])))


def lag_program(profil: dict, ovelser: list[dict], utstyr: set[str] | None) -> dict:
    """Lager et program fra maler ut fra profilens mål, erfaring, tid og utstyr."""
    dager = max(1, min(6, int(profil.get("dager_per_uke") or 3)))
    minutter = int(profil.get("okt_minutter") or 60)
    erfaring = profil.get("erfaring") or "noe"
    maal = profil.get("maal") or ["generell"]
    rehab = "rehab" in maal
    regler = doseringsregler(maal, erfaring)
    n = antall_ovelser(minutter)
    brukt: set[str] = set()
    resultat = []
    for mal in OPPSETT[dager]:
        navn, plasser = DAGMALER[mal]
        valgt: list[tuple[str, dict]] = []
        # Første runde: én øvelse per plass. Andre runde (lite utstyr): fyll på med varianter.
        for runde, liste in ((1, plasser), (2, [*plasser, "kjerne", "kjerne"])):
            for monster in liste:
                if len(valgt) >= n or (runde == 2 and len(valgt) >= min(n, 4)):
                    break
                o = velg_ovelse(monster, ovelser, utstyr, erfaring, rehab, brukt, unnta={x["nokkel"] for _, x in valgt})
                if o:
                    valgt.append((monster, o))
                    brukt.add(o["nokkel"])
        dag_ovelser = []
        for monster, o in valgt:
            r = dict(regler["stor" if monster in STORE else "liten"])
            if sekunder(o):
                r.update(reps_min=20 if rehab or erfaring == "nybegynner" else 30, reps_maks=45 if rehab else 60, sett=min(r["sett"], 3))
            elif not vektbasert(o):
                r.update(reps_min=max(r["reps_min"], 8), reps_maks=max(r["reps_maks"], 15))
            dag_ovelser.append({"ovelse": o["nokkel"], **r, "notat": ""})
        resultat.append({"navn": navn, "ovelser": dag_ovelser})
    maaltekst = " + ".join(MAAL.get(m, m) for m in maal)
    return {
        "navn": f"{['', 'Helkropp', 'Helkropp', 'Helkropp', 'Over/under', 'Over/under + helkropp', 'Over/under + helkropp'][dager]} – {dager} dager",
        "beskrivelse": f"{maaltekst}. {dager} økter i uka à ca. {minutter} min.",
        "begrunnelse": _begrunnelse(dager, maal, erfaring),
        "kilde": "mal",
        "dager": resultat,
    }


def _begrunnelse(dager: int, maal: list[str], erfaring: str) -> str:
    deler = []
    if dager <= 3:
        deler.append("Helkroppsøkter gir hver muskelgruppe trening flere ganger i uka selv med få økter.")
    else:
        deler.append("Fordeling på overkropp og underkropp gir mer volum per muskel uten for lange økter.")
    if "muskelvekst" in maal:
        deler.append("For muskelvekst sikter vi mot 8–12 reps nær utmattelse og rundt 10 sett per muskelgruppe i uka.")
    if "styrke" in maal:
        deler.append("For styrke ligger de store løftene på 5–8 reps med god hvile.")
    if "rehab" in maal:
        deler.append("Rehab/forebygging: skånsomme øvelsesvalg, 12–15 reps og 3 reps i reserve. Det skal ikke gjøre vondt – stopp ved smerte.")
    if "generell" in maal:
        deler.append("Generell form: balansert program for hele kroppen, i tråd med anbefalingen om styrketrening minst to dager i uka.")
    if erfaring == "nybegynner":
        deler.append("Som ny starter vi med få sett og enkle øvelser – teknikk først, så øker vi.")
    return " ".join(deler)


# --------------------------------------------------------------------------- progresjon
def avrund(vekt: float, steg: float) -> float:
    fin = 0.5 if steg < 2.5 else 1.25 if steg == 2.5 else 0.5
    return round(round(vekt / fin) * fin, 2)


def foreslaa(ovelse: dict, plan: dict, tidligere: list[list[dict]]) -> dict:
    """Foreslår vekt og reps for neste økt.

    tidligere: arbeidssett fra de siste øktene med denne øvelsen, nyeste først.
    Returnerer {"kg", "reps", "tekst", "trend"} – trend er «opp», «likt», «ned» eller «ny».
    """
    rmin, rmaks = int(plan.get("reps_min") or 8), int(plan.get("reps_maks") or 12)
    rir_maal = plan.get("rir")
    enhet = "sek" if sekunder(ovelse) else "reps"
    if not tidligere or not tidligere[0]:
        if vektbasert(ovelse):
            tekst = f"Første gang: velg en vekt du klarer {rmin}–{rmaks} {enhet} med {rir_maal if rir_maal is not None else 2} i reserve."
        else:
            tekst = f"Første gang: sikt mot {rmin}–{rmaks} {enhet} med god teknikk."
        return {"kg": None, "reps": rmin, "tekst": tekst, "trend": "ny"}

    sist = tidligere[0]
    vekter = [s["vekt"] for s in sist if s.get("vekt") is not None]
    kg = max(vekter) if vekter else None
    # arbeidssett med den tyngste vekten
    sett = [s for s in sist if (s.get("vekt") if kg is not None else None) == kg] or sist
    reps = [int(s.get("reps") or 0) for s in sett]
    alle_topp = all(r >= rmaks for r in reps) and len(reps) >= max(1, int(plan.get("sett_plan") or plan.get("sett") or 1) - 1)
    rir_ok = all((s.get("rir") is None or rir_maal is None or s["rir"] >= rir_maal - 1) for s in sett)
    under = any(r < rmin for r in reps)

    def feilet(okt: list[dict]) -> bool:
        return any(int(s.get("reps") or 0) < rmin for s in okt)

    if not vektbasert(ovelse):
        if alle_topp:
            return {"kg": kg, "reps": rmaks, "trend": "opp",
                    "tekst": f"Du klarte {rmaks} {enhet} i alle sett – gjør øvelsen tyngre (vekt i hånden, tyngre strikk eller vanskeligere variant)."}
        maal = min(rmaks, max(reps) + 1) if reps else rmin
        return {"kg": kg, "reps": maal, "trend": "likt", "tekst": f"Prøv {maal} {enhet} i settene i dag."}

    if kg is None:
        return {"kg": None, "reps": rmin, "trend": "ny", "tekst": f"Velg en vekt du klarer {rmin}–{rmaks} {enhet} med."}
    steg = steg_for(ovelse, kg)
    if alle_topp and rir_ok:
        ny = avrund(kg + steg, steg)
        return {"kg": ny, "reps": rmin, "trend": "opp",
                "tekst": f"Sist: {_kg(kg)} × {', '.join(map(str, reps))}. Alle sett nådde {rmaks} – øk til {_kg(ny)} og sikt mot {rmin}+."}
    if under and len(tidligere) >= 2 and feilet(tidligere[1]):
        ny = avrund(kg * 0.9, steg)
        return {"kg": ny, "reps": rmin, "trend": "ned",
                "tekst": f"Under {rmin} reps to økter på rad – ta ned til {_kg(ny)} og bygg opp igjen med god teknikk."}
    maal = min(rmaks, max(reps) + 1) if not under else rmin
    return {"kg": kg, "reps": maal, "trend": "likt",
            "tekst": f"Sist: {_kg(kg)} × {', '.join(map(str, reps))}. Behold vekten og sikt mot {maal} reps."}


def _kg(v: float | None) -> str:
    if v is None:
        return ""
    return (f"{v:g}").replace(".", ",") + " kg"


def e1rm(vekt: float | None, reps: int | None) -> float | None:
    """Estimert 1RM (Epley). Kun meningsfullt for 1–12 reps."""
    if not vekt or not reps or reps < 1 or reps > 12:
        return None
    return round(vekt * (1 + reps / 30), 1) if reps > 1 else float(vekt)


def oppvarming(kg: float | None, ovelse: dict) -> list[dict]:
    """Enkel oppvarmingsstige for den første tunge øvelsen."""
    if not kg or ovelse.get("type") not in ("stang", "manualer", "maskin") or kg < 20:
        return []
    steg = steg_for(ovelse, kg)
    trinn = [(0.5, 8), (0.7, 5)] if kg < 60 else [(0.4, 8), (0.6, 5), (0.8, 3)]
    ut = []
    for andel, r in trinn:
        v = avrund(kg * andel, steg)
        if ovelse.get("type") == "stang":
            v = max(v, 20.0)
        ut.append({"kg": v, "reps": r})
    return ut


def beregn_tid(dag: list[dict]) -> int:
    """Grovt anslag på økttid i minutter (1 min per sett + hvile + 1,5 min bytte + 5 min oppvarming)."""
    sek = 300
    for o in dag:
        s = int(o.get("sett") or o.get("sett_plan") or 3)
        sek += s * 60 + max(0, s - 1) * int(o.get("hvile_s") or 90) + 90
    return math.ceil(sek / 60)


def monster_navn(m: str) -> str:
    return MONSTER.get(m, m)
