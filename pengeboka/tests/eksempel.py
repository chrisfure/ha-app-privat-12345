"""Oppdiktede kontoutskrifter for tester og lokal utvikling. Ingen ekte data."""
from __future__ import annotations

import random
from datetime import date, timedelta


def _fmt(ore: int) -> str:
    return f"{abs(ore) / 100:.2f}".replace(".", ",")


def _maneder(slutt: date, n: int) -> list[date]:
    y, m = slutt.year, slutt.month
    ut = []
    for _ in range(n):
        ut.append(date(y, m, 1))
        m -= 1
        if m == 0:
            m, y = 12, y - 1
    return list(reversed(ut))


def lag(slutt: date, maneder: int = 4, seed: int = 7) -> dict[str, list[tuple[date, str, int]]]:
    """{konto: [(dato, tekst, øre)]}. Felles brukskonto, kredittkort, sparekonto og en privat konto."""
    rnd = random.Random(seed)
    k: dict[str, list] = {"felles": [], "kreditt": [], "sparing": [], "privat": []}
    for start in _maneder(slutt, maneder):
        def d(dag):
            return start.replace(day=min(dag, 28))
        if d(25) <= slutt:
            k["felles"].append((d(25), "Lønn fra ARBEIDSGIVER AS", 4_200_000))
            k["felles"].append((d(20), "NAV BARNETRYGD", 517_200))
        for dag, tekst, ore in [(1, "AvtaleGiro BOLIGLÅN DNB", -1_850_000), (3, "AvtaleGiro TIBBER NORGE AS", -rnd.randint(90_000, 260_000)),
                                (5, "AvtaleGiro GJENSIDIGE FORSIKRING", -142_300), (10, "Efaktura BARNEHAGE KOMMUNE", -315_000),
                                (12, "Visa 4925 NETFLIX.COM", -16_900 if start < _maneder(slutt, 1)[0] else -19_900),
                                (14, "Visa 4925 SPOTIFY P1234", -22_900), (15, "AvtaleGiro TELIA NORGE", -49_900)]:
            if d(dag) <= slutt:
                k["felles"].append((d(dag), tekst, ore))
        # dagligvarer
        for uke in range(5):
            for butikk in ("KIWI 505 SENTRUM", "REMA 1000 TORGET", "COOP EXTRA STASJONEN"):
                dato = d(1 + uke * 7 + rnd.randint(0, 5))
                if dato <= slutt and rnd.random() < 0.8:
                    k["felles"].append((dato, f"Varekjøp {butikk} DATO {dato:%d.%m}", -rnd.randint(25_000, 140_000)))
        # sparing hver måned
        if d(26) <= slutt:
            k["felles"].append((d(26), "Overføring til sparekonto", -500_000))
            k["sparing"].append((d(26), "Overføring fra brukskonto", 500_000))
        # kredittkort: kjøp, og betaling fra felles den 18.
        sum_kort = 0
        for _ in range(6):
            dato = d(rnd.randint(1, 27))
            if dato > slutt:
                continue
            tekst, ore = rnd.choice([("CIRCLE K SENTRUM", -rnd.randint(30_000, 90_000)), ("XXL OSLO", -rnd.randint(40_000, 150_000)),
                                     ("PEPPES PIZZA", -rnd.randint(50_000, 120_000)), ("APOTEK 1 SENTRUM", -rnd.randint(9_000, 40_000))])
            k["kreditt"].append((dato, tekst, ore))
            sum_kort += ore
        if sum_kort and d(18) <= slutt:
            k["felles"].append((d(18), "Betaling kredittkort", sum_kort))
            k["kreditt"].append((d(19), "Innbetaling", -sum_kort))
        # privat konto: overføring inn fra felles, litt forbruk
        if d(26) <= slutt:
            k["felles"].append((d(26), "Overføring Innland", -300_000))
            k["privat"].append((d(27), "Overføring Innland", 300_000))
        for _ in range(4):
            dato = d(rnd.randint(1, 27))
            if dato <= slutt:
                k["privat"].append((dato, rnd.choice(["Vipps*Ola Nordmann", "ESPRESSO HOUSE", "CUBUS STORO", "FRISØR HÅRSTUDIO 123 SENTRUM"]),
                                    -rnd.randint(5_000, 60_000)))
    # rett feil: kredittkortbetaling skal være negativ fra felles og positiv på kortet
    k["felles"] = [(d, t, -abs(o)) if t == "Betaling kredittkort" else (d, t, o) for d, t, o in k["felles"]]
    k["kreditt"] = [(d, t, abs(o)) if t == "Innbetaling" else (d, t, o) for d, t, o in k["kreditt"]]
    # en uvanlig stor regning
    stor = slutt - timedelta(days=3)
    k["felles"].append((stor, "AvtaleGiro TIBBER NORGE AS", -720_000))
    return k


