"""Kropp og kondisjon: målinger over tid, løping/gåing og andre aktiviteter, og avledede verdier.

Referanser:
* WHO (2020) / Helsedirektoratet: 150–300 min moderat eller 75–150 min høy intensitet per uke
  (1 min høy intensitet regnes som 2 min moderat).
* Makspuls estimert med HUNT-formelen: 211 − 0,64 × alder (Nes m.fl., 2013).
* BMI = vekt / høyde²; midje/høyde-forhold under 0,5 regnes som gunstig.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import TYPE_CHECKING

from db import fra_iso, naa, til_iso

if TYPE_CHECKING:
    from logikk import Styrkeboka

MAALETYPER = {
    "vekt": {"navn": "Vekt", "enhet": "kg", "min": 20, "maks": 300, "desimaler": 1},
    "midje": {"navn": "Midjemål", "enhet": "cm", "min": 40, "maks": 200, "desimaler": 1},
    "fettprosent": {"navn": "Fettprosent", "enhet": "%", "min": 2, "maks": 70, "desimaler": 1},
    "hvilepuls": {"navn": "Hvilepuls", "enhet": "slag/min", "min": 25, "maks": 140, "desimaler": 0},
    "vo2max": {"navn": "VO₂max", "enhet": "ml/kg/min", "min": 10, "maks": 95, "desimaler": 0},
    "skritt": {"navn": "Skritt", "enhet": "skritt/dag", "min": 0, "maks": 100000, "desimaler": 0},
    "blodtrykk_sys": {"navn": "Blodtrykk (over)", "enhet": "mmHg", "min": 60, "maks": 260, "desimaler": 0},
    "blodtrykk_dia": {"navn": "Blodtrykk (under)", "enhet": "mmHg", "min": 30, "maks": 160, "desimaler": 0},
}

AKTIVITETSTYPER = {
    "loping": {"navn": "Løping", "intensitet": "hoy"},
    "gaing": {"navn": "Gåing", "intensitet": "moderat"},
    "tur": {"navn": "Fjelltur", "intensitet": "moderat"},
    "sykling": {"navn": "Sykling", "intensitet": "moderat"},
    "ski": {"navn": "Ski", "intensitet": "hoy"},
    "svomming": {"navn": "Svømming", "intensitet": "hoy"},
    "annet": {"navn": "Annet", "intensitet": "moderat"},
}

# Garmin-aktivitetstyper → våre typer. Styrketrening fra klokka hoppes over (logges i appen).
GARMIN_TYPER = {
    "running": "loping", "trail_running": "loping", "treadmill_running": "loping", "track_running": "loping",
    "indoor_running": "loping", "virtual_run": "loping", "obstacle_run": "loping", "ultra_run": "loping",
    "walking": "gaing", "casual_walking": "gaing", "speed_walking": "gaing", "indoor_walking": "gaing",
    "hiking": "tur", "mountaineering": "tur",
    "cycling": "sykling", "road_biking": "sykling", "mountain_biking": "sykling", "gravel_cycling": "sykling",
    "indoor_cycling": "sykling", "e_bike_fitness": "sykling", "e_bike_mountain": "sykling", "virtual_ride": "sykling",
    "cross_country_skiing_ws": "ski", "skate_skiing_ws": "ski", "backcountry_skiing": "ski", "cross_country_skiing": "ski",
    "resort_skiing_snowboarding_ws": "ski",
    "lap_swimming": "svomming", "open_water_swimming": "svomming",
}
HOPP_OVER = {"strength_training", "indoor_cardio", "yoga", "pilates", "breathwork"}


def lokal_dato(sb: "Styrkeboka", d: datetime | str | None = None) -> str:
    return sb.lokal(d or naa()).date().isoformat()


# --------------------------------------------------------------------------- målinger
def lagre_maaling(sb: "Styrkeboka", pid: int, typ: str, verdi, dato: str | None = None, kilde: str = "manuell") -> dict | None:
    if typ not in MAALETYPER:
        raise ValueError(typ)
    t = MAALETYPER[typ]
    try:
        v = float(str(verdi).replace(",", "."))
    except (TypeError, ValueError):
        return None
    if not t["min"] <= v <= t["maks"]:
        return None
    dato = (dato or lokal_dato(sb))[:10]
    date.fromisoformat(dato)
    # manuelle målinger overskrives ikke av automatisk henting samme dag
    finnes = sb.db.en("SELECT kilde FROM maalinger WHERE profil_id = ? AND type = ? AND dato = ?", (pid, typ, dato))
    if finnes and finnes["kilde"] == "manuell" and kilde != "manuell":
        return None
    sb.db.kjor("INSERT INTO maalinger (profil_id, type, verdi, dato, tid, kilde) VALUES (?, ?, ?, ?, ?, ?) "
               "ON CONFLICT(profil_id, type, dato) DO UPDATE SET verdi = excluded.verdi, tid = excluded.tid, kilde = excluded.kilde",
               (pid, typ, round(v, 2), dato, til_iso(naa()), kilde))
    if typ == "vekt":
        siste = sb.db.en("SELECT verdi FROM maalinger WHERE profil_id = ? AND type = 'vekt' ORDER BY dato DESC LIMIT 1", (pid,))
        if siste:
            sb.db.kjor("UPDATE profiler SET kroppsvekt = ? WHERE id = ?", (siste["verdi"], pid))
    return sb.db.en("SELECT * FROM maalinger WHERE profil_id = ? AND type = ? AND dato = ?", (pid, typ, dato))


def slett_maaling(sb: "Styrkeboka", mid: int) -> None:
    sb.db.slett("maalinger", mid)


def maalinger(sb: "Styrkeboka", pid: int, typ: str, dager: int | None = None) -> list[dict]:
    sql, args = "SELECT * FROM maalinger WHERE profil_id = ? AND type = ?", [pid, typ]
    if dager:
        sql += " AND dato >= ?"
        args.append((date.fromisoformat(lokal_dato(sb)) - timedelta(days=dager)).isoformat())
    return sb.db.alle(sql + " ORDER BY dato", tuple(args))


def siste(sb: "Styrkeboka", pid: int, typ: str) -> dict | None:
    return sb.db.en("SELECT * FROM maalinger WHERE profil_id = ? AND type = ? ORDER BY dato DESC LIMIT 1", (pid, typ))


def endring(sb: "Styrkeboka", pid: int, typ: str, dager: int = 30) -> float | None:
    """Endring fra rundt «dager» siden til siste måling (bruker snitt av nærmeste målinger for å dempe svingninger)."""
    rader = maalinger(sb, pid, typ, dager + 7)
    if len(rader) < 2:
        return None
    grense = (date.fromisoformat(rader[-1]["dato"]) - timedelta(days=dager)).isoformat()
    tidlige = [r["verdi"] for r in rader if r["dato"] <= (date.fromisoformat(grense) + timedelta(days=3)).isoformat()][-3:] or [rader[0]["verdi"]]
    sene = [r["verdi"] for r in rader[-3:]]
    return round(sum(sene) / len(sene) - sum(tidlige) / len(tidlige), 1)


# --------------------------------------------------------------------------- aktiviteter
def importer_garmin(sb: "Styrkeboka", pid: int, akt: dict) -> bool:
    """Lagrer én aktivitet fra Garmin Connect-sensoren. Koordinater lagres ikke. True hvis ny."""
    gtype = str(akt.get("activityType") or "")
    if not akt.get("activityId") or gtype in HOPP_OVER:
        return False
    typ = GARMIN_TYPER.get(gtype, "annet")
    start = fra_iso(str(akt.get("startTime") or "")) if akt.get("startTime") else None
    if not start:
        return False
    eid = f"garmin-{akt['activityId']}"
    if sb.db.verdi("SELECT 1 FROM aktiviteter WHERE profil_id = ? AND ekstern_id = ?", (pid, eid)):
        return False

    def tall(k, f=float):
        v = akt.get(k)
        try:
            return f(v) if v is not None else None
        except (TypeError, ValueError):
            return None
    varighet = tall("movingDuration") if typ in ("sykling",) and tall("movingDuration") else tall("duration")
    sb.db.sett_inn("aktiviteter", {
        "profil_id": pid, "ekstern_id": eid, "type": typ, "navn": str(akt.get("activityName") or "")[:80],
        "start": til_iso(start), "varighet_s": varighet, "distanse_m": tall("distance"), "hoydemeter": tall("elevationGain"),
        "snittpuls": tall("averageHR", lambda x: int(round(float(x)))), "makspuls": tall("maxHR", lambda x: int(round(float(x)))),
        "kalorier": tall("calories", lambda x: int(round(float(x)))), "skritt": tall("steps", lambda x: int(float(x))),
        "moderate_min": tall("moderateIntensityMinutes", int), "hoy_min": tall("vigorousIntensityMinutes", int),
        "belastning": tall("activityTrainingLoad"), "aerob_effekt": tall("aerobicTrainingEffect"), "kilde": "garmin",
    })
    return True


def lagre_aktivitet(sb: "Styrkeboka", pid: int, d: dict, aid: int | None = None) -> dict:
    from logikk import Feil
    typ = d.get("type")
    if typ not in AKTIVITETSTYPER:
        raise Feil("Velg type aktivitet")
    start = fra_iso(d.get("start")) or naa()
    try:
        minutter = float(str(d.get("minutter") or "").replace(",", "."))
    except ValueError:
        minutter = 0
    if not 1 <= minutter <= 1440:
        raise Feil("Skriv inn varighet i minutter")
    km = d.get("km")
    km = float(str(km).replace(",", ".")) if km not in (None, "") else None
    if km is not None and not 0 <= km <= 500:
        raise Feil("Ugyldig distanse")
    puls = int(d["snittpuls"]) if str(d.get("snittpuls") or "").isdigit() else None
    hoy = AKTIVITETSTYPER[typ]["intensitet"] == "hoy"
    rad = {"type": typ, "navn": str(d.get("navn") or AKTIVITETSTYPER[typ]["navn"])[:80], "start": til_iso(start),
           "varighet_s": minutter * 60, "distanse_m": km * 1000 if km is not None else None, "snittpuls": puls,
           "moderate_min": 0 if hoy else round(minutter), "hoy_min": round(minutter) if hoy else 0,
           "notat": str(d.get("notat") or "")[:300]}
    if aid is None:
        aid = sb.db.sett_inn("aktiviteter", {"profil_id": pid, "kilde": "manuell", **rad})
    else:
        sb.db.oppdater("aktiviteter", aid, rad)
    return aktivitet(sb, aid)


def aktivitet(sb: "Styrkeboka", aid: int) -> dict:
    a = sb.db.en("SELECT * FROM aktiviteter WHERE id = ?", (aid,))
    return berik(a) if a else None


def berik(a: dict) -> dict:
    a["typenavn"] = AKTIVITETSTYPER.get(a["type"], AKTIVITETSTYPER["annet"])["navn"]
    a["minutter"] = round((a.get("varighet_s") or 0) / 60)
    a["km"] = round(a["distanse_m"] / 1000, 2) if a.get("distanse_m") else None
    # tempo (min/km) for løping og gåing
    if a["km"] and a["type"] in ("loping", "gaing", "tur") and a.get("varighet_s"):
        sek = a["varighet_s"] / a["km"]
        a["tempo"] = f"{int(sek // 60)}:{int(sek % 60):02d}"
    else:
        a["tempo"] = None
    if a["km"] and a["type"] == "sykling" and a.get("varighet_s"):
        a["fart"] = round(a["km"] / (a["varighet_s"] / 3600), 1)
    return a


def aktiviteter(sb: "Styrkeboka", pid: int, dager: int = 90, grense: int = 100) -> list[dict]:
    fra = til_iso(naa() - timedelta(days=dager))
    return [berik(a) for a in sb.db.alle(
        "SELECT * FROM aktiviteter WHERE profil_id = ? AND start >= ? ORDER BY start DESC LIMIT ?", (pid, fra, grense))]


def aktivitetsminutter(a: dict) -> float:
    """WHO-ekvivalente minutter: moderat + 2 × høy intensitet."""
    mod, hoy = a.get("moderate_min"), a.get("hoy_min")
    if mod is None and hoy is None:
        m = (a.get("varighet_s") or 0) / 60
        return m * 2 if AKTIVITETSTYPER.get(a["type"], {}).get("intensitet") == "hoy" else m
    return (mod or 0) + 2 * (hoy or 0)


def uker(sb: "Styrkeboka", pid: int, antall: int = 12) -> list[dict]:
    """Per uke: aktivitetsminutter, km løping/gåing og antall styrkeøkter."""
    naa_l = sb.lokal(naa())
    mandag = (naa_l - timedelta(days=naa_l.weekday())).replace(hour=0, minute=0, second=0, microsecond=0)
    ut = []
    for i in range(antall - 1, -1, -1):
        start, slutt = mandag - timedelta(weeks=i), mandag - timedelta(weeks=i - 1)
        akt = [berik(a) for a in sb.db.alle("SELECT * FROM aktiviteter WHERE profil_id = ? AND start >= ? AND start < ?",
                                            (pid, til_iso(start), til_iso(slutt)))]
        styrke = sb.db.alle("SELECT startet, avsluttet FROM okter WHERE profil_id = ? AND status = 'fullfort' AND startet >= ? AND startet < ?",
                            (pid, til_iso(start), til_iso(slutt)))
        # styrketrening teller som moderat aktivitet i tiden økta varte (maks 90 min)
        styrke_min = sum(min(90, max(0, ((fra_iso(o["avsluttet"]) or fra_iso(o["startet"])) - fra_iso(o["startet"])).total_seconds() / 60))
                         for o in styrke if o.get("avsluttet"))
        per_type: dict[str, dict] = {}
        for a in akt:
            t = per_type.setdefault(a["type"], {"antall": 0, "km": 0.0, "minutter": 0})
            t["antall"] += 1
            t["km"] = round(t["km"] + (a["km"] or 0), 1)
            t["minutter"] += a["minutter"]
        ut.append({
            "uke": start.isocalendar()[1], "start": start.date().isoformat(),
            "minutter": round(sum(aktivitetsminutter(a) for a in akt) + styrke_min),
            "kondisjon_min": round(sum(aktivitetsminutter(a) for a in akt)),
            "styrke_min": round(styrke_min), "styrkeokter": len(styrke), "per_type": per_type,
            "km_loping": round(sum(a["km"] or 0 for a in akt if a["type"] == "loping"), 1),
            "km_gaing": round(sum(a["km"] or 0 for a in akt if a["type"] in ("gaing", "tur")), 1),
        })
    return ut


# --------------------------------------------------------------------------- avledet
def alder(p: dict) -> int | None:
    fa = p.get("fodselsaar")
    return date.today().year - int(fa) if fa else None


def avledet(sb: "Styrkeboka", pid: int) -> dict:
    p = sb.profil(pid)
    a = alder(p)
    vekt = (siste(sb, pid, "vekt") or {}).get("verdi") or p.get("kroppsvekt")
    hoyde = p.get("hoyde_cm")
    midje = (siste(sb, pid, "midje") or {}).get("verdi")
    hvile = (siste(sb, pid, "hvilepuls") or {}).get("verdi")
    ut: dict = {"alder": a, "vekt": vekt, "hoyde_cm": hoyde}
    if vekt and hoyde:
        bmi = vekt / (hoyde / 100) ** 2
        ut["bmi"] = round(bmi, 1)
        ut["bmi_kategori"] = "under 18,5" if bmi < 18.5 else "18,5–24,9" if bmi < 25 else "25–29,9" if bmi < 30 else "30 eller mer"
    if midje and hoyde:
        ut["midje_hoyde"] = round(midje / hoyde, 2)
    if a:
        maks = round(211 - 0.64 * a)
        ut["makspuls"] = maks
        # soner etter prosent av makspuls (vanlig 5-sonemodell)
        ut["soner"] = [{"sone": i + 1, "fra": round(maks * f), "til": round(maks * t)}
                       for i, (f, t) in enumerate([(0.5, 0.6), (0.6, 0.7), (0.7, 0.8), (0.8, 0.9), (0.9, 1.0)])]
        if hvile:
            ut["pulsreserve"] = maks - int(hvile)
    return ut


def oversikt(sb: "Styrkeboka", pid: int) -> dict:
    nokkel = {}
    for typ in MAALETYPER:
        s = siste(sb, pid, typ)
        if s:
            nokkel[typ] = {"verdi": s["verdi"], "dato": s["dato"], "kilde": s["kilde"],
                           "endring_30": endring(sb, pid, typ, 30) if typ in ("vekt", "midje", "fettprosent", "hvilepuls", "vo2max") else None}
    u = uker(sb, pid, 12)
    return {"maalinger": nokkel, "avledet": avledet(sb, pid), "uker": u, "denne_uka": u[-1],
            "aktiviteter": aktiviteter(sb, pid, 60, 30), "maaletyper": MAALETYPER, "aktivitetstyper": AKTIVITETSTYPER,
            "koblinger": sb.profil(pid).get("koblinger") or {}}


def ai_tekst(sb: "Styrkeboka", pid: int) -> str:
    """Kort om kropp og kondisjon til AI-treneren."""
    av = avledet(sb, pid)
    deler = []
    if av.get("alder"):
        deler.append(f"Alder: {av['alder']} år")
    p = sb.profil(pid)
    if p.get("kjonn") in ("mann", "kvinne"):
        deler.append(f"Kjønn: {p['kjonn']}")
    if av.get("hoyde_cm"):
        deler.append(f"Høyde: {av['hoyde_cm']:g} cm")
    if av.get("vekt"):
        e = endring(sb, pid, "vekt", 30)
        deler.append(f"Vekt: {av['vekt']:g} kg" + (f" ({e:+g} kg siste 30 dager)" if e is not None else ""))
    for typ in ("fettprosent", "midje", "hvilepuls", "vo2max"):
        s = siste(sb, pid, typ)
        if s:
            deler.append(f"{MAALETYPER[typ]['navn']}: {s['verdi']:g} {MAALETYPER[typ]['enhet']}")
    akt = aktiviteter(sb, pid, 14, 20)
    if akt:
        deler.append("Kondisjon siste 14 dager: " + "; ".join(
            f"{sb.lokal(a['start']):%d.%m} {a['typenavn'].lower()} {a['minutter']} min"
            + (f" {a['km']:g} km" if a['km'] else "") + (f" snittpuls {a['snittpuls']}" if a.get('snittpuls') else "")
            for a in akt))
    u = uker(sb, pid, 2)
    deler.append(f"Aktivitetsminutter (moderat + 2×høy, inkl. styrke) denne uka: {u[-1]['minutter']}, forrige uke: {u[0]['minutter']} (anbefalt 150–300)")
    return "\n".join(deler)
