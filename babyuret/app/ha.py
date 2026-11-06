"""Kobling mot Home Assistant via Supervisor.

* Publiserer sensorer (sensor.babyuret_*) ved hver endring og hvert minutt.
* Sender hendelsen «babyuret_hendelse» ved endringer, så automasjoner kan reagere.
* Lytter på hendelsen «babyuret_registrer», så knapper, NFC og Assist kan registrere.
* Lytter på hendelsen «babyuret_lyd» fra lytteenheter (gråt/rop). Ingen varsler sendes.
"""
from __future__ import annotations

import asyncio
import logging
import os

import aiohttp

from logikk import Babyuret, Feil

log = logging.getLogger("babyuret.ha")

CORE_API = "http://supervisor/core/api"
CORE_WS = "ws://supervisor/core/websocket"
LYTT_PA = "babyuret_registrer"
LYTT_LYD = "babyuret_lyd"


def _supervisor_token() -> str | None:
    """Tokenet ligger i miljøet, eller – når s6-overlay starter appen uten miljø – i en fil."""
    t = os.environ.get("SUPERVISOR_TOKEN")
    if t:
        return t
    for sti in ("/run/s6/container_environment/SUPERVISOR_TOKEN", "/var/run/s6/container_environment/SUPERVISOR_TOKEN"):
        try:
            with open(sti, encoding="utf-8") as f:
                if (t := f.read().strip()):
                    return t
        except OSError:
            continue
    return None


class HAKobling:
    def __init__(self, bu: Babyuret):
        self.bu = bu
        self.token = _supervisor_token()
        self.aktiv = bool(self.token)
        self._session: aiohttp.ClientSession | None = None
        self._publiser_nå = asyncio.Event()
        self._siste_hendelse: dict | None = None
        self._sende_hendelse = False

    @property
    def _hoder(self) -> dict:
        return {"Authorization": f"Bearer {self.token}", "Content-Type": "application/json"}

    async def start(self) -> None:
        if not self.aktiv:
            log.info("Ingen SUPERVISOR_TOKEN – kjører uten Home Assistant-kobling")
            return
        self._session = aiohttp.ClientSession()
        await self._hent_tidssone()
        self.bu.ved_endring(self._ved_endring)
        asyncio.create_task(self._publiser_loop())
        asyncio.create_task(self._lytt_loop())

    async def stopp(self) -> None:
        if self._session:
            await self._session.close()

    async def _hent_tidssone(self) -> None:
        try:
            async with self._session.get(f"{CORE_API}/config", headers=self._hoder) as r:
                if r.status == 200:
                    tz = (await r.json()).get("time_zone")
                    if tz:
                        self.bu.sett_tidssone(tz)
                        log.info("Tidssone fra Home Assistant: %s", tz)
        except aiohttp.ClientError as e:
            log.warning("Klarte ikke hente tidssone: %s", e)

    def _ved_endring(self, hva: str, hendelse: dict | None) -> None:
        self._siste_hendelse = {"handling": hva, "hendelse": hendelse}
        self._sende_hendelse = True
        self._publiser_nå.set()

    async def _publiser_loop(self) -> None:
        while True:
            try:
                self.bu.lyd.sjekk_frister()
                await self.publiser()
                if self._sende_hendelse:
                    self._sende_hendelse = False
                    await self._fyr_hendelse(self._siste_hendelse or {})
            except Exception as e:  # noqa: BLE001
                log.warning("Publisering feilet: %s", e)
            self._publiser_nå.clear()
            try:
                await asyncio.wait_for(self._publiser_nå.wait(), timeout=60)
            except asyncio.TimeoutError:
                pass

    async def publiser(self) -> None:
        for entity_id, verdi in self.bu.sensorer().items():
            async with self._session.post(f"{CORE_API}/states/{entity_id}",
                                          headers=self._hoder, json=verdi) as r:
                if r.status >= 400:
                    log.warning("Kunne ikke oppdatere %s: %s", entity_id, r.status)

    async def _fyr_hendelse(self, data: dict) -> None:
        h = data.get("hendelse") or {}
        nyttelast = {
            "handling": data.get("handling"),
            "kategori": h.get("kategori"),
            "start": h.get("start"),
            "slutt": h.get("slutt"),
            "detaljer": h.get("detaljer"),
            "status": self.bu.sensorer()["sensor.babyuret_status"]["state"],
        }
        async with self._session.post(f"{CORE_API}/events/babyuret_hendelse",
                                      headers=self._hoder, json=nyttelast):
            pass

    async def _tilstand(self, entity_id: str) -> str | None:
        try:
            async with self._session.get(f"{CORE_API}/states/{entity_id}", headers=self._hoder) as r:
                if r.status == 200:
                    return (await r.json()).get("state")
        except aiohttp.ClientError as e:
            log.warning("Klarte ikke lese %s: %s", entity_id, e)
        return None

    async def _lyd(self, ev: dict) -> None:
        kilde = str(ev.get("kilde") or "").strip().lower()
        enhet = self.bu.lyd.enhet(kilde)
        nett = await self._tilstand(enhet["nett_entitet"]) if enhet and enhet["nett_entitet"] else None
        try:
            res = self.bu.lyd.motta(str(ev.get("type") or "grat"), kilde, nett)
            log.info("Lyd fra %s: %s%s", kilde or "?", res["tolkning"], f" ({res['grunn']})" if res.get("grunn") else "")
        except Exception as e:  # noqa: BLE001
            log.warning("Kunne ikke behandle lyd fra %s: %s", kilde, e)

    async def _lytt_loop(self) -> None:
        vent = 5
        while True:
            try:
                await self._lytt()
                vent = 5
            except Exception as e:  # noqa: BLE001
                log.warning("Mistet kontakt med Home Assistant (%s) – prøver igjen om %ss", e, vent)
            await asyncio.sleep(vent)
            vent = min(vent * 2, 120)

    async def _lytt(self) -> None:
        async with self._session.ws_connect(CORE_WS, heartbeat=30) as ws:
            msg = await ws.receive_json()  # auth_required
            await ws.send_json({"type": "auth", "access_token": self.token})
            msg = await ws.receive_json()
            if msg.get("type") != "auth_ok":
                raise RuntimeError(f"Autentisering feilet: {msg}")
            await ws.send_json({"id": 1, "type": "subscribe_events", "event_type": LYTT_PA})
            await ws.send_json({"id": 2, "type": "subscribe_events", "event_type": LYTT_LYD})
            log.info("Lytter på hendelsene %s og %s", LYTT_PA, LYTT_LYD)
            async for m in ws:
                if m.type != aiohttp.WSMsgType.TEXT:
                    if m.type in (aiohttp.WSMsgType.CLOSED, aiohttp.WSMsgType.ERROR):
                        break
                    continue
                data = m.json()
                if data.get("type") != "event":
                    continue
                ev = data["event"].get("data", {}) or {}
                if data["event"].get("event_type") == LYTT_LYD:
                    await self._lyd(ev)
                    continue
                handling = ev.pop("handling", None)
                av = ev.pop("av", None) or "Home Assistant"
                try:
                    res = self.bu.handling(handling, ev, av=av)
                    log.info("Registrert fra HA: %s – %s", handling, res["melding"])
                except Feil as e:
                    log.info("Ignorerte %s: %s", handling, e)
