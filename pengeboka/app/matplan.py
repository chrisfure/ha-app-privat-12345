"""Kobling mot Matplan: kvitteringer ↔ dagligvarekjøp i banken.

Pengeboka henter kvitteringene (butikk, dato, sum) fra Matplan med en koblingskode,
finner kjøpet med samme beløp i banken, og sender tilbake hvilke kvitteringer som er
funnet. Bankdata forlater aldri Pengeboka – Matplan får bare «funnet: Felleskonto,
11. nov, 249 kr» eller «mangler» per kvittering.

Matching (ingen AI):
  1. Samme beløp (på øret, eller innenfor 1 kr ved øresavrunding)
  2. Samme kjede når begge er kjent (Kiwi mot Kiwi, Coop Extra mot Coop …)
  3. Dato innen 3 dager (Oda: 6 dager, fordi kortet ofte belastes ved levering)
  Nærmeste dato vinner, og hver kvittering kobles til høyst ett kjøp.
  Deretter en runde for det som er igjen: samme kjede, beløp innen 20 kr eller 3 %.

Dagligvarekjøp i banken uten kvittering sendes også til Matplan (butikk, dato, sum og konto),
så Matplan kan telle dem med i det familien bruker på mat.
"""
from __future__ import annotations

import json
import logging
import threading
import urllib.error
import urllib.request
from datetime import date

from db import naa_iso

log = logging.getLogger("pengeboka.matplan")

STANDARD_URL = "http://f0f11513-matplan:8099"
DAGER = 3
DAGER_ODA = 6
TOLERANSE_ORE = 100

# Kjede ut fra navn – samme kjede selv om banken skriver «COOP EXTRA STASJONEN» og kvitteringen «Coop»
_KJEDER = [("rema", "rema"), ("kiwi", "kiwi"), ("coop", "coop"), ("extra", "coop"), ("obs", "coop"), ("prix", "coop"),
           ("mega", "coop"), ("matkroken", "matkroken"), ("meny", "meny"), ("eurospar", "spar"), ("spar", "spar"),
           ("joker", "joker"), ("bunnpris", "bunnpris"), ("oda", "oda"), ("nærbutikken", "naerbutikken"),
           ("narbutikken", "naerbutikken"), ("holdbart", "holdbart")]

_lås = threading.Lock()


class Matplanfeil(Exception):
    pass


def kjede(navn: str | None) -> str | None:
    lav = (navn or "").lower()
    for ord_, k in _KJEDER:
        if ord_ in lav.replace("-", " ").split() or lav.startswith(ord_):
            return k
    return None


# ---------------------------------------------------------------- HTTP mot Matplan
class _IngenOmdirigering(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *a, **k):
        return None


_opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), _IngenOmdirigering())


def _kall(url: str, kode: str, sti: str, metode: str = "GET", data: dict | None = None):
    if not url or not kode:
        raise Matplanfeil("Matplan er ikke koblet til")
    if not url.startswith(("http://", "https://")):
        raise Matplanfeil("Adressen må begynne med http://")
    body = json.dumps(data).encode() if data is not None else None
    req = urllib.request.Request(url.rstrip("/") + sti, data=body, method=metode,
                                 headers={"Authorization": f"Bearer {kode}", "Content-Type": "application/json",
                                          "Accept": "application/json"})
    try:
        with _opener.open(req, timeout=20) as r:
            return json.loads(r.read() or b"{}")
    except urllib.error.HTTPError as e:
        if e.code == 401:
            raise Matplanfeil("Matplan godtok ikke koblingskoden. Kopier den på nytt fra Matplan.") from None
        if e.code == 404:
            raise Matplanfeil("Fant ikke koblingen i Matplan. Oppdater Matplan til nyeste versjon.") from None
        raise Matplanfeil(f"Matplan svarte med feil {e.code}") from None
    except (urllib.error.URLError, TimeoutError, OSError) as e:
        grunn = getattr(e, "reason", e)
        raise Matplanfeil(f"Får ikke kontakt med Matplan ({grunn}). Sjekk at Matplan kjører.") from None
    except ValueError:
        raise Matplanfeil("Matplan svarte med noe Pengeboka ikke forstår") from None


