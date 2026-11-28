"""Stjerneboka – regler for oppgaver, stjerner, poeng og godkjenning.

Tre slags oppgaver:
* rutine  – ting man gjør for seg selv (tannpuss, do). Gir stjerne, aldri penger.
* familie – bidrag til familien (ta av bordet). Gir poeng, kan telle i ukepenger.
* ekstra  – krevende innsats (tømme oppvaskmaskinen). Flere poeng, ofte med godkjenning.

En stjerne er én godkjent registrering. Poeng (1–3) sier hvor krevende oppgaven er.
Ukepenger = poeng fra pengeoppgaver × kroner per poeng (når det er slått på).
"""
from __future__ import annotations

import re
import unicodedata
from datetime import datetime, time, timedelta
from typing import Callable
from zoneinfo import ZoneInfo

from db import Database, fra_iso, naa, til_iso

TYPER = ("rutine", "familie", "ekstra")
TYPE_NAVN = {"rutine": "Rutine", "familie": "Familiebidrag", "ekstra": "Ekstra innsats"}
OKTER = ("morgen", "dag", "kveld")
OKT_NAVN = {"morgen": "Morgen", "dag": "Dag", "kveld": "Kveld", "hele_dagen": "Hele dagen"}
SPERRER = ("okt", "dag", "intervall", "fri")
FARGER = ("rosa", "blaa", "lilla", "gronn", "oransje", "gul")
INNEBYGDE_BILDER = ("tannpuss", "gre_haret", "do", "kle_pa", "neseskylling", "ta_av_bordet",
                    "dekke_bordet", "rydde_rommet", "rydde_leker", "oppvaskmaskin", "skittentoy")

STANDARD = {
    "morgen_fra": "04:00", "dag_fra": "12:00", "kveld_fra": "16:00",
    "ukepenger_aktiv": "0", "kr_per_poeng": "2",
    "lyd_aktiv": "1", "lydmetode": "music_assistant", "hoyttaler": "", "tts": "",
    "volum_dag": "45", "volum_kveld": "30", "stille_fra": "19:00", "stille_til": "07:00", "fanfare_url": "",
    "skjerm_browser": "", "barneside_url": "", "vis_ved_kort": "1",
    "varsle_tjeneste": "", "angre_sekunder": "120", "musikk_hoyttaler": "",
}
HANDLINGER = ("oppgave", "vis_skjerm", "musikk", "ha")
MEDIETYPER = ("auto", "track", "album", "playlist", "artist", "radio", "audiobook", "podcast")

# Forslag som kan legges til med ett trykk. Generiske – ingen navn eller personlige data.
MALER = [
    {"navn": "Tannpuss", "bilde": "innebygd:tannpuss", "type": "rutine", "poeng": 1, "nar": "morgen,kveld",
     "sperre": "okt", "ros": "pusset tenner"},
    {"navn": "Gå på do", "bilde": "innebygd:do", "type": "rutine", "poeng": 1, "nar": "hele_dagen",
     "sperre": "intervall", "intervall_min": 30, "ros": "vært på do"},
    {"navn": "Kle på seg", "bilde": "innebygd:kle_pa", "type": "rutine", "poeng": 1, "nar": "morgen,kveld",
     "sperre": "okt", "ros": "kledd på deg"},
    {"navn": "Gre håret", "bilde": "innebygd:gre_haret", "type": "rutine", "poeng": 1, "nar": "morgen,kveld",
     "sperre": "okt", "ros": "gredd håret"},
    {"navn": "Neseskylling", "bilde": "innebygd:neseskylling", "type": "rutine", "poeng": 1, "nar": "morgen,kveld",
     "sperre": "okt", "ros": "skylt nesen"},
    {"navn": "Ta av bordet", "bilde": "innebygd:ta_av_bordet", "type": "familie", "poeng": 1, "nar": "hele_dagen",
     "sperre": "intervall", "intervall_min": 120, "ros": "tatt av bordet"},
    {"navn": "Dekke bordet", "bilde": "innebygd:dekke_bordet", "type": "familie", "poeng": 2, "nar": "hele_dagen",
     "sperre": "intervall", "intervall_min": 120, "ros": "dekket bordet"},
    {"navn": "Klær i skittentøyet", "bilde": "innebygd:skittentoy", "type": "familie", "poeng": 1,
     "nar": "kveld", "sperre": "okt", "ros": "lagt klærne i skittentøyet"},
    {"navn": "Rydde leker", "bilde": "innebygd:rydde_leker", "type": "familie", "poeng": 1, "nar": "hele_dagen",
     "sperre": "okt", "ros": "ryddet lekene"},
    {"navn": "Rydde rommet", "bilde": "innebygd:rydde_rommet", "type": "familie", "poeng": 2, "nar": "hele_dagen",
     "sperre": "dag", "godkjenning": 1, "ros": "ryddet rommet"},
    {"navn": "Tømme oppvaskmaskinen", "bilde": "innebygd:oppvaskmaskin", "type": "ekstra", "poeng": 3,
     "nar": "hele_dagen", "sperre": "dag", "godkjenning": 1, "ros": "tømt oppvaskmaskinen"},
]


