"""Lokal lagring i SQLite. Alle tider lagres i UTC (ISO 8601).

Ingen personlige opplysninger ligger i koden: barn, legemidler og alle
registreringer finnes bare i databasen under /data.
"""
from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

UTC = timezone.utc

SKJEMA = """
CREATE TABLE IF NOT EXISTS barn (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    navn        TEXT NOT NULL,
    farge       TEXT NOT NULL DEFAULT 'lilla',
    fodselsdato TEXT,                    -- YYYY-MM-DD (eller termin)
    vekt_kg     REAL,
    aktiv       INTEGER NOT NULL DEFAULT 1,
    rekkefolge  INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS legemidler (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    navn        TEXT NOT NULL,
    virkestoff  TEXT NOT NULL,           -- døgndose summeres per virkestoff
    form        TEXT NOT NULL DEFAULT 'annet', -- mikstur | tablett | stikkpille | annet
    mg_per_ml   REAL,                    -- for mikstur: registrer i ml, lagres som mg
    arkivert    INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS barn_legemiddel (
    barn_id        INTEGER NOT NULL REFERENCES barn(id) ON DELETE CASCADE,
    legemiddel_id  INTEGER NOT NULL REFERENCES legemidler(id) ON DELETE CASCADE,
    aktiv          INTEGER NOT NULL DEFAULT 1,
    standard_mg    REAL,
    min_intervall_t REAL,                -- timer mellom doser
    maks_dogn_mg   REAL,                 -- maks per døgn (rullerende 24 t)
    kur_doser_dag  INTEGER,              -- kur: planlagte doser per dag
    kur_til        TEXT,                 -- kur: siste dag (YYYY-MM-DD)
    PRIMARY KEY (barn_id, legemiddel_id)
);
CREATE TABLE IF NOT EXISTS episoder (
    id       INTEGER PRIMARY KEY AUTOINCREMENT,
    barn_id  INTEGER NOT NULL REFERENCES barn(id) ON DELETE CASCADE,
    navn     TEXT,
    start    TEXT NOT NULL,
    slutt    TEXT NOT NULL,
    avsluttet INTEGER NOT NULL DEFAULT 0,  -- «frisk igjen» trykket
    notat    TEXT
);
CREATE TABLE IF NOT EXISTS registreringer (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    barn_id       INTEGER REFERENCES barn(id) ON DELETE CASCADE,  -- NULL = ukjent (import)
    tid           TEXT NOT NULL,
    temp          REAL,
    temp_metode   TEXT,                 -- ore | munn | panne | endetarm | arm | notat
    legemiddel_id INTEGER REFERENCES legemidler(id),
    dose_mg       REAL,
    dose_ml       REAL,
    symptomer     TEXT NOT NULL DEFAULT '[]',
    notat         TEXT,
    episode_id    INTEGER REFERENCES episoder(id) ON DELETE SET NULL,
    status        TEXT NOT NULL DEFAULT 'ok',  -- ok | antatt | ukjent | sjekk
    merknad       TEXT,
    kilde         TEXT NOT NULL DEFAULT 'app', -- app | ha | import
    kilde_ref     TEXT,
    av            TEXT,
    opprettet     TEXT NOT NULL,
    endret        TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_reg_barn_tid ON registreringer(barn_id, tid);
CREATE INDEX IF NOT EXISTS idx_reg_status ON registreringer(status);
CREATE INDEX IF NOT EXISTS idx_reg_kilde ON registreringer(kilde_ref);
CREATE TABLE IF NOT EXISTS innstillinger (
    nokkel TEXT PRIMARY KEY,
    verdi  TEXT
);
"""

REG_FELT = ("barn_id", "tid", "temp", "temp_metode", "legemiddel_id", "dose_mg", "dose_ml",
            "symptomer", "notat", "episode_id", "status", "merknad", "kilde", "kilde_ref", "av")


def naa() -> datetime:
    return datetime.now(UTC).replace(microsecond=0)


def til_iso(dt: datetime) -> str:
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    return dt.astimezone(UTC).replace(microsecond=0).isoformat()


def fra_iso(s: str) -> datetime:
    dt = datetime.fromisoformat(str(s).replace("Z", "+00:00"))
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    return dt.astimezone(UTC)


