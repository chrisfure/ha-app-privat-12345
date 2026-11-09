"""SQLite-lagring for Styrkeboka. Alt ligger lokalt i appens /data-mappe."""
from __future__ import annotations

import json
import sqlite3
import threading
from datetime import datetime, timezone
from pathlib import Path


def naa() -> datetime:
    return datetime.now(timezone.utc)


def til_iso(d: datetime) -> str:
    return d.astimezone(timezone.utc).isoformat(timespec="seconds")


def fra_iso(s: str | None) -> datetime | None:
    if not s:
        return None
    d = datetime.fromisoformat(s.replace("Z", "+00:00"))
    return d if d.tzinfo else d.replace(tzinfo=timezone.utc)


SKJEMA = """
CREATE TABLE IF NOT EXISTS innstillinger (nokkel TEXT PRIMARY KEY, verdi TEXT);

CREATE TABLE IF NOT EXISTS utstyrsprofiler (
  id INTEGER PRIMARY KEY, navn TEXT NOT NULL, utstyr TEXT NOT NULL DEFAULT '[]', rekkefolge INTEGER DEFAULT 0
);

CREATE TABLE IF NOT EXISTS profiler (
  id INTEGER PRIMARY KEY, navn TEXT NOT NULL, farge TEXT DEFAULT 'lilla', ha_bruker TEXT,
  erfaring TEXT DEFAULT 'noe', maal TEXT DEFAULT '["generell"]', dager_per_uke INTEGER DEFAULT 3,
  okt_minutter INTEGER DEFAULT 60, hensyn TEXT DEFAULT '', utstyrsprofil_id INTEGER,
  opprettet TEXT, arkivert INTEGER DEFAULT 0
);

CREATE TABLE IF NOT EXISTS egne_ovelser (
  id INTEGER PRIMARY KEY, navn TEXT NOT NULL, monster TEXT NOT NULL, type TEXT NOT NULL,
  utstyr TEXT DEFAULT '[]', muskler TEXT DEFAULT '[]', tips TEXT DEFAULT '', arkivert INTEGER DEFAULT 0
);

CREATE TABLE IF NOT EXISTS programmer (
  id INTEGER PRIMARY KEY, profil_id INTEGER NOT NULL, navn TEXT NOT NULL, beskrivelse TEXT DEFAULT '',
  begrunnelse TEXT DEFAULT '', kilde TEXT DEFAULT 'mal', aktiv INTEGER DEFAULT 0,
  opprettet TEXT, endret TEXT, arkivert INTEGER DEFAULT 0
);
CREATE TABLE IF NOT EXISTS programdager (
  id INTEGER PRIMARY KEY, program_id INTEGER NOT NULL REFERENCES programmer(id) ON DELETE CASCADE,
  rekkefolge INTEGER NOT NULL, navn TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS programovelser (
  id INTEGER PRIMARY KEY, dag_id INTEGER NOT NULL REFERENCES programdager(id) ON DELETE CASCADE,
  rekkefolge INTEGER NOT NULL, ovelse TEXT NOT NULL, sett INTEGER DEFAULT 3,
  reps_min INTEGER DEFAULT 8, reps_maks INTEGER DEFAULT 12, hvile_s INTEGER DEFAULT 90, rir INTEGER DEFAULT 2,
  notat TEXT DEFAULT ''
);
CREATE TABLE IF NOT EXISTS programversjoner (
  id INTEGER PRIMARY KEY, program_id INTEGER NOT NULL REFERENCES programmer(id) ON DELETE CASCADE,
  tid TEXT NOT NULL, kilde TEXT, beskrivelse TEXT, data TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS okter (
  id INTEGER PRIMARY KEY, profil_id INTEGER NOT NULL, program_id INTEGER, dag_id INTEGER, dag_navn TEXT,
  utstyrsprofil_id INTEGER, startet TEXT NOT NULL, avsluttet TEXT, status TEXT DEFAULT 'pagar',
  opplevd INTEGER, notat TEXT DEFAULT '', ai_tips TEXT, ai_oppsummering TEXT, av TEXT
);
CREATE INDEX IF NOT EXISTS ix_okter_profil ON okter(profil_id, startet);
CREATE TABLE IF NOT EXISTS okt_ovelser (
  id INTEGER PRIMARY KEY, okt_id INTEGER NOT NULL REFERENCES okter(id) ON DELETE CASCADE,
  rekkefolge INTEGER NOT NULL, ovelse TEXT NOT NULL, programovelse_id INTEGER,
  sett_plan INTEGER DEFAULT 3, reps_min INTEGER DEFAULT 8, reps_maks INTEGER DEFAULT 12,
  hvile_s INTEGER DEFAULT 90, rir INTEGER DEFAULT 2, forslag_kg REAL, forslag_reps INTEGER,
  forslag_tekst TEXT DEFAULT '', notat TEXT DEFAULT '', erstattet_fra TEXT
);
CREATE TABLE IF NOT EXISTS sett (
  id INTEGER PRIMARY KEY, okt_id INTEGER NOT NULL REFERENCES okter(id) ON DELETE CASCADE,
  okt_ovelse_id INTEGER NOT NULL REFERENCES okt_ovelser(id) ON DELETE CASCADE,
  ovelse TEXT NOT NULL, settnr INTEGER NOT NULL, vekt REAL, reps INTEGER, rir INTEGER,
  oppvarming INTEGER DEFAULT 0, tid TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS ix_sett_ovelse ON sett(ovelse, tid);

CREATE TABLE IF NOT EXISTS startvekter (
  profil_id INTEGER NOT NULL, ovelse TEXT NOT NULL, kg REAL NOT NULL, kilde TEXT, tid TEXT,
  PRIMARY KEY (profil_id, ovelse)
);

CREATE TABLE IF NOT EXISTS maalinger (
  id INTEGER PRIMARY KEY, profil_id INTEGER NOT NULL, type TEXT NOT NULL, verdi REAL NOT NULL,
  dato TEXT NOT NULL, tid TEXT NOT NULL, kilde TEXT DEFAULT 'manuell', UNIQUE (profil_id, type, dato)
);
CREATE TABLE IF NOT EXISTS aktiviteter (
  id INTEGER PRIMARY KEY, profil_id INTEGER NOT NULL, ekstern_id TEXT, type TEXT NOT NULL, navn TEXT,
  start TEXT NOT NULL, varighet_s REAL, distanse_m REAL, hoydemeter REAL, snittpuls INTEGER, makspuls INTEGER,
  kalorier INTEGER, skritt INTEGER, moderate_min INTEGER, hoy_min INTEGER, belastning REAL, aerob_effekt REAL,
  kilde TEXT DEFAULT 'manuell', notat TEXT DEFAULT '', UNIQUE (profil_id, ekstern_id)
);
CREATE INDEX IF NOT EXISTS ix_akt_profil ON aktiviteter(profil_id, start);

CREATE TABLE IF NOT EXISTS loepeperioder (
  id INTEGER PRIMARY KEY, profil_id INTEGER NOT NULL, fra TEXT NOT NULL, til TEXT NOT NULL,
  okter_per_uke INTEGER DEFAULT 2, niva TEXT DEFAULT 'vanlig', maal TEXT DEFAULT 'form',
  juster_styrke INTEGER DEFAULT 1, opprettet TEXT
);

CREATE TABLE IF NOT EXISTS garmin_okter (
  id INTEGER PRIMARY KEY, profil_id INTEGER NOT NULL, periode_id INTEGER, dato TEXT NOT NULL, nokkel TEXT NOT NULL,
  workout_id TEXT, schedule_id TEXT, tid TEXT, UNIQUE (profil_id, dato)
);

CREATE TABLE IF NOT EXISTS ai_logg (
  id INTEGER PRIMARY KEY, profil_id INTEGER, okt_id INTEGER, tid TEXT NOT NULL, type TEXT,
  sporsmal TEXT, svar TEXT
);
"""

