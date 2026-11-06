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
import maalinger as mal
import referanser

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
        bu.lyd.sjekk_frister()
        return web.json_response({
            "innstillinger": bu.cfg.offentlig(),
            "alder": bu.alder(),
            "status": bu.status(),
            "prognose": bu.prognose.beregn(),
            "siste_dogn": bu.prognose.siste_dogn(),
            "oppsummering": bu.oppsummering(dag),
            "lyd": bu.lyd.oversikt(),
            "i_dag": bu.i_dag().isoformat(),
            "bruker": _bruker(req),
        })

    @routes.get("/api/periode")
    async def periode(req):
        try:
            dato = date.fromisoformat(req.query["dato"]) if req.query.get("dato") else None
            return web.json_response(bu.periode(req.query.get("type", "uke"), dato))
        except ValueError:
            return _feil("Ugyldig dato")
        except Feil as e:
            return _feil(str(e))

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

    @routes.get("/api/maalinger")
    async def maalinger(_req):
        return web.json_response({
            "maalinger": bu.db.maalinger(),
            "vurderinger": mal.vurderinger(bu),
            "kilder": referanser.KILDER,
        })

    @routes.post("/api/maalinger")
    async def ny_maaling(req):
        d = await req.json()
        try:
            verdi, tid = mal.valider(d.get("type"), d.get("verdi"), d.get("tid"))
        except mal.UgyldigMaaling as e:
            return _feil(str(e))
        m = bu.db.ny_maaling(d["type"], verdi, tid, (d.get("notat") or "").strip()[:200] or None, _bruker(req))
        return web.json_response({"maaling": m, "vurderinger": mal.vurderinger(bu)})

    @routes.patch("/api/maalinger/{mid:\\d+}")
    async def endre_maaling(req):
        mid = int(req.match_info["mid"])
        gammel = bu.db.maaling(mid)
        if not gammel:
            return _feil("Fant ikke målingen", 404)
        d = await req.json()
        try:
            verdi, tid = mal.valider(gammel["type"], d.get("verdi", gammel["verdi"]), d.get("tid", gammel["tid"]))
        except mal.UgyldigMaaling as e:
            return _feil(str(e))
        m = bu.db.endre_maaling(mid, verdi, tid, (d.get("notat", gammel["notat"]) or "").strip()[:200] or None)
        return web.json_response({"maaling": m})

    @routes.delete("/api/maalinger/{mid:\\d+}")
    async def slett_maaling(req):
        if not bu.db.slett_maaling(int(req.match_info["mid"])):
            return _feil("Fant ikke målingen", 404)
        return web.json_response({"ok": True})

    @routes.put("/api/lyd/sted")
    async def lyd_sted(req):
        d = await req.json()
        try:
            return web.json_response(bu.lyd.sett_sted(d.get("sted"), d.get("med"), _bruker(req)))
        except ValueError as e:
            return _feil(str(e))

    @routes.post("/api/lyd/forslag/{fid:\\d+}")
    async def lyd_svar(req):
        d = await req.json()
        try:
            return web.json_response(bu.lyd.svar(int(req.match_info["fid"]), d.get("svar"), _bruker(req)))
        except ValueError as e:
            return _feil(str(e))

    @routes.get("/api/lyd/logg")
    async def lyd_logg(_req):
        return web.json_response({
            "logg": bu.lyd.logg(),
            "per_enhet": bu.lyd.per_enhet(),
            "forslag": bu.lyd.forslag(None, 10),
            "laering": {"alle": bu.lyd.laering(), "uten_stoy": bu.lyd.laering(False),
                        "med_stoy": bu.lyd.laering(True)},
        })

    @routes.get("/api/kilder")
    async def kilder(_req):
        return web.json_response(referanser.KILDER)

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
