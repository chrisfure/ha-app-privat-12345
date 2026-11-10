"""Løpeperioder: velg en periode (f.eks. sommeren) med 1–3 løpeturer i uka ved siden av styrketreningen.

Prinsipper:
* De fleste turene rolige (sone 2), én hard økt i uka for kondisjon (4×4 min i sone 4 – godt dokumentert
  for VO₂max, bl.a. fra NTNU), og en langtur for utholdenhet.
* Gradvis økning, og hver 4. uke litt lettere.
* Nybegynnere starter med løp/gå-intervaller.
* Harde løpeøkter bør ikke ligge rett før en tung beinøkt; med «juster styrke» tas ett sett bort på
  hjelpeøvelsene for bein i perioden, så totalbelastningen holdes nede.
"""
from __future__ import annotations

from datetime import date, timedelta
from typing import TYPE_CHECKING

from db import naa, til_iso

if TYPE_CHECKING:
    from logikk import Styrkeboka

NIVAA = {"nybegynner": "Nybegynner (løp/gå)", "vanlig": "Løper av og til", "erfaren": "Løper jevnlig"}
MAAL = {"form": "Bedre form", "5km": "5 km", "10km": "10 km", "halvmaraton": "Halvmaraton"}
LANGTUR_TAK = {"form": 60, "5km": 50, "10km": 75, "halvmaraton": 110}
BEIN_HJELP = {"utfall", "sete", "bakside_iso", "forside_iso", "legger"}
UKEDAGER = ["mandag", "tirsdag", "onsdag", "torsdag", "fredag", "lørdag", "søndag"]
# standarddager: rolige turer og intervall midt i uka, langtur i helga
STANDARD_DAGER = {1: [5], 2: [1, 5], 3: [1, 3, 6]}


LOPENDE_TIL = "2099-12-31"   # «til jeg skrur av»


def lopende(p: dict) -> bool:
    return (p.get("til") or "") >= "2090"


def har_molle(sb: "Styrkeboka") -> bool:
    return any("tredemolle" in (u.get("utstyr") or []) for u in sb.utstyrsprofiler())


MOLLE_TIPS = {
    "rolig": "På tredemølle: 1 % stigning og en fart der du kan prate.",
    "langtur": "På tredemølle: 1 % stigning, rolig fart – varier gjerne stigningen litt underveis.",
    "intervall": "På tredemølle: 1 % stigning. Øk farten i dragene og gå eller jogg rolig på båndet i pausene.",
    "lopgaa": "På tredemølle: 1 % stigning – bytt mellom rolig jogg og rask gange på båndet.",
}


def lopedager(p: dict) -> list[int]:
    dager = sorted({int(d) for d in (p.get("lopedager") or []) if str(d).isdigit() and 0 <= int(d) <= 6})
    n = int(p.get("okter_per_uke") or 2)
    return dager[:3] if dager else STANDARD_DAGER.get(n, [1, 5])

# løp/gå-progresjon (løp min, gå min, repetisjoner) – uke 1 til 8
LOP_GAA = [(1, 1.5, 10), (1.5, 1.5, 8), (2, 1.5, 7), (3, 1.5, 6), (5, 2, 4), (8, 2, 3), (12, 2, 2), (25, 0, 1)]


def _mandag(d: date) -> date:
    return d - timedelta(days=d.weekday())


