"""Stjerneboka – to webservere.

* Administrasjon: Home Assistant ingress (port 8099) – bare for de voksne i sidemenyen.
* Barnesiden: egen port (8097) på hjemmenettet – for veggskjermen. Kan bare vise status,
  registrere en oppgave og angre den siste innen kort tid.
"""
from __future__ import annotations

import asyncio
import logging
import os
import secrets
from pathlib import Path

from aiohttp import web

from db import Database, naa
from ha import HAKobling
from logikk import (FARGER, INNEBYGDE_BILDER, MALER, MEDIETYPER, OKT_NAVN, SPERRER, TYPE_NAVN, TYPER, Feil,
                    Sperret, Stjerneboka)

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger("stjerneboka")

STATISK = Path(__file__).parent / "static"
BILDETYPER = {"image/png": ".png", "image/jpeg": ".jpg", "image/webp": ".webp", "image/gif": ".gif"}
MAKS_BILDE = 5 * 1024 * 1024


def _bruker(req: web.Request) -> str | None:
    return req.headers.get("X-Remote-User-Display-Name") or req.headers.get("X-Remote-User-Name")


def _feil(melding: str, status: int = 400, **ekstra) -> web.Response:
    return web.json_response({"feil": melding, **ekstra}, status=status)


def fanget(fn):
    async def inner(req):
        try:
            return await fn(req)
        except Sperret as s:
            return _feil(str(s), 409, sperret=True)
        except Feil as e:
            return _feil(str(e))
        except (ValueError, TypeError, KeyError) as e:
            log.info("Ugyldig forespørsel: %s", e)
            return _feil("Ugyldig forespørsel")
    return inner


def _id(req, navn="id") -> int:
    return int(req.match_info[navn])


def _ingen_cache(fil: Path) -> web.FileResponse:
    return web.FileResponse(fil, headers={"Cache-Control": "no-cache"})


def _felles(app: web.Application, bildemappe: Path) -> None:
    app.router.add_static("/static/", STATISK)
    app.router.add_static("/bilder/", bildemappe)


# ---------------------------------------------------------------- barnesiden
def lag_barneside(sb: Stjerneboka, bildemappe: Path) -> web.Application:
    routes = web.RouteTableDef()

    @routes.get("/")
    async def index(_req):
        return _ingen_cache(STATISK / "barn.html")

    @routes.get("/api/status")
    @fanget
    async def status(_req):
        return web.json_response(sb.barnevisning())

    @routes.post("/api/registrer")
    @fanget
    async def registrer(req):
        d = await req.json()
        res = sb.registrer(int(d["barn_id"]), int(d["oppgave_id"]), kilde="skjerm", av="Veggskjermen")
        return web.json_response({**res, "status": sb.barnevisning()})

    @routes.post("/api/angre")
    @fanget
    async def angre(req):
        d = await req.json()
        sb.angre(int(d["id"]), fra_skjerm=True)
        return web.json_response({"status": sb.barnevisning()})

    app = web.Application()
    app.add_routes(routes)
    _felles(app, bildemappe)
    return app


