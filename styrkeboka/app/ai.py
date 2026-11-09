"""AI-treneren: bygger oppgaver til Home Assistants AI (ai_task) og tolker svarene.

Ingen navn sendes – profilen omtales som «brukeren». Alt AI foreslår av program
valideres mot øvelsesbiblioteket før det kan lagres, og må godkjennes i appen.
"""
from __future__ import annotations

import json
import re
from datetime import timedelta

from db import naa, til_iso
from logikk import Feil, Styrkeboka
from ovelser import MONSTER, UTSTYR, tilgjengelig
import program as P

ROLLE = (
    "Du er en erfaren personlig trener med kompetanse i styrketrening og opptrening etter skade. "
    "Du bygger på etablert kunnskap (WHO, Helsedirektoratet, ACSM og forskningsoversikter) og unngår moteråd. "
    "Svar alltid på norsk bokmål, kort, konkret og vennlig. "
    "Brukeren ønsker praktiske tips og triks, ikke standardforbehold: "
    "ikke gjenta at trening ikke skal gjøre vondt, og ikke henvis til lege eller fysioterapeut med mindre brukeren spør om det. "
    "Ved plager eller ubehag: gi konkrete løsninger, som justert teknikk, kortere bevegelsesbane, lavere belastning, "
    "annet tempo eller en alternativ øvelse."
)


def les_json(tekst) -> dict:
    """Henter ut JSON-objektet fra et AI-svar (tåler ```json-blokker og tekst rundt)."""
    if isinstance(tekst, dict):
        return tekst
    t = str(tekst or "")
    m = re.search(r"```(?:json)?\s*(\{.*\})\s*```", t, re.S)
    if m:
        t = m.group(1)
    start, slutt = t.find("{"), t.rfind("}")
    if start < 0 or slutt <= start:
        raise Feil("AI-svaret inneholdt ikke et gyldig forslag. Prøv igjen.")
    try:
        return json.loads(t[start:slutt + 1])
    except ValueError as e:
        raise Feil("Klarte ikke å lese AI-svaret. Prøv igjen.") from e


def profilkontekst(sb: Styrkeboka, pid: int, upid: int | None = None) -> str:
    p = sb.profil(pid)
    upid = upid or p.get("utstyrsprofil_id")
    sted = next((u for u in sb.utstyrsprofiler() if u["id"] == upid), None)
    utstyr = ", ".join(UTSTYR[u] for u in (sted["utstyr"] if sted else []) if u in UTSTYR) or "kun kroppsvekt"
    andre = [u for u in sb.utstyrsprofiler() if u["id"] != upid]
    linjer = [
        f"Erfaring: {P.ERFARING.get(p.get('erfaring'), 'ukjent')}",
        f"Mål: {', '.join(P.MAAL.get(m, m) for m in p.get('maal') or [])}",
        f"Ønsker {p.get('dager_per_uke')} økter i uka à ca. {p.get('okt_minutter')} minutter",
        f"Trener vanligvis: {sted['navn'] if sted else 'ukjent sted'} – utstyr: {utstyr}",
    ]
    if andre:
        linjer.append("Trener av og til også: " + "; ".join(
            f"{u['navn']} ({', '.join(UTSTYR[x] for x in u['utstyr'] if x in UTSTYR) or 'kun kroppsvekt'})" for u in andre))
    if (p.get("hensyn") or "").strip():
        linjer.append(f"Hensyn/skader brukeren har oppgitt: {p['hensyn'].strip()}")
    import kropp
    linjer.append(kropp.ai_tekst(sb, pid))
    return "\n".join(linjer)


def historikkontekst(sb: Styrkeboka, pid: int, antall: int = 6) -> str:
    okter = sb.db.alle("SELECT id FROM okter WHERE profil_id = ? AND status = 'fullfort' ORDER BY startet DESC LIMIT ?", (pid, antall))
    if not okter:
        return "Ingen tidligere økter registrert."
    deler = []
    for r in okter:
        o = sb.okt(r["id"])
        dato = sb.lokal(o["startet"]).strftime("%d.%m")
        ovl = []
        for oo in o["ovelser"]:
            s = [x for x in oo["sett"] if not x["oppvarming"]]
            if s:
                ovl.append(f"{oo['info']['navn']}: " + ", ".join(_sett_tekst(x) for x in s))
        tekst = f"{dato} {o['dag_navn']} ({o['nokkeltall']['minutter']} min"
        if o.get("opplevd"):
            tekst += f", opplevd tyngde {o['opplevd']}/5"
        tekst += "): " + "; ".join(ovl)
        if o.get("notat"):
            tekst += f" Notat: {o['notat']}"
        deler.append(tekst)
    st = sb.statistikk(pid)
    deler.append(f"Økter per uke siste 4 uker: {', '.join(str(u['okter']) for u in st['uker'][-4:])}")
    return "\n".join(deler)