def ukeplan(p: dict, uke: int, makspuls: int | None = None) -> list[dict]:
    """Planlagte løpeturer for uke nr. «uke» (1 = første uke i perioden)."""
    n = int(p.get("okter_per_uke") or 2)
    niva = p.get("niva") or "vanlig"
    maal = p.get("maal") or "form"
    lett = uke % 4 == 0
    faktor = 0.75 if lett else 1.0

    def sone(nr: int) -> str:
        if not makspuls:
            return {2: "rolig – du skal klare å prate", 4: "hardt – du klarer bare noen få ord"}[nr]
        fra, til = {2: (0.6, 0.7), 4: (0.85, 0.95)}[nr]
        return f"sone {nr}: {round(makspuls * fra)}–{round(makspuls * til)} slag/min"

    okter: list[dict] = []
    if niva == "nybegynner" and uke <= len(LOP_GAA):
        lop, gaa, reps = LOP_GAA[uke - 1]
        if lop >= 25:
            beskr = f"Løp rolig sammenhengende i {lop} minutter."
        else:
            beskr = f"{reps} × ({str(lop).replace('.', ',')} min løp + {str(gaa).replace('.', ',')} min gange)."
        minutter = round(5 + reps * (lop + gaa) + 5)
        for i in range(n):
            okter.append({"type": "lopgaa", "tittel": "Løp/gå" if lop < 25 else "Rolig løpetur", "minutter": minutter,
                          "beskrivelse": f"5 min gange for å varme opp. {beskr} Avslutt med 5 min gange.",
                          "puls": sone(2)})
        return okter

    base = {"nybegynner": (20, 35, 35), "vanlig": (25, 45, 40), "erfaren": (35, 55, 60)}[niva]
    rolig = min(base[1], base[0] + round(2.5 * (uke - 1)))
    lang = min(LANGTUR_TAK[maal] + (20 if niva == "erfaren" else 0), base[2] + 5 * (uke - 1))
    if niva == "erfaren":
        drag = (5, 4) if uke < 4 else (6, 4)
    elif niva == "nybegynner":
        drag = (4, 2) if uke < 4 else (4, 3)
    else:
        drag = (4, 3) if uke < 3 else (4, 4) if uke < 6 else (5, 4)
    if lett:
        drag = (max(3, drag[0] - 1), drag[1])
    intervall = {"type": "intervall", "tittel": f"Intervall {drag[0]}×{drag[1]} min", "minutter": round(10 + drag[0] * drag[1] + (drag[0] - 1) * 3 + 5),
                 "beskrivelse": f"10 min rolig oppvarming. {drag[0]} drag à {drag[1]} min hardt, med 3 min rolig jogg mellom. 5 min rolig nedjogg.",
                 "puls": sone(4)}
    rolig_okt = {"type": "rolig", "tittel": "Rolig tur", "minutter": round(rolig * faktor),
                 "beskrivelse": f"{round(rolig * faktor)} min rolig løping. Skal kjennes lett – sakk av eller gå i bakkene om pulsen stiger.",
                 "puls": sone(2)}
    langtur = {"type": "langtur", "tittel": "Langtur", "minutter": round(lang * faktor),
               "beskrivelse": f"{round(lang * faktor)} min i rolig tempo. Den viktigste økta for utholdenhet – heller for rolig enn for fort.",
               "puls": sone(2)}
    okter = [rolig_okt, intervall, langtur][:max(1, min(3, n))]
    if n == 1 and uke % 2 == 0:
        okter = [intervall]
    return okter


def perioder(sb: "Styrkeboka", pid: int) -> list[dict]:
    return sb.db.alle("SELECT * FROM loepeperioder WHERE profil_id = ? ORDER BY fra", (pid,))


def aktiv_periode(sb: "Styrkeboka", pid: int, dag: date | None = None) -> dict | None:
    d = (dag or sb.lokal(naa()).date()).isoformat()
    return sb.db.en("SELECT * FROM loepeperioder WHERE profil_id = ? AND fra <= ? AND til >= ? ORDER BY fra DESC LIMIT 1", (pid, d, d))


def lagre_periode(sb: "Styrkeboka", pid: int, d: dict, lid: int | None = None) -> dict:
    from logikk import Feil
    apen = bool(d.get("lopende")) or not d.get("til") or str(d.get("til")) >= "2090"
    try:
        fra = date.fromisoformat(str(d.get("fra"))[:10]) if d.get("fra") else sb.lokal(naa()).date()
        til = date.fromisoformat(LOPENDE_TIL if apen else str(d.get("til"))[:10])
    except ValueError as e:
        raise Feil("Velg fra- og til-dato") from e
    if til < fra:
        raise Feil("Til-datoen må være etter fra-datoen")
    if not apen and (til - fra).days > 366:
        raise Feil("En tidsbegrenset løpeperiode kan vare maks ett år")
    dager = sorted({int(x) for x in (d.get("lopedager") or []) if str(x).isdigit() and 0 <= int(x) <= 6})[:3]
    n = len(dager) if dager else max(1, min(3, int(d.get("okter_per_uke") or 2)))
    rad = {"profil_id": pid, "fra": fra.isoformat(), "til": til.isoformat(), "okter_per_uke": n,
           "lopedager": dager or STANDARD_DAGER[n],
           "niva": d.get("niva") if d.get("niva") in NIVAA else "vanlig",
           "maal": d.get("maal") if d.get("maal") in MAAL else "form",
           "juster_styrke": 1 if d.get("juster_styrke", True) else 0}
    if lid is None:
        lid = sb.db.sett_inn("loepeperioder", {**rad, "opprettet": til_iso(naa())})
    else:
        sb.db.oppdater("loepeperioder", lid, rad)
    sb._varsle("profil", None)  # noqa: SLF001
    return sb.db.en("SELECT * FROM loepeperioder WHERE id = ?", (lid,))


