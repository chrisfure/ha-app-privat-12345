"""Automatisk henting fra banken via Enable Banking (open banking/PSD2, bare lesetilgang).

Slik henger det sammen:
  1. Familien registrerer en egen «app» hos Enable Banking og kobler sine egne kontoer
     til den («restricted mode», gratis for egne kontoer). De får en app-ID og en
     privat nøkkel (.pem), som limes inn under Innstillinger.
  2. «Koble til» starter et samtykke: Pengeboka ber Enable Banking om en adresse,
     brukeren logger inn med BankID hos banken og havner til slutt på redirect-adressen
     (https://localhost/?code=…). Den adressen limes inn i Pengeboka, som bytter koden
     mot en økt. Pengeboka trenger derfor ingen åpen port – den snakker bare utover.
  3. Hver natt (og på «Hent nå») hentes bokførte transaksjoner og importeres som en vanlig fil.

Innloggingen mot Enable Banking er en JWT signert med RS256. Signeringen er gjort med
standardbiblioteket (RSA PKCS#1 v1.5), så appen trenger ingen ekstra pakker.
Den private nøkkelen ligger bare i databasen og sendes aldri ut av appen.
"""
from __future__ import annotations

import base64
import hashlib
import json
import logging
import secrets
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation

import fil
from db import naa_iso

log = logging.getLogger("pengeboka.bank")

API = "https://api.enablebanking.com"
STANDARD_REDIRECT = "https://localhost/"
LAND = "NO"
FORSTE_HENTING_DAGER = 730      # første gang: så langt tilbake banken gir
OVERLAPP_DAGER = 10             # senere: litt overlapp, i tilfelle sene bokføringer
VARSEL_DAGER = 14               # varsle før samtykket går ut
_lås = threading.Lock()


class Bankfeil(Exception):
    pass


# ---------------------------------------------------------------- RSA og JWT (bare stdlib)
def _der(b: bytes, i: int) -> tuple[int, bytes, int]:
    tag = b[i]
    n = b[i + 1]
    i += 2
    if n & 0x80:
        k = n & 0x7F
        n = int.from_bytes(b[i:i + k], "big")
        i += k
    return tag, b[i:i + n], i + n


def _sekvens(b: bytes) -> list[tuple[int, bytes]]:
    ut, i = [], 0
    while i < len(b):
        tag, v, i = _der(b, i)
        ut.append((tag, v))
    return ut


def les_nokkel(pem: str) -> dict:
    """RSA-nøkkel fra PEM (PKCS#8 «PRIVATE KEY» eller PKCS#1 «RSA PRIVATE KEY»)."""
    tekst = (pem or "").strip()
    if "ENCRYPTED" in tekst:
        raise Bankfeil("Nøkkelen er kryptert med passord. Bruk nøkkelfilen slik den ble lastet ned fra Enable Banking.")
    linjer = [l.strip() for l in tekst.splitlines() if l.strip() and not l.startswith("-----")]
    if not linjer or "PRIVATE KEY-----" not in tekst:
        raise Bankfeil("Dette ser ikke ut som en privat nøkkel (.pem-filen fra Enable Banking)")
    try:
        der = base64.b64decode("".join(linjer), validate=True)
        tag, innhold, _ = _der(der, 0)
        deler = _sekvens(innhold)
        if len(deler) >= 3 and deler[1][0] == 0x30 and deler[2][0] == 0x04:   # PKCS#8 → pakk ut PKCS#1
            _, innhold, _ = _der(deler[2][1], 0)
            deler = _sekvens(innhold)
        tall = [int.from_bytes(v, "big") for t, v in deler if t == 0x02]
        _, n, e, d, p, q, dp, dq, qi = tall[:9]
    except Bankfeil:
        raise
    except Exception:
        raise Bankfeil("Klarte ikke å lese nøkkelen. Last opp .pem-filen slik den er.") from None
    if n.bit_length() < 2048 or p * q != n:
        raise Bankfeil("Nøkkelen er ugyldig eller for kort (må være RSA på minst 2048 bit)")
    return {"n": n, "e": e, "d": d, "p": p, "q": q, "dp": dp, "dq": dq, "qi": qi}


