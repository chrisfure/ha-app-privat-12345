"""Tester for import og dosekontroll. Kjør: python3 -m pytest plasterboka/tests"""
from __future__ import annotations

import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "app"))

import importer  # noqa: E402
from db import Database, naa, til_iso  # noqa: E402
from logikk import Advarsel, Plasterboka  # noqa: E402

TZ = ZoneInfo("Europe/Oslo")


def hendelse(tid: str, tittel: str, notat: str = "", uid: str | None = None) -> dict:
    return {"start": {"dateTime": tid}, "summary": tittel, "description": notat,
            "uid": uid or f"{tid}-{tittel}-{notat}-{id(object())}"}


@pytest.fixture
def pb(tmp_path):
    p = Plasterboka(Database(tmp_path / "t.db"))
    p.lagre_barn({"navn": "Ola", "farge": "blaa"})
    p.lagre_barn({"navn": "Kari", "farge": "rosa"})
    return p


def plan(pb, hendelser, oppsett):
    return importer.planlegg(hendelser, oppsett, pb.db.barn(), pb.db.kilde_refs(), pb.kl, pb.tz)


def test_tolker_alle_formater():
    navn = ["Ola", "Kari"]
    r = importer.tolk(hendelse("2024-04-03T16:43:00+02:00", "Nurofen 100.0 mg"), "k", navn)
    assert (r.legemiddel, r.dose_mg, r.barn_navn) == ("Nurofen", 100.0, None)
    r = importer.tolk(hendelse("2026-02-28T22:15:00+01:00", "Temperatur Ola: 39.8°C"), "k", navn)
    assert (r.temp, r.barn_navn) == (39.8, "Ola")
    r = importer.tolk(hendelse("2026-03-01T09:51:00+01:00", "Ola Temp: 37.3°C", "Godt humør"), "k", navn)
    assert (r.temp, r.notat) == (37.3, "Godt humør")
    r = importer.tolk(hendelse("2026-02-28T22:15:00+01:00", "Paracetamol  250.0mg"), "k", navn)
    assert (r.legemiddel, r.dose_mg) == ("Paracetamol", 250.0)
    r = importer.tolk(hendelse("2026-05-16T22:30:00+02:00", "Kari: Penicillin 200.0mg"), "k", navn)
    assert (r.legemiddel, r.dose_mg, r.barn_navn) == ("Penicillin", 200.0, "Kari")
    r = importer.tolk(hendelse("2026-06-13T22:53:00+02:00", "Ola: Kun notat", "Klam og varm"), "k", navn)
    assert (r.temp, r.legemiddel, r.notat) == (None, None, "Klam og varm")


def test_duplikater_sammenslaing_og_barn(pb):
    h = []
    # samme dose kopiert mange ganger
    for i in range(50):
        h.append(hendelse("2024-04-08T06:30:00+02:00", "Penicillin 125.0 mg", uid=f"dup{i}"))
    h.append(hendelse("2024-04-08T12:30:00+02:00", "Penicillin 125.0 mg"))
    # temperatur og dose samtidig blir én registrering
    h.append(hendelse("2026-10-16T17:23:00+02:00", "Ola Temp: 38.7°C"))
    h.append(hendelse("2026-10-16T17:23:00+02:00", "Ola: Paracetamol 250.0mg"))
    # temperatur hentes fra notatet
    h.append(hendelse("2026-10-15T23:55:00+02:00", "Ola: Paracetamol 250.0mg", "Temp: 38,7"))
    p = plan(pb, {"calendar.a": h}, [importer.Kalenderoppsett("calendar.a", barn_id=1,
                                                                  gjennomga_for=date(2025, 4, 11))])
    o = p["oppsummering"]
    assert o["duplikater"] == 49
    assert o["registreringer"] == 4
    assert o["ukjent"] == 2            # 2024 uten navn → gjennomgang
    assert o["temp_fra_notat"] == 1
    samlet = [r for r in p["rader"] if r.temp == 38.7 and r.temp_metode == "ore"][0]
    assert samlet.legemiddel == "Paracetamol" and samlet.barn_id == 1

    res = pb.importer(p["rader"])
    assert res["importert"] == 4
    # idempotent
    p2 = plan(pb, {"calendar.a": h}, [importer.Kalenderoppsett("calendar.a", barn_id=1,
                                                                   gjennomga_for=date(2025, 4, 11))])
    assert p2["oppsummering"]["registreringer"] == 0

    g = pb.gjennomgang()
    assert len(g["ukjente"]) == 1 and len(g["ukjente"][0]["ider"]) == 2
    pb.tildel(g["ukjente"][0]["ider"], 2)
    assert pb.db.antall_status()["ukjent"] == 0
    assert len(pb.db.episoder(2)) == 1