JSON_FELT = {"utstyr", "muskler", "maal", "ai_tips", "ai_oppsummering", "data", "kjente_loft", "koblinger", "lopedager", "garmin_eksport"}


class Database:
    def __init__(self, sti: Path | str):
        self.con = sqlite3.connect(str(sti), check_same_thread=False)
        self.con.row_factory = sqlite3.Row
        self.lås = threading.RLock()
        self.con.execute("PRAGMA journal_mode=WAL")
        self.con.execute("PRAGMA foreign_keys=ON")
        self.con.executescript(SKJEMA)
        self._migrer()
        self.con.commit()

    def _migrer(self) -> None:
        """Legger til kolonner som kom i senere versjoner. self.nye_kolonner sier hva som ble lagt til nå."""
        self.nye_kolonner: set[str] = set()
        nye = {
            "egne_ovelser": [("instruksjon", "TEXT DEFAULT ''")],
            "programmer": [("blokk_nr", "INTEGER DEFAULT 1"), ("blokk_start", "TEXT"), ("blokk_uker", "INTEGER DEFAULT 6"),
                           ("lett_uke", "INTEGER DEFAULT 1")],
            "programovelser": [("fast", "INTEGER DEFAULT 0")],
            "okter": [("lett", "INTEGER DEFAULT 0"), ("blokk_nr", "INTEGER"), ("garmin_sendt", "TEXT")],
            "loepeperioder": [("lopedager", "TEXT DEFAULT '[]'")],
            "profiler": [("kroppsvekt", "REAL"), ("kjente_loft", "TEXT DEFAULT '[]'"), ("fodselsaar", "INTEGER"),
                         ("hoyde_cm", "REAL"), ("kjonn", "TEXT"), ("koblinger", "TEXT DEFAULT '{}'"),
                         ("garmin_eksport", "TEXT DEFAULT '{}'")],
        }
        for tabell, kolonner in nye.items():
            finnes = {r[1] for r in self.con.execute(f"PRAGMA table_info({tabell})")}
            for navn, typ in kolonner:
                if navn not in finnes:
                    self.con.execute(f"ALTER TABLE {tabell} ADD COLUMN {navn} {typ}")
                    self.nye_kolonner.add(f"{tabell}.{navn}")

    # ------------------------------------------------------------ hjelpere
    @staticmethod
    def _rad(r: sqlite3.Row | None) -> dict | None:
        if r is None:
            return None
        d = dict(r)
        for k in JSON_FELT & d.keys():
            if isinstance(d[k], str):
                try:
                    d[k] = json.loads(d[k])
                except ValueError:
                    pass
        return d

    def alle(self, sql: str, args: tuple = ()) -> list[dict]:
        with self.lås:
            return [self._rad(r) for r in self.con.execute(sql, args).fetchall()]

    def en(self, sql: str, args: tuple = ()) -> dict | None:
        with self.lås:
            return self._rad(self.con.execute(sql, args).fetchone())

    def verdi(self, sql: str, args: tuple = ()):
        with self.lås:
            r = self.con.execute(sql, args).fetchone()
            return r[0] if r else None

    def kjor(self, sql: str, args: tuple = (), commit: bool = True) -> int:
        with self.lås:
            cur = self.con.execute(sql, args)
            if commit:
                self.con.commit()
            return cur.lastrowid

    @staticmethod
    def _ser(v):
        return json.dumps(v, ensure_ascii=False) if isinstance(v, (list, dict)) else v

    def sett_inn(self, tabell: str, d: dict, commit: bool = True) -> int:
        kol = list(d)
        return self.kjor(f"INSERT INTO {tabell} ({', '.join(kol)}) VALUES ({', '.join('?' * len(kol))})",
                         tuple(self._ser(d[k]) for k in kol), commit)

    def oppdater(self, tabell: str, rid: int, d: dict, commit: bool = True) -> None:
        if not d:
            return
        self.kjor(f"UPDATE {tabell} SET {', '.join(f'{k} = ?' for k in d)} WHERE id = ?",
                  (*(self._ser(v) for v in d.values()), rid), commit)

    def slett(self, tabell: str, rid: int) -> None:
        self.kjor(f"DELETE FROM {tabell} WHERE id = ?", (rid,))

    def commit(self) -> None:
        with self.lås:
            self.con.commit()

    # ------------------------------------------------------------ innstillinger
    def innstillinger(self) -> dict:
        return {r["nokkel"]: json.loads(r["verdi"]) for r in self.alle("SELECT * FROM innstillinger")}

    def lagre_innstilling(self, nokkel: str, verdi) -> None:
        self.kjor("INSERT INTO innstillinger (nokkel, verdi) VALUES (?, ?) "
                  "ON CONFLICT(nokkel) DO UPDATE SET verdi = excluded.verdi",
                  (nokkel, json.dumps(verdi, ensure_ascii=False)))
