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
    assert t == [{"dato": "2026-10-01", "tekst": "KIWI 505 SENTRUM", "belop_ore": -24950},
                 {"dato": "2026-10-02", "tekst": "Lønn", "belop_ore": 4_200_000}]


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
