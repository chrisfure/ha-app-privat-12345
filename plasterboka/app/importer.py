"""Import av eldre medisin- og temperaturlogger fra kalendere i Home Assistant.

Kalenderhendelsene har hatt flere tekstformater opp gjennom årene, f.eks.
«Paracetamol 125.0 mg», «Temperatur Ola: 39.8°C», «Ola Temp: 37.9°C»,
«Ola: Paracetamol 250.0mg» og «Ola: Kun notat». Beskrivelsen er et fritt notat,
som av og til inneholder en temperatur («Temp: 38,7»).

Importen
* tolker alle formatene,
* fjerner duplikater (samme tidspunkt og innhold),
* slår sammen temperatur og dose som er registrert samtidig,
* finner barnet fra navnet i teksten – ellers brukes kalenderens innstilling,
* merker mulige dobbeltregistreringer og avvikende doser for gjennomgang,
* kan kjøres flere ganger uten å lage dobbelt opp.
"""
from __future__ import annotations

import hashlib
import re
from collections import Counter
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta

from db import fra_iso, til_iso

TEMP_RE = re.compile(r"temp(?:eratur)?\b[^:\d]*:?\s*(\d{2}[.,]\d+)\s*°?\s*c?", re.I)
DOSE_RE = re.compile(r"([A-Za-zÆØÅæøåéü][\wÆØÅæøåéü\- ]*?)\s+(\d+(?:[.,]\d+)?)\s*mg\b", re.I)
NOTAT_TEMP_RE = re.compile(r"\btemp\w*\s*:?\s*(\d{2}[.,]\d)\b", re.I)
KUN_NOTAT_RE = re.compile(r"kun\s+notat", re.I)

DOBBEL_VINDU = timedelta(minutes=90)


@dataclass
class Rad:
    tid: datetime
    barn_navn: str | None          # navn funnet i teksten
    kalender: str
    temp: float | None = None
    temp_metode: str | None = None
    legemiddel: str | None = None
    dose_mg: float | None = None
    notat: str | None = None
    uids: list[str] = field(default_factory=list)
    barn_id: int | None = None
    status: str = "ok"
    merknad: str | None = None

    def nokkel(self) -> str:
        deler = [til_iso(self.tid), (self.barn_navn or "").lower(), str(self.temp), (self.legemiddel or "").lower(),
                 str(self.dose_mg), (self.notat or "").strip().lower()]
        return "imp:" + hashlib.sha1("|".join(deler).encode()).hexdigest()[:16]


def _tall(s: str) -> float:
    return float(s.replace(",", "."))


def finn_navn(tekst: str, navn: list[str]) -> str | None:
    for n in sorted(navn, key=len, reverse=True):
        if re.search(rf"(?<![\wæøå]){re.escape(n)}(?![\wæøå])", tekst, re.I):
            return n
    return None


def tolk(hendelse: dict, kalender: str, navn: list[str]) -> Rad | None:
    """Tolk én kalenderhendelse. Returnerer None for hendelser uten innhold."""
    start = hendelse.get("start") or {}
    tid_s = start.get("dateTime") if isinstance(start, dict) else start
    if not tid_s:
        return None  # heldagshendelser er ikke logger
    tid = fra_iso(tid_s)
    tittel = re.sub(r"\s+", " ", (hendelse.get("summary") or "").strip())
    notat = (hendelse.get("description") or "").strip() or None
    barn = finn_navn(tittel, navn)
    rest = tittel
    if barn:
        rest = re.sub(rf"(?<![\wæøå]){re.escape(barn)}(?![\wæøå])", "", rest, flags=re.I).strip(" :-")
    r = Rad(tid=tid, barn_navn=barn, kalender=kalender, notat=notat, uids=[hendelse.get("uid") or ""])
    if m := TEMP_RE.search(rest):
        r.temp = _tall(m.group(1))
        r.temp_metode = "ore"
    elif KUN_NOTAT_RE.search(rest):
        pass
    elif m := DOSE_RE.search(rest):
        r.legemiddel = m.group(1).strip(" :-").capitalize()
        r.dose_mg = _tall(m.group(2))
    elif rest:
        r.notat = " – ".join(x for x in (rest, notat) if x)
    if r.temp is None and r.legemiddel is None and not r.notat:
        return None
    return r


def _slaa_sammen(rader: list[Rad]) -> list[Rad]:
    """Samme barn og samme minutt: temperatur og notat legges på dose-raden."""
    ut: list[Rad] = []
    grupper: dict[tuple, list[Rad]] = {}
    for r in rader:
        grupper.setdefault((til_iso(r.tid), r.kalender), []).append(r)
    # Innen samme minutt og kalender: hendelser uten navn følger det ene navnet som finnes
    delt: list[list[Rad]] = []
    for g in grupper.values():
        navn = {r.barn_navn.lower() for r in g if r.barn_navn}
        if len(navn) <= 1:
            felles = next((r.barn_navn for r in g if r.barn_navn), None)
            for r in g:
                r.barn_navn = felles
            delt.append(g)
        else:
            per: dict[str, list[Rad]] = {}
            for r in g:
                per.setdefault((r.barn_navn or "").lower(), []).append(r)
            delt.extend(per.values())
    for g in delt:
        doser = [r for r in g if r.legemiddel]
        andre = [r for r in g if not r.legemiddel]
        if not doser:
            doser = [andre.pop(0)]
        hoved = doser[0]
        for r in andre:
            if r.temp is not None and hoved.temp is None:
                hoved.temp, hoved.temp_metode = r.temp, r.temp_metode
            elif r.temp is not None:
                doser.append(r)
                continue
            if r.notat and r.notat != hoved.notat:
                hoved.notat = " – ".join(x for x in (hoved.notat, r.notat) if x)
            hoved.uids += r.uids
        ut.extend(doser)
    return sorted(ut, key=lambda r: r.tid)