_SHA256_PREFIKS = bytes.fromhex("3031300d060960864801650304020105000420")


def signer(nokkel: dict, data: bytes) -> bytes:
    """RSASSA-PKCS1-v1_5 med SHA-256 (RS256)."""
    k = (nokkel["n"].bit_length() + 7) // 8
    t = _SHA256_PREFIKS + hashlib.sha256(data).digest()
    em = b"\x00\x01" + b"\xff" * (k - len(t) - 3) + b"\x00" + t
    m = int.from_bytes(em, "big")
    # Kinesisk restteorem – samme svar som pow(m, d, n), men raskere
    m1 = pow(m, nokkel["dp"], nokkel["p"])
    m2 = pow(m, nokkel["dq"], nokkel["q"])
    h = (nokkel["qi"] * (m1 - m2)) % nokkel["p"]
    s = m2 + h * nokkel["q"]
    return s.to_bytes(k, "big")


def _b64(b: bytes) -> str:
    return base64.urlsafe_b64encode(b).rstrip(b"=").decode()


def jwt(app_id: str, nokkel: dict, levetid: int = 3600) -> str:
    naa = int(time.time())
    hode = _b64(json.dumps({"typ": "JWT", "alg": "RS256", "kid": app_id}, separators=(",", ":")).encode())
    innhold = _b64(json.dumps({"iss": "enablebanking.com", "aud": "api.enablebanking.com", "iat": naa,
                               "exp": naa + levetid}, separators=(",", ":")).encode())
    return f"{hode}.{innhold}.{_b64(signer(nokkel, f'{hode}.{innhold}'.encode()))}"


# ---------------------------------------------------------------- HTTP
class _IngenOmdirigering(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *a, **k):
        return None


_opener = urllib.request.build_opener(_IngenOmdirigering())


def _kall(db, metode: str, sti: str, data: dict | None = None, app: dict | None = None):
    app = app or oppsett(db)
    if not app:
        raise Bankfeil("Bankkoblingen er ikke satt opp")
    token = jwt(app["id"], les_nokkel(app["nokkel"]))
    body = json.dumps(data).encode() if data is not None else None
    base = db.innstilling("bank_api") or API   # kan overstyres i tester
    req = urllib.request.Request(base + sti, data=body, method=metode,
                                 headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json",
                                          "Accept": "application/json"})
    try:
        with _opener.open(req, timeout=60) as r:
            return json.loads(r.read() or b"{}")
    except urllib.error.HTTPError as e:
        try:
            svar = json.loads(e.read() or b"{}")
        except ValueError:
            svar = {}
        kode = str(svar.get("error") or svar.get("code") or "")
        melding = str(svar.get("message") or svar.get("detail") or "")[:200]
        log.info("Enable Banking svarte %s på %s %s: %s %s", e.code, metode, sti.split("?")[0], kode, melding)
        if e.code == 401:
            raise Bankfeil("Enable Banking godtok ikke app-ID-en eller nøkkelen. Sjekk at de hører sammen.") from None
        if e.code == 429 or "RATE" in kode.upper():
            raise Bankfeil("Banken tillater bare noen få hentinger i døgnet. Prøv igjen senere – nattens henting går som vanlig.") from None
        if "EXPIRED" in kode.upper() or "CLOSED" in kode.upper() or "REVOKED" in kode.upper() or e.code in (403, 410):
            raise Utlopt("Samtykket fra banken har gått ut eller er trukket tilbake. Koble til på nytt.") from None
        raise Bankfeil(f"Enable Banking svarte med feil {e.code}{': ' + melding if melding else ''}") from None
    except (urllib.error.URLError, TimeoutError, OSError) as e:
        raise Bankfeil(f"Får ikke kontakt med Enable Banking ({getattr(e, 'reason', e)}). Sjekk internettforbindelsen.") from None
    except ValueError:
        raise Bankfeil("Enable Banking svarte med noe Pengeboka ikke forstår") from None


