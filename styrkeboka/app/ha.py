"""Kobling mot Home Assistant via Supervisor.

* Publiserer én sensor per profil (sensor.styrkeboka_<navn>).
* Sender hendelsen «styrkeboka_hendelse» når en økt startes eller fullføres.
* Spør Home Assistants AI via ai_task.generate_data (eller conversation.process).
"""
from __future__ import annotations

import asyncio
import logging
import os

import aiohttp

from logikk import Feil, Styrkeboka

log = logging.getLogger("styrkeboka.ha")

CORE_API = "http://supervisor/core/api"


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
    def __init__(self, sb: Styrkeboka):
        self.sb = sb
        self.token = _supervisor_token()
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
        self.sb.ved_endring(self._ved_endring)
        asyncio.create_task(self._publiser_loop())

    async def _hent_tidssone(self) -> None:
        try:
            async with self._session.get(f"{CORE_API}/config", headers=self._hoder) as r:
                if r.status == 200 and (tz := (await r.json()).get("time_zone")):
                    self.sb.sett_tidssone(tz)
        except aiohttp.ClientError as e:
            log.warning("Klarte ikke hente tidssone: %s", e)

    def _ved_endring(self, hva: str, data: dict | None) -> None:
        self._ko.append((hva, data))
        self._publiser_naa.set()

    async def _publiser_loop(self) -> None:
        while True:
            try:
                ko, self._ko = self._ko, []
                if any(h != "sett" for h, _ in ko) or not ko:
                    await self.publiser()
                for hva, data in ko:
                    if hva in ("okt_startet", "okt_fullfort"):
                        await self._fyr_hendelse(hva, data)
            except Exception as e:  # noqa: BLE001
                log.warning("Publisering feilet: %s", e)
            self._publiser_naa.clear()
            try:
                await asyncio.wait_for(self._publiser_naa.wait(), timeout=300)
            except asyncio.TimeoutError:
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

    async def _fyr_hendelse(self, hva: str, data: dict | None) -> None:
        if not data or not data.get("profil_id"):
            return
        try:
            p = self.sb.profil(data["profil_id"])
        except Feil:
            return
        nyttelast = {"handling": hva, "profil": p["navn"]}
        if hva == "okt_startet" and data.get("okt"):
            nyttelast["okt"] = data["okt"]["dag_navn"]
        if hva == "okt_fullfort" and data.get("oppsummering"):
            o = data["oppsummering"]["okt"]
            nyttelast.update(okt=o["dag_navn"], minutter=o["nokkeltall"]["minutter"], sett=o["nokkeltall"]["sett"],
                             volum_kg=o["nokkeltall"]["volum"], rekorder=[r["ovelse"] + ": " + r["tekst"] for r in data["oppsummering"]["rekorder"]])
        async with self._session.post(f"{CORE_API}/events/styrkeboka_hendelse", headers=self._hoder, json=nyttelast):
            pass

    # ------------------------------------------------------------ AI
    async def ai_entiteter(self) -> list[dict]:
        if not self.aktiv:
            return []
        async with self._session.get(f"{CORE_API}/states", headers=self._hoder) as r:
            r.raise_for_status()
            tilstander = await r.json()
        ut = []
        for s in tilstander:
            eid = s.get("entity_id", "")
            if eid.startswith(("ai_task.", "conversation.")) and s.get("state") != "unavailable" and eid != "conversation.home_assistant":
                ut.append({"entity_id": eid, "navn": (s.get("attributes") or {}).get("friendly_name") or eid})
        ut.sort(key=lambda x: (not x["entity_id"].startswith("ai_task."), "claude" not in x["entity_id"], x["navn"]))
        return ut

    async def _velg_entitet(self) -> str | None:
        valgt = self.sb.inn.get("ai_entitet") or ""
        if valgt:
            return valgt
        alle = await self.ai_entiteter()
        return alle[0]["entity_id"] if alle else None

    async def spor(self, oppgave: str, instruksjoner: str) -> str | dict:
        """Sender en oppgave til AI i Home Assistant og returnerer svaret (tekst)."""
        if not self.sb.inn.get("ai_paa"):
            raise Feil("AI-treneren er slått av i innstillingene")
        if not self.aktiv:
            raise Feil("Ingen kontakt med Home Assistant – AI er ikke tilgjengelig")
        entitet = await self._velg_entitet()
        if not entitet:
            raise Feil("Fant ingen AI i Home Assistant. Sett opp en AI-integrasjon (f.eks. Anthropic) med «AI-oppgave».")
        tidsavbrudd = aiohttp.ClientTimeout(total=150)
        try:
            if entitet.startswith("ai_task."):
                body = {"task_name": f"Styrkeboka: {oppgave}", "instructions": instruksjoner, "entity_id": entitet}
                url = f"{CORE_API}/services/ai_task/generate_data?return_response"
            else:
                body = {"text": instruksjoner, "agent_id": entitet, "language": "nb"}
                url = f"{CORE_API}/services/conversation/process?return_response"
            async with self._session.post(url, headers=self._hoder, json=body, timeout=tidsavbrudd) as r:
                tekst = await r.text()
                if r.status >= 400:
                    log.warning("AI-kall feilet (%s): %s", r.status, tekst[:500])
                    raise Feil(f"AI-en svarte ikke (feil {r.status}). Sjekk AI-integrasjonen i Home Assistant.")
                svar = await r.json(content_type=None)
        except asyncio.TimeoutError as e:
            raise Feil("AI-en brukte for lang tid. Prøv igjen.") from e
        except aiohttp.ClientError as e:
            raise Feil(f"Fikk ikke kontakt med AI-en: {e}") from e
        resp = (svar or {}).get("service_response") or {}
        if entitet.startswith("ai_task."):
            data = resp.get("data")
        else:
            data = (((resp.get("response") or {}).get("speech") or {}).get("plain") or {}).get("speech")
        if not data:
            raise Feil("AI-en ga et tomt svar. Prøv igjen.")
        return data