def _sett_tekst(s: dict) -> str:
    t = f"{s['vekt']:g}kg×{s['reps']}" if s.get("vekt") else f"{s['reps']}"
    if s.get("rir") is not None:
        t += f"@RIR{s['rir']}"
    return t


def bibliotek_tekst(sb: Styrkeboka, utstyr: set[str] | None) -> str:
    linjer = []
    for m, navn in MONSTER.items():
        ovl = [o for o in sb.ovelser() if o["monster"] == m and tilgjengelig(o, utstyr)]
        if ovl:
            linjer.append(f"[{navn}] " + "; ".join(f"{o['nokkel']} = {o['navn']}{' (skånsom)' if o.get('skansom') else ''}" for o in ovl))
    return "\n".join(linjer)


def program_tekst(data: dict, sb: Styrkeboka) -> str:
    linjer = [f"Program: {data.get('navn')}"]
    for d in data["dager"]:
        linjer.append(f"- {d['navn']}: " + "; ".join(
            f"{o['ovelse']} ({sb.ovelse(o['ovelse'])['navn']}){' [FAST]' if o.get('fast') else ''} {o['sett']}×{o['reps_min']}-{o['reps_maks']}, hvile {o['hvile_s']}s, RIR {o['rir']}"
            + (f", notat: {o['notat']}" if o.get("notat") else "") for o in d["ovelser"]))
    return "\n".join(linjer)


JSON_FORMAT = (
    'Svar KUN med JSON på formen {"navn": "...", "beskrivelse": "én setning", "begrunnelse": "2-4 setninger om hvorfor programmet passer", '
    '"endringer": ["kort punkt per endring (kun ved justering)"], "dager": [{"navn": "Økt A – ...", "ovelser": [{"ovelse": "<nøkkel>", '
    '"sett": 3, "reps_min": 8, "reps_maks": 12, "hvile_s": 90, "rir": 2, "notat": "valgfritt kort tips"}]}]}. '
    "Bruk bare nøkler fra øvelseslisten. rir = reps i reserve. For planke/sideplanke/bondegange betyr reps sekunder."
)


def oppgave_lag_program(sb: Styrkeboka, pid: int, upid: int | None, onske: str = "") -> str:
    p = sb.profil(pid)
    utstyr = sb.utstyr_for(upid or p.get("utstyrsprofil_id"))
    mal = sb.foreslaa_program(pid, upid)
    return "\n\n".join(x for x in [
        ROLLE,
        "OPPGAVE: Lag et styrketreningsprogram for brukeren som gir gode resultater og er realistisk å gjennomføre over tid.",
        "OM BRUKEREN:\n" + profilkontekst(sb, pid, upid),
        "SISTE ØKTER:\n" + historikkontekst(sb, pid),
        f"BRUKERENS ØNSKER: {onske.strip()}" if onske.strip() else "",
        "UTGANGSPUNKT (appens eget forslag – forbedre det gjerne):\n" + program_tekst(mal, sb),
        "TILGJENGELIGE ØVELSER (nøkkel = navn):\n" + bibliotek_tekst(sb, utstyr),
        "Krav: dekk alle store muskelgrupper i løpet av uka, tilpass antall øvelser til tiden, ta hensyn til oppgitte skader "
        "(velg skånsomme varianter og unngå det som kan provosere), og bruk dobbel progresjon (reps-intervall).",
        JSON_FORMAT,
    ] if x)


def oppgave_juster_program(sb: Styrkeboka, pid: int, prid: int, onske: str) -> str:
    p = sb.profil(pid)
    utstyr = sb.utstyr_for(p.get("utstyrsprofil_id"))
    data = sb.program_data(prid)
    return "\n\n".join([
        ROLLE,
        "OPPGAVE: Juster brukerens nåværende program etter ønsket under. Behold det som fungerer – gjør bare endringer som trengs. "
        "List hver endring kort i \"endringer\".",
        f"ØNSKE: {onske.strip()}",
        "OM BRUKEREN:\n" + profilkontekst(sb, pid),
        "NÅVÆRENDE PROGRAM:\n" + program_tekst(data, sb),
        "SISTE ØKTER:\n" + historikkontekst(sb, pid),
        "TILGJENGELIGE ØVELSER (nøkkel = navn):\n" + bibliotek_tekst(sb, utstyr),
        JSON_FORMAT,
    ])


