"""API-ruter for Styrkeboka – uavhengig av webrammeverk (aiohttp i drift, enkel testserver lokalt)."""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable, Protocol

import ai
import kropp
import loping
import program as P
from db import naa
from logikk import FARGER, TYPER, Feil, Styrkeboka
from ovelser import MONSTER, MUSKLER, UTSTYR

log = logging.getLogger("styrkeboka.api")


class AIKlient(Protocol):
    aktiv: bool

    async def spor(self, oppgave: str, instruksjoner: str) -> Any: ...

    async def ai_entiteter(self) -> list[dict]: ...


@dataclass
class Foresporsel:
    metode: str
    sti: str
    query: dict = field(default_factory=dict)
    body: Any = None
    bruker: str | None = None       # visningsnavn
    brukernavn: str | None = None   # innloggingsnavn
    params: dict = field(default_factory=dict)

    def int(self, navn: str) -> int:
        return int(self.params[navn])

    def q_int(self, navn: str) -> int | None:
        v = self.query.get(navn)
        return int(v) if v not in (None, "") else None

    @property
    def data(self) -> dict:
        return self.body if isinstance(self.body, dict) else {}


@dataclass
class Svar:
    data: Any = None
    status: int = 200
    tekst: str | None = None
    innholdstype: str = "application/json"
    hoder: dict = field(default_factory=dict)


Handler = Callable[[Foresporsel], Awaitable[Any]]