# ---------------------------------------------------------------- matching
def match(transaksjoner: list[dict], kvitteringer: list[dict]) -> dict[int, int]:
    """{transaksjon_id: matplan_id}. transaksjoner: id, dato, belop_ore (negativ), motpart.
    kvitteringer: matplan_id, dato, total_ore, butikk."""
    par = []
    for k in kvitteringer:
        if not k.get("dato") or not k.get("total_ore"):
            continue
        kd = date.fromisoformat(k["dato"])
        kk = kjede(k.get("butikk"))
        grense = DAGER_ODA if kk == "oda" else DAGER
        for t in transaksjoner:
            diff = abs(-t["belop_ore"] - k["total_ore"])
            if diff > TOLERANSE_ORE:
                continue
            dager = abs((date.fromisoformat(t["dato"]) - kd).days)
            if dager > grense:
                continue
            tk = kjede(t.get("motpart")) or kjede(t.get("tekst"))
            if tk and kk and tk != kk:
                continue  # Kiwi-kvittering mot Rema-kjøp
            usikker = not (tk and kk)
            if usikker and (diff or dager > 1):
                continue  # ukjent kjede: bare helt likt beløp og nesten samme dag
            par.append(((1 if diff else 0, 1 if usikker else 0, dager, t["id"]), t["id"], k["matplan_id"]))
    par.sort()
    brukt_t, brukt_k, ut = set(), set(), {}
    for _, tid, kid in par:
        if tid in brukt_t or kid in brukt_k:
            continue
        brukt_t.add(tid)
        brukt_k.add(kid)
        ut[tid] = kid
    # Runde 2 for det som er igjen: samme kjede og nesten samme beløp (Oda justerer ofte beløpet
    # etter bytter og manglende varer). Uten denne ville både kvitteringen og kjøpet telt i Matplan.
    par = []
    for k in kvitteringer:
        if k["matplan_id"] in brukt_k or not k.get("dato") or not k.get("total_ore"):
            continue
        kk = kjede(k.get("butikk"))
        if not kk:
            continue
        kd = date.fromisoformat(k["dato"])
        grense = DAGER_ODA if kk == "oda" else DAGER
        for t in transaksjoner:
            if t["id"] in brukt_t or (kjede(t.get("motpart")) or kjede(t.get("tekst"))) != kk:
                continue
            diff = abs(-t["belop_ore"] - k["total_ore"])
            dager = abs((date.fromisoformat(t["dato"]) - kd).days)
            if dager <= grense and diff <= max(2000, k["total_ore"] * 0.03):
                par.append(((diff, dager, t["id"]), t["id"], k["matplan_id"]))
    par.sort()
    for _, tid, kid in par:
        if tid in brukt_t or kid in brukt_k:
            continue
        brukt_t.add(tid)
        brukt_k.add(kid)
        ut[tid] = kid
    return ut


# ---------------------------------------------------------------- synk
def innstillinger(db) -> dict:
    return {"url": db.innstilling("matplan_url") or STANDARD_URL, "kode": db.innstilling("matplan_kode") or "",
            "status": db.innstilling("matplan_status") or {}}


def tilkoblet(db) -> bool:
    return bool(db.innstilling("matplan_kode"))


def kandidater(db) -> list[dict]:
    """Bankkjøp som kan ha kvittering: penger ut, ikke overføring, dagligvarer eller en kjent matbutikk."""
    rader = db.rader("""
        SELECT t.id, t.dato, t.belop_ore, t.motpart, t.tekst, c.navn AS kategori, k.navn AS konto
        FROM transaksjoner t JOIN kontoer k ON k.id = t.konto_id LEFT JOIN kategorier c ON c.id = t.kategori_id
        WHERE t.belop_ore < 0 AND (t.kilde IS NULL OR t.kilde != 'overforing')""")
    return [r for r in rader if r["kategori"] == "Dagligvarer" or kjede(r["motpart"])]


def dekket_til(db) -> str | None:
    """Siste dato der banken er importert for alle synlige kontoer med dagligvarekjøp."""
    rader = db.rader("""
        SELECT t.konto_id, MAX(t.dato) AS til FROM transaksjoner t JOIN kontoer k ON k.id = t.konto_id
        LEFT JOIN kategorier c ON c.id = t.kategori_id
        WHERE k.skjult = 0 AND t.konto_id IN (SELECT DISTINCT t2.konto_id FROM transaksjoner t2
              LEFT JOIN kategorier c2 ON c2.id = t2.kategori_id WHERE c2.navn = 'Dagligvarer')
        GROUP BY t.konto_id""")
    return min((r["til"] for r in rader), default=None)


