"""Babyuret – webserver (Home Assistant ingress) og API."""
from __future__ import annotations

import asyncio
import logging
import os
from datetime import date
from pathlib import Path

from aiohttp import web

import innstillinger
from db import Database
from ha import HAKobling
from logikk import Babyuret, Feil

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger("babyuret")

STATISK = Path(__file__).parent / "static"


def _bruker(req: web.Request) -> str | None:
    """Ingress sender navnet på innlogget HA-bruker."""
    return req.headers.get("X-Remote-User-Display-Name") or req.headers.get("X-Remote-User-Name")


def _feil(melding: str, status: int = 400) -> web.Response:
    return web.json_response({"feil": melding}, status=status)


def lag_app(bu: Babyuret) -> web.Application:
    routes = web.RouteTableDef()

    @routes.get("/")
    async def index(_req):
        return web.FileResponse(STATISK / "index.html", headers={"Cache-Control": "no-cache"})

    @routes.get("/api/status")
    async def status(req):
        try:
            dag = date.fromisoformat(req.query["dag"]) if req.query.get("dag") else None
        except ValueError:
            return _feil("Ugyldig dato")
        return web.json_response({
            "innstillinger": bu.cfg.offentlig(),
            "alder": bu.alder(),
            "status": bu.status(),
            "oppsummering": bu.oppsummering(dag),
            "i_dag": bu.i_dag().isoformat(),
            "bruker": _bruker(req),
        })

    @routes.post("/api/handling")
    async def handling(req):
        data = await req.json()
        try:
            res = bu.handling(data.pop("handling", ""), data, av=_bruker(req))
        except Feil as e:
            return _feil(str(e))
        return web.json_response(res)

    @routes.get("/api/innstillinger")
    async def hent_innstillinger(_req):
        return web.json_response(bu.cfg.offentlig())

    @routes.put("/api/innstillinger")
    async def lagre_innstillinger(req):
        try:
            return web.json_response(bu.lagre_innstillinger(await req.json()))
        except Feil as e:
            return _feil(str(e))

    @routes.post("/api/hendelser")
    async def legg_til(req):
        d = await req.json()
        try:
            h = bu.legg_til(d.get("kategori"), d.get("start"), d.get("slutt"), d.get("detaljer"), _bruker(req))
        except (Feil, ValueError, TypeError) as e:
            return _feil(str(e))
        return web.json_response({"hendelse": h})

    @routes.patch("/api/hendelser/{hid:\\d+}")
    async def endre(req):
        try:
            h = bu.endre(int(req.match_info["hid"]), await req.json())
        except (Feil, ValueError) as e:
            return _feil(str(e))
        return web.json_response({"hendelse": h})

    @routes.delete("/api/hendelser/{hid:\\d+}")
    async def slett(req):
        try:
            bu.slett(int(req.match_info["hid"]))
        except Feil as e:
            return _feil(str(e), 404)
        return web.json_response({"ok": True})

    @routes.get("/api/eksport.csv")
    async def eksport(_req):
        linjer = ["id;kategori;start;slutt;detaljer;av"]
        for h in bu.db.alle():
            det = ",".join(f"{k}={v}" for k, v in h["detaljer"].items())
            linjer.append(f"{h['id']};{h['kategori']};{h['start']};{h['slutt'] or ''};{det};{h['av'] or ''}")
        return web.Response(
            text="\n".join(linjer), content_type="text/csv", charset="utf-8",
            headers={"Content-Disposition": 'attachment; filename="babyuret.csv"'},
        )

    app = web.Application()
    app.add_routes(routes)
    app.router.add_static("/static/", STATISK)
    return app


async def main() -> None:
    cfg = innstillinger.les()
    db = Database(cfg.data_dir / "babyuret.db")
    bu = Babyuret(db, cfg, tz=os.environ.get("TZ") or "Europe/Oslo")
    ha = HAKobling(bu)
    await ha.start()

    runner = web.AppRunner(lag_app(bu))
    await runner.setup()
    await web.TCPSite(runner, "0.0.0.0", cfg.port).start()
    log.info("Babyuret kjører på port %s", cfg.port)
    await asyncio.Event().wait()


if __name__ == "__main__":
    asyncio.run(main())
