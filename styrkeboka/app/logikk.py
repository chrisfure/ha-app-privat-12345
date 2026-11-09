"""Styrkeboka – forretningslogikk: profiler, program, økter, historikk og nøkkeltall."""
from __future__ import annotations

import csv
import io
import logging
import re
from datetime import datetime, timedelta
from typing import Callable
from zoneinfo import ZoneInfo

import program as P
from db import Database, fra_iso, naa, til_iso
from instruksjoner import STANDARD_PUST, instruksjon_for
from ovelser import BIBLIOTEK, MONSTER, MUSKLER, UTSTYR, sekunder, tilgjengelig, vektbasert

log = logging.getLogger("styrkeboka")

FARGER = ["lilla", "oransje", "blaa", "gronn", "rosa", "gul"]
TYPER = {"stang": "Vektstang", "manualer": "Manualer", "maskin": "Apparat", "kabel": "Kabel",
         "kettlebell": "Kettlebell", "kroppsvekt": "Kroppsvekt", "strikk": "Strikk"}
STANDARD_INNSTILLINGER = {
    "ai_entitet": "",          # tom = velg automatisk
    "ai_paa": True,
    "ai_auto_oppsummering": True,
    "ai_auto_tips": False,
    "hviletimer_lyd": True,
}


_BIBLIOTEK_MED_INSTRUKSJON = [{**o, "instruksjon": instruksjon_for(o["nokkel"])} for o in BIBLIOTEK]


class Feil(Exception):
    """Feil som vises for brukeren."""


def slug(tekst: str) -> str:
    t = tekst.lower().translate(str.maketrans({"æ": "ae", "ø": "o", "å": "a", "é": "e", "ü": "u", "ö": "o", "ä": "a"}))
    return re.sub(r"[^a-z0-9]+", "_", t).strip("_") or "profil"


def _int(v, std=None, lo=None, hi=None):
    if v in (None, ""):
        return std
    x = int(round(float(str(v).replace(",", "."))))
    if lo is not None:
        x = max(lo, x)
    if hi is not None:
        x = min(hi, x)
    return x


def _float(v):
    if v in (None, ""):
        return None
    x = float(str(v).replace(",", "."))
    if x < 0 or x > 1000:
        raise Feil("Ugyldig vekt")
    return round(x, 2)