class Utlopt(Bankfeil):
    pass


# ---------------------------------------------------------------- oppsett
def oppsett(db) -> dict | None:
    a = db.innstilling("bank_app")
    if not a or not db.innstilling("bank_nokkel"):
        return None
    return {**a, "nokkel": db.innstilling("bank_nokkel")}


def sett_opp(db, app_id: str, pem: str, redirect: str | None = None) -> dict:
    app_id = (app_id or "").strip()
    if not app_id or len(app_id) > 100 or any(c.isspace() for c in app_id):
        raise Bankfeil("Lim inn app-ID-en (Application ID) fra Enable Banking")
    les_nokkel(pem)  # gir en forståelig feil hvis filen er feil
    redirect = (redirect or STANDARD_REDIRECT).strip()
    if not redirect.startswith("https://"):
        raise Bankfeil("Redirect-adressen må begynne med https://")
    info = _kall(db, "GET", "/application", app={"id": app_id, "nokkel": pem})
    if info.get("redirect_urls") and redirect not in info["redirect_urls"]:
        raise Bankfeil(f"{redirect} står ikke under «Allowed redirect URLs» i appen hos Enable Banking. "
                       f"Der står: {', '.join(info['redirect_urls'])}")
    if info.get("active") is False:
        raise Bankfeil("Appen er ikke aktivert ennå. Trykk «Link accounts» på appen hos Enable Banking og godkjenn med BankID.")
    db.sett_innstilling("bank_app", {"id": app_id, "navn": str(info.get("name") or "")[:60],
                                     "miljo": str(info.get("environment") or "")[:20], "redirect": redirect})
    db.sett_innstilling("bank_nokkel", pem.strip())
    return status(db)


def fjern_oppsett(db) -> None:
    for okt in db.rader("SELECT session_id FROM bank_okter"):
        koble_fra(db, okt["session_id"])
    for k in ("bank_app", "bank_nokkel", "bank_venter", "bank_banker", "bank_sist"):
        db.kjor("DELETE FROM innstillinger WHERE nokkel = ?", (k,))


def banker(db) -> list[dict]:
    """Banker i Norge for privatpersoner. Lagres et døgn."""
    lagret = db.innstilling("bank_banker")
    if lagret and lagret.get("tid", 0) > time.time() - 86400:
        return lagret["liste"]
    svar = _kall(db, "GET", f"/aspsps?country={LAND}&psu_type=personal")
    liste = sorted(({"navn": a["name"], "maks_sekunder": a.get("maximum_consent_validity")}
                    for a in svar.get("aspsps", []) if a.get("name")), key=lambda a: (a["navn"] != "DNB", a["navn"]))
    db.sett_innstilling("bank_banker", {"tid": time.time(), "liste": liste})
    return liste


# ---------------------------------------------------------------- samtykke
def start(db, bank: str, av: str | None) -> dict:
    app = oppsett(db)
    if not app:
        raise Bankfeil("Sett opp bankkoblingen først")
    valgt = next((b for b in banker(db) if b["navn"] == bank), None)
    if not valgt:
        raise Bankfeil("Velg en bank fra lista")
    sek = valgt.get("maks_sekunder") or 180 * 86400
    gyldig = datetime.now(timezone.utc) + timedelta(seconds=max(3600, min(int(sek), 180 * 86400) - 3600))
    state = secrets.token_urlsafe(18)
    svar = _kall(db, "POST", "/auth", {
        "access": {"valid_until": gyldig.isoformat(timespec="seconds")},
        "aspsp": {"name": bank, "country": LAND}, "state": state,
        "redirect_url": app.get("redirect") or STANDARD_REDIRECT, "psu_type": "personal", "language": "no"})
    if not svar.get("url"):
        raise Bankfeil("Enable Banking ga ingen adresse å logge inn på")
    db.sett_innstilling("bank_venter", {"state": state, "bank": bank, "tid": time.time(), "av": av})
    return {"url": svar["url"]}


