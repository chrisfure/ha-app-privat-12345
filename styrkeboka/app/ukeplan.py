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
    vinduer: list[tuple[datetime, datetime]] = []      # opptatte tidsrom (uten titler) – til AI-en
    reise = {"drar": False, "hjem": False, "reisetid": None}
    for h in alle:
        hs, he = _tid(h.get("start"), sb), _tid(h.get("slutt"), sb)
        if not hs:
            continue
        he = he or hs + timedelta(hours=1)
        if he <= start or hs >= slutt:
            continue
        er_reise = bool(BORTE_ORD.search(h["tittel"]) or "tripit" in h.get("kalender", ""))
        if h.get("heldag"):
            heldag.append(h["tittel"])
            if er_reise or h.get("sted"):
                borte = True
                if (he - hs).days > 1:
                    reise["drar"] = reise["drar"] or hs >= start
                    reise["hjem"] = reise["hjem"] or he <= slutt
            spenn = ""
            if (he - hs).days > 1:
                spenn = f", {hs:%d.%m}–{(he - timedelta(days=1)):%d.%m}"
            titler.append(f"hele dagen: {h['tittel']}" + (f" ({h['sted']}{spenn})" if h.get("sted") else f" ({spenn[2:]})" if spenn else ""))
        else:
            fra, til = max(hs, start), min(he, slutt)
            timer += (til - fra).total_seconds() / 3600
            if er_reise:
                reise["reisetid"] = f"{fra:%H:%M}–{til:%H:%M}"
                if (til - fra).total_seconds() > 3 * 3600:
                    borte = True
            else:
                vinduer.append((fra, til))
            titler.append(f"{fra:%H:%M}–{til:%H:%M} {h['tittel']}" + (f" ({h['sted']})" if h.get("sted") else ""))
    return {"titler": titler, "opptatt_t": round(timer, 1), "borte": borte, "heldag": heldag,
            "vinduer": vinduer, "reise": reise}


def status_tekst(info: dict) -> str:
    """Dagens status uten titler, steder eller andre detaljer – det eneste AI-en får fra kalenderen."""
    deler = []
    r = info["reise"]
    if info["borte"]:
        deler.append("borte hjemmefra" + (" – reiser ut i dag" if r["drar"] else " – kommer hjem i dag" if r["hjem"] else ""))
    elif r["reisetid"]:
        deler.append("reisedag")
    else:
        deler.append("hjemme")
    if r["reisetid"]:
        deler.append(f"på reise {r['reisetid']}")
    if info["vinduer"]:
        fra = min(v[0] for v in info["vinduer"])
        til = max(v[1] for v in info["vinduer"])
        t = sum((b - a).total_seconds() for a, b in info["vinduer"]) / 3600
        deler.append(f"opptatt {fra:%H:%M}–{til:%H:%M} (ca. {t:.0f} t)")
    elif not info["borte"] and not r["reisetid"]:
        deler.append("ingen avtaler")
    return ", ".join(deler)


def kalender_tekst(sb: "Styrkeboka", pid: int, dager: int = 7) -> str:
    """Kalenderen som status per dag (hjemme/borte/opptatt) – aldri titler eller steder."""
    alle = hendelser(sb, pid)
    if not alle:
        return ""
    i_dag = sb.lokal(naa()).date()
    linjer = []
    for i in range(dager):
        d = i_dag + timedelta(days=i)
        linjer.append(f"- {UKEDAG[d.weekday()]} {d:%d.%m}: {status_tekst(dag_info(sb, alle, d))}")
    return "KALENDERSTATUS NESTE 7 DAGER (bare tilgjengelighet, ingen detaljer):\n" + "\n".join(linjer)


def _gjort_i_dag(sb: "Styrkeboka", pid: int) -> str | None:
    i_dag = sb.lokal(naa()).date()
    for o in sb.db.alle("SELECT startet, dag_navn FROM okter WHERE profil_id = ? AND status = 'fullfort' AND startet >= ? ORDER BY startet DESC",
                        (pid, til_iso(naa() - timedelta(days=1)))):
        if sb.lokal(o["startet"]).date() == i_dag:
            return o["dag_navn"] or "Styrkeøkt"
    return None


