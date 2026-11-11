"""Pengeboka – webserver for Home Assistant ingress. Bare Python-standardbiblioteket.

Appen har ingen egen port ut og ingen tilgang til resten av Home Assistant. Forespørsler
godtas bare fra Home Assistants ingress-proxy, som sørger for innlogging.
"""
from __future__ import annotations

import json
import logging
import mimetypes
import os
import re
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qsl, unquote, urlparse

from db import Database
from logikk import Feil, Pengeboka

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger("pengeboka")

STATISK = Path(__file__).parent / "static"
INGRESS_IP = "172.30.32.2"
UTVIKLING = os.environ.get("PENGEBOKA_DEV") == "1"
MAKS_FIL = 20 * 1024 * 1024

ROUTES: list[tuple[str, re.Pattern, callable]] = []


def route(metode: str, sti: str):
    def dek(fn):
        ROUTES.append((metode, re.compile("^" + sti + "$"), fn))
        return fn
    return dek


PB: Pengeboka | None = None


# ---------------------------------------------------------------- API
@route("GET", r"/api/oversikt")
def oversikt(r):
    return {**PB.oversikt(r.q.get("maned")), "bruker": r.bruker}


@route("GET", r"/api/transaksjoner")
def transaksjoner(r):
    return PB.transaksjoner(r.q)


@route("GET", r"/api/transaksjoner/(\d+)")
def transaksjon(r, tid):
    return {"transaksjon": PB.transaksjon(int(tid))}


@route("PATCH", r"/api/transaksjoner/(\d+)")
def endre_transaksjon(r, tid):
    return {"transaksjon": PB.endre_transaksjon(int(tid), r.json(), r.bruker)}


@route("GET", r"/api/kategorier")
def kategorier(r):
    return {"kategorier": PB.kategorier()}


@route("POST", r"/api/kategorier")
def ny_kategori(r):
    return {"kategori": PB.lagre_kategori(r.json())}


@route("PATCH", r"/api/kategorier/(\d+)")
def endre_kategori(r, kid):
    return {"kategori": PB.lagre_kategori(r.json(), int(kid))}


@route("GET", r"/api/budsjett")
def budsjett(r):
    return PB.budsjett()


@route("PUT", r"/api/budsjett")
def lagre_budsjett(r):
    PB.lagre_budsjett(r.json().get("budsjett") or {})
    return PB.budsjett()


@route("GET", r"/api/budsjett/forslag")
def budsjettforslag(r):
    return {"forslag": {str(k): v for k, v in PB.foresla_budsjett().items()}}


@route("GET", r"/api/faste")
def faste(r):
    return {"faste": PB.faste()}


@route("POST", r"/api/faste")
def merk_fast(r):
    d = r.json()
    PB.merk_fast(str(d.get("motpart") or ""), d.get("valg"))
    return {"faste": PB.faste()}


@route("POST", r"/api/avvis")
def avvis(r):
    PB.avvis(str(r.json().get("nokkel") or ""))
    return {"trenger": PB.trenger()}


@route("GET", r"/api/kontoer")
def kontoer(r):
    return {"kontoer": PB.kontoer(), "importer": PB.importer_liste(), "regler": PB.regler()}


@route("POST", r"/api/kontoer")
def ny_konto(r):
    return {"konto": PB.lagre_konto(r.json())}


@route("PATCH", r"/api/kontoer/(\d+)")
def endre_konto(r, kid):
    return {"konto": PB.lagre_konto(r.json(), int(kid))}


@route("DELETE", r"/api/kontoer/(\d+)")
def slett_konto(r, kid):
    PB.slett_konto(int(kid))
    return {"ok": True}


@route("DELETE", r"/api/regler/(\d+)")
def slett_regel(r, rid):
    PB.slett_regel(int(rid))
    return {"regler": PB.regler()}


def _oppsett(r) -> dict | None:
    o = r.q.get("oppsett")
    if not o:
        return None
    try:
        d = json.loads(o)
        k = {f: int(v) for f, v in (d.get("kolonner") or {}).items()
             if v not in (None, "") and f in ("dato", "tekst", "belop", "ut", "inn", "status", "fra", "til")}
        return {"overskrift": int(d.get("overskrift", -1)), "kolonner": k}
    except (ValueError, TypeError, AttributeError):
        raise Feil("Ugyldig kolonneoppsett") from None


@route("POST", r"/api/import/forhandsvis")
def forhandsvis(r):
    konto = int(r.q["konto"]) if r.q.get("konto") else None
    return PB.forhandsvis(r.fil(), konto, _oppsett(r), r.filnavn)


@route("POST", r"/api/import")
def importer(r):
    konto = int(r.q["konto"]) if r.q.get("konto") else None  # uten konto: appen finner den selv
    return PB.importer(r.fil(), r.filnavn, konto, _oppsett(r), r.bruker)


@route("DELETE", r"/api/importer/(\d+)")
def angre_import(r, iid):
    return {"slettet": PB.angre_import(int(iid))}


