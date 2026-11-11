"""Tester for Pengeboka. Kjør: python3 -m pytest pengeboka/tests"""
from __future__ import annotations

import io
import json
import os
import sys
import threading
import urllib.request
import zipfile
from datetime import date, timedelta
from pathlib import Path

import pytest

os.environ["PENGEBOKA_DEV"] = "1"
HER = Path(__file__).resolve().parent
sys.path.insert(0, str(HER.parent / "app"))
sys.path.insert(0, str(HER))

import eksempel  # noqa: E402
import fil  # noqa: E402
import regler  # noqa: E402
from db import Database  # noqa: E402
from logikk import Feil, Pengeboka  # noqa: E402

I_DAG = date(2026, 11, 20)


@pytest.fixture
def pb(tmp_path, monkeypatch):
    p = Pengeboka(Database(tmp_path / "t.db"))
    monkeypatch.setattr(p, "i_dag", lambda: I_DAG)
    return p


def konto(pb, navn, typ="felles", skjult=False):
    return pb.lagre_konto({"navn": navn, "type": typ, "skjult": skjult})["id"]


def csv(rader):
    return eksempel.csv_dnb([(date.fromisoformat(d), t, o) for d, t, o in rader])


def kat(pb, tid):
    return pb.transaksjon(tid)["kategori"]


def tx(pb, **q):
    return pb.transaksjoner({"skjulte": 1, "overforinger": 1, **q})["transaksjoner"]


# ---------------------------------------------------------------- filer
def test_belop_og_dato():
    assert fil.tolk_belop("-1 234,56") == -123456
    assert fil.tolk_belop("1.234,56") == 123456
    assert fil.tolk_belop("(249,00)") == -24900
    assert fil.tolk_belop("12,50-") == -1250
    assert fil.tolk_belop("abc") is None
    assert fil.tolk_dato("14.10.2026") == date(2026, 10, 14)
    assert fil.tolk_dato("14/10/26") == date(2026, 10, 14)
    assert fil.tolk_dato(46000) == date(2025, 12, 9)
    assert fil.tolk_dato("31.02.2026") is None


def test_gjenkjenner_dnb_format_med_ut_og_inn():
    rader = fil.les(csv([("2026-10-01", "KIWI 505 SENTRUM", -24900), ("2026-10-02", "Lønn", 4_000_000)]))
    o = fil.gjett_oppsett(rader)
    assert o == {"overskrift": 0, "kolonner": {"dato": 0, "tekst": 1, "ut": 3, "inn": 4}}
    t = fil.tolk_rader(rader, o)["transaksjoner"]
    assert [x["belop_ore"] for x in t] == [4_000_000, -24900]


def test_gjenkjenner_ett_belopsfelt_og_komma():
    data = eksempel.csv_enkel([(date(2026, 10, 1), "XXL OSLO", -48200), (date(2026, 10, 3), "Innbetaling", 48200)])
    rader = fil.les(data)
    o = fil.gjett_oppsett(rader)
    assert o["kolonner"] == {"dato": 0, "tekst": 1, "belop": 2}
    assert [x["belop_ore"] for x in fil.tolk_rader(rader, o)["transaksjoner"]] == [-48200, 48200]


def test_fil_uten_overskrift_og_med_tekstlinjer_over():
    data = "Kontoutskrift\nKonto: brukskonto\n\n01.10.2026;KIWI 505;-249,00\n02.10.2026;REMA 1000;-100,50\n".encode()
    rader = fil.les(data)
    o = fil.gjett_oppsett(rader)
    t = fil.tolk_rader(rader, o)
    assert [x["belop_ore"] for x in t["transaksjoner"]] == [-24900, -10050]


def _xlsx(rader):
    def celle(ref, v):
        if isinstance(v, (int, float)):
            return f'<c r="{ref}"><v>{v}</v></c>'
        return f'<c r="{ref}" t="inlineStr"><is><t>{v}</t></is></c>'
    xml = "".join(f'<row r="{i + 1}">' + "".join(celle(f"{chr(65 + j)}{i + 1}", v) for j, v in enumerate(r)) + "</row>"
                  for i, r in enumerate(rader))
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("xl/worksheets/sheet1.xml",
                   f'<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><sheetData>{xml}</sheetData></worksheet>')
    return buf.getvalue()


