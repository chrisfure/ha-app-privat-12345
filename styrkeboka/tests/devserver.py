"""Lokal testserver uten aiohttp/Home Assistant, med en falsk AI.

Kjør: python3 styrkeboka/tests/devserver.py [port] [databasesti]
"""
from __future__ import annotations

import asyncio
import json
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qsl, urlparse

APP = Path(__file__).resolve().parent.parent / "app"
sys.path.insert(0, str(APP))

from api import API, Foresporsel  # noqa: E402
from db import Database  # noqa: E402
from logikk import Styrkeboka  # noqa: E402


class FalskAI:
    aktiv = True

    def __init__(self, sb):
        self.sb = sb

    @staticmethod
    def garmin_konto(p):
        return (p.get("koblinger") or {}).get("aktiviteter")

    async def synk_garmin_lopeokter(self, p):
        import loping
        from db import naa
        if not (p.get("garmin_eksport") or {}).get("loping"):
            n = self.sb.db.verdi("SELECT COUNT(*) FROM garmin_okter WHERE profil_id = ?", (p["id"],))
            self.sb.db.kjor("DELETE FROM garmin_okter WHERE profil_id = ?", (p["id"],))
            return {"lagt_inn": 0, "fjernet": n}
        self.sb.db.kjor("DELETE FROM garmin_okter WHERE profil_id = ?", (p["id"],))
        x = loping.planlagte_garmin_okter(self.sb, p["id"])
        for o in x:
            self.sb.db.kjor("INSERT INTO garmin_okter (profil_id, periode_id, dato, nokkel, workout_id, tid) VALUES (?,?,?,?,?,?)",
                            (p["id"], o["periode_id"], o["dato"], o["nokkel"], "1", naa().isoformat()))
        return {"lagt_inn": len(x), "fjernet": 0}

    async def send_okt_til_garmin(self, oid, tving=False):
        from db import naa
        self.sb.db.oppdater("okter", oid, {"garmin_sendt": naa().isoformat()})
        return True

    async def kilder(self, profil):
        return {"kilder": {"aktiviteter": [{"entity_id": "sensor.test_last_activities", "navn": "Test Garmin Last activities", "state": "0"}],
                           "vekt": [{"entity_id": "sensor.test_weight", "navn": "Test Garmin Weight", "state": "81.4", "enhet": "kg"}],
                           "hvilepuls": [{"entity_id": "sensor.test_rhr", "navn": "Test Resting heart rate", "state": "56"}],
                           "vo2max": [], "skritt": [{"entity_id": "sensor.test_yesterday_steps", "navn": "Test Yesterday steps", "state": "8123"}],
                           "fettprosent": []},
                "forslag": {"aktiviteter": "sensor.test_last_activities", "vekt": "sensor.test_weight", "hvilepuls": "sensor.test_rhr",
                            "skritt": "sensor.test_yesterday_steps"}}

    async def synk_profil(self, profil, historikk=False):
        import random
        from datetime import timedelta
        import kropp
        from db import naa, til_iso
        pid = profil["id"]
        n = m = 0
        rnd = random.Random(1)
        for i in range(40):
            d = naa() - timedelta(days=i * 2 + 1)
            typ = ["running", "walking", "walking", "e_bike_fitness"][i % 4]
            dist = {"running": 6000, "walking": 3500, "e_bike_fitness": 9000}[typ] + rnd.randint(-800, 800)
            dur = dist / {"running": 2.9, "walking": 1.3, "e_bike_fitness": 4.5}[typ]
            if kropp.importer_garmin(self.sb, pid, {"activityId": 1000 + i, "activityName": {"running": "Løping", "walking": "Gåtur", "e_bike_fitness": "Sykkel"}[typ],
                                     "activityType": typ, "distance": dist, "duration": dur, "averageHR": 150 if typ == "running" else 95,
                                     "moderateIntensityMinutes": 0 if typ == "running" else int(dur / 60), "vigorousIntensityMinutes": int(dur / 60) if typ == "running" else 0,
                                     "startTime": til_iso(d)}):
                n += 1
        for i in range(120):
            dag = (self.sb.lokal(naa()).date() - timedelta(days=i))
            if kropp.lagre_maaling(self.sb, pid, "vekt", round(81.5 - i * -0.02 + rnd.uniform(-0.6, 0.6) - 2.4 + i * 0.02, 1), dag.isoformat(), "ha"):
                m += 1
            if kropp.lagre_maaling(self.sb, pid, "hvilepuls", 56 + rnd.randint(-2, 3) + i // 40, dag.isoformat(), "ha"):
                m += 1
            kropp.lagre_maaling(self.sb, pid, "skritt", 6000 + rnd.randint(-3000, 5000), (dag - timedelta(days=1)).isoformat(), "ha")
        kropp.lagre_maaling(self.sb, pid, "vo2max", 50, None, "ha")
        return {"importert": n, "maalinger": m}

    async def ai_entiteter(self):
        return [{"entity_id": "ai_task.claude_ai_task", "navn": "Claude AI Task"}]

    async def spor(self, oppgave, instruksjoner):
        await asyncio.sleep(0.4)
        if "startvekter" in oppgave:
            import re as _re
            vekter = {m.group(1): float(m.group(2)) * 1.05 for m in _re.finditer(r"- (\S+) \(.*?appens anslag: ([\d.]+) kg", instruksjoner)}
            return json.dumps({"vekter": vekter, "kommentar": "Jeg tok utgangspunkt i benkpressen din og la meg litt forsiktig på manualøvelsene."}, ensure_ascii=False)
        if "blokk" in oppgave:
            p = self.sb.aktivt_program(self.sb.profiler()[0]["id"])
            data = self.sb.foreslaa_ny_blokk(p["id"])
            data["endringer"] = ["Byttet bicepscurl til hammercurl for variasjon", "Knebøy: 6–10 reps denne blokka"]
            data["begrunnelse"] = "Hovedløftene står fast; hjelpeøvelsene varieres."
            return json.dumps(data, ensure_ascii=False)
        if "program" in oppgave:
            p = self.sb.profiler()[0]
            data = self.sb.foreslaa_program(p["id"])
            data["navn"] = "AI: " + data["navn"]
            data["begrunnelse"] = "Programmet bygger på helkroppsøkter med skånsomme øvelser og dobbel progresjon."
            data["endringer"] = ["Byttet første øvelse", "Kortere hvile på småøvelser"] if "juster" in oppgave else []
            return "```json\n" + json.dumps(data, ensure_ascii=False) + "\n```"
        if "tips" in oppgave:
            return json.dumps({"tips": ["Varm opp med lette sett før knebøy.", "Sikt mot 11 reps i dag – du klarte 10 sist.",
                                        "Hold 2 reps i reserve på det siste settet."]}, ensure_ascii=False)
        if "oppsummer" in oppgave:
            return {"oppsummering": "Solid økt! Du holdt deg innenfor rep-målene og økte volumet.",
                    "neste_gang": ["Øk knebøy med 2,5 kg", "Behold vekten på skulderpress"]}
        return "Godt spørsmål! Hold albuene litt inn og kontroller vekten på vei ned. Stopp hvis det gjør vondt."


def lag_server(port: int, dbsti: str):
    sb = Styrkeboka(Database(dbsti))
    api = API(sb, FalskAI(sb))
    statisk = APP / "static"

    class H(BaseHTTPRequestHandler):
        def log_message(self, *a):
            pass

        def _send(self, status, body: bytes, ctype):
            self.send_response(status)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def _api(self):
            u = urlparse(self.path)
            if u.path in ("/", "/index.html"):
                return self._send(200, (statisk / "index.html").read_bytes(), "text/html; charset=utf-8")
            if u.path.startswith("/static/"):
                f = statisk / u.path[len("/static/"):]
                ctype = {"css": "text/css", "js": "application/javascript", "json": "application/json"}.get(f.suffix[1:], "application/octet-stream")
                return self._send(200, f.read_bytes(), ctype) if f.is_file() else self._send(404, b"", "text/plain")
            n = int(self.headers.get("Content-Length") or 0)
            body = json.loads(self.rfile.read(n) or b"null") if n else None
            svar = asyncio.run(api.handter(Foresporsel(self.command, u.path, dict(parse_qsl(u.query)), body,
                                                       bruker="Testbruker", brukernavn="test")))
            if svar.tekst is not None:
                return self._send(svar.status, svar.tekst.encode(), svar.innholdstype)
            return self._send(svar.status, json.dumps(svar.data, ensure_ascii=False).encode(), "application/json")

        do_GET = do_POST = do_PUT = do_PATCH = do_DELETE = _api

    return ThreadingHTTPServer(("127.0.0.1", port), H)


if __name__ == "__main__":
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8765
    lag_server(port, sys.argv[2] if len(sys.argv) > 2 else ":memory:").serve_forever()
