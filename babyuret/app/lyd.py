"""Lydgjenkjenning: gråt og rop som data til søvnloggen.

Lytteenheter (iPhone/iPad med Lydgjenkjenning, Android med Lydvarsler)
sender hendelsen «babyuret_lyd» med `type` (grat/rop) og `kilde`.
Hver melding går gjennom fire sperrer før den kan gi poeng:

1. Kjent enhet?
2. Er enheten der babyen er? (babyens sted + hjemmenett)
3. Pågår en søvnøkt?
4. Er vi forbi innsovningsvinduet?

Poengsummen over et glidende vindu avgjør om det bare er uro, en mulig
oppvåkning eller en trolig oppvåkning. En trolig oppvåkning blir et
*forslag* som dere bekrefter i appen. Ingen varsler sendes herfra.

Svarene (Våknet / Sovnet igjen / Feil) brukes til å justere terskelen
lokalt for akkurat denne babyen.
"""
from __future__ import annotations

import re
from datetime import datetime, timedelta

from db import fra_iso, naa, til_iso

SKJEMA = """
CREATE TABLE IF NOT EXISTS lyd (
    id        INTEGER PRIMARY KEY AUTOINCREMENT,
    tid       TEXT NOT NULL,           -- UTC ISO
    type      TEXT NOT NULL,           -- grat | rop
    kilde     TEXT NOT NULL,
    sted      TEXT,
    vekt      REAL NOT NULL DEFAULT 0, -- effektiv vekt (enhet × type × sted)
    tolkning  TEXT NOT NULL,           -- avvist | vaaken | innsovning | uro | mulig | trolig | motbevis
    grunn     TEXT,
    poeng     REAL,
    sovn_id   INTEGER
);
CREATE INDEX IF NOT EXISTS idx_lyd_tid ON lyd(tid);
CREATE TABLE IF NOT EXISTS lyd_forslag (
    id        INTEGER PRIMARY KEY AUTOINCREMENT,
    sovn_id   INTEGER NOT NULL,
    tid       TEXT NOT NULL,           -- foreslått oppvåkning (første treff i vinduet)
    poeng     REAL NOT NULL,
    stoy      INTEGER NOT NULL DEFAULT 0,
    status    TEXT NOT NULL,           -- venter | vaaknet | sovnet_igjen | feil | manuelt_vaaknet | auto | utlopt
    opprettet TEXT NOT NULL,
    besvart   TEXT,
    av        TEXT
);
CREATE INDEX IF NOT EXISTS idx_forslag_status ON lyd_forslag(status, opprettet);
"""

TYPER = ("grat", "rop")
ROLLER = ("fast", "flyttbar", "personlig", "motbevis")
STEDER = ("hjemme", "hjemme_vogn", "ute", "reise", "barnevakt_hjemme", "barnevakt_ute")
STED_NAVN = {
    "hjemme": "Hjemme",
    "hjemme_vogn": "Hjemme, i vogna ute",
    "ute": "Ute",
    "reise": "På reise",
    "barnevakt_hjemme": "Hjemme med barnevakt",
    "barnevakt_ute": "Ute med barnevakt",
}
HJEMME_STEDER = ("hjemme", "hjemme_vogn", "barnevakt_hjemme")
STEDSFAKTOR = {"hjemme": 1.0, "hjemme_vogn": 0.8, "ute": 0.5, "reise": 1.0,
               "barnevakt_hjemme": 1.0, "barnevakt_ute": 0.5}

VEKT_HJEMME_IKKE_VED = 0.3     # personlig/flyttbar enhet hjemme, men ikke valgt som «ved babyen»
SAMTIDIG_SEK = 30              # to enheter innen så mange sekunder = bekreftelse
NAER_PROGNOSE_MIN = 20         # ± rundt prognosevinduet for oppvåkning
MOTBEVIS_MAKS = 2              # maks poengtrekk fra motbevis-enheter
LAERING_ANTALL = 30            # så mange siste besvarte forslag brukes i læringen

STANDARD = {
    "aktiv": False,
    "enheter": [],
    "hjemmenett": [],
    "innsovning_min": 15,
    "vindu_min": 5,
    "terskel_mulig": 2.0,
    "terskel_trolig": 4.0,
    "svarfrist_min": 30,
    "rop_vekt": 0.5,
    "laering": True,
}