def test_excel():
    data = _xlsx([["Dato", "Forklaring", "Rentedato", "Ut fra konto", "Inn på konto"],
                  [46296, "KIWI 505 SENTRUM", 46296, 249.5, ""], [46297, "Lønn", 46297, "", 42000]])
    rader = fil.les(data)
    t = fil.tolk_rader(rader, fil.gjett_oppsett(rader))["transaksjoner"]
    assert [(x["dato"], x["tekst"], x["belop_ore"]) for x in t] == [("2026-10-01", "KIWI 505 SENTRUM", -24950),
                                                                    ("2026-10-02", "Lønn", 4_200_000)]


def test_pdf_avvises():
    with pytest.raises(fil.Filfeil):
        fil.les(b"%PDF-1.7 ...")


# ---------------------------------------------------------------- regler
def test_motpart_og_kategori():
    assert regler.motpart("Visa 4925 12.10 NOK 249,00 KIWI 505 SENTRUM Kurs: 1.0000") == "Kiwi"
    assert regler.motpart("Varekjøp REMA 1000 TORGET DATO 14.10") == "Rema 1000"
    assert regler.motpart("*4925 14.10 NOK 89.00 FRISØR HÅRSTUDIO 123 SENTRUM") == "Frisør Hårstudio"
    assert regler.motpart("Vipps*Ola Nordmann") == "Vipps: Ola Nordmann"
    assert regler.kategoriser("AvtaleGiro TIBBER NORGE AS", -100, []) == ("Strøm", None)
    assert regler.kategoriser("Kiwiplanter AS", -100, []) == (None, None)
    assert regler.kategoriser("Lønn fra ARBEIDSGIVER", 100, []) == ("Lønn", None)
    assert regler.kategoriser("Lønn fra ARBEIDSGIVER", -100, []) == (None, None)  # «lønn» ut er ikke lønn
    egen = [{"id": 1, "monster": "kiwi", "kategori": "Annet"}]
    assert regler.kategoriser("KIWI 505", -100, egen) == ("Annet", 1)


# ---------------------------------------------------------------- import
def test_import_hopper_over_duplikater_men_ikke_like_kjop_samme_dag(pb):
    k = konto(pb, "Felles")
    f1 = csv([("2026-10-01", "KIWI 505", -24900), ("2026-10-01", "KIWI 505", -24900), ("2026-10-02", "REMA 1000", -10000)])
    assert pb.importer(f1, "a.csv", k, None, "A")["nye"] == 3
    f2 = csv([("2026-10-02", "REMA 1000", -10000), ("2026-10-03", "COOP EXTRA", -5000)])
    r = pb.importer(f2, "b.csv", k, None, "B")
    assert (r["nye"], r["duplikater"]) == (1, 1)
    assert pb.forhandsvis(f1, k)["nye"] == 0


def test_import_krever_konto_og_kan_angres(pb):
    with pytest.raises(Feil):
        pb.importer(csv([("2026-10-01", "KIWI", -100)]), "a.csv", 999, None, None)
    k = konto(pb, "Felles")
    pb.importer(csv([("2026-10-01", "KIWI", -100)]), "a.csv", k, None, "A")
    iid = pb.importer_liste()[0]["id"]
    assert pb.angre_import(iid) == 1
    assert tx(pb) == []


# ---------------------------------------------------------------- overføringer
@pytest.fixture
def familie(pb):
    ids = {"felles": konto(pb, "Felles"), "kort": konto(pb, "Kort", "kreditt"),
           "spar": konto(pb, "Spar", "sparing", skjult=True), "lan": konto(pb, "Boliglån", "lan", skjult=True)}
    pb.importer(csv([
        ("2026-10-25", "Lønn fra ARBEIDSGIVER", 4_000_000),
        ("2026-10-26", "Overføring til sparekonto", -500_000),
        ("2026-10-18", "Betaling kredittkort", -120_000),
        ("2026-10-01", "Avtalegiro lån", -1_500_000),
        ("2026-10-28", "Overføring fra sparekonto", 200_000),
        ("2026-10-05", "KIWI 505", -80_000),
    ]), "f.csv", ids["felles"], None, "A")
    pb.importer(csv([("2026-10-19", "Innbetaling", 120_000), ("2026-10-10", "XXL OSLO", -120_000)]), "k.csv", ids["kort"], None, "A")
    pb.importer(csv([("2026-10-26", "Fra brukskonto", 500_000), ("2026-10-28", "Til brukskonto", -200_000)]), "s.csv", ids["spar"], None, "A")
    pb.importer(csv([("2026-10-01", "Innbetaling", 1_500_000)]), "l.csv", ids["lan"], None, "A")
    return ids