class Feil(Exception):
    """Ugyldig forespørsel – vises som feilmelding."""


class Sperret(Feil):
    """Oppgaven er allerede gjort i dette tidsrommet."""


def slug(tekst: str) -> str:
    t = unicodedata.normalize("NFKD", tekst.lower().replace("æ", "ae").replace("ø", "o").replace("å", "a"))
    t = "".join(c for c in t if not unicodedata.combining(c))
    return re.sub(r"[^a-z0-9]+", "_", t).strip("_") or "barn"


def _kl(s: str, std: str) -> time:
    try:
        h, m = (int(x) for x in str(s or std).split(":")[:2])
        return time(h, m)
    except (ValueError, TypeError):
        h, m = (int(x) for x in std.split(":"))
        return time(h, m)


def _tall(s, std: float) -> float:
    try:
        return float(str(s).replace(",", "."))
    except (ValueError, TypeError):
        return std


def _bool(v) -> int:
    return 1 if v in (True, 1, "1", "true", "on", "ja") else 0


class Stjerneboka:
    def __init__(self, db: Database, tz: str = "Europe/Oslo"):
        self.db = db
        self.tz = ZoneInfo(tz)
        self._lyttere: list[Callable[[str, dict], None]] = []
        self.inn: dict[str, str] = {}
        self._les_innstillinger()

    # ------------------------------------------------------------ oppsett
    def sett_tidssone(self, tz: str) -> None:
        try:
            self.tz = ZoneInfo(tz)
        except Exception:  # noqa: BLE001
            pass

    def ved_endring(self, fn: Callable[[str, dict], None]) -> None:
        self._lyttere.append(fn)

    def _endret(self, hva: str, data: dict) -> None:
        for fn in self._lyttere:
            fn(hva, data)

    def _les_innstillinger(self) -> None:
        self.inn = {**STANDARD, **self.db.innstillinger()}

    def lagre_innstillinger(self, d: dict) -> dict:
        ok = {k: ("" if v is None else str(v)).strip() for k, v in d.items() if k in STANDARD}
        for k in ("hoyttaler", "musikk_hoyttaler"):
            if ok.get(k) and not ok[k].startswith("media_player."):
                raise Feil("Høyttaleren må være en media_player")
        if ok.get("tts") and not ok["tts"].startswith("tts."):
            raise Feil("Talemotoren må være en tts-enhet")
        for t in [x.strip() for x in (ok.get("varsle_tjeneste") or "").split(",") if x.strip()]:
            if not t.startswith("notify."):
                raise Feil("Varsling må være notify-tjenester, f.eks. notify.mobile_app_telefon")
        self.db.lagre_innstillinger(ok)
        self._les_innstillinger()
        self._endret("innstillinger", {})
        return self.inn

    @property
    def ukepenger(self) -> bool:
        return self.inn.get("ukepenger_aktiv") == "1"

    @property
    def kr_per_poeng(self) -> float:
        return _tall(self.inn.get("kr_per_poeng"), 2.0)

    # ------------------------------------------------------------ tid
    def lokal(self, t: datetime | None = None) -> datetime:
        return (t or naa()).astimezone(self.tz)

    def _grenser(self) -> list[tuple[str, time]]:
        return [("morgen", _kl(self.inn.get("morgen_fra"), "04:00")),
                ("dag", _kl(self.inn.get("dag_fra"), "12:00")),
                ("kveld", _kl(self.inn.get("kveld_fra"), "16:00"))]

    def okt(self, t: datetime | None = None) -> str:
        lt = self.lokal(t).time()
        navn = "kveld"
        for n, fra in self._grenser():
            if lt >= fra:
                navn = n
        return navn

    def okt_start(self, t: datetime | None = None) -> datetime:
        lt = self.lokal(t)
        start = None
        for _n, fra in self._grenser():
            if lt.time() >= fra:
                start = lt.replace(hour=fra.hour, minute=fra.minute, second=0, microsecond=0)
        if start is None:  # før morgen: kvelden i går
            fra = self._grenser()[2][1]
            start = (lt - timedelta(days=1)).replace(hour=fra.hour, minute=fra.minute, second=0, microsecond=0)
        return start

    def dag_start(self, t: datetime | None = None) -> datetime:
        lt = self.lokal(t)
        fra = self._grenser()[0][1]
        start = lt.replace(hour=fra.hour, minute=fra.minute, second=0, microsecond=0)
        return start if lt >= start else start - timedelta(days=1)

    def uke_start(self, t: datetime | None = None) -> datetime:
        lt = self.lokal(t)
        return (lt - timedelta(days=lt.weekday())).replace(hour=0, minute=0, second=0, microsecond=0)

    def uke_id(self, t: datetime | None = None) -> str:
        y, w, _ = self.lokal(t).isocalendar()
        return f"{y}-W{w:02d}"

    def i_stilletid(self, t: datetime | None = None) -> bool:
        fra, til = _kl(self.inn.get("stille_fra"), "19:00"), _kl(self.inn.get("stille_til"), "07:00")
        lt = self.lokal(t).time()
        return (lt >= fra or lt < til) if fra > til else (fra <= lt < til)

    # ------------------------------------------------------------ barn
    def lagre_barn(self, d: dict, bid: int | None = None) -> dict:
        navn = str(d.get("navn") or "").strip() if ("navn" in d or bid is None) else None
        if navn is not None and not navn:
            raise Feil("Barnet må ha et navn")
        ut = {}
        if navn is not None:
            ut["navn"] = navn[:40]
        if "farge" in d:
            if d["farge"] not in FARGER:
                raise Feil("Ukjent farge")
            ut["farge"] = d["farge"]
        if "emoji" in d:
            ut["emoji"] = str(d["emoji"] or "")[:8]
        if "aktiv" in d:
            ut["aktiv"] = _bool(d["aktiv"])
        b = self.db.lagre_barn(ut, bid)
        self._endret("barn", {})
        return b

    def slett_barn(self, bid: int) -> None:
        self.db.slett_barn(bid)
        self._endret("barn", {})

    # ------------------------------------------------------------ oppgaver
    def _rens_oppgave(self, d: dict, ny: bool) -> dict:
        ut: dict = {}
        if "navn" in d or ny:
            navn = str(d.get("navn") or "").strip()
            if not navn:
                raise Feil("Oppgaven må ha et navn")
            ut["navn"] = navn[:40]
        if "bilde" in d:
            b = str(d["bilde"] or "")
            if b.startswith("innebygd:") and b.split(":", 1)[1] not in INNEBYGDE_BILDER:
                raise Feil("Ukjent bilde")
            if not re.match(r"^(innebygd|emoji|fil):.+", b):
                raise Feil("Ugyldig bilde")
            ut["bilde"] = b[:120]
        if "type" in d:
            if d["type"] not in TYPER:
                raise Feil("Ukjent oppgavetype")
            ut["type"] = d["type"]
        if "poeng" in d:
            p = int(d["poeng"])
            if not 1 <= p <= 3:
                raise Feil("Poeng må være 1, 2 eller 3")
            ut["poeng"] = p
        for k in ("godkjenning", "penger", "aktiv"):
            if k in d:
                ut[k] = _bool(d[k])
        if "nar" in d:
            deler = [x.strip() for x in str(d["nar"]).split(",") if x.strip()]
            if not deler or "hele_dagen" in deler:
                ut["nar"] = "hele_dagen"
            else:
                if any(x not in OKTER for x in deler):
                    raise Feil("Ukjent tidspunkt")
                ut["nar"] = ",".join(x for x in OKTER if x in deler)
        if "sperre" in d:
            if d["sperre"] not in SPERRER:
                raise Feil("Ukjent sperre")
            ut["sperre"] = d["sperre"]
        if "intervall_min" in d:
            ut["intervall_min"] = max(1, min(24 * 60, int(d["intervall_min"] or 30)))
        if "maks_per_dag" in d:
            ut["maks_per_dag"] = max(0, min(20, int(d["maks_per_dag"] or 0)))
        if "ros" in d:
            ut["ros"] = str(d["ros"] or "").strip()[:80]
        if "barn" in d:
            gyldige = {b["id"] for b in self.db.barn()}
            ut["barn"] = [int(b) for b in d["barn"] or [] if int(b) in gyldige]
        # Rutiner gir aldri penger
        typ = ut.get("type")
        if typ == "rutine":
            ut["penger"] = 0
        return ut

    def lagre_oppgave(self, d: dict, oid: int | None = None) -> dict:
        if oid is not None and not self.db.en_oppgave(oid):
            raise Feil("Fant ikke oppgaven")
        ut = self._rens_oppgave(d, oid is None)
        if oid is not None and ut.get("penger") and "type" not in ut:
            if self.db.en_oppgave(oid)["type"] == "rutine":
                raise Feil("Rutiner kan ikke gi penger – gjør den til familiebidrag eller ekstra først")
        o = self.db.lagre_oppgave(ut, oid)
        self._endret("oppgave", {})
        return o

    def legg_til_mal(self, indeks: int, barn: list[int]) -> dict:
        if not 0 <= indeks < len(MALER):
            raise Feil("Ukjent forslag")
        return self.lagre_oppgave({**MALER[indeks], "barn": barn})

    def slett_oppgave(self, oid: int) -> None:
        self.db.slett_oppgave(oid)
        self._endret("oppgave", {})

    # ------------------------------------------------------------ status
    def _vindu_start(self, o: dict, t: datetime) -> datetime | None:
        s = o["sperre"]
        if s == "okt":
            return self.okt_start(t)
        if s == "dag":
            return self.dag_start(t)
        if s == "intervall":
            return t - timedelta(minutes=int(o.get("intervall_min") or 30))
        return None

    def oppgavestatus(self, barn_id: int, o: dict, t: datetime | None = None) -> dict:
        t = t or naa()
        siste = self.db.siste_for(barn_id, o["id"])
        fra = self._vindu_start(o, t)
        innenfor = bool(siste and fra and fra_iso(siste["tid"]) >= fra)
        dag = til_iso(self.dag_start(t))
        i_dag = [r for r in self.db.registreringer(fra=dag, barn_id=barn_id)
                 if r["oppgave_id"] == o["id"] and r["status"] != "avvist"]
        maks = int(o.get("maks_per_dag") or 0)
        dagsgrense = bool(maks and len(i_dag) >= maks)
        venter = innenfor and siste["status"] == "venter"
        return {
            "ferdig": (innenfor and siste["status"] == "godkjent") or (dagsgrense and not venter),
            "venter": venter,
            "dagsgrense": dagsgrense,
            "siste_id": siste["id"] if siste else None,
            "siste_tid": siste["tid"] if siste else None,
            "antall_i_dag": sum(1 for r in i_dag if r["status"] == "godkjent"),
            "brukt_i_dag": len(i_dag),
            "maks_per_dag": maks,
        }

    def aktuell(self, o: dict, t: datetime | None = None) -> bool:
        return o["nar"] == "hele_dagen" or self.okt(t) in o["nar"].split(",")

    def _for_barn(self, barn_id: int, bare_aktive: bool = True) -> list[dict]:
        return [o for o in self.db.oppgaver(bare_aktive) if barn_id in o["barn"]]

    # ------------------------------------------------------------ registrering
    def ros_tekst(self, o: dict) -> str:
        return o.get("ros") or f"gjort «{o['navn'].lower()}»"

    def registrer(self, barn_id: int, oppgave_id: int, kilde: str = "skjerm", av: str | None = None,
                  t: datetime | None = None) -> dict:
        t = t or naa()
        b = self.db.ett_barn(barn_id)
        if not b or not b["aktiv"]:
            raise Feil("Ukjent barn")
        o = self.db.en_oppgave(oppgave_id)
        if not o or not o["aktiv"]:
            raise Feil("Ukjent oppgave")
        if barn_id not in o["barn"]:
            raise Feil(f"{o['navn']} er ikke en oppgave for {b['navn']}")
        st = self.oppgavestatus(barn_id, o, t)
        if st["ferdig"] or st["venter"]:
            if st["dagsgrense"] and not st["venter"]:
                ganger = "én gang" if st["maks_per_dag"] == 1 else f"{st['maks_per_dag']} ganger"
                melding = (f"Du har {self.ros_tekst(o)} {ganger} i dag, {b['navn']}. "
                           "Det holder for i dag – kjempebra!")
            elif o["sperre"] == "intervall":
                melding = f"Du har nettopp {self.ros_tekst(o)}, {b['navn']}. Prøv igjen litt senere!"
            elif st["venter"]:
                melding = f"{b['navn']}, en voksen skal snart sjekke {o['navn'].lower()}."
            else:
                melding = f"Du har allerede {self.ros_tekst(o)}, {b['navn']}. Godt husket!"
            self._endret("sperret", {"barn": b, "oppgave": o, "melding": melding, "kilde": kilde})
            raise Sperret(melding)
        r = self.db.ny_registrering({
            "barn_id": barn_id, "oppgave_id": oppgave_id, "oppgave_navn": o["navn"], "tid": til_iso(t),
            "status": "venter" if o["godkjenning"] else "godkjent", "poeng": o["poeng"],
            "penger": o["penger"], "type": o["type"], "kilde": kilde, "av": av,
        })
        antall = self.stjerner_i_dag(barn_id, t)
        if r["status"] == "venter":
            melding = f"Så flott, {b['navn']}! Nå skal en voksen sjekke {o['navn'].lower()}."
        else:
            melding = (f"Bra jobba, {b['navn']}! Du har {self.ros_tekst(o)}. "
                       f"Det er stjerne nummer {antall} i dag!")
        data = {"registrering": r, "barn": b, "oppgave": o, "melding": melding, "stjerner_i_dag": antall,
                "kilde": kilde}
        self._endret("registrert", data)
        return {"registrering": r, "melding": melding, "stjerner_i_dag": antall}

    def godkjenn(self, rid: int, av: str | None = None, godkjent: bool = True) -> dict:
        r = self.db.registrering(rid)
        if not r:
            raise Feil("Fant ikke registreringen")
        if r["status"] != "venter":
            raise Feil("Registreringen er allerede behandlet")
        r = self.db.sett_status(rid, "godkjent" if godkjent else "avvist", av, til_iso(naa()))
        b = self.db.ett_barn(r["barn_id"])
        o = self.db.en_oppgave(r["oppgave_id"]) if r["oppgave_id"] else {"navn": r["oppgave_navn"], "ros": ""}
        if godkjent:
            melding = (f"Hurra, {b['navn']}! En voksen har godkjent {r['oppgave_navn'].lower()}. "
                       f"Du fikk {r['poeng']} {'poeng' if r['poeng'] > 1 else 'stjerne'}!")
        else:
            melding = f"{b['navn']}, {r['oppgave_navn'].lower()} er ikke helt ferdig ennå. Prøv en gang til!"
        self._endret("godkjent" if godkjent else "avvist",
                     {"registrering": r, "barn": b, "oppgave": o, "melding": melding,
                      "stjerner_i_dag": self.stjerner_i_dag(r["barn_id"])})
        return r

    def angre(self, rid: int, fra_skjerm: bool = True) -> None:
        r = self.db.registrering(rid)
        if not r:
            raise Feil("Fant ikke registreringen")
        if fra_skjerm:
            grense = int(_tall(self.inn.get("angre_sekunder"), 120))
            if (naa() - fra_iso(r["tid"])).total_seconds() > grense:
                raise Feil("Det er for lenge siden – be en voksen om å fjerne den")
        self.db.slett_registrering(rid)
        self._endret("angret", {"registrering": r})

    def registrer_admin(self, d: dict, av: str | None) -> dict:
        """Voksen registrerer for et barn, evt. bakover i tid. Hopper over sperre og godkjenning."""
        b = self.db.ett_barn(int(d["barn_id"]))
        o = self.db.en_oppgave(int(d["oppgave_id"]))
        if not b or not o:
            raise Feil("Ukjent barn eller oppgave")
        t = fra_iso(d["tid"]) if d.get("tid") else naa()
        r = self.db.ny_registrering({
            "barn_id": b["id"], "oppgave_id": o["id"], "oppgave_navn": o["navn"], "tid": til_iso(t),
            "status": "godkjent", "poeng": o["poeng"], "penger": o["penger"], "type": o["type"],
            "kilde": "admin", "av": av})
        self._endret("admin", {"registrering": r})
        return r

    def slett_registrering(self, rid: int) -> None:
        self.angre(rid, fra_skjerm=False)

    # ------------------------------------------------------------ kort og lesere
    def skann(self, uid: str, leser_id: str | None = None, leser_navn: str | None = None,
              leser_rom: str | None = None) -> dict:
        """Et kort er skannet. leser_id er Home Assistant-enheten som leste det (None for MQTT/gammel leser)."""
        uid = str(uid or "").strip().upper()
        if not uid:
            raise Feil("Tomt kort")
        leser = self.db.se_leser(leser_id, leser_navn, leser_rom, til_iso(naa())) if leser_id else None
        k = self.db.ett_kort(uid)
        if not k:
            self.db.ukjent_kort(uid, til_iso(naa()), leser_id)
            self._endret("ukjent_kort", {"uid": uid, "leser": leser})
            return {"handling": "ukjent", "uid": uid}
        if k["handling"] == "vis_skjerm":
            self._endret("vis_skjerm", {"uid": uid})
            return {"handling": "vis_skjerm"}
        if k["handling"] == "musikk":
            hoyttaler = k.get("hoyttaler") or (leser or {}).get("hoyttaler") or self.inn.get("musikk_hoyttaler")
            if not hoyttaler:
                return {"handling": "mangler_hoyttaler",
                        "melding": "Velg en høyttaler for leseren (eller en standard) under NFC-kort."}
            data = {"uid": uid, "kort": k, "hoyttaler": hoyttaler, "leser": leser}
            self._endret("musikk", data)
            return {"handling": "musikk", "hoyttaler": hoyttaler, "melding": f"Spiller {k.get('navn') or k['media_id']}"}
        if k["handling"] == "ha":
            self._endret("ha_handling", {"uid": uid, "kort": k, "leser": leser})
            return {"handling": "ha", "melding": f"Kjører {k['entity']}"}
        # oppgave
        if leser and not leser["gir_stjerner"]:
            return {"handling": "ikke_her", "melding": "Denne leseren gir ikke stjerner"}
        try:
            res = self.registrer(k["barn_id"], k["oppgave_id"], kilde="kort")
            return {"handling": "registrert", **res}
        except Sperret as s:
            return {"handling": "sperret", "melding": str(s)}

    def lagre_kort(self, uid: str, d: dict) -> dict:
        uid = str(uid or "").strip().upper()
        if not re.match(r"^[A-Z0-9:\-]{4,40}$", uid):
            raise Feil("Ugyldig kort-ID")
        handling = d.get("handling") or "oppgave"
        if handling not in HANDLINGER:
            raise Feil("Ukjent handling")
        ut = {"handling": handling, "navn": (str(d.get("navn") or "").strip()[:60]) or None}
        if handling == "oppgave":
            bid, oid = int(d.get("barn_id") or 0), int(d.get("oppgave_id") or 0)
            o = self.db.en_oppgave(oid)
            if not self.db.ett_barn(bid) or not o:
                raise Feil("Velg barn og oppgave")
            if bid not in o["barn"]:
                raise Feil("Oppgaven er ikke valgt for dette barnet")
            ut.update(barn_id=bid, oppgave_id=oid)
        elif handling == "musikk":
            media = str(d.get("media_id") or "").strip()
            if not media:
                raise Feil("Skriv hva som skal spilles (navn på sang, spilleliste, album eller radio)")
            typ = d.get("media_type") or "auto"
            if typ not in MEDIETYPER:
                raise Feil("Ukjent medietype")
            hoyttaler = str(d.get("hoyttaler") or "").strip()
            if hoyttaler and not hoyttaler.startswith("media_player."):
                raise Feil("Høyttaleren må være en media_player")
            bryter = str(d.get("bryter") or "").strip()
            if bryter and not re.match(r"^(input_boolean|switch)\.", bryter):
                raise Feil("Bryteren må være en input_boolean eller switch")
            ut.update(media_id=media[:200], media_type=typ, hoyttaler=hoyttaler or None, bryter=bryter or None)
        elif handling == "ha":
            ent = str(d.get("entity") or "").strip()
            if not re.match(r"^(automation|script|scene)\.[a-z0-9_]+$", ent):
                raise Feil("Velg en automasjon, et skript eller en scene")
            ut["entity"] = ent
        return self.db.lagre_kort(uid, ut)

    def lagre_leser(self, lid: str, d: dict) -> dict:
        if not self.db.en_leser(lid):
            raise Feil("Ukjent leser")
        ut = {}
        if "gir_stjerner" in d:
            ut["gir_stjerner"] = _bool(d["gir_stjerner"])
        if "hoyttaler" in d:
            h = str(d["hoyttaler"] or "").strip()
            if h and not h.startswith("media_player."):
                raise Feil("Høyttaleren må være en media_player")
            ut["hoyttaler"] = h
        return self.db.lagre_leser(lid, ut)

    # ------------------------------------------------------------ tall
    def _godkjente(self, barn_id: int, fra: datetime, til: datetime | None = None) -> list[dict]:
        return self.db.registreringer(fra=til_iso(fra), til=til_iso(til) if til else None,
                                      barn_id=barn_id, status="godkjent")

    def stjerner_i_dag(self, barn_id: int, t: datetime | None = None) -> int:
        return len(self._godkjente(barn_id, self.dag_start(t)))

    def ukesum(self, barn_id: int, uke_start: datetime) -> dict:
        regs = self._godkjente(barn_id, uke_start, uke_start + timedelta(days=7))
        poeng_penger = sum(r["poeng"] for r in regs if r["penger"])
        per_type = {t: sum(1 for r in regs if r["type"] == t) for t in TYPER}
        return {
            "stjerner": len(regs), "poeng": sum(r["poeng"] for r in regs if r["type"] != "rutine"),
            "poeng_penger": poeng_penger,
            "kroner": round(poeng_penger * self.kr_per_poeng, 2) if self.ukepenger else None,
            "per_type": per_type,
        }

    # ------------------------------------------------------------ visninger
    def barnevisning(self, t: datetime | None = None) -> dict:
        """Alt barnesiden trenger: barn, oppgaver nå og status."""
        t = t or naa()
        okt = self.okt(t)
        angre_grense = int(_tall(self.inn.get("angre_sekunder"), 120))
        ut = []
        for b in self.db.barn(bare_aktive=True):
            na, hjelpe, mangler = [], [], []
            for o in self._for_barn(b["id"]):
                if not self.aktuell(o, t):
                    continue
                st = self.oppgavestatus(b["id"], o, t)
                kan_angre = bool(st["siste_id"] and (st["ferdig"] or st["venter"]) and st["siste_tid"]
                                 and (t - fra_iso(st["siste_tid"])).total_seconds() <= angre_grense)
                kort = {"id": o["id"], "navn": o["navn"], "bilde": o["bilde"], "type": o["type"],
                        "poeng": o["poeng"], "godkjenning": bool(o["godkjenning"]), "penger": bool(o["penger"]),
                        "ferdig": st["ferdig"], "venter": st["venter"], "antall_i_dag": st["antall_i_dag"],
                        "fri": o["sperre"] == "fri", "maks_per_dag": st["maks_per_dag"],
                        "brukt_i_dag": st["brukt_i_dag"],
                        "angre_id": st["siste_id"] if kan_angre else None}
                if o["type"] == "rutine":
                    na.append(kort)
                    if not (st["ferdig"] or st["venter"]):
                        mangler.append(o["navn"])
                else:
                    hjelpe.append(kort)
            uke = self.ukesum(b["id"], self.uke_start(t))
            ut.append({"id": b["id"], "navn": b["navn"], "farge": b["farge"], "emoji": b["emoji"],
                       "stjerner_i_dag": self.stjerner_i_dag(b["id"], t), "uke": uke,
                       "rutiner": na, "hjelpe": hjelpe, "mangler": mangler,
                       "alt_ferdig": bool(na) and not mangler})
        return {"okt": okt, "okt_navn": OKT_NAVN[okt], "barn": ut, "ukepenger": self.ukepenger,
                "naa": til_iso(t), "feiringer": self.feiringer(t)}

    def feiringer(self, t: datetime | None = None, sekunder: int = 30) -> list[dict]:
        """Nylige stjerner og godkjenninger, så barnesiden kan vise raketten uansett hvor de kom fra."""
        t = t or naa()
        fra = til_iso(t - timedelta(seconds=sekunder))
        ut = []
        navn = {b["id"]: b for b in self.db.barn()}
        for r in self.db.registreringer(fra=til_iso(t - timedelta(hours=12)), grense=50):
            b = navn.get(r["barn_id"])
            if not b:
                continue
            if r["status"] == "godkjent" and r["behandlet_tid"] and r["behandlet_tid"] >= fra:
                ut.append({"nokkel": f"{r['id']}-g", "barn": b["navn"], "farge": b["farge"],
                           "tekst": r["oppgave_navn"], "poeng": r["poeng"], "art": "godkjent"})
            elif r["tid"] >= fra and r["status"] in ("godkjent", "venter"):
                ut.append({"nokkel": f"{r['id']}-{r['status'][0]}", "barn": b["navn"], "farge": b["farge"],
                           "tekst": r["oppgave_navn"], "poeng": r["poeng"],
                           "art": "stjerne" if r["status"] == "godkjent" else "venter"})
        return ut

    def admin_oversikt(self, t: datetime | None = None) -> dict:
        t = t or naa()
        uke0 = self.uke_start(t)
        barn = self.db.barn()
        navn = {b["id"]: b["navn"] for b in barn}
        utbetalt = {(u["barn_id"], u["uke"]): u for u in self.db.utbetalinger()}
        uker = []
        for i in range(8):
            us = uke0 - timedelta(days=7 * i)
            uid = self.uke_id(us)
            rader = []
            for b in barn:
                s = self.ukesum(b["id"], us)
                u = utbetalt.get((b["id"], uid))
                rader.append({"barn_id": b["id"], **s, "utbetalt": u["belop"] if u else None})
            uker.append({"uke": uid, "start": us.date().isoformat(), "nr": int(uid.split("W")[1]), "barn": rader})
        ventende = [{**r, "barn": navn.get(r["barn_id"], "?")} for r in self.db.registreringer(status="venter")]
        siste = [{**r, "barn": navn.get(r["barn_id"], "?")}
                 for r in self.db.registreringer(fra=til_iso(t - timedelta(days=14)), grense=120)]
        return {"barn": barn, "uker": uker, "ventende": ventende, "siste": siste,
                "ukepenger": self.ukepenger, "kr_per_poeng": self.kr_per_poeng,
                "barnevisning": self.barnevisning(t)}

    def marker_utbetalt(self, barn_id: int, uke: str, av: str | None, angre: bool = False) -> None:
        if not re.match(r"^\d{4}-W\d{2}$", uke):
            raise Feil("Ugyldig uke")
        if angre:
            self.db.angre_utbetaling(barn_id, uke)
            return
        y, w = uke.split("-W")
        start = datetime.fromisocalendar(int(y), int(w), 1).replace(tzinfo=self.tz)
        s = self.ukesum(barn_id, start)
        if s["kroner"] is None:
            raise Feil("Ukepenger er ikke slått på")
        self.db.registrer_utbetaling(barn_id, uke, s["kroner"], til_iso(naa()), av)

    # ------------------------------------------------------------ Home Assistant
    def sensorer(self, t: datetime | None = None) -> dict[str, dict]:
        vis = self.barnevisning(t)
        ut: dict[str, dict] = {}
        ventende_tot = 0
        for b in vis["barn"]:
            ventende = sum(1 for k in b["rutiner"] + b["hjelpe"] if k["venter"])
            ventende_tot += ventende
            ut[f"sensor.stjerneboka_{slug(b['navn'])}"] = {
                "state": b["stjerner_i_dag"],
                "attributes": {
                    "friendly_name": f"Stjerneboka {b['navn']}", "icon": "mdi:star-face",
                    "unit_of_measurement": "stjerner", "state_class": "measurement",
                    "stjerner_uke": b["uke"]["stjerner"], "poeng_uke": b["uke"]["poeng"],
                    "kroner_uke": b["uke"]["kroner"], "okt": vis["okt"],
                    "mangler": b["mangler"], "alt_ferdig": b["alt_ferdig"], "venter_godkjenning": ventende,
                },
            }
        ut["sensor.stjerneboka_venter_godkjenning"] = {
            "state": ventende_tot,
            "attributes": {"friendly_name": "Stjerneboka venter på godkjenning", "icon": "mdi:account-clock"},
        }
        return ut

    def finn_barn(self, verdi) -> dict | None:
        s = str(verdi or "").strip().lower()
        return next((b for b in self.db.barn() if str(b["id"]) == s or b["navn"].lower() == s), None)

    def finn_oppgave(self, verdi) -> dict | None:
        s = str(verdi or "").strip().lower()
        return next((o for o in self.db.oppgaver() if str(o["id"]) == s or o["navn"].lower() == s), None)