class Database:
    def __init__(self, sti: Path | str):
        self.con = sqlite3.connect(str(sti), check_same_thread=False)
        self.con.row_factory = sqlite3.Row
        self.con.execute("PRAGMA journal_mode=WAL")
        self.con.execute("PRAGMA foreign_keys=ON")
        self.con.executescript(SKJEMA)
        self.con.execute("PRAGMA user_version = 1")
        self.con.commit()

    def _alle(self, sql: str, p: tuple = ()) -> list[dict]:
        return [dict(r) for r in self.con.execute(sql, p).fetchall()]

    def _en(self, sql: str, p: tuple = ()) -> dict | None:
        r = self.con.execute(sql, p).fetchone()
        return dict(r) if r else None

    # ---- barn -----------------------------------------------------------
    def barn(self) -> list[dict]:
        return self._alle("SELECT * FROM barn ORDER BY rekkefolge, id")

    def ett_barn(self, bid: int) -> dict | None:
        return self._en("SELECT * FROM barn WHERE id = ?", (bid,))

    def lagre_barn(self, d: dict, bid: int | None = None) -> dict:
        felt = ("navn", "farge", "fodselsdato", "vekt_kg", "aktiv", "rekkefolge")
        verdier = {k: d[k] for k in felt if k in d}
        if bid is None:
            if "rekkefolge" not in verdier:
                verdier["rekkefolge"] = (self._en("SELECT COALESCE(MAX(rekkefolge),0)+1 AS n FROM barn") or {"n": 1})["n"]
            kol = ", ".join(verdier)
            cur = self.con.execute(f"INSERT INTO barn ({kol}) VALUES ({', '.join('?' * len(verdier))})",
                                   tuple(verdier.values()))
            bid = cur.lastrowid
        elif verdier:
            self.con.execute(f"UPDATE barn SET {', '.join(f'{k} = ?' for k in verdier)} WHERE id = ?",
                             (*verdier.values(), bid))
        self.con.commit()
        return self.ett_barn(bid)

    def slett_barn(self, bid: int) -> bool:
        cur = self.con.execute("DELETE FROM barn WHERE id = ?", (bid,))
        self.con.commit()
        return cur.rowcount > 0

    # ---- legemidler -----------------------------------------------------
    def legemidler(self, med_arkiv: bool = True) -> list[dict]:
        sql = "SELECT * FROM legemidler" + ("" if med_arkiv else " WHERE arkivert = 0")
        return self._alle(sql + " ORDER BY navn COLLATE NOCASE")

    def legemiddel(self, lid: int) -> dict | None:
        return self._en("SELECT * FROM legemidler WHERE id = ?", (lid,))

    def finn_legemiddel(self, navn: str) -> dict | None:
        return self._en("SELECT * FROM legemidler WHERE lower(navn) = lower(?)", (navn.strip(),))

    def lagre_legemiddel(self, d: dict, lid: int | None = None) -> dict:
        felt = ("navn", "virkestoff", "form", "mg_per_ml", "arkivert")
        verdier = {k: d[k] for k in felt if k in d}
        if lid is None:
            cur = self.con.execute(
                f"INSERT INTO legemidler ({', '.join(verdier)}) VALUES ({', '.join('?' * len(verdier))})",
                tuple(verdier.values()))
            lid = cur.lastrowid
        elif verdier:
            self.con.execute(f"UPDATE legemidler SET {', '.join(f'{k} = ?' for k in verdier)} WHERE id = ?",
                             (*verdier.values(), lid))
        self.con.commit()
        return self.legemiddel(lid)

    def bruk_av_legemiddel(self, lid: int) -> int:
        return self.con.execute("SELECT COUNT(*) FROM registreringer WHERE legemiddel_id = ?", (lid,)).fetchone()[0]

    def slett_legemiddel(self, lid: int) -> None:
        self.con.execute("DELETE FROM legemidler WHERE id = ?", (lid,))
        self.con.commit()

    # ---- legemidler per barn -------------------------------------------
    def barn_legemidler(self, bid: int | None = None) -> list[dict]:
        sql = ("SELECT bl.*, l.navn, l.virkestoff, l.form, l.mg_per_ml, l.arkivert FROM barn_legemiddel bl "
               "JOIN legemidler l ON l.id = bl.legemiddel_id")
        if bid is None:
            return self._alle(sql + " ORDER BY l.navn COLLATE NOCASE")
        return self._alle(sql + " WHERE bl.barn_id = ? ORDER BY l.navn COLLATE NOCASE", (bid,))

    def barn_legemiddel(self, bid: int, lid: int) -> dict | None:
        return self._en("SELECT * FROM barn_legemiddel WHERE barn_id = ? AND legemiddel_id = ?", (bid, lid))

    def lagre_barn_legemiddel(self, bid: int, lid: int, d: dict) -> None:
        felt = ("aktiv", "standard_mg", "min_intervall_t", "maks_dogn_mg", "kur_doser_dag", "kur_til")
        verdier = {k: d.get(k) for k in felt if k in d}
        if self.barn_legemiddel(bid, lid) is None:
            verdier.setdefault("aktiv", 1)
            kol = ["barn_id", "legemiddel_id", *verdier]
            self.con.execute(f"INSERT INTO barn_legemiddel ({', '.join(kol)}) VALUES ({', '.join('?' * len(kol))})",
                             (bid, lid, *verdier.values()))
        elif verdier:
            self.con.execute(
                f"UPDATE barn_legemiddel SET {', '.join(f'{k} = ?' for k in verdier)} "
                "WHERE barn_id = ? AND legemiddel_id = ?", (*verdier.values(), bid, lid))
        self.con.commit()

    # ---- registreringer -------------------------------------------------
    @staticmethod
    def _reg(r: dict | None) -> dict | None:
        if r is None:
            return None
        r["symptomer"] = json.loads(r.get("symptomer") or "[]")
        return r

    def ny_registrering(self, d: dict, commit: bool = True) -> dict | None:
        t = til_iso(naa())
        verdier = {k: d.get(k) for k in REG_FELT if k in d}
        if isinstance(verdier.get("tid"), datetime):
            verdier["tid"] = til_iso(verdier["tid"])
        verdier["symptomer"] = json.dumps(verdier.get("symptomer") or [], ensure_ascii=False)
        verdier["opprettet"] = verdier["endret"] = t
        cur = self.con.execute(
            f"INSERT INTO registreringer ({', '.join(verdier)}) VALUES ({', '.join('?' * len(verdier))})",
            tuple(verdier.values()))
        if commit:
            self.con.commit()
            return self.registrering(cur.lastrowid)
        return None

    def registrering(self, rid: int) -> dict | None:
        return self._reg(self._en("SELECT * FROM registreringer WHERE id = ?", (rid,)))

    def oppdater_registrering(self, rid: int, d: dict, commit: bool = True) -> dict | None:
        verdier = {k: d[k] for k in REG_FELT if k in d}
        if "symptomer" in verdier:
            verdier["symptomer"] = json.dumps(verdier["symptomer"] or [], ensure_ascii=False)
        if isinstance(verdier.get("tid"), datetime):
            verdier["tid"] = til_iso(verdier["tid"])
        if not verdier:
            return self.registrering(rid)
        verdier["endret"] = til_iso(naa())
        self.con.execute(f"UPDATE registreringer SET {', '.join(f'{k} = ?' for k in verdier)} WHERE id = ?",
                         (*verdier.values(), rid))
        if commit:
            self.con.commit()
        return self.registrering(rid) if commit else None

    def slett_registrering(self, rid: int) -> bool:
        cur = self.con.execute("DELETE FROM registreringer WHERE id = ?", (rid,))
        self.con.commit()
        return cur.rowcount > 0

    def slett_registreringer(self, ider: list[int]) -> int:
        if not ider:
            return 0
        cur = self.con.execute(f"DELETE FROM registreringer WHERE id IN ({', '.join('?' * len(ider))})", tuple(ider))
        self.con.commit()
        return cur.rowcount

    def registreringer(self, barn_id: int | None = None, fra: datetime | None = None,
                       til: datetime | None = None, status: tuple[str, ...] | None = None,
                       episode_id: int | None = None, ukjent: bool = False) -> list[dict]:
        hvor, p = [], []
        if ukjent:
            hvor.append("barn_id IS NULL")
        elif barn_id is not None:
            hvor.append("barn_id = ?"); p.append(barn_id)
        if fra is not None:
            hvor.append("tid >= ?"); p.append(til_iso(fra))
        if til is not None:
            hvor.append("tid < ?"); p.append(til_iso(til))
        if status:
            hvor.append(f"status IN ({', '.join('?' * len(status))})"); p.extend(status)
        if episode_id is not None:
            hvor.append("episode_id = ?"); p.append(episode_id)
        sql = "SELECT * FROM registreringer" + (" WHERE " + " AND ".join(hvor) if hvor else "") + " ORDER BY tid, id"
        return [self._reg(r) for r in self._alle(sql, tuple(p))]

    def kilde_refs(self) -> set[str]:
        return {r[0] for r in self.con.execute("SELECT kilde_ref FROM registreringer WHERE kilde_ref IS NOT NULL")}

    def antall_status(self) -> dict:
        rad = self.con.execute(
            "SELECT SUM(barn_id IS NULL) AS ukjent, SUM(status = 'sjekk' AND barn_id IS NOT NULL) AS sjekk "
            "FROM registreringer").fetchone()
        return {"ukjent": rad["ukjent"] or 0, "sjekk": rad["sjekk"] or 0}

    # ---- episoder -------------------------------------------------------
    def episoder(self, barn_id: int | None = None) -> list[dict]:
        if barn_id is None:
            return self._alle("SELECT * FROM episoder ORDER BY start DESC")
        return self._alle("SELECT * FROM episoder WHERE barn_id = ? ORDER BY start DESC", (barn_id,))

    def episode(self, eid: int) -> dict | None:
        return self._en("SELECT * FROM episoder WHERE id = ?", (eid,))

    def commit(self) -> None:
        self.con.commit()

    # ---- innstillinger --------------------------------------------------
    def les_innstillinger(self) -> dict:
        return {r["nokkel"]: json.loads(r["verdi"]) for r in self.con.execute("SELECT * FROM innstillinger")}

    def lagre_innstillinger(self, d: dict) -> None:
        self.con.executemany(
            "INSERT INTO innstillinger (nokkel, verdi) VALUES (?, ?) "
            "ON CONFLICT(nokkel) DO UPDATE SET verdi = excluded.verdi",
            [(k, json.dumps(v, ensure_ascii=False)) for k, v in d.items()])
        self.con.commit()