# ---------------------------------------------------------------- administrasjon
def lag_admin(sb: Stjerneboka, ha: HAKobling, bildemappe: Path) -> web.Application:
    routes = web.RouteTableDef()

    @routes.get("/")
    async def index(_req):
        return _ingen_cache(STATISK / "admin.html")

    def _alt(req=None) -> dict:
        return {
            **sb.admin_oversikt(),
            "innstillinger": sb.inn, "oppgaver": sb.db.oppgaver(), "kort": sb.db.kortliste(),
            "ukjente_kort": sb.db.ukjente_kort(), "maler": MALER, "lesere": sb.db.lesere(),
            "konstanter": {"typer": [{"id": t, "navn": TYPE_NAVN[t]} for t in TYPER], "farger": FARGER,
                           "okter": OKT_NAVN, "sperrer": SPERRER, "innebygde": INNEBYGDE_BILDER,
                           "medietyper": MEDIETYPER},
            "ha": ha.aktiv, "bruker": _bruker(req) if req else None,
            "sensorer": list(sb.sensorer().keys()),
        }

    @routes.get("/api/alt")
    @fanget
    async def alt(req):
        return web.json_response(_alt(req))

    @routes.put("/api/innstillinger")
    @fanget
    async def innstillinger(req):
        sb.lagre_innstillinger(await req.json())
        return web.json_response(_alt(req))

    # ---- barn
    @routes.post("/api/barn")
    @fanget
    async def nytt_barn(req):
        sb.lagre_barn(await req.json())
        return web.json_response(_alt(req))

    @routes.patch("/api/barn/{id:\\d+}")
    @fanget
    async def endre_barn(req):
        sb.lagre_barn(await req.json(), _id(req))
        return web.json_response(_alt(req))

    @routes.delete("/api/barn/{id:\\d+}")
    @fanget
    async def slett_barn(req):
        sb.slett_barn(_id(req))
        return web.json_response(_alt(req))

    # ---- oppgaver
    @routes.post("/api/oppgaver")
    @fanget
    async def ny_oppgave(req):
        sb.lagre_oppgave(await req.json())
        return web.json_response(_alt(req))

    @routes.post("/api/oppgaver/mal")
    @fanget
    async def mal(req):
        d = await req.json()
        sb.legg_til_mal(int(d["indeks"]), [int(b) for b in d.get("barn") or []])
        return web.json_response(_alt(req))

    @routes.patch("/api/oppgaver/{id:\\d+}")
    @fanget
    async def endre_oppgave(req):
        sb.lagre_oppgave(await req.json(), _id(req))
        return web.json_response(_alt(req))

    @routes.delete("/api/oppgaver/{id:\\d+}")
    @fanget
    async def slett_oppgave(req):
        sb.slett_oppgave(_id(req))
        return web.json_response(_alt(req))

    @routes.put("/api/rekkefolge")
    @fanget
    async def rekkefolge(req):
        d = await req.json()
        sb.db.sett_rekkefolge(d["tabell"], d["ider"])
        sb._endret("rekkefolge", {})
        return web.json_response(_alt(req))

    # ---- registreringer
    @routes.post("/api/godkjenn/{id:\\d+}")
    @fanget
    async def godkjenn(req):
        d = await req.json()
        sb.godkjenn(_id(req), av=_bruker(req), godkjent=bool(d.get("godkjent", True)))
        return web.json_response(_alt(req))

    @routes.post("/api/registreringer")
    @fanget
    async def ny_reg(req):
        sb.registrer_admin(await req.json(), _bruker(req))
        return web.json_response(_alt(req))

    @routes.delete("/api/registreringer/{id:\\d+}")
    @fanget
    async def slett_reg(req):
        sb.slett_registrering(_id(req))
        return web.json_response(_alt(req))

    @routes.post("/api/utbetalt")
    @fanget
    async def utbetalt(req):
        d = await req.json()
        sb.marker_utbetalt(int(d["barn_id"]), str(d["uke"]), _bruker(req), bool(d.get("angre")))
        return web.json_response(_alt(req))

    # ---- kort
    @routes.put("/api/kort/{uid}")
    @fanget
    async def lagre_kort(req):
        sb.lagre_kort(req.match_info["uid"], await req.json())
        return web.json_response(_alt(req))

    @routes.delete("/api/kort/{uid}")
    @fanget
    async def slett_kort(req):
        sb.db.slett_kort(req.match_info["uid"].upper())
        return web.json_response(_alt(req))

    @routes.delete("/api/ukjente_kort")
    @fanget
    async def glem_ukjente(req):
        sb.db.glem_ukjente_kort()
        return web.json_response(_alt(req))

    @routes.patch("/api/lesere/{lid}")
    @fanget
    async def lagre_leser(req):
        sb.lagre_leser(req.match_info["lid"], await req.json())
        return web.json_response(_alt(req))

    @routes.delete("/api/lesere/{lid}")
    @fanget
    async def slett_leser(req):
        sb.db.slett_leser(req.match_info["lid"])
        return web.json_response(_alt(req))

    @routes.post("/api/kort/test")
    @fanget
    async def test_kort(req):
        d = await req.json()
        return web.json_response({"resultat": sb.skann(d["uid"]), **_alt(req)})

    # ---- bilder
    @routes.post("/api/bilder")
    @fanget
    async def last_opp(req):
        reader = await req.multipart()
        felt = await reader.next()
        if felt is None or felt.name != "fil":
            raise Feil("Mangler fil")
        ending = BILDETYPER.get(felt.headers.get("Content-Type", ""))
        if not ending:
            raise Feil("Bruk PNG, JPG, WEBP eller GIF")
        data = bytearray()
        while (bit := await felt.read_chunk()):
            data.extend(bit)
            if len(data) > MAKS_BILDE:
                raise Feil("Bildet er større enn 5 MB")
        navn = f"{secrets.token_hex(8)}{ending}"
        (bildemappe / navn).write_bytes(bytes(data))
        return web.json_response({"bilde": f"fil:{navn}"})

    # ---- test av lyd og skjerm
    @routes.post("/api/test/lyd")
    @fanget
    async def test_lyd(_req):
        return web.json_response({"ok": await ha.si("Dette er Stjerneboka. Bra jobba!", fanfare=True)})

    @routes.post("/api/test/skjerm")
    @fanget
    async def test_skjerm(_req):
        return web.json_response({"ok": await ha.vis_skjerm()})

    app = web.Application(client_max_size=MAKS_BILDE + 64 * 1024)
    app.add_routes(routes)
    _felles(app, bildemappe)
    return app


def data_dir() -> Path:
    d = Path(os.environ.get("STJERNEBOKA_DATA", "/data"))
    if not d.exists():
        d = Path(__file__).resolve().parent.parent / "data"
    d.mkdir(parents=True, exist_ok=True)
    return d


async def main() -> None:
    data = data_dir()
    bilder = data / "bilder"
    bilder.mkdir(exist_ok=True)
    sb = Stjerneboka(Database(data / "stjerneboka.db"), tz=os.environ.get("TZ") or "Europe/Oslo")
    ha = HAKobling(sb)
    await ha.start()
    for app, port in ((lag_admin(sb, ha, bilder), int(os.environ.get("STJERNEBOKA_PORT", "8099"))),
                      (lag_barneside(sb, bilder), int(os.environ.get("STJERNEBOKA_BARNEPORT", "8097")))):
        runner = web.AppRunner(app)
        await runner.setup()
        await web.TCPSite(runner, "0.0.0.0", port).start()
    log.info("Stjerneboka kjører – administrasjon på 8099 (ingress), barnesiden på 8097 (%s)", naa().isoformat())
    await asyncio.Event().wait()


if __name__ == "__main__":
    asyncio.run(main())