def status(sb: "Styrkeboka", pid: int) -> dict:
    """Aktiv periode med denne ukas plan (hvilke turer som er gjort), og kommende perioder."""
    import kropp
    i_dag = sb.lokal(naa()).date()
    p = aktiv_periode(sb, pid, i_dag)
    kommende = [x for x in perioder(sb, pid) if x["fra"] > i_dag.isoformat()]
    molle = har_molle(sb)
    ut = {"perioder": [{**x, "lopende": lopende(x)} for x in perioder(sb, pid)], "kommende": kommende[:3], "aktiv": None,
          "nivaa": NIVAA, "maal": MAAL, "har_molle": molle}
    if not p:
        return ut
    start = _mandag(date.fromisoformat(p["fra"]))
    uke = (_mandag(i_dag) - start).days // 7 + 1
    uker_totalt = None if lopende(p) else (_mandag(date.fromisoformat(p["til"])) - start).days // 7 + 1
    makspuls = kropp.avledet(sb, pid).get("makspuls")
    plan = ukeplan(p, uke, makspuls)
    dager = lopedager(p)
    for i, o in enumerate(plan):
        if molle:
            o["molle"] = MOLLE_TIPS.get(o["type"])
        if i < len(dager):
            o["dag"] = UKEDAGER[dager[i]]
            o["dato"] = (_mandag(i_dag) + timedelta(days=dager[i])).isoformat()
    # løpeturer denne uka (minst 10 min) krysses av i rekkefølge
    mandag = sb.lokal(naa()).replace(hour=0, minute=0, second=0, microsecond=0) - timedelta(days=i_dag.weekday())
    turer = [kropp.berik(a) for a in sb.db.alle(
        "SELECT * FROM aktiviteter WHERE profil_id = ? AND type = 'loping' AND start >= ? AND varighet_s >= 600 ORDER BY start",
        (pid, til_iso(mandag)))]
    turer = [t for t in turer if sb.lokal(t["start"]).date().isoformat() >= p["fra"]]   # turer fra før løpingen ble lagt inn teller ikke
    for i, o in enumerate(plan):
        o["gjort"] = i < len(turer)
        if o["gjort"]:
            t = turer[i]
            o["logget"] = {"id": t["id"], "start": t["start"], "km": t["km"], "minutter": t["minutter"], "tempo": t["tempo"]}
    neste = next((o for o in plan if not o["gjort"]), None)
    ut["aktiv"] = {"periode": {**p, "lopende": lopende(p)}, "uke": uke, "uker": uker_totalt, "plan": plan, "neste": neste,
                   "gjort": sum(1 for o in plan if o["gjort"]), "lett_uke": uke % 4 == 0,
                   "neste_uke": ukeplan(p, uke + 1, makspuls) if uker_totalt is None or uke < uker_totalt else []}
    return ut


def juster_plan(sb: "Styrkeboka", pid: int, po: dict, monster: str, fast: bool) -> dict:
    """I en løpeperiode med «juster styrke»: ett sett mindre på hjelpeøvelser for bein (minst 2)."""
    p = aktiv_periode(sb, pid)
    if not p or not p.get("juster_styrke") or fast or monster not in BEIN_HJELP:
        return po
    sett = int(po.get("sett_plan") or po.get("sett") or 3)
    return {**po, "sett": max(2, sett - 1), "sett_plan": max(2, sett - 1)}


def ai_tekst(sb: "Styrkeboka", pid: int) -> str:
    s = status(sb, pid)
    a = s["aktiv"]
    if not a:
        if s["kommende"]:
            k = s["kommende"][0]
            return f"Planlagt løping fra {k['fra']} ({k['okter_per_uke']} turer/uke)."
        return ""
    p = a["periode"]
    return (f"Løping i opplegget: uke {a['uke']}{f' av ' + str(a['uker']) if a['uker'] else ''}, {p['okter_per_uke']} turer i uka, nivå {NIVAA[p['niva']].lower()}, "
            f"mål {MAAL[p['maal']].lower()}. Denne uka: " + "; ".join(f"{o['tittel']} ({'gjort' if o['gjort'] else 'gjenstår'})" for o in a["plan"])
            + (". Ett sett mindre på hjelpeøvelser for bein mens løpingen pågår." if p.get("juster_styrke") else ".")
            + (" Har tredemølle hjemme – turene kan tas inne." if s.get("har_molle") else ""))