def _temp_fra_notat(r: Rad) -> None:
    if r.temp is None and r.notat and (m := NOTAT_TEMP_RE.search(r.notat)):
        t = _tall(m.group(1))
        if 35 <= t <= 42.5:
            r.temp, r.temp_metode = t, "notat"


def _merk_avvik(rader: list[Rad], kl) -> None:
    """Mulige dobbeltregistreringer og doser som avviker fra det vanlige."""
    per: dict[tuple, list[Rad]] = {}
    for r in rader:
        if r.legemiddel:
            per.setdefault((r.barn_id or ("kalender", r.kalender), r.legemiddel.lower()), []).append(r)
    for liste in per.values():
        for a, b in zip(liste, liste[1:]):
            if b.tid - a.tid < DOBBEL_VINDU:
                b.status = "sjekk"
                b.merknad = f"Mulig dobbeltregistrering – også {a.legemiddel} kl. {kl(a.tid)}"
        for r in liste:
            naboer = [x.dose_mg for x in liste if abs(x.tid - r.tid) <= timedelta(days=3)]
            vanlig, antall = Counter(naboer).most_common(1)[0]
            if antall >= 3 and r.dose_mg != vanlig and r.status != "sjekk":
                r.status = "sjekk"
                r.merknad = f"Avvikende dose – vanlig dose disse dagene var {vanlig:g} mg"


@dataclass
class Kalenderoppsett:
    entity_id: str
    barn_id: int | None = None           # standardbarn for hendelser uten navn
    gjennomga_for: date | None = None    # hendelser uten navn før denne datoen gjennomgås
    gjennomga_alle: bool = False


def planlegg(hendelser: dict[str, list[dict]], oppsett: list[Kalenderoppsett], barn: list[dict],
             eksisterende: set[str], kl, tz) -> dict:
    """Lag importplanen uten å skrive noe. Returnerer rader og en oppsummering."""
    navn_til_id = {b["navn"].lower(): b["id"] for b in barn}
    navn = [b["navn"] for b in barn]
    per_kal = {o.entity_id: o for o in oppsett}
    lest = 0
    rader: list[Rad] = []
    for kal, liste in hendelser.items():
        for h in liste:
            lest += 1
            r = tolk(h, kal, navn)
            if r:
                rader.append(r)

    # 1) Duplikater: samme tidspunkt og identisk innhold
    unike: dict[str, Rad] = {}
    for r in rader:
        k = r.nokkel()
        if k in unike:
            unike[k].uids += r.uids
        else:
            unike[k] = r
    duplikater = len(rader) - len(unike)

    # 2) Slå sammen temperatur og dose registrert samtidig
    samlet = _slaa_sammen(list(unike.values()))
    for r in samlet:
        _temp_fra_notat(r)

    # 3) Hvilket barn?
    for r in samlet:
        o = per_kal.get(r.kalender) or Kalenderoppsett(r.kalender)
        if r.barn_navn:
            r.barn_id = navn_til_id.get(r.barn_navn.lower())
        elif o.gjennomga_alle or o.barn_id is None:
            r.barn_id = None
        elif o.gjennomga_for and r.tid.astimezone(tz).date() < o.gjennomga_for:
            r.barn_id = None
        else:
            r.barn_id = o.barn_id
            r.status = "antatt"
        if r.barn_id is None:
            r.status = "ukjent"

    _merk_avvik(samlet, kl)

    nye = [r for r in samlet if r.nokkel() not in eksisterende]
    legemidler = sorted({r.legemiddel for r in nye if r.legemiddel})
    aar = Counter(r.tid.astimezone(tz).year for r in nye)
    per_barn = Counter(r.barn_id for r in nye)
    return {
        "rader": nye,
        "oppsummering": {
            "hendelser": lest,
            "duplikater": duplikater,
            "sammenslatt": len(unike) - len(samlet),
            "registreringer": len(nye),
            "allerede_importert": len(samlet) - len(nye),
            "med_navn": sum(1 for r in nye if r.barn_navn),
            "antatt": sum(1 for r in nye if r.status == "antatt"),
            "ukjent": sum(1 for r in nye if r.barn_id is None),
            "sjekk": sum(1 for r in nye if r.status == "sjekk"),
            "temp_fra_notat": sum(1 for r in nye if r.temp_metode == "notat"),
            "legemidler": legemidler,
            "per_aar": dict(sorted(aar.items())),
            "per_barn": {str(k) if k else "ukjent": v for k, v in per_barn.items()},
            "fra": til_iso(min(r.tid for r in nye)) if nye else None,
            "til": til_iso(max(r.tid for r in nye)) if nye else None,
        },
    }
