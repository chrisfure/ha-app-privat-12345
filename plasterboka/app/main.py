"""Plasterboka – webserver (Home Assistant ingress) og API."""
from __future__ import annotations

import asyncio
import logging
import os
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from aiohttp import web

import importer
from db import Database, naa
from ha import HAKobling
from logikk import FARGER, FORMER, METODE_NAVN, METODER, Advarsel, Feil, Plasterboka

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger("plasterboka")

STATISK = Path(__file__).parent / "static"
IMPORT_FRA = datetime(2015, 1, 1, tzinfo=timezone.utc)


def _bruker(req: web.Request) -> str | None:
    return req.headers.get("X-Remote-User-Display-Name") or req.headers.get("X-Remote-User-Name")


def _feil(melding: str, status: int = 400, **ekstra) -> web.Response:
    return web.json_response({"feil": melding, **ekstra}, status=status)


def lag_app(pb: Plasterboka, ha: HAKobling) -> web.Application:
    routes = web.RouteTableDef()

    def fanget(fn):
        async def inner(req):
            try:
                return await fn(req)
            except Advarsel as a:
                return _feil(str(a), 409, advarsler=a.advarsler)
            except Feil as e:
                return _feil(str(e))
            except (ValueError, TypeError, KeyError) as e:
                log.info("Ugyldig forespørsel: %s", e)
                return _feil("Ugyldig forespørsel")
        return inner

    def _id(req, navn="id") -> int:
        return int(req.match_info[navn])

    @routes.get("/")
    async def index(_req):
        return web.FileResponse(STATISK / "index.html", headers={"Cache-Control": "no-cache"})

    @routes.get("/api/oversikt")
    @fanget
    async def oversikt(req):
        return web.json_response({**pb.oversikt(), "bruker": _bruker(req), "naa": naa().isoformat()})

    # ---- registreringer ----
    @routes.post("/api/registreringer")
    @fanget
    async def ny(req):
        r = pb.registrer(await req.json(), av=_bruker(req))
        return web.json_response({"registrering": pb.beskriv(r)})

    @routes.get("/api/registreringer/{id:\\d+}")
    @fanget
    async def hent(req):
        r = pb.db.registrering(_id(req))
        if not r:
            raise Feil("Fant ikke registreringen")
        return web.json_response({"registrering": pb.beskriv(r)})

    @routes.patch("/api/registreringer/{id:\\d+}")
    @fanget
    async def endre(req):
        return web.json_response({"registrering": pb.beskriv(pb.endre_registrering(_id(req), await req.json()))})

    @routes.delete("/api/registreringer/{id:\\d+}")
    @fanget
    async def slett(req):
        return web.json_response({"slettet": pb.slett_registrering(_id(req))})

    @routes.post("/api/registreringer/gjenopprett")
    @fanget
    async def gjenopprett(req):
        return web.json_response({"registrering": pb.beskriv(pb.gjenopprett(await req.json()))})

    @routes.post("/api/dosekontroll")
    @fanget
    async def dosekontroll(req):
        d = await req.json()
        tid = datetime.fromisoformat(d["tid"].replace("Z", "+00:00")) if d.get("tid") else naa()
        return web.json_response({"advarsler": pb.kontroller_dose(int(d["barn_id"]), int(d["legemiddel_id"]),
                                                                  float(d["dose_mg"]), tid, d.get("unntatt"))})

    @routes.post("/api/barn/{id:\\d+}/frisk")
    @fanget
    async def frisk(req):
        pb.frisk(_id(req))
        return web.json_response({"ok": True})

    # ---- historikk ----
    @routes.get("/api/historikk")
    @fanget
    async def historikk(req):
        barn = int(req.query["barn"]) if req.query.get("barn") else None
        aar = int(req.query["aar"]) if req.query.get("aar") else None
        return web.json_response(pb.historikk(barn, aar))

    @routes.get("/api/episoder/{id:\\d+}")
    @fanget
    async def episode(req):
        return web.json_response(pb.episode_detalj(_id(req)))

    @routes.patch("/api/episoder/{id:\\d+}")
    @fanget
    async def endre_episode(req):
        return web.json_response({"episode": pb.lagre_episode(_id(req), await req.json())})

    # ---- innstillinger ----
    def _innstillinger() -> dict:
        return {
            "innstillinger": pb.inn, "barn": pb.db.barn(), "legemidler": pb.db.legemidler(),
            "barn_legemidler": pb.db.barn_legemidler(),
            "farger": FARGER, "former": FORMER, "metoder": [{"id": m, "navn": METODE_NAVN[m]} for m in METODER],
            "sensorer": {b["id"]: pb.sensor_navn(b) for b in pb.db.barn()},
        }

    @routes.get("/api/innstillinger")
    @fanget
    async def innstillinger(_req):
        return web.json_response(_innstillinger())

    @routes.put("/api/innstillinger")
    @fanget
    async def lagre_innstillinger(req):
        pb.lagre_innstillinger(await req.json())
        return web.json_response(_innstillinger())

    @routes.post("/api/barn")
    @fanget
    async def nytt_barn(req):
        return web.json_response({"barn": pb.lagre_barn(await req.json())})

    @routes.patch("/api/barn/{id:\\d+}")
    @fanget
    async def endre_barn(req):
        return web.json_response({"barn": pb.lagre_barn(await req.json(), _id(req))})

    @routes.delete("/api/barn/{id:\\d+}")
    @fanget
    async def slett_barn(req):
        pb.slett_barn(_id(req))
        return web.json_response({"ok": True})

    @routes.post("/api/legemidler")
    @fanget
    async def nytt_lm(req):
        return web.json_response({"legemiddel": pb.lagre_legemiddel(await req.json())})

    @routes.patch("/api/legemidler/{id:\\d+}")
    @fanget
    async def endre_lm(req):
        return web.json_response({"legemiddel": pb.lagre_legemiddel(await req.json(), _id(req))})

    @routes.delete("/api/legemidler/{id:\\d+}")
    @fanget
    async def slett_lm(req):
        return web.json_response({"resultat": pb.slett_legemiddel(_id(req))})

    @routes.put("/api/barn/{bid:\\d+}/legemidler/{lid:\\d+}")
    @fanget
    async def barn_lm(req):
        return web.json_response({"oppsett": pb.lagre_barn_legemiddel(_id(req, "bid"), _id(req, "lid"), await req.json())})

    # ---- gjennomgang ----
    @routes.get("/api/gjennomgang")
    @fanget
    async def gjennomgang(_req):
        return web.json_response(pb.gjennomgang())

    @routes.post("/api/gjennomgang/tildel")
    @fanget
    async def tildel(req):
        d = await req.json()
        bid = int(d["barn_id"]) if d.get("barn_id") not in (None, "") else None
        return web.json_response({"antall": pb.tildel([int(i) for i in d.get("ider") or []], bid)})

    # ---- import ----
    @routes.get("/api/import/kalendere")
    @fanget
    async def kalendere(_req):
        if not ha.aktiv:
            return web.json_response({"kalendere": [], "feil": "Ingen kontakt med Home Assistant"})
        return web.json_response({"kalendere": await ha.kalendere()})

    async def _plan(req) -> dict:
        d = await req.json()
        oppsett = []
        for k in d.get("kalendere") or []:
            if not str(k.get("entity_id", "")).startswith("calendar."):
                raise Feil("Ugyldig kalender")
            oppsett.append(importer.Kalenderoppsett(
                entity_id=k["entity_id"],
                barn_id=int(k["barn_id"]) if k.get("barn_id") else None,
                gjennomga_for=date.fromisoformat(k["gjennomga_for"]) if k.get("gjennomga_for") else None,
                gjennomga_alle=bool(k.get("gjennomga_alle")),
            ))
        if not oppsett:
            raise Feil("Velg minst én kalender")
        hendelser = {}
        for o in oppsett:
            hendelser[o.entity_id] = await ha.kalenderhendelser(o.entity_id, IMPORT_FRA, naa() + timedelta(days=1))
        return importer.planlegg(hendelser, oppsett, pb.db.barn(), pb.db.kilde_refs(), pb.kl, pb.tz)

    @routes.post("/api/import/forhandsvis")
    @fanget
    async def forhandsvis(req):
        return web.json_response(_lesbar(await _plan(req)))

    @routes.post("/api/import/kjor")
    @fanget
    async def kjor(req):
        plan = await _plan(req)
        res = pb.importer(plan["rader"])
        return web.json_response({**_lesbar(plan), **res})

    def _lesbar(plan: dict) -> dict:
        o = dict(plan["oppsummering"])
        navn = {str(b["id"]): b["navn"] for b in pb.db.barn()}
        o["per_barn"] = {navn.get(k, "Ukjent barn"): v for k, v in o["per_barn"].items()}
        return {"oppsummering": o}

    @routes.get("/api/eksport.csv")
    @fanget
    async def eksport(_req):
        return web.Response(text=pb.csv(), content_type="text/csv", charset="utf-8",
                            headers={"Content-Disposition": 'attachment; filename="plasterboka.csv"'})

    app = web.Application()
    app.add_routes(routes)
    app.router.add_static("/static/", STATISK)
    return app


def data_dir() -> Path:
    d = Path(os.environ.get("PLASTERBOKA_DATA", "/data"))
    if not d.exists():
        d = Path(__file__).resolve().parent.parent / "data"
    d.mkdir(parents=True, exist_ok=True)
    return d


async def main() -> None:
    db = Database(data_dir() / "plasterboka.db")
    pb = Plasterboka(db, tz=os.environ.get("TZ") or "Europe/Oslo")
    ha = HAKobling(pb)
    await ha.start()
    runner = web.AppRunner(lag_app(pb, ha))
    await runner.setup()
    port = int(os.environ.get("PLASTERBOKA_PORT", "8099"))
    await web.TCPSite(runner, "0.0.0.0", port).start()
    log.info("Plasterboka kjører på port %s", port)
    await asyncio.Event().wait()


if __name__ == "__main__":
    asyncio.run(main())