def oppgave_ny_blokk(sb: Styrkeboka, pid: int, prid: int) -> str:
    p = sb.profil(pid)
    utstyr = sb.utstyr_for(p.get("utstyrsprofil_id"))
    prog = sb.program(prid)
    data = sb.program_data(prid)
    b = prog["blokk"]
    return "\n\n".join([
        ROLLE,
        f"OPPGAVE: Brukeren har fullført treningsblokk {b['nr']} ({b['uker']} uker). Lag neste blokk for variasjon og fortsatt fremgang.",
        "REGLER:\n"
        "- Øvelser merket [FAST] er hovedøvelser og SKAL beholdes med samme nøkkel i samme økt. Du kan justere sett/reps litt "
        "hvis fremgangen tilsier det (f.eks. stillstand → endre rep-intervall).\n"
        "- Bytt 1–3 av de andre øvelsene per økt til en annen øvelse med samme bevegelsesmønster, for variasjon.\n"
        "- Behold antall økter, omtrent samme økttid og ta fortsatt hensyn til oppgitte skader.\n"
        "- List hver endring kort i \"endringer\" og forklar i \"begrunnelse\" hva blokka fokuserer på.",
        "OM BRUKEREN:\n" + profilkontekst(sb, pid),
        "NÅVÆRENDE PROGRAM:\n" + program_tekst(data, sb),
        "FREMGANG I BLOKKA (første → siste økt):\n" + sb.blokk_oppsummering(prid),
        "TILGJENGELIGE ØVELSER (nøkkel = navn):\n" + bibliotek_tekst(sb, utstyr),
        JSON_FORMAT,
    ])


def oppgave_startvekter(sb: Styrkeboka, pid: int, lokalt: dict) -> str:
    p = sb.profil(pid)
    kjente = "; ".join(f"{sb.ovelse(k['ovelse'])['navn']}: {k['kg']:g} kg × {k['reps']}" for k in lokalt["kjente"]) or "ingen oppgitt"
    linjer = []
    for f in lokalt["forslag"]:
        ov = sb.ovelse(f["ovelse"])
        linjer.append(f"- {f['ovelse']} ({f['navn']}, {ov['type']}{', vekt per manual' if ov['type'] == 'manualer' else ''}): "
                      f"mål {f['reps_min']}-{f['reps_maks']} reps med {f['rir']} i reserve; appens anslag: "
                      f"{str(f['kg']) + ' kg' if f['kg'] else 'mangler'}{' (har allerede historikk)' if f['har_historikk'] else ''}")
    return "\n\n".join([
        ROLLE,
        "OPPGAVE: Foreslå startvekt (kg) for hver øvelse under, slik at brukeren treffer rep-målet med ønsket antall reps i reserve "
        "i første økt. Bruk løftene brukeren kjenner, kroppsvekt, erfaring og vanlige styrkeforhold mellom øvelser "
        "(f.eks. manualpress per manual ≈ 35–40 % av benkpress med stang). Vær heller litt forsiktig enn for tung. "
        "Rund av til vekter som finnes: stang/skiver 2,5 kg, manualer 1–2 kg, apparat 2,5–5 kg, kettlebell 4 kg.",
        "OM BRUKEREN:\n" + profilkontekst(sb, pid) + (f"\nKroppsvekt: {p['kroppsvekt']:g} kg" if p.get("kroppsvekt") else ""),
        f"LØFT BRUKEREN KJENNER: {kjente}",
        "SISTE ØKTER:\n" + historikkontekst(sb, pid, 4),
        "ØVELSER:\n" + "\n".join(linjer),
        'Svar KUN med JSON: {"vekter": {"<nøkkel>": kg, ...}, "kommentar": "1-2 setninger om hvordan du har tenkt"}',
    ])


def oppgave_tips(sb: Styrkeboka, oid: int) -> str:
    o = sb.okt(oid)
    plan = []
    for oo in o["ovelser"]:
        t = f"- {oo['info']['navn']}: {oo['sett_plan']}×{oo['reps_min']}-{oo['reps_maks']}"
        if oo.get("forslag_kg"):
            t += f", forslag {oo['forslag_kg']:g} kg"
        t += f" ({oo['forslag_tekst']})"
        plan.append(t)
    return "\n\n".join([
        ROLLE,
        "OPPGAVE: Brukeren skal starte økten under. Gi 3–5 korte, konkrete tips for akkurat denne økten "
        "(teknikk, hva de bør sikte mot ut fra forrige gang, hvile, hensyn). Maks 25 ord per tips.",
        "OM BRUKEREN:\n" + profilkontekst(sb, o["profil_id"], o.get("utstyrsprofil_id")),
        f"DAGENS ØKT ({o['dag_navn']}{', ' + o['sted'] if o.get('sted') else ''}):\n" + "\n".join(plan),
        "SISTE ØKTER:\n" + historikkontekst(sb, o["profil_id"], 4),
        'Svar KUN med JSON: {"tips": ["...", "..."]}',
    ])