def test_merker_dobbel_og_avvikende_dose(pb):
    h = [hendelse(f"2026-10-2{d}T{t}:00+02:00", "Ola: Penicillin 200.0mg")
         for d in (0, 1, 2) for t in ("08:00", "14:00", "20:00")]
    h.append(hendelse("2026-10-23T19:00:00+02:00", "Ola: Penicillin 100.0mg"))
    h.append(hendelse("2026-10-22T20:40:00+02:00", "Ola: Penicillin 200.0mg"))
    p = plan(pb, {"calendar.a": h}, [importer.Kalenderoppsett("calendar.a", barn_id=1)])
    sjekk = [r for r in p["rader"] if r.status == "sjekk"]
    assert any("dobbeltregistrering" in r.merknad for r in sjekk)
    assert any("Avvikende dose" in r.merknad for r in sjekk)


def test_dosekontroll_per_virkestoff(pb):
    mikstur = pb.lagre_legemiddel({"navn": "Paracet mikstur", "virkestoff": "Paracetamol",
                                   "form": "mikstur", "mg_per_ml": 24})
    pille = pb.lagre_legemiddel({"navn": "Paracet stikkpille", "virkestoff": "Paracetamol", "form": "stikkpille"})
    for lm in (mikstur, pille):
        pb.lagre_barn_legemiddel(1, lm["id"], {"aktiv": 1, "min_intervall_t": 6, "maks_dogn_mg": 1000})
    t = naa() - timedelta(hours=3)
    r = pb.registrer({"barn_id": 1, "tid": til_iso(t), "legemiddel_id": mikstur["id"], "dose_ml": 10})
    assert r["dose_mg"] == 240
    with pytest.raises(Advarsel) as e:
        pb.registrer({"barn_id": 1, "legemiddel_id": pille["id"], "dose_mg": 250})
    assert "tidligst" in e.value.advarsler[0]
    pb.registrer({"barn_id": 1, "legemiddel_id": pille["id"], "dose_mg": 250, "bekreftet": True})
    status = {d["navn"]: d for d in pb.dosestatus(1)}
    assert status["Paracet mikstur"]["sum_24t"] == 490
    assert status["Paracet stikkpille"]["neste_kl"] is not None
    with pytest.raises(Advarsel) as e:
        pb.registrer({"barn_id": 1, "legemiddel_id": pille["id"], "dose_mg": 600, "bekreftet": False,
                      "minutter_siden": 0})
    assert any("Maks døgndose" in a for a in e.value.advarsler)


def test_episoder_og_frisk(pb):
    t0 = naa() - timedelta(days=10)
    pb.registrer({"barn_id": 1, "tid": til_iso(t0), "temp": 39})
    pb.registrer({"barn_id": 1, "tid": til_iso(t0 + timedelta(hours=20)), "temp": 38.5})
    pb.registrer({"barn_id": 1, "tid": til_iso(naa() - timedelta(hours=2)), "temp": 38.2})
    assert len(pb.db.episoder(1)) == 2
    assert pb.aktiv_episode(1) is not None
    pb.frisk(1)
    assert pb.aktiv_episode(1) is None
    pb.registrer({"barn_id": 1, "temp": 37.0})
    assert len(pb.db.episoder(1)) == 3
    s = pb.sensorer()
    assert s["sensor.plasterboka_ola"]["state"] == "syk"
    assert s["sensor.plasterboka_kari"]["state"] == "frisk"
