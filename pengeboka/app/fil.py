"""Leser kontoutskrifter fra nettbanken: CSV/TXT (alle vanlige skilletegn og tegnsett) og Excel (.xlsx).

Formatet varierer mellom banker og over tid, så vi gjetter kolonnene ut fra overskriftene
og lar brukeren rette gjetningen i forhåndsvisningen før noe lagres.
"""
from __future__ import annotations

import csv
import io
import re
import zipfile
from datetime import date, timedelta
from xml.etree import ElementTree as ET

MAKS_BYTES = 20 * 1024 * 1024
FELT = ("dato", "tekst", "belop", "ut", "inn")

# Ord i kolonneoverskrifter → felt. Mer presise ord først.
_HINT = {
    "dato": ["bokført dato", "bokfort dato", "bokføringsdato", "transaksjonsdato", "kjøpsdato", "dato", "bokført",
             "date", "utført", "posted"],
    "tekst": ["forklaring", "beskrivelse", "transaksjonstekst", "tekst", "description", "mottaker", "navn",
              "melding", "spesifikasjon", "text"],
    "belop": ["beløp i nok", "beløp", "belop", "amount", "sum", "nok"],
    "ut": ["ut fra konto", "uttak", "utgående", "ut", "debet", "belastet", "debit"],
    "inn": ["inn på konto", "innskudd", "inngående", "inn", "kredit", "godskrevet", "credit"],
}
_IKKE_DATO = ("rentedato", "valuteringsdato", "valørdato", "rente dato", "forfallsdato")


class Filfeil(Exception):
    pass


# ---------------------------------------------------------------- tall og datoer
def tolk_belop(v) -> int | None:
    """Tekst eller tall → øre. Tåler «-1 234,56», «1.234,56», «1,234.56», «(249,00)», «kr 50»."""
    if v is None:
        return None
    if isinstance(v, (int, float)):
        return int(round(float(v) * 100))
    s = str(v).strip().replace("\xa0", " ").replace("−", "-")
    if not s:
        return None
    neg = s.startswith("(") and s.endswith(")")
    s = re.sub(r"(?i)\b(kr|nok)\b|[()\s]", "", s)
    if s.endswith("-"):
        neg, s = True, s[:-1]
    if s.startswith("-"):
        neg, s = not neg, s[1:]
    elif s.startswith("+"):
        s = s[1:]
    if not re.fullmatch(r"[\d.,']+", s or "x"):
        return None
    s = s.replace("'", "")
    if "," in s and "." in s:
        if s.rfind(",") > s.rfind("."):
            s = s.replace(".", "").replace(",", ".")
        else:
            s = s.replace(",", "")
    elif "," in s:
        # Norsk desimalkomma. Flere kommaer = tusenskille («1,234,567»).
        s = s.replace(",", "") if s.count(",") > 1 else s.replace(",", ".")
    elif s.count(".") > 1:
        s = s.replace(".", "")
    try:
        ore = int(round(float(s) * 100))
    except ValueError:
        return None
    return -ore if neg else ore


def tolk_dato(v) -> date | None:
    if v is None or v == "":
        return None
    if isinstance(v, (int, float)) or re.fullmatch(r"\d{5}(?:\.\d+)?", str(v).strip()):
        n = float(v)
        if 20000 < n < 80000:  # Excel-serienummer
            return date(1899, 12, 30) + timedelta(days=int(n))
        return None
    s = str(v).strip()[:10]
    m = re.fullmatch(r"(\d{4})-(\d{1,2})-(\d{1,2})", s)
    if m:
        y, mo, d = map(int, m.groups())
    else:
        m = re.match(r"(\d{1,2})[./-](\d{1,2})[./-](\d{2,4})$", s)
        if not m:
            return None
        d, mo, y = map(int, m.groups())
        if y < 100:
            y += 2000
    try:
        return date(y, mo, d)
    except ValueError:
        return None