@route("GET", r"/api/eksport\.csv")
def eksport(r):
    return Raw(PB.eksport_csv().encode("utf-8-sig"), "text/csv; charset=utf-8",
               {"Content-Disposition": 'attachment; filename="pengeboka.csv"'})


# ---------------------------------------------------------------- HTTP
class Raw:
    def __init__(self, data: bytes, typ: str, hoder: dict | None = None):
        self.data, self.typ, self.hoder = data, typ, hoder or {}


class Foresporsel:
    def __init__(self, h: "Handler", q: dict):
        self.h, self.q = h, q
        self._kropp = None

    @property
    def bruker(self) -> str | None:
        return self.h.headers.get("X-Remote-User-Display-Name") or self.h.headers.get("X-Remote-User-Name")

    @property
    def filnavn(self) -> str:
        return unquote(self.h.headers.get("X-Filnavn") or "")

    def kropp(self) -> bytes:
        if self._kropp is None:
            n = int(self.h.headers.get("Content-Length") or 0)
            if n > MAKS_FIL:
                raise Feil("Filen er for stor (maks 20 MB)")
            self._kropp = self.h.rfile.read(n) if n else b""
        return self._kropp

    def json(self) -> dict:
        b = self.kropp()
        try:
            d = json.loads(b or b"{}")
        except ValueError:
            raise Feil("Ugyldig forespørsel") from None
        if not isinstance(d, dict):
            raise Feil("Ugyldig forespørsel")
        return d

    def fil(self) -> bytes:
        return self.kropp()


class Handler(BaseHTTPRequestHandler):
    server_version = "Pengeboka"

    def log_message(self, fmt, *args):  # ingen tilgangslogg med beløp eller søk
        pass

    def _tillatt(self) -> bool:
        return UTVIKLING or self.client_address[0] == INGRESS_IP

    def _send(self, status: int, data: bytes, typ: str, hoder: dict | None = None):
        self.send_response(status)
        self.send_header("Content-Type", typ)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        for k, v in (hoder or {}).items():
            self.send_header(k, v)
        self.end_headers()
        self.wfile.write(data)

    def _json(self, status: int, obj):
        self._send(status, json.dumps(obj, ensure_ascii=False).encode(), "application/json; charset=utf-8")

    def _statisk(self, sti: str):
        if sti in ("", "/"):
            sti = "/index.html"
        elif not sti.startswith("/static/"):
            return self._json(404, {"feil": "Ikke funnet"})
        else:
            sti = sti[len("/static"):]
        fil = (STATISK / sti.lstrip("/")).resolve()
        if STATISK.resolve() not in fil.parents or not fil.is_file():
            return self._json(404, {"feil": "Ikke funnet"})
        typ = mimetypes.guess_type(fil.name)[0] or "application/octet-stream"
        if typ.startswith("text/") or typ in ("application/javascript",):
            typ += "; charset=utf-8"
        self._send(200, fil.read_bytes(), typ)

    def _hand(self, metode: str):
        if not self._tillatt():
            return self._json(403, {"feil": "Bare tilgjengelig gjennom Home Assistant"})
        url = urlparse(self.path)
        sti = re.sub(r"/{2,}", "/", url.path)
        if metode == "GET" and not sti.startswith("/api/"):
            return self._statisk(sti)
        for m, monster, fn in ROUTES:
            treff = monster.match(sti)
            if treff and m == metode:
                try:
                    svar = fn(Foresporsel(self, dict(parse_qsl(url.query))), *treff.groups())
                except Feil as e:
                    return self._json(400, {"feil": str(e)})
                except (ValueError, TypeError, KeyError) as e:
                    log.info("Ugyldig forespørsel til %s: %s", sti, type(e).__name__)
                    return self._json(400, {"feil": "Ugyldig forespørsel"})
                except Exception:
                    log.exception("Feil i %s %s", metode, sti)
                    return self._json(500, {"feil": "Noe gikk galt. Se loggen til appen."})
                if isinstance(svar, Raw):
                    return self._send(200, svar.data, svar.typ, svar.hoder)
                return self._json(200, svar)
        return self._json(404, {"feil": "Ikke funnet"})

    def do_GET(self):
        self._hand("GET")

    def do_POST(self):
        self._hand("POST")

    def do_PUT(self):
        self._hand("PUT")

    def do_PATCH(self):
        self._hand("PATCH")

    def do_DELETE(self):
        self._hand("DELETE")


def data_dir() -> Path:
    d = Path(os.environ.get("PENGEBOKA_DATA", "/data"))
    if not d.exists():
        d = Path(__file__).resolve().parent.parent / "data"
    d.mkdir(parents=True, exist_ok=True)
    return d


def start(port: int | None = None, db_sti: Path | None = None) -> ThreadingHTTPServer:
    global PB
    PB = Pengeboka(Database(db_sti or data_dir() / "pengeboka.db"))
    srv = ThreadingHTTPServer(("0.0.0.0" if not UTVIKLING else "127.0.0.1", port or int(os.environ.get("PENGEBOKA_PORT", "8099"))), Handler)
    return srv


if __name__ == "__main__":
    s = start()
    log.info("Pengeboka kjører på port %s", s.server_address[1])
    s.serve_forever()