def synk(db, url: str | None = None, kode: str | None = None) -> dict:
    """Henter kvitteringer, kobler og sender svar tilbake. Kaster Matplanfeil ved problemer."""
    if not _lås.acquire(blocking=False):
        return innstillinger(db)["status"]
    try:
        url = url or innstillinger(db)["url"]
        kode = kode or innstillinger(db)["kode"]
        fra = db.verdi("SELECT MIN(dato) FROM transaksjoner")
        if not fra:
            data = _kall(url, kode, "/kobling/kvitteringer?fra=2100-01-01")  # bare test av koblingen
            kv = []
        else:
            data = _kall(url, kode, f"/kobling/kvitteringer?fra={fra}")
            kv = [{"matplan_id": int(k["id"]), "butikk": str(k.get("store") or "")[:60], "dato": str(k.get("purchased_on") or "")[:10],
                   "total_ore": int(round(float(k["total"]) * 100)) if k.get("total") is not None else None,
                   "varer": int(k.get("varer") or 0)} for k in data.get("kvitteringer", []) if k.get("id") is not None]
        tx = kandidater(db)
        koblet = match(tx, kv)
        with db.transaksjon():
            db.con.execute("DELETE FROM kvitteringer")
            db.con.executemany("INSERT INTO kvitteringer(matplan_id, butikk, dato, total_ore, varer) VALUES(?,?,?,?,?)",
                               [(k["matplan_id"], k["butikk"], k["dato"], k["total_ore"], k["varer"]) for k in kv])
            db.con.execute("DELETE FROM kvittering_kobling")
            db.con.executemany("INSERT INTO kvittering_kobling(transaksjon_id, matplan_id) VALUES(?, ?)", list(koblet.items()))
        # Svar til Matplan: bare for kvitteringer i perioden banken dekker
        dekket = dekket_til(db)
        tx_map = {t["id"]: t for t in tx}
        funnet = {kid: tid for tid, kid in koblet.items()}
        svar = []
        for k in kv:
            if k["matplan_id"] in funnet:
                t = tx_map[funnet[k["matplan_id"]]]
                svar.append({"kvittering": k["matplan_id"], "status": "funnet", "dato": t["dato"],
                             "konto": t["konto"], "belop": -t["belop_ore"] / 100})
            elif dekket and fra and fra <= (k["dato"] or "") <= dekket:
                svar.append({"kvittering": k["matplan_id"], "status": "mangler"})
        uten = [{"ref": str(t["id"]), "dato": t["dato"], "butikk": t["motpart"], "belop": -t["belop_ore"] / 100,
                 "konto": t["konto"]} for t in tx if t["id"] not in koblet and t["kategori"] == "Dagligvarer"]
        _kall(url, kode, "/kobling/bank", "PUT", {"koblinger": svar, "dekket_til": dekket, "kilde": "Pengeboka",
                                                   "uten_kvittering": uten})
        status = {"synket": naa_iso(), "feil": None, "kvitteringer": len(kv), "koblet": len(koblet),
                  "kjop": len(tx), "uten_kvittering": len(tx) - len(koblet)}
        db.sett_innstilling("matplan_status", status)
        return status
    except Matplanfeil as e:
        status = {**(db.innstilling("matplan_status") or {}), "feil": str(e), "forsokt": naa_iso()}
        db.sett_innstilling("matplan_status", status)
        raise
    finally:
        _lås.release()


def hent_kvittering(db, matplan_id: int) -> dict:
    s = innstillinger(db)
    return _kall(s["url"], s["kode"], f"/kobling/kvitteringer/{int(matplan_id)}")


def synk_stille(db) -> None:
    """For bakgrunnen: logg feil i stedet for å kaste dem."""
    if not tilkoblet(db):
        return
    try:
        synk(db)
    except Matplanfeil as e:
        log.info("Matplan-synk: %s", e)
    except Exception:
        log.exception("Matplan-synk feilet")


def start_bakgrunn(db, minutter: int = 60) -> None:
    def loop():
        import time
        time.sleep(20)
        while True:
            synk_stille(db)
            time.sleep(minutter * 60)
    threading.Thread(target=loop, daemon=True, name="matplan-synk").start()
