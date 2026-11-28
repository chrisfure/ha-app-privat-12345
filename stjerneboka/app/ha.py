"""Kobling mot Home Assistant via Supervisor.

* Publiserer én sensor per barn (sensor.stjerneboka_<navn>) og sensor.stjerneboka_venter_godkjenning.
* Sender hendelsen «stjerneboka_hendelse» ved hver stjerne, godkjenning og sperre.
* Lytter på:
  - «tag_scanned» {tag_id, device_id}   – NFC-lesere i Home Assistant (ESPHome) – vet hvilken leser
  - «stjerneboka_skann» {uid}           – lesere uten Home Assistant-tagger (f.eks. MQTT via automasjon)
  - «stjerneboka_registrer» {barn, oppgave} – fra knapper, automasjoner eller Assist
  - «mobile_app_notification_action»     – Godkjenn / Ikke helt ennå fra varselet på mobilen
* Spiller fanfare + stemme på valgt høyttaler og kan åpne barnesiden på veggskjermen (Browser Mod).
"""
from __future__ import annotations

import asyncio
import logging
import os

import aiohttp

from logikk import Feil, Stjerneboka

log = logging.getLogger("stjerneboka.ha")

CORE_API = "http://supervisor/core/api"
CORE_WS = "ws://supervisor/core/websocket"
LYTT_PA = ("tag_scanned", "stjerneboka_skann", "stjerneboka_registrer", "mobile_app_notification_action")
GODKJENN, AVVIS = "STJERNEBOKA_GODKJENN_", "STJERNEBOKA_AVVIS_"


