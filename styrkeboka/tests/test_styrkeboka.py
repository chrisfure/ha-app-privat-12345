"""Tester for program, progresjon og økter. Kjør: python3 -m pytest styrkeboka/tests"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "app"))

import ai  # noqa: E402
import program as P  # noqa: E402
from db import Database  # noqa: E402
from logikk import Feil, Styrkeboka  # noqa: E402
from ovelser import BIBLIOTEK, MONSTER, UTSTYR  # noqa: E402


@pytest.fixture
def sb(tmp_path):
    s = Styrkeboka(Database(tmp_path / "t.db"))
    s.lagre_profil({"navn": "Testperson", "maal": ["muskelvekst", "generell"], "dager_per_uke": 3, "okt_minutter": 60})
    return s


def test_bibliotek_gyldig():
    for o in BIBLIOTEK:
        assert o["monster"] in MONSTER, o["nokkel"]
        assert set(o["utstyr"]) <= set(UTSTYR), o["nokkel"]
        assert o["tips"], o["nokkel"]


@pytest.mark.parametrize("dager", [1, 2, 3, 4, 5, 6])
@pytest.mark.parametrize("utstyr", [None, set(), {"manualer", "strikk"}, {"manualer", "benk"}])
def test_program_for_alle_oppsett(dager, utstyr):
    prof = {"dager_per_uke": dager, "okt_minutter": 45, "erfaring": "noe", "maal": ["generell"]}
    prog = P.lag_program(prof, BIBLIOTEK, utstyr)
    assert len(prog["dager"]) == dager
    for d in prog["dager"]:
        assert 3 <= len(d["ovelser"]) <= 5
        nokler = [o["ovelse"] for o in d["ovelser"]]
        assert len(nokler) == len(set(nokler))


def test_rehab_velger_skansomt():
    prof = {"dager_per_uke": 2, "okt_minutter": 60, "erfaring": "nybegynner", "maal": ["rehab"]}
    prog = P.lag_program(prof, BIBLIOTEK, None)
    idx = {o["nokkel"]: o for o in BIBLIOTEK}
    for d in prog["dager"]:
        for o in d["ovelser"]:
            assert idx[o["ovelse"]]["skansom"], o["ovelse"]
            assert o["rir"] >= 3
            assert o["reps_maks"] >= 15


def _sett(kg, reps, rir=None):
    return {"vekt": kg, "reps": reps, "rir": rir}


def test_progresjon():
    stang = next(o for o in BIBLIOTEK if o["nokkel"] == "knebøy-stang")
    plan = {"sett": 3, "reps_min": 8, "reps_maks": 12, "rir": 2}
    assert P.foreslaa(stang, plan, [])["trend"] == "ny"
    opp = P.foreslaa(stang, plan, [[_sett(60, 12), _sett(60, 12), _sett(60, 12)]])
    assert opp["trend"] == "opp" and opp["kg"] == 62.5
    likt = P.foreslaa(stang, plan, [[_sett(60, 10), _sett(60, 9), _sett(60, 8)]])
    assert likt["trend"] == "likt" and likt["kg"] == 60 and likt["reps"] == 11
    ned = P.foreslaa(stang, plan, [[_sett(60, 6)], [_sett(60, 7)]])
    assert ned["trend"] == "ned" and ned["kg"] < 60
    # én dårlig økt gir ikke nedtrapping
    assert P.foreslaa(stang, plan, [[_sett(60, 6)], [_sett(60, 10)]])["trend"] == "likt"


def test_okt_flyt(sb):
    pid = sb.profiler()[0]["id"]
    prog = sb.lagre_program(pid, sb.foreslaa_program(pid), kilde="mal")
    assert prog["aktiv"] == 1
    dag = sb.neste_dag(pid)
    assert dag["id"] == prog["dager"][0]["id"]
    okt = sb.start_okt(pid, dag["id"])
    assert len(okt["ovelser"]) == len(dag["ovelser"])
    with pytest.raises(Feil):
        sb.avslutt_okt(okt["id"], {})
    forste = okt["ovelser"][0]
    for _ in range(3):
        sb.logg_sett(okt["id"], {"okt_ovelse_id": forste["id"], "vekt": "40", "reps": forste["reps_maks"], "rir": 2})
    res = sb.avslutt_okt(okt["id"], {"opplevd": 3})
    assert res["okt"]["nokkeltall"]["sett"] == 3
    assert sb.neste_dag(pid)["id"] == prog["dager"][1]["id"]
    # neste gang samme dag: forslag om mer vekt
    for d in prog["dager"][1:]:
        o2 = sb.start_okt(pid, d["id"])
        sb.logg_sett(o2["id"], {"okt_ovelse_id": o2["ovelser"][0]["id"], "vekt": 10, "reps": 10})
        sb.avslutt_okt(o2["id"], {})
    o3 = sb.start_okt(pid, prog["dager"][0]["id"])
    assert o3["ovelser"][0]["forslag_kg"] > 40
    assert sb.historikk(pid)
    h = sb.ovelse_historikk(pid, forste["ovelse"])
    assert h["punkter"][0]["topp_kg"] == 40


def test_bytte_lagres_i_program(sb):
    pid = sb.profiler()[0]["id"]
    prog = sb.lagre_program(pid, sb.foreslaa_program(pid), kilde="mal")
    okt = sb.start_okt(pid, prog["dager"][0]["id"])
    oo = okt["ovelser"][0]
    alt = next(a for a in sb.alternativer(oo["ovelse"], None) if a["tilgjengelig"])
    sb.endre_okt_ovelse(oo["id"], {"ovelse": alt["nokkel"], "ogsa_program": True})
    ny = sb.aktivt_program(pid)
    assert ny["dager"][0]["ovelser"][0]["ovelse"] == alt["nokkel"]
    assert len(sb.versjoner(ny["id"])) == 2


def test_hjemme_bytter_ut_utilgjengelig(sb):
    pid = sb.profiler()[0]["id"]
    gym, hjemme = sb.utstyrsprofiler()
    prog = sb.lagre_program(pid, sb.foreslaa_program(pid, gym["id"]), kilde="mal")
    okt = sb.start_okt(pid, prog["dager"][0]["id"], upid=hjemme["id"])
    tilgj = sb.utstyr_for(hjemme["id"])
    for oo in okt["ovelser"]:
        assert set(oo["info"]["utstyr"]) <= tilgj or oo["erstattet_fra"] is None


def test_ai_tolk_program(sb):
    svar = """Her er programmet:
```json
{"navn": "Test", "dager": [{"navn": "A", "ovelser": [
  {"ovelse": "goblet-knebøy", "sett": 3, "reps_min": 10, "reps_maks": 15},
  {"ovelse": "finnes-ikke", "sett": 3}
]}], "begrunnelse": "fordi"}
```"""
    data = ai.les_json(svar)
    pid = sb.profiler()[0]["id"]
    prog = sb.lagre_program(pid, data, kilde="ai")
    assert [o["ovelse"] for o in prog["dager"][0]["ovelser"]] == ["goblet-knebøy"]


def test_ai_kontekst_uten_navn(sb):
    pid = sb.profiler()[0]["id"]
    sb.lagre_profil({"hensyn": "Vond venstre skulder"}, pid)
    tekst = ai.profilkontekst(sb, pid)
    assert "Testperson" not in tekst
    assert "skulder" in tekst