class Styrkeboka:
    def __init__(self, db: Database, tz: str = "Europe/Oslo"):
        self.db = db
        self.tz = ZoneInfo(tz)
        self._lyttere: list[Callable[[str, dict | None], None]] = []
        if "programovelser.fast" in self.db.nye_kolonner:
            # eksisterende programmer: hovedøvelsene står fast, blokken starter da programmet ble laget
            for r in self.db.alle("SELECT id, ovelse FROM programovelser"):
                if self.ovelse(r["ovelse"])["monster"] in P.HOVED:
                    self.db.kjor("UPDATE programovelser SET fast = 1 WHERE id = ?", (r["id"],), commit=False)
            for r in self.db.alle("SELECT id, opprettet FROM programmer WHERE blokk_start IS NULL"):
                self.db.kjor("UPDATE programmer SET blokk_start = ? WHERE id = ?",
                             (self._mandag(fra_iso(r["opprettet"]) or naa()), r["id"]), commit=False)
            self.db.commit()
        if not self.db.verdi("SELECT COUNT(*) FROM utstyrsprofiler"):
            self.db.sett_inn("utstyrsprofiler", {"navn": "Treningssenter", "utstyr": list(UTSTYR), "rekkefolge": 0})
            self.db.sett_inn("utstyrsprofiler", {"navn": "Hjemme", "utstyr": ["manualer", "strikk"], "rekkefolge": 1})

    # ------------------------------------------------------------ generelt
    def sett_tidssone(self, tz: str) -> None:
        try:
            self.tz = ZoneInfo(tz)
        except Exception:  # noqa: BLE001
            log.warning("Ukjent tidssone %s", tz)

    def ved_endring(self, fn: Callable[[str, dict | None], None]) -> None:
        self._lyttere.append(fn)

    def _varsle(self, hva: str, data: dict | None = None) -> None:
        for fn in self._lyttere:
            try:
                fn(hva, data)
            except Exception as e:  # noqa: BLE001
                log.warning("Lytter feilet: %s", e)

    @property
    def inn(self) -> dict:
        return {**STANDARD_INNSTILLINGER, **self.db.innstillinger()}

    def lagre_innstillinger(self, d: dict) -> dict:
        for k in STANDARD_INNSTILLINGER:
            if k in d:
                v = d[k]
                if isinstance(STANDARD_INNSTILLINGER[k], bool):
                    v = bool(v)
                elif k == "ai_entitet":
                    v = str(v or "").strip()
                    if v and not re.fullmatch(r"(ai_task|conversation)\.[a-z0-9_]+", v):
                        raise Feil("Ugyldig AI-entitet")
                self.db.lagre_innstilling(k, v)
        return self.inn

    def lokal(self, iso: str | datetime) -> datetime:
        d = fra_iso(iso) if isinstance(iso, str) else iso
        return d.astimezone(self.tz)

    # ------------------------------------------------------------ øvelser
    def ovelser(self, med_arkiv: bool = False) -> list[dict]:
        egne = []
        for r in self.db.alle("SELECT * FROM egne_ovelser"):
            if r["arkivert"] and not med_arkiv:
                continue
            egne.append({
                "nokkel": f"egen-{r['id']}", "navn": r["navn"], "monster": r["monster"], "type": r["type"],
                "utstyr": r["utstyr"] or [], "muskler": r["muskler"] or [], "niva": 1, "skansom": True,
                "sammensatt": r["monster"] in P.STORE, "tips": [t for t in (r["tips"] or "").split("\n") if t.strip()],
                "egen": True, "id": r["id"], "arkivert": bool(r["arkivert"]),
                "instruksjon": {"start": "", "steg": [t.strip() for t in (r.get("instruksjon") or "").split("\n") if t.strip()],
                                "feil": [], "pust": STANDARD_PUST} if (r.get("instruksjon") or "").strip() else None,
            })
        return [*_BIBLIOTEK_MED_INSTRUKSJON, *egne]

    def ovelse(self, nokkel: str) -> dict:
        for o in _BIBLIOTEK_MED_INSTRUKSJON:
            if o["nokkel"] == nokkel:
                return o
        if nokkel.startswith("egen-"):
            for o in self.ovelser(med_arkiv=True):
                if o["nokkel"] == nokkel:
                    return o
        return {"nokkel": nokkel, "navn": nokkel, "monster": "kjerne", "type": "kroppsvekt", "utstyr": [], "muskler": [],
                "tips": [], "ukjent": True}

    def finnes(self, nokkel: str) -> bool:
        return not self.ovelse(nokkel).get("ukjent")

    def lagre_egen_ovelse(self, d: dict, oid: int | None = None) -> dict:
        navn = str(d.get("navn") or "").strip()
        if not navn:
            raise Feil("Øvelsen må ha et navn")
        if d.get("monster") not in MONSTER:
            raise Feil("Velg bevegelsesmønster")
        if d.get("type") not in TYPER:
            raise Feil("Velg type")
        rad = {"navn": navn[:80], "monster": d["monster"], "type": d["type"],
               "utstyr": [u for u in d.get("utstyr") or [] if u in UTSTYR],
               "muskler": [m for m in d.get("muskler") or [] if m in MUSKLER],
               "tips": str(d.get("tips") or "")[:600], "instruksjon": str(d.get("instruksjon") or "")[:2000],
               "arkivert": 1 if d.get("arkivert") else 0}
        if oid is None:
            oid = self.db.sett_inn("egne_ovelser", rad)
        else:
            self.db.oppdater("egne_ovelser", oid, rad)
        return self.ovelse(f"egen-{oid}")

    def alternativer(self, nokkel: str, utstyr: set[str] | None) -> list[dict]:
        o = self.ovelse(nokkel)
        alle = [x for x in self.ovelser() if x["nokkel"] != nokkel]
        samme = [x for x in alle if x["monster"] == o["monster"]]
        samme.sort(key=lambda x: (not tilgjengelig(x, utstyr), x.get("niva", 1), x["navn"]))
        return [{**x, "tilgjengelig": tilgjengelig(x, utstyr)} for x in samme]

    # ------------------------------------------------------------ utstyr
    def utstyrsprofiler(self) -> list[dict]:
        return self.db.alle("SELECT * FROM utstyrsprofiler ORDER BY rekkefolge, id")

    def utstyr_for(self, upid: int | None) -> set[str] | None:
        if not upid:
            return None
        r = self.db.en("SELECT utstyr FROM utstyrsprofiler WHERE id = ?", (upid,))
        return set(r["utstyr"]) if r else None

    def lagre_utstyrsprofil(self, d: dict, uid: int | None = None) -> dict:
        navn = str(d.get("navn") or "").strip()
        if not navn:
            raise Feil("Gi stedet et navn")
        rad = {"navn": navn[:40], "utstyr": [u for u in d.get("utstyr") or [] if u in UTSTYR]}
        if uid is None:
            rad["rekkefolge"] = len(self.utstyrsprofiler())
            uid = self.db.sett_inn("utstyrsprofiler", rad)
        else:
            self.db.oppdater("utstyrsprofiler", uid, rad)
        return self.db.en("SELECT * FROM utstyrsprofiler WHERE id = ?", (uid,))

    def slett_utstyrsprofil(self, uid: int) -> None:
        if len(self.utstyrsprofiler()) <= 1:
            raise Feil("Du må ha minst ett treningssted")
        self.db.kjor("UPDATE profiler SET utstyrsprofil_id = NULL WHERE utstyrsprofil_id = ?", (uid,))
        self.db.slett("utstyrsprofiler", uid)

    # ------------------------------------------------------------ profiler
    def profiler(self) -> list[dict]:
        return self.db.alle("SELECT * FROM profiler WHERE arkivert = 0 ORDER BY id")

    def profil(self, pid: int) -> dict:
        p = self.db.en("SELECT * FROM profiler WHERE id = ?", (pid,))
        if not p:
            raise Feil("Fant ikke profilen")
        return p

    def lagre_profil(self, d: dict, pid: int | None = None) -> dict:
        rad: dict = {}
        if "navn" in d or pid is None:
            navn = str(d.get("navn") or "").strip()
            if not navn:
                raise Feil("Profilen må ha et navn")
            rad["navn"] = navn[:30]
        if "farge" in d:
            rad["farge"] = d["farge"] if d["farge"] in FARGER else "lilla"
        if "ha_bruker" in d:
            rad["ha_bruker"] = str(d["ha_bruker"] or "").strip()[:80] or None
        if "erfaring" in d:
            rad["erfaring"] = d["erfaring"] if d["erfaring"] in P.ERFARING else "noe"
        if "maal" in d:
            maal = [m for m in d.get("maal") or [] if m in P.MAAL]
            rad["maal"] = maal or ["generell"]
        if "dager_per_uke" in d:
            rad["dager_per_uke"] = _int(d["dager_per_uke"], 3, 1, 6)
        if "okt_minutter" in d:
            rad["okt_minutter"] = _int(d["okt_minutter"], 60, 20, 120)
        if "hensyn" in d:
            rad["hensyn"] = str(d["hensyn"] or "")[:1000]
        if "kroppsvekt" in d:
            kv = _float(d["kroppsvekt"])
            rad["kroppsvekt"] = kv if kv and 25 <= kv <= 300 else None
        if "fodselsaar" in d:
            fa = _int(d["fodselsaar"])
            rad["fodselsaar"] = fa if fa and 1920 <= fa <= naa().year - 10 else None
        if "hoyde_cm" in d:
            h = _float(d["hoyde_cm"])
            rad["hoyde_cm"] = h if h and 100 <= h <= 230 else None
        if "kjonn" in d:
            rad["kjonn"] = d["kjonn"] if d["kjonn"] in ("mann", "kvinne") else None
        if "garmin_eksport" in d:
            g = d["garmin_eksport"] or {}
            rad["garmin_eksport"] = {"okter": bool(g.get("okter")), "loping": bool(g.get("loping")), "styrke": bool(g.get("styrke"))}
        if "koblinger" in d:
            k = d["koblinger"] or {}
            import kropp
            gyldige = {"aktiviteter", *kropp.KOBLBARE_TALL, *kropp.KOBLBARE_TEKST}
            rad["koblinger"] = {n: str(v) for n, v in k.items()
                                if n in gyldige and isinstance(v, str) and re.fullmatch(r"sensor\.[a-z0-9_]+", v)}
            kal = [str(x) for x in (k.get("kalendere") or []) if isinstance(x, str) and re.fullmatch(r"calendar\.[a-z0-9_]+", x)]
            if kal:
                rad["koblinger"]["kalendere"] = kal[:6]
        if "utstyrsprofil_id" in d:
            rad["utstyrsprofil_id"] = _int(d["utstyrsprofil_id"])
        if pid is None:
            rad.setdefault("farge", FARGER[len(self.profiler()) % len(FARGER)])
            rad["opprettet"] = til_iso(naa())
            if not rad.get("utstyrsprofil_id"):
                up = self.utstyrsprofiler()
                rad["utstyrsprofil_id"] = up[0]["id"] if up else None
            pid = self.db.sett_inn("profiler", rad)
        else:
            self.profil(pid)
            self.db.oppdater("profiler", pid, rad)
        if rad.get("kroppsvekt") and d.get("lagre_maaling", True):
            import kropp
            if not kropp.siste(self, pid, "vekt") or kropp.siste(self, pid, "vekt")["verdi"] != rad["kroppsvekt"]:
                kropp.lagre_maaling(self, pid, "vekt", rad["kroppsvekt"])
        self._varsle("profil", None)
        return self.profil(pid)

    def slett_profil(self, pid: int) -> None:
        self.db.kjor("UPDATE profiler SET arkivert = 1, ha_bruker = NULL WHERE id = ?", (pid,))
        self._varsle("profil", None)

    def profil_for_bruker(self, *navn: str | None) -> dict | None:
        kandidater = {n.strip().lower() for n in navn if n}
        for p in self.profiler():
            if p.get("ha_bruker") and p["ha_bruker"].lower() in kandidater:
                return p
        return None

    # ------------------------------------------------------------ program
    def _valider_program(self, data: dict) -> dict:
        dager = data.get("dager") or []
        if not isinstance(dager, list) or not dager:
            raise Feil("Programmet må ha minst én økt")
        if len(dager) > 7:
            raise Feil("Maks 7 økter i et program")
        ut = []
        for i, dag in enumerate(dager):
            ovl = []
            for o in dag.get("ovelser") or []:
                nokkel = str(o.get("ovelse") or "")
                if not self.finnes(nokkel):
                    continue
                rmin = _int(o.get("reps_min"), 8, 1, 120)
                rmaks = max(rmin, _int(o.get("reps_maks"), 12, 1, 120))
                fast = bool(o["fast"]) if o.get("fast") is not None else self.ovelse(nokkel)["monster"] in P.HOVED
                ovl.append({
                    "ovelse": nokkel, "sett": _int(o.get("sett"), 3, 1, 8), "reps_min": rmin, "reps_maks": rmaks,
                    "hvile_s": _int(o.get("hvile_s"), 90, 15, 600), "rir": _int(o.get("rir"), 2, 0, 5),
                    "notat": str(o.get("notat") or "")[:200], "fast": 1 if fast else 0,
                })
            ut.append({"navn": (str(dag.get("navn") or "").strip() or f"Økt {chr(65 + i)}")[:40], "ovelser": ovl[:12]})
        if not any(d["ovelser"] for d in ut):
            raise Feil("Programmet har ingen gyldige øvelser")
        return {
            "navn": (str(data.get("navn") or "").strip() or "Mitt program")[:60],
            "beskrivelse": str(data.get("beskrivelse") or "")[:400],
            "begrunnelse": str(data.get("begrunnelse") or "")[:2000],
            "dager": ut,
        }

    def program(self, prid: int) -> dict:
        p = self.db.en("SELECT * FROM programmer WHERE id = ?", (prid,))
        if not p:
            raise Feil("Fant ikke programmet")
        p["dager"] = []
        for d in self.db.alle("SELECT * FROM programdager WHERE program_id = ? ORDER BY rekkefolge", (prid,)):
            d["ovelser"] = []
            for o in self.db.alle("SELECT * FROM programovelser WHERE dag_id = ? ORDER BY rekkefolge", (d["id"],)):
                ov = self.ovelse(o["ovelse"])
                o["navn"] = ov["navn"]
                o["monster"] = ov["monster"]
                o["type"] = ov["type"]
                d["ovelser"].append(o)
            d["minutter"] = P.beregn_tid(d["ovelser"])
            p["dager"].append(d)
        p["blokk"] = self.blokk_status(p)
        return p

    def program_data(self, prid: int) -> dict:
        p = self.program(prid)
        return {"navn": p["navn"], "beskrivelse": p["beskrivelse"], "begrunnelse": p["begrunnelse"],
                "dager": [{"navn": d["navn"], "ovelser": [
                    {k: o[k] for k in ("ovelse", "sett", "reps_min", "reps_maks", "hvile_s", "rir", "notat", "fast")}
                    for o in d["ovelser"]]} for d in p["dager"]]}

    def aktivt_program(self, pid: int) -> dict | None:
        r = self.db.en("SELECT id FROM programmer WHERE profil_id = ? AND aktiv = 1 AND arkivert = 0", (pid,))
        return self.program(r["id"]) if r else None

    def programmer(self, pid: int) -> list[dict]:
        return self.db.alle(
            "SELECT p.*, (SELECT COUNT(*) FROM okter o WHERE o.program_id = p.id AND o.status = 'fullfort') AS okter, "
            "(SELECT COUNT(*) FROM programversjoner v WHERE v.program_id = p.id) AS versjoner "
            "FROM programmer p WHERE profil_id = ? AND arkivert = 0 ORDER BY aktiv DESC, endret DESC", (pid,))

    def foreslaa_program(self, pid: int, upid: int | None = None) -> dict:
        p = self.profil(pid)
        data = P.lag_program(p, self.ovelser(), self.utstyr_for(upid or p.get("utstyrsprofil_id")))
        return self.berik_forhandsvisning(data)

    def berik_forhandsvisning(self, data: dict) -> dict:
        """Legger på navn og tidsanslag så et forslag kan vises før det lagres."""
        d = {**data, "dager": []}
        for dag in data["dager"]:
            ovl = [{**o, "navn": self.ovelse(o["ovelse"])["navn"], "monster": self.ovelse(o["ovelse"])["monster"]}
                   for o in dag["ovelser"]]
            d["dager"].append({**dag, "ovelser": ovl, "minutter": P.beregn_tid(ovl)})
        return d

    def lagre_program(self, pid: int, data: dict, kilde: str = "egen", beskrivelse: str = "",
                      prid: int | None = None, aktiver: bool = True) -> dict:
        self.profil(pid)
        v = self._valider_program(data)
        t = til_iso(naa())
        with self.db.lås:
            if prid is None:
                erfaring = self.profil(pid).get("erfaring")
                prid = self.db.sett_inn("programmer", {
                    "profil_id": pid, "navn": v["navn"], "beskrivelse": v["beskrivelse"], "begrunnelse": v["begrunnelse"],
                    "kilde": kilde, "aktiv": 0, "opprettet": t, "endret": t, "blokk_nr": 1, "blokk_start": self._mandag(naa()),
                    "blokk_uker": P.BLOKK_UKER, "lett_uke": 0 if erfaring == "nybegynner" else 1}, commit=False)
            else:
                gammel = self.db.en("SELECT * FROM programmer WHERE id = ? AND profil_id = ?", (prid, pid))
                if not gammel:
                    raise Feil("Fant ikke programmet")
                self.db.oppdater("programmer", prid, {"navn": v["navn"], "beskrivelse": v["beskrivelse"],
                                                      "begrunnelse": v["begrunnelse"], "endret": t}, commit=False)
                self.db.kjor("DELETE FROM programdager WHERE program_id = ?", (prid,), commit=False)
            for i, dag in enumerate(v["dager"]):
                did = self.db.sett_inn("programdager", {"program_id": prid, "rekkefolge": i, "navn": dag["navn"]}, commit=False)
                for j, o in enumerate(dag["ovelser"]):
                    self.db.sett_inn("programovelser", {"dag_id": did, "rekkefolge": j, **o}, commit=False)
            self.db.sett_inn("programversjoner", {"program_id": prid, "tid": t, "kilde": kilde,
                                                  "beskrivelse": beskrivelse or ("Opprettet" if kilde != "egen" else "Endret"),
                                                  "data": v}, commit=False)
            self.db.commit()
        if aktiver:
            self.aktiver_program(pid, prid)
        self._varsle("program", {"profil_id": pid})
        return self.program(prid)

    def aktiver_program(self, pid: int, prid: int) -> None:
        with self.db.lås:
            self.db.kjor("UPDATE programmer SET aktiv = 0 WHERE profil_id = ?", (pid,), commit=False)
            self.db.kjor("UPDATE programmer SET aktiv = 1 WHERE id = ? AND profil_id = ?", (prid, pid))

    def arkiver_program(self, pid: int, prid: int) -> None:
        self.db.kjor("UPDATE programmer SET arkivert = 1, aktiv = 0 WHERE id = ? AND profil_id = ?", (prid, pid))

    # ------------------------------------------------------------ blokker
    def _mandag(self, d: datetime) -> str:
        lok = self.lokal(d)
        return (lok - timedelta(days=lok.weekday())).date().isoformat()

    def blokk_status(self, p: dict) -> dict:
        from datetime import date as _date
        start = _date.fromisoformat(p.get("blokk_start") or self._mandag(fra_iso(p["opprettet"]) or naa()))
        denne = _date.fromisoformat(self._mandag(naa()))
        uke = (denne - start).days // 7 + 1
        uker = int(p.get("blokk_uker") or P.BLOKK_UKER)
        lett = bool(p.get("lett_uke")) and uke == uker
        return {"nr": p.get("blokk_nr") or 1, "uke": max(1, uke), "uker": uker, "lett_uke": bool(p.get("lett_uke")),
                "lett_naa": lett, "ferdig": uke > uker, "start": start.isoformat()}

    def lagre_blokkinnstillinger(self, prid: int, d: dict) -> dict:
        p = self.program(prid)
        rad = {}
        if "blokk_uker" in d:
            rad["blokk_uker"] = _int(d["blokk_uker"], P.BLOKK_UKER, 3, 12)
        if "lett_uke" in d:
            rad["lett_uke"] = 1 if d["lett_uke"] else 0
        self.db.oppdater("programmer", prid, rad)
        self._varsle("program", {"profil_id": p["profil_id"]})
        return self.program(prid)

    def foreslaa_ny_blokk(self, prid: int) -> dict:
        """Ny blokk uten AI: faste øvelser beholdes, hjelpeøvelsene byttes."""
        p = self.program(prid)
        prof = self.profil(p["profil_id"])
        data = self.program_data(prid)
        ny, endringer = P.roter_hjelpeovelser(data, self.ovelser(), self.utstyr_for(prof.get("utstyrsprofil_id")),
                                               prof.get("erfaring") or "noe", "rehab" in (prof.get("maal") or []))
        return {**self.berik_forhandsvisning(self._valider_program(ny)),
                "endringer": endringer or ["Fant ingen gode alternativer – programmet beholdes som det er."]}

    def sikre_faste(self, prid: int, ny: dict) -> dict:
        """Faste hovedøvelser fra forrige blokk skal være med videre – legg dem inn igjen hvis de mangler."""
        gammel = self.program_data(prid)
        for i, gdag in enumerate(gammel["dager"]):
            if i >= len(ny["dager"]):
                ny["dager"].append({"navn": gdag["navn"], "ovelser": [o for o in gdag["ovelser"] if o.get("fast")]})
                continue
            nokler = {o["ovelse"] for o in ny["dager"][i]["ovelser"]}
            for j, o in enumerate(gdag["ovelser"]):
                if o.get("fast") and o["ovelse"] not in nokler:
                    ny["dager"][i]["ovelser"].insert(min(j, len(ny["dager"][i]["ovelser"])), dict(o))
            for o in ny["dager"][i]["ovelser"]:
                if any(g["ovelse"] == o["ovelse"] and g.get("fast") for g in gdag["ovelser"]):
                    o["fast"] = 1
        return ny

    def start_ny_blokk(self, prid: int, data: dict | None, kilde: str = "egen", beskrivelse: str = "") -> dict:
        p = self.program(prid)
        nr = (p.get("blokk_nr") or 1) + 1
        if data is not None:
            self.lagre_program(p["profil_id"], self.sikre_faste(prid, data), kilde=kilde, prid=prid, aktiver=bool(p["aktiv"]),
                               beskrivelse=beskrivelse or f"Blokk {nr}")
        self.db.oppdater("programmer", prid, {"blokk_nr": nr, "blokk_start": self._mandag(naa())})
        self._varsle("program", {"profil_id": p["profil_id"]})
        return self.program(prid)

    def blokk_oppsummering(self, prid: int) -> str:
        """Kort tekst om fremgangen per øvelse i inneværende blokk (til AI)."""
        p = self.program(prid)
        fra = p["blokk"]["start"]
        linjer = []
        for dag in p["dager"]:
            for o in dag["ovelser"]:
                okter = self.db.alle(
                    "SELECT DISTINCT ok.id, ok.startet FROM okter ok JOIN sett s ON s.okt_id = ok.id WHERE ok.profil_id = ? "
                    "AND s.ovelse = ? AND ok.status = 'fullfort' AND ok.lett = 0 AND s.oppvarming = 0 AND ok.startet >= ? ORDER BY ok.startet",
                    (p["profil_id"], o["ovelse"], fra))
                if not okter:
                    linjer.append(f"- {o['navn']}: ikke trent i blokka")
                    continue

                def beste(oid):
                    s = self.db.alle("SELECT vekt, reps FROM sett WHERE okt_id = ? AND ovelse = ? AND oppvarming = 0", (oid, o["ovelse"]))
                    t = max(s, key=lambda x: ((x["vekt"] or 0), x["reps"] or 0))
                    return f"{t['vekt']:g}kg×{t['reps']}" if t["vekt"] else f"{t['reps']} reps"
                linjer.append(f"- {o['navn']}{' (fast)' if o.get('fast') else ''}: {len(okter)} økter, fra {beste(okter[0]['id'])} til {beste(okter[-1]['id'])}")
        return "\n".join(linjer)

    def versjoner(self, prid: int) -> list[dict]:
        return self.db.alle("SELECT id, tid, kilde, beskrivelse, data FROM programversjoner WHERE program_id = ? ORDER BY id DESC", (prid,))

    def gjenopprett_versjon(self, pid: int, vid: int) -> dict:
        v = self.db.en("SELECT * FROM programversjoner WHERE id = ?", (vid,))
        if not v:
            raise Feil("Fant ikke versjonen")
        return self.lagre_program(pid, v["data"], kilde="egen", prid=v["program_id"],
                                  beskrivelse=f"Gjenopprettet versjon fra {self.lokal(v['tid']):%d.%m.%Y %H:%M}")

    def neste_dag(self, pid: int, prog: dict | None = None) -> dict | None:
        prog = prog or self.aktivt_program(pid)
        if not prog or not prog["dager"]:
            return None
        sist = self.db.en("SELECT dag_id FROM okter WHERE profil_id = ? AND program_id = ? AND status = 'fullfort' "
                          "AND dag_id IS NOT NULL ORDER BY startet DESC LIMIT 1", (pid, prog["id"]))
        ider = [d["id"] for d in prog["dager"]]
        if sist and sist["dag_id"] in ider:
            return prog["dager"][(ider.index(sist["dag_id"]) + 1) % len(ider)]
        return prog["dager"][0]

    # ------------------------------------------------------------ historikk per øvelse
    def tidligere_sett(self, pid: int, nokkel: str, for_okt: int | None = None, antall: int = 3) -> list[list[dict]]:
        okter = self.db.alle(
            "SELECT DISTINCT o.id, o.startet FROM okter o JOIN sett s ON s.okt_id = o.id "
            "WHERE o.profil_id = ? AND s.ovelse = ? AND s.oppvarming = 0 AND o.status = 'fullfort' AND o.id != ? "
            "AND COALESCE(o.lett, 0) = 0 ORDER BY o.startet DESC LIMIT ?", (pid, nokkel, for_okt or -1, antall))
        return [self.db.alle("SELECT * FROM sett WHERE okt_id = ? AND ovelse = ? AND oppvarming = 0 ORDER BY settnr",
                             (o["id"], nokkel)) for o in okter]

    # ------------------------------------------------------------ startvekter
    def forslag(self, pid: int, ov: dict, plan: dict, tidl: list[list[dict]]) -> dict:
        """Vektforslag: egen historikk først, så lagret startvekt, så anslag fra andre løft du har logget."""
        f = P.foreslaa(ov, plan, tidl)
        if f["trend"] != "ny" or not vektbasert(ov):
            return f
        lagret = self.db.en("SELECT kg, kilde FROM startvekter WHERE profil_id = ? AND ovelse = ?", (pid, ov["nokkel"]))
        if lagret:
            kilde = {"ai": "fra AI-treneren", "manuell": "som du la inn"}.get(lagret["kilde"], "anslått")
            kg = P.rund_til_utstyr(ov, lagret["kg"])
            return {**f, "kg": kg, "tekst": f"Startvekt {kilde}: {P._kg(kg)}. Juster etter første sett – "
                    f"målet er {plan.get('reps_min')}–{plan.get('reps_maks')} reps med {plan.get('rir', 2)} i reserve."}
        est = self.anslag_fra_historikk(pid, ov, plan)
        if est:
            kg, grunnlag = est
            return {**f, "kg": kg, "tekst": f"Anslått ut fra {grunnlag}: {P._kg(kg)}. Juster etter første sett."}
        return f

    def _referanser_fra_historikk(self, pid: int) -> tuple[dict, list[str]]:
        rader = self.db.alle(
            "SELECT s.ovelse, s.vekt, s.reps FROM sett s JOIN okter o ON o.id = s.okt_id WHERE o.profil_id = ? "
            "AND o.status = 'fullfort' AND COALESCE(o.lett, 0) = 0 AND s.oppvarming = 0 AND s.vekt > 0 AND o.startet >= ?",
            (pid, til_iso(naa() - timedelta(days=120))))
        beste: dict[str, float] = {}
        for r in rader:
            e = P.e1rm(r["vekt"], r["reps"])
            if e and r["ovelse"] in P.FORHOLD:
                beste[r["ovelse"]] = max(beste.get(r["ovelse"], 0), e)
        kjente = [{"ovelse": k, "kg": e, "reps": 1} for k, e in beste.items()]
        return P.referanser(kjente), [self.ovelse(k)["navn"].lower() for k in beste]

    def anslag_fra_historikk(self, pid: int, ov: dict, plan: dict) -> tuple[float, str] | None:
        ref, navn = self._referanser_fra_historikk(pid)
        if ref and navn:
            kg = P.anslaa_vekt(ov, plan, ref)
            if kg:
                return kg, "det du løfter i " + ", ".join(navn[:2])
        p = self.profil(pid)
        ref = P.referanser(p.get("kjente_loft") or [], p.get("kroppsvekt"), p.get("erfaring") or "noe")
        kg = P.anslaa_vekt(ov, plan, ref) if ref else None
        if kg:
            return kg, "løftene du har oppgitt" if p.get("kjente_loft") else "kroppsvekt og erfaring"
        return None

    def beregn_startvekter(self, pid: int, kjente: list[dict] | None = None, kroppsvekt=None) -> dict:
        """Lokalt anslag for alle vektøvelser i aktivt program. Lagrer svarene på profilen."""
        p = self.profil(pid)
        if kjente is not None:
            rene = []
            for k in kjente[:10]:
                kg, reps = _float(k.get("kg")), _int(k.get("reps"), None, 1, 30)
                if self.finnes(str(k.get("ovelse") or "")) and kg and reps:
                    rene.append({"ovelse": k["ovelse"], "kg": kg, "reps": reps})
            self.db.oppdater("profiler", pid, {"kjente_loft": rene})
            if kroppsvekt not in (None, ""):
                self.lagre_profil({"kroppsvekt": kroppsvekt}, pid)
            p = self.profil(pid)
        kjente = p.get("kjente_loft") or []
        ref_hist, hist_navn = self._referanser_fra_historikk(pid)
        ref = P.referanser(kjente, p.get("kroppsvekt"), p.get("erfaring") or "noe")
        prog = self.aktivt_program(pid)
        ut, sett_ = [], set()
        for dag in (prog["dager"] if prog else []):
            for o in dag["ovelser"]:
                ov = self.ovelse(o["ovelse"])
                if o["ovelse"] in sett_ or not vektbasert(ov) or sekunder(ov):
                    continue
                sett_.add(o["ovelse"])
                har_hist = bool(self.tidligere_sett(pid, o["ovelse"], antall=1))
                kg = P.anslaa_vekt(ov, o, ref) if ref else None
                grunnlag = "løftene du oppga" if kjente else "kroppsvekt og erfaring" if ref else ""
                if not kg and ref_hist:
                    kg, grunnlag = P.anslaa_vekt(ov, o, ref_hist), "det du har logget"
                ut.append({"ovelse": o["ovelse"], "navn": ov["navn"], "type": ov["type"], "kg": kg, "grunnlag": grunnlag,
                           "reps_min": o["reps_min"], "reps_maks": o["reps_maks"], "rir": o["rir"], "har_historikk": har_hist,
                           "kan_anslaas": o["ovelse"] in P.FORHOLD})
        return {"forslag": ut, "referanser": {k: round(v, 1) for k, v in ref.items()}, "kjente": kjente,
                "kroppsvekt": p.get("kroppsvekt")}

    def lagre_startvekter(self, pid: int, vekter: dict, kilde: str = "manuell") -> int:
        self.profil(pid)
        t = til_iso(naa())
        n = 0
        with self.db.lås:
            for nokkel, kg in (vekter or {}).items():
                if not self.finnes(str(nokkel)):
                    continue
                v = _float(kg)
                if v:
                    v = P.rund_til_utstyr(self.ovelse(str(nokkel)), v)
                if v is None or v <= 0:
                    self.db.kjor("DELETE FROM startvekter WHERE profil_id = ? AND ovelse = ?", (pid, nokkel), commit=False)
                    continue
                self.db.kjor("INSERT INTO startvekter (profil_id, ovelse, kg, kilde, tid) VALUES (?, ?, ?, ?, ?) "
                             "ON CONFLICT(profil_id, ovelse) DO UPDATE SET kg = excluded.kg, kilde = excluded.kilde, tid = excluded.tid",
                             (pid, nokkel, v, kilde, t), commit=False)
                n += 1
            # oppdater forslag i en pågående økt for øvelser uten logget sett
            aktiv = self.db.en("SELECT id FROM okter WHERE profil_id = ? AND status = 'pagar'", (pid,))
            self.db.commit()
        if aktiv:
            for oo in self.db.alle("SELECT * FROM okt_ovelser WHERE okt_id = ?", (aktiv["id"],)):
                if self.db.verdi("SELECT COUNT(*) FROM sett WHERE okt_ovelse_id = ?", (oo["id"],)):
                    continue
                ov = self.ovelse(oo["ovelse"])
                f = self.forslag(pid, ov, oo, self.tidligere_sett(pid, ov["nokkel"], aktiv["id"]))
                self.db.oppdater("okt_ovelser", oo["id"], {"forslag_kg": f["kg"], "forslag_tekst": f["tekst"]})
        return n

    def startvekter(self, pid: int) -> dict:
        return {r["ovelse"]: r for r in self.db.alle("SELECT * FROM startvekter WHERE profil_id = ?", (pid,))}

    def mangler_startvekt(self, pid: int) -> int:
        """Antall vektøvelser i programmet uten historikk, lagret startvekt eller anslag."""
        prog = self.aktivt_program(pid)
        p = self.profil(pid)
        if not prog or p.get("kjente_loft") or p.get("kroppsvekt"):
            return 0
        lagret = self.startvekter(pid)
        n = 0
        for dag in prog["dager"]:
            for o in dag["ovelser"]:
                ov = self.ovelse(o["ovelse"])
                if vektbasert(ov) and not sekunder(ov) and o["ovelse"] not in lagret and not self.tidligere_sett(pid, o["ovelse"], antall=1):
                    n += 1
        return n

    # ------------------------------------------------------------ økter
    def aktiv_okt(self, pid: int) -> dict | None:
        r = self.db.en("SELECT id FROM okter WHERE profil_id = ? AND status = 'pagar' ORDER BY startet DESC LIMIT 1", (pid,))
        return self.okt(r["id"]) if r else None

    def _okt_rad(self, oid: int) -> dict:
        o = self.db.en("SELECT * FROM okter WHERE id = ?", (oid,))
        if not o:
            raise Feil("Fant ikke økten")
        return o

    def start_okt(self, pid: int, dag_id: int | None = None, upid: int | None = None, av: str | None = None) -> dict:
        p = self.profil(pid)
        if (aktiv := self.aktiv_okt(pid)):
            return aktiv
        upid = upid or p.get("utstyrsprofil_id")
        utstyr = self.utstyr_for(upid)
        prog = self.aktivt_program(pid)
        dag = None
        if dag_id and prog:
            dag = next((d for d in prog["dager"] if d["id"] == dag_id), None)
        lett = bool(dag and prog["blokk"]["lett_naa"])
        with self.db.lås:
            oid = self.db.sett_inn("okter", {
                "profil_id": pid, "program_id": prog["id"] if dag else None, "dag_id": dag["id"] if dag else None,
                "dag_navn": dag["navn"] if dag else "Fri økt", "utstyrsprofil_id": upid, "startet": til_iso(naa()),
                "status": "pagar", "av": av, "lett": 1 if lett else 0,
                "blokk_nr": prog["blokk"]["nr"] if dag else None}, commit=False)
            brukt: set[str] = set()
            for i, po in enumerate(dag["ovelser"] if dag else []):
                ov = self.ovelse(po["ovelse"])
                erstattet = None
                if not tilgjengelig(ov, utstyr):
                    alt = P.velg_ovelse(ov["monster"], self.ovelser(), utstyr, p.get("erfaring") or "noe",
                                        "rehab" in (p.get("maal") or []), brukt | {po["ovelse"]})
                    if alt:
                        erstattet, ov = po["ovelse"], alt
                brukt.add(ov["nokkel"])
                import loping
                plan = loping.juster_plan(self, pid, P.lett_dose(po) if lett else po, ov["monster"], bool(po.get("fast")))
                self._sett_inn_okt_ovelse(oid, i, ov, plan, pid, programovelse_id=po["id"],
                                          erstattet_fra=erstattet, lett=lett)
            self.db.commit()
        okt = self.okt(oid)
        self._varsle("okt_startet", {"profil_id": pid, "okt": okt})
        return okt

    def _sett_inn_okt_ovelse(self, oid: int, rekkefolge: int, ov: dict, plan: dict, pid: int,
                             programovelse_id: int | None = None, erstattet_fra: str | None = None, lett: bool = False) -> int:
        plan = {"sett_plan": _int(plan.get("sett_plan") or plan.get("sett"), 3, 1, 10),
                "reps_min": _int(plan.get("reps_min"), 8, 1, 120), "reps_maks": _int(plan.get("reps_maks"), 12, 1, 120),
                "hvile_s": _int(plan.get("hvile_s"), 90, 15, 600), "rir": _int(plan.get("rir"), 2, 0, 5)}
        plan["reps_maks"] = max(plan["reps_min"], plan["reps_maks"])
        tidl = self.tidligere_sett(pid, ov["nokkel"], oid)
        f = self.forslag(pid, ov, plan, tidl)
        if lett:
            f = P.lett_forslag(f, tidl)
        return self.db.sett_inn("okt_ovelser", {
            "okt_id": oid, "rekkefolge": rekkefolge, "ovelse": ov["nokkel"], "programovelse_id": programovelse_id,
            **plan, "forslag_kg": f["kg"], "forslag_reps": f["reps"], "forslag_tekst": f["tekst"],
            "erstattet_fra": erstattet_fra}, commit=False)

    def okt(self, oid: int) -> dict:
        o = self._okt_rad(oid)
        alle_sett = self.db.alle("SELECT * FROM sett WHERE okt_id = ? ORDER BY tid, id", (oid,))
        o["ovelser"] = []
        varmet: set[str] = set()
        for oo in self.db.alle("SELECT * FROM okt_ovelser WHERE okt_id = ? ORDER BY rekkefolge, id", (oid,)):
            ov = self.ovelse(oo["ovelse"])
            oo["info"] = {k: ov.get(k) for k in ("navn", "monster", "type", "utstyr", "muskler", "tips", "egen", "instruksjon")}
            oo["info"]["monster_navn"] = MONSTER.get(ov["monster"], ov["monster"])
            oo["info"]["vektbasert"] = vektbasert(ov)
            oo["info"]["sekunder"] = sekunder(ov)
            oo["sett"] = sorted([s for s in alle_sett if s["okt_ovelse_id"] == oo["id"]], key=lambda s: (s["oppvarming"] == 0, s["settnr"]))
            if oo["erstattet_fra"]:
                oo["erstattet_navn"] = self.ovelse(oo["erstattet_fra"])["navn"]
            oo["oppvarming"] = []
            region = "under" if ov["monster"] in P.UNDERKROPP else "over" if ov["monster"] in P.OVERKROPP else None
            if region and vektbasert(ov) and ov.get("sammensatt"):
                oo["oppvarming"] = P.oppvarming(oo["forslag_kg"], ov, kort=region in varmet)
                if oo["oppvarming"] or oo["forslag_kg"]:
                    varmet.add(region)
            arbeid = [s for s in oo["sett"] if not s["oppvarming"]]
            oo["ferdig"] = len(arbeid) >= oo["sett_plan"]
            o["ovelser"].append(oo)
        o["generell_oppvarming"] = P.generell_oppvarming([x["info"]["monster"] for x in o["ovelser"]])
        o["klokke"] = self._klokke(oid, alle_sett)
        arbeid = [s for s in alle_sett if not s["oppvarming"]]
        o["nokkeltall"] = {
            "sett": len(arbeid),
            "planlagt": sum(x["sett_plan"] for x in o["ovelser"]),
            "volum": round(sum((s["vekt"] or 0) * (s["reps"] or 0) for s in arbeid)),
            "reps": sum(s["reps"] or 0 for s in arbeid),
            "minutter": self._minutter(o),
        }
        if o["utstyrsprofil_id"]:
            up = self.db.en("SELECT navn FROM utstyrsprofiler WHERE id = ?", (o["utstyrsprofil_id"],))
            o["sted"] = up["navn"] if up else None
        return o

    def garmin_dagplan(self, pid: int, dag: dict, prog: dict) -> list[dict]:
        """Øvelsene i en programdag med dagens vektforslag – grunnlaget for Garmin-økta."""
        import loping
        lett = prog["blokk"]["lett_naa"]
        varmet: set[str] = set()
        ut = []
        for po in dag["ovelser"]:
            ov = self.ovelse(po["ovelse"])
            plan = loping.juster_plan(self, pid, P.lett_dose(po) if lett else po, ov["monster"], bool(po.get("fast")))
            tidl = self.tidligere_sett(pid, ov["nokkel"])
            f = self.forslag(pid, ov, plan, tidl)
            if lett:
                f = P.lett_forslag(f, tidl)
            region = "under" if ov["monster"] in P.UNDERKROPP else "over" if ov["monster"] in P.OVERKROPP else None
            oppv = []
            if region and vektbasert(ov) and ov.get("sammensatt") and f["kg"]:
                oppv = P.oppvarming(f["kg"], ov, kort=region in varmet)
                varmet.add(region)
            ut.append({"ovelse": ov, "sett": int(plan.get("sett_plan") or plan.get("sett") or 3), "reps": f["reps"] or plan.get("reps_min") or 8,
                       "kg": f["kg"] if vektbasert(ov) else None, "hvile_s": plan.get("hvile_s") or 90, "sekunder": sekunder(ov),
                       "oppvarming": oppv, "tekst": f"{plan.get('reps_min')}–{plan.get('reps_maks')} reps, {plan.get('rir', 2)} i reserve"})
        return ut

    def _klokke(self, oid: int, alle_sett: list[dict]) -> dict | None:
        """Pulsdata fra en styrkeøkt registrert på klokka, koblet til denne økta."""
        import kropp
        a = self.db.en("SELECT * FROM aktiviteter WHERE okt_id = ? AND type = 'styrke'", (oid,))
        if not a:
            return None
        p = kropp.puls(self, a["id"])
        serie = (p or {}).get("data") or []
        ut = {k: a.get(k) for k in ("id", "start", "varighet_s", "snittpuls", "makspuls", "kalorier", "belastning", "aerob_effekt", "soner")}
        ut["puls"] = serie
        ut["puls_start"] = (p or {}).get("start")
        ut["puls_hentet"] = p is not None
        if serie:
            ut["analyse"] = kropp.puls_analyse(serie, alle_sett, p["start"])
            t0 = fra_iso(p["start"])
            ut["sett_tider"] = [{"t": round((fra_iso(s["tid"]) - t0).total_seconds()), "ovelse": s["ovelse"], "oppvarming": s["oppvarming"]}
                                for s in alle_sett]
        return ut

    def _minutter(self, o: dict) -> int:
        slutt = fra_iso(o["avsluttet"]) if o.get("avsluttet") else naa()
        return max(0, round((slutt - fra_iso(o["startet"])).total_seconds() / 60))

    def _oo(self, ooid: int) -> dict:
        oo = self.db.en("SELECT * FROM okt_ovelser WHERE id = ?", (ooid,))
        if not oo:
            raise Feil("Fant ikke øvelsen i økten")
        return oo

    def logg_sett(self, oid: int, d: dict) -> dict:
        o = self._okt_rad(oid)
        oo = self._oo(int(d["okt_ovelse_id"]))
        if oo["okt_id"] != oid:
            raise Feil("Øvelsen hører ikke til økten")
        reps = _int(d.get("reps"), None, 0, 1000)
        if reps is None:
            raise Feil("Skriv inn antall reps")
        oppv = 1 if d.get("oppvarming") else 0
        nr = (self.db.verdi("SELECT MAX(settnr) FROM sett WHERE okt_ovelse_id = ? AND oppvarming = ?", (oo["id"], oppv)) or 0) + 1
        sid = self.db.sett_inn("sett", {
            "okt_id": oid, "okt_ovelse_id": oo["id"], "ovelse": oo["ovelse"], "settnr": nr, "vekt": _float(d.get("vekt")),
            "reps": reps, "rir": _int(d.get("rir"), None, 0, 10), "oppvarming": oppv, "tid": til_iso(naa())})
        if o["status"] == "pagar":
            self._varsle("sett", {"profil_id": o["profil_id"]})
        return self.db.en("SELECT * FROM sett WHERE id = ?", (sid,))

    def endre_sett(self, sid: int, d: dict) -> dict:
        s = self.db.en("SELECT * FROM sett WHERE id = ?", (sid,))
        if not s:
            raise Feil("Fant ikke settet")
        rad = {}
        if "vekt" in d:
            rad["vekt"] = _float(d["vekt"])
        if "reps" in d:
            rad["reps"] = _int(d["reps"], 0, 0, 1000)
        if "rir" in d:
            rad["rir"] = _int(d["rir"], None, 0, 10)
        self.db.oppdater("sett", sid, rad)
        return self.db.en("SELECT * FROM sett WHERE id = ?", (sid,))

    def slett_sett(self, sid: int) -> None:
        s = self.db.en("SELECT * FROM sett WHERE id = ?", (sid,))
        if not s:
            return
        self.db.slett("sett", sid)
        # nummerer om
        for i, r in enumerate(self.db.alle("SELECT id FROM sett WHERE okt_ovelse_id = ? AND oppvarming = ? ORDER BY settnr",
                                           (s["okt_ovelse_id"], s["oppvarming"])), 1):
            self.db.kjor("UPDATE sett SET settnr = ? WHERE id = ?", (i, r["id"]), commit=False)
        self.db.commit()

    def legg_til_ovelse(self, oid: int, d: dict) -> dict:
        o = self._okt_rad(oid)
        nokkel = str(d.get("ovelse") or "")
        if not self.finnes(nokkel):
            raise Feil("Ukjent øvelse")
        ov = self.ovelse(nokkel)
        p = self.profil(o["profil_id"])
        regler = P.doseringsregler(p.get("maal") or [], p.get("erfaring") or "noe")["stor" if ov["monster"] in P.STORE else "liten"]
        n = (self.db.verdi("SELECT MAX(rekkefolge) FROM okt_ovelser WHERE okt_id = ?", (oid,)) or 0) + 1
        with self.db.lås:
            self._sett_inn_okt_ovelse(oid, n, ov, {**regler, **{k: d[k] for k in ("sett", "reps_min", "reps_maks", "hvile_s", "rir") if d.get(k)}},
                                      o["profil_id"])
            self.db.commit()
        return self.okt(oid)

    def endre_okt_ovelse(self, ooid: int, d: dict) -> dict:
        oo = self._oo(ooid)
        o = self._okt_rad(oo["okt_id"])
        rad: dict = {}
        if d.get("ovelse") and d["ovelse"] != oo["ovelse"]:
            if not self.finnes(d["ovelse"]):
                raise Feil("Ukjent øvelse")
            ny = self.ovelse(d["ovelse"])
            f = self.forslag(o["profil_id"], ny, oo, self.tidligere_sett(o["profil_id"], ny["nokkel"], o["id"]))
            rad.update(ovelse=ny["nokkel"], forslag_kg=f["kg"], forslag_reps=f["reps"], forslag_tekst=f["tekst"],
                       erstattet_fra=oo["erstattet_fra"] or oo["ovelse"])
            self.db.kjor("UPDATE sett SET ovelse = ? WHERE okt_ovelse_id = ?", (ny["nokkel"], ooid), commit=False)
            if d.get("ogsa_program") and oo["programovelse_id"]:
                self._bytt_i_program(oo["programovelse_id"], oo["ovelse"], ny["nokkel"], o["profil_id"])
        for k, lo, hi in (("sett_plan", 1, 10), ("reps_min", 1, 120), ("reps_maks", 1, 120), ("hvile_s", 15, 600), ("rir", 0, 5)):
            if k in d:
                rad[k] = _int(d[k], None, lo, hi)
        if "notat" in d:
            rad["notat"] = str(d["notat"] or "")[:300]
        if "rekkefolge" in d:
            rad["rekkefolge"] = _int(d["rekkefolge"], 0)
        self.db.oppdater("okt_ovelser", ooid, rad)
        return self.okt(oo["okt_id"])

    def _bytt_i_program(self, poid: int, fra: str, til: str, pid: int) -> None:
        r = self.db.en("SELECT d.program_id FROM programovelser po JOIN programdager d ON d.id = po.dag_id WHERE po.id = ?", (poid,))
        if not r:
            return
        data = self.program_data(r["program_id"])
        for dag in data["dager"]:
            for o in dag["ovelser"]:
                if o["ovelse"] == fra:
                    o["ovelse"] = til
        self.lagre_program(pid, data, kilde="egen", prid=r["program_id"], aktiver=False,
                           beskrivelse=f"Byttet {self.ovelse(fra)['navn']} med {self.ovelse(til)['navn']} under en økt")

    def flytt_okt_ovelse(self, ooid: int, retning: int) -> dict:
        oo = self._oo(ooid)
        rader = self.db.alle("SELECT id FROM okt_ovelser WHERE okt_id = ? ORDER BY rekkefolge, id", (oo["okt_id"],))
        ider = [r["id"] for r in rader]
        i = ider.index(ooid)
        j = max(0, min(len(ider) - 1, i + (1 if retning > 0 else -1)))
        ider[i], ider[j] = ider[j], ider[i]
        for n, rid in enumerate(ider):
            self.db.kjor("UPDATE okt_ovelser SET rekkefolge = ? WHERE id = ?", (n, rid), commit=False)
        self.db.commit()
        return self.okt(oo["okt_id"])

    def slett_okt_ovelse(self, ooid: int) -> dict:
        oo = self._oo(ooid)
        self.db.slett("okt_ovelser", ooid)
        return self.okt(oo["okt_id"])

    def avslutt_okt(self, oid: int, d: dict) -> dict:
        o = self._okt_rad(oid)
        if not self.db.verdi("SELECT COUNT(*) FROM sett WHERE okt_id = ? AND oppvarming = 0", (oid,)):
            raise Feil("Ingen sett er registrert – avbryt økten i stedet")
        rad = {"status": "fullfort", "opplevd": _int(d.get("opplevd"), None, 1, 5), "notat": str(d.get("notat") or "")[:1000]}
        if o["status"] == "pagar":
            rad["avsluttet"] = til_iso(naa())
        self.db.oppdater("okter", oid, rad)
        res = self.okt_oppsummering(oid)
        self._varsle("okt_fullfort", {"profil_id": o["profil_id"], "oppsummering": res})
        return res

    def lettere_okt(self, oid: int) -> dict:
        """Gjør resten av økta lettere (dagsform): halvparten av settene, samme vekt som sist, mer i reserve."""
        o = self._okt_rad(oid)
        for oo in self.db.alle("SELECT * FROM okt_ovelser WHERE okt_id = ?", (oid,)):
            if self.db.verdi("SELECT COUNT(*) FROM sett WHERE okt_ovelse_id = ? AND oppvarming = 0", (oo["id"],)):
                continue
            ny = P.lett_dose(oo)
            ov = self.ovelse(oo["ovelse"])
            tidl = self.tidligere_sett(o["profil_id"], ov["nokkel"], oid)
            f = P.lett_forslag(self.forslag(o["profil_id"], ov, ny, tidl), tidl)
            self.db.oppdater("okt_ovelser", oo["id"], {"sett_plan": ny["sett_plan"], "rir": ny["rir"], "forslag_kg": f["kg"],
                                                       "forslag_tekst": "Lettere i dag: færre sett og samme vekt som sist – stopp med god margin."})
        return self.okt(oid)

    def avbryt_okt(self, oid: int) -> None:
        o = self._okt_rad(oid)
        self.db.slett("okter", oid)
        self._varsle("okt_avbrutt", {"profil_id": o["profil_id"]})

    def endre_okt(self, oid: int, d: dict) -> dict:
        self._okt_rad(oid)
        rad = {}
        if "notat" in d:
            rad["notat"] = str(d["notat"] or "")[:1000]
        if "opplevd" in d:
            rad["opplevd"] = _int(d["opplevd"], None, 1, 5)
        if d.get("startet"):
            start = fra_iso(d["startet"])
            o = self._okt_rad(oid)
            varighet = (fra_iso(o["avsluttet"]) - fra_iso(o["startet"])) if o.get("avsluttet") else timedelta(minutes=60)
            rad["startet"] = til_iso(start)
            rad["avsluttet"] = til_iso(start + varighet)
        self.db.oppdater("okter", oid, rad)
        return self.okt(oid)

    def registrer_tidligere_okt(self, pid: int, d: dict, av: str | None = None) -> dict:
        """Lager en tom, fullført økt på et tidligere tidspunkt som fylles ut etterpå."""
        self.profil(pid)
        start = fra_iso(d.get("startet")) or naa()
        oid = self.db.sett_inn("okter", {
            "profil_id": pid, "dag_navn": str(d.get("navn") or "Økt").strip()[:40], "startet": til_iso(start),
            "avsluttet": til_iso(start + timedelta(minutes=_int(d.get("minutter"), 60, 5, 300))),
            "status": "fullfort", "av": av})
        return self.okt(oid)

    def lagre_ai(self, oid: int, felt: str, verdi) -> None:
        if felt not in ("ai_tips", "ai_oppsummering"):
            raise ValueError(felt)
        self.db.oppdater("okter", oid, {felt: verdi})

    # ------------------------------------------------------------ oppsummering og rekorder
    def _beste_for(self, pid: int, nokkel: str, for_startet: str) -> dict:
        r = self.db.alle(
            "SELECT s.vekt, s.reps FROM sett s JOIN okter o ON o.id = s.okt_id "
            "WHERE o.profil_id = ? AND s.ovelse = ? AND s.oppvarming = 0 AND o.status = 'fullfort' AND o.startet < ?",
            (pid, nokkel, for_startet))
        e = [P.e1rm(x["vekt"], x["reps"]) for x in r]
        return {"e1rm": max([x for x in e if x] or [0]), "vekt": max([x["vekt"] or 0 for x in r] or [0]),
                "reps": max([x["reps"] or 0 for x in r] or [0]), "finnes": bool(r)}

    def okt_oppsummering(self, oid: int) -> dict:
        o = self.okt(oid)
        rekorder = []
        for oo in o["ovelser"]:
            arbeid = [s for s in oo["sett"] if not s["oppvarming"]]
            if not arbeid:
                continue
            tidl = self._beste_for(o["profil_id"], oo["ovelse"], o["startet"])
            if not tidl["finnes"]:
                continue
            navn = oo["info"]["navn"]
            if oo["info"]["vektbasert"]:
                tung = max(s["vekt"] or 0 for s in arbeid)
                e = max([P.e1rm(s["vekt"], s["reps"]) or 0 for s in arbeid])
                if tung > tidl["vekt"]:
                    rekorder.append({"ovelse": navn, "tekst": f"Tyngste vekt: {P._kg(tung)}"})
                elif e > tidl["e1rm"] > 0:
                    rekorder.append({"ovelse": navn, "tekst": f"Ny beste estimerte 1RM: {P._kg(e)}"})
            else:
                r = max(s["reps"] or 0 for s in arbeid)
                if r > tidl["reps"]:
                    rekorder.append({"ovelse": navn, "tekst": f"Flest {'sekunder' if oo['info']['sekunder'] else 'reps'}: {r}"})
        return {"okt": o, "rekorder": rekorder}

    # ------------------------------------------------------------ historikk
    def _uke(self, d: datetime) -> str:
        iso = self.lokal(d).isocalendar()
        return f"{iso[0]}-U{iso[1]:02d}"

    def historikk(self, pid: int, grense: int = 200) -> list[dict]:
        okter = self.db.alle("SELECT * FROM okter WHERE profil_id = ? AND status = 'fullfort' ORDER BY startet DESC LIMIT ?", (pid, grense))
        if not okter:
            return []
        ider = [o["id"] for o in okter]
        sett = self.db.alle(f"SELECT okt_id, ovelse, vekt, reps, oppvarming FROM sett WHERE okt_id IN ({','.join('?' * len(ider))})", tuple(ider))
        ut = []
        for o in okter:
            s = [x for x in sett if x["okt_id"] == o["id"] and not x["oppvarming"]]
            ovl = list(dict.fromkeys(x["ovelse"] for x in s))
            ut.append({
                "id": o["id"], "startet": o["startet"], "dag_navn": o["dag_navn"], "opplevd": o["opplevd"],
                "minutter": self._minutter(o), "sett": len(s), "volum": round(sum((x["vekt"] or 0) * (x["reps"] or 0) for x in s)),
                "ovelser": [self.ovelse(k)["navn"] for k in ovl], "notat": o["notat"], "har_ai": bool(o["ai_oppsummering"]),
                "uke": self._uke(fra_iso(o["startet"])),
            })
        return ut

    def ovelser_med_historikk(self, pid: int) -> list[dict]:
        r = self.db.alle(
            "SELECT s.ovelse, COUNT(DISTINCT s.okt_id) AS okter, MAX(o.startet) AS sist FROM sett s JOIN okter o ON o.id = s.okt_id "
            "WHERE o.profil_id = ? AND o.status = 'fullfort' AND s.oppvarming = 0 GROUP BY s.ovelse ORDER BY sist DESC", (pid,))
        return [{**x, "navn": self.ovelse(x["ovelse"])["navn"], "monster": self.ovelse(x["ovelse"])["monster"]} for x in r]

    def ovelse_historikk(self, pid: int, nokkel: str) -> dict:
        ov = self.ovelse(nokkel)
        okter = self.db.alle(
            "SELECT DISTINCT o.id, o.startet, o.dag_navn FROM okter o JOIN sett s ON s.okt_id = o.id "
            "WHERE o.profil_id = ? AND s.ovelse = ? AND o.status = 'fullfort' ORDER BY o.startet", (pid, nokkel))
        punkter = []
        beste = {"e1rm": None, "vekt": None, "reps": None}
        for o in okter:
            s = self.db.alle("SELECT vekt, reps, rir, settnr FROM sett WHERE okt_id = ? AND ovelse = ? AND oppvarming = 0 ORDER BY settnr", (o["id"], nokkel))
            if not s:
                continue
            e = [P.e1rm(x["vekt"], x["reps"]) for x in s]
            e_best = max([x for x in e if x] or [None], key=lambda x: x or 0)
            topp = max(s, key=lambda x: ((x["vekt"] or 0), x["reps"] or 0))
            punkt = {"okt_id": o["id"], "startet": o["startet"], "dag_navn": o["dag_navn"], "sett": s, "e1rm": e_best,
                     "topp_kg": topp["vekt"], "topp_reps": topp["reps"], "maks_reps": max(x["reps"] or 0 for x in s),
                     "volum": round(sum((x["vekt"] or 0) * (x["reps"] or 0) for x in s))}
            punkter.append(punkt)
            if e_best and (beste["e1rm"] is None or e_best > beste["e1rm"]):
                beste["e1rm"] = e_best
            if topp["vekt"] and (beste["vekt"] is None or topp["vekt"] > beste["vekt"]):
                beste["vekt"] = topp["vekt"]
            if beste["reps"] is None or punkt["maks_reps"] > beste["reps"]:
                beste["reps"] = punkt["maks_reps"]
        return {"ovelse": {k: ov.get(k) for k in ("nokkel", "navn", "monster", "type", "tips", "muskler", "instruksjon")},
                "vektbasert": vektbasert(ov), "sekunder": sekunder(ov), "punkter": punkter, "beste": beste}

    def statistikk(self, pid: int) -> dict:
        p = self.profil(pid)
        naa_l = self.lokal(naa())
        mandag = (naa_l - timedelta(days=naa_l.weekday())).replace(hour=0, minute=0, second=0, microsecond=0)
        uker = []
        for i in range(11, -1, -1):
            start = mandag - timedelta(weeks=i)
            slutt = start + timedelta(weeks=1)
            n = self.db.verdi("SELECT COUNT(*) FROM okter WHERE profil_id = ? AND status = 'fullfort' AND startet >= ? AND startet < ?",
                              (pid, til_iso(start), til_iso(slutt)))
            uker.append({"uke": start.isocalendar()[1], "start": start.date().isoformat(), "okter": n})
        # harde sett per muskelgruppe siste 7 dager og snitt siste 4 uker
        fra4 = til_iso(naa() - timedelta(days=28))
        fra1 = til_iso(naa() - timedelta(days=7))
        rader = self.db.alle(
            "SELECT s.ovelse, o.startet FROM sett s JOIN okter o ON o.id = s.okt_id "
            "WHERE o.profil_id = ? AND o.status = 'fullfort' AND s.oppvarming = 0 AND o.startet >= ?", (pid, fra4))
        muskel = {m: {"navn": n, "uke": 0, "snitt": 0.0} for m, n in MUSKLER.items()}
        for r in rader:
            ov = self.ovelse(r["ovelse"])
            for i, m in enumerate(ov.get("muskler") or []):
                if m not in muskel:
                    continue
                vekt = 1.0 if i == 0 else 0.5  # primærmuskel teller helt, de andre halvt
                muskel[m]["snitt"] += vekt / 4
                if r["startet"] >= fra1:
                    muskel[m]["uke"] += vekt
        for m in muskel.values():
            m["uke"] = round(m["uke"], 1)
            m["snitt"] = round(m["snitt"], 1)
        totalt = self.db.en("SELECT COUNT(*) AS okter, MIN(startet) AS forste FROM okter WHERE profil_id = ? AND status = 'fullfort'", (pid,))
        denne = uker[-1]["okter"]
        # rekke: uker på rad med planlagt antall økter (ikke medregnet inneværende uke hvis den ikke er nådd)
        rekke = 0
        for u in reversed(uker[:-1] if denne < (p.get("dager_per_uke") or 3) else uker):
            if u["okter"] >= min(2, p.get("dager_per_uke") or 2):
                rekke += 1
            else:
                break
        return {"uker": uker, "muskler": list(muskel.values()), "totalt": totalt["okter"], "forste": totalt["forste"],
                "denne_uka": denne, "plan_per_uke": p.get("dager_per_uke") or 3, "uker_paa_rad": rekke,
                "muskelvekst": "muskelvekst" in (p.get("maal") or [])}

    def oversikt(self, pid: int, upid: int | None = None) -> dict:
        p = self.profil(pid)
        prog = self.aktivt_program(pid)
        neste = self.neste_dag(pid, prog)
        aktiv = self.aktiv_okt(pid)
        sist = self.db.en("SELECT * FROM okter WHERE profil_id = ? AND status = 'fullfort' ORDER BY startet DESC LIMIT 1", (pid,))
        neste_ut = None
        if neste:
            utstyr = self.utstyr_for(upid or p.get("utstyrsprofil_id"))
            ovl = []
            brukt: set[str] = set()
            for o in neste["ovelser"]:
                ov = self.ovelse(o["ovelse"])
                erstatning = None
                if not tilgjengelig(ov, utstyr):
                    alt = P.velg_ovelse(ov["monster"], self.ovelser(), utstyr, p.get("erfaring") or "noe",
                                        "rehab" in (p.get("maal") or []), brukt | {o["ovelse"]})
                    if alt:
                        erstatning, ov = ov["navn"], alt
                brukt.add(ov["nokkel"])
                tidl = self.tidligere_sett(pid, ov["nokkel"], antall=2)
                f = self.forslag(pid, ov, o, tidl)
                if prog["blokk"]["lett_naa"]:
                    f = P.lett_forslag(f, tidl)
                    o = P.lett_dose(o)
                ovl.append({"navn": ov["navn"], "sett": o["sett"], "reps_min": o["reps_min"], "reps_maks": o["reps_maks"],
                            "kg": f["kg"], "trend": f["trend"], "erstatter": erstatning, "tilgjengelig": tilgjengelig(ov, utstyr)})
            neste_ut = {"id": neste["id"], "navn": neste["navn"], "minutter": neste["minutter"], "ovelser": ovl}
        st = self.statistikk(pid)
        return {
            "profil": p, "program": {"id": prog["id"], "navn": prog["navn"], "blokk": prog["blokk"],
                                     "dager": [{"id": d["id"], "navn": d["navn"]} for d in prog["dager"]]} if prog else None,
            "neste": neste_ut, "aktiv": aktiv, "mangler_startvekt": self.mangler_startvekt(pid) if prog else 0,
            "loping": self._loping_kort(pid),
            "dagsform": __import__("dagsform").status(self, pid),
            "spill": __import__("spill").status(self, pid),
            "ukeplan": __import__("ukeplan").hent(self, pid) if (prog or (p.get("koblinger") or {}).get("kalendere")) else None,
            "sist": {"id": sist["id"], "startet": sist["startet"], "dag_navn": sist["dag_navn"]} if sist else None,
            "uke": {"okter": st["denne_uka"], "plan": st["plan_per_uke"], "uker_paa_rad": st["uker_paa_rad"],
                    "aktivitetsminutter": self._kropp_attributter(pid)["aktivitetsminutter_uke"]},
        }

    # ------------------------------------------------------------ sensorer
    def sensor_navn(self, p: dict) -> str:
        return f"sensor.styrkeboka_{slug(p['navn'])}"

    def sensorer(self) -> dict[str, dict]:
        ut = {}
        for p in self.profiler():
            st = self.statistikk(p["id"])
            sist = self.db.en("SELECT startet, dag_navn FROM okter WHERE profil_id = ? AND status = 'fullfort' ORDER BY startet DESC LIMIT 1", (p["id"],))
            aktiv = self.db.en("SELECT startet, dag_navn FROM okter WHERE profil_id = ? AND status = 'pagar' LIMIT 1", (p["id"],))
            neste = self.neste_dag(p["id"])
            dager_siden = (self.lokal(naa()).date() - self.lokal(sist["startet"]).date()).days if sist else None
            ut[self.sensor_navn(p)] = {
                "state": st["denne_uka"],
                "attributes": {
                    "friendly_name": f"Styrkeboka {p['navn']}", "icon": "mdi:dumbbell", "unit_of_measurement": "økter",
                    "plan_per_uke": st["plan_per_uke"], "uker_paa_rad": st["uker_paa_rad"],
                    "siste_okt": sist["startet"] if sist else None, "siste_okt_navn": sist["dag_navn"] if sist else None,
                    "dager_siden": dager_siden, "neste_okt": neste["navn"] if neste else None,
                    "trener_naa": bool(aktiv), "pagaende_okt": aktiv["dag_navn"] if aktiv else None,
                    "okter_totalt": st["totalt"],
                    **self._kropp_attributter(p["id"]),
                },
            }
        return ut

    def _loping_kort(self, pid: int) -> dict | None:
        import loping
        s = loping.status(self, pid)
        return s["aktiv"]

    def _kropp_attributter(self, pid: int) -> dict:
        import kropp
        u = kropp.uker(self, pid, 1)[-1]
        vekt = kropp.siste(self, pid, "vekt")
        return {"aktivitetsminutter_uke": u["minutter"], "km_loping_uke": u["km_loping"], "km_gaing_uke": u["km_gaing"],
                "vekt": vekt["verdi"] if vekt else None}

    # ------------------------------------------------------------ eksport
    def csv(self, pid: int | None = None) -> str:
        buf = io.StringIO()
        w = csv.writer(buf, delimiter=";")
        w.writerow(["profil", "dato", "økt", "øvelse", "sett", "oppvarming", "vekt_kg", "reps", "rir", "notat_økt"])
        sql = ("SELECT p.navn AS profil, o.startet, o.dag_navn, o.notat, s.ovelse, s.settnr, s.oppvarming, s.vekt, s.reps, s.rir "
               "FROM sett s JOIN okter o ON o.id = s.okt_id JOIN profiler p ON p.id = o.profil_id WHERE o.status = 'fullfort'")
        args: tuple = ()
        if pid:
            sql += " AND o.profil_id = ?"
            args = (pid,)
        for r in self.db.alle(sql + " ORDER BY o.startet, s.okt_ovelse_id, s.oppvarming DESC, s.settnr", args):
            w.writerow([r["profil"], self.lokal(r["startet"]).strftime("%Y-%m-%d %H:%M"), r["dag_navn"], self.ovelse(r["ovelse"])["navn"],
                        r["settnr"], "ja" if r["oppvarming"] else "", str(r["vekt"] or "").replace(".", ","), r["reps"],
                        r["rir"] if r["rir"] is not None else "", r["notat"] or ""])
        return buf.getvalue()

    # ------------------------------------------------------------ AI-logg
    def logg_ai(self, pid: int | None, typ: str, sporsmal: str, svar: str, oid: int | None = None) -> dict:
        aid = self.db.sett_inn("ai_logg", {"profil_id": pid, "okt_id": oid, "tid": til_iso(naa()), "type": typ,
                                           "sporsmal": sporsmal[:2000], "svar": svar[:8000]})
        return self.db.en("SELECT * FROM ai_logg WHERE id = ?", (aid,))

    def ai_logg(self, pid: int, grense: int = 30) -> list[dict]:
        return self.db.alle("SELECT * FROM ai_logg WHERE profil_id = ? AND type = 'sporsmal' ORDER BY id DESC LIMIT ?", (pid, grense))
