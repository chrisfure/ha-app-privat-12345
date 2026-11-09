"""Intervalløkter: HIIT, Tabata, sirkel, EMOM og AMRAP – med ferdige maler, forslag og logging.

Oppsettet lagres som JSON og er det samme klokka i appen bruker:
  {"format": "hiit", "arbeid": 40, "hvile": 20, "runder": 3, "rundehvile": 60,
   "minutter": 12, "ovelser": [{"nokkel": "burpees", "reps": 10}, …]}
Tidsstyrte formater (hiit, tabata, sirkel) bruker arbeid/hvile/runder/rundehvile.
EMOM bruker minutter (én øvelse per minutt, på rundgang), AMRAP bruker minutter og reps per øvelse.
"""
from __future__ import annotations

import random
from datetime import timedelta
from typing import TYPE_CHECKING

from db import fra_iso, naa, til_iso
from ovelser import tilgjengelig

if TYPE_CHECKING:
    from logikk import Styrkeboka

FORMATER = {
    "hiit": {"navn": "HIIT", "kort": "Korte, harde drag med pause",
             "beskrivelse": "Jobb hardt i et fast antall sekunder, hvil, og gå videre til neste øvelse. Gjenta rundene.",
             "standard": {"arbeid": 40, "hvile": 20, "runder": 3, "rundehvile": 60}},
    "tabata": {"navn": "Tabata", "kort": "20 s fullt, 10 s pause × 8",
               "beskrivelse": "Klassisk Tabata: 20 sekunder så hardt du klarer, 10 sekunder pause, åtte ganger – fire minutter totalt per blokk.",
               "standard": {"arbeid": 20, "hvile": 10, "runder": 4, "rundehvile": 60}},
    "sirkel": {"navn": "Sirkel", "kort": "Lengre drag, rolig tempo",
               "beskrivelse": "Sirkeltrening med litt lengre drag og kontrollert tempo – fin for sete, kjerne og helkropp.",
               "standard": {"arbeid": 45, "hvile": 15, "runder": 3, "rundehvile": 60}},
    "emom": {"navn": "EMOM", "kort": "Ny øvelse hvert minutt",
             "beskrivelse": "Every minute on the minute: start en ny øvelse hvert minutt, gjør repetisjonene og hvil resten av minuttet.",
             "standard": {"minutter": 12}},
    "amrap": {"navn": "AMRAP", "kort": "Flest mulig runder på tid",
              "beskrivelse": "As many rounds as possible: gjør øvelsene i rekkefølge med angitte repetisjoner, og ta så mange runder du rekker før tiden er ute.",
              "standard": {"minutter": 12}},
}
TIDSSTYRT = {"hiit", "tabata", "sirkel"}

