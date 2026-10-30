"""Kjernelogikken i Plasterboka: registrering, episoder, døgndoser og sensorverdier."""
from __future__ import annotations

import re
from datetime import date, datetime, time, timedelta
from typing import Callable
from zoneinfo import ZoneInfo

from db import Database, fra_iso, naa, til_iso

FARGER = ("lilla", "oransje", "blaa", "gronn", "rosa", "gul")
FORMER = ("mikstur", "tablett", "stikkpille", "annet")
METODER = ("ore", "munn", "panne", "endetarm", "arm")
METODE_NAVN = {"ore": "øre", "munn": "munn", "panne": "panne", "endetarm": "endetarm", "arm": "armhule", "notat": "fra notat"}

STANDARD_SYMPTOMER = [
    "Frysninger", "Slapp", "Hoste", "Rennende nese", "Sår hals", "Vondt i øret", "Hodepine",
    "Magevondt", "Oppkast", "Diaré", "Utslett", "Dårlig matlyst", "Urolig søvn", "Hes",
    "Rask pust", "Neseblod",
]

STANDARD_INNSTILLINGER = {
    "symptomer": STANDARD_SYMPTOMER,
    "feber_grense": 38.0,        # Helsenorge: feber = 38,0 °C eller mer
    "episode_pause_t": 72,       # mer enn så mange timer uten registrering = ny sykdomsepisode
    "syk_vindu_t": 48,           # «syk» så lenge siste registrering er nyere enn dette
    "varsle_tjeneste": "",       # f.eks. notify.mobil – tom = ingen varsling
    "standard_metode": "ore",
}

HELSENORGE_FEBER = "https://www.helsenorge.no/sykdom/barn/feber-hos-barn/"


class Feil(Exception):
    """Feil som skal vises til brukeren."""


class Advarsel(Exception):
    """Registreringen kan lagres, men bør bekreftes først."""

    def __init__(self, advarsler: list[str]):
        super().__init__("; ".join(advarsler))
        self.advarsler = advarsler


def _tall(v, navn: str, lav: float | None = None, hoy: float | None = None) -> float | None:
    if v in (None, ""):
        return None
    try:
        x = float(str(v).replace(",", "."))
    except ValueError:
        raise Feil(f"Ugyldig verdi for {navn}")
    if (lav is not None and x < lav) or (hoy is not None and x > hoy):
        raise Feil(f"{navn.capitalize()} må være mellom {lav:g} og {hoy:g}")
    return x


def _fmt(x: float | None) -> str:
    if x is None:
        return ""
    return f"{x:g}".replace(".", ",")


def slug(tekst: str) -> str:
    t = tekst.lower()
    for a, b in (("æ", "ae"), ("ø", "o"), ("å", "a"), ("é", "e"), ("ü", "u"), ("ö", "o"), ("ä", "a")):
        t = t.replace(a, b)
    return re.sub(r"[^a-z0-9]+", "_", t).strip("_") or "barn"