def fullfor(db, pb, limt_inn: str, av: str | None) -> dict:
    """Tar imot adressen brukeren havnet på etter BankID (eller bare koden)."""
    tekst = (limt_inn or "").strip()
    if not tekst:
        raise Bankfeil("Lim inn adressen du havnet på etter BankID")
    q = dict(urllib.parse.parse_qsl(urllib.parse.urlparse(tekst).query)) if "?" in tekst or "://" in tekst else {"code": tekst}
    if q.get("error"):
        grunn = q.get("error_description") or q["error"]
        raise Bankfeil(f"Banken avbrøt innloggingen: {grunn[:150]}")
    venter = db.innstilling("bank_venter")
    if not venter or venter.get("tid", 0) < time.time() - 3600:
        raise Bankfeil("Innloggingen er for gammel. Trykk «Koble til» og prøv igjen.")
    if q.get("state") and not secrets.compare_digest(q["state"], venter["state"]):
        raise Bankfeil("Adressen hører ikke til denne innloggingen. Trykk «Koble til» og prøv igjen.")
    kode = q.get("code")
    if not kode or len(kode) > 400:
        raise Bankfeil("Fant ingen kode i adressen. Kopier hele adressen fra adressefeltet.")
    s = _kall(db, "POST", "/sessions", {"code": kode})
    sid = s.get("session_id")
    if not sid:
        raise Bankfeil("Enable Banking ga ingen økt tilbake")
    gyldig = (s.get("access") or {}).get("valid_until") or ""
    with db.transaksjon():
        db.con.execute("INSERT OR REPLACE INTO bank_okter(session_id, bank, gyldig_til, opprettet, av) VALUES(?,?,?,?,?)",
                       (sid, venter["bank"], gyldig[:25], naa_iso(), av or venter.get("av")))
        for a in s.get("accounts") or []:
            uid = a.get("uid")
            if not uid:
                continue
            nummer = kontonummer(a)
            gammel = db.con.execute("SELECT konto_id, aktiv, sist_til FROM bank_kontoer WHERE nummer = ?",
                                    (nummer,)).fetchone() if nummer else None
            if gammel:   # samme konto fra et tidligere samtykke – behold valgene
                konto_id = gammel[0]
                db.con.execute("DELETE FROM bank_kontoer WHERE nummer = ?", (nummer,))
            elif nummer:
                rad = db.con.execute("SELECT id FROM kontoer WHERE nummer = ?", (nummer,)).fetchone()
                konto_id = rad[0] if rad else None
            else:
                konto_id = None
            db.con.execute("INSERT OR REPLACE INTO bank_kontoer(uid, session_id, navn, nummer, type, konto_id, aktiv, sist_til) "
                           "VALUES(?,?,?,?,?,?,?,?)",
                           (uid, sid, kontonavn(a)[:60], nummer, kontotype(a), konto_id,
                            gammel[1] if gammel else 1, gammel[2] if gammel else None))
    db.kjor("DELETE FROM innstillinger WHERE nokkel = 'bank_venter'")
    # Kontoer som ikke finnes i Pengeboka ennå, opprettes – de kan skjules eller slås av etterpå
    for bk in db.rader("SELECT * FROM bank_kontoer WHERE session_id = ? AND konto_id IS NULL AND aktiv = 1", (sid,)):
        ny = pb.lagre_konto({"navn": bk["navn"], "type": bk["type"], "nummer": bk["nummer"]})
        db.kjor("UPDATE bank_kontoer SET konto_id = ? WHERE uid = ?", (ny["id"], bk["uid"]))
    try:
        hent(db, pb, session_id=sid, forste=True)
    except Bankfeil as e:
        log.info("Første henting etter tilkobling: %s", e)
    return status(db)


