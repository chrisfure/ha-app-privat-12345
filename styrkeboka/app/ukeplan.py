"""Ukeplan: hvilke dager du bør trene de neste 7 dagene – rundt kalenderen (jobb, reiser) og dagsformen.

Lokal plan: styrkeøktene spres med hviledag mellom der det går, dager du er borte eller svært opptatt
unngås, og løpeturene fra løpeplanen tas med. AI-treneren kan lage en mer gjennomtenkt plan med samme data.
"""
from __future__ import annotations

import re
from datetime import date, datetime, timedelta
from typing import TYPE_CHECKING

from db import fra_iso, naa, til_iso

if TYPE_CHECKING:
    from logikk import Styrkeboka

UKEDAG = ["mandag", "tirsdag", "onsdag", "torsdag", "fredag", "lørdag", "søndag"]
# ord som tyder på at du er borte hjemmefra (jobbvakter regnes ikke som borte – de teller som opptatte timer)
BORTE_ORD = re.compile(r"reise|\bfly\b|flight|tur til|kurs|seminar|konferanse|ferie|hytte|tjenestereise|\b[A-Z]{3} to [A-Z]{3}\b|\btrip\b",
                       re.IGNORECASE)


def hendelser(sb: "Styrkeboka", pid: int) -> list[dict]:
    return (sb.db.innstillinger().get(f"kalender-{pid}") or {}).get("hendelser") or []


def _tid(s: str | None, sb: "Styrkeboka") -> datetime | None:
    if not s:
        return None
    if len(s) == 10:
        return datetime.combine(date.fromisoformat(s), datetime.min.time(), tzinfo=sb.tz)
    return sb.lokal(fra_iso(s))


def dag_info(sb: "Styrkeboka", alle: list[dict], dag: date) -> dict:
    start = datetime.combine(dag, datetime.min.time(), tzinfo=sb.tz)
    slutt = start + timedelta(days=1)
    titler, timer, borte, heldag = [], 0.0, False, []
    for h in alle:
        hs, he = _tid(h.get("start"), sb), _tid(h.get("slutt"), sb)
        if not hs:
            continue
        he = he or hs + timedelta(hours=1)
        if he <= start or hs >= slutt:
            continue
        if h.get("heldag"):
            heldag.append(h["tittel"])
            if BORTE_ORD.search(h["tittel"]) or "tripit" in h.get("kalender", "") or h.get("sted"):
                borte = True
            titler.append(f"hele dagen: {h['tittel']}" + (f" ({h['sted']})" if h.get("sted") else ""))
        else:
            fra, til = max(hs, start), min(he, slutt)
            timer += (til - fra).total_seconds() / 3600
            if BORTE_ORD.search(h["tittel"]) and (til - fra).total_seconds() > 3 * 3600:
                borte = True
            titler.append(f"{fra:%H:%M}–{til:%H:%M} {h['tittel']}" + (f" ({h['sted']})" if h.get("sted") else ""))
    return {"titler": titler, "opptatt_t": round(timer, 1), "borte": borte, "heldag": heldag}


def kalender_tekst(sb: "Styrkeboka", pid: int, dager: int = 7) -> str:
    alle = hendelser(sb, pid)
    if not alle:
        return ""
    i_dag = sb.lokal(naa()).date()
    linjer = []
    for i in range(dager):
        d = i_dag + timedelta(days=i)
        info = dag_info(sb, alle, d)
        if info["titler"]:
            linjer.append(f"- {UKEDAG[d.weekday()]} {d:%d.%m}{' (BORTE/REISE)' if info['borte'] else ''}: " + "; ".join(info["titler"][:6]))
    return "KALENDER NESTE 7 DAGER:\n" + ("\n".join(linjer) if linjer else "ingen avtaler")