def csv_dnb(rader: list[tuple[date, str, int]]) -> bytes:
    """Ligner på en eksport fra nettbanken: semikolon, desimalkomma, ut og inn i hver sin kolonne."""
    linjer = ['"Dato";"Forklaring";"Rentedato";"Ut fra konto";"Inn på konto"']
    for d, t, o in sorted(rader, key=lambda x: x[0], reverse=True):
        linjer.append(f'"{d:%d.%m.%Y}";"{t}";"{d:%d.%m.%Y}";"{_fmt(o) if o < 0 else ""}";"{_fmt(o) if o > 0 else ""}"')
    return "\r\n".join(linjer).encode("cp1252")


def csv_enkel(rader: list[tuple[date, str, int]]) -> bytes:
    """Annet vanlig format: komma, ett beløpsfelt med fortegn, ISO-datoer, UTF-8."""
    linjer = ["Bokført dato,Beskrivelse,Beløp"]
    for d, t, o in rader:
        linjer.append(f'{d.isoformat()},"{t}",{o / 100:.2f}')
    return "\n".join(linjer).encode("utf-8")


TRANSAKSJONSLISTE = ["Utført dato", "Bokført dato", "Rentedato", "Beskrivelse", "Type", "Undertype", "Fra konto", "Avsender",
                     "Til konto", "Mottakernavn", "Beløp inn", "Beløp ut", "Valuta", "Status", "Melding/KID/Fakt.nr"]


def csv_transaksjonsliste(konto: str, rader: list[tuple], reservert: list[tuple] = ()) -> bytes:
    """Nettbankens «Transaksjonsliste»: 15 kolonner, UTF-8 med BOM, semikolon, punktum som desimaltegn,
    kontonummer i «Fra konto»/«Til konto» og en bunntekst med summer. rader: (dato, tekst, øre, motkonto|None)."""
    linjer = [";".join(TRANSAKSJONSLISTE)]

    def linje(d, tekst, ore, mot, status):
        fra, til = (konto, mot or "") if ore < 0 else (mot or "", konto)
        inn, ut = (f"{ore / 100:g}", "") if ore > 0 else ("", f"{ore / 100:g}")
        bokfort = "" if status == "Reservert" else f"{d:%d.%m.%Y}"
        return ";".join([f"{d:%d.%m.%Y}", bokfort, f"{d:%d.%m.%Y}", tekst, "Varekjøp" if ore < 0 else "Overføring", "",
                         fra, "Fiktiv Testesen", til, "", inn, ut, "NOK", status, tekst])
    for d, t, o, m in reservert:
        linjer.append(linje(d, t, o, m, "Reservert"))
    for d, t, o, m in sorted(rader, key=lambda x: x[0], reverse=True):
        linjer.append(linje(d, t, o, m, "Bokført"))
    tom = ";" * 14
    sum_inn = sum(o for _, _, o, _ in rader if o > 0) / 100
    sum_ut = sum(o for _, _, o, _ in rader if o < 0) / 100
    linjer += [tom, f"Total beløp inn på konto:;;{sum_inn:.2f} NOK".replace(".", ",") + ";" * 12, tom,
               f"Totalt beløp ut av konto:;;{sum_ut:.2f} NOK".replace(".", ",") + ";" * 12, tom,
               "Inngående saldo pr. 01.10.2026:;;1 000,00 NOK" + ";" * 12]
    return ("﻿" + "\r\n".join(linjer)).encode("utf-8")