def koble_fra(db, session_id: str) -> None:
    try:
        _kall(db, "DELETE", f"/sessions/{urllib.parse.quote(session_id)}")
    except Bankfeil as e:
        log.info("Kunne ikke avslutte økten hos Enable Banking: %s", e)
    db.kjor("DELETE FROM bank_okter WHERE session_id = ?", (session_id,))


# ---------------------------------------------------------------- kontoer
def _id_nummer(ident: dict | None) -> str | None:
    if not isinstance(ident, dict):
        return None
    iban = str(ident.get("iban") or "").replace(" ", "")
    if iban.upper().startswith("NO") and len(iban) == 15:
        return fil.kontonummer(iban[4:])
    other = ident.get("other") or {}
    return fil.kontonummer(str(other.get("identification") or "")) if isinstance(other, dict) else None


def kontonummer(a: dict) -> str | None:
    for ident in [a.get("account_id")] + list(a.get("all_account_ids") or []):
        nr = _id_nummer(ident)
        if nr:
            return nr
    return None


def kontonavn(a: dict) -> str:
    nr = kontonummer(a)
    navn = str(a.get("name") or a.get("product") or a.get("details") or "").strip()
    return navn or (f"Konto {fil.vis_nummer(nr)}" if nr else "Bankkonto")


def kontotype(a: dict) -> str:
    t = str(a.get("cash_account_type") or "").upper()
    tekst = f"{a.get('name') or ''} {a.get('product') or ''}".lower()
    if t == "CARD" or "kredittkort" in tekst or "mastercard" in tekst or "visa" in tekst:
        return "kreditt"
    if t == "SVGS" or "spare" in tekst or "sparing" in tekst or "bsu" in tekst:
        return "sparing"
    if t == "LOAN" or "lån" in tekst:
        return "lan"
    return "bruk"


def endre_konto(db, pb, uid: str, d: dict) -> dict:
    bk = db.rad("SELECT * FROM bank_kontoer WHERE uid = ?", (uid,))
    if not bk:
        raise Bankfeil("Ukjent bankkonto")
    if "aktiv" in d:
        db.kjor("UPDATE bank_kontoer SET aktiv = ? WHERE uid = ?", (1 if d["aktiv"] else 0, uid))
    if "konto_id" in d:
        kid = d["konto_id"]
        if kid == "ny":
            kid = pb.lagre_konto({"navn": bk["navn"], "type": bk["type"], "nummer": None})["id"]
        elif kid is not None:
            kid = int(kid)
            if not db.verdi("SELECT 1 FROM kontoer WHERE id = ?", (kid,)):
                raise Bankfeil("Ukjent konto")
        db.kjor("UPDATE bank_kontoer SET konto_id = ? WHERE uid = ?", (kid, uid))
    return status(db)


# ---------------------------------------------------------------- henting
def _belop_ore(t: dict) -> int | None:
    a = t.get("transaction_amount") or {}
    try:
        v = Decimal(str(a.get("amount")))
    except (InvalidOperation, ValueError):
        return None
    ore = int((abs(v) * 100).to_integral_value())
    ind = str(t.get("credit_debit_indicator") or "").upper()
    if ind == "DBIT" or (not ind and v < 0):
        ore = -ore
    return ore


def _tekst(t: dict, belop: int) -> str:
    rem = t.get("remittance_information") or []
    if isinstance(rem, str):
        rem = [rem]
    tekst = " ".join(str(r).strip() for r in rem if str(r).strip())
    part = (t.get("creditor") if belop < 0 else t.get("debtor")) or {}
    navn = str(part.get("name") or "").strip() if isinstance(part, dict) else ""
    if navn and navn.lower() not in tekst.lower() and not any(c.isalpha() for c in tekst):
        tekst = f"{navn} {tekst}".strip()   # tom tekst eller bare et referansenummer
    if not tekst:
        kode = t.get("bank_transaction_code") or {}
        tekst = str((kode.get("description") if isinstance(kode, dict) else "") or t.get("note") or "").strip()
    return tekst[:300] or "(uten tekst)"