# Ferdige økter. Øvelser som krever utstyr du ikke har, byttes mot en med samme bevegelsesmønster.
MALER = [
    {"id": "tabata-svette", "navn": "Tabata-svette", "format": "tabata", "fokus": "kondisjon",
     "beskrivelse": "To øvelser annenhver gang – fire intense minutter.",
     "ovelser": [{"nokkel": "burpees"}, {"nokkel": "fjellklatrer"}]},
    {"id": "hiit-helkropp", "navn": "HIIT helkropp", "format": "hiit", "fokus": "helkropp",
     "beskrivelse": "Seks øvelser, 40/20, tre runder. Ca. 20 minutter.",
     "ovelser": [{"nokkel": "hoppknebøy"}, {"nokkel": "armhevinger"}, {"nokkel": "fjellklatrer"},
                 {"nokkel": "utfall-kroppsvekt"}, {"nokkel": "sprellemann"}, {"nokkel": "planke"}]},
    {"id": "sete-bein", "navn": "Sete og bein", "format": "sirkel", "fokus": "sete",
     "beskrivelse": "Setefokusert sirkel uten hopp – 45/15, tre runder.",
     "ovelser": [{"nokkel": "setehev"}, {"nokkel": "sumoknebøy"}, {"nokkel": "eselspark"},
                 {"nokkel": "sidegange-strikk"}, {"nokkel": "utfall-kroppsvekt"}, {"nokkel": "setehev-ettbeins"}]},
    {"id": "kjerne-10", "navn": "Kjerne 10", "format": "sirkel", "fokus": "kjerne",
     "beskrivelse": "Seks kjerneøvelser, 40/20, to runder. Ca. 13 minutter.",
     "ovelser": [{"nokkel": "dead-bug"}, {"nokkel": "sykkelcrunch"}, {"nokkel": "planke-skulderklapp"},
                 {"nokkel": "russisk-vri"}, {"nokkel": "sideplanke"}, {"nokkel": "saksespark"}],
     "oppsett": {"arbeid": 40, "hvile": 20, "runder": 2, "rundehvile": 45}},
    {"id": "amrap-12", "navn": "AMRAP 12", "format": "amrap", "fokus": "helkropp",
     "beskrivelse": "Fire kroppsvektøvelser – hvor mange runder rekker du på 12 minutter?",
     "ovelser": [{"nokkel": "knebøy-kroppsvekt", "reps": 10}, {"nokkel": "armhevinger", "reps": 8},
                 {"nokkel": "fjellklatrer", "reps": 20}, {"nokkel": "burpees", "reps": 6}]},
    {"id": "kb-amrap", "navn": "Kettlebell-AMRAP 15", "format": "amrap", "fokus": "helkropp",
     "beskrivelse": "Sving, knebøy og press – 15 minutter.",
     "ovelser": [{"nokkel": "kettlebell-sving", "reps": 15}, {"nokkel": "goblet-knebøy-kb", "reps": 10},
                 {"nokkel": "armhevinger", "reps": 8}],
     "oppsett": {"minutter": 15}},
    {"id": "emom-12", "navn": "EMOM 12", "format": "emom", "fokus": "helkropp",
     "beskrivelse": "Tre øvelser på rundgang, én per minutt.",
     "ovelser": [{"nokkel": "hoppknebøy", "reps": 12}, {"nokkel": "armhevinger", "reps": 10}, {"nokkel": "sykkelcrunch", "reps": 20}]},
    {"id": "emom-sete", "navn": "EMOM sete", "format": "emom", "fokus": "sete",
     "beskrivelse": "Setehev og sumoknebøy annenhvert minutt i 10 minutter.",
     "ovelser": [{"nokkel": "setehev", "reps": 15}, {"nokkel": "sumoknebøy", "reps": 15}],
     "oppsett": {"minutter": 10}},
    {"id": "manual-sirkel", "navn": "Manualsirkel", "format": "sirkel", "fokus": "helkropp",
     "beskrivelse": "Styrke og puls med manualer – 40/20, tre runder.",
     "ovelser": [{"nokkel": "thruster-manualer"}, {"nokkel": "ettarms-roing"}, {"nokkel": "utfall-manualer"},
                 {"nokkel": "skulderpress-manualer"}, {"nokkel": "fjellklatrer"}],
     "oppsett": {"arbeid": 40, "hvile": 20, "runder": 3, "rundehvile": 60}},
    {"id": "rolig-start", "navn": "Rolig start", "format": "sirkel", "fokus": "helkropp",
     "beskrivelse": "Skånsom sirkel uten hopp – fin første gang eller på en sliten dag.",
     "ovelser": [{"nokkel": "jogg-pa-stedet"}, {"nokkel": "knebøy-kroppsvekt"}, {"nokkel": "setehev"},
                 {"nokkel": "bird-dog"}, {"nokkel": "dead-bug"}],
     "oppsett": {"arbeid": 40, "hvile": 20, "runder": 2, "rundehvile": 60}},
]

FOKUS = {
    "helkropp": {"navn": "Helkropp", "monstre": ["kondisjon", "kne", "press_hor", "utfall", "kjerne", "kondisjon", "sete", "trekk_hor"]},
    "kondisjon": {"navn": "Puls", "monstre": ["kondisjon", "kondisjon", "kondisjon", "kjerne", "kondisjon", "kne"]},
    "sete": {"navn": "Sete og bein", "monstre": ["sete", "kne", "sete", "utfall", "sete", "hofte"]},
    "kjerne": {"navn": "Kjerne", "monstre": ["kjerne", "kjerne", "kjerne", "kjerne", "kjerne", "kjerne"]},
    "overkropp": {"navn": "Overkropp", "monstre": ["press_hor", "trekk_hor", "press_vert", "kjerne", "triceps", "trekk_vert"]},
}
STANDARD_REPS = {"kondisjon": 20, "kjerne": 15, "sete": 15, "kne": 12, "utfall": 10, "hofte": 12}


def _utstyr(sb: "Styrkeboka", pid: int, upid: int | None = None) -> set[str] | None:
    if upid is None:
        upid = sb.profil(pid).get("utstyrsprofil_id")
    return sb.utstyr_for(upid)


def _egnet(o: dict) -> bool:
    """Øvelser som passer i intervaller: kroppsvekt, manualer, kettlebell, strikk – ikke tunge stangløft eller apparater."""
    return o["type"] in ("kroppsvekt", "manualer", "kettlebell", "strikk") and not o.get("arkivert")


