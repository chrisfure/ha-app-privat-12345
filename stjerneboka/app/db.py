"""Lokal lagring i SQLite. Alle tider lagres i UTC (ISO 8601).

Ingen personlige opplysninger ligger i koden: barn, oppgaver, kort og alle
registreringer finnes bare i databasen under /data.
"""
from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from pathlib import Path

UTC = timezone.utc

SKJEMA = """
CREATE TABLE IF NOT EXISTS barn (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    navn        TEXT NOT NULL,
    farge       TEXT NOT NULL DEFAULT 'rosa',
    emoji       TEXT NOT NULL DEFAULT '',
    aktiv       INTEGER NOT NULL DEFAULT 1,
    rekkefolge  INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS oppgaver (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    navn          TEXT NOT NULL,
    bilde         TEXT NOT NULL DEFAULT 'emoji:⭐',   -- innebygd:<navn> | emoji:<tegn> | fil:<filnavn>
    type          TEXT NOT NULL DEFAULT 'rutine',     -- rutine | familie | ekstra
    poeng         INTEGER NOT NULL DEFAULT 1,         -- 1 lett, 2 middels, 3 krevende
    godkjenning   INTEGER NOT NULL DEFAULT 0,         -- 1 = en voksen må godkjenne
    penger        INTEGER NOT NULL DEFAULT 0,         -- 1 = teller med i ukepenger
    nar           TEXT NOT NULL DEFAULT 'hele_dagen', -- kommaliste: morgen,dag,kveld eller hele_dagen
    sperre        TEXT NOT NULL DEFAULT 'okt',        -- okt | dag | intervall | fri
    intervall_min INTEGER NOT NULL DEFAULT 30,
    maks_per_dag  INTEGER NOT NULL DEFAULT 0,         -- 0 = ingen grense
    ros           TEXT NOT NULL DEFAULT '',           -- «Du har …» i stemmen, f.eks. «pusset tenner»
    aktiv         INTEGER NOT NULL DEFAULT 1,
    rekkefolge    INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS oppgave_barn (
    oppgave_id INTEGER NOT NULL REFERENCES oppgaver(id) ON DELETE CASCADE,
    barn_id    INTEGER NOT NULL REFERENCES barn(id) ON DELETE CASCADE,
    PRIMARY KEY (oppgave_id, barn_id)
);
CREATE TABLE IF NOT EXISTS kort (
    uid        TEXT PRIMARY KEY,
    handling   TEXT NOT NULL DEFAULT 'oppgave',       -- oppgave | vis_skjerm
    barn_id    INTEGER REFERENCES barn(id) ON DELETE CASCADE,
    oppgave_id INTEGER REFERENCES oppgaver(id) ON DELETE CASCADE,
    navn       TEXT
);
CREATE TABLE IF NOT EXISTS ukjente_kort (
    uid  TEXT PRIMARY KEY,
    tid  TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS lesere (
    id           TEXT PRIMARY KEY,                    -- device_id fra Home Assistant
    navn         TEXT NOT NULL DEFAULT '',
    rom          TEXT NOT NULL DEFAULT '',
    gir_stjerner INTEGER NOT NULL DEFAULT 1,
    hoyttaler    TEXT NOT NULL DEFAULT '',            -- media_player for musikk-kort på denne leseren
    sist_sett    TEXT
);
CREATE TABLE IF NOT EXISTS registreringer (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    barn_id       INTEGER NOT NULL REFERENCES barn(id) ON DELETE CASCADE,
    oppgave_id    INTEGER REFERENCES oppgaver(id) ON DELETE SET NULL,
    oppgave_navn  TEXT NOT NULL,
    tid           TEXT NOT NULL,
    status        TEXT NOT NULL DEFAULT 'godkjent',   -- godkjent | venter | avvist
    poeng         INTEGER NOT NULL DEFAULT 1,
    penger        INTEGER NOT NULL DEFAULT 0,
    type          TEXT NOT NULL DEFAULT 'rutine',
    kilde         TEXT NOT NULL DEFAULT 'skjerm',     -- skjerm | kort | ha | admin
    av            TEXT,
    behandlet_av  TEXT,
    behandlet_tid TEXT
);
CREATE INDEX IF NOT EXISTS idx_reg_barn_tid ON registreringer(barn_id, tid);
CREATE INDEX IF NOT EXISTS idx_reg_status ON registreringer(status);
CREATE TABLE IF NOT EXISTS utbetalinger (
    id       INTEGER PRIMARY KEY AUTOINCREMENT,
    barn_id  INTEGER NOT NULL REFERENCES barn(id) ON DELETE CASCADE,
    uke      TEXT NOT NULL,                           -- f.eks. 2026-W48
    belop    REAL NOT NULL,
    tid      TEXT NOT NULL,
    av       TEXT,
    UNIQUE (barn_id, uke)
);
CREATE TABLE IF NOT EXISTS innstillinger (
    nokkel TEXT PRIMARY KEY,
    verdi  TEXT
);
"""