def tolk(transaksjoner: list[dict]) -> list[dict]:
    """Enable Banking-format → Pengebokas importformat. Bare bokførte (ikke reserverte) beløp."""
    ut, teller = [], {}
    for t in transaksjoner:
        if str(t.get("status") or "BOOK").upper() != "BOOK":
            continue
        belop = _belop_ore(t)
        dato = str(t.get("transaction_date") or t.get("booking_date") or t.get("value_date") or "")[:10]
        if belop is None or not belop or len(dato) != 10:
            continue
        try:
            date.fromisoformat(dato)
        except ValueError:
            continue
        tekst = _tekst(t, belop)
        ref = t.get("transaction_id") or t.get("entry_reference")
        if not ref:
            grunn = f"{dato}|{belop}|{tekst}"
            teller[grunn] = teller.get(grunn, 0) + 1
            ref = "h" + hashlib.sha1(f"{grunn}#{teller[grunn]}".encode()).hexdigest()[:20]
        motkonto = _id_nummer(t.get("creditor_account") if belop < 0 else t.get("debtor_account"))
        ut.append({"dato": dato, "belop_ore": belop, "tekst": tekst, "motkonto": motkonto, "ref": str(ref)[:100]})
    return ut


def _hent_konto(db, uid: str, fra: date) -> list[dict]:
    alle, nokkel, runder = [], None, 0
    while True:
        q = {"date_from": fra.isoformat(), "transaction_status": "BOOK"}
        if nokkel:
            q["continuation_key"] = nokkel
        svar = _kall(db, "GET", f"/accounts/{urllib.parse.quote(uid)}/transactions?{urllib.parse.urlencode(q)}")
        alle += svar.get("transactions") or []
        nokkel = svar.get("continuation_key")
        runder += 1
        if not nokkel or runder >= 200:
            return alle


def hent(db, pb, session_id: str | None = None, forste: bool = False, av: str | None = None) -> dict:
    """Henter nye transaksjoner for alle aktive bankkontoer. Kaster Bankfeil hvis alt feilet."""
    if not _lås.acquire(blocking=False):
        raise Bankfeil("Henter allerede – vent litt")
    try:
        sql = ("SELECT bk.*, o.gyldig_til, o.bank FROM bank_kontoer bk JOIN bank_okter o ON o.session_id = bk.session_id "
               "WHERE bk.aktiv = 1 AND bk.konto_id IS NOT NULL")
        kontoer = db.rader(sql + (" AND bk.session_id = ?" if session_id else ""), (session_id,) if session_id else ())
        i_dag = pb.i_dag()
        nye, feil = 0, []
        for bk in kontoer:
            if bk["sist_til"] and not forste:
                fra = date.fromisoformat(bk["sist_til"]) - timedelta(days=OVERLAPP_DAGER)
            else:
                fra = i_dag - timedelta(days=FORSTE_HENTING_DAGER)
            try:
                tx = tolk(_hent_konto(db, bk["uid"], fra))
                r = pb.importer_bank(bk["konto_id"], tx, f"{bk['bank']}: {bk['navn']}", av or "Automatisk") if tx else {"nye": 0}
                nye += r["nye"]
                til = max([t["dato"] for t in tx] + ([bk["sist_til"]] if bk["sist_til"] else []), default=None)
                db.kjor("UPDATE bank_kontoer SET sist_hentet = ?, sist_til = ?, feil = NULL WHERE uid = ?", (naa_iso(), til, bk["uid"]))
            except Bankfeil as e:
                feil.append(f"{bk['navn']}: {e}")
                db.kjor("UPDATE bank_kontoer SET feil = ?, sist_forsok = ? WHERE uid = ?", (str(e)[:300], naa_iso(), bk["uid"]))
                if isinstance(e, Utlopt):
                    db.kjor("UPDATE bank_okter SET utlopt = 1 WHERE session_id = ?", (bk["session_id"],))
        db.sett_innstilling("bank_sist", {"tid": naa_iso(), "nye": nye, "feil": feil})
        if kontoer and len(feil) == len(kontoer):
            raise Bankfeil(feil[0] if len(feil) == 1 else "Hentingen feilet: " + "; ".join(feil))
        return {"nye": nye, "feil": feil}
    finally:
        _lås.release()