class API:
    def __init__(self, sb: Styrkeboka, ai_klient: AIKlient):
        self.sb = sb
        self.ai = ai_klient
        self.ruter: list[tuple[str, re.Pattern, Handler]] = []
        self._registrer()

    def rute(self, metode: str, monster: str):
        regex = re.compile("^" + re.sub(r"\{(\w+)\}", r"(?P<\1>\\d+)", monster) + "$")

        def dek(fn: Handler) -> Handler:
            self.ruter.append((metode, regex, fn))
            return fn
        return dek

    async def handter(self, req: Foresporsel) -> Svar:
        for metode, regex, fn in self.ruter:
            if metode != req.metode:
                continue
            m = regex.match(req.sti)
            if m:
                req.params = m.groupdict()
                try:
                    res = await fn(req)
                except Feil as e:
                    return Svar({"feil": str(e)}, 400)
                except (ValueError, TypeError, KeyError) as e:
                    log.info("Ugyldig forespørsel %s %s: %s", req.metode, req.sti, e)
                    return Svar({"feil": "Ugyldig forespørsel"}, 400)
                return res if isinstance(res, Svar) else Svar(res)
        return Svar({"feil": "Finnes ikke"}, 404)

    # ------------------------------------------------------------------ ruter
    def _registrer(self) -> None:  # noqa: C901 – en lang, men flat liste
        sb = self.sb
        r = self.rute

        @r("GET", "/api/start")
        async def start(req):
            meg = sb.profil_for_bruker(req.bruker, req.brukernavn)
            return {
                "bruker": req.bruker, "brukernavn": req.brukernavn, "meg": meg["id"] if meg else None,
                "profiler": sb.profiler(), "utstyrsprofiler": sb.utstyrsprofiler(), "innstillinger": sb.inn,
                "ovelser": sb.ovelser(), "monster": MONSTER, "utstyr": UTSTYR, "muskler": MUSKLER, "typer": TYPER,
                "maal": P.MAAL, "erfaring": P.ERFARING, "kan_anslaas": sorted(P.FORHOLD), "farger": FARGER, "ai_tilgjengelig": self.ai.aktiv,
                "naa": naa().isoformat(),
            }

        @r("GET", "/api/profiler/{pid}/oversikt")
        async def oversikt(req):
            return sb.oversikt(req.int("pid"), req.q_int("sted"))

        # ---- profiler, steder og øvelser
        @r("POST", "/api/profiler")
        async def ny_profil(req):
            return {"profil": sb.lagre_profil(req.data)}

        @r("PATCH", "/api/profiler/{pid}")
        async def endre_profil(req):
            return {"profil": sb.lagre_profil(req.data, req.int("pid"))}

        @r("DELETE", "/api/profiler/{pid}")
        async def slett_profil(req):
            sb.slett_profil(req.int("pid"))
            return {"ok": True}

        @r("POST", "/api/utstyrsprofiler")
        async def nytt_sted(req):
            return {"utstyrsprofil": sb.lagre_utstyrsprofil(req.data)}

        @r("PATCH", "/api/utstyrsprofiler/{uid}")
        async def endre_sted(req):
            return {"utstyrsprofil": sb.lagre_utstyrsprofil(req.data, req.int("uid"))}

        @r("DELETE", "/api/utstyrsprofiler/{uid}")
        async def slett_sted(req):
            sb.slett_utstyrsprofil(req.int("uid"))
            return {"ok": True}

        @r("POST", "/api/ovelser")
        async def ny_ovelse(req):
            return {"ovelse": sb.lagre_egen_ovelse(req.data)}

        @r("PATCH", "/api/ovelser/{oid}")
        async def endre_ovelse(req):
            return {"ovelse": sb.lagre_egen_ovelse(req.data, req.int("oid"))}

        @r("POST", "/api/alternativer")
        async def alternativer(req):
            d = req.data
            return {"alternativer": sb.alternativer(str(d["ovelse"]), sb.utstyr_for(d.get("utstyrsprofil_id")))}

        # ---- innstillinger
        @r("PUT", "/api/innstillinger")
        async def innstillinger(req):
            return {"innstillinger": sb.lagre_innstillinger(req.data)}

        @r("GET", "/api/ai/entiteter")
        async def ai_entiteter(_req):
            try:
                return {"entiteter": await self.ai.ai_entiteter()}
            except Exception as e:  # noqa: BLE001
                log.warning("Klarte ikke hente AI-entiteter: %s", e)
                return {"entiteter": [], "feil": "Fikk ikke hentet AI-er fra Home Assistant"}

        # ---- program
        @r("GET", "/api/profiler/{pid}/programmer")
        async def programmer(req):
            pid = req.int("pid")
            aktivt = sb.aktivt_program(pid)
            return {"aktivt": aktivt, "programmer": sb.programmer(pid)}

        @r("GET", "/api/programmer/{prid}")
        async def program(req):
            prid = req.int("prid")
            return {"program": sb.program(prid), "versjoner": sb.versjoner(prid)}

        @r("POST", "/api/profiler/{pid}/forslag")
        async def forslag(req):
            return {"forslag": sb.foreslaa_program(req.int("pid"), req.data.get("utstyrsprofil_id"))}

        @r("POST", "/api/profiler/{pid}/programmer")
        async def lagre_nytt(req):
            d = req.data
            kilde = d.get("kilde") if d.get("kilde") in ("mal", "ai", "egen") else "egen"
            return {"program": sb.lagre_program(req.int("pid"), d["program"], kilde=kilde,
                                                beskrivelse=str(d.get("beskrivelse") or "")[:200], aktiver=d.get("aktiver", True))}

        @r("PUT", "/api/programmer/{prid}")
        async def lagre_program(req):
            d = req.data
            p = sb.program(req.int("prid"))
            kilde = d.get("kilde") if d.get("kilde") in ("ai", "egen") else "egen"
            return {"program": sb.lagre_program(p["profil_id"], d["program"], kilde=kilde, prid=p["id"],
                                                beskrivelse=str(d.get("beskrivelse") or "Endret")[:200], aktiver=bool(p["aktiv"]))}

        @r("POST", "/api/programmer/{prid}/aktiver")
        async def aktiver(req):
            p = sb.program(req.int("prid"))
            sb.aktiver_program(p["profil_id"], p["id"])
            return {"ok": True}

        @r("DELETE", "/api/programmer/{prid}")
        async def arkiver(req):
            p = sb.program(req.int("prid"))
            sb.arkiver_program(p["profil_id"], p["id"])
            return {"ok": True}

        # ---- kropp og kondisjon
        @r("GET", "/api/profiler/{pid}/kropp")
        async def kropp_oversikt(req):
            return kropp.oversikt(sb, req.int("pid"))

        @r("GET", "/api/profiler/{pid}/maalinger")
        async def hent_maalinger(req):
            typ = str(req.query.get("type") or "vekt")
            if typ not in kropp.MAALETYPER:
                raise Feil("Ukjent måling")
            return {"type": typ, "maalinger": kropp.maalinger(sb, req.int("pid"), typ, req.q_int("dager"))}

        @r("POST", "/api/profiler/{pid}/maalinger")
        async def ny_maaling(req):
            d = req.data
            pid = req.int("pid")
            lagret = []
            for typ, verdi in (d.get("verdier") or {d.get("type"): d.get("verdi")}).items():
                if typ in kropp.MAALETYPER and verdi not in (None, ""):
                    m = kropp.lagre_maaling(sb, pid, typ, verdi, d.get("dato"))
                    if not m:
                        raise Feil(f"Ugyldig verdi for {kropp.MAALETYPER[typ]['navn'].lower()}")
                    lagret.append(m)
            if not lagret:
                raise Feil("Skriv inn minst én verdi")
            sb._varsle("profil", None)  # noqa: SLF001
            return {"lagret": lagret}

        @r("DELETE", "/api/maalinger/{mid}")
        async def slett_maaling(req):
            kropp.slett_maaling(sb, req.int("mid"))
            return {"ok": True}

        @r("POST", "/api/profiler/{pid}/aktiviteter")
        async def ny_aktivitet(req):
            a = kropp.lagre_aktivitet(sb, req.int("pid"), req.data)
            sb._varsle("profil", None)  # noqa: SLF001
            return {"aktivitet": a}

        @r("PATCH", "/api/aktiviteter/{aid}")
        async def endre_aktivitet(req):
            a = sb.db.en("SELECT * FROM aktiviteter WHERE id = ?", (req.int("aid"),))
            if not a:
                raise Feil("Fant ikke aktiviteten")
            if a["kilde"] != "manuell":
                sb.db.oppdater("aktiviteter", a["id"], {"notat": str(req.data.get("notat") or "")[:300]})
                return {"aktivitet": kropp.aktivitet(sb, a["id"])}
            return {"aktivitet": kropp.lagre_aktivitet(sb, a["profil_id"], req.data, a["id"])}

        @r("GET", "/api/aktiviteter/{aid}")
        async def hent_aktivitet(req):
            a = kropp.aktivitet(sb, req.int("aid"))
            if not a:
                raise Feil("Fant ikke aktiviteten")
            p = kropp.puls(sb, a["id"])
            return {"aktivitet": a, "puls": (p or {}).get("data") or [], "puls_hentet": p is not None}

        @r("POST", "/api/aktiviteter/{aid}/puls")
        async def hent_aktivitet_puls(req):
            if not hasattr(self.ai, "hent_puls"):
                raise Feil("Garmin er ikke tilgjengelig")
            ok = await self.ai.hent_puls(req.int("aid"))
            p = kropp.puls(sb, req.int("aid"))
            if not ok and not (p or {}).get("data"):
                raise Feil("Fant ingen pulsdata for denne aktiviteten")
            return {"puls": (p or {}).get("data") or []}

        @r("POST", "/api/okter/{oid}/klokke")
        async def okt_klokke(req):
            oid = req.int("oid")
            o = sb.okt(oid)
            kropp.koble_styrke(sb, o["profil_id"])
            if hasattr(self.ai, "synk_profil") and not sb.okt(oid).get("klokke"):
                await self.ai.synk_profil(sb.profil(o["profil_id"]))
            k = sb.okt(oid).get("klokke")
            if k and not k["puls_hentet"] and hasattr(self.ai, "hent_puls"):
                await self.ai.hent_puls(k["id"])
            return {"okt": sb.okt(oid)}

        @r("DELETE", "/api/aktiviteter/{aid}")
        async def slett_aktivitet(req):
            sb.db.slett("aktiviteter", req.int("aid"))
            return {"ok": True}

        @r("GET", "/api/profiler/{pid}/ha-kilder")
        async def ha_kilder(req):
            if not hasattr(self.ai, "kilder"):
                return {"kilder": {}, "forslag": {}}
            try:
                return await self.ai.kilder(sb.profil(req.int("pid")))
            except Exception as e:  # noqa: BLE001
                log.warning("Klarte ikke hente sensorer: %s", e)
                return {"kilder": {}, "forslag": {}, "feil": "Fikk ikke hentet sensorer fra Home Assistant"}

        @r("PUT", "/api/profiler/{pid}/koblinger")
        async def koblinger(req):
            pid = req.int("pid")
            p = sb.lagre_profil({"koblinger": req.data.get("koblinger") or {}}, pid)
            res = {"importert": 0, "maalinger": 0}
            if hasattr(self.ai, "synk_profil"):
                try:
                    res = await self.ai.synk_profil(p, historikk=True)
                except Exception as e:  # noqa: BLE001
                    log.warning("Synk feilet: %s", e)
                    raise Feil("Lagret, men klarte ikke å hente data fra Home Assistant nå") from e
            return {"profil": sb.profil(pid), **res}

        @r("POST", "/api/profiler/{pid}/synk")
        async def synk(req):
            if not hasattr(self.ai, "synk_profil"):
                return {"importert": 0, "maalinger": 0}
            return await self.ai.synk_profil(sb.profil(req.int("pid")), historikk=bool(req.data.get("historikk")))

        # ---- Garmin-eksport
        @r("PUT", "/api/profiler/{pid}/garmin")
        async def garmin_eksport(req):
            p = sb.lagre_profil({"garmin_eksport": req.data}, req.int("pid"))
            res = {}
            if hasattr(self.ai, "synk_garmin_lopeokter"):
                if any(p["garmin_eksport"].values()) and not self.ai.garmin_konto(p):
                    raise Feil("Koble profilen til Garmin-sensorene først (Helse → Hent data fra Home Assistant)")
                try:
                    res = await self.ai.synk_garmin_lopeokter(p)
                    if hasattr(self.ai, "synk_garmin_styrke"):
                        res["styrke"] = await self.ai.synk_garmin_styrke(p)
                except Exception as e:  # noqa: BLE001
                    log.warning("Til Garmin: %s", e)
                    raise Feil(f"Lagret, men klarte ikke å oppdatere Garmin: {e}") from e
            return {"garmin_eksport": p["garmin_eksport"], **res}

        @r("POST", "/api/okter/{oid}/garmin")
        async def okt_til_garmin(req):
            if not hasattr(self.ai, "send_okt_til_garmin"):
                raise Feil("Garmin er ikke tilgjengelig")
            await self.ai.send_okt_til_garmin(req.int("oid"), tving=True)
            return {"okt": sb.okt(req.int("oid"))}

        async def _lope_synk(pid: int) -> None:
            if hasattr(self.ai, "synk_garmin_lopeokter"):
                try:
                    await self.ai.synk_garmin_lopeokter(sb.profil(pid))
                except Exception as e:  # noqa: BLE001
                    log.warning("Løpeøkter til Garmin: %s", e)

        # ---- dagsform og ukeplan
        @r("GET", "/api/profiler/{pid}/dagsform")
        async def dagsform_status(req):
            import dagsform
            return {"dagsform": dagsform.status(sb, req.int("pid"))}

        @r("GET", "/api/profiler/{pid}/ukeplan")
        async def hent_ukeplan(req):
            import ukeplan
            return {"ukeplan": ukeplan.hent(sb, req.int("pid"))}

        @r("POST", "/api/profiler/{pid}/ukeplan/ai")
        async def ai_ukeplan(req):
            import ukeplan
            pid = req.int("pid")
            p = sb.profil(pid)
            if hasattr(self.ai, "hent_kalender") and (p.get("koblinger") or {}).get("kalendere"):
                try:
                    await self.ai.hent_kalender(p)
                except Exception as e:  # noqa: BLE001
                    log.warning("Kalender: %s", e)
            data = ai.les_json(await self.ai.spor("ukeplan", ai.oppgave_ukeplan(sb, pid, str(req.data.get("onske") or ""))))
            plan = ukeplan.valider_ai_plan(sb, pid, data)
            ukeplan.lagre(sb, pid, plan)
            sb.logg_ai(pid, "ukeplan", str(req.data.get("onske") or ""), plan["oppsummering"])
            sb._varsle("ukeplan", {"profil_id": pid})  # noqa: SLF001
            return {"ukeplan": plan}

        # ------------------------------------------------ intervalløkter (HIIT, Tabata, sirkel, EMOM, AMRAP)
        @r("GET", "/api/profiler/{pid}/intervaller")
        async def intervaller(req):
            import intervall
            pid = req.int("pid")
            upid = int(req.query["sted"]) if str(req.query.get("sted") or "").isdigit() else None
            return {"formater": intervall.FORMATER, "fokus": {k: v["navn"] for k, v in intervall.FOKUS.items()},
                    "maler": intervall.maler(sb, pid, upid), "historikk": intervall.historikk(sb, pid)}

        @r("POST", "/api/profiler/{pid}/intervaller/forslag")
        async def intervall_forslag(req):
            import intervall
            d = req.data or {}
            return intervall.foreslaa(sb, req.int("pid"), str(d.get("format") or "hiit"), str(d.get("fokus") or "helkropp"),
                                      int(d["antall"]) if str(d.get("antall") or "").isdigit() else None,
                                      int(d["sted"]) if str(d.get("sted") or "").isdigit() else None)

        @r("POST", "/api/profiler/{pid}/intervaller/ai")
        async def intervall_ai(req):
            import intervall
            pid = req.int("pid")
            d = req.data or {}
            fmt = str(d.get("format") or "hiit")
            if fmt not in intervall.FORMATER:
                raise Feil("Ukjent format")
            minutter = max(4, min(60, int(d.get("minutter") or 20)))
            upid = int(d["sted"]) if str(d.get("sted") or "").isdigit() else None
            svar = ai.les_json(await self.ai.spor("intervalløkt", ai.oppgave_intervall(
                sb, pid, fmt, minutter, str(d.get("fokus") or "helkropp"), upid, str(d.get("onske") or ""))))
            oppsett = intervall.valider(sb, {**(svar.get("oppsett") or {}), "format": fmt})
            sb.logg_ai(pid, "intervalløkt", str(d.get("onske") or ""), str(svar.get("begrunnelse") or ""))
            return {"navn": str(svar.get("navn") or intervall.FORMATER[fmt]["navn"])[:60], "oppsett": oppsett,
                    "sekunder": intervall.total_sekunder(oppsett), "begrunnelse": str(svar.get("begrunnelse") or "")[:400],
                    "tips": [str(t)[:200] for t in (svar.get("tips") or [])][:4]}

        @r("POST", "/api/profiler/{pid}/intervaller")
        async def lagre_intervall(req):
            import intervall
            pid = req.int("pid")
            d = req.data or {}
            forrige = intervall.beste(sb, pid, str(d.get("navn") or ""), str((d.get("oppsett") or {}).get("format") or ""))
            x = intervall.lagre(sb, pid, d)
            sb._varsle("aktivitet", {"profil_id": pid})  # noqa: SLF001
            return {"intervall": x, "forrige_beste": forrige}

        @r("DELETE", "/api/intervaller/{iid}")
        async def slett_intervall(req):
            import intervall
            intervall.slett(sb, req.int("iid"))
            return {"ok": True}

        @r("DELETE", "/api/profiler/{pid}/ukeplan")
        async def nullstill_ukeplan(req):
            import ukeplan
            sb.db.kjor("DELETE FROM innstillinger WHERE nokkel = ?", (f"ukeplan-{req.int('pid')}",))
            sb._varsle("ukeplan", {"profil_id": req.int("pid")})  # noqa: SLF001
            return {"ukeplan": ukeplan.hent(sb, req.int("pid"))}

        @r("POST", "/api/okter/{oid}/lettere")
        async def lettere(req):
            return {"okt": sb.lettere_okt(req.int("oid"))}

        # ---- løpeperioder
        @r("GET", "/api/profiler/{pid}/loping")
        async def loping_status(req):
            return loping.status(sb, req.int("pid"))

        @r("POST", "/api/profiler/{pid}/loping")
        async def ny_periode(req):
            p = loping.lagre_periode(sb, req.int("pid"), req.data)
            await _lope_synk(req.int("pid"))
            return {"periode": p}

        @r("PATCH", "/api/loping/{lid}")
        async def endre_periode(req):
            p = sb.db.en("SELECT * FROM loepeperioder WHERE id = ?", (req.int("lid"),))
            if not p:
                raise Feil("Fant ikke perioden")
            ny = loping.lagre_periode(sb, p["profil_id"], {**p, **req.data}, p["id"])
            await _lope_synk(p["profil_id"])
            return {"periode": ny}

        @r("DELETE", "/api/loping/{lid}")
        async def slett_periode(req):
            p = sb.db.en("SELECT profil_id FROM loepeperioder WHERE id = ?", (req.int("lid"),))
            sb.db.slett("loepeperioder", req.int("lid"))
            if p:
                await _lope_synk(p["profil_id"])
            return {"ok": True}

        # ---- startvekter
        @r("GET", "/api/profiler/{pid}/startvekter")
        async def startvekter(req):
            pid = req.int("pid")
            return {**sb.beregn_startvekter(pid), "lagret": sb.startvekter(pid)}

        @r("POST", "/api/profiler/{pid}/startvekter/beregn")
        async def beregn_startvekter(req):
            pid = req.int("pid")
            d = req.data
            lokalt = sb.beregn_startvekter(pid, d.get("kjente") or [], d.get("kroppsvekt"))
            kommentar, kilde = "", "beregnet"
            if d.get("ai"):
                svar = ai.les_json(await self.ai.spor("startvekter", ai.oppgave_startvekter(sb, pid, lokalt)))
                vekter = svar.get("vekter") or {}
                for f in lokalt["forslag"]:
                    v = vekter.get(f["ovelse"])
                    try:
                        v = float(str(v).replace(",", ".")) if v not in (None, "") else None
                    except ValueError:
                        v = None
                    if v and 0 < v < 500:
                        f["kg"], f["grunnlag"] = P.rund_til_utstyr(sb.ovelse(f["ovelse"]), v), "AI-treneren"
                kommentar, kilde = str(svar.get("kommentar") or "")[:600], "ai"
                sb.logg_ai(pid, "startvekter", "", kommentar)
            return {**lokalt, "kommentar": kommentar, "kilde": kilde}

        @r("PUT", "/api/profiler/{pid}/startvekter")
        async def lagre_startvekter(req):
            d = req.data
            kilde = d.get("kilde") if d.get("kilde") in ("ai", "beregnet", "manuell") else "manuell"
            n = sb.lagre_startvekter(req.int("pid"), d.get("vekter") or {}, kilde)
            sb._varsle("startvekter", {"profil_id": req.int("pid")})  # noqa: SLF001
            return {"lagret": n}

        # ---- blokker
        @r("PATCH", "/api/programmer/{prid}/blokk")
        async def blokk_innst(req):
            return {"program": sb.lagre_blokkinnstillinger(req.int("prid"), req.data)}

        @r("POST", "/api/programmer/{prid}/blokkforslag")
        async def blokkforslag(req):
            prid = req.int("prid")
            p = sb.program(prid)
            if not req.data.get("ai"):
                return {"forslag": sb.foreslaa_ny_blokk(prid), "kilde": "mal"}
            data = ai.les_json(await self.ai.spor("ny blokk", ai.oppgave_ny_blokk(sb, p["profil_id"], prid)))
            v = sb._valider_program(sb.sikre_faste(prid, sb._valider_program(data)))  # noqa: SLF001
            endringer = [str(x)[:300] for x in (data.get("endringer") or []) if str(x).strip()][:12]
            sb.logg_ai(p["profil_id"], "ny blokk", f"Blokk {p['blokk']['nr'] + 1}", v["begrunnelse"])
            return {"forslag": {**sb.berik_forhandsvisning(v), "endringer": endringer}, "kilde": "ai"}

        @r("POST", "/api/programmer/{prid}/ny-blokk")
        async def ny_blokk(req):
            d = req.data
            kilde = d.get("kilde") if d.get("kilde") in ("ai", "mal", "egen") else "egen"
            return {"program": sb.start_ny_blokk(req.int("prid"), d.get("program"), kilde=kilde,
                                                 beskrivelse=str(d.get("beskrivelse") or "")[:200])}

        @r("POST", "/api/versjoner/{vid}/gjenopprett")
        async def gjenopprett(req):
            v = sb.db.en("SELECT program_id FROM programversjoner WHERE id = ?", (req.int("vid"),))
            if not v:
                raise Feil("Fant ikke versjonen")
            p = sb.program(v["program_id"])
            return {"program": sb.gjenopprett_versjon(p["profil_id"], req.int("vid"))}

        # ---- økter
        @r("POST", "/api/profiler/{pid}/okter")
        async def start_okt(req):
            d = req.data
            return {"okt": sb.start_okt(req.int("pid"), d.get("dag_id"), d.get("utstyrsprofil_id"), av=req.bruker)}

        @r("POST", "/api/profiler/{pid}/tidligere-okt")
        async def tidligere_okt(req):
            return {"okt": sb.registrer_tidligere_okt(req.int("pid"), req.data, av=req.bruker)}

        @r("GET", "/api/okter/{oid}")
        async def okt(req):
            return {"okt": sb.okt(req.int("oid"))}

        @r("PATCH", "/api/okter/{oid}")
        async def endre_okt(req):
            return {"okt": sb.endre_okt(req.int("oid"), req.data)}

        @r("DELETE", "/api/okter/{oid}")
        async def slett_okt(req):
            sb.avbryt_okt(req.int("oid"))
            return {"ok": True}

        @r("POST", "/api/okter/{oid}/sett")
        async def logg_sett(req):
            s = sb.logg_sett(req.int("oid"), req.data)
            return {"sett": s, "okt": sb.okt(req.int("oid"))}

        @r("PATCH", "/api/sett/{sid}")
        async def endre_sett(req):
            s = sb.endre_sett(req.int("sid"), req.data)
            return {"sett": s, "okt": sb.okt(s["okt_id"])}

        @r("DELETE", "/api/sett/{sid}")
        async def slett_sett(req):
            s = sb.db.en("SELECT okt_id FROM sett WHERE id = ?", (req.int("sid"),))
            sb.slett_sett(req.int("sid"))
            return {"okt": sb.okt(s["okt_id"]) if s else None}

        @r("POST", "/api/okter/{oid}/ovelser")
        async def legg_til(req):
            return {"okt": sb.legg_til_ovelse(req.int("oid"), req.data)}

        @r("PATCH", "/api/okt-ovelser/{ooid}")
        async def endre_oo(req):
            return {"okt": sb.endre_okt_ovelse(req.int("ooid"), req.data)}

        @r("POST", "/api/okt-ovelser/{ooid}/flytt")
        async def flytt_oo(req):
            return {"okt": sb.flytt_okt_ovelse(req.int("ooid"), int(req.data.get("retning") or 1))}

        @r("DELETE", "/api/okt-ovelser/{ooid}")
        async def slett_oo(req):
            return {"okt": sb.slett_okt_ovelse(req.int("ooid"))}

        @r("POST", "/api/okter/{oid}/avslutt")
        async def avslutt(req):
            res = sb.avslutt_okt(req.int("oid"), req.data)
            return res

        @r("GET", "/api/okter/{oid}/oppsummering")
        async def oppsummering(req):
            return sb.okt_oppsummering(req.int("oid"))

        # ---- historikk
        @r("GET", "/api/profiler/{pid}/historikk")
        async def historikk(req):
            pid = req.int("pid")
            return {"okter": sb.historikk(pid), "ovelser": sb.ovelser_med_historikk(pid), "statistikk": sb.statistikk(pid)}

        @r("GET", "/api/profiler/{pid}/ovelse")
        async def ovelse_hist(req):
            return sb.ovelse_historikk(req.int("pid"), str(req.query["nokkel"]))

        @r("GET", "/api/eksport.csv")
        async def eksport(req):
            return Svar(tekst=sb.csv(req.q_int("profil")), innholdstype="text/csv",
                        hoder={"Content-Disposition": 'attachment; filename="styrkeboka.csv"'})

        # ---- AI
        @r("POST", "/api/profiler/{pid}/ai/program")
        async def ai_program(req):
            pid = req.int("pid")
            d = req.data
            if d.get("program_id"):
                instr = ai.oppgave_juster_program(sb, pid, int(d["program_id"]), str(d.get("onske") or ""))
                oppg = "juster program"
            else:
                instr = ai.oppgave_lag_program(sb, pid, d.get("utstyrsprofil_id"), str(d.get("onske") or ""))
                oppg = "lag program"
            data = ai.les_json(await self.ai.spor(oppg, instr))
            v = sb._valider_program(data)  # noqa: SLF001 – samme validering som ved lagring
            endringer = [str(x)[:300] for x in (data.get("endringer") or []) if str(x).strip()][:12]
            sb.logg_ai(pid, oppg, str(d.get("onske") or ""), v["begrunnelse"])
            return {"forslag": {**sb.berik_forhandsvisning(v), "endringer": endringer}}

        @r("POST", "/api/okter/{oid}/ai/tips")
        async def ai_tips(req):
            oid = req.int("oid")
            o = sb.okt(oid)
            if o.get("ai_tips") and not req.data.get("ny"):
                return {"tips": o["ai_tips"]}
            data = ai.les_json(await self.ai.spor("tips til økt", ai.oppgave_tips(sb, oid)))
            tips = [str(t)[:300] for t in (data.get("tips") or []) if str(t).strip()][:6]
            if not tips:
                raise Feil("AI-en ga ingen tips. Prøv igjen.")
            sb.lagre_ai(oid, "ai_tips", tips)
            return {"tips": tips}

        @r("POST", "/api/okter/{oid}/ai/oppsummering")
        async def ai_oppsummering(req):
            oid = req.int("oid")
            o = sb.okt(oid)
            if o.get("ai_oppsummering") and not req.data.get("ny"):
                return {"oppsummering": o["ai_oppsummering"]}
            rek = sb.okt_oppsummering(oid)["rekorder"]
            data = ai.les_json(await self.ai.spor("oppsummer økt", ai.oppgave_oppsummering(sb, oid, rek)))
            res = {"oppsummering": str(data.get("oppsummering") or "")[:1500],
                   "neste_gang": [str(x)[:300] for x in (data.get("neste_gang") or []) if str(x).strip()][:5]}
            if not res["oppsummering"]:
                raise Feil("AI-en ga ingen oppsummering. Prøv igjen.")
            sb.lagre_ai(oid, "ai_oppsummering", res)
            return {"oppsummering": res}

        @r("POST", "/api/profiler/{pid}/ai/sporsmal")
        async def ai_sporsmal(req):
            pid = req.int("pid")
            d = req.data
            sp = str(d.get("sporsmal") or "").strip()
            if not sp:
                raise Feil("Skriv et spørsmål")
            svar = ai.rens_tekst(await self.ai.spor("spørsmål", ai.oppgave_sporsmal(
                sb, pid, sp[:1000], int(d["okt_id"]) if d.get("okt_id") else None, d.get("ovelse"))))
            return {"svar": sb.logg_ai(pid, "sporsmal", sp, svar, d.get("okt_id"))}

        @r("GET", "/api/profiler/{pid}/ai/logg")
        async def ai_logg(req):
            return {"logg": sb.ai_logg(req.int("pid"))}
