"""Lokal søvnprognose.

Ingen sky og ingen AI – bare babyens egne registreringer:

* Våkenperioder (tid fra babyen våknet til den sovnet igjen) og
  søvnlengder fra de siste 7 dagene.
* Nyere data teller mer (halveringstid 2 døgn).
* Dag og natt beregnes hver for seg (nattmodus-tidsrommet fra innstillingene).
* Resultatet er et tidsvindu (25.–75. persentil), ikke et eksakt klokkeslett.

Før det finnes nok egne data, brukes Helsenorges beskrivelse av nyfødte
(våkenperioder ofte 30–60 min) som startestimat de første tre månedene.
Etter hvert som dataene øker, overtar babyens eget mønster.
"""
from __future__ import annotations

from datetime import datetime, timedelta

import referanser as ref
from db import UTC, fra_iso, naa, til_iso

DAGER_BAKOVER = 7
HALVERING_TIMER = 48
MIN_EGNE = 3        # minst så mange observasjoner før egne data brukes
PRIOR_VEKT = 4      # hvor mange observasjoner startestimatet «er verdt»


def _vektet_kvantil(verdier: list[float], vekter: list[float], q: float) -> float:
    par = sorted(zip(verdier, vekter))
    tot = sum(v for _, v in par)
    acc = 0.0
    for x, w in par:
        acc += w
        if acc >= q * tot:
            return x
    return par[-1][0]


def _minutter(hhmm: str) -> int:
    h, m = hhmm.split(":")
    return int(h) * 60 + int(m)


