"""Automatisk henting fra banken – mot en falsk Enable Banking-server."""
from __future__ import annotations

import base64
import hashlib
import http.server
import json
import subprocess
import threading
import urllib.parse
from datetime import datetime, timedelta, timezone

import pytest

from test_pengeboka import I_DAG, csv, konto, pb, tx  # noqa: F401  (pb er en fixture)

import bank  # noqa: E402

FELLES = "12345678903"   # syntetiske kontonumre
SPARE = "98765432109"


def _ny_nokkel(tmp_path, pkcs1=False) -> str:
    sti = tmp_path / "n.pem"
    if pkcs1:
        subprocess.run(["openssl", "genrsa", "-traditional", "-out", str(sti), "2048"], check=True, capture_output=True)
    else:
        subprocess.run(["openssl", "genpkey", "-algorithm", "RSA", "-pkeyopt", "rsa_keygen_bits:2048", "-out", str(sti)],
                       check=True, capture_output=True)
    return sti.read_text()


@pytest.mark.parametrize("pkcs1", [False, True])
def test_rs256_godkjennes_av_openssl(tmp_path, pkcs1):
    pem = _ny_nokkel(tmp_path, pkcs1)
    assert ("BEGIN RSA PRIVATE KEY" in pem) == pkcs1
    data = b"hode.innhold"
    (tmp_path / "sig").write_bytes(bank.signer(bank.les_nokkel(pem), data))
    (tmp_path / "data").write_bytes(data)
    subprocess.run(["openssl", "pkey", "-in", str(tmp_path / "n.pem"), "-pubout", "-out", str(tmp_path / "pub.pem")], check=True)
    r = subprocess.run(["openssl", "dgst", "-sha256", "-verify", str(tmp_path / "pub.pem"), "-signature",
                        str(tmp_path / "sig"), str(tmp_path / "data")], capture_output=True, text=True)
    assert "Verified OK" in r.stdout


def test_feil_nokkel_gir_forstaelig_feil():
    for tekst in ("", "hei", "-----BEGIN ENCRYPTED PRIVATE KEY-----\nabc\n-----END ENCRYPTED PRIVATE KEY-----",
                  "-----BEGIN PRIVATE KEY-----\nAAAA\n-----END PRIVATE KEY-----"):
        with pytest.raises(bank.Bankfeil):
            bank.les_nokkel(tekst)


def _tx(id_, dato, belop, tekst, status="BOOK", **ekstra):
    return {"transaction_id": id_, "booking_date": dato, "transaction_amount": {"amount": f"{abs(belop) / 100:.2f}", "currency": "NOK"},
            "credit_debit_indicator": "DBIT" if belop < 0 else "CRDT", "status": status,
            "remittance_information": [tekst] if tekst else [], **ekstra}