def oppgave_oppsummering(sb: Styrkeboka, oid: int, rekorder: list[dict]) -> str:
    o = sb.okt(oid)
    gjort = []
    for oo in o["ovelser"]:
        s = [x for x in oo["sett"] if not x["oppvarming"]]
        mal = f"mål {oo['sett_plan']}×{oo['reps_min']}-{oo['reps_maks']}"
        gjort.append(f"- {oo['info']['navn']} ({mal}): " + (", ".join(_sett_tekst(x) for x in s) or "ikke gjort"))
    return "\n\n".join(x for x in [
        ROLLE,
        "OPPGAVE: Oppsummer økten brukeren nettopp fullførte. Vær oppmuntrende, men ærlig. "
        "Gi 1–3 konkrete råd til neste gang (f.eks. øke vekt, beholde, teknikkfokus, mer hvile).",
        "OM BRUKEREN:\n" + profilkontekst(sb, o["profil_id"], o.get("utstyrsprofil_id")),
        f"ØKTEN ({o['dag_navn']}, {o['nokkeltall']['minutter']} min"
        + (f", opplevd tyngde {o['opplevd']}/5" if o.get("opplevd") else "") + "):\n" + "\n".join(gjort),
        f"Brukerens notat: {o['notat']}" if o.get("notat") else "",
        "Rekorder: " + "; ".join(f"{r['ovelse']} – {r['tekst']}" for r in rekorder) if rekorder else "",
        "TIDLIGERE ØKTER:\n" + historikkontekst(sb, o["profil_id"], 5),
        'Svar KUN med JSON: {"oppsummering": "2-3 setninger", "neste_gang": ["...", "..."]}',
    ] if x)


def oppgave_sporsmal(sb: Styrkeboka, pid: int, sporsmal: str, oid: int | None = None, ovelse: str | None = None) -> str:
    deler = [
        ROLLE,
        "OPPGAVE: Svar på brukerens spørsmål. Hold svaret under 150 ord, gjerne med korte punkter.",
        "OM BRUKEREN:\n" + profilkontekst(sb, pid),
    ]
    prog = sb.aktivt_program(pid)
    if prog:
        deler.append("AKTIVT PROGRAM:\n" + program_tekst(sb.program_data(prog["id"]), sb))
    if oid:
        o = sb.okt(oid)
        deler.append(f"PÅGÅENDE ØKT ({o['dag_navn']}): " + "; ".join(
            f"{oo['info']['navn']} " + (", ".join(_sett_tekst(x) for x in oo["sett"] if not x["oppvarming"]) or "ikke startet")
            for oo in o["ovelser"]))
    if ovelse:
        ov = sb.ovelse(ovelse)
        ins = ov.get("instruksjon") or {}
        deler.append(f"SPØRSMÅLET GJELDER ØVELSEN: {ov['navn']} ({MONSTER.get(ov['monster'], '')}). "
                     f"Appens instruksjon – start: {ins.get('start', '')} Steg: {' '.join(ins.get('steg') or [])} "
                     f"Vanlige feil: {'; '.join(ins.get('feil') or [])}. Teknikkpunkter: {'; '.join(ov.get('tips') or [])}")
    deler.append("SISTE ØKTER:\n" + historikkontekst(sb, pid, 4))
    tidligere = sb.db.alle("SELECT sporsmal, svar FROM ai_logg WHERE profil_id = ? AND type = 'sporsmal' AND tid >= ? ORDER BY id DESC LIMIT 3",
                           (pid, til_iso(naa() - timedelta(hours=3))))
    if tidligere:
        deler.append("NYLIG SAMTALE:\n" + "\n".join(f"Bruker: {t['sporsmal']}\nTrener: {t['svar'][:400]}" for t in reversed(tidligere)))
    deler.append(f"SPØRSMÅL: {sporsmal.strip()}")
    deler.append("Svar med ren tekst (ikke JSON).")
    return "\n\n".join(deler)


def rens_tekst(svar) -> str:
    if isinstance(svar, dict):
        return str(svar.get("svar") or svar.get("text") or json.dumps(svar, ensure_ascii=False))
    return str(svar or "").strip()
