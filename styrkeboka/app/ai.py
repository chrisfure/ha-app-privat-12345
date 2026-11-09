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
from ovelser import MONSTER, UTSTYR, tilgjengelig, sekunder as er_sekunder
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
    import loping
    import dagsform
    import ukeplan
    linjer.append(kropp.ai_tekst(sb, pid))
    if (lt := loping.ai_tekst(sb, pid)):
        linjer.append(lt)
    if (dt := dagsform.ai_tekst(sb, pid)):
        linjer.append(dt)
    if (kt := ukeplan.kalender_tekst(sb, pid)):
        linjer.append(kt)
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


def treningsanalyse(sb: Styrkeboka, pid: int) -> str:
    """Utdrag av hele historikken: oppmøte, progresjon per øvelse, volum per muskelgruppe og formtrend.
    Gir AI-en grunnlag for gode valg (stillstand, ubalanse, for lite/mye volum, dårlig restitusjon) uten rådata."""
    p = sb.profil(pid)
    deler = []
    st = sb.statistikk(pid)
    plan = st["plan_per_uke"]
    uker = [u["okter"] for u in st["uker"]]
    if st["totalt"]:
        aktive = [u for u in uker if u]
        deler.append(f"Oppmøte siste 12 uker (eldst→nyest): {', '.join(map(str, uker))} økter/uke; mål {plan}; "
                     f"ukemål nådd {sum(1 for u in uker if u >= plan)} av 12 uker; totalt {st['totalt']} økter"
                     + (f"; snitt i aktive uker {sum(aktive) / len(aktive):.1f}" if aktive else ""))
    prog = sb.aktivt_program(pid)
    if prog and prog.get("blokk"):
        b = prog["blokk"]
        deler.append(f"Treningsblokk: nr {b['nr']}, uke {b.get('uke')} av {b['uker']}" + (" (lettere uke nå)" if b.get("lett_naa") else ""))
    # progresjon per øvelse siste 12 uker: estimert 1RM første → beste siste 2 uker, og uker siden forrige rekord
    fra = til_iso(naa() - timedelta(weeks=12))
    rader = sb.db.alle(
        "SELECT s.ovelse, s.vekt, s.reps, o.startet FROM sett s JOIN okter o ON o.id = s.okt_id "
        "WHERE o.profil_id = ? AND o.status = 'fullfort' AND s.oppvarming = 0 AND o.startet >= ? ORDER BY o.startet", (pid, fra))
    per: dict[str, list] = {}
    for r in rader:
        sek = er_sekunder(sb.ovelse(r["ovelse"]))
        e = P.e1rm(r["vekt"], r["reps"]) if r["vekt"] and not sek else None
        verdi, enhet = (round(e * 2) / 2, "kg e1RM") if e else ((r["reps"] or 0), "sek" if sek else "reps")
        per.setdefault(r["ovelse"], []).append((r["startet"], verdi, enhet))
    linjer = []
    grense2 = til_iso(naa() - timedelta(weeks=2))
    for ov, xs in sorted(per.items(), key=lambda kv: -len(kv[1])):
        dager = sorted({x[0][:10] for x in xs})
        if len(dager) < 2:
            continue
        forste = max(v for t, v, _ in xs if t[:10] == dager[0])
        nyeste = max([v for t, v, _ in xs if t >= grense2] or [0])
        beste, siste_rek = 0, xs[0][0]
        for t, v, _ in xs:
            if v > beste * 1.001:
                beste, siste_rek = v, t
        uker_siden = (naa() - __import__("db").fra_iso(siste_rek)).days // 7
        flagg = " – STILLSTAND" if uker_siden >= 3 and len(dager) >= 4 else ""
        linjer.append(f"{sb.ovelse(ov)['navn']}: {forste:g}→{nyeste or beste:g} {xs[0][2]} ({len(dager)} økter, "
                      f"beste {beste:g}, {uker_siden} uker siden rekord{flagg})")
    if linjer:
        deler.append("PROGRESJON SISTE 12 UKER (første → siste 2 uker):\n" + "\n".join(f"- {x}" for x in linjer[:14]))
    musk = [m for m in st["muskler"] if m["uke"] or m["snitt"]]
    if musk:
        deler.append("HARDE SETT PER MUSKELGRUPPE (siste 7 dager / snitt per uke siste 4 uker; ca. 10–20 per uke er vanlig anbefaling for vekst): "
                     + "; ".join(f"{m['navn']} {m['uke']:g}/{m['snitt']:g}" for m in musk))
    opplevd = sb.db.alle("SELECT opplevd FROM okter WHERE profil_id = ? AND status = 'fullfort' AND opplevd IS NOT NULL AND startet >= ?",
                         (pid, til_iso(naa() - timedelta(weeks=4))))
    if opplevd:
        deler.append(f"Opplevd tyngde siste 4 uker: snitt {sum(r['opplevd'] for r in opplevd) / len(opplevd):.1f}/5 ({len(opplevd)} økter)")
    # formtrend: snitt siste 7 dager mot 28 dager
    trend = []
    navn = {"sovn_min": ("søvn", "min"), "sovn_score": ("søvnscore", ""), "hrv": ("HRV", "ms"), "hvilepuls": ("hvilepuls", ""),
            "stress": ("stress", ""), "body_battery": ("Body Battery", ""), "beredskap": ("treningsberedskap", "")}
    i_dag = sb.lokal(naa()).date()
    for typ, (n, enhet) in navn.items():
        r7 = sb.db.alle("SELECT verdi FROM maalinger WHERE profil_id = ? AND type = ? AND dato > ?", (pid, typ, (i_dag - timedelta(days=7)).isoformat()))
        r28 = sb.db.alle("SELECT verdi FROM maalinger WHERE profil_id = ? AND type = ? AND dato > ?", (pid, typ, (i_dag - timedelta(days=28)).isoformat()))
        if r7 and len(r28) >= 5:
            a7, a28 = sum(x["verdi"] for x in r7) / len(r7), sum(x["verdi"] for x in r28) / len(r28)
            trend.append(f"{n} {a7:.0f}{enhet} (28 d: {a28:.0f})")
    if trend:
        deler.append("FORMTREND, snitt siste 7 dager (mot 28 dager): " + ", ".join(trend))
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
        "TRENINGSANALYSE:\n" + treningsanalyse(sb, pid),
        f"BRUKERENS ØNSKER: {onske.strip()}" if onske.strip() else "",
        "UTGANGSPUNKT (appens eget forslag – forbedre det gjerne):\n" + program_tekst(mal, sb),
        "TILGJENGELIGE ØVELSER (nøkkel = navn):\n" + bibliotek_tekst(sb, utstyr),
        "Krav: dekk alle store muskelgrupper i løpet av uka, bruk treningsanalysen (stillstand, muskelgrupper med for lite volum, oppmøte og restitusjon), tilpass antall øvelser til tiden, ta hensyn til oppgitte skader "
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
        "TRENINGSANALYSE:\n" + treningsanalyse(sb, pid),
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
        "TRENINGSANALYSE:\n" + treningsanalyse(sb, pid),
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