class FalskBank:
    def __init__(self, pem: str, app_id="app-123"):
        self.n = bank.les_nokkel(pem)
        self.app_id, self.koder, self.slettet, self.kall = app_id, {"kode-ok"}, [], []
        self.redirects = ["https://localhost/"]
        self.feil_konto: dict[str, tuple[int, dict]] = {}
        self.tx = {
            "uid-felles": [_tx("t1", "2026-10-02", -24900, "Varekjøp KIWI 505 SENTRUM"),
                           _tx("t2", "2026-10-03", -7500, "Vipps:Ruter"),
                           _tx("t3", "2026-10-05", -99900, "", creditor={"name": "Strømselskapet AS"}),
                           _tx("t4", "2026-10-06", 4_000_000, "Lønn"),
                           _tx("t5", "2026-10-07", -12000, "REMA 1000", status="PDNG")],
            "uid-spare": [_tx("s1", "2026-10-06", 500_000, "Overføring")]}
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

            def _sjekk(self):
                tok = (self.headers.get("Authorization") or "")[7:]
                h, i, s = tok.split(".")
                pad = lambda x: base64.urlsafe_b64decode(x + "=" * (-len(x) % 4))
                hode, innhold = json.loads(pad(h)), json.loads(pad(i))
                k = (meg.n["n"].bit_length() + 7) // 8
                em = pow(int.from_bytes(pad(s), "big"), meg.n["e"], meg.n["n"]).to_bytes(k, "big")
                ok = (hode == {"typ": "JWT", "alg": "RS256", "kid": meg.app_id} and innhold["aud"] == "api.enablebanking.com"
                      and innhold["iss"] == "enablebanking.com" and 0 < innhold["exp"] - innhold["iat"] <= 86400
                      and em.endswith(hashlib.sha256(f"{h}.{i}".encode()).digest()))
                meg.kall.append((self.command, self.path))
                return ok

            def _kropp(self):
                n = int(self.headers.get("Content-Length") or 0)
                return json.loads(self.rfile.read(n)) if n else {}

            def do_GET(self):
                if not self._sjekk():
                    return self._svar(401, {"error": "UNAUTHORIZED"})
                u = urllib.parse.urlparse(self.path)
                q = dict(urllib.parse.parse_qsl(u.query))
                if u.path == "/application":
                    return self._svar(200, {"name": "Pengeboka", "environment": "PRODUCTION", "active": True,
                                            "redirect_urls": meg.redirects})
                if u.path == "/aspsps":
                    assert q == {"country": "NO", "psu_type": "personal"}
                    return self._svar(200, {"aspsps": [{"name": "Nordea", "country": "NO"},
                                                       {"name": "DNB", "country": "NO", "maximum_consent_validity": 15552000}]})
                if u.path.startswith("/accounts/") and u.path.endswith("/transactions"):
                    uid = u.path.split("/")[2]
                    if uid in meg.feil_konto:
                        return self._svar(*meg.feil_konto[uid])
                    assert q.get("transaction_status") == "BOOK"
                    alle = [t for t in meg.tx[uid] if t["booking_date"] >= q["date_from"]]
                    side = int(q.get("continuation_key") or 0)   # to per side → tester blaing
                    neste = side + 2 if side + 2 < len(alle) else None
                    return self._svar(200, {"transactions": alle[side:side + 2],
                                            "continuation_key": str(neste) if neste else None})
                self._svar(404, {})

            def do_POST(self):
                if not self._sjekk():
                    return self._svar(401, {})
                d = self._kropp()
                if self.path == "/auth":
                    assert d["aspsp"] == {"name": "DNB", "country": "NO"} and d["psu_type"] == "personal"
                    assert d["redirect_url"] == "https://localhost/"
                    gyldig = datetime.fromisoformat(d["access"]["valid_until"])
                    assert timedelta(days=170) < gyldig - datetime.now(timezone.utc) < timedelta(days=180)
                    meg.state = d["state"]
                    return self._svar(200, {"url": "https://tilisy.enablebanking.com/welcome?x=1"})
                if self.path == "/sessions":
                    if d.get("code") not in meg.koder:
                        return self._svar(422, {"error": "WRONG_AUTH_CODE", "message": "Wrong code"})
                    return self._svar(200, {"session_id": "okt-1", "access": {"valid_until": "2027-05-01T00:00:00+00:00"},
                                            "accounts": [
                                                {"uid": "uid-felles", "account_id": {"iban": "NO93" + FELLES}, "name": "Felleskonto",
                                                 "cash_account_type": "CACC"},
                                                {"uid": "uid-spare", "account_id": {"other": {"identification": SPARE}},
                                                 "name": "Høyrente", "cash_account_type": "SVGS"}]})
                self._svar(404, {})

            def do_DELETE(self):
                self._sjekk()
                meg.slettet.append(self.path)
                self._svar(200, {"message": "OK"})
        self.srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), H)
        threading.Thread(target=self.srv.serve_forever, daemon=True).start()
        self.url = f"http://127.0.0.1:{self.srv.server_address[1]}"


@pytest.fixture
def falsk(pb, tmp_path):  # noqa: F811
    pem = _ny_nokkel(tmp_path)
    f = FalskBank(pem)
    pb.db.sett_innstilling("bank_api", f.url)
    f.pem = pem
    return f


def test_oppsett(pb, falsk):  # noqa: F811
    with pytest.raises(bank.Bankfeil, match="app-ID"):
        bank.sett_opp(pb.db, "", falsk.pem)
    with pytest.raises(bank.Bankfeil, match="hører sammen"):
        bank.sett_opp(pb.db, "feil-app", falsk.pem)
    with pytest.raises(bank.Bankfeil, match="Allowed redirect"):
        bank.sett_opp(pb.db, "app-123", falsk.pem, "https://annen.no/")
    s = bank.sett_opp(pb.db, "app-123", falsk.pem)
    assert s["satt_opp"] and s["app"]["navn"] == "Pengeboka" and "nokkel" not in json.dumps(s).lower().replace("satt_opp", "")
    assert [b["navn"] for b in bank.banker(pb.db)] == ["DNB", "Nordea"]


