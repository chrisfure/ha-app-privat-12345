"""Pengeboka – all logikk. Bare regler og enkel statistikk, ingen AI.

Kort om tallene:
- Overføringer mellom egne kontoer (også skjulte) telles aldri som forbruk.
- Oversikten bruker bare kontoer som ikke er skjult.
- «Brukt» i en kategori = penger ut minus refusjoner inn.
"""
from __future__ import annotations

import calendar
import csv
import io
import os
import re
from collections import defaultdict
from datetime import date, datetime, timedelta
from statistics import median
from zoneinfo import ZoneInfo

import fil
import matplan
import regler
from db import Database, naa_iso

KONTOTYPER = {"bruk": "Brukskonto", "felles": "Felleskonto", "kreditt": "Kredittkort",
              "sparing": "Sparekonto", "lan": "Lån", "annet": "Annet"}
OVERFORING_DAGER = 4          # maks dager mellom de to halvdelene av en overføring
IMPORT_PAMINNELSE_DAGER = 35  # «på tide å importere» etter så mange dager


class Feil(Exception):
    pass


def kr(ore: int | float) -> str:
    """12345600 → «123 456 kr»"""
    n = round(ore / 100)
    return f"{n:,}".replace(",", " ").replace("-", "−") + " kr"


def _ym(d: str | date) -> str:
    return (d.isoformat() if isinstance(d, date) else d)[:7]


def _forrige_maned(ym: str, n: int = 1) -> str:
    y, m = map(int, ym.split("-"))
    m -= n
    while m < 1:
        m += 12
        y -= 1
    return f"{y:04d}-{m:02d}"


def _dager_i(ym: str) -> int:
    y, m = map(int, ym.split("-"))
    return calendar.monthrange(y, m)[1]