def oppgave_ukeplan(sb: Styrkeboka, pid: int, onske: str = "") -> str:
    import ukeplan
    prog = sb.aktivt_program(pid)
    neste = sb.neste_dag(pid, prog) if prog else None
    dager = ""
    if prog:
        ider = [d["id"] for d in prog["dager"]]
        start = ider.index(neste["id"]) if neste else 0
        rekke = [prog["dager"][(start + i) % len(ider)] for i in range(len(ider))]
        dager = "\n".join(f"- dag_id {d['id']}: {d['navn']} ({', '.join(o['navn'] for o in d['ovelser'][:6])})" for d in rekke)
    lokal = ukeplan.lokal_plan(sb, pid)
    i_dag = sb.lokal(__import__("db").naa()).date()
    return "\n\n".join(x for x in [
        ROLLE,
        "OPPGAVE: Lag en treningsplan for de neste 7 dagene (fra og med i dag) som gir best mulig fremgang og passer med "
        "kalenderen, dagsformen og løpeplanen. Plasser styrkeøktene i programrekkefølgen under (neste først), helst med "
        "minst én dag mellom; unngå dager brukeren er borte/reiser eller har svært lange dager; legg ikke harde intervaller "
        "dagen før en tung beinøkt; ved lav dagsform i dag: lettere start på uka. Løpeturer fra løpeplanen kan flyttes "
        "om kalenderen krever det. Legg gjerne inn et kort notat per dag (f.eks. «lang jobbdag – kort økt» eller «hviledag»).",
        f"I DAG: {ukeplan.UKEDAG[i_dag.weekday()]} {i_dag.isoformat()}",
        "OM BRUKEREN:\n" + profilkontekst(sb, pid),
        "PROGRAMDAGER I REKKEFØLGE:\n" + dager if dager else "",
        f"MÅL: {sb.profil(pid).get('dager_per_uke')} styrkeøkter per uke",
        "APPENS EGET FORSLAG (forbedre det gjerne):\n" + "\n".join(
            f"- {d['dato']} {d['ukedag']}: " + (", ".join(o.get('navn') or o.get('tittel') for o in d['okter']) or "hvile")
            + (f" [{d['notat']}]" if d['notat'] else "") for d in lokal["dager"]),
        "SISTE ØKTER:\n" + historikkontekst(sb, pid, 4),
        "TRENINGSANALYSE:\n" + treningsanalyse(sb, pid),
        f"BRUKERENS ØNSKER: {onske.strip()}" if onske.strip() else "",
        'Svar KUN med JSON: {"oppsummering": "2-3 setninger om uka", "dager": [{"dato": "YYYY-MM-DD", '
        '"okter": [{"type": "styrke", "dag_id": 123} eller {"type": "lop", "tittel": "Rolig tur", "minutter": 30} eller '
        '{"type": "annet", "tittel": "Mobilitet 15 min"}], "notat": "kort"}]}. Ta med alle 7 dagene.',
    ] if x)


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
        _puls_tekst(sb, o),
        "Rekorder: " + "; ".join(f"{r['ovelse']} – {r['tekst']}" for r in rekorder) if rekorder else "",
        "TIDLIGERE ØKTER:\n" + historikkontekst(sb, o["profil_id"], 5),
        'Svar KUN med JSON: {"oppsummering": "2-3 setninger", "neste_gang": ["...", "..."]}',
    ] if x)


