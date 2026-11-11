"""Lokal lagring i SQLite under /data. Beløp lagres i øre (heltall), datoer som YYYY-MM-DD.

Ingen personlige opplysninger ligger i koden: kontoer, transaksjoner og regler finnes bare i databasen.
"""
from __future__ import annotations

import json
import sqlite3
import threading
from datetime import datetime, timezone
from pathlib import Path

SKJEMA = """
CREATE TABLE IF NOT EXISTS kontoer (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    navn        TEXT NOT NULL,
    type        TEXT NOT NULL DEFAULT 'bruk',   -- bruk | felles | kreditt | sparing | lan | annet
    skjult      INTEGER NOT NULL DEFAULT 0,     -- vises ikke i oversikten, men brukes til å finne overføringer
    rekkefolge  INTEGER NOT NULL DEFAULT 0,
    opprettet   TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS kategorier (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    navn        TEXT NOT NULL UNIQUE,
    ikon        TEXT NOT NULL DEFAULT '📦',
    gruppe      TEXT NOT NULL DEFAULT 'utgift', -- utgift | inntekt | sparing | overforing
    budsjett_ore INTEGER,                       -- per måned, NULL = uten budsjett
    rekkefolge  INTEGER NOT NULL DEFAULT 0,
    skjult      INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS importer (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    konto_id    INTEGER NOT NULL REFERENCES kontoer(id) ON DELETE CASCADE,
    filnavn     TEXT,
    tid         TEXT NOT NULL,
    av          TEXT,
    nye         INTEGER NOT NULL DEFAULT 0,
    duplikater  INTEGER NOT NULL DEFAULT 0,
    fra         TEXT,
    til         TEXT
);
CREATE TABLE IF NOT EXISTS regler (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    monster     TEXT NOT NULL UNIQUE,           -- små bokstaver, treffer hele ord i banktekst
    kategori_id INTEGER NOT NULL REFERENCES kategorier(id) ON DELETE CASCADE,
    laget_av    TEXT,
    opprettet   TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS transaksjoner (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    konto_id      INTEGER NOT NULL REFERENCES kontoer(id) ON DELETE CASCADE,
    import_id     INTEGER REFERENCES importer(id) ON DELETE CASCADE,
    dato          TEXT NOT NULL,
    belop_ore     INTEGER NOT NULL,             -- negativt = ut
    tekst         TEXT NOT NULL,
    motpart       TEXT NOT NULL,
    kategori_id   INTEGER REFERENCES kategorier(id) ON DELETE SET NULL,
    kilde         TEXT,                         -- regel | kjent | manuell | overforing
    regel_id      INTEGER REFERENCES regler(id) ON DELETE SET NULL,
    par_id        INTEGER,                      -- den andre halvdelen av en overføring
    ikke_overforing INTEGER NOT NULL DEFAULT 0,
    notat         TEXT,
    fingeravtrykk TEXT NOT NULL,
    endret_av     TEXT,
    endret        TEXT,
    UNIQUE (konto_id, fingeravtrykk)
);
CREATE INDEX IF NOT EXISTS tx_dato ON transaksjoner(dato);
CREATE INDEX IF NOT EXISTS tx_motpart ON transaksjoner(motpart);
CREATE TABLE IF NOT EXISTS merknader (
    nokkel  TEXT PRIMARY KEY,                   -- «sett» varsler og valg for faste trekk
    verdi   TEXT NOT NULL,
    tid     TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS innstillinger (
    nokkel  TEXT PRIMARY KEY,
    verdi   TEXT NOT NULL
);
"""


def naa_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class Database:
    def __init__(self, sti: Path | str):
        self.sti = str(sti)
        self._lås = threading.RLock()
        self.con = sqlite3.connect(self.sti, check_same_thread=False, isolation_level=None)
        self.con.row_factory = sqlite3.Row
        self.con.execute("PRAGMA foreign_keys = ON")
        self.con.execute("PRAGMA journal_mode = WAL")
        self.con.executescript(SKJEMA)

    # ---- grunnleggende
    def rader(self, sql: str, args=()) -> list[dict]:
        with self._lås:
            return [dict(r) for r in self.con.execute(sql, args).fetchall()]

    def rad(self, sql: str, args=()) -> dict | None:
        with self._lås:
            r = self.con.execute(sql, args).fetchone()
            return dict(r) if r else None

    def verdi(self, sql: str, args=()):
        with self._lås:
            r = self.con.execute(sql, args).fetchone()
            return r[0] if r else None

    def kjor(self, sql: str, args=()) -> int:
        with self._lås:
            return self.con.execute(sql, args).lastrowid

    def transaksjon(self):
        """with db.transaksjon(): … – alt eller ingenting."""
        db = self

        class _T:
            def __enter__(self):
                db._lås.acquire()
                db.con.execute("BEGIN")

            def __exit__(self, typ, *_):
                try:
                    db.con.execute("ROLLBACK" if typ else "COMMIT")
                finally:
                    db._lås.release()
        return _T()

    # ---- innstillinger og merknader
    def innstilling(self, nokkel: str, standard=None):
        v = self.verdi("SELECT verdi FROM innstillinger WHERE nokkel = ?", (nokkel,))
        return json.loads(v) if v is not None else standard

    def sett_innstilling(self, nokkel: str, verdi) -> None:
        self.kjor("INSERT INTO innstillinger(nokkel, verdi) VALUES(?, ?) "
                  "ON CONFLICT(nokkel) DO UPDATE SET verdi = excluded.verdi", (nokkel, json.dumps(verdi)))

    def merknader(self) -> dict[str, str]:
        return {r["nokkel"]: r["verdi"] for r in self.rader("SELECT nokkel, verdi FROM merknader")}

    def merk(self, nokkel: str, verdi: str | None) -> None:
        if verdi is None:
            self.kjor("DELETE FROM merknader WHERE nokkel = ?", (nokkel,))
        else:
            self.kjor("INSERT INTO merknader(nokkel, verdi, tid) VALUES(?, ?, ?) ON CONFLICT(nokkel) "
                      "DO UPDATE SET verdi = excluded.verdi, tid = excluded.tid", (nokkel, verdi, naa_iso()))