class Prognose:
    def __init__(self, bu):
        self.bu = bu

    def _er_natt(self, dt: datetime) -> bool:
        lokal = dt.astimezone(self.bu.tz)
        n = lokal.hour * 60 + lokal.minute
        fra, til = _minutter(self.bu.cfg.nattmodus_fra), _minutter(self.bu.cfg.nattmodus_til)
        return n >= fra or n < til if fra > til else fra <= n < til

    def _data(self):
        nå = naa()
        sovn = [h for h in self.bu.db.i_tidsrom(nå - timedelta(days=DAGER_BAKOVER), nå)
                if h["kategori"] == "sovn" and h["slutt"]]
        sovn.sort(key=lambda h: h["start"])
        vaaken, varighet = [], []  # (minutter, vekt, natt?)
        for i, h in enumerate(sovn):
            s, e = fra_iso(h["start"]), fra_iso(h["slutt"])
            w = 0.5 ** ((nå - e).total_seconds() / 3600 / HALVERING_TIMER)
            d = (e - s).total_seconds() / 60
            if 5 <= d <= 14 * 60:
                varighet.append((d, w, self._er_natt(s)))
            if i + 1 < len(sovn):
                gap = (fra_iso(sovn[i + 1]["start"]) - e).total_seconds() / 60
                if 5 <= gap <= 6 * 60:  # lengre hull = sannsynligvis glemt å registrere
                    vaaken.append((gap, w, self._er_natt(e)))
        return vaaken, varighet

    @staticmethod
    def _velg(obs, natt: bool):
        egne = [o for o in obs if o[2] == natt]
        return egne if len(egne) >= MIN_EGNE else obs

    def _estimat(self, obs, prior: tuple[int, int] | None):
        """Returnerer (lav, midt, høy, antall_egne) i minutter, eller None."""
        n = len(obs)
        if n >= MIN_EGNE:
            v, w = [o[0] for o in obs], [o[1] for o in obs]
            lav, midt, hoy = (_vektet_kvantil(v, w, q) for q in (0.25, 0.5, 0.75))
            if prior and n < 15:
                k = PRIOR_VEKT
                pm = (prior[0] + prior[1]) / 2
                blend = lambda a, b: (n * a + k * b) / (n + k)
                lav, midt, hoy = blend(lav, prior[0]), blend(midt, pm), blend(hoy, prior[1])
            return lav, midt, max(hoy, lav + 10), n
        if prior:
            return prior[0], (prior[0] + prior[1]) / 2, prior[1], n
        return None

    def beregn(self) -> dict:
        alder = self.bu.alder()
        alder_dager = alder["dager"] if alder else None
        nå = naa()
        st = self.bu.status()
        vaaken, varighet = self._data()

        prior = None
        if alder_dager is not None and 0 <= alder_dager < ref.NYFODT_VAAKEN_TIL_DAG:
            prior = ref.NYFODT_VAAKENPERIODE_MIN

        def sikkerhet(n):
            return "god" if n >= 20 else "middels" if n >= 8 else "lav"

        if st["tilstand"] == "sover":
            start = fra_iso(st["sovn"]["start"])
            est = self._estimat(self._velg(varighet, self._er_natt(start)), None)
            if not est:
                return {"type": "vaakner", "klar": False,
                        "tekst": "Prognose for når babyen våkner kommer etter noen registrerte søvnperioder."}
            lav, midt, hoy, n = est
            return {
                "type": "vaakner", "klar": True,
                "fra": til_iso(start + timedelta(minutes=lav)),
                "midt": til_iso(start + timedelta(minutes=midt)),
                "til": til_iso(start + timedelta(minutes=hoy)),
                "sikkerhet": sikkerhet(n),
                "grunnlag": f"Basert på {n} søvnperioder de siste {DAGER_BAKOVER} dagene.",
            }

        if not st["siden"]:
            if prior:
                return {"type": "neste_sovn", "klar": False,
                        "tekst": f"Nyfødte er ofte våkne {prior[0]}–{prior[1]} min av gangen (Helsenorge). "
                                 "Trykk «Sover» første gang, så starter prognosen."}
            return {"type": "neste_sovn", "klar": False,
                    "tekst": "Prognosen starter når de første søvnperiodene er registrert."}

        vaaknet = fra_iso(st["siden"])
        est = self._estimat(self._velg(vaaken, self._er_natt(vaaknet)), prior)
        if not est:
            return {"type": "neste_sovn", "klar": False,
                    "tekst": "Prognose for neste søvn kommer etter noen registrerte søvnperioder."}
        lav, midt, hoy, n = est
        fra, til = vaaknet + timedelta(minutes=lav), vaaknet + timedelta(minutes=hoy)
        midt_tid = vaaknet + timedelta(minutes=midt)

        res = {
            "type": "neste_sovn", "klar": True,
            "fra": til_iso(fra), "midt": til_iso(midt_tid), "til": til_iso(til),
            "sikkerhet": sikkerhet(n) if n >= MIN_EGNE else "startestimat",
            "forbi": nå > til,
        }
        if n >= MIN_EGNE:
            res["grunnlag"] = f"Basert på {n} våkenperioder de siste {DAGER_BAKOVER} dagene" + (
                ", veid sammen med Helsenorges startestimat." if prior and n < 15 else ".")
        else:
            res["grunnlag"] = (f"Startestimat: Helsenorge oppgir at nyfødte ofte er våkne "
                               f"{prior[0]}–{prior[1]} minutter av gangen. Blir mer treffsikkert etter "
                               "hvert som dere registrerer.")

        dur = self._estimat(self._velg(varighet, self._er_natt(midt_tid)), None)
        if dur:
            res["varighet_min"] = [round(dur[0]), round(dur[2])]
        return res

    def siste_dogn(self) -> dict:
        """Søvn og måltider siste 24 timer, med referanse for alderen."""
        nå = naa()
        fra = nå - timedelta(hours=24)
        sovn_sek = 0.0
        mat_tider = []
        for h in self.bu.db.i_tidsrom(fra, nå):
            s = fra_iso(h["start"])
            e = fra_iso(h["slutt"]) if h["slutt"] else nå
            if h["kategori"] == "sovn":
                sovn_sek += max(0.0, (min(e, nå) - max(s, fra)).total_seconds())
            elif h["kategori"] == "mat" and s >= fra:
                mat_tider.append((s, e))
        maltider, siste = 0, None
        for s, e in sorted(mat_tider):
            if siste is None or s - siste > timedelta(minutes=20):
                maltider += 1
            siste = max(e, siste or e)

        alder = self.bu.alder()
        alder_dager = alder["dager"] if alder else None
        res = {
            "sovn_timer": round(sovn_sek / 3600, 1),
            "maltider": maltider,
            "sovn_referanse": ref.sovn_referanse(alder_dager),
            "amming_referanse": None,
            "antall_dager_med_data": self._dager_med_data(),
        }
        if (alder_dager is not None and 0 <= alder_dager < ref.NYFODT_TIL_DAG
                and self.bu.cfg.mating != "flaske"):
            a, b = ref.NYFODT_AMMING_PER_DOGN
            res["amming_referanse"] = {
                "tekst": f"Nyfødte som ammes, spiser minst {a}–{b} ganger i døgnet.",
                "kilde": "helsenorge_sovn",
            }
        return res

    def _dager_med_data(self) -> int:
        r = self.bu.db.con.execute(
            "SELECT MIN(start) FROM hendelser WHERE kategori = 'sovn'").fetchone()[0]
        if not r:
            return 0
        return max(0, (naa() - fra_iso(r)).days)
