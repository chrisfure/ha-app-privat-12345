"""Styrkeboka – webserver (Home Assistant ingress)."""
from __future__ import annotations

import asyncio
import logging
import os
from pathlib import Path

from aiohttp import web

from api import API, Foresporsel
from db import Database
from ha import HAKobling
from logikk import Styrkeboka

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger("styrkeboka")

STATISK = Path(__file__).parent / "static"


def lag_app(api: API) -> web.Application:
    async def index(_req):
        return web.FileResponse(STATISK / "index.html", headers={"Cache-Control": "no-cache"})

    async def api_handler(req: web.Request) -> web.Response:
        body = None
        if req.can_read_body:
            try:
                body = await req.json()
            except ValueError:
                return web.json_response({"feil": "Ugyldig JSON"}, status=400)
        svar = await api.handter(Foresporsel(
            metode=req.method, sti=req.path, query=dict(req.query), body=body,
            bruker=req.headers.get("X-Remote-User-Display-Name"), brukernavn=req.headers.get("X-Remote-User-Name")))
        if svar.tekst is not None:
            return web.Response(text=svar.tekst, status=svar.status, content_type=svar.innholdstype,
                                charset="utf-8", headers=svar.hoder)
        return web.json_response(svar.data, status=svar.status, headers=svar.hoder)

    app = web.Application()
    app.router.add_get("/", index)
    app.router.add_route("*", "/api/{hale:.*}", api_handler)
    app.router.add_static("/static/", STATISK)
    return app


def data_dir() -> Path:
    d = Path(os.environ.get("STYRKEBOKA_DATA", "/data"))
    if not d.exists():
        d = Path(__file__).resolve().parent.parent / "data"
    d.mkdir(parents=True, exist_ok=True)
    return d


async def main() -> None:
    sb = Styrkeboka(Database(data_dir() / "styrkeboka.db"), tz=os.environ.get("TZ") or "Europe/Oslo")
    ha = HAKobling(sb)
    await ha.start()
    runner = web.AppRunner(lag_app(API(sb, ha)))
    await runner.setup()
    port = int(os.environ.get("STYRKEBOKA_PORT", "8099"))
    await web.TCPSite(runner, "0.0.0.0", port).start()
    log.info("Styrkeboka kjører på port %s", port)
    await asyncio.Event().wait()


if __name__ == "__main__":
    asyncio.run(main())
