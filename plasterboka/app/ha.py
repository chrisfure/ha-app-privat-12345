"""Kobling mot Home Assistant via Supervisor.

* Publiserer én sensor per barn (sensor.plasterboka_<navn>) og sensor.plasterboka_skjermtekst.
* Sender hendelsen «plasterboka_hendelse» ved hver registrering.
* Lytter på hendelsen «plasterboka_registrer», så knapper og Assist kan registrere.
* Sender valgfritt varsel via en notify-tjeneste (settes i appen).
* Leser kalendere for import av eldre logger.
"""
from __future__ import annotations

import asyncio
import logging
import os
from datetime import datetime

import aiohttp

from logikk import Advarsel, Feil, Plasterboka

log = logging.getLogger("plasterboka.ha")

CORE_API = "http://supervisor/core/api"
CORE_WS = "ws://supervisor/core/websocket"
LYTT_PA = "plasterboka_registrer"


class HAKobling:
    def __init__(self, pb: Plasterboka):
        self.pb = pb
        self.token = os.environ.get("SUPERVISOR_TOKEN")
        self.aktiv = bool(self.token)
        self._session: aiohttp.ClientSession | None = None
        self._publiser_naa = asyncio.Event()
        self._ko: list[tuple[str, dict | None]] = []
        self._publisert: set[str] = set()

    @property
    def _hoder(self) -> dict:
        return {"Authorization": f"Bearer {self.token}", "Content-Type": "application/json"}

    async def start(self) -> None:
        if not self.aktiv:
            log.info("Ingen SUPERVISOR_TOKEN – kjører uten Home Assistant-kobling")
            return
        self._session = aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=30))
        await self._hent_tidssone()
        self.pb.ved_endring(self._ved_endring)
        asyncio.create_task(self._publiser_loop())
        asyncio.create_task(self._lytt_loop())

    async def _hent_tidssone(self) -> None:
        try:
            async with self._session.get(f"{CORE_API}/config", headers=self._hoder) as r:
                if r.status == 200 and (tz := (await r.json()).get("time_zone")):
                    self.pb.sett_tidssone(tz)
        except aiohttp.ClientError as e:
            log.warning("Klarte ikke hente tidssone: %s", e)

    def _ved_endring(self, hva: str, data: dict | None) -> None:
        self._ko.append((hva, data))
        self._publiser_naa.set()

    async def _publiser_loop(self) -> None:
        while True:
            try:
                await self.publiser()
                ko, self._ko = self._ko, []
                for hva, data in ko:
                    await self._fyr_hendelse(hva, data)
                    if hva == "registrert" and data and data.get("kilde") != "import":
                        await self._varsle(data)
            except Exception as e:  # noqa: BLE001
                log.warning("Publisering feilet: %s", e)
            self._publiser_naa.clear()
            try:
                await asyncio.wait_for(self._publiser_naa.wait(), timeout=60)
            except asyncio.TimeoutError:
                pass

    async def publiser(self) -> None:
        sensorer = self.pb.sensorer()
        for entity_id, verdi in sensorer.items():
            async with self._session.post(f"{CORE_API}/states/{entity_id}", headers=self._hoder, json=verdi) as r:
                if r.status >= 400:
                    log.warning("Kunne ikke oppdatere %s: %s", entity_id, r.status)
        # Barn som er fjernet eller har byttet navn: fjern den gamle sensoren
        for gammel in self._publisert - sensorer.keys():
            async with self._session.delete(f"{CORE_API}/states/{gammel}", headers=self._hoder):
                pass
        self._publisert = set(sensorer)

    async def _fyr_hendelse(self, hva: str, data: dict | None) -> None:
        barn = self.pb.db.ett_barn(data["barn_id"]) if data and data.get("barn_id") else None
        nyttelast = {"handling": hva}
        if data:
            nyttelast.update({
                "barn": barn["navn"] if barn else None,
                "tid": data.get("tid"), "temperatur": data.get("temp"), "feber": data.get("feber"),
                "legemiddel": data.get("legemiddel"), "dose_mg": data.get("dose_mg"),
                "symptomer": data.get("symptomer"), "notat": data.get("notat"), "tekst": data.get("tittel"),
            })
        async with self._session.post(f"{CORE_API}/events/plasterboka_hendelse", headers=self._hoder, json=nyttelast):
            pass

    async def _varsle(self, data: dict) -> None:
        tjeneste = self.pb.inn.get("varsle_tjeneste") or ""
        if not tjeneste.startswith("notify."):
            return
        barn = self.pb.db.ett_barn(data["barn_id"]) if data.get("barn_id") else None
        melding = f"{data.get('tittel')} kl. {data.get('kl')}"
        if data.get("notat") and data.get("tittel") != "Notat":
            melding += f"\nNotat: {data['notat']}"
        elif data.get("notat"):
            melding = f"{data['notat']} (kl. {data.get('kl')})"
        if data.get("av"):
            melding += f"\nRegistrert av {data['av']}"
        body = {"title": f"🩹 {barn['navn'] if barn else 'Plasterboka'}", "message": melding}
        async with self._session.post(f"{CORE_API}/services/notify/{tjeneste.split('.', 1)[1]}",
                                      headers=self._hoder, json=body) as r:
            if r.status >= 400:
                log.warning("Varsling via %s feilet: %s", tjeneste, r.status)

    # ------------------------------------------------------------ kalendere
    async def kalendere(self) -> list[dict]:
        if not self.aktiv:
            return []
        async with self._session.get(f"{CORE_API}/calendars", headers=self._hoder) as r:
            r.raise_for_status()
            return await r.json()

    async def kalenderhendelser(self, entity_id: str, fra: datetime, til: datetime) -> list[dict]:
        params = {"start": fra.isoformat(), "end": til.isoformat()}
        async with self._session.get(f"{CORE_API}/calendars/{entity_id}", headers=self._hoder, params=params) as r:
            r.raise_for_status()
            return await r.json()

    # ------------------------------------------------------------ lytting
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
            await ws.receive_json()
            await ws.send_json({"type": "auth", "access_token": self.token})
            msg = await ws.receive_json()
            if msg.get("type") != "auth_ok":
                raise RuntimeError(f"Autentisering feilet: {msg}")
            await ws.send_json({"id": 1, "type": "subscribe_events", "event_type": LYTT_PA})
            log.info("Lytter på hendelsen %s", LYTT_PA)
            async for m in ws:
                if m.type != aiohttp.WSMsgType.TEXT:
                    if m.type in (aiohttp.WSMsgType.CLOSED, aiohttp.WSMsgType.ERROR):
                        break
                    continue
                data = m.json()
                if data.get("type") == "event":
                    self._fra_ha(dict(data["event"].get("data") or {}))

    def _fra_ha(self, ev: dict) -> None:
        """Registrering fra en automasjon, knapp eller Assist.

        Felt: barn (navn), temperatur, legemiddel (navn), dose_mg/dose_ml (standarddose hvis utelatt),
        symptomer (liste), notat, minutter_siden, av.
        """
        try:
            navn = str(ev.get("barn") or "").strip().lower()
            barn = next((b for b in self.pb.db.barn() if b["navn"].lower() == navn), None)
            if not barn:
                raise Feil(f"Ukjent barn: {ev.get('barn')}")
            d = {"barn_id": barn["id"], "minutter_siden": ev.get("minutter_siden"), "bekreftet": True}
            if ev.get("temperatur") not in (None, ""):
                d["temp"] = ev["temperatur"]
                d["temp_metode"] = ev.get("metode")
            if ev.get("legemiddel"):
                lm = self.pb.db.finn_legemiddel(str(ev["legemiddel"]))
                if not lm:
                    raise Feil(f"Ukjent legemiddel: {ev['legemiddel']}")
                bl = self.pb.db.barn_legemiddel(barn["id"], lm["id"]) or {}
                d.update(legemiddel_id=lm["id"], dose_mg=ev.get("dose_mg") or bl.get("standard_mg"),
                         dose_ml=ev.get("dose_ml"))
            for k in ("symptomer", "notat"):
                if ev.get(k):
                    d[k] = ev[k]
            r = self.pb.registrer(d, av=ev.get("av") or "Home Assistant", kilde="ha")
            log.info("Registrert fra HA for %s (id %s)", barn["navn"], r["id"])
        except (Feil, Advarsel, ValueError) as e:
            log.info("Ignorerte registrering fra HA: %s", e)