def lokal_plan(sb: "Styrkeboka", pid: int, dager: int = 7) -> dict:
    import dagsform
    import loping
    p = sb.profil(pid)
    prog = sb.aktivt_program(pid)
    i_dag = sb.lokal(naa()).date()
    alle = hendelser(sb, pid)
    info = {i_dag + timedelta(days=i): dag_info(sb, alle, i_dag + timedelta(days=i)) for i in range(dager)}
    gjort_i_dag = _gjort_i_dag(sb, pid)
    trent_i_dag = bool(gjort_i_dag)
    form = dagsform.status(sb, pid)

    # løpeturer fra løpeplanen (faste dager)
    lop: dict[date, list[dict]] = {}
    for x in loping.planlagte_garmin_okter(sb, pid, uker_frem=1):
        d = date.fromisoformat(x["dato"])
        if d in info:
            lop.setdefault(d, []).append({"type": "lop", "tittel": x["okt"]["tittel"], "minutter": x["okt"]["minutter"],
                                          "hard": x["okt"]["type"] == "intervall", "orig": x.get("orig") or x["dato"]})
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
        if d == i_dag and gjort_i_dag:
            okter.insert(0, {"type": "styrke", "gjort": True, "navn": gjort_i_dag})
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


def lop_flytt(sb: "Styrkeboka", pid: int) -> dict:
    """Løpeturer brukeren (eller AI-planen) har flyttet: {opprinnelig dato: ny dato, eller "" for å hoppe over}."""
    return sb.db.innstillinger().get(f"lop-flytt-{pid}") or {}


def _lagre_lop_flytt(sb: "Styrkeboka", pid: int, flytt: dict) -> None:
    grense = (sb.lokal(naa()).date() - timedelta(days=14)).isoformat()
    sb.db.lagre_innstilling(f"lop-flytt-{pid}", {k: v for k, v in flytt.items() if k >= grense})


def valider_ai_plan(sb: "Styrkeboka", pid: int, data: dict) -> dict:
    """Gjør AI-svaret om til en lagret plan. Løpeturene AI-en har lagt på andre dager, flyttes i løpeplanen
    (så klokka følger etter); styrkedagene lagres, og hvilken økt det blir følger programmets rekkefølge."""
    flytt = lop_flytt(sb, pid)
    lokal = lokal_plan(sb, pid)
    planlagt = sorted({o["orig"] for d in lokal["dager"] for o in d["okter"] if o["type"] == "lop"})
    datoer = {d["dato"] for d in lokal["dager"]}
    dager, ai_lop = [], []
    for d in data.get("dager") or []:
        dato = str(d.get("dato") or "")[:10]
        if dato not in datoer:
            continue
        okter = []
        for o in d.get("okter") or []:
            if o.get("type") == "styrke" and not any(x["type"] == "styrke" for x in okter):
                okter.append({"type": "styrke"})
            elif o.get("type") == "lop":
                ai_lop.append((dato, o, okter))
            elif o.get("type") == "annet" and str(o.get("tittel") or "").strip():
                okter.append({"type": "annet", "tittel": str(o["tittel"])[:60]})
        dager.append({"dato": dato, "okter": okter, "notat": str(d.get("notat") or "")[:200]})
    ai_lop.sort(key=lambda x: x[0])
    for i, (dato, o, okter) in enumerate(ai_lop):
        if i < len(planlagt):
            if dato == planlagt[i]:
                flytt.pop(planlagt[i], None)
            else:
                flytt[planlagt[i]] = dato
        else:  # løpetur som ikke finnes i løpeplanen – vises som forslag
            okter.append({"type": "annet", "tittel": f"🏃 {str(o.get('tittel') or 'Løpetur')[:40]}"})
    _lagre_lop_flytt(sb, pid, flytt)
    return {"kilde": "ai", "laget": til_iso(naa()), "dager": dager, "oppsummering": str(data.get("oppsummering") or "")[:600]}