def _supervisor_token() -> str | None:
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
    def __init__(self, sb: Stjerneboka):
        self.sb = sb
        self.token = _supervisor_token()
        self.aktiv = bool(self.token)
        self._session: aiohttp.ClientSession | None = None
        self._publiser_naa = asyncio.Event()
        self._ko: list[tuple[str, dict]] = []
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
        self.sb.ved_endring(self._ved_endring)
        asyncio.create_task(self._publiser_loop())
        asyncio.create_task(self._lytt_loop())

    async def _hent_tidssone(self) -> None:
        try:
            async with self._session.get(f"{CORE_API}/config", headers=self._hoder) as r:
                if r.status == 200 and (tz := (await r.json()).get("time_zone")):
                    self.sb.sett_tidssone(tz)
        except aiohttp.ClientError as e:
            log.warning("Klarte ikke hente tidssone: %s", e)

    def _ved_endring(self, hva: str, data: dict) -> None:
        self._ko.append((hva, data))
        self._publiser_naa.set()

    # ------------------------------------------------------------ tjenester
    async def tjeneste(self, domene: str, tjeneste: str, data: dict) -> bool:
        if not self.aktiv:
            return False
        try:
            async with self._session.post(f"{CORE_API}/services/{domene}/{tjeneste}",
                                          headers=self._hoder, json=data) as r:
                if r.status >= 400:
                    log.warning("%s.%s feilet: %s %s", domene, tjeneste, r.status, (await r.text())[:200])
                    return False
                return True
        except aiohttp.ClientError as e:
            log.warning("%s.%s feilet: %s", domene, tjeneste, e)
            return False

    async def si(self, melding: str, fanfare: bool = True) -> bool:
        inn = self.sb.inn
        if inn.get("lyd_aktiv") != "1" or not inn.get("hoyttaler"):
            return False
        volum = int(float(inn.get("volum_kveld" if self.sb.i_stilletid() else "volum_dag") or 40))
        if inn.get("lydmetode") == "music_assistant":
            data = {"entity_id": inn["hoyttaler"], "message": melding, "use_pre_announce": fanfare,
                    "announce_volume": max(1, min(100, volum))}
            if inn.get("tts"):
                data["tts_entity_id"] = inn["tts"]
            if fanfare and inn.get("fanfare_url"):
                data["pre_announce_url"] = inn["fanfare_url"]
            return await self.tjeneste("music_assistant", "play_announcement", data)
        if not inn.get("tts"):
            return False
        return await self.tjeneste("tts", "speak", {"entity_id": inn["tts"], "message": melding,
                                                    "media_player_entity_id": inn["hoyttaler"]})

    async def vis_skjerm(self) -> bool:
        inn = self.sb.inn
        if not inn.get("skjerm_browser") or not inn.get("barneside_url"):
            return False
        return await self.tjeneste("browser_mod", "popup", {
            "browser_id": [inn["skjerm_browser"]], "tag": "stjerneboka", "title": "⭐ Stjerneboka",
            "initial_style": "fullscreen", "dismissable": True, "timeout": 600000, "timeout_hide_progress": True,
            "content": {"type": "iframe", "url": inn["barneside_url"], "aspect_ratio": "170%"},
        })

    def _varsel_tjenester(self) -> list[str]:
        return [t.strip().split(".", 1)[1] for t in (self.sb.inn.get("varsle_tjeneste") or "").split(",")
                if t.strip().startswith("notify.")]

    async def _be_om_godkjenning(self, d: dict) -> None:
        r, b = d["registrering"], d["barn"]
        for t in self._varsel_tjenester():
            await self.tjeneste("notify", t, {
                "title": f"⭐ {b['navn']} vil ha godkjent",
                "message": f"{r['oppgave_navn']} ({r['poeng']} poeng)",
                "data": {"tag": f"stjerneboka-{r['id']}", "group": "stjerneboka",
                         "actions": [{"action": f"{GODKJENN}{r['id']}", "title": "Godkjenn ⭐"},
                                     {"action": f"{AVVIS}{r['id']}", "title": "Ikke helt ennå"}]},
            })

    async def _fjern_varsel(self, rid: int) -> None:
        for t in self._varsel_tjenester():
            await self.tjeneste("notify", t, {"message": "clear_notification",
                                              "data": {"tag": f"stjerneboka-{rid}"}})

    # ------------------------------------------------------------ publisering
    async def _publiser_loop(self) -> None:
        while True:
            try:
                ko, self._ko = self._ko, []
                for hva, data in ko:
                    await self._behandle(hva, data)
                await self.publiser()
            except Exception as e:  # noqa: BLE001
                log.warning("Publisering feilet: %s", e)
            self._publiser_naa.clear()
            try:
                # Sensorene oppdateres også jevnlig, så «mangler» følger morgen/dag/kveld
                await asyncio.wait_for(self._publiser_naa.wait(), timeout=60)
            except asyncio.TimeoutError:
                pass

    async def _behandle(self, hva: str, d: dict) -> None:
        if hva in ("registrert", "godkjent", "avvist", "sperret"):
            r = d.get("registrering") or {}
            await self._fyr("stjerneboka_hendelse", {
                "handling": "venter" if r.get("status") == "venter" else hva,
                "barn": d["barn"]["navn"], "oppgave": d["oppgave"]["navn"], "poeng": r.get("poeng"),
                "stjerner_i_dag": d.get("stjerner_i_dag"), "melding": d.get("melding"), "kilde": d.get("kilde"),
            })
            if d.get("kilde") == "kort" and self.sb.inn.get("vis_ved_kort") == "1":
                await self.vis_skjerm()
            # Stemmen kan ta flere sekunder – ikke la den holde igjen sensorer og varsler
            asyncio.create_task(self.si(d["melding"],
                                        fanfare=hva in ("registrert", "godkjent") and r.get("status") != "venter"))
            if hva == "registrert" and r.get("status") == "venter":
                await self._be_om_godkjenning(d)
            if hva in ("godkjent", "avvist"):
                await self._fjern_varsel(r["id"])
        elif hva == "vis_skjerm":
            await self.vis_skjerm()
        elif hva == "musikk":
            k = d["kort"]
            if k.get("bryter") and not await self._er_paa(k["bryter"]):
                log.info("Musikk-kort %s: %s er av", d["uid"], k["bryter"])
                return
            data = {"entity_id": d["hoyttaler"], "media_id": k["media_id"], "enqueue": "replace"}
            if k.get("media_type") and k["media_type"] != "auto":
                data["media_type"] = k["media_type"]
            await self.tjeneste("music_assistant", "play_media", data)
            await self._fyr("stjerneboka_hendelse", {"handling": "musikk", "uid": d["uid"], "media": k["media_id"],
                                                     "hoyttaler": d["hoyttaler"],
                                                     "leser": (d.get("leser") or {}).get("navn")})
        elif hva == "ha_handling":
            ent = d["kort"]["entity"]
            domene = ent.split(".", 1)[0]
            if domene == "automation":
                # Automasjonens egne betingelser gjelder fortsatt (skip_condition: false)
                await self.tjeneste("automation", "trigger", {"entity_id": ent, "skip_condition": False})
            elif domene == "script":
                await self.tjeneste("script", "turn_on", {"entity_id": ent})
            elif domene == "scene":
                await self.tjeneste("scene", "turn_on", {"entity_id": ent})
        elif hva == "ukjent_kort":
            await self._fyr("stjerneboka_hendelse", {"handling": "ukjent_kort", "uid": d["uid"]})
        elif hva == "angret":
            r = d["registrering"]
            if r.get("status") == "venter":
                await self._fjern_varsel(r["id"])

    async def _fyr(self, hendelse: str, data: dict) -> None:
        if not self.aktiv:
            return
        async with self._session.post(f"{CORE_API}/events/{hendelse}", headers=self._hoder, json=data):
            pass

    async def publiser(self) -> None:
        sensorer = self.sb.sensorer()
        for entity_id, verdi in sensorer.items():
            async with self._session.post(f"{CORE_API}/states/{entity_id}", headers=self._hoder, json=verdi) as r:
                if r.status >= 400:
                    log.warning("Kunne ikke oppdatere %s: %s", entity_id, r.status)
        for gammel in self._publisert - sensorer.keys():
            async with self._session.delete(f"{CORE_API}/states/{gammel}", headers=self._hoder):
                pass
        self._publisert = set(sensorer)

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
            for i, ev in enumerate(LYTT_PA, start=1):
                await ws.send_json({"id": i, "type": "subscribe_events", "event_type": ev})
            log.info("Lytter på %s", ", ".join(LYTT_PA))
            async for m in ws:
                if m.type != aiohttp.WSMsgType.TEXT:
                    if m.type in (aiohttp.WSMsgType.CLOSED, aiohttp.WSMsgType.ERROR):
                        break
                    continue
                data = m.json()
                if data.get("type") == "event":
                    ev = data["event"]
                    self._fra_ha(ev.get("event_type"), dict(ev.get("data") or {}))

    async def _mal(self, mal: str) -> str:
        async with self._session.post(f"{CORE_API}/template", headers=self._hoder, json={"template": mal}) as r:
            return (await r.text()).strip() if r.status == 200 else ""

    async def _tag(self, ev: dict) -> None:
        uid, enhet = ev.get("tag_id") or "", ev.get("device_id")
        navn = rom = None
        try:
            if enhet:
                kjent = self.sb.db.en_leser(enhet)
                if not kjent or not kjent["navn"]:
                    svar = await self._mal("{{ device_attr('%s', 'name_by_user') or device_attr('%s', 'name') }}|"
                                           "{{ area_name('%s') or '' }}" % (enhet, enhet, enhet))
                    navn, _, rom = svar.partition("|")
            res = self.sb.skann(uid, enhet, navn, rom)
            log.info("Kort skannet på %s: %s", navn or enhet or "ukjent leser", res.get("handling"))
        except (Feil, aiohttp.ClientError) as e:
            log.info("Ignorerte tag_scanned: %s", e)

    async def _er_paa(self, entity_id: str) -> bool:
        async with self._session.get(f"{CORE_API}/states/{entity_id}", headers=self._hoder) as r:
            return r.status == 200 and (await r.json()).get("state") == "on"

    def _fra_ha(self, typ: str, ev: dict) -> None:
        if typ == "tag_scanned":
            asyncio.create_task(self._tag(ev))
            return
        try:
            if typ == "stjerneboka_skann":
                res = self.sb.skann(ev.get("uid") or ev.get("tag_id") or "")
                log.info("Kort skannet: %s", res.get("handling"))
            elif typ == "stjerneboka_registrer":
                b, o = self.sb.finn_barn(ev.get("barn")), self.sb.finn_oppgave(ev.get("oppgave"))
                if not b or not o:
                    raise Feil(f"Ukjent barn eller oppgave: {ev.get('barn')} / {ev.get('oppgave')}")
                self.sb.registrer(b["id"], o["id"], kilde="ha", av=ev.get("av") or "Home Assistant")
            elif typ == "mobile_app_notification_action":
                handling = str(ev.get("action") or "")
                if handling.startswith(GODKJENN):
                    self.sb.godkjenn(int(handling[len(GODKJENN):]), av="Mobil", godkjent=True)
                elif handling.startswith(AVVIS):
                    self.sb.godkjenn(int(handling[len(AVVIS):]), av="Mobil", godkjent=False)
        except (Feil, ValueError) as e:
            log.info("Ignorerte %s: %s", typ, e)