OPPGAVE_FELT = ("navn", "bilde", "type", "poeng", "godkjenning", "penger", "nar", "sperre",
                "intervall_min", "maks_per_dag", "ros", "aktiv", "rekkefolge")
BARN_FELT = ("navn", "farge", "emoji", "aktiv", "rekkefolge")


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
        self._migrer()
        self.con.execute("PRAGMA user_version = 2")
        self.con.commit()

    def _migrer(self) -> None:
        def kolonner(tabell):
            return {r[1] for r in self.con.execute(f"PRAGMA table_info({tabell})").fetchall()}
        for kol in ("media_id", "media_type", "hoyttaler", "entity", "bryter"):
            if kol not in kolonner("kort"):
                self.con.execute(f"ALTER TABLE kort ADD COLUMN {kol} TEXT")
        if "maks_per_dag" not in kolonner("oppgaver"):
            self.con.execute("ALTER TABLE oppgaver ADD COLUMN maks_per_dag INTEGER NOT NULL DEFAULT 0")
        if "leser_id" not in kolonner("ukjente_kort"):
            self.con.execute("ALTER TABLE ukjente_kort ADD COLUMN leser_id TEXT")

    def _alle(self, sql: str, p: tuple = ()) -> list[dict]:
        return [dict(r) for r in self.con.execute(sql, p).fetchall()]

    def _en(self, sql: str, p: tuple = ()) -> dict | None:
        r = self.con.execute(sql, p).fetchone()
        return dict(r) if r else None

    def _neste_rekkefolge(self, tabell: str) -> int:
        return (self._en(f"SELECT COALESCE(MAX(rekkefolge), 0) + 1 AS n FROM {tabell}") or {"n": 1})["n"]

    def _lagre(self, tabell: str, felt: tuple, d: dict, rid: int | None) -> int:
        verdier = {k: d[k] for k in felt if k in d}
        if rid is None:
            verdier.setdefault("rekkefolge", self._neste_rekkefolge(tabell))
            kol = ", ".join(verdier)
            cur = self.con.execute(f"INSERT INTO {tabell} ({kol}) VALUES ({', '.join('?' * len(verdier))})",
                                   tuple(verdier.values()))
            rid = cur.lastrowid
        elif verdier:
            self.con.execute(f"UPDATE {tabell} SET {', '.join(f'{k} = ?' for k in verdier)} WHERE id = ?",
                             (*verdier.values(), rid))
        return rid

    # ---- barn -----------------------------------------------------------
    def barn(self, bare_aktive: bool = False) -> list[dict]:
        sql = "SELECT * FROM barn" + (" WHERE aktiv = 1" if bare_aktive else "") + " ORDER BY rekkefolge, id"
        return self._alle(sql)

    def ett_barn(self, bid: int) -> dict | None:
        return self._en("SELECT * FROM barn WHERE id = ?", (bid,))

    def lagre_barn(self, d: dict, bid: int | None = None) -> dict:
        bid = self._lagre("barn", BARN_FELT, d, bid)
        self.con.commit()
        return self.ett_barn(bid)

    def slett_barn(self, bid: int) -> None:
        self.con.execute("DELETE FROM barn WHERE id = ?", (bid,))
        self.con.commit()

    # ---- oppgaver -------------------------------------------------------
    def oppgaver(self, bare_aktive: bool = False) -> list[dict]:
        sql = "SELECT * FROM oppgaver" + (" WHERE aktiv = 1" if bare_aktive else "") + " ORDER BY rekkefolge, id"
        rader = self._alle(sql)
        kobling: dict[int, list[int]] = {}
        for r in self._alle("SELECT oppgave_id, barn_id FROM oppgave_barn"):
            kobling.setdefault(r["oppgave_id"], []).append(r["barn_id"])
        for r in rader:
            r["barn"] = sorted(kobling.get(r["id"], []))
        return rader

    def en_oppgave(self, oid: int) -> dict | None:
        r = self._en("SELECT * FROM oppgaver WHERE id = ?", (oid,))
        if r:
            r["barn"] = [x["barn_id"] for x in self._alle(
                "SELECT barn_id FROM oppgave_barn WHERE oppgave_id = ? ORDER BY barn_id", (oid,))]
        return r

    def lagre_oppgave(self, d: dict, oid: int | None = None) -> dict:
        oid = self._lagre("oppgaver", OPPGAVE_FELT, d, oid)
        if "barn" in d:
            self.con.execute("DELETE FROM oppgave_barn WHERE oppgave_id = ?", (oid,))
            self.con.executemany("INSERT OR IGNORE INTO oppgave_barn (oppgave_id, barn_id) VALUES (?, ?)",
                                 [(oid, int(b)) for b in d["barn"]])
        self.con.commit()
        return self.en_oppgave(oid)

    def slett_oppgave(self, oid: int) -> None:
        self.con.execute("DELETE FROM oppgaver WHERE id = ?", (oid,))
        self.con.commit()

    def sett_rekkefolge(self, tabell: str, ider: list[int]) -> None:
        if tabell not in ("barn", "oppgaver"):
            raise ValueError(tabell)
        self.con.executemany(f"UPDATE {tabell} SET rekkefolge = ? WHERE id = ?",
                             [(i + 1, int(x)) for i, x in enumerate(ider)])
        self.con.commit()

    # ---- kort -----------------------------------------------------------
    def kortliste(self) -> list[dict]:
        return self._alle("SELECT * FROM kort ORDER BY uid")

    def ett_kort(self, uid: str) -> dict | None:
        return self._en("SELECT * FROM kort WHERE uid = ?", (uid,))

    KORT_FELT = ("handling", "barn_id", "oppgave_id", "navn", "media_id", "media_type", "hoyttaler", "entity", "bryter")

    def lagre_kort(self, uid: str, d: dict) -> dict:
        felt = self.KORT_FELT
        verdier = [d.get(k) for k in felt]
        verdier[0] = verdier[0] or "oppgave"
        self.con.execute(
            f"INSERT INTO kort (uid, {', '.join(felt)}) VALUES (?, {', '.join('?' * len(felt))}) "
            f"ON CONFLICT(uid) DO UPDATE SET {', '.join(f'{k} = excluded.{k}' for k in felt)}",
            (uid, *verdier))
        self.con.execute("DELETE FROM ukjente_kort WHERE uid = ?", (uid,))
        self.con.commit()
        return self.ett_kort(uid)

    def slett_kort(self, uid: str) -> None:
        self.con.execute("DELETE FROM kort WHERE uid = ?", (uid,))
        self.con.commit()

    def ukjent_kort(self, uid: str, tid: str, leser_id: str | None = None) -> None:
        self.con.execute("INSERT INTO ukjente_kort (uid, tid, leser_id) VALUES (?, ?, ?) "
                         "ON CONFLICT(uid) DO UPDATE SET tid = excluded.tid, leser_id = excluded.leser_id",
                         (uid, tid, leser_id))
        self.con.execute("DELETE FROM ukjente_kort WHERE uid NOT IN "
                         "(SELECT uid FROM ukjente_kort ORDER BY tid DESC LIMIT 20)")
        self.con.commit()

    def ukjente_kort(self) -> list[dict]:
        return self._alle("SELECT * FROM ukjente_kort ORDER BY tid DESC")

    def glem_ukjente_kort(self) -> None:
        self.con.execute("DELETE FROM ukjente_kort")
        self.con.commit()

    # ---- lesere ---------------------------------------------------------
    def lesere(self) -> list[dict]:
        return self._alle("SELECT * FROM lesere ORDER BY navn, id")

    def en_leser(self, lid: str) -> dict | None:
        return self._en("SELECT * FROM lesere WHERE id = ?", (lid,))

    def se_leser(self, lid: str, navn: str | None, rom: str | None, tid: str) -> dict:
        """Registrerer at en leser er sett. Navn og rom fra Home Assistant oppdateres, innstillinger beholdes."""
        self.con.execute(
            "INSERT INTO lesere (id, navn, rom, sist_sett) VALUES (?, ?, ?, ?) ON CONFLICT(id) DO UPDATE SET "
            "navn = CASE WHEN excluded.navn != '' THEN excluded.navn ELSE lesere.navn END, "
            "rom = CASE WHEN excluded.rom != '' THEN excluded.rom ELSE lesere.rom END, sist_sett = excluded.sist_sett",
            (lid, navn or "", rom or "", tid))
        self.con.commit()
        return self.en_leser(lid)

    def lagre_leser(self, lid: str, d: dict) -> dict | None:
        verdier = {k: d[k] for k in ("gir_stjerner", "hoyttaler") if k in d}
        if verdier:
            self.con.execute(f"UPDATE lesere SET {', '.join(f'{k} = ?' for k in verdier)} WHERE id = ?",
                             (*verdier.values(), lid))
            self.con.commit()
        return self.en_leser(lid)

    def slett_leser(self, lid: str) -> None:
        self.con.execute("DELETE FROM lesere WHERE id = ?", (lid,))
        self.con.commit()

    # ---- registreringer -------------------------------------------------
    def ny_registrering(self, d: dict) -> dict:
        felt = ("barn_id", "oppgave_id", "oppgave_navn", "tid", "status", "poeng", "penger", "type", "kilde", "av")
        verdier = {k: d.get(k) for k in felt}
        cur = self.con.execute(f"INSERT INTO registreringer ({', '.join(felt)}) VALUES ({', '.join('?' * len(felt))})",
                               tuple(verdier.values()))
        self.con.commit()
        return self.registrering(cur.lastrowid)

    def registrering(self, rid: int) -> dict | None:
        return self._en("SELECT * FROM registreringer WHERE id = ?", (rid,))

    def registreringer(self, fra: str | None = None, til: str | None = None, barn_id: int | None = None,
                       status: str | None = None, grense: int | None = None) -> list[dict]:
        sql, p = "SELECT * FROM registreringer WHERE 1 = 1", []
        if fra:
            sql += " AND tid >= ?"
            p.append(fra)
        if til:
            sql += " AND tid < ?"
            p.append(til)
        if barn_id is not None:
            sql += " AND barn_id = ?"
            p.append(barn_id)
        if status:
            sql += " AND status = ?"
            p.append(status)
        sql += " ORDER BY tid DESC, id DESC"
        if grense:
            sql += f" LIMIT {int(grense)}"
        return self._alle(sql, tuple(p))

    def siste_for(self, barn_id: int, oppgave_id: int) -> dict | None:
        return self._en("SELECT * FROM registreringer WHERE barn_id = ? AND oppgave_id = ? AND status != 'avvist' "
                        "ORDER BY tid DESC, id DESC LIMIT 1", (barn_id, oppgave_id))

    def sett_status(self, rid: int, status: str, av: str | None, tid: str) -> dict | None:
        self.con.execute("UPDATE registreringer SET status = ?, behandlet_av = ?, behandlet_tid = ? WHERE id = ?",
                         (status, av, tid, rid))
        self.con.commit()
        return self.registrering(rid)

    def slett_registrering(self, rid: int) -> None:
        self.con.execute("DELETE FROM registreringer WHERE id = ?", (rid,))
        self.con.commit()

    # ---- utbetalinger ---------------------------------------------------
    def utbetalinger(self) -> list[dict]:
        return self._alle("SELECT * FROM utbetalinger ORDER BY uke DESC, barn_id")

    def registrer_utbetaling(self, barn_id: int, uke: str, belop: float, tid: str, av: str | None) -> None:
        self.con.execute("INSERT INTO utbetalinger (barn_id, uke, belop, tid, av) VALUES (?, ?, ?, ?, ?) "
                         "ON CONFLICT(barn_id, uke) DO UPDATE SET belop = excluded.belop, tid = excluded.tid, "
                         "av = excluded.av", (barn_id, uke, belop, tid, av))
        self.con.commit()

    def angre_utbetaling(self, barn_id: int, uke: str) -> None:
        self.con.execute("DELETE FROM utbetalinger WHERE barn_id = ? AND uke = ?", (barn_id, uke))
        self.con.commit()

    # ---- innstillinger --------------------------------------------------
    def innstillinger(self) -> dict[str, str]:
        return {r["nokkel"]: r["verdi"] for r in self._alle("SELECT * FROM innstillinger")}

    def lagre_innstillinger(self, d: dict[str, str]) -> None:
        self.con.executemany("INSERT INTO innstillinger (nokkel, verdi) VALUES (?, ?) "
                             "ON CONFLICT(nokkel) DO UPDATE SET verdi = excluded.verdi", list(d.items()))
        self.con.commit()
