"""Tester for uke- og månedsoversikten i dagboken."""
from __future__ import annotations

import sys
from datetime import date, timedelta
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "app"))

import innstillinger  # noqa: E402
from db import Database  # noqa: E402
from logikk import Babyuret, Feil  # noqa: E402


@pytest.fixture
def bu(tmp_path):
    cfg = innstillinger.Innstillinger(data_dir=tmp_path)
    return Babyuret(Database(tmp_path / "t.db"), cfg, tz="Europe/Oslo")


def test_uke_gaar_fra_mandag_til_sondag(bu):
    p = bu.periode("uke", date(2026, 11, 4))
    assert p["fra"] == "2026-11-02" and p["til"] == "2026-11-08"
    assert p["tittel"] == "Uke 45" and len(p["dager"]) == 7
    assert p["forrige"] == "2026-10-26"


def test_maaned_har_riktig_antall_dager(bu):
    p = bu.periode("maaned", date(2026, 2, 14))
    assert p["fra"] == "2026-02-01" and p["til"] == "2026-02-28"
    assert p["tittel"] == "Februar 2026" and p["forrige"] == "2026-01-01"
    assert p["neste"] == "2026-03-01"


def test_ingen_neste_for_innevaerende_periode(bu):
    assert bu.periode("uke")["neste"] is None
    assert bu.periode("maaned")["neste"] is None


def test_snitt_og_totalt(bu):
    bu.handling("sovn_start", {"minutter_siden": 300})
    bu.handling("sovn_slutt", {"minutter_siden": 60})
    bu.handling("tiss", {})
    p = bu.periode("uke")
    assert p["totalt"]["sovn_sek"] >= 4 * 3600 - 60
    assert p["totalt"]["bleier"] == 1
    assert p["dager_i_snitt"] == 1
    assert p["snitt"]["sovn_timer"] is not None


def test_framtidige_dager_har_ingen_data(bu):
    p = bu.periode("maaned", bu.i_dag())
    framtid = [r for r in p["dager"] if r["framtid"]]
    assert all("sovn_sek" not in r for r in framtid)


def test_dager_for_fodsel_merkes(bu):
    i_dag = bu.i_dag()
    bu.lagre_innstillinger({"fodselsdato": i_dag.isoformat()})
    p = bu.periode("uke", i_dag)
    for r in p["dager"]:
        assert r["for_fodsel"] == (r["dag"] < i_dag.isoformat())


def test_ugyldig_periode(bu):
    with pytest.raises(Feil):
        bu.periode("aar")