# --------------------------------------------------------------------------- Garmin-økter
def _steg(nr: int, typ: str, sek: float | None, sone: int | None = None, barn: bool = False) -> dict:
    typer = {"warmup": 1, "cooldown": 2, "interval": 3, "recovery": 4}
    st = {"type": "ExecutableStepDTO", "stepOrder": nr, "stepType": {"stepTypeId": typer[typ], "stepTypeKey": typ},
          "endCondition": {"conditionTypeId": 2, "conditionTypeKey": "time"} if sek else {"conditionTypeId": 1, "conditionTypeKey": "lap.button"},
          "endConditionValue": round(sek) if sek else None,
          "targetType": {"workoutTargetTypeId": 4, "workoutTargetTypeKey": "heart.rate.zone"} if sone else
                        {"workoutTargetTypeId": 1, "workoutTargetTypeKey": "no.target"}}
    if sone:
        st["zoneNumber"] = sone
    if barn:
        st["childStepId"] = 1
    return st


def garmin_okt(o: dict, navn_prefiks: str = "Styrkeboka") -> dict:
    """Bygger en strukturert Garmin-løpeøkt (oppvarming, drag/pauser med pulssoner, nedjogg)."""
    sport = {"sportTypeId": 1, "sportTypeKey": "running"}
    steg: list[dict] = []
    if o["type"] == "intervall":
        import re
        m = re.search(r"(\d+)×(\d+)", o["tittel"])
        drag, minutter = (int(m.group(1)), int(m.group(2))) if m else (4, 4)
        steg = [_steg(1, "warmup", 600, 2),
                {"type": "RepeatGroupDTO", "stepOrder": 2, "stepType": {"stepTypeId": 6, "stepTypeKey": "repeat"},
                 "numberOfIterations": drag, "smartRepeat": False, "childStepId": 1,
                 "workoutSteps": [_steg(3, "interval", minutter * 60, 4, True), _steg(4, "recovery", 180, 1, True)]},
                _steg(5, "cooldown", 300, None)]
    elif o["type"] == "lopgaa":
        import re
        m = re.search(r"(\d+) × \(([\d,]+) min løp \+ ([\d,]+) min gange\)", o["beskrivelse"])
        if m:
            reps, lop, gaa = int(m.group(1)), float(m.group(2).replace(",", ".")), float(m.group(3).replace(",", "."))
            steg = [_steg(1, "warmup", 300, None),
                    {"type": "RepeatGroupDTO", "stepOrder": 2, "stepType": {"stepTypeId": 6, "stepTypeKey": "repeat"},
                     "numberOfIterations": reps, "smartRepeat": False, "childStepId": 1,
                     "workoutSteps": [_steg(3, "interval", lop * 60, 2, True), _steg(4, "recovery", gaa * 60, None, True)]},
                    _steg(5, "cooldown", 300, None)]
        else:
            steg = [_steg(1, "warmup", 300, None), _steg(2, "interval", (o["minutter"] - 10) * 60, 2), _steg(3, "cooldown", 300, None)]
    else:
        steg = [_steg(1, "interval", o["minutter"] * 60, 2)]
    return {"workoutName": f"{navn_prefiks}: {o['tittel']}"[:60], "description": o["beskrivelse"][:500],
            "sportType": sport, "workoutSegments": [{"segmentOrder": 1, "sportType": sport, "workoutSteps": steg}]}


def planlagte_garmin_okter(sb: "Styrkeboka", pid: int, uker_frem: int = 2) -> list[dict]:
    """Løpeturer som skal ligge i Garmin-kalenderen: fra i dag og «uker_frem» uker fram, i alle perioder."""
    import kropp
    i_dag = sb.lokal(naa()).date()
    makspuls = kropp.avledet(sb, pid).get("makspuls")
    ut = []
    for p in perioder(sb, pid):
        start = _mandag(date.fromisoformat(p["fra"]))
        slutt = date.fromisoformat(p["til"])
        dager = lopedager(p)
        for u in range(uker_frem + 1):
            mandag = _mandag(i_dag) + timedelta(weeks=u)
            if mandag + timedelta(days=6) < start or mandag > slutt:
                continue
            uke = (mandag - start).days // 7 + 1
            for i, o in enumerate(ukeplan(p, uke, makspuls)):
                if i >= len(dager):
                    break
                dato = mandag + timedelta(days=dager[i])
                if dato < i_dag or dato < date.fromisoformat(p["fra"]) or dato > slutt:
                    continue
                ut.append({"periode_id": p["id"], "dato": dato.isoformat(), "okt": o,
                           "nokkel": f"{p['id']}:{o['type']}:{o['tittel']}:{o['minutter']}"})
    return ut