def _puls_tekst(sb: Styrkeboka, o: dict) -> str:
    k = o.get("klokke")
    if not k:
        return ""
    deler = [f"PULS FRA KLOKKA: snitt {k.get('snittpuls') or '?'}, maks {k.get('makspuls') or '?'}"]
    if k.get("kalorier"):
        deler.append(f"{k['kalorier']} kcal")
    if k.get("soner"):
        deler.append("tid i soner 1–5 (min): " + ", ".join(str(round(s / 60)) for s in k["soner"]))
    a = k.get("analyse") or {}
    if a.get("per_ovelse"):
        deler.append("per øvelse (pulstopp i sett / puls rett før neste sett): " + "; ".join(
            f"{sb.ovelse(n)['navn']} {v['topp'] or '?'}/{v['foer_neste'] or '?'}" for n, v in a["per_ovelse"].items()))
    makspuls = __import__("kropp").avledet(sb, o["profil_id"]).get("makspuls")
    if makspuls:
        deler.append(f"estimert makspuls {makspuls}")
    return ", ".join(deler) + ". Kommenter gjerne hvile og intensitet ut fra pulsen."


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
    if (ta := treningsanalyse(sb, pid)):
        deler.append("TRENINGSANALYSE:\n" + ta)
    import ukeplan
    if (ut := ukeplan.ai_tekst(sb, pid)):
        deler.append(ut)
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