def test_overforinger_telles_riktig(pb, familie):
    m = pb.maned("2026-10")
    assert m["inn"] == 4_000_000
    # Kiwi + XXL på kortet + lånet. Kortbetalingen er ikke forbruk.
    assert m["ut"] == 80_000 + 120_000 + 1_500_000
    assert m["sparing"] == 500_000 - 200_000
    assert m["igjen"] == 4_000_000 - 1_700_000 - 300_000
    kategorier = {t["tekst"]: t["kategori"] for t in tx(pb)}
    assert kategorier["Overføring til sparekonto"] == "Sparing"
    assert kategorier["Overføring fra sparekonto"] == "Sparing"
    assert kategorier["Betaling kredittkort"] == "Overføring"
    assert kategorier["Avtalegiro lån"] == "Lån"
    assert kategorier["XXL OSLO"] == "Fritid og ferie"


def test_skjult_konto_vises_ikke_men_brukes_til_overforinger(pb, familie):
    vanlige = pb.transaksjoner({})["transaksjoner"]
    assert all(t["konto"] in ("Felles", "Kort") for t in vanlige)
    assert not any(t["tekst"] == "Betaling kredittkort" for t in vanlige)  # rene overføringer skjules i lista
    assert any(t["tekst"] == "Overføring til sparekonto" for t in vanlige)  # sparing vises


def test_ikke_en_overforing(pb, familie):
    t = next(t for t in tx(pb) if t["tekst"] == "Betaling kredittkort")
    pb.endre_transaksjon(t["id"], {"ikke_overforing": True}, "B")
    assert pb.transaksjon(t["id"])["par_id"] is None
    pb.finn_overforinger()
    assert pb.transaksjon(t["id"])["par_id"] is None  # blir ikke paret på nytt


# ---------------------------------------------------------------- kategorier og regler
def test_regel_fra_transaksjon_gjelder_alle_og_nye(pb):
    k = konto(pb, "Felles")
    pb.importer(csv([("2026-10-01", "FRISØR HÅRSTUDIO 123 SENTRUM", -50000), ("2026-11-01", "FRISØR HÅRSTUDIO 123 SENTRUM", -55000)]),
                "a.csv", k, None, "A")
    t = tx(pb)[0]
    assert t["kategori"] is None
    hjem = next(c["id"] for c in pb.kategorier() if c["navn"] == "Hjem og klær")
    pb.endre_transaksjon(t["id"], {"kategori_id": hjem, "regel": True}, "Voksen 2")
    assert {x["kategori"] for x in tx(pb)} == {"Hjem og klær"}
    pb.importer(csv([("2026-11-15", "FRISØR HÅRSTUDIO 999 OSLO", -60000)]), "b.csv", k, None, "A")
    assert {x["kategori"] for x in tx(pb)} == {"Hjem og klær"}
    regel = pb.regler()[0]
    assert (regel["monster"], regel["laget_av"], regel["treff"]) == ("frisør hårstudio", "Voksen 2", 2)
    pb.slett_regel(regel["id"])
    assert {x["kategori"] for x in tx(pb)} == {"Hjem og klær", None}  # den manuelle beholdes


def test_manuell_kategori_overstyres_ikke(pb):
    k = konto(pb, "Felles")
    pb.importer(csv([("2026-10-01", "KIWI 505", -24900)]), "a.csv", k, None, "A")
    t = tx(pb)[0]
    annet = next(c["id"] for c in pb.kategorier() if c["navn"] == "Annet")
    pb.endre_transaksjon(t["id"], {"kategori_id": annet}, "A")
    pb.kategoriser_alle()
    assert kat(pb, t["id"]) == "Annet"