def _bytt(sb: "Styrkeboka", nokkel: str, utstyr: set[str] | None, brukt: set[str]) -> str | None:
    o = sb.ovelse(nokkel)
    if o.get("ukjent"):
        return None
    if tilgjengelig(o, utstyr):
        return nokkel
    alt = [x for x in sb.ovelser() if x["monster"] == o["monster"] and _egnet(x) and tilgjengelig(x, utstyr) and x["nokkel"] not in brukt]
    alt.sort(key=lambda x: (x["type"] != "kroppsvekt", x["niva"]))
    return alt[0]["nokkel"] if alt else None


def _ovelse_ut(sb: "Styrkeboka", nokkel: str, reps: int | None = None) -> dict:
    o = sb.ovelse(nokkel)
    return {"nokkel": nokkel, "navn": o["navn"], "monster": o["monster"], "type": o["type"],
            "reps": reps, "tips": o.get("tips", [])[:3]}


def maler(sb: "Styrkeboka", pid: int, upid: int | None = None) -> list[dict]:
    utstyr = _utstyr(sb, pid, upid)
    ut = []
    for m in MALER:
        brukt: set[str] = set()
        ovl = []
        for x in m["ovelser"]:
            k = _bytt(sb, x["nokkel"], utstyr, brukt)
            if k:
                brukt.add(k)
                ovl.append(_ovelse_ut(sb, k, x.get("reps")))
        if len(ovl) < max(2, len(m["ovelser"]) - 1):
            continue
        oppsett = {**FORMATER[m["format"]]["standard"], **(m.get("oppsett") or {}), "format": m["format"], "ovelser": ovl}
        if m["format"] == "tabata":
            oppsett["runder"] = max(1, round(8 / len(ovl)))
        ut.append({"id": m["id"], "navn": m["navn"], "format": m["format"], "fokus": m["fokus"],
                   "beskrivelse": m["beskrivelse"], "oppsett": oppsett, "sekunder": total_sekunder(oppsett)})
    return ut


def foreslaa(sb: "Styrkeboka", pid: int, fmt: str, fokus: str = "helkropp", antall: int | None = None,
             upid: int | None = None, seed: int | None = None) -> dict:
    """Trekker øvelser til en ny økt ut fra fokus og utstyret der du trener."""
    if fmt not in FORMATER:
        from logikk import Feil
        raise Feil("Ukjent format")
    rnd = random.Random(seed)
    utstyr = _utstyr(sb, pid, upid)
    monstre = FOKUS.get(fokus, FOKUS["helkropp"])["monstre"]
    antall = antall or {"tabata": 2, "emom": 3, "amrap": 4}.get(fmt, 6)
    kandidater = [o for o in sb.ovelser() if _egnet(o) and tilgjengelig(o, utstyr)]
    valgt: list[dict] = []
    for i in range(antall):
        m = monstre[i % len(monstre)]
        pool = [o for o in kandidater if o["monster"] == m and o["nokkel"] not in {v["nokkel"] for v in valgt}]
        if not pool:
            pool = [o for o in kandidater if o["monster"] in monstre and o["nokkel"] not in {v["nokkel"] for v in valgt}]
        if not pool:
            break
        # kroppsvekt først – minst rigging mellom dragene
        o = rnd.choices(pool, weights=[3 if x["type"] == "kroppsvekt" else 1 for x in pool])[0]
        reps = STANDARD_REPS.get(o["monster"], 10) if fmt in ("emom", "amrap") else None
        valgt.append(_ovelse_ut(sb, o["nokkel"], reps))
    oppsett = {**FORMATER[fmt]["standard"], "format": fmt, "ovelser": valgt}
    if fmt == "tabata":
        oppsett["runder"] = max(1, round(8 / max(1, len(valgt))))
    return {"oppsett": oppsett, "sekunder": total_sekunder(oppsett)}


def total_sekunder(o: dict) -> int:
    n = len(o.get("ovelser") or [])
    if o.get("format") in TIDSSTYRT:
        runder = int(o.get("runder") or 1)
        return int(runder * n * int(o.get("arbeid") or 0) + runder * (n - 1) * int(o.get("hvile") or 0)
                   + (runder - 1) * int(o.get("rundehvile") or 0))
    return int(o.get("minutter") or 0) * 60


