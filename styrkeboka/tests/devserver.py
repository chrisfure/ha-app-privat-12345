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

    async def ai_entiteter(self):
        return [{"entity_id": "ai_task.claude_ai_task", "navn": "Claude AI Task"}]

    async def spor(self, oppgave, instruksjoner):
        await asyncio.sleep(0.4)
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
