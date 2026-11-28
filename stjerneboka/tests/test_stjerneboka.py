"""Tester for regler, sperrer, godkjenning og ukepenger. Kjør: python3 -m pytest stjerneboka/tests"""
from __future__ import annotations

import sys
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "app"))

from db import Database  # noqa: E402
from logikk import MALER, Feil, Sperret, Stjerneboka  # noqa: E402

TZ = ZoneInfo("Europe/Oslo")


def kl(dag: int, t: int, m: int = 0) -> datetime:
    """Tidspunkt i uke 48 2026 (mandag 23. nov = dag 0)."""
    return datetime(2026, 11, 23 + dag, t, m, tzinfo=TZ)


@pytest.fixture
def sb(tmp_path):
    s = Stjerneboka(Database(tmp_path / "t.db"))
    a = s.lagre_barn({"navn": "Ola", "farge": "blaa"})
    b = s.lagre_barn({"navn": "Kari", "farge": "rosa"})
    s.a, s.b = a["id"], b["id"]
    s.tann = s.lagre_oppgave({**MALER[0], "barn": [a["id"], b["id"]]})["id"]
    s.do = s.lagre_oppgave({**MALER[1], "barn": [a["id"]]})["id"]
    s.bord = s.lagre_oppgave({"navn": "Ta av bordet", "type": "familie", "poeng": 1, "penger": 1,
                              "nar": "hele_dagen", "sperre": "intervall", "intervall_min": 120,
                              "barn": [a["id"]]})["id"]
    s.oppvask = s.lagre_oppgave({"navn": "Oppvask", "type": "ekstra", "poeng": 3, "penger": 1,
                                 "godkjenning": 1, "sperre": "dag", "barn": [a["id"]]})["id"]
    return s


def test_okter(sb):
    assert sb.okt(kl(0, 7)) == "morgen"
    assert sb.okt(kl(0, 13)) == "dag"
    assert sb.okt(kl(0, 19)) == "kveld"
    assert sb.okt(kl(1, 2)) == "kveld"
    assert sb.okt_start(kl(1, 2)) == kl(0, 16)


def test_tannpuss_en_gang_per_okt(sb):
    sb.registrer(sb.a, sb.tann, t=kl(0, 7))
    with pytest.raises(Sperret):
        sb.registrer(sb.a, sb.tann, t=kl(0, 8))
    sb.registrer(sb.a, sb.tann, t=kl(0, 19))   # ny økt
    sb.registrer(sb.b, sb.tann, t=kl(0, 19))   # annet barn
    assert sb.stjerner_i_dag(sb.a, kl(0, 20)) == 2


def test_do_intervall(sb):
    sb.registrer(sb.a, sb.do, t=kl(0, 10))
    with pytest.raises(Sperret):
        sb.registrer(sb.a, sb.do, t=kl(0, 10, 20))
    sb.registrer(sb.a, sb.do, t=kl(0, 10, 31))


def test_ikke_tildelt(sb):
    with pytest.raises(Feil):
        sb.registrer(sb.b, sb.do, t=kl(0, 10))


def test_godkjenning_og_ukepenger(sb):
    r = sb.registrer(sb.a, sb.oppvask, t=kl(1, 17))["registrering"]
    assert r["status"] == "venter"
    with pytest.raises(Sperret):  # venter allerede
        sb.registrer(sb.a, sb.oppvask, t=kl(1, 17, 5))
    s = sb.ukesum(sb.a, sb.uke_start(kl(1, 18)))
    assert s["stjerner"] == 0 and s["kroner"] is None
    sb.godkjenn(r["id"], av="Voksen")
    sb.registrer(sb.a, sb.bord, t=kl(1, 18))
    sb.registrer(sb.a, sb.tann, t=kl(1, 19))   # rutine – ingen penger
    sb.lagre_innstillinger({"ukepenger_aktiv": "1", "kr_per_poeng": "2,5"})
    s = sb.ukesum(sb.a, sb.uke_start(kl(1, 20)))
    assert s["stjerner"] == 3 and s["poeng_penger"] == 4 and s["kroner"] == 10.0


def test_avvist_kan_proves_igjen(sb):
    r = sb.registrer(sb.a, sb.oppvask, t=kl(2, 17))["registrering"]
    sb.godkjenn(r["id"], godkjent=False)
    sb.registrer(sb.a, sb.oppvask, t=kl(2, 17, 30))


def test_rutine_kan_ikke_gi_penger(sb):
    o = sb.lagre_oppgave({"navn": "Test", "type": "rutine", "penger": 1})
    assert o["penger"] == 0
    with pytest.raises(Feil):
        sb.lagre_oppgave({"penger": 1}, sb.tann)
    # men kan flyttes til familiebidrag og bli pengeoppgave
    assert sb.lagre_oppgave({"type": "familie", "penger": 1}, sb.tann)["penger"] == 1


def test_barnevisning_mangler(sb):
    v = sb.barnevisning(kl(3, 19))
    ola = next(b for b in v["barn"] if b["navn"] == "Ola")
    assert "Tannpuss" in ola["mangler"] and not ola["alt_ferdig"]
    sb.registrer(sb.a, sb.tann, t=kl(3, 19))
    sb.registrer(sb.a, sb.do, t=kl(3, 19))
    ola = next(b for b in sb.barnevisning(kl(3, 19, 1))["barn"] if b["navn"] == "Ola")
    assert ola["alt_ferdig"] and {k["navn"] for k in ola["hjelpe"]} == {"Ta av bordet", "Oppvask"}


