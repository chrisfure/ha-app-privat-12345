"""Ukesoppsummering: hva som gikk bra denne uka og hva som bør være fokus neste – lages søndag kveld.

Med AI-treneren skrives den av AI ut fra ukas tall; uten AI lages en kort oppsummering av tallene.
"""
from __future__ import annotations

import logging
from datetime import timedelta
from typing import TYPE_CHECKING

from db import fra_iso, naa, til_iso

if TYPE_CHECKING:
    from logikk import Styrkeboka

log = logging.getLogger("styrkeboka.oppsummering")


def ukenokkel(sb: "Styrkeboka", d=None) -> str:
    iso = sb.lokal(d or naa()).isocalendar()
    return f"{iso[0]}-U{iso[1]:02d}"


def fakta(sb: "Styrkeboka", pid: int) -> dict:
    import kropp
    import loping
    import spill
    s = spill.status(sb, pid, lagre=False)
    u = kropp.uker(sb, pid, 2)
    lop = (loping.status(sb, pid).get("aktiv") or {})
    return {
        "uke": sb.lokal(naa()).isocalendar()[1],
        "ringer": [{"navn": r["navn"], "verdi": r["verdi"], "maal": round(r["maal"], 1), "lukket": r["andel"] >= 1} for r in s["ringer"]],
        "okter": s["ringer"][0]["verdi"], "plan": s["ringer"][0]["maal"], "rekke": s["rekke"],
        "rekorder": s["rekorder_uka"], "minutter": u[-1]["minutter"], "minutter_forrige": u[-2]["minutter"],
        "km_loping": u[-1]["km_loping"], "xp": s["xp_uka"], "niva": s["niva"]["nr"],
        "lop_gjort": lop.get("gjort"), "lop_plan": len(lop.get("plan") or []) or None,
    }


def fakta_tekst(f: dict) -> str:
    linjer = [f"Styrkeøkter: {f['okter']} av {f['plan']} (ukemål nådd {f['rekke']} uker på rad)",
              "Ringer: " + ", ".join(f"{r['navn']} {r['verdi']:g}/{r['maal']:g}{' (lukket)' if r['lukket'] else ''}" for r in f["ringer"]),
              f"Aktivitetsminutter: {f['minutter']} (forrige uke {f['minutter_forrige']})"]
    if f["rekorder"]:
        linjer.append("Nye rekorder: " + ", ".join(f["rekorder"]))
    if f["lop_plan"]:
        linjer.append(f"Løpeturer: {f['lop_gjort']} av {f['lop_plan']} ({f['km_loping']:g} km)")
    return "\n".join(f"- {x}" for x in linjer)


def lokal(sb: "Styrkeboka", pid: int, f: dict) -> dict:
    bra, forbedre = [], []
    for r in f["ringer"]:
        (bra if r["lukket"] else forbedre).append(
            f"{r['navn']}-ringen er lukket ({r['verdi']:g} av {r['maal']:g})" if r["lukket"]
            else f"{r['navn']}: {r['verdi']:g} av {r['maal']:g} – litt igjen til målet")
    if f["rekorder"]:
        bra.append(f"{len(f['rekorder'])} nye rekorder: {', '.join(f['rekorder'][:3])}")
    if f["rekke"] >= 2:
        bra.append(f"Ukemålet nådd {f['rekke']} uker på rad")
    return {"tittel": f"Uke {f['uke']}: {f['okter']} av {f['plan']} økter", "bra": bra[:4], "forbedre": forbedre[:3],
            "neste_uke": "Se ukeplanen under for når øktene passer best neste uke."}


async def lag(sb: "Styrkeboka", pid: int, spor=None) -> dict:
    """Lager og lagrer ukas oppsummering. «spor» er AI-kallet (oppgave, instruksjoner) – uten det brukes tallene alene."""
    import ai
    f = fakta(sb, pid)
    data, kilde = None, "lokal"
    if spor and sb.inn.get("ai_paa"):
        try:
            svar = ai.les_json(await spor("ukesoppsummering", ai.oppgave_ukesoppsummering(sb, pid, fakta_tekst(f))))
            data = {"tittel": str(svar.get("tittel") or "")[:80] or f"Uke {f['uke']}",
                    "bra": [str(x)[:200] for x in (svar.get("bra") or [])][:4],
                    "forbedre": [str(x)[:200] for x in (svar.get("forbedre") or [])][:3],
                    "neste_uke": str(svar.get("neste_uke") or "")[:500]}
            kilde = "ai"
        except Exception as e:  # noqa: BLE001
            log.warning("AI-oppsummering feilet, bruker tallene: %s", e)
    ut = {**(data or lokal(sb, pid, f)), "kilde": kilde, "uke": ukenokkel(sb), "ukenr": f["uke"], "laget": til_iso(naa()), "fakta": f}
    sb.db.lagre_innstilling(f"ukesoppsummering-{pid}", ut)
    return ut


def aktuell(sb: "Styrkeboka", pid: int) -> dict | None:
    """Oppsummeringen vises fra den lages (søndag kveld) til og med onsdag."""
    o = sb.db.innstillinger().get(f"ukesoppsummering-{pid}")
    if not o or naa() - fra_iso(o["laget"]) > timedelta(days=3, hours=6):
        return None
    return o


def skal_lages(sb: "Styrkeboka", pid: int) -> bool:
    """Søndag fra kl. 18, én gang per uke – bare for den som har trent eller har et program."""
    n = sb.lokal(naa())
    if n.weekday() != 6 or n.hour < 18 or not sb.inn.get("ukesoppsummering", True):
        return False
    o = sb.db.innstillinger().get(f"ukesoppsummering-{pid}")
    if o and o.get("uke") == ukenokkel(sb):
        return False
    mandag = (n - timedelta(days=6)).replace(hour=0, minute=0, second=0, microsecond=0)
    return bool(sb.aktivt_program(pid) or sb.db.verdi(
        "SELECT 1 FROM okter WHERE profil_id = ? AND status = 'fullfort' AND startet >= ? LIMIT 1", (pid, til_iso(mandag))))
