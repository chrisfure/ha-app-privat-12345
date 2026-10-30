"""Kjernelogikken i Babyuret: handlinger, oppsummeringer og sensorverdier."""
from __future__ import annotations

from datetime import date, datetime, time, timedelta
from typing import Callable
from zoneinfo import ZoneInfo

from db import UTC, Database, fra_iso, naa, til_iso
from innstillinger import Innstillinger
from prognose import Prognose

# Amming-økter med mindre pause enn dette regnes som ett måltid.
MALTID_PAUSE = timedelta(minutes=20)

ANDRE_SIDE = {"V": "H", "H": "V"}


class Feil(Exception):
    """Feil som skal vises til brukeren."""


def _tid(data: dict) -> datetime:
    """Tidspunkt fra en handling: «tid» (ISO) eller «minutter_siden», ellers nå."""
    if data.get("tid"):
        return fra_iso(str(data["tid"]))
    if data.get("minutter_siden") not in (None, ""):
        return naa() - timedelta(minutes=int(data["minutter_siden"]))
    return naa()


def varighet_tekst(sek: float) -> str:
    m = int(sek // 60)
    t, m = divmod(m, 60)
    if t and m:
        return f"{t} t {m} min"
    if t:
        return f"{t} t"
    return f"{m} min"


class Babyuret:
    def __init__(self, db: Database, cfg: Innstillinger, tz: str = "UTC"):
        self.db = db
        self.cfg = cfg
        self.tz = ZoneInfo(tz)
        self._lyttere: list[Callable[[str, dict | None], None]] = []
        self.prognose = Prognose(self)
        try:
            self.cfg.oppdater(self.db.les_innstillinger())
        except ValueError:
            pass

    def lagre_innstillinger(self, d: dict) -> dict:
        try:
            self.cfg.oppdater(d)
        except ValueError as e:
            raise Feil(str(e))
        self.db.lagre_innstillinger(self.cfg.til_lagring())
        self._endret("innstillinger", None)
        return self.cfg.offentlig()

    def sett_tidssone(self, tz: str) -> None:
        try:
            self.tz = ZoneInfo(tz)
        except Exception:  # noqa: BLE001 – ukjent sone, behold gammel
            pass

    # ---- lyttere (HA-publisering) ---------------------------------------
    def ved_endring(self, fn: Callable[[str, dict | None], None]) -> None:
        self._lyttere.append(fn)

    def _endret(self, hva: str, hendelse: dict | None) -> None:
        for fn in self._lyttere:
            try:
                fn(hva, hendelse)
            except Exception:  # noqa: BLE001
                pass

    # ---- handlinger -----------------------------------------------------
    def handling(self, navn: str, data: dict | None = None, av: str | None = None) -> dict:
        data = data or {}
        navn = (navn or "").strip().lower()
        tid = _tid(data)
        fn = {
            "sovn_start": self._sovn_start,
            "sovn_slutt": self._sovn_slutt,
            "sovn_veksle": self._sovn_veksle,
            "amming_start": self._amming_start,
            "amming_bytt": self._amming_bytt,
            "amming_slutt": self._amming_slutt,
            "flaske": self._flaske,
            "tiss": lambda t, d, a: self._bleie(t, a, tiss=True, baesj=False),
            "baesj": lambda t, d, a: self._bleie(t, a, tiss=False, baesj=True),
            "begge": lambda t, d, a: self._bleie(t, a, tiss=True, baesj=True),
        }.get(navn)
        if fn is None:
            raise Feil(f"Ukjent handling: {navn}")
        hendelse, melding = fn(tid, data, av)
        self._endret(navn, hendelse)
        return {"hendelse": hendelse, "melding": melding}

    def _sovn_start(self, tid, data, av):
        pag = self.db.pagaende("sovn")
        if pag:
            return pag, "Sover allerede"
        h = self.db.opprett("sovn", tid, None, {}, av)
        return h, f"Sovnet {self._kl(tid)}"

    def _sovn_slutt(self, tid, data, av):
        pag = self.db.pagaende("sovn")
        if not pag:
            raise Feil("Ingen pågående søvn")
        start = fra_iso(pag["start"])
        if tid < start:
            tid = start
        h = self.db.oppdater(pag["id"], slutt=tid)
        return h, f"Våknet etter {varighet_tekst((tid - start).total_seconds())}"

    def _sovn_veksle(self, tid, data, av):
        if self.db.pagaende("sovn"):
            return self._sovn_slutt(tid, data, av)
        return self._sovn_start(tid, data, av)

    def _amming_pagaende(self) -> dict | None:
        pag = self.db.pagaende("mat")
        if pag and pag["detaljer"].get("type") == "amming":
            return pag
        return None

    def _amming_start(self, tid, data, av):
        side = str(data.get("side") or "").upper()[:1]
        if side not in ("V", "H"):
            side = self.neste_side()
        pag = self._amming_pagaende()
        if pag:
            if pag["detaljer"].get("side") == side:
                return pag, "Ammer allerede"
            self.db.oppdater(pag["id"], slutt=max(tid, fra_iso(pag["start"])))
        h = self.db.opprett("mat", tid, None, {"type": "amming", "side": side}, av)
        return h, f"Ammer {'venstre' if side == 'V' else 'høyre'} side"

    def _amming_bytt(self, tid, data, av):
        pag = self._amming_pagaende()
        if not pag:
            raise Feil("Ingen pågående amming")
        ny = ANDRE_SIDE.get(pag["detaljer"].get("side", "V"), "H")
        return self._amming_start(tid, {"side": ny}, av)

    def _amming_slutt(self, tid, data, av):
        pag = self._amming_pagaende()
        if not pag:
            raise Feil("Ingen pågående amming")
        start = fra_iso(pag["start"])
        h = self.db.oppdater(pag["id"], slutt=max(tid, start))
        return h, f"Amming ferdig ({varighet_tekst((max(tid, start) - start).total_seconds())})"

    def _flaske(self, tid, data, av):
        try:
            ml = int(data.get("ml") or self.cfg.standard_flaske_ml)
        except (TypeError, ValueError):
            raise Feil("Ugyldig mengde")
        if not 0 < ml <= 500:
            raise Feil("Mengden må være mellom 1 og 500 ml")
        h = self.db.opprett("mat", tid, tid, {"type": "flaske", "ml": ml}, av)
        return h, f"Flaske {ml} ml registrert"

    def _bleie(self, tid, av, tiss: bool, baesj: bool):
        h = self.db.opprett("bleie", tid, tid, {"tiss": tiss, "baesj": baesj}, av)
        hva = "Tiss og bæsj" if tiss and baesj else ("Tiss" if tiss else "Bæsj")
        return h, f"{hva} registrert {self._kl(tid)}"

    # ---- manuell redigering --------------------------------------------
    def legg_til(self, kategori: str, start: str, slutt: str | None,
                 detaljer: dict | None, av: str | None) -> dict:
        s = fra_iso(start)
        e = fra_iso(slutt) if slutt else None
        punkt = kategori == "bleie" or (kategori == "mat" and (detaljer or {}).get("type") == "flaske")
        if punkt:
            e = s
        if e and e < s:
            raise Feil("Slutt kan ikke være før start")
        h = self.db.opprett(kategori, s, e, self._rens(kategori, detaljer), av)
        self._endret("legg_til", h)
        return h

    def endre(self, hid: int, felt: dict) -> dict:
        gammel = self.db.hent(hid)
        if not gammel:
            raise Feil("Fant ikke registreringen")
        detaljer = felt.get("detaljer", gammel["detaljer"])
        detaljer = self._rens(gammel["kategori"], detaljer)
        start = fra_iso(felt["start"]) if felt.get("start") else fra_iso(gammel["start"])
        if "slutt" in felt:
            slutt = fra_iso(felt["slutt"]) if felt["slutt"] else None
        else:
            slutt = fra_iso(gammel["slutt"]) if gammel["slutt"] else None
        punkt = gammel["kategori"] == "bleie" or detaljer.get("type") == "flaske"
        if punkt:
            slutt = start
        if slutt and slutt < start:
            raise Feil("Slutt kan ikke være før start")
        if start > naa() + timedelta(minutes=1):
            raise Feil("Starttid kan ikke være i fremtiden")
        h = self.db.oppdater(hid, start=start, slutt=slutt, detaljer=detaljer)
        self._endret("endre", h)
        return h

    def slett(self, hid: int) -> None:
        if not self.db.slett(hid):
            raise Feil("Fant ikke registreringen")
        self._endret("slett", None)

    @staticmethod
    def _rens(kategori: str, d: dict | None) -> dict:
        d = dict(d or {})
        if kategori == "bleie":
            return {"tiss": bool(d.get("tiss")), "baesj": bool(d.get("baesj"))}
        if kategori == "mat":
            if d.get("type") == "flaske":
                try:
                    ml = max(1, min(500, int(d.get("ml") or 0)))
                except (TypeError, ValueError):
                    ml = 0
                return {"type": "flaske", "ml": ml}
            side = str(d.get("side") or "V").upper()[:1]
            return {"type": "amming", "side": side if side in ("V", "H") else "V"}
        return {}

    # ---- avledet info ---------------------------------------------------
    def _kl(self, dt: datetime) -> str:
        return dt.astimezone(self.tz).strftime("%H:%M")

    def neste_side(self) -> str:
        siste = self.db.siste("mat", "AND json_extract(detaljer, '$.type') = 'amming'")
        if not siste:
            return "V"
        return ANDRE_SIDE.get(siste["detaljer"].get("side", "H"), "V")

    def alder(self) -> dict | None:
        f = self.cfg.fodselsdato
        if not f:
            return None
        i_dag = datetime.now(self.tz).date()
        dager = (i_dag - f).days
        if dager < 0:
            igjen = -dager
            if igjen <= 14:
                return {"dager": dager, "tekst": f"{igjen} {'dag' if igjen == 1 else 'dager'} til termin"}
            u, d = divmod(igjen, 7)
            return {"dager": dager, "tekst": f"{u} uker{f' og {d} d' if d else ''} til termin"}
        uker, rest = divmod(dager, 7)
        if dager < 7:
            tekst = f"{dager} {'dag' if dager == 1 else 'dager'}"
        elif uker < 13:
            tekst = f"{uker} {'uke' if uker == 1 else 'uker'}" + (f" og {rest} d" if rest else "")
        else:
            mnd = (i_dag.year - f.year) * 12 + i_dag.month - f.month - (1 if i_dag.day < f.day else 0)
            tekst = f"{mnd} måneder"
        return {"dager": dager, "tekst": tekst}

    def dag_grenser(self, dag: date) -> tuple[datetime, datetime]:
        start = datetime.combine(dag, time.min, tzinfo=self.tz)
        slutt = datetime.combine(dag + timedelta(days=1), time.min, tzinfo=self.tz)
        return start.astimezone(UTC), slutt.astimezone(UTC)

    def i_dag(self) -> date:
        return datetime.now(self.tz).date()

    def oppsummering(self, dag: date | None = None) -> dict:
        dag = dag or self.i_dag()
        fra, til = self.dag_grenser(dag)
        nå = naa()
        hendelser = self.db.i_tidsrom(fra, til)

        sovn_sek, lurer = 0.0, 0
        amming_sek = {"V": 0.0, "H": 0.0}
        ml, flasker = 0, 0
        tiss = baesj = bleier = 0
        mat_tider: list[tuple[datetime, datetime]] = []

        for h in hendelser:
            s = fra_iso(h["start"])
            e = fra_iso(h["slutt"]) if h["slutt"] else nå
            ks, ke = max(s, fra), min(e, til, nå)
            if h["kategori"] == "sovn":
                if ke > ks:
                    sovn_sek += (ke - ks).total_seconds()
                if s >= fra:
                    lurer += 1
            elif h["kategori"] == "mat" and s >= fra:
                d = h["detaljer"]
                if d.get("type") == "flaske":
                    ml += int(d.get("ml") or 0)
                    flasker += 1
                else:
                    side = d.get("side", "V")
                    amming_sek[side] = amming_sek.get(side, 0) + max(0.0, (min(e, nå) - s).total_seconds())
                mat_tider.append((s, e))
            elif h["kategori"] == "bleie" and s >= fra:
                bleier += 1
                tiss += 1 if h["detaljer"].get("tiss") else 0
                baesj += 1 if h["detaljer"].get("baesj") else 0

        # slå sammen nære mat-økter til måltider
        maltider = 0
        siste_slutt: datetime | None = None
        for s, e in sorted(mat_tider):
            if siste_slutt is None or s - siste_slutt > MALTID_PAUSE:
                maltider += 1
            siste_slutt = max(e, siste_slutt or e)

        return {
            "dag": dag.isoformat(),
            "sovn_sek": int(sovn_sek),
            "lurer": lurer,
            "maltider": maltider,
            "amming_sek": {k: int(v) for k, v in amming_sek.items()},
            "flasker": flasker,
            "ml": ml,
            "tiss": tiss,
            "baesj": baesj,
            "bleier": bleier,
            "hendelser": hendelser,
        }

    def status(self) -> dict:
        nå = naa()
        sovn = self.db.pagaende("sovn")
        amming = self._amming_pagaende()
        siste_sovn = self.db.siste("sovn", "AND slutt IS NOT NULL")
        siste_mat = self.db.siste("mat")
        siste_tiss = self.db.siste("bleie", "AND json_extract(detaljer, '$.tiss') = 1")
        siste_baesj = self.db.siste("bleie", "AND json_extract(detaljer, '$.baesj') = 1")

        if sovn:
            tilstand, siden = "sover", sovn["start"]
        elif siste_sovn:
            tilstand, siden = "vaaken", siste_sovn["slutt"]
        else:
            tilstand, siden = "vaaken", None

        return {
            "naa": til_iso(nå),
            "tilstand": tilstand,
            "siden": siden,
            "sovn": sovn,
            "amming": amming,
            "siste": {
                "sovn": siste_sovn,
                "mat": siste_mat,
                "tiss": siste_tiss,
                "baesj": siste_baesj,
            },
            "neste_side": self.neste_side(),
        }

    # ---- sensorer til Home Assistant -----------------------------------
    def sensorer(self) -> dict[str, dict]:
        st = self.status()
        dag = self.oppsummering()
        nå = naa()
        siste_mat = st["siste"]["mat"]
        siden_sek = (nå - fra_iso(st["siden"])).total_seconds() if st["siden"] else None

        if st["amming"]:
            tilstand = "ammer"
        else:
            tilstand = "sover" if st["tilstand"] == "sover" else "våken"

        mat_attr: dict = {"friendly_name": "Babyuret sist matet", "icon": "mdi:baby-bottle-outline",
                          "device_class": "timestamp"}
        if siste_mat:
            d = siste_mat["detaljer"]
            mat_attr["type"] = d.get("type")
            if d.get("type") == "amming":
                mat_attr["side"] = d.get("side")
            else:
                mat_attr["ml"] = d.get("ml")
            mat_attr["neste_side"] = st["neste_side"]

        prog = self.prognose.beregn()
        prog_attr = {"friendly_name": "Babyuret prognose", "icon": "mdi:crystal-ball",
                     "device_class": "timestamp", "type": prog["type"]}
        if prog.get("klar"):
            prog_attr.update({"fra": prog["fra"], "til": prog["til"], "sikkerhet": prog.get("sikkerhet"),
                              "varighet_min": prog.get("varighet_min")})
        self._siste_prognose = prog

        return {
            "sensor.babyuret_prognose": {
                "state": prog["midt"] if prog.get("klar") else "unknown",
                "attributes": prog_attr,
            },
            "sensor.babyuret_status": {
                "state": tilstand,
                "attributes": {
                    "friendly_name": "Babyuret status",
                    "icon": {"sover": "mdi:sleep", "ammer": "mdi:mother-nurse"}.get(tilstand, "mdi:baby-face-outline"),
                    "siden": st["siden"],
                    "varighet_min": int(siden_sek // 60) if siden_sek is not None else None,
                },
            },
            "sensor.babyuret_sist_matet": {
                "state": siste_mat["start"] if siste_mat else "unknown",
                "attributes": mat_attr,
            },
            "sensor.babyuret_sovn_i_dag": {
                "state": round(dag["sovn_sek"] / 3600, 1),
                "attributes": {"friendly_name": "Babyuret søvn i dag", "unit_of_measurement": "h",
                               "icon": "mdi:power-sleep", "lurer": dag["lurer"]},
            },
            "sensor.babyuret_maltider_i_dag": {
                "state": dag["maltider"],
                "attributes": {"friendly_name": "Babyuret måltider i dag", "icon": "mdi:food-apple-outline",
                               "ml": dag["ml"], "flasker": dag["flasker"],
                               "amming_min_venstre": dag["amming_sek"].get("V", 0) // 60,
                               "amming_min_hoyre": dag["amming_sek"].get("H", 0) // 60},
            },
            "sensor.babyuret_bleier_i_dag": {
                "state": dag["bleier"],
                "attributes": {"friendly_name": "Babyuret bleier i dag", "icon": "mdi:water-outline",
                               "tiss": dag["tiss"], "baesj": dag["baesj"]},
            },
            "sensor.babyuret_skjermtekst": {
                "state": self.skjermtekst(st, tilstand, siden_sek),
                "attributes": {"friendly_name": "Babyuret skjermtekst", "icon": "mdi:monitor"},
            },
        }

    def skjermtekst(self, st: dict, tilstand: str, siden_sek: float | None) -> str:
        deler = []
        if tilstand == "ammer":
            side = "venstre" if st["amming"]["detaljer"].get("side") == "V" else "høyre"
            deler.append(f"🤱 Ammer ({side})")
        elif tilstand == "sover":
            deler.append(f"😴 Sover · {varighet_tekst(siden_sek or 0)}")
        elif siden_sek is not None:
            deler.append(f"👶 Våken · {varighet_tekst(siden_sek)}")
        else:
            deler.append("👶 Våken")
        m = st["siste"]["mat"]
        if m and tilstand != "ammer":
            kl = self._kl(fra_iso(m["start"]))
            d = m["detaljer"]
            ekstra = d.get("side") if d.get("type") == "amming" else f"{d.get('ml')} ml"
            deler.append(f"Sist matet {kl} ({ekstra})")
        prog = getattr(self, "_siste_prognose", None)
        if prog and prog.get("klar") and not prog.get("forbi"):
            f, t = self._kl(fra_iso(prog["fra"])), self._kl(fra_iso(prog["til"]))
            hva = "Våkner ca." if prog["type"] == "vaakner" else "Neste lur ca."
            deler.append(f"{hva} {f}–{t}")
        return " · ".join(deler)