# ---------------------------------------------------------------- faste trekk, avvik, budsjett
def test_faste_trekk_og_prisendring(pb):
    k = konto(pb, "Felles")
    rader = []
    for i, m in enumerate(range(5, 12)):
        rader.append((f"2026-{m:02d}-12", "Visa NETFLIX.COM", -16900 if m < 11 else -19900))
        rader.append((f"2026-{m:02d}-03", "AvtaleGiro TIBBER", -(150_000 + i * 20_000)))
        rader.append((f"2026-{m:02d}-{10 + i}", "KIWI 505", -60_000))
    pb.importer(csv(rader), "a.csv", k, None, "A")
    faste = {f["motpart"]: f for f in pb.faste()}
    assert faste["Netflix"]["hyppighet"] == "måned" and faste["Netflix"]["fast_belop"]
    assert faste["Netflix"]["endring"] == {"fra": 16900, "til": 19900}
    assert "Tibber" in faste and not faste["Tibber"]["fast_belop"]
    trenger = pb.trenger()
    assert any(t["type"] == "pris" and "Netflix" in t["tekst"] for t in trenger)
    pb.avvis(next(t["nokkel"] for t in trenger if t["type"] == "pris"))
    assert not any(t["type"] == "pris" for t in pb.trenger())
    pb.merk_fast("Netflix", "nei")
    assert "Netflix" not in {f["motpart"] for f in pb.faste()}


def test_avvik_og_budsjett(pb):
    k = konto(pb, "Felles")
    rader = [(f"2026-{m:02d}-05", "AvtaleGiro TIBBER", -200_000) for m in range(6, 11)]
    rader.append(("2026-11-05", "AvtaleGiro TIBBER", -700_000))
    rader += [(f"2026-{m:02d}-{d:02d}", "KIWI 505", -100_000) for m in (8, 9, 10) for d in (2, 9, 16, 23)]
    pb.importer(csv(rader), "a.csv", k, None, "A")
    assert any(t["type"] == "avvik" and "Tibber" in t["tekst"] for t in pb.trenger())
    forslag = pb.foresla_budsjett()
    dagligvarer = next(c["id"] for c in pb.kategorier() if c["navn"] == "Dagligvarer")
    assert forslag[dagligvarer] == 4000
    pb.lagre_budsjett({str(dagligvarer): "4000", })
    strom = next(c["id"] for c in pb.kategorier() if c["navn"] == "Strøm")
    pb.lagre_budsjett({str(strom): 2500})
    assert any(t["type"] == "over" and "Strøm" in t["tekst"] for t in pb.trenger())


def test_import_paminnelse(pb):
    k = konto(pb, "Felles")
    pb.importer(csv([("2026-09-01", "KIWI", -100)]), "a.csv", k, None, "A")
    assert any(t["type"] == "import" for t in pb.trenger())


# ---------------------------------------------------------------- finne kontoen selv
BRUK, SPAR, ANNEN = "1111 22 33001", "1111 22 33004", "9001 00 00001"


def _liste(konto, rader, reservert=()):
    return eksempel.csv_transaksjonsliste(konto, [(date.fromisoformat(d), t, o, m) for d, t, o, m in rader],
                                          [(date.fromisoformat(d), t, o, m) for d, t, o, m in reservert])


def test_transaksjonsliste_format():
    data = _liste(BRUK, [("2026-10-05", "KIWI 505 SENTRUM", -8850, None), ("2026-10-25", "Lønn", 4_200_000, ANNEN)],
                  reservert=[("2026-10-30", "REMA 1000 TORGET", -5300, None)])
    rader = fil.les(data)
    o = fil.gjett_oppsett(rader)
    assert o["overskrift"] == 0
    assert o["kolonner"] == {"dato": 0, "tekst": 3, "ut": 11, "inn": 10, "status": 13, "fra": 6, "til": 8}
    t = fil.tolk_rader(rader, o)
    assert [(x["dato"], x["belop_ore"], x["konto_nr"], x["motkonto"]) for x in t["transaksjoner"]] == [
        ("2026-10-25", 4_200_000, "11112233001", "90010000001"), ("2026-10-05", -8850, "11112233001", None)]
    assert t["reservert"] == 1  # den reserverte raden og bunnteksten er ikke med
    assert fil.finn_kontonummer(rader, t["transaksjoner"]) == "11112233001"


def test_kontonummer_i_filnavn_eller_toppen():
    rader = fil.les("Kontoutskrift for 1111.22.33001\nDato;Tekst;Beløp\n01.10.2026;KIWI;-10,00\n".encode())
    assert fil.finn_kontonummer(rader, []) == "11112233001"
    assert fil.finn_kontonummer([], [], "Transaksjoner 1111 22 33004 okt.csv") == "11112233004"
    assert fil.finn_kontonummer([], [], "Transaksjonsliste-07-11-25-07-11-26.csv") is None


