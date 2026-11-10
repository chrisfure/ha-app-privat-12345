"""Kobling mot Home Assistant via Supervisor.

* Publiserer én sensor per profil (sensor.styrkeboka_<navn>).
* Sender hendelsen «styrkeboka_hendelse» når en økt startes eller fullføres.
* Spør Home Assistants AI via ai_task.generate_data (eller conversation.process).
"""
from __future__ import annotations

import asyncio
import re
import logging
import os
from datetime import timedelta

import aiohttp

import kropp
from db import fra_iso, naa
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
        asyncio.create_task(self._synk_loop())

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
                    if hva == "okt_fullfort" and data:
                        try:
                            await self.send_okt_til_garmin(data["oppsummering"]["okt"]["id"])
                        except Exception as e:  # noqa: BLE001
                            log.warning("Kunne ikke sende økt til Garmin: %s", e)
                    if hva in ("okt_fullfort", "klokke_okt", "program", "startvekter", "ukeplan") and data and data.get("profil_id"):
                        try:
                            p = self.sb.profil(data["profil_id"])
                            if (p.get("garmin_eksport") or {}).get("styrke"):
                                await self.synk_garmin_styrke(p)
                        except Exception as e:  # noqa: BLE001
                            log.warning("Styrkeøkter til Garmin feilet: %s", e)
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

    # ------------------------------------------------------------ kropp: data fra f.eks. Garmin Connect
    async def _tilstander(self) -> list[dict]:
        async with self._session.get(f"{CORE_API}/states", headers=self._hoder) as r:
            r.raise_for_status()
            return await r.json()

    async def sok_sensorer(self, q: str, grense: int = 25) -> list[dict]:
        """Fritekstsøk blant alle sensorer – når forslagene ikke treffer."""
        ord_ = [o for o in q.lower().split() if o]
        if not self.aktiv or not ord_:
            return []
        ut = []
        for s in await self._tilstander():
            eid = s.get("entity_id", "")
            if not eid.startswith("sensor."):
                continue
            a = s.get("attributes") or {}
            navn = str(a.get("friendly_name") or eid)
            tekst = f"{eid} {navn}".lower().replace("_", " ")
            if all(o in tekst for o in ord_):
                ut.append({"entity_id": eid, "navn": navn, "state": s.get("state"), "enhet": a.get("unit_of_measurement")})
                if len(ut) >= grense:
                    break
        return ut

    async def kilder(self, profil: dict) -> dict:
        """Sensorer som kan kobles til en profil, gruppert per type, med et forslag per type."""
        if not self.aktiv:
            return {"kilder": {}, "forslag": {}}
        tilstander = await self._tilstander()
        andre = [p["navn"].lower() for p in self.sb.profiler() if p["id"] != profil["id"]]
        mitt = profil["navn"].lower()
        kilder: dict[str, list[dict]] = {k: [] for k in ("aktiviteter", *kropp.KOBLBARE_TALL, *kropp.KOBLBARE_TEKST, "kalendere")}
        monstre = [("sovn_score", "sleep_score"), ("sovn_min", "total_sleep_duration"), ("stress", "avg_stress_level"),
                   ("body_battery", "body_battery_highest"), ("hrv", "hrv_last_night_average"), ("restitusjon", "recovery_time"),
                   ("hrv_status", "hrv_status"), ("treningsstatus", "training_status")]
        for s in tilstander:
            eid = s.get("entity_id", "")
            if eid.startswith("calendar."):
                kilder["kalendere"].append({"entity_id": eid, "navn": str((s.get("attributes") or {}).get("friendly_name") or eid), "state": s.get("state")})
                continue
            if not eid.startswith("sensor."):
                continue
            a = s.get("attributes") or {}
            navn = str(a.get("friendly_name") or eid)
            tekst = f"{eid} {navn}".lower()
            enhet = str(a.get("unit_of_measurement") or "").lower()
            rad = {"entity_id": eid, "navn": navn, "state": s.get("state"), "enhet": a.get("unit_of_measurement")}
            treff = next((typ for typ, m in monstre if m in eid), None)
            if treff:
                kilder[treff].append(rad)
            elif eid.endswith("training_readiness") or "treningsberedskap" in tekst:
                kilder["beredskap"].append(rad)
            elif isinstance(a.get("last_activities"), list):
                kilder["aktiviteter"].append(rad)
            elif a.get("device_class") == "weight" or (enhet == "kg" and ("weight" in tekst or "vekt" in tekst)):
                if "power" not in tekst:
                    kilder["vekt"].append(rad)
            elif "resting_heart_rate" in eid or "resting heart" in tekst or "hvilepuls" in tekst:
                kilder["hvilepuls"].append(rad)
            elif "vo2" in tekst and "cycling" not in tekst:
                kilder["vo2max"].append(rad)
            elif ("steps" in eid or "skritt" in tekst) and "lifetime" not in tekst and "goal" not in tekst and "average" not in tekst:
                kilder["skritt"].append(rad)
            elif ("body_fat" in eid or "fettprosent" in tekst or "body fat" in tekst) and enhet == "%":
                kilder["fettprosent"].append(rad)

        def poeng(r: dict, typ: str) -> float:
            t = f"{r['entity_id']} {r['navn']}".lower()
            p = 0.0
            if mitt and mitt in t:
                p += 3
            if any(n and n in t for n in andre):
                p -= 3
            if r["state"] in ("unavailable", "unknown", None):
                p -= 2
            if typ == "skritt":
                p += 2 if "yesterday" in t else (-1 if "today" in t or "device" in t else 0)
            if "garmin" in t:
                p += 0.5
            return p
        forslag = {}
        mine_kal = [x["entity_id"] for x in kilder["kalendere"]
                    if re.search(r"jobb|\bwork(?!out|day)|working|tripit|reise|arbeid|vakt", f"{x['entity_id']} {x['navn']}".lower().replace("_", " "))
                    and not re.search(r"garmin|workout|workday|holiday|helligdag", f"{x['entity_id']} {x['navn']}".lower())
                    and not any(n and n in f"{x['entity_id']} {x['navn']}".lower() for n in andre)]
        kilder["kalendere"].sort(key=lambda x: (x["entity_id"] not in mine_kal, x["navn"]))
        if mine_kal:
            forslag["kalendere"] = mine_kal[:4]
        for typ, liste in kilder.items():
            if typ == "kalendere":
                continue
            liste.sort(key=lambda r: -poeng(r, typ))
            if liste and poeng(liste[0], typ) > -1:
                forslag[typ] = liste[0]["entity_id"]
        return {"kilder": kilder, "forslag": forslag}

    async def _historikk(self, eid: str, dager: int, attributter: bool = False) -> list[dict]:
        start = (naa() - timedelta(days=dager)).isoformat()
        url = f"{CORE_API}/history/period/{start}?filter_entity_id={eid}&end_time={naa().isoformat()}"
        if not attributter:
            url += "&minimal_response&no_attributes"
        async with self._session.get(url, headers=self._hoder, timeout=aiohttp.ClientTimeout(total=60)) as r:
            if r.status != 200:
                return []
            data = await r.json()
        return data[0] if data else []

    async def synk_profil(self, profil: dict, historikk: bool = False) -> dict:
        """Henter aktiviteter og målinger fra koblede sensorer. Med historikk: også bakover i tid."""
        k = profil.get("koblinger") or {}
        pid = profil["id"]
        importert = maalt = 0
        if not self.aktiv or not k:
            return {"importert": 0, "maalinger": 0}
        tilstander = {s["entity_id"]: s for s in await self._tilstander()}
        # aktiviteter
        if (eid := k.get("aktiviteter")) and eid in tilstander:
            lister = [(tilstander[eid].get("attributes") or {}).get("last_activities") or []]
            if historikk:
                for st in await self._historikk(eid, 90, attributter=True):
                    lister.append((st.get("attributes") or {}).get("last_activities") or [])
            for liste in lister:
                for akt in liste:
                    if isinstance(akt, dict) and kropp.importer_garmin(self.sb, pid, akt):
                        importert += 1
        # målinger
        for typ in kropp.KOBLBARE_TALL:
            eid = k.get(typ)
            if not eid or eid not in tilstander:
                continue
            punkter = []
            if historikk:
                punkter += [(st.get("state"), st.get("last_changed")) for st in await self._historikk(eid, 365)]
            st = tilstander[eid]
            punkter.append((st.get("state"), st.get("last_changed")))
            igaar = "yesterday" in eid
            for verdi, tid in punkter:
                if verdi in (None, "unknown", "unavailable", "") or not tid:
                    continue
                dag = self.sb.lokal(fra_iso(tid)).date()
                # vekt og fett: dagen målingen kom; daglige verdier: dagen de gjelder
                if typ in kropp.DAGLIGE and tid == st.get("last_changed"):
                    dag = self.sb.lokal(naa()).date()
                if igaar:
                    dag -= timedelta(days=1)
                if typ == "skritt" and not igaar and dag == self.sb.lokal(naa()).date():
                    continue  # dagens skritt er ikke ferdige – vent til dagen er over
                if kropp.lagre_maaling(self.sb, pid, typ, verdi, dag.isoformat(), kilde="ha"):
                    maalt += 1
        # tekstverdier (HRV-status, treningsstatus)
        status = {}
        for typ in kropp.KOBLBARE_TEKST:
            eid = k.get(typ)
            if eid and eid in tilstander and tilstander[eid].get("state") not in (None, "unknown", "unavailable"):
                status[typ] = tilstander[eid]["state"]
        if status:
            self.sb.db.lagre_innstilling(f"status-{pid}", {**status, "tid": naa().isoformat(timespec="seconds")})
        # kalendere
        if k.get("kalendere"):
            try:
                await self.hent_kalender(profil)
            except Exception as e:  # noqa: BLE001
                log.warning("Kalender feilet: %s", e)
        koblet = kropp.koble_styrke(self.sb, pid)
        koblet += len(kropp.registrer_klokke_okter(self.sb, pid))
        hentet = 0
        if k.get("aktiviteter"):
            hentet = await self.hent_manglende_puls(profil, maks=6 if historikk else 3)
        if importert or maalt or koblet:
            self._ved_endring("profil", None)
        return {"importert": importert, "maalinger": maalt, "koblet": koblet, "pulskurver": hentet}

    # ------------------------------------------------------------ kalender
    async def hent_kalender(self, profil: dict, dager: int = 14) -> int:
        """Henter hendelser fra valgte kalendere og lagrer dem (bare tittel, tid og sted) til ukeplanen og AI-treneren."""
        from urllib.parse import quote
        fra = naa() - timedelta(days=1)
        til = naa() + timedelta(days=dager)
        hendelser = []
        for eid in (profil.get("koblinger") or {}).get("kalendere") or []:
            url = f"{CORE_API}/calendars/{eid}?start={quote(fra.isoformat())}&end={quote(til.isoformat())}"
            async with self._session.get(url, headers=self._hoder) as r:
                if r.status != 200:
                    continue
                for h in await r.json():
                    s, e = h.get("start") or {}, h.get("end") or {}
                    hendelser.append({"kalender": eid, "tittel": str(h.get("summary") or "")[:100],
                                      "start": s.get("dateTime") or s.get("date"), "slutt": e.get("dateTime") or e.get("date"),
                                      "heldag": "dateTime" not in s, "sted": str(h.get("location") or "")[:80]})
        self.sb.db.lagre_innstilling(f"kalender-{profil['id']}", {"tid": naa().isoformat(timespec="seconds"), "hendelser": hendelser})
        return len(hendelser)

    # ------------------------------------------------------------ pulskurver (TCX via garmin_connect.download_activity)
    HA_CONFIG = "/homeassistant"

    async def hent_puls(self, aid: int) -> bool:
        """Laster ned aktivitetsfila fra Garmin, leser pulsen og sletter fila igjen."""
        a = self.sb.db.en("SELECT * FROM aktiviteter WHERE id = ?", (aid,))
        if not a or a["kilde"] != "garmin" or not str(a.get("ekstern_id") or "").startswith("garmin-"):
            return False
        konto = self.garmin_konto(self.sb.profil(a["profil_id"]))
        if not self.aktiv or not konto:
            return False
        res = await self._tjeneste("garmin_connect", "download_activity", {
            "entity_id": konto, "activity_id": int(a["ekstern_id"].split("-", 1)[1]), "file_format": "tcx"}, svar=True)
        sti = str(res.get("file_path") or "")
        lokal = sti.replace("/config/", f"{self.HA_CONFIG}/", 1) if sti.startswith("/config/") else sti
        if not lokal or not os.path.exists(lokal):
            log.warning("Fant ikke aktivitetsfila %s – mangler appen tilgang til Home Assistant-mappa?", lokal)
            return False
        try:
            with open(lokal, encoding="utf-8") as f:
                start, serie = kropp.les_tcx(f.read())
        finally:
            try:
                os.remove(lokal)  # fila inneholder GPS-spor – den skal ikke bli liggende
            except OSError as e:
                log.info("Kunne ikke slette %s: %s", lokal, e)
        if not serie:
            kropp.lagre_puls(self.sb, aid, a["start"], [])
            return False
        kropp.lagre_puls(self.sb, aid, start or a["start"], serie)
        return True

    async def hent_manglende_puls(self, profil: dict, maks: int = 3) -> int:
        fra = (naa() - timedelta(days=21)).isoformat(timespec="seconds")
        kandidater = self.sb.db.alle(
            "SELECT a.id FROM aktiviteter a LEFT JOIN pulsdata p ON p.aktivitet_id = a.id WHERE a.profil_id = ? AND a.kilde = 'garmin' "
            "AND p.aktivitet_id IS NULL AND a.start >= ? AND (a.type != 'styrke' OR a.okt_id IS NOT NULL) ORDER BY a.start DESC LIMIT ?",
            (profil["id"], fra, maks))
        n = 0
        for r in kandidater:
            try:
                if await self.hent_puls(r["id"]):
                    n += 1
            except Exception as e:  # noqa: BLE001
                log.warning("Pulskurve for aktivitet %s feilet: %s", r["id"], e)
        return n

    async def _synk_loop(self) -> None:
        await asyncio.sleep(20)
        runde = 0
        while True:
            for p in self.sb.profiler():
                if p.get("koblinger"):
                    try:
                        await self.synk_profil(p)
                    except Exception as e:  # noqa: BLE001
                        log.warning("Henting av kroppsdata feilet for profil %s: %s", p["id"], e)
                if runde % 4 == 0 and (p.get("garmin_eksport") or {}).get("styrke"):
                    try:
                        await self.synk_garmin_styrke(p)
                    except Exception as e:  # noqa: BLE001
                        log.warning("Styrkeøkter til Garmin feilet for profil %s: %s", p["id"], e)
                if runde % 4 == 0 and (p.get("garmin_eksport") or {}).get("loping"):
                    try:
                        await self.synk_garmin_lopeokter(p)
                    except Exception as e:  # noqa: BLE001
                        log.warning("Løpeøkter til Garmin feilet for profil %s: %s", p["id"], e)
            runde += 1
            await asyncio.sleep(900)

    # ------------------------------------------------------------ til Garmin Connect
    async def _tjeneste(self, domene: str, tjeneste: str, data: dict, svar: bool = False):
        url = f"{CORE_API}/services/{domene}/{tjeneste}" + ("?return_response" if svar else "")
        async with self._session.post(url, headers=self._hoder, json=data, timeout=aiohttp.ClientTimeout(total=60)) as r:
            tekst = await r.text()
            if r.status >= 400:
                raise Feil(f"Garmin svarte med feil {r.status}: {tekst[:200]}")
            if svar:
                import json
                return (json.loads(tekst) or {}).get("service_response") or {}
            return None

    @staticmethod
    def garmin_konto(p: dict) -> str | None:
        """Garmin-sensoren som peker ut riktig Garmin-konto for profilen."""
        k = p.get("koblinger") or {}
        for typ in ("aktiviteter", "vekt", "hvilepuls", "vo2max", "skritt"):
            if k.get(typ):
                return k[typ]
        return None

    async def send_okt_til_garmin(self, oid: int, tving: bool = False) -> bool:
        o = self.sb.okt(oid)
        p = self.sb.profil(o["profil_id"])
        if not self.aktiv or o["status"] != "fullfort" or (o.get("garmin_sendt") and not tving):
            return False
        if not tving and not (p.get("garmin_eksport") or {}).get("okter"):
            return False
        konto = self.garmin_konto(p)
        if not konto:
            raise Feil("Koble profilen til Garmin under Helse først")
        start = self.sb.lokal(o["startet"])
        await self._tjeneste("garmin_connect", "create_activity", {
            "entity_id": konto, "activity_name": f"Styrketrening: {o['dag_navn']}"[:60], "activity_type": "fitness_equipment",
            "start_datetime": start.replace(tzinfo=None).isoformat(timespec="seconds"),
            "duration_min": max(1, o["nokkeltall"]["minutter"]), "time_zone": str(self.sb.tz)})
        self.sb.db.oppdater("okter", oid, {"garmin_sendt": naa().isoformat(timespec="seconds")})
        return True

    async def synk_garmin_styrke(self, p: dict) -> dict:
        """Én Garmin-økt per programdag med dagens vekter. Neste økt legges i kalenderen (i dag, eller i morgen
        hvis du allerede har trent i dag), så klokka henter den automatisk."""
        import garmin
        konto = self.garmin_konto(p)
        if not self.aktiv or not konto:
            return {"nye": 0, "oppdatert": 0, "fjernet": 0}
        pid = p["id"]
        aktiv = (p.get("garmin_eksport") or {}).get("styrke")
        prog = self.sb.aktivt_program(pid) if aktiv else None
        lagret = {r["dag_id"]: r for r in self.sb.db.alle("SELECT * FROM garmin_styrke WHERE profil_id = ?", (pid,))}
        dager = {d["id"]: d for d in (prog["dager"] if prog else [])}
        nye = oppdatert = fjernet = 0
        for dag_id, r in lagret.items():
            if dag_id not in dager:
                try:
                    await self._tjeneste("garmin_connect", "delete_workout", {"entity_id": konto, "workout_id": int(r["workout_id"])})
                except Feil as e:
                    log.info("Klarte ikke slette Garmin-økt: %s", e)
                self.sb.db.kjor("DELETE FROM garmin_styrke WHERE id = ?", (r["id"],))
                fjernet += 1
        if not prog:
            return {"nye": nye, "oppdatert": oppdatert, "fjernet": fjernet}
        tid = naa().isoformat(timespec="seconds")
        for dag_id, dag in dager.items():
            w = garmin.bygg_workout(dag["navn"], self.sb.garmin_dagplan(pid, dag, prog))
            fa = garmin.fingeravtrykk(w)
            r = lagret.get(dag_id)
            if r and r["fingeravtrykk"] == fa:
                continue
            if r:
                await self._tjeneste("garmin_connect", "update_workout", {"entity_id": konto, "workout_id": int(r["workout_id"]), "workout": w})
                self.sb.db.oppdater("garmin_styrke", r["id"], {"fingeravtrykk": fa, "tid": tid})
                oppdatert += 1
            else:
                res = await self._tjeneste("garmin_connect", "create_workout", {"entity_id": konto, "workout": w}, svar=True)
                self.sb.db.sett_inn("garmin_styrke", {"profil_id": pid, "dag_id": dag_id, "workout_id": str(res.get("workout_id")),
                                                      "fingeravtrykk": fa, "tid": tid})
                nye += 1
        # neste økt i kalenderen
        neste = self.sb.neste_dag(pid, prog)
        i_dag = self.sb.lokal(naa()).date()
        trent_i_dag = any(self.sb.lokal(o["startet"]).date() == i_dag for o in self.sb.db.alle(
            "SELECT startet FROM okter WHERE profil_id = ? AND status = 'fullfort' ORDER BY startet DESC LIMIT 3", (pid,)))
        dato = (i_dag + timedelta(days=1 if trent_i_dag else 0)).isoformat()
        if neste:
            import ukeplan
            planlagt = ukeplan.neste_styrkedato(self.sb, pid, neste["id"])
            if planlagt and planlagt >= i_dag.isoformat() and not (planlagt == i_dag.isoformat() and trent_i_dag):
                dato = planlagt
        rader = self.sb.db.alle("SELECT * FROM garmin_styrke WHERE profil_id = ?", (pid,))
        for r in rader:
            riktig = neste and r["dag_id"] == neste["id"] and r["schedule_dato"] == dato
            if r.get("schedule_id") and not riktig:
                try:
                    await self._tjeneste("garmin_connect", "unschedule_workout", {"entity_id": konto, "schedule_id": int(r["schedule_id"])})
                except Feil as e:
                    log.info("Klarte ikke fjerne fra Garmin-kalenderen: %s", e)
                self.sb.db.oppdater("garmin_styrke", r["id"], {"schedule_id": None, "schedule_dato": None})
        r = next((x for x in self.sb.db.alle("SELECT * FROM garmin_styrke WHERE profil_id = ?", (pid,)) if neste and x["dag_id"] == neste["id"]), None)
        if r and r["schedule_dato"] != dato:
            res = await self._tjeneste("garmin_connect", "schedule_workout", {"entity_id": konto, "workout_id": int(r["workout_id"]), "date": dato}, svar=True)
            self.sb.db.oppdater("garmin_styrke", r["id"], {"schedule_id": str(res.get("schedule_id") or ""), "schedule_dato": dato})
        return {"nye": nye, "oppdatert": oppdatert, "fjernet": fjernet, "planlagt": dato if r else None}

    async def synk_garmin_lopeokter(self, p: dict) -> dict:
        """Holder Garmin-kalenderen i takt med løpeplanen: nye turer legges inn, endrede byttes ut."""
        import loping
        konto = self.garmin_konto(p)
        if not self.aktiv or not konto:
            return {"lagt_inn": 0, "fjernet": 0}
        pid = p["id"]
        i_dag = self.sb.lokal(naa()).date().isoformat()
        aktiv = (p.get("garmin_eksport") or {}).get("loping")
        planlagt = {x["dato"]: x for x in loping.planlagte_garmin_okter(self.sb, pid)} if aktiv else {}
        lagret = {r["dato"]: r for r in self.sb.db.alle("SELECT * FROM garmin_okter WHERE profil_id = ? AND dato >= ?", (pid, i_dag))}
        lagt_inn = fjernet = 0
        for dato, r in lagret.items():
            if dato not in planlagt or planlagt[dato]["nokkel"] != r["nokkel"]:
                if r.get("workout_id"):
                    try:
                        await self._tjeneste("garmin_connect", "delete_workout", {"entity_id": konto, "workout_id": int(r["workout_id"])})
                    except Feil as e:
                        log.info("Klarte ikke slette Garmin-økt %s: %s", r["workout_id"], e)
                self.sb.db.kjor("DELETE FROM garmin_okter WHERE id = ?", (r["id"],))
                fjernet += 1
        for dato, x in planlagt.items():
            if dato in lagret and lagret[dato]["nokkel"] == x["nokkel"]:
                continue
            res = await self._tjeneste("garmin_connect", "create_workout", {
                "entity_id": konto, "workout": loping.garmin_okt(x["okt"]), "date": dato}, svar=True)
            self.sb.db.kjor("INSERT OR REPLACE INTO garmin_okter (profil_id, periode_id, dato, nokkel, workout_id, schedule_id, tid) "
                            "VALUES (?, ?, ?, ?, ?, ?, ?)", (pid, x["periode_id"], dato, x["nokkel"], str(res.get("workout_id") or ""),
                                                            str(res.get("schedule_id") or ""), naa().isoformat(timespec="seconds")))
            lagt_inn += 1
        return {"lagt_inn": lagt_inn, "fjernet": fjernet}

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

    # oppgaver som krever mest vurdering – kan gå til en kraftigere modell
    PLANLEGGING = {"lag program", "juster program", "ny blokk", "ukeplan", "startvekter", "intervalløkt"}

    async def _velg_entitet(self, oppgave: str = "") -> str | None:
        if oppgave in self.PLANLEGGING and self.sb.inn.get("ai_entitet_plan"):
            return self.sb.inn["ai_entitet_plan"]
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
        entitet = await self._velg_entitet(oppgave)
        if not entitet:
            raise Feil("Fant ingen AI i Home Assistant. Sett opp en AI-integrasjon (f.eks. Anthropic) med «AI-oppgave».")
        tidsavbrudd = aiohttp.ClientTimeout(total=240)
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