def hent(sb: "Styrkeboka", pid: int) -> dict:
    """Ukeplanen som gjelder: din egen eller AI-ens lagrede plan hvis den finnes, ellers appens forslag.
    Lagrede planer sier hvilke dager det er styrke; hvilken økt det blir følger programmet. Dager lenger
    fram enn den lagrede planen fylles på med appens forslag."""
    lokal = lokal_plan(sb, pid)
    lagret = sb.db.innstillinger().get(f"ukeplan-{pid}")
    i_dag = sb.lokal(naa()).date().isoformat()
    per = {d["dato"]: d for d in (lagret or {}).get("dager") or [] if d["dato"] >= i_dag}
    if not lagret or lagret.get("kilde") not in ("ai", "egen") or not per:
        return lokal
    p = sb.profil(pid)
    prog = sb.aktivt_program(pid)
    n = int(p.get("dager_per_uke") or 3)
    antall, forrige = 0, False
    for d in lokal["dager"]:
        lop = [o for o in d["okter"] if o["type"] == "lop"]
        gjort = [o for o in d["okter"] if o.get("gjort")]
        if d["dato"] in per:
            l = per[d["dato"]]
            styrke = any(o["type"] == "styrke" for o in l["okter"]) and not gjort
            annet = [o for o in l["okter"] if o["type"] == "annet"]
            d["notat"] = l.get("notat") or ""
            if styrke and d["borte"]:
                d["notat"] = "Du ser ut til å være borte denne dagen – flytt økta om det ikke passer."
        else:
            styrke = any(o["type"] == "styrke" and not o.get("gjort") for o in d["okter"]) and antall < n and not forrige
            annet = []
        antall += 1 if styrke or gjort else 0
        forrige = bool(styrke or gjort)
        d["okter"] = gjort + ([{"type": "styrke"}] if styrke else []) + lop + annet
    # hvilken økt: programmets rekkefølge fra neste
    rekke = []
    if prog and prog["dager"]:
        neste = sb.neste_dag(pid, prog)
        ider = [x["id"] for x in prog["dager"]]
        start = ider.index(neste["id"]) if neste else 0
        rekke = [prog["dager"][(start + i) % len(ider)] for i in range(7)]
    i = 0
    for d in lokal["dager"]:
        for o in d["okter"]:
            if o["type"] == "styrke" and not o.get("gjort"):
                pd = rekke[i] if i < len(rekke) else None
                o["dag_id"], o["navn"] = (pd["id"], pd["navn"]) if pd else (None, "Styrkeøkt")
                i += 1
    return {"kilde": lagret["kilde"], "laget": lagret["laget"], "dager": lokal["dager"],
            "oppsummering": lagret.get("oppsummering") or ("Din egen plan – appen følger den." if lagret["kilde"] == "egen" else "")}


def lagre(sb: "Styrkeboka", pid: int, plan: dict) -> None:
    sb.db.lagre_innstilling(f"ukeplan-{pid}", plan)


def nullstill(sb: "Styrkeboka", pid: int) -> None:
    sb.db.kjor("DELETE FROM innstillinger WHERE nokkel IN (?, ?)", (f"ukeplan-{pid}", f"lop-flytt-{pid}"))


def endre(sb: "Styrkeboka", pid: int, d: dict) -> dict:
    """Flytt, fjern eller legg til en økt i ukeplanen. Resultatet lagres som din egen plan."""
    from logikk import Feil
    plan = hent(sb, pid)
    per = {x["dato"]: x for x in plan["dager"]}
    handling, typ = d.get("handling"), d.get("type") or "styrke"
    fra, til = str(d.get("fra") or "")[:10], str(d.get("til") or "")[:10]
    if handling in ("flytt", "fjern") and fra not in per:
        raise Feil("Fant ikke dagen i planen")
    if handling in ("flytt", "legg_til") and til not in per:
        raise Feil("Velg en av de neste 7 dagene")
    if typ == "lop":
        tur = next((o for o in per[fra]["okter"] if o["type"] == "lop"), None)
        if not tur:
            raise Feil("Fant ingen løpetur denne dagen")
        flytt = lop_flytt(sb, pid)
        ny = "" if handling == "fjern" else til
        if ny == tur["orig"]:
            flytt.pop(tur["orig"], None)
        else:
            flytt[tur["orig"]] = ny
        _lagre_lop_flytt(sb, pid, flytt)
    elif typ == "styrke":
        def har(x):
            return any(o["type"] == "styrke" for o in x["okter"])
        if handling in ("flytt", "fjern"):
            if not any(o["type"] == "styrke" and not o.get("gjort") for o in per[fra]["okter"]):
                raise Feil("Ingen styrkeøkt å flytte denne dagen")
            per[fra]["okter"] = [o for o in per[fra]["okter"] if o["type"] != "styrke" or o.get("gjort")]
        if handling in ("flytt", "legg_til"):
            if har(per[til]):
                raise Feil("Det er allerede en styrkeøkt den dagen")
            per[til]["okter"].insert(0, {"type": "styrke"})
            per[til]["notat"] = ""
    elif typ == "annet" and handling == "fjern":
        per[fra]["okter"] = [o for o in per[fra]["okter"] if o["type"] != "annet"]
    else:
        raise Feil("Ukjent endring")
    fra_ai = plan["kilde"] == "ai"
    lagre(sb, pid, {"kilde": "egen", "laget": til_iso(naa()), "oppsummering": "",
                    "dager": [{"dato": x["dato"], "notat": x["notat"] if fra_ai else "",
                               "okter": [{"type": "styrke"} for o in x["okter"] if o["type"] == "styrke" and not o.get("gjort")]
                               + [{"type": "annet", "tittel": o["tittel"]} for o in x["okter"] if o["type"] == "annet"]}
                              for x in plan["dager"]]})
    sb._varsle("ukeplan", {"profil_id": pid})  # noqa: SLF001
    return hent(sb, pid)


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