def test_finner_konto_fra_kontonummer_og_laerer_det(pb):
    data = _liste(BRUK, [("2026-10-05", "KIWI 505", -8850, None)])
    f = pb.forhandsvis(data, None)
    assert (f["konto"], f["kontonummer"], f["kontonummer_vis"]) == (None, "11112233001", "1111 22 33001")
    k = pb.lagre_konto({"navn": "Brukskonto", "type": "bruk", "nummer": f["kontonummer"]})
    assert k["nummer_vis"] == "1111 22 33001"
    f = pb.forhandsvis(data, None)
    assert f["konto"] == {"id": k["id"], "grunn": "kontonummer"} and f["nye"] == 1
    r = pb.importer(data, "x.csv", None, None, "A")  # ingen konto valgt – appen finner den
    assert (r["konto_id"], r["nye"]) == (k["id"], 1)
    with pytest.raises(Feil):
        pb.lagre_konto({"navn": "Dobbel", "nummer": BRUK})


def test_finner_konto_fra_tidligere_import_uten_nummer(pb):
    k = konto(pb, "Felles")
    pb.importer(csv([("2026-10-01", "KIWI 505", -100), ("2026-10-02", "REMA 1000", -200), ("2026-10-03", "COOP", -300)]),
                "a.csv", k, None, "A")
    f = pb.forhandsvis(csv([("2026-10-02", "REMA 1000", -200), ("2026-10-03", "COOP", -300), ("2026-10-04", "KIWI", -50),
                            ("2026-10-01", "KIWI 505", -100)]), None)
    assert f["konto"] == {"id": k, "grunn": "tidligere"} and f["nye"] == 1
    assert pb.forhandsvis(csv([("2026-11-01", "Helt ny", -100)]), None)["konto"] is None


def test_feil_konto_stoppes(pb):
    pb.lagre_konto({"navn": "Spar", "type": "sparing", "nummer": SPAR})
    annen = konto(pb, "Bruk", "bruk")
    pb.lagre_konto({"navn": "Bruk", "type": "bruk", "nummer": BRUK}, annen)
    with pytest.raises(Feil):
        pb.importer(_liste(SPAR, [("2026-10-05", "Renter", 100, None)]), "x.csv", annen, None, "A")


def test_overforing_til_egen_konto_som_ikke_er_importert_enna(pb):
    b = pb.lagre_konto({"navn": "Bruk", "type": "bruk", "nummer": BRUK})["id"]
    pb.lagre_konto({"navn": "Spar", "type": "sparing", "nummer": SPAR, "skjult": True})
    pb.importer(_liste(BRUK, [("2026-10-26", "Til sparing", -500_000, SPAR), ("2026-10-27", "Vipps", -500_000, ANNEN)]),
                "b.csv", None, None, "A")
    kats = {t["tekst"]: (t["kategori"], t["par_id"]) for t in tx(pb)}
    assert kats["Til sparing"] == ("Sparing", None)       # egen konto, selv om sparekontoen ikke er importert
    assert kats["Vipps"][0] != "Sparing"                  # et annet kontonummer er ikke en overføring
    # Når sparekontoen importeres, pares de
    pb.importer(_liste(SPAR, [("2026-10-26", "Fra brukskonto", 500_000, BRUK)]), "s.csv", None, None, "A")
    t = next(t for t in tx(pb) if t["tekst"] == "Til sparing")
    assert t["kategori"] == "Sparing" and t["par_id"]
    assert pb.maned("2026-10")["sparing"] == 500_000
    assert b


# ---------------------------------------------------------------- server
@pytest.fixture
def server(tmp_path):
    import main
    srv = main.start(0, tmp_path / "s.db")
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{srv.server_address[1]}", main
    srv.shutdown()


def _hent(url, data=None, metode=None, hoder=None):
    req = urllib.request.Request(url, data=data, method=metode, headers=hoder or {})
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    try:
        with opener.open(req) as r:
            return r.status, r.read()
    except urllib.error.HTTPError as e:
        return e.code, e.read()