# ---------------------------------------------------------------- lesing
def _dekod(b: bytes) -> str:
    if b.startswith(b"\xff\xfe") or b.startswith(b"\xfe\xff"):
        return b.decode("utf-16")
    if b.startswith(b"\xef\xbb\xbf"):
        return b[3:].decode("utf-8", "replace")
    try:
        return b.decode("utf-8")
    except UnicodeDecodeError:
        return b.decode("cp1252", "replace")


def _csv_rader(tekst: str) -> list[list[str]]:
    linjer = [l for l in tekst.splitlines() if l.strip()][:20]
    if not linjer:
        raise Filfeil("Filen er tom")
    beste, poeng = ";", -1
    for skille in (";", "\t", ",", "|"):
        antall = [len(next(csv.reader([l], delimiter=skille))) for l in linjer]
        vanligst = max(set(antall), key=antall.count)
        p = antall.count(vanligst) * (vanligst if vanligst > 1 else 0)
        if p > poeng:
            beste, poeng = skille, p
    return [[c.strip() for c in r] for r in csv.reader(io.StringIO(tekst), delimiter=beste) if any(c.strip() for c in r)]


def _kolonne(ref: str) -> int:
    bokst = re.match(r"[A-Z]+", ref).group(0)
    n = 0
    for ch in bokst:
        n = n * 26 + (ord(ch) - 64)
    return n - 1


def _xlsx_rader(b: bytes) -> list[list]:
    ns = {"m": "http://schemas.openxmlformats.org/spreadsheetml/2006/main",
          "r": "http://schemas.openxmlformats.org/officeDocument/2006/relationships"}
    try:
        z = zipfile.ZipFile(io.BytesIO(b))
        navn = set(z.namelist())
        delt: list[str] = []
        if "xl/sharedStrings.xml" in navn:
            for si in ET.fromstring(z.read("xl/sharedStrings.xml")).findall("m:si", ns):
                delt.append("".join(t.text or "" for t in si.iter(f"{{{ns['m']}}}t")))
        ark = "xl/worksheets/sheet1.xml"
        if ark not in navn:
            ark = sorted(n for n in navn if n.startswith("xl/worksheets/sheet"))[0]
        rot = ET.fromstring(z.read(ark))
    except (zipfile.BadZipFile, KeyError, IndexError, ET.ParseError):
        raise Filfeil("Klarte ikke å lese Excel-filen. Prøv å lagre den som CSV.") from None
    rader = []
    for rad in rot.iter(f"{{{ns['m']}}}row"):
        celler: dict[int, object] = {}
        for c in rad.findall("m:c", ns):
            t, v = c.get("t"), c.find("m:v", ns)
            if t == "s" and v is not None:
                verdi = delt[int(v.text)]
            elif t == "inlineStr":
                verdi = "".join(x.text or "" for x in c.iter(f"{{{ns['m']}}}t"))
            elif v is not None and v.text is not None:
                try:
                    verdi = float(v.text) if t not in ("str", "b") else v.text
                except ValueError:
                    verdi = v.text
            else:
                continue
            celler[_kolonne(c.get("r", "A"))] = verdi
        if celler:
            rad_liste = [""] * (max(celler) + 1)
            for i, v in celler.items():
                rad_liste[i] = v.strip() if isinstance(v, str) else v
            if any(str(x).strip() for x in rad_liste):
                rader.append(rad_liste)
    return rader


def les(data: bytes) -> list[list]:
    if not data:
        raise Filfeil("Filen er tom")
    if len(data) > MAKS_BYTES:
        raise Filfeil("Filen er for stor (maks 20 MB)")
    if data[:2] == b"PK":
        return _xlsx_rader(data)
    if data[:5] == b"%PDF-":
        raise Filfeil("PDF kan ikke leses. Last ned transaksjonene som CSV eller Excel i nettbanken.")
    return _csv_rader(_dekod(data))


# ---------------------------------------------------------------- gjenkjenning
def _norm(h) -> str:
    return re.sub(r"\s+", " ", str(h or "").strip().lower().replace("_", " "))


def _passer(h: str, ord: str) -> bool:
    return h == ord or re.search(r"(?<![a-zæøå])" + re.escape(ord) + r"(?![a-zæøå])", h) is not None