class Pengeboka:
    def __init__(self, db: Database, tz: str | None = None):
        self.db = db
        self.tz = ZoneInfo(tz or os.environ.get("TZ") or "Europe/Oslo")
        self._standard()

    def i_dag(self) -> date:
        return datetime.now(self.tz).date()

    # ------------------------------------------------------------ oppstart
    def _standard(self) -> None:
        if self.db.verdi("SELECT COUNT(*) FROM kategorier"):
            return
        for i, (navn, ikon, gruppe) in enumerate(regler.KATEGORIER):
            self.db.kjor("INSERT INTO kategorier(navn, ikon, gruppe, rekkefolge) VALUES(?,?,?,?)", (navn, ikon, gruppe, i))

    # ------------------------------------------------------------ kontoer
    def kontoer(self) -> list[dict]:
        rader = self.db.rader("""
            SELECT k.*, COUNT(t.id) AS antall, MIN(t.dato) AS fra, MAX(t.dato) AS til,
                   (SELECT MAX(i.tid) FROM importer i WHERE i.konto_id = k.id) AS sist_importert
            FROM kontoer k LEFT JOIN transaksjoner t ON t.konto_id = k.id
            GROUP BY k.id ORDER BY k.skjult, k.rekkefolge, k.id""")
        for r in rader:
            r["type_navn"] = KONTOTYPER.get(r["type"], r["type"])
            r["nummer_vis"] = fil.vis_nummer(r.get("nummer"))
        return rader

    def _sett_nummer(self, kid: int, nummer: str | None) -> None:
        nr = fil.kontonummer(nummer) if nummer else None
        if nummer and not nr:
            raise Feil("Kontonummeret må ha 11 siffer")
        if nr and self.db.verdi("SELECT id FROM kontoer WHERE nummer = ? AND id != ?", (nr, kid)):
            raise Feil("En annen konto har allerede det kontonummeret")
        self.db.kjor("UPDATE kontoer SET nummer = ? WHERE id = ?", (nr, kid))

    def lagre_konto(self, d: dict, kid: int | None = None) -> dict:
        navn = str(d.get("navn") or "").strip()[:60]
        typ = d.get("type") or "bruk"
        if typ not in KONTOTYPER:
            raise Feil("Ukjent kontotype")
        if kid is None:
            if not navn:
                raise Feil("Gi kontoen et navn")
            kid = self.db.kjor("INSERT INTO kontoer(navn, type, skjult, rekkefolge, opprettet) VALUES(?,?,?,?,?)",
                               (navn, typ, 1 if d.get("skjult") else 0,
                                (self.db.verdi("SELECT MAX(rekkefolge) FROM kontoer") or 0) + 1, naa_iso()))
            if d.get("nummer"):
                try:
                    self._sett_nummer(kid, d["nummer"])
                except Feil:
                    self.db.kjor("DELETE FROM kontoer WHERE id = ?", (kid,))
                    raise
        else:
            gml = self.db.rad("SELECT * FROM kontoer WHERE id = ?", (kid,))
            if not gml:
                raise Feil("Fant ikke kontoen")
            self.db.kjor("UPDATE kontoer SET navn = ?, type = ?, skjult = ? WHERE id = ?",
                         (navn or gml["navn"], typ, 1 if d.get("skjult", gml["skjult"]) else 0, kid))
            if "nummer" in d:
                self._sett_nummer(kid, d["nummer"])
            if typ != gml["type"] or ("nummer" in d and fil.kontonummer(d["nummer"]) != gml["nummer"]):
                self.finn_overforinger(nullstill=True)
        return next(k for k in self.kontoer() if k["id"] == kid)

    def slett_konto(self, kid: int) -> None:
        self.db.kjor("DELETE FROM kontoer WHERE id = ?", (kid,))
        self.finn_overforinger(nullstill=True)

    # ------------------------------------------------------------ kategorier
    def kategorier(self, alle: bool = True) -> list[dict]:
        sql = "SELECT * FROM kategorier" + ("" if alle else " WHERE skjult = 0") + " ORDER BY rekkefolge, id"
        return self.db.rader(sql)

    def _kat_id(self, navn: str) -> int | None:
        return self.db.verdi("SELECT id FROM kategorier WHERE navn = ?", (navn,))

    def lagre_kategori(self, d: dict, kid: int | None = None) -> dict:
        navn = str(d.get("navn") or "").strip()[:40]
        ikon = str(d.get("ikon") or "").strip()[:8] or "📦"
        gruppe = d.get("gruppe") or "utgift"
        if gruppe not in ("utgift", "inntekt", "sparing"):
            raise Feil("Ukjent gruppe")
        budsjett = d.get("budsjett")
        budsjett_ore = None if budsjett in (None, "") else int(round(float(str(budsjett).replace(",", ".").replace(" ", "")) * 100))
        if budsjett_ore is not None and budsjett_ore < 0:
            raise Feil("Budsjettet kan ikke være negativt")
        if kid is None:
            if not navn:
                raise Feil("Gi kategorien et navn")
            if self._kat_id(navn):
                raise Feil("Det finnes allerede en kategori med det navnet")
            kid = self.db.kjor("INSERT INTO kategorier(navn, ikon, gruppe, budsjett_ore, rekkefolge) VALUES(?,?,?,?,?)",
                               (navn, ikon, gruppe, budsjett_ore, (self.db.verdi("SELECT MAX(rekkefolge) FROM kategorier") or 0) + 1))
        else:
            gml = self.db.rad("SELECT * FROM kategorier WHERE id = ?", (kid,))
            if not gml:
                raise Feil("Fant ikke kategorien")
            if gml["gruppe"] == "overforing":
                raise Feil("Overføring kan ikke endres")
            if navn and navn != gml["navn"] and self._kat_id(navn):
                raise Feil("Det finnes allerede en kategori med det navnet")
            self.db.kjor("UPDATE kategorier SET navn = ?, ikon = ?, budsjett_ore = ?, skjult = ? WHERE id = ?",
                         (navn or gml["navn"], ikon if d.get("ikon") else gml["ikon"],
                          budsjett_ore if "budsjett" in d else gml["budsjett_ore"],
                          1 if d.get("skjult", gml["skjult"]) else 0, kid))
        return self.db.rad("SELECT * FROM kategorier WHERE id = ?", (kid,))

    def lagre_budsjett(self, budsjett: dict) -> None:
        """{kategori_id: kroner eller None}"""
        with self.db.transaksjon():
            for kid, kroner in budsjett.items():
                ore = None if kroner in (None, "") else int(round(float(str(kroner).replace(",", ".").replace(" ", "")) * 100))
                self.db.con.execute("UPDATE kategorier SET budsjett_ore = ? WHERE id = ? AND gruppe != 'overforing'",
                                    (ore if ore is None or ore >= 0 else None, int(kid)))

    # ------------------------------------------------------------ regler
    def regler(self) -> list[dict]:
        return self.db.rader("""
            SELECT r.*, k.navn AS kategori, k.ikon,
                   (SELECT COUNT(*) FROM transaksjoner t WHERE t.regel_id = r.id) AS treff
            FROM regler r JOIN kategorier k ON k.id = r.kategori_id ORDER BY r.monster""")

    def _egne_regler(self) -> list[dict]:
        return sorted(self.regler(), key=lambda r: -len(r["monster"]))

    def lag_regel(self, monster: str, kategori_id: int, av: str | None) -> dict:
        m = regler.rydd(monster) or monster.strip().lower()
        if len(m) < 2:
            raise Feil("Mønsteret er for kort")
        if not self.db.rad("SELECT id FROM kategorier WHERE id = ?", (kategori_id,)):
            raise Feil("Ukjent kategori")
        self.db.kjor("INSERT INTO regler(monster, kategori_id, laget_av, opprettet) VALUES(?,?,?,?) "
                     "ON CONFLICT(monster) DO UPDATE SET kategori_id = excluded.kategori_id, laget_av = excluded.laget_av",
                     (m, kategori_id, av, naa_iso()))
        self.kategoriser_alle()
        return self.db.rad("SELECT * FROM regler WHERE monster = ?", (m,))

    def slett_regel(self, rid: int) -> None:
        self.db.kjor("UPDATE transaksjoner SET kategori_id = NULL, kilde = NULL, regel_id = NULL WHERE regel_id = ?", (rid,))
        self.db.kjor("DELETE FROM regler WHERE id = ?", (rid,))
        self.kategoriser_alle()

    # ------------------------------------------------------------ import
    def _les(self, data: bytes, oppsett: dict | None) -> tuple[list, dict]:
        try:
            rader = fil.les(data)
            if not oppsett or not oppsett.get("kolonner"):
                oppsett = fil.gjett_oppsett(rader)
            return rader, oppsett
        except fil.Filfeil as e:
            raise Feil(str(e)) from None

    @staticmethod
    def _fingeravtrykk(tx: list[dict]) -> list[str]:
        """dato|beløp|tekst – med løpenummer når samme kjøp står flere ganger samme dag."""
        teller: dict[str, int] = defaultdict(int)
        ut = []
        for t in tx:
            grunn = f"{t['dato']}|{t['belop_ore']}|{regler.rydd(t['tekst'])}"
            teller[grunn] += 1
            ut.append(f"{grunn}#{teller[grunn]}")
        return ut

    def _gjett_konto(self, nummer: str | None, fa: list[str]) -> dict | None:
        """Hvilken konto filen hører til: kontonummeret, ellers transaksjoner som er importert før."""
        if nummer:
            k = self.db.rad("SELECT id FROM kontoer WHERE nummer = ?", (nummer,))
            if k:
                return {"id": k["id"], "grunn": "kontonummer"}
        if not fa:
            return None
        beste = None
        for k in self.db.rader("SELECT id, nummer FROM kontoer"):
            if nummer and k["nummer"]:
                continue  # en konto med et annet nummer kan ikke være denne
            fins = {r["fingeravtrykk"] for r in self.db.rader(
                "SELECT fingeravtrykk FROM transaksjoner WHERE konto_id = ?", (k["id"],))}
            treff = sum(1 for f in fa if f in fins)
            if treff and (beste is None or treff > beste[1]):
                beste = (k["id"], treff)
        if beste and beste[1] >= min(3, len(fa)) and beste[1] >= 0.2 * len(fa):
            return {"id": beste[0], "grunn": "tidligere"}
        return None

    def forhandsvis(self, data: bytes, konto_id: int | None, oppsett: dict | None = None, filnavn: str = "") -> dict:
        rader, oppsett = self._les(data, oppsett)
        svar = {"oppsett": oppsett, "overskrifter": fil.overskrifter(rader, oppsett),
                "radeksempel": [[str(x) for x in r] for r in rader[max(0, oppsett.get("overskrift", -1) + 1):][:5]]}
        try:
            tolket = fil.tolk_rader(rader, oppsett)
        except fil.Filfeil as e:
            return {**svar, "feil": str(e)}
        tx = tolket["transaksjoner"]
        if not tx:
            return {**svar, "feil": "Fant ingen transaksjoner med disse kolonnene. Sjekk valgene under."}
        fa = self._fingeravtrykk(tx)
        nummer = fil.finn_kontonummer(rader, tx, filnavn)
        gjettet = self._gjett_konto(nummer, fa)
        if not konto_id and gjettet:
            konto_id = gjettet["id"]
        fins = set()
        if konto_id:
            fins = {r["fingeravtrykk"] for r in self.db.rader(
                "SELECT fingeravtrykk FROM transaksjoner WHERE konto_id = ?", (konto_id,))}
        nye = sum(1 for f in fa if f not in fins)
        datoer = sorted(t["dato"] for t in tx)
        return {**svar, "antall": len(tx), "nye": nye, "duplikater": len(tx) - nye, "hoppet": tolket["hoppet"],
                "reservert": tolket.get("reservert", 0), "konto": gjettet, "konto_id": konto_id,
                "kontonummer": nummer, "kontonummer_vis": fil.vis_nummer(nummer),
                "kontotype": self._gjett_type(tx),
                "fra": datoer[0], "til": datoer[-1],
                "eksempel": [{**t, "motpart": regler.motpart(t["tekst"])} for t in tx[:6]],
                "sum_inn": sum(t["belop_ore"] for t in tx if t["belop_ore"] > 0),
                "sum_ut": -sum(t["belop_ore"] for t in tx if t["belop_ore"] < 0)}

    @staticmethod
    def _gjett_type(tx: list[dict]) -> str:
        """Grovt forslag til kontotype for en ny konto: mange kortkjøp = brukskonto, få store inn = sparing."""
        ut = [t for t in tx if t["belop_ore"] < 0]
        inn = [t for t in tx if t["belop_ore"] > 0]
        if tx and len(ut) >= 0.8 * len(tx) and any("innbetaling" in t["tekst"].lower() or "betaling" in t["tekst"].lower() for t in inn):
            if len(inn) <= max(2, len(tx) // 10):
                return "kreditt"
        if len(tx) <= 30 and len(ut) <= len(inn) and all(regler.ser_ut_som_overforing(t["tekst"]) or abs(t["belop_ore"]) >= 50000 for t in tx):
            return "sparing"
        return "bruk"

    def importer(self, data: bytes, filnavn: str, konto_id: int | None, oppsett: dict | None, av: str | None) -> dict:
        rader, oppsett = self._les(data, oppsett)
        try:
            tx = fil.tolk_rader(rader, oppsett)["transaksjoner"]
        except fil.Filfeil as e:
            raise Feil(str(e)) from None
        if not tx:
            raise Feil("Fant ingen transaksjoner i filen")
        nummer = fil.finn_kontonummer(rader, tx, filnavn)
        if not konto_id:
            gjettet = self._gjett_konto(nummer, self._fingeravtrykk(tx))
            konto_id = gjettet["id"] if gjettet else None
        konto = self.db.rad("SELECT * FROM kontoer WHERE id = ?", (konto_id,)) if konto_id else None
        if not konto:
            raise Feil("Velg hvilken konto filen gjelder")
        if nummer and konto["nummer"] and konto["nummer"] != nummer:
            raise Feil(f"Filen gjelder konto {fil.vis_nummer(nummer)}, men {konto['navn']} har {fil.vis_nummer(konto['nummer'])}")
        if nummer and not konto["nummer"] and not self.db.verdi("SELECT id FROM kontoer WHERE nummer = ?", (nummer,)):
            self.db.kjor("UPDATE kontoer SET nummer = ? WHERE id = ?", (nummer, konto_id))  # lær nummeret
        fa = self._fingeravtrykk(tx)
        datoer = sorted(t["dato"] for t in tx)
        nye = 0
        with self.db.transaksjon():
            iid = self.db.con.execute(
                "INSERT INTO importer(konto_id, filnavn, tid, av, fra, til) VALUES(?,?,?,?,?,?)",
                (konto_id, (filnavn or "")[:120], naa_iso(), av, datoer[0], datoer[-1])).lastrowid
            for t, f in zip(tx, fa):
                cur = self.db.con.execute(
                    "INSERT OR IGNORE INTO transaksjoner(konto_id, import_id, dato, belop_ore, tekst, motpart, motkonto, fingeravtrykk) "
                    "VALUES(?,?,?,?,?,?,?,?)",
                    (konto_id, iid, t["dato"], t["belop_ore"], t["tekst"][:300], regler.motpart(t["tekst"])[:80],
                     t.get("motkonto"), f))
                nye += cur.rowcount
            self.db.con.execute("UPDATE importer SET nye = ?, duplikater = ? WHERE id = ?", (nye, len(tx) - nye, iid))
        if nye == 0:
            self.db.kjor("DELETE FROM importer WHERE id = ?", (iid,))
        self.db.sett_innstilling("sist_oppsett", oppsett)
        self.finn_overforinger()
        self.kategoriser_alle()
        return {"nye": nye, "duplikater": len(tx) - nye, "fra": datoer[0], "til": datoer[-1], "konto_id": konto_id,
                "ukategorisert": self.db.verdi(
                    "SELECT COUNT(*) FROM transaksjoner WHERE import_id = ? AND kategori_id IS NULL", (iid,)) or 0}

    def importer_liste(self) -> list[dict]:
        return self.db.rader("""SELECT i.*, k.navn AS konto FROM importer i JOIN kontoer k ON k.id = i.konto_id
                                ORDER BY i.tid DESC LIMIT 30""")

    def angre_import(self, iid: int) -> int:
        n = self.db.verdi("SELECT COUNT(*) FROM transaksjoner WHERE import_id = ?", (iid,)) or 0
        self.db.kjor("DELETE FROM importer WHERE id = ?", (iid,))
        self.finn_overforinger(nullstill=True)
        return n

    # ------------------------------------------------------------ kategorisering
    def kategoriser_alle(self) -> None:
        """Gir kategori til alt som ikke er satt for hånd eller er en overføring."""
        egne = self._egne_regler()
        kat = {k["navn"]: k["id"] for k in self.kategorier()}
        rader = self.db.rader("SELECT id, tekst, belop_ore, kategori_id, kilde, regel_id FROM transaksjoner "
                              "WHERE kilde IS NULL OR kilde IN ('regel', 'kjent')")
        with self.db.transaksjon():
            for t in rader:
                navn, rid = regler.kategoriser(t["tekst"], t["belop_ore"], egne)
                kid = kat.get(navn) if navn else None
                kilde = ("regel" if rid else "kjent") if kid else None
                if (kid, kilde, rid) != (t["kategori_id"], t["kilde"], t["regel_id"]):
                    self.db.con.execute("UPDATE transaksjoner SET kategori_id = ?, kilde = ?, regel_id = ? WHERE id = ?",
                                        (kid, kilde, rid, t["id"]))

    def finn_overforinger(self, nullstill: bool = False) -> int:
        """Parer penger ut av én egen konto med samme beløp inn på en annen egen konto innen noen dager."""
        kontoer = self.db.rader("SELECT id, type, nummer FROM kontoer")
        kontotype = {k["id"]: k["type"] for k in kontoer}
        nummer_til = {k["nummer"]: k["id"] for k in kontoer if k["nummer"]}
        kat = {k["navn"]: k["id"] for k in self.kategorier()}

        def kategorier_for(fra_t, til_t):
            # Penger til sparing/lån teller som sparing/lån; uttak fra sparing gir «negativ sparing».
            ut_kat, inn_kat = regler.OVERFORING, regler.OVERFORING
            if til_t == "sparing" and fra_t != "sparing":
                ut_kat = regler.SPARING
            elif til_t == "lan" and fra_t != "lan":
                ut_kat = regler.LAN
            elif fra_t == "sparing" and til_t != "sparing":
                inn_kat = regler.SPARING
            return ut_kat, inn_kat
        with self.db.transaksjon():
            if nullstill:
                self.db.con.execute("UPDATE transaksjoner SET par_id = NULL, kategori_id = NULL, kilde = NULL "
                                    "WHERE kilde = 'overforing'")
            rader = [dict(r) for r in self.db.con.execute(
                "SELECT id, konto_id, dato, belop_ore, tekst, motkonto FROM transaksjoner "
                "WHERE par_id IS NULL AND ikke_overforing = 0 AND (kilde IS NULL OR kilde IN ('regel', 'kjent', 'overforing')) "
                "ORDER BY dato, id").fetchall()]
            inn: dict[int, list[dict]] = defaultdict(list)
            for r in rader:
                if r["belop_ore"] > 0:
                    inn[r["belop_ore"]].append(r)
            brukt: set[int] = set()
            par = 0
            for ut in (r for r in rader if r["belop_ore"] < 0):
                d0 = date.fromisoformat(ut["dato"])
                kandidater = []
                for m in inn.get(-ut["belop_ore"], []):
                    if m["id"] in brukt or m["konto_id"] == ut["konto_id"]:
                        continue
                    avstand = abs((date.fromisoformat(m["dato"]) - d0).days)
                    if avstand <= OVERFORING_DAGER:
                        hint = regler.ser_ut_som_overforing(ut["tekst"]) or regler.ser_ut_som_overforing(m["tekst"])
                        sikker = nummer_til.get(ut["motkonto"]) == m["konto_id"] or nummer_til.get(m["motkonto"]) == ut["konto_id"]
                        kandidater.append((avstand - (0.5 if hint else 0) - (10 if sikker else 0), m["id"], m))
                if not kandidater:
                    continue
                _, _, m = min(kandidater, key=lambda x: (x[0], x[1]))
                brukt.add(m["id"])
                brukt.add(ut["id"])
                ut_kat, inn_kat = kategorier_for(kontotype.get(ut["konto_id"]), kontotype.get(m["konto_id"]))
                self.db.con.execute("UPDATE transaksjoner SET par_id = ?, kategori_id = ?, kilde = 'overforing', regel_id = NULL "
                                    "WHERE id = ?", (m["id"], kat.get(ut_kat), ut["id"]))
                self.db.con.execute("UPDATE transaksjoner SET par_id = ?, kategori_id = ?, kilde = 'overforing', regel_id = NULL "
                                    "WHERE id = ?", (ut["id"], kat.get(inn_kat), m["id"]))
                par += 1
            # Filen sier at pengene gikk til/kom fra en av deres egne kontoer, men den andre halvdelen
            # er ikke importert (ennå): da er det likevel en overføring.
            for r in rader:
                if r["id"] in brukt or not r["motkonto"]:
                    continue
                annen = nummer_til.get(r["motkonto"])
                if not annen or annen == r["konto_id"]:
                    if self.db.con.execute("SELECT kilde FROM transaksjoner WHERE id = ?", (r["id"],)).fetchone()[0] == "overforing":
                        self.db.con.execute("UPDATE transaksjoner SET kategori_id = NULL, kilde = NULL WHERE id = ?", (r["id"],))
                    continue
                if r["belop_ore"] < 0:
                    navn = kategorier_for(kontotype.get(r["konto_id"]), kontotype.get(annen))[0]
                else:
                    navn = kategorier_for(kontotype.get(annen), kontotype.get(r["konto_id"]))[1]
                self.db.con.execute("UPDATE transaksjoner SET kategori_id = ?, kilde = 'overforing', regel_id = NULL "
                                    "WHERE id = ?", (kat.get(navn), r["id"]))
        if nullstill:
            self.kategoriser_alle()  # det som ikke lenger er overføringer, trenger kategori igjen
        return par

    # ------------------------------------------------------------ transaksjoner
    def _synlige(self) -> list[int]:
        return [r["id"] for r in self.db.rader("SELECT id FROM kontoer WHERE skjult = 0")]

    def transaksjoner(self, q: dict) -> dict:
        hvor, args = [], []
        if q.get("konto"):
            hvor.append("t.konto_id = ?")
            args.append(int(q["konto"]))
        elif not q.get("skjulte"):
            hvor.append("k.skjult = 0")
        if q.get("maned"):
            hvor.append("substr(t.dato, 1, 7) = ?")
            args.append(q["maned"])
        if q.get("kategori") == "ingen":
            hvor.append("t.kategori_id IS NULL")
        elif q.get("kategori"):
            hvor.append("t.kategori_id = ?")
            args.append(int(q["kategori"]))
        if q.get("motpart"):
            hvor.append("t.motpart = ?")
            args.append(q["motpart"])
        if not q.get("overforinger") and q.get("kategori") in (None, "", "ingen"):
            hvor.append("(t.kilde IS NULL OR t.kilde != 'overforing' OR c.gruppe != 'overforing')")
        # Kvittering fra Matplan: «har» = koblet, «mangler» = dagligvarekjøp i perioden Matplan har kvitteringer for
        forste_kv = self._forste_kvittering()
        if q.get("kvittering") == "har":
            hvor.append("kk.matplan_id IS NOT NULL")
        elif q.get("kvittering") == "mangler":
            hvor.append("kk.matplan_id IS NULL AND t.belop_ore < 0 AND c.navn = 'Dagligvarer' AND t.dato >= ?")
            args.append(forste_kv or "9999")
        sok = str(q.get("sok") or "").strip().lower()
        if sok:
            hvor.append("(lower(t.tekst) LIKE ? OR lower(t.motpart) LIKE ? OR lower(coalesce(t.notat,'')) LIKE ?)")
            args += [f"%{sok}%"] * 3
        sql_hvor = (" WHERE " + " AND ".join(hvor)) if hvor else ""
        grense = min(int(q.get("grense") or 300), 2000)
        fra = """FROM transaksjoner t JOIN kontoer k ON k.id = t.konto_id LEFT JOIN kategorier c ON c.id = t.kategori_id
                 LEFT JOIN kvittering_kobling kk ON kk.transaksjon_id = t.id"""
        rader = self.db.rader(f"""
            SELECT t.id, t.konto_id, t.dato, t.belop_ore, t.tekst, t.motpart, t.kategori_id, t.kilde, t.par_id,
                   t.notat, t.endret_av, k.navn AS konto, k.skjult AS konto_skjult, c.navn AS kategori, c.ikon, c.gruppe,
                   kk.matplan_id AS kvittering
            {fra} {sql_hvor} ORDER BY t.dato DESC, t.id DESC LIMIT ?""", (*args, grense + 1))
        sum_ = self.db.verdi(f"SELECT COALESCE(SUM(t.belop_ore), 0) {fra} {sql_hvor}", args)
        for r in rader:
            # Vis «mangler kvittering» bare der Matplan faktisk har kvitteringer fra den perioden
            r["kvittering_mangler"] = bool(forste_kv and not r["kvittering"] and r["belop_ore"] < 0
                                           and r["kategori"] == "Dagligvarer" and r["dato"] >= forste_kv)
        return {"transaksjoner": rader[:grense], "flere": len(rader) > grense, "sum": sum_,
                "matplan": bool(forste_kv)}

    def _forste_kvittering(self) -> str | None:
        if not matplan.tilkoblet(self.db):
            return None
        return self.db.verdi("SELECT MIN(dato) FROM kvitteringer")

    def transaksjon(self, tid: int) -> dict:
        t = self.db.rad("""SELECT t.*, k.navn AS konto, c.navn AS kategori, c.ikon, c.gruppe
                           FROM transaksjoner t JOIN kontoer k ON k.id = t.konto_id
                           LEFT JOIN kategorier c ON c.id = t.kategori_id WHERE t.id = ?""", (tid,))
        if not t:
            raise Feil("Fant ikke transaksjonen")
        if t["par_id"]:
            t["par"] = self.db.rad("SELECT t.dato, t.belop_ore, k.navn AS konto FROM transaksjoner t "
                                   "JOIN kontoer k ON k.id = t.konto_id WHERE t.id = ?", (t["par_id"],))
        t["like"] = self.db.verdi("SELECT COUNT(*) FROM transaksjoner WHERE motpart = ? AND id != ?",
                                  (t["motpart"], tid)) or 0
        t["kvittering"] = self.db.rad("""SELECT kv.* FROM kvittering_kobling kk JOIN kvitteringer kv ON kv.matplan_id = kk.matplan_id
                                         WHERE kk.transaksjon_id = ?""", (tid,)) if matplan.tilkoblet(self.db) else None
        forste = self._forste_kvittering()
        t["kvittering_mangler"] = bool(forste and not t["kvittering"] and t["belop_ore"] < 0
                                       and t["kategori"] == "Dagligvarer" and t["dato"] >= forste)
        # «Gjelder alle» er på som standard – men ikke for generiske tekster som «Overføring Innland»
        t["regel_anbefalt"] = bool(t["like"]) and not regler.ser_ut_som_overforing(t["tekst"])
        t["regelforslag"] = regler.rydd(t["motpart"]) if not t["motpart"].lower().startswith("vipps") \
            else regler.rydd(t["tekst"])
        return t

    def endre_transaksjon(self, tid: int, d: dict, av: str | None) -> dict:
        t = self.transaksjon(tid)
        if "notat" in d:
            self.db.kjor("UPDATE transaksjoner SET notat = ?, endret_av = ?, endret = ? WHERE id = ?",
                         (str(d["notat"] or "").strip()[:300] or None, av, naa_iso(), tid))
        if d.get("ikke_overforing") and t["par_id"]:
            for x in (tid, t["par_id"]):
                self.db.kjor("UPDATE transaksjoner SET par_id = NULL, ikke_overforing = 1, kategori_id = NULL, kilde = NULL "
                             "WHERE id = ?", (x,))
            self.kategoriser_alle()
        if "kategori_id" in d:
            kid = d["kategori_id"]
            if kid in (None, ""):
                self.db.kjor("UPDATE transaksjoner SET kategori_id = NULL, kilde = NULL, regel_id = NULL, endret_av = ?, "
                             "endret = ? WHERE id = ?", (av, naa_iso(), tid))
                self.kategoriser_alle()
            else:
                kid = int(kid)
                k = self.db.rad("SELECT * FROM kategorier WHERE id = ?", (kid,))
                if not k:
                    raise Feil("Ukjent kategori")
                if d.get("regel"):
                    monster = str(d.get("monster") or t["regelforslag"]).strip()
                    self.lag_regel(monster, kid, av)
                if t["par_id"] and k["gruppe"] not in ("overforing", "sparing") and not d.get("ikke_overforing"):
                    # En overføring som faktisk var et kjøp: løs opp paret
                    for x in (tid, t["par_id"]):
                        self.db.kjor("UPDATE transaksjoner SET par_id = NULL, ikke_overforing = 1 WHERE id = ?", (x,))
                    other = self.db.rad("SELECT kilde FROM transaksjoner WHERE id = ?", (t["par_id"],))
                    if other and other["kilde"] == "overforing":
                        self.db.kjor("UPDATE transaksjoner SET kategori_id = NULL, kilde = NULL WHERE id = ?", (t["par_id"],))
                self.db.kjor("UPDATE transaksjoner SET kategori_id = ?, kilde = 'manuell', regel_id = NULL, "
                             "endret_av = ?, endret = ? WHERE id = ?", (kid, av, naa_iso(), tid))
                self.kategoriser_alle()
        return self.transaksjon(tid)

    # ------------------------------------------------------------ måned og budsjett
    def _maned_tall(self, ym: str, til_dag: int | None = None) -> dict[int | None, int]:
        """Netto per kategori (øre, fortegn som i banken) for synlige kontoer, uten rene overføringer."""
        args: list = [ym]
        ekstra = ""
        if til_dag:
            ekstra = " AND t.dato <= ?"
            args.append(f"{ym}-{til_dag:02d}")
        rader = self.db.rader(f"""
            SELECT t.kategori_id, SUM(t.belop_ore) AS sum
            FROM transaksjoner t JOIN kontoer k ON k.id = t.konto_id LEFT JOIN kategorier c ON c.id = t.kategori_id
            WHERE k.skjult = 0 AND substr(t.dato, 1, 7) = ? {ekstra}
              AND (c.gruppe IS NULL OR c.gruppe != 'overforing')
            GROUP BY t.kategori_id""", args)
        return {r["kategori_id"]: r["sum"] for r in rader}

    def _ukategorisert(self, ym: str) -> tuple[int, int]:
        r = self.db.rad("""SELECT COALESCE(SUM(CASE WHEN belop_ore > 0 THEN belop_ore END), 0) AS inn,
                                  COALESCE(SUM(CASE WHEN belop_ore < 0 THEN -belop_ore END), 0) AS ut
                           FROM transaksjoner t JOIN kontoer k ON k.id = t.konto_id
                           WHERE k.skjult = 0 AND t.kategori_id IS NULL AND substr(t.dato, 1, 7) = ?""", (ym,))
        return r["inn"], r["ut"]

    def maneder(self) -> list[str]:
        r = self.db.rad("SELECT MIN(dato) AS fra, MAX(dato) AS til FROM transaksjoner")
        if not r or not r["fra"]:
            return [_ym(self.i_dag())]
        ut, ym, slutt = [], _ym(r["fra"]), max(_ym(r["til"]), _ym(self.i_dag()))
        while ym <= slutt:
            ut.append(ym)
            y, m = map(int, ym.split("-"))
            ym = f"{y + (m == 12):04d}-{m % 12 + 1:02d}"
        return ut

    def snitt(self, ym: str, n: int = 3) -> dict[int, float]:
        """Snitt brukt per utgiftskategori de n hele månedene før ym (bare måneder med data teller)."""
        sum_: dict[int, int] = defaultdict(int)
        med_data = 0
        for i in range(1, n + 1):
            m = _forrige_maned(ym, i)
            tall = self._maned_tall(m)
            if not tall:
                continue
            med_data += 1
            for kid, s in tall.items():
                if kid is not None:
                    sum_[kid] += s
        return {kid: -s / med_data for kid, s in sum_.items()} if med_data else {}

    def _andel_brukt_innen(self, kid: int, ym: str, dag: int, n: int = 3) -> float | None:
        """Hvor stor del av en kategoris månedsforbruk som pleier å være brukt innen dag X."""
        andeler = []
        for i in range(1, n + 1):
            m = _forrige_maned(ym, i)
            hele = self.db.verdi("""SELECT SUM(t.belop_ore) FROM transaksjoner t JOIN kontoer k ON k.id = t.konto_id
                                    WHERE k.skjult = 0 AND t.kategori_id = ? AND substr(t.dato, 1, 7) = ?""", (kid, m))
            if not hele or hele >= 0:
                continue
            dag_m = min(dag, _dager_i(m))
            innen = self.db.verdi("""SELECT SUM(t.belop_ore) FROM transaksjoner t JOIN kontoer k ON k.id = t.konto_id
                                     WHERE k.skjult = 0 AND t.kategori_id = ? AND t.dato >= ? AND t.dato <= ?""",
                                  (kid, f"{m}-01", f"{m}-{dag_m:02d}")) or 0
            andeler.append(max(0.0, min(1.0, innen / hele)))
        return sum(andeler) / len(andeler) if andeler else None

    def maned(self, ym: str | None = None) -> dict:
        i_dag = self.i_dag()
        ym = ym or _ym(i_dag)
        if not re.fullmatch(r"\d{4}-\d{2}", ym):
            raise Feil("Ugyldig måned")
        forste_kv = self._forste_kvittering()
        tall = self._maned_tall(ym)
        kats = self.kategorier()
        snitt = self.snitt(ym)
        faste = {f["motpart"] for f in self.faste(intern=True)}
        pagar = ym == _ym(i_dag)
        dag, dager = (i_dag.day, _dager_i(ym)) if pagar else (_dager_i(ym), _dager_i(ym))
        inn = ut = sparing = 0
        rader = []
        for k in kats:
            s = tall.get(k["id"], 0)
            if k["gruppe"] == "inntekt":
                inn += s
            elif k["gruppe"] == "sparing":
                sparing += -s
            elif k["gruppe"] == "utgift":
                ut += -s
            if k["gruppe"] != "utgift":
                continue
            brukt = -s
            prognose = None
            if pagar:
                if snitt.get(k["id"], 0) > 0:
                    andel = self._andel_brukt_innen(k["id"], ym, dag)
                    andel = dag / dager if andel is None else andel
                    prognose = max(brukt, brukt + snitt[k["id"]] * (1 - andel))
                else:
                    prognose = brukt
            if brukt == 0 and not k["budsjett_ore"] and not snitt.get(k["id"]) and k["skjult"]:
                continue
            kv = None
            if k["navn"] == "Dagligvarer" and forste_kv:
                kv = self.db.rad("""SELECT COUNT(*) AS av, COUNT(kk.matplan_id) AS har
                    FROM transaksjoner t JOIN kontoer ko ON ko.id = t.konto_id
                    LEFT JOIN kvittering_kobling kk ON kk.transaksjon_id = t.id
                    WHERE ko.skjult = 0 AND t.kategori_id = ? AND t.belop_ore < 0 AND substr(t.dato, 1, 7) = ? AND t.dato >= ?""",
                                 (k["id"], ym, forste_kv))
            rader.append({"kvitteringer": kv, "id": k["id"], "navn": k["navn"], "ikon": k["ikon"], "brukt": brukt, "budsjett": k["budsjett_ore"],
                          "snitt": round(snitt.get(k["id"], 0)), "prognose": round(prognose) if prognose is not None else None,
                          "skjult": k["skjult"]})
        ukat_inn, ukat_ut = self._ukategorisert(ym)
        inn += ukat_inn
        ut += ukat_ut
        faste_sum = -(self.db.verdi(f"""
            SELECT COALESCE(SUM(t.belop_ore), 0) FROM transaksjoner t JOIN kontoer k ON k.id = t.konto_id
            LEFT JOIN kategorier c ON c.id = t.kategori_id
            WHERE k.skjult = 0 AND substr(t.dato, 1, 7) = ? AND t.belop_ore < 0 AND (c.gruppe IS NULL OR c.gruppe = 'utgift')
              AND t.motpart IN ({','.join('?' * len(faste)) or "''"})""", (ym, *faste)) or 0)
        budsjett_sum = sum(r["budsjett"] or 0 for r in rader)
        rader.sort(key=lambda r: (-(r["brukt"] or 0)))
        return {
            "maned": ym, "pagar": pagar, "dag": dag, "dager": dager,
            "inn": inn, "ut": ut, "sparing": sparing, "igjen": inn - ut - sparing, "faste": faste_sum,
            "ukategorisert": {"inn": ukat_inn, "ut": ukat_ut,
                              "antall": self.db.verdi("""SELECT COUNT(*) FROM transaksjoner t JOIN kontoer k ON k.id = t.konto_id
                                                         WHERE k.skjult = 0 AND t.kategori_id IS NULL AND substr(t.dato,1,7) = ?""", (ym,)) or 0},
            "budsjett_sum": budsjett_sum,
            "prognose_ut": round(sum((r["prognose"] if r["prognose"] is not None else r["brukt"]) for r in rader) + ukat_ut) if pagar else None,
            "kategorier": rader,
        }

    def budsjett(self) -> dict:
        ym = _ym(self.i_dag())
        snitt = self.snitt(ym)
        kats = [k for k in self.kategorier() if k["gruppe"] != "overforing"]
        for k in kats:
            k["snitt"] = round(snitt.get(k["id"], 0)) if k["gruppe"] == "utgift" else None
        return {"kategorier": kats, "maneder_grunnlag": sum(
            1 for i in range(1, 4) if self._maned_tall(_forrige_maned(ym, i)))}

    def foresla_budsjett(self) -> dict[int, int]:
        """Snittet av de tre siste hele månedene, rundet opp til nærmeste 100 kr (500 kr over 5000)."""
        snitt = self.snitt(_ym(self.i_dag()))
        ut = {}
        for k in self.kategorier():
            if k["gruppe"] != "utgift" or snitt.get(k["id"], 0) <= 0:
                continue
            kroner = snitt[k["id"]] / 100
            steg = 500 if kroner > 5000 else 100
            ut[k["id"]] = int(-(-kroner // steg) * steg)
        return ut

    # ------------------------------------------------------------ faste trekk
    def faste(self, intern: bool = False) -> list[dict]:
        """Finner abonnementer og regninger: samme mottaker, jevnt mellomrom, omtrent samme beløp."""
        i_dag = self.i_dag()
        fra = (i_dag - timedelta(days=400)).isoformat()
        merk = self.db.merknader()
        rader = self.db.rader("""
            SELECT t.motpart, t.dato, t.belop_ore, t.kategori_id, c.navn AS kategori, c.ikon
            FROM transaksjoner t JOIN kontoer k ON k.id = t.konto_id LEFT JOIN kategorier c ON c.id = t.kategori_id
            WHERE k.skjult = 0 AND t.belop_ore < 0 AND t.dato >= ? AND (c.gruppe IS NULL OR c.gruppe IN ('utgift'))
            ORDER BY t.dato""", (fra,))
        per: dict[str, list[dict]] = defaultdict(list)
        for r in rader:
            per[r["motpart"]].append(r)
        forste_data = self.db.verdi("""SELECT MIN(t.dato) FROM transaksjoner t JOIN kontoer k ON k.id = t.konto_id
                                       WHERE k.skjult = 0""")
        forste_data = date.fromisoformat(forste_data) if forste_data else i_dag
        ut = []
        for navn, liste in per.items():
            valg = merk.get(f"fast:{navn}")
            if valg == "nei" or navn.lower().startswith("vipps") and valg != "ja":
                continue
            # Slå sammen trekk samme dag (f.eks. to linjer på samme regning)
            dager: dict[str, int] = defaultdict(int)
            for r in liste:
                dager[r["dato"]] += -r["belop_ore"]
            datoer = sorted(dager)
            if len(datoer) < 3 and valg != "ja":
                continue
            d = [date.fromisoformat(x) for x in datoer]
            intervaller = [(b - a).days for a, b in zip(d, d[1:])]
            if not intervaller:
                continue
            mid = median(intervaller)
            if 25 <= mid <= 35:
                hyppighet, lengde = "måned", 30.4
            elif 6 <= mid <= 8:
                hyppighet, lengde = "uke", 7
            elif 80 <= mid <= 100:
                hyppighet, lengde = "kvartal", 91
            elif 350 <= mid <= 380:
                hyppighet, lengde = "år", 365
            else:
                if valg != "ja":
                    continue
                hyppighet, lengde = "uregelmessig", mid
            jevn = sum(1 for x in intervaller if abs(x - lengde) <= max(5, lengde * 0.2)) / len(intervaller)
            if jevn < 0.7 and valg != "ja":
                continue
            belop = [dager[x] for x in datoer]
            typisk = median(belop[-6:])
            avvik = median(abs(b - typisk) for b in belop[-6:]) / typisk if typisk else 1
            fast_belop = avvik <= 0.08
            if not fast_belop and hyppighet == "uke" and valg != "ja":
                continue  # ukentlige butikkbesøk er ikke et abonnement
            if not fast_belop and avvik > 0.6 and valg != "ja":
                continue
            # Ukentlige dagligvarekjøp o.l. hører ikke hjemme her
            if hyppighet == "uke" and liste[-1]["kategori"] in ("Dagligvarer", "Mat ute og kos") and valg != "ja":
                continue
            siste = d[-1]
            neste = siste + timedelta(days=round(lengde))
            forrige_typisk = median(belop[-7:-1]) if len(belop) >= 3 else None
            endring = None
            if forrige_typisk and len(belop) >= 3:
                stabil_for = median(abs(b - forrige_typisk) for b in belop[-7:-1]) / forrige_typisk <= 0.05
                diff = belop[-1] - forrige_typisk
                if stabil_for and abs(diff) >= 1000 and abs(diff) / forrige_typisk >= 0.04:
                    endring = {"fra": round(forrige_typisk), "til": belop[-1]}
            ut.append({
                "motpart": navn, "kategori": liste[-1]["kategori"], "ikon": liste[-1]["ikon"],
                "hyppighet": hyppighet, "typisk": round(typisk), "fast_belop": fast_belop,
                "per_maned": round(typisk * 30.4 / lengde), "siste": siste.isoformat(), "siste_belop": belop[-1],
                "neste": neste.isoformat(), "antall": len(datoer), "forst": datoer[0],
                "endring": endring, "bekreftet": valg == "ja",
                # «Ny» bare når vi har data fra før uten dette trekket – ellers er alt nytt etter første import
                "ny": (i_dag - d[0]).days <= 100 and (d[0] - forste_data).days >= 45,
                "uteblitt": (i_dag - neste).days > max(10, lengde * 0.3),
            })
        ut.sort(key=lambda f: (f["uteblitt"], -f["per_maned"]))
        return ut

    def merk_fast(self, motpart: str, valg: str | None) -> None:
        if valg not in ("ja", "nei", None):
            raise Feil("Ugyldig valg")
        self.db.merk(f"fast:{motpart}", valg)

    # ------------------------------------------------------------ trenger dere
    def avvik(self, dager: int = 45) -> list[dict]:
        """Uvanlig store beløp: mer enn dobbelt så mye som vanlig hos samme mottaker, eller store engangsbeløp."""
        i_dag = self.i_dag()
        nylige = self.db.rader("""
            SELECT t.id, t.dato, t.belop_ore, t.motpart, c.navn AS kategori
            FROM transaksjoner t JOIN kontoer k ON k.id = t.konto_id LEFT JOIN kategorier c ON c.id = t.kategori_id
            WHERE k.skjult = 0 AND t.belop_ore < 0 AND t.dato >= ? AND (c.gruppe IS NULL OR c.gruppe = 'utgift')""",
                               ((i_dag - timedelta(days=dager)).isoformat(),))
        ut = []
        for t in nylige:
            hist = [-r["belop_ore"] for r in self.db.rader(
                "SELECT belop_ore FROM transaksjoner WHERE motpart = ? AND belop_ore < 0 AND dato < ? ORDER BY dato DESC LIMIT 12",
                (t["motpart"], t["dato"]))]
            belop = -t["belop_ore"]
            if len(hist) >= 3:
                vanlig = median(hist)
                if belop > 2 * vanlig and belop - vanlig >= 100000:
                    ut.append({**t, "vanlig": round(vanlig), "grunn": "storre"})
            elif not hist and belop >= 500000:
                ut.append({**t, "vanlig": None, "grunn": "stort"})
        return ut

    def trenger(self) -> list[dict]:
        """Det dere bør se på. Tom liste = alt i orden."""
        merk = self.db.merknader()
        i_dag = self.i_dag()
        ym = _ym(i_dag)
        ut = []
        n = self.db.verdi("""SELECT COUNT(*) FROM transaksjoner t JOIN kontoer k ON k.id = t.konto_id
                             WHERE k.skjult = 0 AND t.kategori_id IS NULL""") or 0
        if n:
            ut.append({"nokkel": None, "type": "ukategorisert", "antall": n,
                       "tekst": f"{n} {'transaksjon' if n == 1 else 'transaksjoner'} uten kategori"})
        for f in self.faste(intern=True):
            if f["endring"]:
                k = f"pris:{f['motpart']}:{f['siste']}"
                if k not in merk:
                    ret = "økt" if f["endring"]["til"] > f["endring"]["fra"] else "satt ned"
                    ut.append({"nokkel": k, "type": "pris", "motpart": f["motpart"],
                               "tekst": f"{f['motpart']} har {ret} prisen fra {kr(f['endring']['fra'])} til {kr(f['endring']['til'])}"})
            if f["ny"] and not f["bekreftet"]:
                k = f"ny:{f['motpart']}"
                if k not in merk:
                    ut.append({"nokkel": k, "type": "ny_fast", "motpart": f["motpart"],
                               "tekst": f"Nytt fast trekk: {f['motpart']}, ca. {kr(f['typisk'])} per {f['hyppighet']}"})
        for a in self.avvik():
            k = f"avvik:{a['id']}"
            if k in merk:
                continue
            tekst = (f"Uvanlig stort beløp hos {a['motpart']}: {kr(-a['belop_ore'])} (vanligvis {kr(a['vanlig'])})"
                     if a["vanlig"] else f"Stort beløp: {kr(-a['belop_ore'])} hos {a['motpart']}")
            ut.append({"nokkel": k, "type": "avvik", "id": a["id"], "tekst": tekst, "dato": a["dato"]})
        m = self.maned(ym)
        for kat in m["kategorier"]:
            b = kat["budsjett"]
            if not b:
                continue
            if kat["brukt"] > b:
                k = f"over:{kat['id']}:{ym}"
                if k not in merk:
                    ut.append({"nokkel": k, "type": "over", "kategori_id": kat["id"],
                               "tekst": f"{kat['ikon']} {kat['navn']} er {kr(kat['brukt'] - b)} over budsjett"})
            elif kat["prognose"] and kat["prognose"] > b * 1.15 and kat["prognose"] - b >= 50000 and m["dag"] >= 10:
                # Bare tydelige tilfeller – små avvik fra prognosen er støy
                k = f"kurs:{kat['id']}:{ym}"
                if k not in merk:
                    ut.append({"nokkel": k, "type": "kurs", "kategori_id": kat["id"],
                               "tekst": f"{kat['ikon']} {kat['navn']} ligger an til ca. {kr(kat['prognose'])} – budsjett {kr(b)}"})
        for konto in self.kontoer():
            if konto["skjult"] or not konto["sist_importert"]:
                continue
            siden = (i_dag - date.fromisoformat((konto["til"] or konto["sist_importert"])[:10])).days
            if siden > IMPORT_PAMINNELSE_DAGER:
                k = f"import:{konto['id']}:{ym}"
                if k not in merk:
                    ut.append({"nokkel": k, "type": "import", "konto_id": konto["id"],
                               "tekst": f"{konto['navn']}: siste transaksjon er {siden} dager gammel – på tide å importere"})
        return ut

    def avvis(self, nokkel: str) -> None:
        if not nokkel or len(nokkel) > 200:
            raise Feil("Ugyldig")
        self.db.merk(nokkel, "sett")

    # ------------------------------------------------------------ samlet
    def oversikt(self, ym: str | None = None) -> dict:
        return {"maned": self.maned(ym), "trenger": self.trenger(), "maneder": self.maneder(),
                "kontoer": self.kontoer(), "har_data": bool(self.db.verdi("SELECT COUNT(*) FROM transaksjoner"))}

    def eksport_csv(self) -> str:
        buf = io.StringIO()
        w = csv.writer(buf, delimiter=";")
        w.writerow(["Dato", "Konto", "Mottaker", "Tekst", "Beløp", "Kategori", "Notat"])
        for r in self.db.rader("""SELECT t.dato, k.navn AS konto, t.motpart, t.tekst, t.belop_ore, c.navn AS kategori, t.notat
                                  FROM transaksjoner t JOIN kontoer k ON k.id = t.konto_id
                                  LEFT JOIN kategorier c ON c.id = t.kategori_id ORDER BY t.dato, t.id"""):
            w.writerow([r["dato"], r["konto"], r["motpart"], r["tekst"], f"{r['belop_ore'] / 100:.2f}".replace(".", ","),
                        r["kategori"] or "", r["notat"] or ""])
        return buf.getvalue()