def test_kort(sb):
    assert sb.skann("04a1b2c3")["handling"] == "ukjent"
    assert sb.db.ukjente_kort()[0]["uid"] == "04A1B2C3"
    sb.lagre_kort("04a1b2c3", {"barn_id": sb.b, "oppgave_id": sb.tann})
    assert not sb.db.ukjente_kort()
    assert sb.skann("04A1B2C3")["handling"] == "registrert"
    assert sb.skann("04A1B2C3")["handling"] == "sperret"
    with pytest.raises(Feil):
        sb.lagre_kort("XYZ12345", {"barn_id": sb.b, "oppgave_id": sb.do})  # ikke tildelt Kari


def test_angre_tidsgrense(sb):
    t0 = datetime.now(TZ) - timedelta(minutes=10)
    r = sb.registrer(sb.a, sb.bord, t=t0)["registrering"]
    with pytest.raises(Feil):
        sb.angre(r["id"])
    sb.angre(r["id"], fra_skjerm=False)


def test_sensorer(sb):
    s = sb.sensorer()
    assert "sensor.stjerneboka_ola" in s and "sensor.stjerneboka_venter_godkjenning" in s


def test_lesere_og_musikk(sb):
    hendelser = []
    sb.ved_endring(lambda hva, d: hendelser.append((hva, d)))
    # ukjent kort på en leser registrerer leseren
    assert sb.skann("aa-bb-cc-dd", leser_id="dev1", leser_navn="NFC stue", leser_rom="Stue")["handling"] == "ukjent"
    assert sb.db.en_leser("dev1")["navn"] == "NFC stue"
    assert sb.db.ukjente_kort()[0]["leser_id"] == "dev1"
    # musikk uten høyttaler gir beskjed
    sb.lagre_kort("AA-BB-CC-DD", {"handling": "musikk", "media_id": "Dilla på", "media_type": "track"})
    assert sb.skann("AA-BB-CC-DD", leser_id="dev1")["handling"] == "mangler_hoyttaler"
    # med høyttaler på leseren spilles det der
    sb.lagre_leser("dev1", {"hoyttaler": "media_player.stue"})
    res = sb.skann("AA-BB-CC-DD", leser_id="dev1")
    assert res["handling"] == "musikk" and res["hoyttaler"] == "media_player.stue"
    assert hendelser[-1][0] == "musikk"
    # samme kort på en annen leser spiller i det rommet
    sb.skann("AA-BB-CC-DD", leser_id="dev2", leser_navn="NFC rom", leser_rom="Barnerom")
    sb.lagre_leser("dev2", {"hoyttaler": "media_player.barnerom"})
    assert sb.skann("AA-BB-CC-DD", leser_id="dev2")["hoyttaler"] == "media_player.barnerom"
    with pytest.raises(Feil):
        sb.lagre_kort("AA-BB-CC-DD", {"handling": "musikk", "media_id": ""})


def test_leser_uten_stjerner_og_ha(sb):
    sb.skann("11-22-33-44", leser_id="rom", leser_navn="Rom")
    sb.lagre_leser("rom", {"gir_stjerner": False})
    sb.lagre_kort("11-22-33-44", {"barn_id": sb.a, "oppgave_id": sb.bord})
    assert sb.skann("11-22-33-44", leser_id="rom")["handling"] == "ikke_her"
    assert sb.skann("11-22-33-44")["handling"] == "registrert"   # leser uten id (MQTT) gir stjerner
    sb.lagre_kort("55-66-77-88", {"handling": "ha", "entity": "automation.lys_rosa"})
    assert sb.skann("55-66-77-88", leser_id="rom")["handling"] == "ha"
    with pytest.raises(Feil):
        sb.lagre_kort("55-66-77-88", {"handling": "ha", "entity": "light.x"})


def test_maks_per_dag_med_pause(sb):
    sb.lagre_oppgave({"sperre": "intervall", "intervall_min": 30, "maks_per_dag": 2}, sb.do)
    sb.registrer(sb.a, sb.do, t=kl(4, 8))
    with pytest.raises(Sperret):                       # pausen
        sb.registrer(sb.a, sb.do, t=kl(4, 8, 10))
    sb.registrer(sb.a, sb.do, t=kl(4, 9))
    with pytest.raises(Sperret, match="2 ganger i dag"):  # dagsgrensen, selv etter pausen
        sb.registrer(sb.a, sb.do, t=kl(4, 12))
    st = sb.oppgavestatus(sb.a, sb.db.en_oppgave(sb.do), kl(4, 12))
    assert st["ferdig"] and st["dagsgrense"] and st["brukt_i_dag"] == 2
    sb.registrer(sb.a, sb.do, t=kl(5, 8))              # ny dag


def test_maks_per_dag_fri(sb):
    o = sb.lagre_oppgave({"navn": "Hjelpe til", "type": "familie", "sperre": "fri", "maks_per_dag": 3,
                          "barn": [sb.a]})["id"]
    for m in range(3):
        sb.registrer(sb.a, o, t=kl(6, 10, m))
    with pytest.raises(Sperret):
        sb.registrer(sb.a, o, t=kl(6, 10, 5))