class Plasterboka:
    def __init__(self, db: Database, tz: str = "Europe/Oslo"):
        self.db = db
        self.tz = ZoneInfo(tz)
        self._lyttere: list[Callable[[str, dict | None], None]] = []
        self.inn = dict(STANDARD_INNSTILLINGER)
        self.inn.update({k: v for k, v in db.les_innstillinger().items() if k in STANDARD_INNSTILLINGER})

    # ------------------------------------------------------------ generelt
    def sett_tidssone(self, tz: str) -> None:
        try:
            self.tz = ZoneInfo(tz)
        except Exception:  # noqa: BLE001
            pass

    def ved_endring(self, fn: Callable[[str, dict | None], None]) -> None:
        self._lyttere.append(fn)

    def _endret(self, hva: str, data: dict | None = None) -> None:
        for fn in self._lyttere:
            try:
                fn(hva, data)
            except Exception:  # noqa: BLE001
                pass

    def lokal(self, dt: datetime) -> datetime:
        return dt.astimezone(self.tz)

    def kl(self, dt: datetime | str) -> str:
        if isinstance(dt, str):
            dt = fra_iso(dt)
        return self.lokal(dt).strftime("%H:%M")

    def dag_start(self, d: date) -> datetime:
        return datetime.combine(d, time.min, tzinfo=self.tz)

    def i_dag(self) -> date:
        return self.lokal(naa()).date()

    def lagre_innstillinger(self, d: dict) -> dict:
        ny = {}
        if "symptomer" in d:
            liste = [str(s).strip()[:30] for s in (d["symptomer"] or []) if str(s).strip()]
            ny["symptomer"] = list(dict.fromkeys(liste))[:40]
        if "feber_grense" in d:
            ny["feber_grense"] = _tall(d["feber_grense"], "febergrense", 37.0, 39.0)
        if "episode_pause_t" in d:
            ny["episode_pause_t"] = int(_tall(d["episode_pause_t"], "pause mellom episoder", 12, 240))
        if "syk_vindu_t" in d:
            ny["syk_vindu_t"] = int(_tall(d["syk_vindu_t"], "tid før «frisk»", 6, 168))
        if "varsle_tjeneste" in d:
            t = str(d["varsle_tjeneste"] or "").strip()
            if t and not re.fullmatch(r"notify\.[a-z0-9_]+", t):
                raise Feil("Varslingstjenesten må se ut som notify.navn")
            ny["varsle_tjeneste"] = t
        if "standard_metode" in d:
            if d["standard_metode"] not in METODER:
                raise Feil("Ukjent målemetode")
            ny["standard_metode"] = d["standard_metode"]
        self.inn.update(ny)
        self.db.lagre_innstillinger(ny)
        if {"episode_pause_t"} & ny.keys():
            for b in self.db.barn():
                self.regn_episoder(b["id"])
        self._endret("innstillinger")
        return self.inn

    # ------------------------------------------------------------ barn
    def lagre_barn(self, d: dict, bid: int | None = None) -> dict:
        ny = {}
        if "navn" in d or bid is None:
            navn = str(d.get("navn") or "").strip()
            if not navn or len(navn) > 30:
                raise Feil("Navnet må være 1–30 tegn")
            ny["navn"] = navn
        if "farge" in d:
            if d["farge"] not in FARGER:
                raise Feil("Ukjent farge")
            ny["farge"] = d["farge"]
        if "fodselsdato" in d:
            v = d["fodselsdato"]
            if v in (None, ""):
                ny["fodselsdato"] = None
            else:
                try:
                    ny["fodselsdato"] = date.fromisoformat(str(v)).isoformat()
                except ValueError:
                    raise Feil("Ugyldig dato")
        if "vekt_kg" in d:
            ny["vekt_kg"] = _tall(d["vekt_kg"], "vekt", 0.5, 150)
        if "aktiv" in d:
            ny["aktiv"] = 1 if d["aktiv"] else 0
        if "rekkefolge" in d:
            ny["rekkefolge"] = int(d["rekkefolge"])
        if bid is not None and not self.db.ett_barn(bid):
            raise Feil("Fant ikke barnet")
        b = self.db.lagre_barn(ny, bid)
        self._endret("barn", b)
        return b

    def slett_barn(self, bid: int) -> None:
        if not self.db.slett_barn(bid):
            raise Feil("Fant ikke barnet")
        self._endret("barn")

    def alder(self, b: dict) -> dict | None:
        if not b.get("fodselsdato"):
            return None
        fd = date.fromisoformat(b["fodselsdato"])
        i_dag = self.i_dag()
        if fd > i_dag:
            dager = (fd - i_dag).days
            return {"maaneder": None, "ufodt": True, "tekst": f"termin om {dager} dager" if dager != 1 else "termin i morgen"}
        mnd = (i_dag.year - fd.year) * 12 + i_dag.month - fd.month - (1 if i_dag.day < fd.day else 0)
        if mnd < 1:
            uker = (i_dag - fd).days // 7
            tekst = f"{uker} uker" if uker != 1 else "1 uke"
        elif mnd < 24:
            tekst = f"{mnd} mnd"
        else:
            tekst = f"{mnd // 12} år"
        return {"maaneder": mnd, "ufodt": False, "tekst": tekst}

    # ------------------------------------------------------------ legemidler
    def lagre_legemiddel(self, d: dict, lid: int | None = None) -> dict:
        ny = {}
        if "navn" in d or lid is None:
            navn = str(d.get("navn") or "").strip()
            if not navn or len(navn) > 40:
                raise Feil("Navnet må være 1–40 tegn")
            annen = self.db.finn_legemiddel(navn)
            if annen and annen["id"] != lid:
                raise Feil("Det finnes allerede et legemiddel med det navnet")
            ny["navn"] = navn
        if "virkestoff" in d or lid is None:
            ny["virkestoff"] = (str(d.get("virkestoff") or "").strip() or ny.get("navn") or "")[:40]
        if "form" in d:
            if d["form"] not in FORMER:
                raise Feil("Ukjent legemiddelform")
            ny["form"] = d["form"]
        if "mg_per_ml" in d:
            ny["mg_per_ml"] = _tall(d["mg_per_ml"], "styrke", 0.01, 1000)
        if "arkivert" in d:
            ny["arkivert"] = 1 if d["arkivert"] else 0
        lm = self.db.lagre_legemiddel(ny, lid)
        self._endret("legemidler", lm)
        return lm

    def slett_legemiddel(self, lid: int) -> str:
        if self.db.bruk_av_legemiddel(lid):
            self.db.lagre_legemiddel({"arkivert": 1}, lid)
            self._endret("legemidler")
            return "arkivert"
        self.db.slett_legemiddel(lid)
        self._endret("legemidler")
        return "slettet"

    def lagre_barn_legemiddel(self, bid: int, lid: int, d: dict) -> dict:
        if not self.db.ett_barn(bid) or not self.db.legemiddel(lid):
            raise Feil("Fant ikke barn eller legemiddel")
        ny = {}
        if "aktiv" in d:
            ny["aktiv"] = 1 if d["aktiv"] else 0
        if "standard_mg" in d:
            ny["standard_mg"] = _tall(d["standard_mg"], "standarddose", 0.1, 5000)
        if "min_intervall_t" in d:
            ny["min_intervall_t"] = _tall(d["min_intervall_t"], "minste intervall", 0.5, 72)
        if "maks_dogn_mg" in d:
            ny["maks_dogn_mg"] = _tall(d["maks_dogn_mg"], "maks døgndose", 1, 20000)
        if "kur_doser_dag" in d:
            v = _tall(d["kur_doser_dag"], "doser per dag", 1, 12)
            ny["kur_doser_dag"] = int(v) if v else None
        if "kur_til" in d:
            v = d["kur_til"]
            try:
                ny["kur_til"] = date.fromisoformat(str(v)).isoformat() if v else None
            except ValueError:
                raise Feil("Ugyldig sluttdato for kuren")
        self.db.lagre_barn_legemiddel(bid, lid, ny)
        self._endret("legemidler")
        return self.db.barn_legemiddel(bid, lid)

    # ------------------------------------------------------------ registrering
    def _rens_registrering(self, d: dict, gammel: dict | None = None) -> dict:
        ny: dict = {}
        if "barn_id" in d or gammel is None:
            bid = d.get("barn_id")
            if bid in (None, "") and gammel is None:
                raise Feil("Velg barn")
            if bid not in (None, ""):
                if not self.db.ett_barn(int(bid)):
                    raise Feil("Fant ikke barnet")
                ny["barn_id"] = int(bid)
        if "tid" in d or gammel is None:
            if d.get("tid"):
                tid = fra_iso(d["tid"])
            elif d.get("minutter_siden") not in (None, ""):
                tid = naa() - timedelta(minutes=int(d["minutter_siden"]))
            else:
                tid = naa()
            if tid > naa() + timedelta(minutes=5):
                raise Feil("Tidspunktet kan ikke være frem i tid")
            ny["tid"] = til_iso(tid)
        if "temp" in d:
            ny["temp"] = _tall(d["temp"], "temperatur", 34, 43)
            if ny["temp"] is not None:
                m = d.get("temp_metode") or (gammel or {}).get("temp_metode") or self.inn["standard_metode"]
                ny["temp_metode"] = m if m in METODER or m == "notat" else self.inn["standard_metode"]
            else:
                ny["temp_metode"] = None
        elif "temp_metode" in d and d["temp_metode"] in METODER:
            ny["temp_metode"] = d["temp_metode"]
        if "legemiddel_id" in d:
            lid = d.get("legemiddel_id")
            if lid in (None, ""):
                ny.update(legemiddel_id=None, dose_mg=None, dose_ml=None)
            else:
                lm = self.db.legemiddel(int(lid))
                if not lm:
                    raise Feil("Fant ikke legemiddelet")
                ny["legemiddel_id"] = lm["id"]
                ml = _tall(d.get("dose_ml"), "mengde", 0.1, 500)
                mg = _tall(d.get("dose_mg"), "dose", 0.1, 10000)
                if ml is not None and lm.get("mg_per_ml"):
                    mg = round(ml * lm["mg_per_ml"], 2)
                if mg is None:
                    raise Feil("Skriv inn dose")
                ny["dose_mg"], ny["dose_ml"] = mg, ml
        if "symptomer" in d:
            liste = d.get("symptomer") or []
            if not isinstance(liste, list):
                raise Feil("Ugyldige symptomer")
            ny["symptomer"] = list(dict.fromkeys(str(s).strip()[:30] for s in liste if str(s).strip()))
        if "notat" in d:
            ny["notat"] = (str(d.get("notat") or "").strip()[:1000]) or None
        return ny

    def _har_innhold(self, r: dict) -> bool:
        return any([r.get("temp") is not None, r.get("legemiddel_id"), r.get("symptomer"), r.get("notat")])

    def _doser(self, barn_id: int, virkestoff: str, fra: datetime, til: datetime,
               unntatt: int | None = None) -> list[dict]:
        ider = {l["id"] for l in self.db.legemidler() if l["virkestoff"].lower() == virkestoff.lower()}
        return [r for r in self.db.registreringer(barn_id=barn_id, fra=fra, til=til)
                if r["legemiddel_id"] in ider and r["dose_mg"] and r["id"] != unntatt]

    def kontroller_dose(self, barn_id: int, lid: int, mg: float, tid: datetime,
                        unntatt: int | None = None) -> list[str]:
        lm = self.db.legemiddel(lid)
        bl = self.db.barn_legemiddel(barn_id, lid) or {}
        adv = []
        if bl.get("min_intervall_t"):
            vindu = timedelta(hours=bl["min_intervall_t"])
            naer = [r for r in self._doser(barn_id, lm["virkestoff"], tid - vindu, tid + vindu, unntatt)]
            for r in naer:
                rt = fra_iso(r["tid"])
                if rt <= tid:
                    adv.append(f"Forrige dose {lm['virkestoff']} var kl. {self.kl(rt)}. Minste intervall er "
                               f"{_fmt(bl['min_intervall_t'])} t, så neste er tidligst kl. {self.kl(rt + vindu)}.")
                else:
                    adv.append(f"Det er allerede registrert {lm['virkestoff']} kl. {self.kl(rt)}, "
                               f"mindre enn {_fmt(bl['min_intervall_t'])} t etter dette tidspunktet.")
                break
        if bl.get("maks_dogn_mg"):
            sum24 = sum(r["dose_mg"] for r in self._doser(barn_id, lm["virkestoff"], tid - timedelta(hours=24),
                                                             tid + timedelta(seconds=1), unntatt))
            if sum24 + mg > bl["maks_dogn_mg"] + 0.01:
                adv.append(f"Med denne dosen blir det {_fmt(round(sum24 + mg, 1))} mg {lm['virkestoff']} siste 24 t. "
                           f"Maks døgndose er satt til {_fmt(bl['maks_dogn_mg'])} mg.")
        return adv

    def registrer(self, d: dict, av: str | None = None, kilde: str = "app") -> dict:
        r = self._rens_registrering(d)
        if not self._har_innhold(r):
            raise Feil("Registrer temperatur, medisin, symptomer eller et notat")
        if r.get("legemiddel_id") and not d.get("bekreftet"):
            adv = self.kontroller_dose(r["barn_id"], r["legemiddel_id"], r["dose_mg"], fra_iso(r["tid"]))
            if adv:
                raise Advarsel(adv)
        r.update(kilde=kilde, av=av, status="ok")
        reg = self.db.ny_registrering(r)
        self.regn_episoder(reg["barn_id"])
        reg = self.db.registrering(reg["id"])
        self._endret("registrert", self.beskriv(reg))
        return reg

    def endre_registrering(self, rid: int, d: dict) -> dict:
        gammel = self.db.registrering(rid)
        if not gammel:
            raise Feil("Fant ikke registreringen")
        ny = self._rens_registrering(d, gammel)
        samlet = {**gammel, **ny}
        if not self._har_innhold(samlet):
            raise Feil("Registreringen kan ikke bli tom – slett den i stedet")
        if ny.get("legemiddel_id") and samlet.get("barn_id") and not d.get("bekreftet"):
            adv = self.kontroller_dose(samlet["barn_id"], samlet["legemiddel_id"], samlet["dose_mg"],
                                       fra_iso(samlet["tid"]), unntatt=rid)
            if adv:
                raise Advarsel(adv)
        if gammel["status"] == "sjekk" and d.get("godkjenn"):
            ny["status"] = "ok"
            ny["merknad"] = None
        reg = self.db.oppdater_registrering(rid, ny)
        for bid in {gammel["barn_id"], reg["barn_id"]} - {None}:
            self.regn_episoder(bid)
        self._endret("endret", self.beskriv(reg))
        return self.db.registrering(rid)

    def slett_registrering(self, rid: int) -> dict:
        gammel = self.db.registrering(rid)
        if not gammel or not self.db.slett_registrering(rid):
            raise Feil("Fant ikke registreringen")
        if gammel["barn_id"]:
            self.regn_episoder(gammel["barn_id"])
        self._endret("slettet", None)
        return gammel

    def gjenopprett(self, r: dict) -> dict:
        """Angre en sletting."""
        felt = {k: r.get(k) for k in ("barn_id", "tid", "temp", "temp_metode", "legemiddel_id", "dose_mg",
                                      "dose_ml", "symptomer", "notat", "status", "merknad", "kilde",
                                      "kilde_ref", "av")}
        reg = self.db.ny_registrering(felt)
        if reg["barn_id"]:
            self.regn_episoder(reg["barn_id"])
        self._endret("registrert", self.beskriv(reg))
        return reg

    # ------------------------------------------------------------ episoder
    def regn_episoder(self, barn_id: int) -> None:
        """Grupper barnets registreringer i sykdomsepisoder.

        Ny episode når det har gått mer enn «episode_pause_t» timer uten registrering,
        eller når forrige episode er avsluttet med «Frisk igjen». Navn og notater på
        eksisterende episoder beholdes.
        """
        regs = self.db.registreringer(barn_id=barn_id)
        gamle = {e["id"]: e for e in self.db.episoder(barn_id)}
        pause = timedelta(hours=self.inn["episode_pause_t"])
        grupper: list[list[dict]] = []
        for r in regs:
            if grupper:
                forrige = grupper[-1][-1]
                gap = fra_iso(r["tid"]) - fra_iso(forrige["tid"])
                avsl = gamle.get(forrige["episode_id"] or -1, {}).get("avsluttet")
                ny_ep = gap > pause or (avsl and r["episode_id"] != forrige["episode_id"])
                if not ny_ep:
                    grupper[-1].append(r)
                    continue
            grupper.append([r])

        brukt: set[int] = set()
        con = self.db.con
        for g in grupper:
            kandidater = {}
            for r in g:
                if r["episode_id"] in gamle and r["episode_id"] not in brukt:
                    kandidater[r["episode_id"]] = kandidater.get(r["episode_id"], 0) + 1
            start, slutt = g[0]["tid"], g[-1]["tid"]
            if kandidater:
                eid = max(kandidater, key=kandidater.get)
                con.execute("UPDATE episoder SET start = ?, slutt = ? WHERE id = ?", (start, slutt, eid))
            else:
                eid = con.execute("INSERT INTO episoder (barn_id, start, slutt) VALUES (?, ?, ?)",
                                  (barn_id, start, slutt)).lastrowid
            brukt.add(eid)
            ider = [r["id"] for r in g if r["episode_id"] != eid]
            if ider:
                con.execute(f"UPDATE registreringer SET episode_id = ? WHERE id IN ({', '.join('?' * len(ider))})",
                            (eid, *ider))
        for eid in set(gamle) - brukt:
            con.execute("DELETE FROM episoder WHERE id = ?", (eid,))
        con.commit()

    def lagre_episode(self, eid: int, d: dict) -> dict:
        e = self.db.episode(eid)
        if not e:
            raise Feil("Fant ikke episoden")
        sett = {}
        if "navn" in d:
            sett["navn"] = (str(d["navn"] or "").strip()[:60]) or None
        if "notat" in d:
            sett["notat"] = (str(d["notat"] or "").strip()[:2000]) or None
        if "avsluttet" in d:
            sett["avsluttet"] = 1 if d["avsluttet"] else 0
        if sett:
            self.db.con.execute(f"UPDATE episoder SET {', '.join(f'{k} = ?' for k in sett)} WHERE id = ?",
                                (*sett.values(), eid))
            self.db.commit()
        self._endret("episode", None)
        return self.db.episode(eid)

    def frisk(self, barn_id: int) -> None:
        ep = self.aktiv_episode(barn_id)
        if not ep:
            raise Feil("Ingen pågående sykdom å avslutte")
        self.lagre_episode(ep["id"], {"avsluttet": True})

    def aktiv_episode(self, barn_id: int) -> dict | None:
        eps = self.db.episoder(barn_id)
        if not eps:
            return None
        e = eps[0]
        if e["avsluttet"]:
            return None
        if naa() - fra_iso(e["slutt"]) > timedelta(hours=self.inn["syk_vindu_t"]):
            return None
        return e

    # ------------------------------------------------------------ beskrivelser
    def _lm_navn(self) -> dict[int, dict]:
        return {l["id"]: l for l in self.db.legemidler()}

    def beskriv(self, r: dict, lm: dict[int, dict] | None = None) -> dict:
        """Registrering beriket med tekster til visning."""
        lm = lm or self._lm_navn()
        deler = []
        if r.get("temp") is not None:
            deler.append(f"{_fmt(r['temp'])} °C")
        if r.get("legemiddel_id"):
            l = lm.get(r["legemiddel_id"], {})
            dose = f"{_fmt(r['dose_mg'])} mg"
            if r.get("dose_ml"):
                dose = f"{_fmt(r['dose_ml'])} ml ({dose})"
            deler.append(f"{l.get('navn', 'Legemiddel')} {dose}")
        if r.get("symptomer"):
            deler.append(", ".join(r["symptomer"]))
        tittel = " · ".join(deler) or "Notat"
        return {
            **r,
            "tittel": tittel,
            "kl": self.kl(r["tid"]),
            "feber": r.get("temp") is not None and r["temp"] >= self.inn["feber_grense"],
            "legemiddel": lm.get(r.get("legemiddel_id") or -1, {}).get("navn"),
            "metode_navn": METODE_NAVN.get(r.get("temp_metode") or "", ""),
        }

    # ------------------------------------------------------------ doser
    def dosestatus(self, barn_id: int) -> list[dict]:
        t = naa()
        i_dag = self.dag_start(self.i_dag())
        ut = []
        regs = self.db.registreringer(barn_id=barn_id, fra=t - timedelta(days=60))
        lm = self._lm_navn()
        for bl in self.db.barn_legemidler(barn_id):
            if not bl["aktiv"] or bl["arkivert"]:
                continue
            samme = {l["id"] for l in lm.values() if l["virkestoff"].lower() == bl["virkestoff"].lower()}
            doser = [r for r in regs if r["legemiddel_id"] in samme and r["dose_mg"]]
            egne = [r for r in doser if r["legemiddel_id"] == bl["legemiddel_id"]]
            siste = doser[-1] if doser else None
            sum24 = sum(r["dose_mg"] for r in doser if fra_iso(r["tid"]) > t - timedelta(hours=24))
            idag = sum(r["dose_mg"] for r in doser if fra_iso(r["tid"]) >= i_dag)
            antall_idag = sum(1 for r in egne if fra_iso(r["tid"]) >= i_dag)
            neste = None
            if siste and bl["min_intervall_t"]:
                n = fra_iso(siste["tid"]) + timedelta(hours=bl["min_intervall_t"])
                if n > t:
                    neste = til_iso(n)
            kur = None
            if bl["kur_doser_dag"]:
                aktiv_kur = not bl["kur_til"] or date.fromisoformat(bl["kur_til"]) >= self.i_dag()
                if aktiv_kur:
                    kur = {"doser_dag": bl["kur_doser_dag"], "gitt_i_dag": antall_idag, "til": bl["kur_til"],
                           "dager_igjen": (date.fromisoformat(bl["kur_til"]) - self.i_dag()).days if bl["kur_til"] else None}
            ut.append({
                "legemiddel_id": bl["legemiddel_id"], "navn": bl["navn"], "virkestoff": bl["virkestoff"],
                "form": bl["form"], "mg_per_ml": bl["mg_per_ml"], "standard_mg": bl["standard_mg"],
                "min_intervall_t": bl["min_intervall_t"], "maks_dogn_mg": bl["maks_dogn_mg"],
                "siste": {"tid": siste["tid"], "mg": siste["dose_mg"], "kl": self.kl(siste["tid"]),
                          "legemiddel": lm.get(siste["legemiddel_id"], {}).get("navn")} if siste else None,
                "sum_24t": round(sum24, 2), "sum_i_dag": round(idag, 2),
                "neste_tidligst": neste, "neste_kl": self.kl(neste) if neste else None,
                "kur": kur,
            })
        return ut

    # ------------------------------------------------------------ status
    def status_barn(self, b: dict) -> dict:
        lm = self._lm_navn()
        ep = self.aktiv_episode(b["id"])
        t = naa()
        siste_temp = None
        for r in reversed(self.db.registreringer(barn_id=b["id"], fra=t - timedelta(days=14))):
            if r["temp"] is not None:
                siste_temp = r
                break
        ep_regs = self.db.registreringer(episode_id=ep["id"]) if ep else []
        symptomer = []
        for r in ep_regs:
            if fra_iso(r["tid"]) > t - timedelta(hours=24):
                symptomer.extend(r["symptomer"])
        alder = self.alder(b)
        feber = bool(siste_temp and siste_temp["temp"] >= self.inn["feber_grense"])
        merknad = None
        if feber and alder and alder["maaneder"] is not None and alder["maaneder"] < 3 \
                and fra_iso(siste_temp["tid"]) > t - timedelta(hours=24):
            merknad = {"tekst": "Helsenorge anbefaler å kontakte lege ved feber hos barn under 3 måneder.",
                       "lenke": HELSENORGE_FEBER}
        siste = ep_regs[-1] if ep_regs else None
        return {
            "barn": b,
            "alder": alder,
            "syk": bool(ep),
            "episode": {
                **ep,
                "dag": (self.i_dag() - self.lokal(fra_iso(ep["start"])).date()).days + 1,
                "maks_temp": max((r["temp"] for r in ep_regs if r["temp"] is not None), default=None),
            } if ep else None,
            "siste_temp": {"temp": siste_temp["temp"], "tid": siste_temp["tid"], "kl": self.kl(siste_temp["tid"]),
                           "metode": METODE_NAVN.get(siste_temp["temp_metode"] or "", ""), "feber": feber} if siste_temp else None,
            "symptomer": list(dict.fromkeys(symptomer)),
            "doser": self.dosestatus(b["id"]),
            "siste": self.beskriv(siste, lm) if siste else None,
            "merknad": merknad,
            "i_dag": [self.beskriv(r, lm) for r in self.db.registreringer(barn_id=b["id"], fra=t - timedelta(hours=36))][::-1],
        }

    def oversikt(self) -> dict:
        return {
            "barn": [self.status_barn(b) for b in self.db.barn() if b["aktiv"]],
            "innstillinger": self.inn,
            "legemidler": self.db.legemidler(),
            "alle_barn": self.db.barn(),
            "gjennomgang": self.db.antall_status(),
            "antall_barn": len(self.db.barn()),
        }

    # ------------------------------------------------------------ historikk
    def episode_sammendrag(self, e: dict, lm: dict[int, dict] | None = None) -> dict:
        lm = lm or self._lm_navn()
        regs = self.db.registreringer(episode_id=e["id"])
        temps = [r["temp"] for r in regs if r["temp"] is not None]
        doser: dict[str, dict] = {}
        symp: dict[str, int] = {}
        for r in regs:
            if r["legemiddel_id"]:
                n = lm.get(r["legemiddel_id"], {}).get("navn", "?")
                d = doser.setdefault(n, {"navn": n, "antall": 0, "mg": 0.0})
                d["antall"] += 1
                d["mg"] = round(d["mg"] + (r["dose_mg"] or 0), 2)
            for s in r["symptomer"]:
                symp[s] = symp.get(s, 0) + 1
        start, slutt = self.lokal(fra_iso(e["start"])), self.lokal(fra_iso(e["slutt"]))
        return {
            **e,
            "start_dato": start.date().isoformat(), "slutt_dato": slutt.date().isoformat(),
            "dager": (slutt.date() - start.date()).days + 1,
            "antall": len(regs),
            "maks_temp": max(temps, default=None),
            "feberdager": len({self.lokal(fra_iso(r["tid"])).date() for r in regs
                               if r["temp"] is not None and r["temp"] >= self.inn["feber_grense"]}),
            "doser": sorted(doser.values(), key=lambda x: -x["antall"]),
            "symptomer": [s for s, _ in sorted(symp.items(), key=lambda x: -x[1])],
            "pagar": bool(self.aktiv_episode(e["barn_id"]) and self.aktiv_episode(e["barn_id"])["id"] == e["id"]),
            "usikker": sum(1 for r in regs if r["status"] in ("antatt", "sjekk")),
        }

    def historikk(self, barn_id: int | None = None, aar: int | None = None) -> dict:
        lm = self._lm_navn()
        eps = []
        for e in self.db.episoder(barn_id):
            s = self.episode_sammendrag(e, lm)
            if aar and int(s["start_dato"][:4]) != aar:
                continue
            eps.append(s)
        alle_aar = sorted({int(e["start"][:4]) for e in self.db.episoder(barn_id)}, reverse=True)
        return {"episoder": eps, "aar": alle_aar}

    def episode_detalj(self, eid: int) -> dict:
        e = self.db.episode(eid)
        if not e:
            raise Feil("Fant ikke episoden")
        lm = self._lm_navn()
        regs = [self.beskriv(r, lm) for r in self.db.registreringer(episode_id=eid)]
        return {"episode": self.episode_sammendrag(e, lm), "barn": self.db.ett_barn(e["barn_id"]),
                "registreringer": regs, "feber_grense": self.inn["feber_grense"]}

    # ------------------------------------------------------------ gjennomgang
    def gjennomgang(self) -> dict:
        lm = self._lm_navn()
        ukjente = self.db.registreringer(ukjent=True)
        pause = timedelta(hours=self.inn["episode_pause_t"])
        grupper: list[list[dict]] = []
        for r in ukjente:
            if grupper and fra_iso(r["tid"]) - fra_iso(grupper[-1][-1]["tid"]) <= pause:
                grupper[-1].append(r)
            else:
                grupper.append([r])
        ut_grupper = []
        for g in grupper:
            doser: dict[str, list] = {}
            for r in g:
                if r["legemiddel_id"]:
                    doser.setdefault(lm.get(r["legemiddel_id"], {}).get("navn", "?"), []).append(r["dose_mg"])
            ut_grupper.append({
                "ider": [r["id"] for r in g],
                "fra": g[0]["tid"], "til": g[-1]["tid"],
                "doser": [{"navn": n, "antall": len(v), "mg": sorted(set(v))} for n, v in doser.items()],
                "temp_maks": max((r["temp"] for r in g if r["temp"] is not None), default=None),
                "notater": [r["notat"] for r in g if r["notat"]][:4],
                "registreringer": [self.beskriv(r, lm) for r in g],
            })
        sjekk = [self.beskriv(r, lm) for r in self.db.registreringer(status=("sjekk",)) if r["barn_id"]]
        return {"ukjente": ut_grupper, "sjekk": sjekk}

    def tildel(self, ider: list[int], barn_id: int | None) -> int:
        if barn_id is None:
            return self.db.slett_registreringer(ider)
        if not self.db.ett_barn(barn_id):
            raise Feil("Fant ikke barnet")
        for rid in ider:
            r = self.db.registrering(rid)
            if r and r["barn_id"] is None:
                status = "sjekk" if r["merknad"] else "ok"
                self.db.oppdater_registrering(rid, {"barn_id": barn_id, "status": status}, commit=False)
        self.db.commit()
        self.regn_episoder(barn_id)
        self._endret("tildelt")
        return len(ider)

    # ------------------------------------------------------------ import
    def importer(self, rader: list) -> dict:
        """Skriv en importplan (fra importer.planlegg) til databasen."""
        eksisterende = self.db.kilde_refs()
        lm_ider: dict[str, int] = {}
        nye_lm = []
        for navn in sorted({r.legemiddel for r in rader if r.legemiddel}):
            lm = self.db.finn_legemiddel(navn)
            if not lm:
                lm = self.db.lagre_legemiddel({"navn": navn, "virkestoff": navn, "form": "annet"})
                nye_lm.append(navn)
            lm_ider[navn.lower()] = lm["id"]
        antall = 0
        for r in rader:
            k = r.nokkel()
            if k in eksisterende:
                continue
            self.db.ny_registrering({
                "barn_id": r.barn_id, "tid": r.tid, "temp": r.temp, "temp_metode": r.temp_metode,
                "legemiddel_id": lm_ider.get((r.legemiddel or "").lower()), "dose_mg": r.dose_mg,
                "notat": r.notat, "status": r.status, "merknad": r.merknad,
                "kilde": "import", "kilde_ref": k, "av": "Import",
            }, commit=False)
            eksisterende.add(k)
            antall += 1
        self.db.commit()
        for bid in {r.barn_id for r in rader} - {None}:
            self.regn_episoder(bid)
            # Aktiver importerte legemidler for barnet, så de dukker opp i historikken og innstillingene
            for navn in {r.legemiddel for r in rader if r.barn_id == bid and r.legemiddel}:
                lid = lm_ider[navn.lower()]
                if not self.db.barn_legemiddel(bid, lid):
                    self.db.lagre_barn_legemiddel(bid, lid, {"aktiv": 0})
        self._endret("import")
        return {"importert": antall, "nye_legemidler": nye_lm}

    # ------------------------------------------------------------ eksport
    def csv(self) -> str:
        lm = self._lm_navn()
        barn = {b["id"]: b["navn"] for b in self.db.barn()}
        linjer = ["tid;barn;temperatur;metode;legemiddel;dose_mg;dose_ml;symptomer;notat;status;kilde"]
        for r in self.db.registreringer():
            lok = self.lokal(fra_iso(r["tid"])).strftime("%Y-%m-%d %H:%M")
            felt = [lok, barn.get(r["barn_id"], "ukjent"), _fmt(r["temp"]), METODE_NAVN.get(r["temp_metode"] or "", ""),
                    lm.get(r["legemiddel_id"] or -1, {}).get("navn", ""), _fmt(r["dose_mg"]), _fmt(r["dose_ml"]),
                    ", ".join(r["symptomer"]), (r["notat"] or "").replace(";", ",").replace("\n", " "),
                    r["status"], r["kilde"]]
            linjer.append(";".join(felt))
        return "\n".join(linjer)

    # ------------------------------------------------------------ Home Assistant
    def sensor_navn(self, b: dict) -> str:
        return f"sensor.plasterboka_{slug(b['navn'])}"

    def sensorer(self) -> dict[str, dict]:
        ut = {}
        syke = []
        for b in self.db.barn():
            if not b["aktiv"]:
                continue
            st = self.status_barn(b)
            doser = {}
            neste = {}
            for d in st["doser"]:
                doser[d["virkestoff"]] = {
                    "siste_kl": d["siste"]["kl"] if d["siste"] else None,
                    "siste_tid": d["siste"]["tid"] if d["siste"] else None,
                    "siste_mg": d["siste"]["mg"] if d["siste"] else None,
                    "sum_24t_mg": d["sum_24t"], "maks_dogn_mg": d["maks_dogn_mg"],
                    "neste_tidligst": d["neste_tidligst"],
                }
                if d["neste_kl"]:
                    neste[d["navn"]] = d["neste_kl"]
            tekst = self.skjermtekst(st)
            if st["syk"]:
                syke.append(tekst)
            ut[self.sensor_navn(b)] = {
                "state": "syk" if st["syk"] else "frisk",
                "attributes": {
                    "friendly_name": f"Plasterboka {b['navn']}",
                    "icon": "mdi:thermometer-alert" if st["syk"] else "mdi:emoticon-happy-outline",
                    "barn": b["navn"],
                    "siste_temperatur": st["siste_temp"]["temp"] if st["siste_temp"] else None,
                    "siste_temperatur_tid": st["siste_temp"]["tid"] if st["siste_temp"] else None,
                    "feber": st["siste_temp"]["feber"] if st["siste_temp"] else False,
                    "symptomer": st["symptomer"],
                    "doser": doser,
                    "neste_dose": neste,
                    "episode_start": st["episode"]["start"] if st["episode"] else None,
                    "episode_dag": st["episode"]["dag"] if st["episode"] else None,
                    "episode_navn": st["episode"]["navn"] if st["episode"] else None,
                    "tekst": tekst,
                },
            }
        ut["sensor.plasterboka_skjermtekst"] = {
            "state": (" · ".join(syke))[:250] if syke else "Alle friske",
            "attributes": {"friendly_name": "Plasterboka skjermtekst", "icon": "mdi:bandage",
                           "antall_syke": len(syke)},
        }
        return ut

    def skjermtekst(self, st: dict) -> str:
        navn = st["barn"]["navn"]
        if not st["syk"]:
            return f"{navn}: frisk"
        deler = [navn]
        if st["siste_temp"]:
            deler.append(f"{_fmt(st['siste_temp']['temp'])} °C kl. {st['siste_temp']['kl']}")
        for d in st["doser"]:
            if d["siste"] and fra_iso(d["siste"]["tid"]) > naa() - timedelta(hours=24):
                s = f"{d['navn']} kl. {d['siste']['kl']}"
                if d["neste_kl"]:
                    s += f" (neste {d['neste_kl']})"
                deler.append(s)
        return ": ".join([deler[0], ", ".join(deler[1:]) or "syk"])