def valider(sb: "Styrkeboka", o: dict) -> dict:
    from logikk import Feil
    fmt = o.get("format")
    if fmt not in FORMATER:
        raise Feil("Ukjent format")

    def tall(k, lo, hi, std):
        try:
            return max(lo, min(hi, int(float(o.get(k, std)))))
        except (TypeError, ValueError):
            return std
    ovl = []
    for x in (o.get("ovelser") or [])[:12]:
        ov = sb.ovelse(str(x.get("nokkel")))
        if ov.get("ukjent"):
            continue
        reps = x.get("reps")
        try:
            reps = max(1, min(200, int(reps))) if reps not in (None, "") else None
        except (TypeError, ValueError):
            reps = None
        ovl.append({"nokkel": ov["nokkel"], "navn": ov["navn"], "monster": ov["monster"], "type": ov["type"],
                    "reps": reps, "tips": ov.get("tips", [])[:3]})
    if not ovl:
        raise Feil("Legg til minst én øvelse")
    ut = {"format": fmt, "ovelser": ovl}
    std = FORMATER[fmt]["standard"]
    if fmt in TIDSSTYRT:
        ut |= {"arbeid": tall("arbeid", 5, 300, std["arbeid"]), "hvile": tall("hvile", 0, 300, std["hvile"]),
               "runder": tall("runder", 1, 20, std["runder"]), "rundehvile": tall("rundehvile", 0, 600, std["rundehvile"])}
    else:
        ut["minutter"] = tall("minutter", 1, 90, std["minutter"])
    return ut


def lagre(sb: "Styrkeboka", pid: int, d: dict) -> dict:
    """Lagrer en gjennomført økt, og registrerer den som aktivitet (teller i aktivitetsminutter og ringene)."""
    oppsett = valider(sb, d.get("oppsett") or {})
    varighet = max(30.0, min(3 * 3600.0, float(d.get("varighet_s") or total_sekunder(oppsett))))
    startet = fra_iso(d.get("startet")) if d.get("startet") else naa() - timedelta(seconds=varighet)
    navn = str(d.get("navn") or FORMATER[oppsett["format"]]["navn"])[:60]
    runder = d.get("runder")
    try:
        runder = round(float(runder), 2) if runder is not None else None
    except (TypeError, ValueError):
        runder = None
    opplevd = d.get("opplevd")
    opplevd = int(opplevd) if str(opplevd or "").isdigit() and 1 <= int(opplevd) <= 5 else None
    # arbeidstid teller som høy intensitet, pauser som moderat
    if oppsett["format"] in TIDSSTYRT:
        andel = oppsett["arbeid"] / max(1, oppsett["arbeid"] + oppsett["hvile"])
    else:
        andel = 0.7
    hoy = round(varighet / 60 * andel)
    mod = round(varighet / 60 - hoy)
    aid = sb.db.sett_inn("aktiviteter", {
        "profil_id": pid, "type": "hiit", "navn": navn, "start": til_iso(startet), "varighet_s": varighet,
        "moderate_min": mod, "hoy_min": hoy, "kilde": "app"})
    iid = sb.db.sett_inn("intervaller", {
        "profil_id": pid, "startet": til_iso(startet), "varighet_s": varighet, "format": oppsett["format"], "navn": navn,
        "oppsett": oppsett, "runder": runder, "fullfort": 1 if d.get("fullfort", True) else 0, "opplevd": opplevd,
        "notat": str(d.get("notat") or "")[:300], "aktivitet_id": aid})
    return hent(sb, iid)


def hent(sb: "Styrkeboka", iid: int) -> dict:
    r = sb.db.en("SELECT * FROM intervaller WHERE id = ?", (iid,))
    if not r:
        from logikk import Feil
        raise Feil("Finnes ikke", 404)
    return r


def historikk(sb: "Styrkeboka", pid: int, antall: int = 20) -> list[dict]:
    return sb.db.alle("SELECT * FROM intervaller WHERE profil_id = ? ORDER BY startet DESC LIMIT ?", (pid, antall))


def beste(sb: "Styrkeboka", pid: int, navn: str, fmt: str) -> dict | None:
    """Beste tidligere AMRAP-resultat med samme navn – å slå det er hele poenget."""
    if fmt != "amrap":
        return None
    return sb.db.en("SELECT runder, startet FROM intervaller WHERE profil_id = ? AND navn = ? AND format = 'amrap' "
                    "AND runder IS NOT NULL ORDER BY runder DESC LIMIT 1", (pid, navn))


def slett(sb: "Styrkeboka", iid: int) -> None:
    r = hent(sb, iid)
    if r.get("aktivitet_id"):
        sb.db.kjor("DELETE FROM aktiviteter WHERE id = ? AND kilde = 'app'", (r["aktivitet_id"],))
    sb.db.slett("intervaller", iid)


def oppsett_tekst(o: dict) -> str:
    f = FORMATER[o["format"]]["navn"]
    if o["format"] in TIDSSTYRT:
        hode = f"{f}: {o['arbeid']} s arbeid / {o['hvile']} s pause, {o['runder']} runder, {o['rundehvile']} s mellom rundene"
    else:
        hode = f"{f}: {o['minutter']} minutter"
    linjer = [f"- {x['nokkel']} ({x['navn']})" + (f" × {x['reps']}" if x.get("reps") else "") for x in o["ovelser"]]
    return hode + "\n" + "\n".join(linjer)