KILDE = re.compile(r"^[a-z0-9_]{1,30}$")
ENTITET = re.compile(r"^[a-z_]+\.[a-z0-9_]+$")


class UgyldigLydoppsett(ValueError):
    pass


def _tall(d: dict, felt: str, lav: float, hoy: float, heltall: bool = False):
    try:
        v = float(d[felt])
    except (TypeError, ValueError):
        raise UgyldigLydoppsett(f"Ugyldig verdi for {felt}")
    if not lav <= v <= hoy:
        raise UgyldigLydoppsett(f"{felt} må være mellom {lav:g} og {hoy:g}")
    return int(round(v)) if heltall else round(v, 2)


def rens_oppsett(d: dict | None, gammel: dict | None = None) -> dict:
    """Valider lydoppsettet fra innstillingene. Ukjente felt ignoreres."""
    ut = dict(STANDARD)
    ut.update(gammel or {})
    d = d or {}
    if "aktiv" in d:
        ut["aktiv"] = bool(d["aktiv"])
    if "laering" in d:
        ut["laering"] = bool(d["laering"])
    if "enheter" in d:
        enheter, sett = [], set()
        for e in d["enheter"] or []:
            kilde = str(e.get("kilde") or "").strip().lower()
            if not KILDE.match(kilde):
                raise UgyldigLydoppsett("Kilde-navn kan bare ha små bokstaver a–z, tall og _ (maks 30 tegn)")
            if kilde in sett:
                raise UgyldigLydoppsett(f"Kilden «{kilde}» er brukt to ganger")
            sett.add(kilde)
            rolle = e.get("rolle") or "personlig"
            if rolle not in ROLLER:
                raise UgyldigLydoppsett("Ugyldig rolle for enhet")
            entitet = str(e.get("nett_entitet") or "").strip()
            if entitet and not ENTITET.match(entitet):
                raise UgyldigLydoppsett(f"«{entitet}» ser ikke ut som en entitet i Home Assistant")
            navn = str(e.get("navn") or kilde).strip()[:40]
            enheter.append({"kilde": kilde, "navn": navn, "rolle": rolle, "nett_entitet": entitet})
        if len(enheter) > 12:
            raise UgyldigLydoppsett("Maks 12 enheter")
        ut["enheter"] = enheter
    if "hjemmenett" in d:
        nett = d["hjemmenett"]
        if isinstance(nett, str):
            nett = nett.split(",")
        ut["hjemmenett"] = [str(n).strip()[:64] for n in nett or [] if str(n).strip()][:6]
    for felt, lav, hoy, heltall in (("innsovning_min", 0, 60, True), ("vindu_min", 1, 30, True),
                                    ("terskel_mulig", 0.5, 10, False), ("terskel_trolig", 1, 15, False),
                                    ("svarfrist_min", 5, 240, True), ("rop_vekt", 0, 1, False)):
        if felt in d:
            ut[felt] = _tall(d, felt, lav, hoy, heltall)
    if ut["terskel_mulig"] >= ut["terskel_trolig"]:
        raise UgyldigLydoppsett("Terskelen for «mulig» må være lavere enn for «trolig»")
    return ut


