"""Tester for gråtlogikken. Kjør: python3 -m pytest babyuret/tests"""
from __future__ import annotations

import sys
from datetime import timedelta
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "app"))

import innstillinger  # noqa: E402
from db import Database, naa  # noqa: E402
from logikk import Babyuret  # noqa: E402
from lyd import UgyldigLydoppsett, rens_oppsett  # noqa: E402

ENHETER = [
    {"kilde": "barnerom", "navn": "Barnerommet", "rolle": "fast"},
    {"kilde": "android_barnerom", "navn": "Android barnerom", "rolle": "fast"},
    {"kilde": "ipad", "navn": "iPad", "rolle": "flyttbar", "nett_entitet": "sensor.ipad_ssid"},
    {"kilde": "telefon", "navn": "Telefon", "rolle": "personlig", "nett_entitet": "sensor.telefon_ssid"},
    {"kilde": "stua", "navn": "Stua", "rolle": "motbevis"},
]


@pytest.fixture
def bu(tmp_path):
    cfg = innstillinger.Innstillinger(data_dir=tmp_path)
    b = Babyuret(Database(tmp_path / "t.db"), cfg, tz="Europe/Oslo")
    b.lagre_innstillinger({"lyd": {"aktiv": True, "enheter": ENHETER, "hjemmenett": ["Hjemme5G"],
                                   "laering": False}})
    return b


def sov(bu, minutter_siden=60, **detaljer):
    return bu.handling("sovn_start", {"minutter_siden": minutter_siden, **detaljer})["hendelse"]


def treff(bu, kilde="barnerom", n=1, sek_mellom=40, start=None, nett=None, type_="grat"):
    t = start or naa()
    res = None
    for i in range(n):
        res = bu.lyd.motta(type_, kilde, nett, t + timedelta(seconds=i * sek_mellom))
    return res


# ---- oppsett ----------------------------------------------------------------

def test_oppsett_validerer_kilde_og_terskler():
    with pytest.raises(UgyldigLydoppsett):
        rens_oppsett({"enheter": [{"kilde": "Ugyldig Navn"}]})
    with pytest.raises(UgyldigLydoppsett):
        rens_oppsett({"enheter": [{"kilde": "a"}, {"kilde": "a"}]})
    with pytest.raises(UgyldigLydoppsett):
        rens_oppsett({"terskel_mulig": 5, "terskel_trolig": 4})
    o = rens_oppsett({"hjemmenett": "Nett1, Nett2 ,", "enheter": [{"kilde": "x", "rolle": "fast"}]})
    assert o["hjemmenett"] == ["Nett1", "Nett2"]
    assert o["enheter"][0]["navn"] == "x"


def test_avslaatt_lagrer_men_teller_ikke(bu):
    bu.lagre_innstillinger({"lyd": {"aktiv": False}})
    sov(bu)
    r = treff(bu)
    assert r["tolkning"] == "avvist" and "slått av" in r["grunn"]


# ---- sperrene -------------------------------------------------------------------

def test_ukjent_enhet_avvises(bu):
    assert treff(bu, "jobbtelefon")["tolkning"] == "avvist"


def test_gråt_mens_våken_påvirker_ikke_søvn(bu):
    assert treff(bu)["tolkning"] == "vaaken"
    assert bu.lyd.forslag() == []


def test_innsovningsvindu(bu):
    sov(bu, minutter_siden=5)
    assert treff(bu)["tolkning"] == "innsovning"


def test_telefon_borte_er_falsk_positiv(bu):
    sov(bu)
    r = treff(bu, "telefon", nett="Jobbnett")
    assert r["tolkning"] == "avvist" and "hjemmenettet" in r["grunn"]


def test_personlig_telefon_hjemme_teller_lite(bu):
    sov(bu)
    r = treff(bu, "telefon", nett="Hjemme5G")
    assert r["tolkning"] == "uro" and r["vekt"] == pytest.approx(0.3)


def test_personlig_uten_nettstatus_avvises(bu):
    sov(bu)
    r = treff(bu, "telefon", nett=None)
    assert r["tolkning"] == "avvist" and "bekrefte" in r["grunn"]


def test_ute_teller_bare_enheter_med_babyen(bu):
    bu.lyd.sett_sted("ute", ["ipad"])
    sov(bu)
    assert treff(bu, "barnerom")["tolkning"] == "avvist"
    r = treff(bu, "ipad", nett="Kafénett")
    assert r["tolkning"] == "uro" and r["vekt"] == pytest.approx(0.5)  # stedsfaktor ute


def test_reise_godtar_reiselytter_uansett_nett(bu):
    bu.lyd.sett_sted("reise", ["ipad"])
    sov(bu)
    assert treff(bu, "ipad", nett="Hotellnett")["vekt"] == pytest.approx(1.0)


def test_vogn_hjemme_teller_bare_enheten_ved_vogna(bu):
    bu.lyd.sett_sted("hjemme_vogn", ["ipad"])
    sov(bu)
    assert treff(bu, "barnerom")["tolkning"] == "avvist"
    assert treff(bu, "ipad", nett="Hjemme5G")["vekt"] == pytest.approx(0.8)


def test_barnevakt_hjemme_bruker_faste_lyttere(bu):
    bu.lyd.sett_sted("barnevakt_hjemme", [])
    sov(bu)
    assert treff(bu, "barnerom")["vekt"] == pytest.approx(1.0)


def test_ukjente_enheter_fjernes_fra_med(bu):
    s = bu.lyd.sett_sted("ute", ["ipad", "finnes_ikke"])
    assert s["med"] == ["ipad"]