def gjett_oppsett(rader: list[list]) -> dict:
    """Finner overskriftsraden og hvilke kolonner som er dato, tekst og beløp (eller ut/inn)."""
    best = (0, 0, {})
    for i, rad in enumerate(rader[:15]):
        h = [_norm(x) for x in rad]
        kart: dict[str, int] = {}
        for felt in ("dato", "tekst", "ut", "inn", "belop"):
            for ord in _HINT[felt]:
                for j, x in enumerate(h):
                    if j in kart.values() or not x:
                        continue
                    if felt == "dato" and any(n in x for n in _IKKE_DATO):
                        continue
                    if felt in ("ut", "inn") and len(x) > 25:
                        continue
                    if _passer(x, ord):
                        kart[felt] = j
                        break
                if felt in kart:
                    break
        poeng = len(kart)
        if poeng > best[1]:
            best = (i, poeng, kart)
    rad_nr, poeng, kart = best
    if poeng < 2:
        # Ingen overskrift: gjett ut fra innholdet i første rad med en dato
        return _gjett_uten_overskrift(rader)
    if "ut" in kart and "inn" in kart:
        kart.pop("belop", None)
    elif "belop" not in kart:
        # bare én av ut/inn funnet – bruk den som beløp
        for f in ("ut", "inn"):
            if f in kart:
                kart["belop"] = kart.pop(f)
                break
        kart.pop("ut", None), kart.pop("inn", None)
    else:
        kart.pop("ut", None), kart.pop("inn", None)
    return {"overskrift": rad_nr, "kolonner": kart}


def _gjett_uten_overskrift(rader: list[list]) -> dict:
    for rad in rader[:10]:
        dato = next((j for j, x in enumerate(rad) if tolk_dato(x)), None)
        if dato is None:
            continue
        tall = [j for j, x in enumerate(rad) if j != dato and tolk_belop(x) is not None and str(x).strip()]
        tekst = max((j for j in range(len(rad)) if j != dato and j not in tall),
                    key=lambda j: len(str(rad[j])), default=None)
        if tall and tekst is not None:
            return {"overskrift": -1, "kolonner": {"dato": dato, "tekst": tekst, "belop": tall[-1]}}
    return {"overskrift": -1, "kolonner": {}}


def tolk_rader(rader: list[list], oppsett: dict) -> dict:
    """Bruker oppsettet på radene. Gir transaksjoner [{dato, tekst, belop_ore}] og hoppet-over-teller."""
    k = oppsett.get("kolonner") or {}
    if "dato" not in k or "tekst" not in k or not ("belop" in k or ("ut" in k or "inn" in k)):
        raise Filfeil("Velg hvilke kolonner som er dato, tekst og beløp")
    start = int(oppsett.get("overskrift", -1)) + 1
    ut, hoppet = [], 0
    for rad in rader[start:]:
        def celle(f):
            j = k.get(f)
            return rad[j] if j is not None and j < len(rad) else None
        d = tolk_dato(celle("dato"))
        if "belop" in k:
            b = tolk_belop(celle("belop"))
        else:
            u, i = tolk_belop(celle("ut")), tolk_belop(celle("inn"))
            if u is None and i is None:
                b = None
            else:
                b = (i or 0) - abs(u or 0)
        tekst = str(celle("tekst") or "").strip()
        if not d or b is None or (b == 0 and not tekst):
            hoppet += 1
            continue
        ut.append({"dato": d.isoformat(), "tekst": tekst or "(uten tekst)", "belop_ore": b})
    return {"transaksjoner": ut, "hoppet": hoppet}


def overskrifter(rader: list[list], oppsett: dict) -> list[str]:
    i = oppsett.get("overskrift", -1)
    bredde = max((len(r) for r in rader[:30]), default=0)
    if i is not None and i >= 0:
        h = [str(x or "").strip() for x in rader[i]]
        return [h[j] if j < len(h) and h[j] else f"Kolonne {j + 1}" for j in range(bredde)]
    return [f"Kolonne {j + 1}" for j in range(bredde)]