class Lydlogikk:
    def __init__(self, bu):
        self.bu = bu
        self.db = bu.db
        self.db.con.executescript(SKJEMA)
        self.db.con.commit()
        bu.ved_endring(self._ved_endring)

    # ---- oppsett og sted -------------------------------------------------
    @property
    def oppsett(self) -> dict:
        return self.bu.cfg.lyd

    def enhet(self, kilde: str) -> dict | None:
        return next((e for e in self.oppsett["enheter"] if e["kilde"] == kilde), None)

    def sted(self) -> dict:
        lagret = self.db.les_innstillinger().get("lyd_sted") or {}
        sted = lagret.get("sted") if lagret.get("sted") in STEDER else "hjemme"
        kjente = {e["kilde"] for e in self.oppsett["enheter"]}
        med = [k for k in lagret.get("med") or [] if k in kjente]
        return {"sted": sted, "navn": STED_NAVN[sted], "med": med, "siden": lagret.get("siden")}

    def sett_sted(self, sted: str, med: list[str] | None, av: str | None = None) -> dict:
        if sted not in STEDER:
            raise UgyldigLydoppsett("Ukjent sted")
        kjente = {e["kilde"] for e in self.oppsett["enheter"]}
        med = [k for k in dict.fromkeys(med or []) if k in kjente]
        self.db.lagre_innstillinger({"lyd_sted": {"sted": sted, "med": med, "siden": til_iso(naa()), "av": av}})
        self.bu._endret("lyd_sted", None)
        return self.sted()

    # ---- sperre 2: er enheten der babyen er? -----------------------------
    def hjemme(self, enhet: dict, nett: str | None) -> bool | None:
        """True = på hjemmenettet, False = borte, None = ukjent."""
        if not enhet["nett_entitet"]:
            return True if enhet["rolle"] in ("fast", "motbevis") else None
        if nett in (None, "", "unknown", "unavailable"):
            return None
        return nett == "home" or nett.strip() in self.oppsett["hjemmenett"]

    def vekt(self, enhet: dict, sted: dict, nett: str | None) -> tuple[float, str | None]:
        """Enhetens vekt der babyen er nå (0–1), og grunnen hvis den avvises."""
        s, med, rolle = sted["sted"], sted["med"], enhet["rolle"]
        if s not in HJEMME_STEDER:
            if enhet["kilde"] in med:
                return 1.0, None
            return 0.0, f"enheten er ikke med babyen ({STED_NAVN[s].lower()})"
        hjemme = self.hjemme(enhet, nett)
        if hjemme is False:
            return 0.0, "enheten er ikke på hjemmenettet"
        if enhet["kilde"] in med:
            return 1.0, None
        if s == "hjemme_vogn":
            return 0.0, "enheten står ikke ved vogna"
        if rolle == "fast":
            return 1.0, None
        if hjemme is None:
            return 0.0, "kan ikke bekrefte at enheten er hjemme"
        return VEKT_HJEMME_IKKE_VED, None

    # ---- mottak ----------------------------------------------------------
    def motta(self, type_: str, kilde: str, nett: str | None = None, tid: datetime | None = None) -> dict:
        """Behandle én lydmelding. Returnerer raden som ble lagret."""
        tid = tid or naa()
        type_ = (type_ or "grat").strip().lower()
        if type_ in ("gråt", "grater", "gråter", "cry", "baby_cry", "crying"):
            type_ = "grat"
        if type_ in ("shout", "shouting", "roper", "roping"):
            type_ = "rop"
        kilde = (kilde or "").strip().lower()
        sted = self.sted()
        rad = {"tid": tid, "type": type_, "kilde": kilde, "sted": sted["sted"], "vekt": 0.0,
               "poeng": None, "sovn_id": None}

        if not self.oppsett["aktiv"]:
            return self._lagre(rad, "avvist", "lydgjenkjenning er slått av")
        if type_ not in TYPER:
            return self._lagre(rad, "avvist", f"ukjent lydtype «{type_}»")
        enhet = self.enhet(kilde)
        if not enhet:
            return self._lagre(rad, "avvist", "ukjent enhet")

        if enhet["rolle"] == "motbevis":
            hjemme = self.hjemme(enhet, nett)
            if sted["sted"] in HJEMME_STEDER and hjemme is not False:
                pag = self.db.pagaende("sovn")
                rad["sovn_id"] = pag["id"] if pag else None
                return self._lagre(rad, "motbevis", None)
            return self._lagre(rad, "avvist", "motbevis-enheten teller bare når babyen er hjemme")

        vekt, grunn = self.vekt(enhet, sted, nett)
        if vekt <= 0:
            return self._lagre(rad, "avvist", grunn)
        faktor = 1.0 if type_ == "grat" else self.oppsett["rop_vekt"]
        rad["vekt"] = round(vekt * faktor * STEDSFAKTOR[sted["sted"]], 3)
        if rad["vekt"] <= 0:
            return self._lagre(rad, "avvist", "rop teller ikke (vekt 0)")

        pag = self.db.pagaende("sovn")
        if not pag:
            return self._lagre(rad, "vaaken", None)
        rad["sovn_id"] = pag["id"]
        start = fra_iso(pag["start"])
        if tid - start < timedelta(minutes=self.oppsett["innsovning_min"]):
            return self._lagre(rad, "innsovning", None)

        rad_lagret = self._lagre(rad, "uro", None)
        poeng, detaljer = self.poengsum(pag, tid)
        terskel_mulig, terskel_trolig = self.terskler(pag)
        if poeng >= terskel_trolig:
            tolkning = "trolig"
        elif poeng >= terskel_mulig:
            tolkning = "mulig"
        else:
            tolkning = "uro"
        self.db.con.execute("UPDATE lyd SET tolkning = ?, poeng = ? WHERE id = ?",
                            (tolkning, poeng, rad_lagret["id"]))
        self.db.con.commit()
        if tolkning == "trolig":
            self._forslag(pag, detaljer["forste"], poeng)
        self.bu._endret("lyd", None)
        return {**rad_lagret, "tolkning": tolkning, "poeng": poeng,
                "detaljer": {**detaljer, "forste": til_iso(detaljer["forste"])}}

    def _lagre(self, rad: dict, tolkning: str, grunn: str | None) -> dict:
        cur = self.db.con.execute(
            "INSERT INTO lyd (tid, type, kilde, sted, vekt, tolkning, grunn, poeng, sovn_id) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (til_iso(rad["tid"]), rad["type"], rad["kilde"], rad["sted"], rad["vekt"], tolkning, grunn,
             rad["poeng"], rad["sovn_id"]),
        )
        self.db.con.commit()
        return {**rad, "id": cur.lastrowid, "tid": til_iso(rad["tid"]), "tolkning": tolkning, "grunn": grunn}

    # ---- poengsum --------------------------------------------------------
    def _vindu_start(self, pag: dict, tid: datetime) -> datetime:
        start = fra_iso(pag["start"]) + timedelta(minutes=self.oppsett["innsovning_min"])
        fra = max(start, tid - timedelta(minutes=self.oppsett["vindu_min"]))
        r = self.db.con.execute(
            "SELECT MAX(besvart) FROM lyd_forslag WHERE sovn_id = ? AND status IN ('sovnet_igjen', 'feil')",
            (pag["id"],)).fetchone()[0]
        if r:
            fra = max(fra, fra_iso(r))
        return fra

    def poengsum(self, pag: dict, tid: datetime) -> tuple[float, dict]:
        fra = self._vindu_start(pag, tid)
        rader = self.db.con.execute(
            "SELECT tid, kilde, vekt, tolkning FROM lyd WHERE sovn_id = ? AND tid >= ? AND tid <= ? "
            "AND tolkning IN ('uro', 'mulig', 'trolig', 'motbevis') ORDER BY tid",
            (pag["id"], til_iso(fra), til_iso(tid))).fetchall()
        treff = [(fra_iso(r["tid"]), r["kilde"], r["vekt"]) for r in rader if r["tolkning"] != "motbevis"]
        motbevis = [fra_iso(r["tid"]) for r in rader if r["tolkning"] == "motbevis"]
        if not treff:
            return 0.0, {"forste": tid, "treff": 0}

        poeng = sum(v for _, _, v in treff)
        detaljer = {"forste": treff[0][0], "treff": len(treff), "grunnpoeng": round(poeng, 2)}

        samtidig = any(
            a[1] != b[1] and abs((a[0] - b[0]).total_seconds()) <= SAMTIDIG_SEK
            for i, a in enumerate(treff) for b in treff[i + 1:]
        )
        if samtidig:
            poeng += 1
            detaljer["flere_enheter"] = True

        trekk = sum(1 for m in motbevis if any(abs((m - t).total_seconds()) <= SAMTIDIG_SEK for t, _, _ in treff))
        if trekk:
            poeng -= min(trekk, MOTBEVIS_MAKS)
            detaljer["motbevis"] = min(trekk, MOTBEVIS_MAKS)

        prog = self._prognose()
        if prog and prog.get("klar") and prog.get("type") == "vaakner":
            p_fra, p_til, p_midt = fra_iso(prog["fra"]), fra_iso(prog["til"]), fra_iso(prog["midt"])
            slakk = timedelta(minutes=NAER_PROGNOSE_MIN)
            if p_fra - slakk <= tid <= p_til + slakk:
                poeng += 1
                detaljer["naer_prognose"] = True
            start = fra_iso(pag["start"])
            if p_midt > start and tid - start < (p_midt - start) / 2:
                poeng -= 1
                detaljer["kort_sovn"] = True
        return round(poeng, 2), detaljer

    def _prognose(self) -> dict | None:
        try:
            return self.bu.prognose.beregn()
        except Exception:  # noqa: BLE001 – prognosen skal aldri stoppe lydlogikken
            return None

    @staticmethod
    def _stoy(pag: dict) -> bool:
        return (pag.get("detaljer") or {}).get("stoykilde", "ingen") not in ("ingen", "", None)

    def terskler(self, pag: dict) -> tuple[float, float]:
        o = self.oppsett
        stoy = self._stoy(pag)
        tillegg = 1.0 if stoy else 0.0
        if o["laering"]:
            tillegg += self.laering(stoy)["justering"]
        return o["terskel_mulig"], max(o["terskel_mulig"] + 0.5, o["terskel_trolig"] + tillegg)

    # ---- forslag ---------------------------------------------------------
    def _forslag(self, pag: dict, tid: datetime, poeng: float) -> None:
        venter = self.db.con.execute(
            "SELECT id, poeng FROM lyd_forslag WHERE sovn_id = ? AND status = 'venter'", (pag["id"],)).fetchone()
        if venter:
            if poeng > venter["poeng"]:
                self.db.con.execute("UPDATE lyd_forslag SET poeng = ? WHERE id = ?", (poeng, venter["id"]))
                self.db.con.commit()
            return
        self.db.con.execute(
            "INSERT INTO lyd_forslag (sovn_id, tid, poeng, stoy, status, opprettet) VALUES (?, ?, ?, ?, 'venter', ?)",
            (pag["id"], til_iso(tid), poeng, int(self._stoy(pag)), til_iso(naa())))
        self.db.con.commit()

    def forslag(self, status: str | None = "venter", antall: int = 20) -> list[dict]:
        if status:
            rader = self.db.con.execute("SELECT * FROM lyd_forslag WHERE status = ? ORDER BY tid DESC LIMIT ?",
                                        (status, antall))
        else:
            rader = self.db.con.execute("SELECT * FROM lyd_forslag ORDER BY tid DESC LIMIT ?", (antall,))
        return [dict(r) for r in rader]

    def svar(self, fid: int, svar: str, av: str | None = None) -> dict:
        if svar not in ("vaaknet", "sovnet_igjen", "feil"):
            raise UgyldigLydoppsett("Ugyldig svar")
        f = self.db.con.execute("SELECT * FROM lyd_forslag WHERE id = ?", (fid,)).fetchone()
        if not f:
            raise UgyldigLydoppsett("Fant ikke forslaget")
        if f["status"] != "venter":
            raise UgyldigLydoppsett("Forslaget er allerede besvart")
        melding = {"vaaknet": "Registrert som oppvåkning", "sovnet_igjen": "Søvnen fortsetter",
                   "feil": "Markert som feil"}[svar]
        if svar == "vaaknet":
            pag = self.db.pagaende("sovn")
            if pag and pag["id"] == f["sovn_id"]:
                self._avslutt_sovn(pag, fra_iso(f["tid"]), "lyd")
                melding = f"Våknet {self.bu._kl(fra_iso(f['tid']))}"
        self.db.con.execute("UPDATE lyd_forslag SET status = ?, besvart = ?, av = ? WHERE id = ?",
                            (svar, til_iso(naa()), av, fid))
        self.db.con.commit()
        self.bu._endret("lyd_svar", None)
        return {"melding": melding}

    def _avslutt_sovn(self, pag: dict, tid: datetime, kilde: str) -> dict:
        start = fra_iso(pag["start"])
        detaljer = dict(pag.get("detaljer") or {})
        detaljer["slutt_kilde"] = kilde
        h = self.db.oppdater(pag["id"], slutt=max(tid, start), detaljer=detaljer)
        self.bu._endret("lyd_vaaknet", h)
        return h

    def sjekk_frister(self, nå: datetime | None = None) -> int:
        """Avslutt søvn automatisk når et forslag har ventet lenger enn svarfristen."""
        nå = nå or naa()
        grense = til_iso(nå - timedelta(minutes=self.oppsett["svarfrist_min"]))
        rader = self.db.con.execute(
            "SELECT * FROM lyd_forslag WHERE status = 'venter' AND opprettet <= ?", (grense,)).fetchall()
        for f in rader:
            pag = self.db.pagaende("sovn")
            if pag and pag["id"] == f["sovn_id"]:
                self._avslutt_sovn(pag, fra_iso(f["tid"]), "auto")
                status = "auto"
            else:
                status = "utlopt"
            self.db.con.execute("UPDATE lyd_forslag SET status = ?, besvart = ? WHERE id = ?",
                                (status, til_iso(nå), f["id"]))
        if rader:
            self.db.con.commit()
        return len(rader)

    def _ved_endring(self, hva: str, hendelse: dict | None) -> None:
        """Manuell «våknet» eller ny søvn avslutter ventende forslag."""
        if hva not in ("sovn_slutt", "sovn_veksle", "sovn_start") or not hendelse:
            return
        if hendelse.get("kategori") != "sovn":
            return
        nå = til_iso(naa())
        if hendelse.get("slutt"):
            self.db.con.execute(
                "UPDATE lyd_forslag SET status = 'manuelt_vaaknet', besvart = ? WHERE sovn_id = ? AND status = 'venter'",
                (nå, hendelse["id"]))
        else:
            self.db.con.execute(
                "UPDATE lyd_forslag SET status = 'utlopt', besvart = ? WHERE sovn_id != ? AND status = 'venter'",
                (nå, hendelse["id"]))
        self.db.con.commit()

    # ---- læring ----------------------------------------------------------
    def laering(self, stoy: bool | None = None) -> dict:
        """Treffsikkerhet fra de siste besvarte forslagene, og hvor mye terskelen justeres."""
        sql = ("SELECT status FROM lyd_forslag WHERE status IN "
               "('vaaknet', 'manuelt_vaaknet', 'sovnet_igjen', 'feil')")
        param: tuple = ()
        if stoy is not None:
            sql += " AND stoy = ?"
            param = (int(stoy),)
        sql += " ORDER BY besvart DESC LIMIT ?"
        rader = [r["status"] for r in self.db.con.execute(sql, (*param, LAERING_ANTALL))]
        n = len(rader)
        riktige = sum(1 for s in rader if s in ("vaaknet", "manuelt_vaaknet"))
        presisjon = riktige / n if n else None
        justering = 0.0
        if n >= 5 and presisjon is not None:
            if presisjon < 0.5:
                justering = 1.0
            elif presisjon < 0.7:
                justering = 0.5
            elif n >= 10 and presisjon > 0.9:
                justering = -0.5
        return {"antall": n, "riktige": riktige,
                "presisjon": round(presisjon, 2) if presisjon is not None else None,
                "justering": justering}

    # ---- oversikt --------------------------------------------------------
    def logg(self, antall: int = 40) -> list[dict]:
        navn = {e["kilde"]: e["navn"] for e in self.oppsett["enheter"]}
        rader = self.db.con.execute("SELECT * FROM lyd ORDER BY tid DESC, id DESC LIMIT ?", (antall,))
        return [{**dict(r), "enhet": navn.get(r["kilde"], r["kilde"])} for r in rader]

    def per_enhet(self, dager: int = 14) -> list[dict]:
        fra = til_iso(naa() - timedelta(days=dager))
        rader = self.db.con.execute(
            "SELECT kilde, COUNT(*) AS totalt, SUM(tolkning = 'avvist') AS avvist FROM lyd "
            "WHERE tid >= ? GROUP BY kilde ORDER BY totalt DESC", (fra,)).fetchall()
        navn = {e["kilde"]: e["navn"] for e in self.oppsett["enheter"]}
        return [{"kilde": r["kilde"], "enhet": navn.get(r["kilde"], r["kilde"]),
                 "totalt": r["totalt"], "avvist": r["avvist"] or 0} for r in rader]

    def oversikt(self) -> dict:
        """Det frontend trenger på forsiden."""
        o = self.oppsett
        siste = self.db.con.execute("SELECT * FROM lyd ORDER BY tid DESC, id DESC LIMIT 1").fetchone()
        return {
            "aktiv": o["aktiv"],
            "sted": self.sted(),
            "steder": [{"verdi": s, "navn": STED_NAVN[s]} for s in STEDER],
            "enheter": [{"kilde": e["kilde"], "navn": e["navn"], "rolle": e["rolle"]} for e in o["enheter"]],
            "forslag": self.forslag("venter"),
            "siste": dict(siste) if siste else None,
        }