# ---- poengsum og forslag ------------------------------------------------------

def test_vedvarende_gråt_gir_forslag(bu):
    sov(bu)
    start = naa()
    r = treff(bu, n=4, start=start)
    assert r["tolkning"] == "trolig"
    f = bu.lyd.forslag()
    assert len(f) == 1 and f[0]["tid"] == start.isoformat()


def test_enkelt_treff_er_bare_uro(bu):
    sov(bu)
    assert treff(bu)["tolkning"] == "uro"
    assert bu.lyd.forslag() == []


def test_to_enheter_samtidig_gir_tillegg(bu):
    sov(bu)
    t = naa()
    treff(bu, "barnerom", start=t)
    r = treff(bu, "android_barnerom", start=t + timedelta(seconds=10))
    assert r["detaljer"].get("flere_enheter") is True
    assert r["poeng"] == pytest.approx(3.0)


def test_motbevis_fra_stua_trekker_poeng(bu):
    sov(bu)
    t = naa()
    treff(bu, "stua", start=t)
    r = treff(bu, "barnerom", n=3, start=t + timedelta(seconds=5), sek_mellom=20)
    assert r["detaljer"]["motbevis"] == 1
    assert r["poeng"] == pytest.approx(2.0)


def test_rop_har_halv_vekt(bu):
    sov(bu)
    assert treff(bu, type_="rop")["vekt"] == pytest.approx(0.5)


def test_stoykilde_hever_terskelen(bu):
    sov(bu, stoykilde="hvit_stoy")
    r = treff(bu, n=4)
    assert r["tolkning"] == "mulig"  # 4 poeng, men terskelen er 5 med støykilde
    assert treff(bu, n=1, start=naa() + timedelta(seconds=200))["tolkning"] == "trolig"


def test_stoykilde_huskes_til_neste_sovn(bu):
    sov(bu, minutter_siden=120, stoykilde="vifte")
    bu.handling("sovn_slutt", {"minutter_siden": 60})
    ny = sov(bu, minutter_siden=30)
    assert ny["detaljer"]["stoykilde"] == "vifte"


def test_svar_vaaknet_avslutter_sovn_ved_forste_treff(bu):
    sov(bu)
    start = naa()
    treff(bu, n=4, start=start)
    f = bu.lyd.forslag()[0]
    bu.lyd.svar(f["id"], "vaaknet", "Test")
    assert bu.db.pagaende("sovn") is None
    h = bu.db.siste("sovn")
    assert h["slutt"] == start.isoformat() and h["detaljer"]["slutt_kilde"] == "lyd"


def test_svar_sovnet_igjen_nullstiller_vinduet(bu):
    sov(bu)
    treff(bu, n=4, start=naa() - timedelta(minutes=3))
    bu.lyd.svar(bu.lyd.forslag()[0]["id"], "sovnet_igjen")
    assert bu.db.pagaende("sovn") is not None
    # nye treff rett etterpå starter fra null
    assert treff(bu, start=naa() + timedelta(seconds=1))["tolkning"] == "uro"


def test_auto_avslutning_etter_svarfrist(bu):
    sov(bu, minutter_siden=120)
    start = naa()
    treff(bu, n=4, start=start)
    assert bu.lyd.sjekk_frister(naa() + timedelta(minutes=31)) == 1
    h = bu.db.siste("sovn")
    assert h["slutt"] and h["detaljer"]["slutt_kilde"] == "auto"


def test_manuell_vaaknet_lukker_forslag(bu):
    sov(bu)
    treff(bu, n=4)
    bu.handling("sovn_slutt")
    assert bu.lyd.forslag("manuelt_vaaknet")


def test_redigering_beholder_sted_og_slutt_kilde(bu):
    h = sov(bu, sted="vogn")
    treff(bu, n=4)
    bu.lyd.svar(bu.lyd.forslag()[0]["id"], "vaaknet")
    endret = bu.endre(h["id"], {"detaljer": bu.db.hent(h["id"])["detaljer"]})
    assert endret["detaljer"] == {"sted": "vogn", "stoykilde": "ingen", "slutt_kilde": "lyd"}


# ---- læring -------------------------------------------------------------------------

def _lag_forslag(bu, svar: str):
    sov(bu, minutter_siden=60)
    treff(bu, n=4)
    bu.lyd.svar(bu.lyd.forslag()[0]["id"], svar)
    if bu.db.pagaende("sovn"):
        bu.handling("sovn_slutt")


def test_laering_hever_terskel_ved_mange_feil(bu):
    for _ in range(5):
        _lag_forslag(bu, "feil")
    l = bu.lyd.laering(False)
    assert l["antall"] == 5 and l["presisjon"] == 0 and l["justering"] == 1.0
    bu.lagre_innstillinger({"lyd": {"laering": True}})
    pag = sov(bu)
    assert bu.lyd.terskler(pag) == (2.0, 5.0)


def test_laering_senker_terskel_ved_hoy_treffsikkerhet(bu):
    for _ in range(10):
        _lag_forslag(bu, "vaaknet")
    assert bu.lyd.laering()["justering"] == -0.5


# ---- sensorer ---------------------------------------------------------------------------

def test_sensorer_for_sted_og_lyd(bu):
    bu.lyd.sett_sted("ute", ["ipad"])
    sov(bu)
    treff(bu, "ipad", nett="x")
    s = bu.sensorer()
    assert s["sensor.babyuret_sted"]["state"] == "ute"
    assert s["sensor.babyuret_sted"]["attributes"]["med"] == ["ipad"]
    assert s["sensor.babyuret_lyd"]["state"] == "uro"