def lokal_plan(sb: "Styrkeboka", pid: int, dager: int = 7) -> dict:
    import dagsform
    import loping
    p = sb.profil(pid)
    prog = sb.aktivt_program(pid)
    i_dag = sb.lokal(naa()).date()
    alle = hendelser(sb, pid)
    info = {i_dag + timedelta(days=i): dag_info(sb, alle, i_dag + timedelta(days=i)) for i in range(dager)}
    trent_i_dag = any(sb.lokal(o["startet"]).date() == i_dag for o in sb.db.alle(
        "SELECT startet FROM okter WHERE profil_id = ? AND status = 'fullfort' AND startet >= ?", (pid, til_iso(naa() - timedelta(days=1)))))
    form = dagsform.status(sb, pid)

    # løpeturer fra løpeplanen (faste dager)
    lop: dict[date, list[dict]] = {}
    for x in loping.planlagte_garmin_okter(sb, pid, uker_frem=1):
        d = date.fromisoformat(x["dato"])
        if d in info:
            lop.setdefault(d, []).append({"type": "lop", "tittel": x["okt"]["tittel"], "minutter": x["okt"]["minutter"],
                                          "hard": x["okt"]["type"] == "intervall"})
    # kandidatdager for styrke
    n = int(p.get("dager_per_uke") or 3) if prog else 0
    kandidater = []
    for d, inf in info.items():
        if inf["borte"] or inf["opptatt_t"] >= 10 or (d == i_dag and trent_i_dag):
            continue
        straff = inf["opptatt_t"] / 4 + (1.5 if any(x.get("hard") for x in lop.get(d, [])) else 0.5 if d in lop else 0)
        if d == i_dag and form and form["niva"] == "lav":
            straff += 3
        kandidater.append((d, straff))
    valgt: list[date] = []
    for _ in range(min(n, len(kandidater))):
        def poeng(k):
            d, straff = k
            avstand = min([abs((d - v).days) for v in valgt] or [3])
            return (min(avstand, 3) * 2 - straff - (d - i_dag).days * 0.05)
        beste = max((k for k in kandidater if k[0] not in valgt), key=poeng)
        if valgt and min(abs((beste[0] - v).days) for v in valgt) == 0:
            break
        valgt.append(beste[0])
    valgt.sort()
    # programdager i rekkefølge fra neste
    rekke = []
    if prog:
        neste = sb.neste_dag(pid, prog)
        ider = [d["id"] for d in prog["dager"]]
        start = ider.index(neste["id"]) if neste else 0
        rekke = [prog["dager"][(start + i) % len(ider)] for i in range(len(valgt))]
    plan_dager = []
    for d, inf in info.items():
        okter = list(lop.get(d, []))
        notat = ""
        if d in valgt:
            pd = rekke[valgt.index(d)]
            okter.insert(0, {"type": "styrke", "dag_id": pd["id"], "navn": pd["navn"]})
        if inf["borte"]:
            notat = "Borte/reise – ingen styrkeøkt planlagt."
            if d in lop:
                notat += " Løpeturen kan tas der du er, eller flyttes."
        elif inf["opptatt_t"] >= 10:
            notat = "Lang arbeidsdag – hviledag."
        elif d == i_dag and form and form["niva"] == "lav" and d not in valgt:
            notat = "Lav dagsform – rolig dag."
        plan_dager.append({"dato": d.isoformat(), "ukedag": UKEDAG[d.weekday()], "okter": okter, "notat": notat,
                           "kalender": inf["titler"][:5], "borte": inf["borte"], "opptatt_t": inf["opptatt_t"]})
    return {"kilde": "lokal", "laget": til_iso(naa()), "dager": plan_dager,
            "oppsummering": f"{len(valgt)} styrkeøkter og {sum(len(v) for v in lop.values())} løpeturer de neste {dager} dagene."
            + (" Dager du er borte eller svært opptatt er hoppet over." if any(i['borte'] or i['opptatt_t'] >= 10 for i in info.values()) else "")}


def valider_ai_plan(sb: "Styrkeboka", pid: int, data: dict) -> dict:
    prog = sb.aktivt_program(pid)
    dag_ider = {d["id"]: d["navn"] for d in (prog["dager"] if prog else [])}
    lokal = lokal_plan(sb, pid)
    per_dato = {d["dato"]: d for d in lokal["dager"]}
    for d in per_dato.values():
        d["okter"], d["notat"] = [], ""
    for d in data.get("dager") or []:
        dato = str(d.get("dato") or "")[:10]
        if dato not in per_dato:
            continue
        okter = []
        for o in d.get("okter") or []:
            if o.get("type") == "styrke" and int(o.get("dag_id") or 0) in dag_ider:
                okter.append({"type": "styrke", "dag_id": int(o["dag_id"]), "navn": dag_ider[int(o["dag_id"])]})
            elif o.get("type") == "lop":
                okter.append({"type": "lop", "tittel": str(o.get("tittel") or "Løpetur")[:40], "minutter": int(o.get("minutter") or 30)})
            elif o.get("type") == "annet":
                okter.append({"type": "annet", "tittel": str(o.get("tittel") or "")[:60]})
        per_dato[dato]["okter"] = okter
        per_dato[dato]["notat"] = str(d.get("notat") or "")[:200]
    return {"kilde": "ai", "laget": til_iso(naa()), "dager": list(per_dato.values()),
            "oppsummering": str(data.get("oppsummering") or "")[:600]}


def hent(sb: "Styrkeboka", pid: int) -> dict:
    """Lagret AI-plan fra i dag hvis den finnes, ellers en fersk lokal plan."""
    lagret = sb.db.innstillinger().get(f"ukeplan-{pid}")
    i_dag = sb.lokal(naa()).date().isoformat()
    if lagret and lagret.get("kilde") == "ai" and sb.lokal(lagret["laget"]).date().isoformat() == i_dag:
        return {**lagret, "dager": [d for d in lagret["dager"] if d["dato"] >= i_dag]}
    return lokal_plan(sb, pid)


def lagre(sb: "Styrkeboka", pid: int, plan: dict) -> None:
    sb.db.lagre_innstilling(f"ukeplan-{pid}", plan)


def neste_styrkedato(sb: "Styrkeboka", pid: int, dag_id: int) -> str | None:
    i_dag = sb.lokal(naa()).date().isoformat()
    for d in hent(sb, pid)["dager"]:
        if d["dato"] >= i_dag and any(o["type"] == "styrke" and o.get("dag_id") == dag_id for o in d["okter"]):
            return d["dato"]
    return None


def ai_tekst(sb: "Styrkeboka", pid: int) -> str:
    plan = hent(sb, pid)
    linjer = []
    for d in plan["dager"]:
        if d["okter"]:
            linjer.append(f"{d['ukedag']} {d['dato'][8:10]}.{d['dato'][5:7]}: " + ", ".join(o.get("navn") or o.get("tittel") for o in d["okter"]))
    return ("UKEPLAN (" + ("AI" if plan["kilde"] == "ai" else "appens forslag") + "): " + "; ".join(linjer)) if linjer else ""