def test_server_api_og_import(server):
    url, _ = server
    s, b = _hent(f"{url}/api/kontoer", json.dumps({"navn": "Felles", "type": "felles"}).encode(), "POST",
                 {"Content-Type": "application/json", "X-Remote-User-Display-Name": "Voksen 2"})
    assert s == 200
    kid = json.loads(b)["konto"]["id"]
    data = csv([("2026-10-01", "KIWI 505", -24900)])
    s, b = _hent(f"{url}/api/import?konto={kid}", data, "POST", {"X-Filnavn": "test%20fil.csv"})
    assert s == 200 and json.loads(b)["nye"] == 1
    s, b = _hent(f"{url}/api/kontoer")
    assert json.loads(b)["importer"][0]["av"] is None  # ingen brukerhode på denne
    s, b = _hent(f"{url}/api/eksport.csv")
    assert s == 200 and "Kiwi" in b.decode("utf-8-sig")


def test_server_sperrer(server, monkeypatch):
    url, main = server
    assert _hent(f"{url}/static/../db.py")[0] == 404
    assert _hent(f"{url}/static/%2e%2e/db.py")[0] == 404
    assert _hent(f"{url}/api/finnes-ikke")[0] == 404
    s, b = _hent(f"{url}/api/kontoer", b"{ikke json", "POST", {"Content-Type": "application/json"})
    assert s == 400
    monkeypatch.setattr(main, "UTVIKLING", False)
    assert _hent(f"{url}/api/oversikt")[0] == 403  # bare Home Assistant-ingress slipper inn


# ---------------------------------------------------------------- kvitteringer fra Matplan
import matplan  # noqa: E402


def _t(id_, dato, ore, motpart):
    return {"id": id_, "dato": dato, "belop_ore": ore, "motpart": motpart, "tekst": motpart}


def _k(id_, dato, ore, butikk):
    return {"matplan_id": id_, "dato": dato, "total_ore": ore, "butikk": butikk}


def test_match_kvitteringer():
    tx = [_t(1, "2026-10-05", -24900, "Kiwi"), _t(2, "2026-10-05", -24900, "Rema 1000"),
          _t(3, "2026-10-09", -54050, "Coop Extra"), _t(4, "2026-10-20", -99900, "Oda"),
          _t(5, "2026-10-12", -10000, "Vipps: Ola"), _t(6, "2026-10-01", -30000, "Kiwi")]
    kv = [_k(10, "2026-10-04", 24900, "Kiwi"),             # Kiwi, dagen før → tx 1, ikke Rema (tx 2)
          _k(11, "2026-10-08", 54000, "Coop"),             # 50 øre avvik, Coop ~ Coop Extra → tx 3
          _k(12, "2026-10-15", 99900, "Oda"),              # Oda belastes ved levering, 5 dager senere → tx 4
          _k(13, "2026-10-12", 10000, "Ukjent butikk"),    # ukjent kjede, men helt likt og samme dag → tx 5
          _k(14, "2026-10-10", 30000, "Kiwi")]             # 9 dager unna tx 6 → ingen
    assert matplan.match(tx, kv) == {1: 10, 3: 11, 4: 12, 5: 13}
    assert matplan.kjede("COOP EXTRA STASJONEN") == matplan.kjede("Coop") == "coop"
    assert matplan.kjede("Rema 1000") == "rema" and matplan.kjede("Frisør") is None


def test_match_en_til_en():
    tx = [_t(1, "2026-10-05", -5000, "Kiwi"), _t(2, "2026-10-06", -5000, "Kiwi")]
    kv = [_k(10, "2026-10-06", 5000, "Kiwi"), _k(11, "2026-10-05", 5000, "Kiwi")]
    assert matplan.match(tx, kv) == {1: 11, 2: 10}