def test_hele_flyten_uten_dobbeltforing(pb, falsk):  # noqa: F811
    # Felleskontoen finnes fra før, med to kjøp importert fra fil (litt annen tekst og dato enn i banken)
    k = pb.lagre_konto({"navn": "Felles", "type": "felles", "nummer": FELLES})["id"]
    pb.importer(csv([("2026-10-01", "KIWI 505 SENTRUM", -24900), ("2026-10-03", "Vipps*Ruter", -7500)]), "a.csv", k, None, "A")
    bank.sett_opp(pb.db, "app-123", falsk.pem)
    url = bank.start(pb.db, "DNB", "Voksen 1")["url"]
    assert url.startswith("https://")
    with pytest.raises(bank.Bankfeil, match="hører ikke til"):
        bank.fullfor(pb.db, pb, "https://localhost/?code=kode-ok&state=feil", "Voksen 1")
    with pytest.raises(bank.Bankfeil, match="avbrøt"):
        bank.fullfor(pb.db, pb, "https://localhost/?error=access_denied&state=" + falsk.state, "Voksen 1")
    s = bank.fullfor(pb.db, pb, f"https://localhost/?code=kode-ok&state={falsk.state}", "Voksen 1")
    okt = s["okter"][0]
    assert okt["bank"] == "DNB" and not okt["utlopt"] and okt["dager_igjen"] > 100
    kontoer = {b["navn"]: b for b in okt["kontoer"]}
    assert kontoer["Felleskonto"]["konto_id"] == k                       # funnet på kontonummeret
    ny = kontoer["Høyrente"]["konto_id"]
    assert ny and pb.db.rad("SELECT type, nummer FROM kontoer WHERE id = ?", (ny,)) == {"type": "sparing", "nummer": SPARE}

    rader = tx(pb, konto=str(k))
    assert len(rader) == 4                       # 2 fra fil (paret med banken) + strøm + lønn; reservert kjøp er ikke med
    assert {r["motpart"] for r in rader} >= {"Kiwi", "Strømselskapet"}
    assert pb.db.verdi("SELECT COUNT(*) FROM transaksjoner WHERE konto_id = ? AND bank_ref IS NOT NULL", (k,)) == 4
    assert len(tx(pb, konto=str(ny))) == 1

    # Ny henting gir ingenting nytt, heller ikke når samme fil importeres igjen
    assert bank.hent(pb.db, pb)["nye"] == 0
    assert pb.importer(csv([("2026-10-01", "KIWI 505 SENTRUM", -24900), ("2026-10-03", "Vipps*Ruter", -7500)]),
                       "a.csv", k, None, "A")["nye"] == 0
    # …og en fil med kjøp banken allerede har gitt, kobles til dem i stedet for å bli dobbelt
    r = pb.importer(csv([("2026-10-05", "AvtaleGiro STRØMSELSKAPET", -99900), ("2026-10-20", "Kiwi", -5000)]), "b.csv", k, None, "A")
    assert r["nye"] == 1 and len(tx(pb, konto=str(k))) == 5
    # Den reserverte blir bokført → kommer med neste gang
    falsk.tx["uid-felles"][4]["status"] = "BOOK"
    assert bank.hent(pb.db, pb)["nye"] == 1

    # Utløpt samtykke vises i «Trenger dere»
    falsk.feil_konto = {"uid-felles": (422, {"error": "EXPIRED_SESSION"}), "uid-spare": (422, {"error": "EXPIRED_SESSION"})}
    with pytest.raises(bank.Bankfeil, match="gått ut"):
        bank.hent(pb.db, pb)
    assert any(t["type"] == "bank" and "gått ut" in t["tekst"] for t in pb.trenger())

    bank.koble_fra(pb.db, "okt-1")
    assert falsk.slettet == ["/sessions/okt-1"] and not bank.status(pb.db)["okter"]
    assert len(tx(pb, konto=str(k))) == 6        # transaksjonene blir liggende


def test_varsel_for_samtykket_gar_ut(pb, falsk):  # noqa: F811
    bank.sett_opp(pb.db, "app-123", falsk.pem)
    bank.start(pb.db, "DNB", None)
    bank.fullfor(pb.db, pb, f"https://localhost/?code=kode-ok&state={falsk.state}", None)
    snart = (datetime.now(timezone.utc) + timedelta(days=5, hours=2)).isoformat()
    pb.db.kjor("UPDATE bank_okter SET gyldig_til = ?", (snart,))
    assert any("går ut om 5 dager" in t["tekst"] for t in pb.trenger())


def test_tolk_bankformat():
    ut = bank.tolk([_tx("a", "2026-10-01", -1050, "Kiwi"),
                    {"entry_reference": "b", "booking_date": "2026-10-02", "transaction_amount": {"amount": "-20.00"},
                     "remittance_information": "Rema"},
                    {"booking_date": "2026-10-03", "transaction_date": "2026-10-02", "transaction_amount": {"amount": "5"},
                     "credit_debit_indicator": "CRDT", "debtor": {"name": "Ola"}, "remittance_information": ["123456"],
                     "debtor_account": {"iban": "NO93" + FELLES}},
                    _tx("c", "2026-10-03", -500, "x", status="PDNG"),
                    {"booking_date": "ikke-dato", "transaction_amount": {"amount": "1"}}])
    assert [(t["dato"], t["belop_ore"], t["tekst"], t["motkonto"]) for t in ut] == [
        ("2026-10-01", -1050, "Kiwi", None), ("2026-10-02", -2000, "Rema", None), ("2026-10-02", 500, "Ola 123456", FELLES)]
    assert ut[0]["ref"] == "a" and ut[1]["ref"] == "b" and ut[2]["ref"].startswith("h")