def hent_stille(db, pb) -> None:
    if not oppsett(db) or not db.verdi("SELECT 1 FROM bank_kontoer WHERE aktiv = 1"):
        return
    try:
        r = hent(db, pb)
        log.info("Bankhenting: %s nye transaksjoner", r["nye"])
    except Bankfeil as e:
        log.info("Bankhenting: %s", e)
    except Exception:
        log.exception("Bankhenting feilet")


# ---------------------------------------------------------------- status og bakgrunn
def status(db) -> dict:
    app = db.innstilling("bank_app")
    okter = db.rader("SELECT session_id, bank, gyldig_til, opprettet, av, utlopt FROM bank_okter ORDER BY opprettet")
    kontoer = db.rader("""SELECT bk.uid, bk.session_id, bk.navn, bk.nummer, bk.konto_id, bk.aktiv, bk.sist_hentet,
                                 bk.sist_til, bk.feil, k.navn AS konto FROM bank_kontoer bk
                          LEFT JOIN kontoer k ON k.id = bk.konto_id ORDER BY bk.navn""")
    i_dag = datetime.now(timezone.utc)
    for o in okter:
        try:
            dager = (datetime.fromisoformat(o["gyldig_til"].replace("Z", "+00:00")) - i_dag).days
        except (ValueError, AttributeError):
            dager = None
        o["dager_igjen"] = dager
        o["utlopt"] = bool(o["utlopt"]) or (dager is not None and dager < 0)
        o["kontoer"] = [dict(k, nummer_vis=fil.vis_nummer(k["nummer"])) for k in kontoer if k["session_id"] == o["session_id"]]
    return {"satt_opp": bool(app and db.innstilling("bank_nokkel")),
            "app": {k: v for k, v in (app or {}).items()} if app else None,
            "standard_redirect": STANDARD_REDIRECT, "venter": bool(db.innstilling("bank_venter")),
            "okter": okter, "sist": db.innstilling("bank_sist")}


def varsler(db) -> list[dict]:
    """Til «Trenger dere»: samtykke som går ut snart, eller henting som feiler."""
    ut = []
    for o in status(db)["okter"]:
        if o["utlopt"]:
            ut.append({"type": "bank", "nokkel": f"bank:utlopt:{o['session_id']}",
                       "tekst": f"{o['bank']}: samtykket har gått ut – koble til på nytt med BankID"})
        elif o["dager_igjen"] is not None and o["dager_igjen"] <= VARSEL_DAGER:
            ut.append({"type": "bank", "nokkel": f"bank:snart:{o['session_id']}",
                       "tekst": f"{o['bank']}: samtykket går ut om {max(o['dager_igjen'], 0)} dager – forny med BankID"})
        else:
            for k in o["kontoer"]:
                if k["aktiv"] and k["feil"]:
                    ut.append({"type": "bank", "nokkel": f"bank:feil:{k['uid']}:{(k['sist_hentet'] or '')[:10]}",
                               "tekst": f"Automatisk henting for {k['navn']} feilet: {k['feil']}"})
    return ut


def start_bakgrunn(db, pb) -> None:
    """Henter hver natt rundt kl. 05, og ved oppstart hvis det er mer enn et døgn siden sist."""
    def loop():
        time.sleep(60)
        while True:
            sist = (db.innstilling("bank_sist") or {}).get("tid")
            naa = datetime.now(pb.tz)
            gammel = not sist or (datetime.now(timezone.utc) - datetime.fromisoformat(sist)).total_seconds() > 20 * 3600
            if gammel and (naa.hour >= 5 or not sist):
                hent_stille(db, pb)
            time.sleep(1800)
    threading.Thread(target=loop, daemon=True, name="bank-henting").start()