class _FalskMatplan:
    """Liten etterligning av Matplans koblingsgrensesnitt."""
    def __init__(self, kvitteringer, kode="hemmelig"):
        import http.server
        self.kv, self.kode, self.mottatt, self.forsok = kvitteringer, kode, None, []
        meg = self

        class H(http.server.BaseHTTPRequestHandler):
            def log_message(self, *a):
                pass

            def _svar(self, kode, obj):
                b = json.dumps(obj).encode()
                self.send_response(kode)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(b)

            def _ok(self):
                meg.forsok.append((self.command, self.path))
                return self.headers.get("Authorization") == f"Bearer {meg.kode}"

            def do_GET(self):
                if not self._ok():
                    return self._svar(401, {"error": "Feil koblingskode"})
                if self.path.startswith("/kobling/kvitteringer?"):
                    return self._svar(200, {"kvitteringer": meg.kv})
                if self.path.startswith("/kobling/kvitteringer/"):
                    return self._svar(200, {"id": 1, "varer": [{"navn": "TINE HELMELK", "produkt": "Melk", "antall": 2, "pris": 49.8}]})
                self._svar(404, {})

            def do_PUT(self):
                if not self._ok():
                    return self._svar(401, {})
                meg.mottatt = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
                self._svar(200, {"ok": True})
        self.srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), H)
        threading.Thread(target=self.srv.serve_forever, daemon=True).start()
        self.url = f"http://127.0.0.1:{self.srv.server_address[1]}"


def test_synk_med_matplan(pb):
    k = konto(pb, "Felles")
    pb.importer(csv([("2026-10-05", "Varekjøp KIWI 505 SENTRUM", -24900), ("2026-10-09", "Varekjøp REMA 1000 TORGET", -54000),
                     ("2026-10-25", "Varekjøp COOP EXTRA", -31000), ("2026-10-26", "Lønn", 4_000_000)]), "a.csv", k, None, "A")
    falsk = _FalskMatplan([{"id": 7, "store": "Kiwi", "purchased_on": "2026-10-05", "total": 249.0, "varer": 12},
                           {"id": 8, "store": "Rema 1000", "purchased_on": "2026-10-09", "total": 999.0, "varer": 3},
                           {"id": 9, "store": "Coop", "purchased_on": "2026-11-30", "total": 50.0, "varer": 1}])
    with pytest.raises(matplan.Matplanfeil, match="koblingskoden"):
        matplan.synk(pb.db, falsk.url, "feil")
    pb.db.sett_innstilling("matplan_url", falsk.url)
    pb.db.sett_innstilling("matplan_kode", "hemmelig")
    st = matplan.synk(pb.db)
    assert (st["kvitteringer"], st["koblet"], st["kjop"], st["uten_kvittering"]) == (3, 1, 3, 2)
    # Svaret til Matplan: Kiwi funnet, Rema mangler (beløpet stemmer ikke), Coop 30. nov er etter siste bankdato → ikke vurdert
    assert falsk.mottatt["koblinger"] == [
        {"kvittering": 7, "status": "funnet", "dato": "2026-10-05", "konto": "Felles", "belop": 249.0},
        {"kvittering": 8, "status": "mangler"}]
    assert falsk.mottatt["dekket_til"] == "2026-10-26"
    rader = {t["motpart"]: t for t in pb.transaksjoner({})["transaksjoner"]}
    assert rader["Kiwi"]["kvittering"] == 7 and not rader["Kiwi"]["kvittering_mangler"]
    assert rader["Rema 1000"]["kvittering_mangler"] and rader["Coop Extra"]["kvittering_mangler"]
    assert not rader["Lønn"]["kvittering_mangler"]
    assert [t["motpart"] for t in pb.transaksjoner({"kvittering": "har"})["transaksjoner"]] == ["Kiwi"]
    assert {t["motpart"] for t in pb.transaksjoner({"kvittering": "mangler"})["transaksjoner"]} == {"Rema 1000", "Coop Extra"}
    t = pb.transaksjon(rader["Kiwi"]["id"])
    assert t["kvittering"]["butikk"] == "Kiwi" and t["kvittering"]["varer"] == 12
    assert matplan.hent_kvittering(pb.db, 7)["varer"][0]["produkt"] == "Melk"
    dag = next(c for c in pb.maned("2026-10")["kategorier"] if c["navn"] == "Dagligvarer")
    assert dag["kvitteringer"] == {"av": 3, "har": 1}


def test_matplan_ikke_tilkoblet_viser_ingenting(pb):
    k = konto(pb, "Felles")
    pb.importer(csv([("2026-10-05", "KIWI 505", -24900)]), "a.csv", k, None, "A")
    t = pb.transaksjoner({})["transaksjoner"][0]
    assert t["kvittering"] is None and not t["kvittering_mangler"]
    with pytest.raises(matplan.Matplanfeil, match="ikke koblet"):
        matplan.synk(pb.db)
