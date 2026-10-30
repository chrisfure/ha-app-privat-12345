"""Lokal lagring i SQLite. Alle tider lagres i UTC (ISO 8601)."""
from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

UTC = timezone.utc

SKJEMA = """
CREATE TABLE IF NOT EXISTS hendelser (
    id        INTEGER PRIMARY KEY AUTOINCREMENT,
    kategori  TEXT NOT NULL,           -- sovn | mat | bleie
    start     TEXT NOT NULL,           -- UTC ISO
    slutt     TEXT,                    -- UTC ISO, NULL = pågår (eller punkt-hendelse)
    detaljer  TEXT NOT NULL DEFAULT '{}',
    av        TEXT,
    opprettet TEXT NOT NULL,
    endret    TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_hendelser_start ON hendelser(start);
CREATE INDEX IF NOT EXISTS idx_hendelser_kategori ON hendelser(kategori, start);
CREATE TABLE IF NOT EXISTS maalinger (
    id      INTEGER PRIMARY KEY AUTOINCREMENT,
    type    TEXT NOT NULL,            -- vekt (g) | lengde (cm) | hode (cm) | temperatur (°C)
    verdi   REAL NOT NULL,
    tid     TEXT NOT NULL,            -- UTC ISO
    notat   TEXT,
    av      TEXT,
    opprettet TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_maalinger ON maalinger(type, tid);
CREATE TABLE IF NOT EXISTS innstillinger (
    nokkel TEXT PRIMARY KEY,
    verdi  TEXT
);
"""

KATEGORIER = ("sovn", "mat", "bleie")


def naa() -> datetime:
    return datetime.now(UTC).replace(microsecond=0)


def til_iso(dt: datetime) -> str:
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    return dt.astimezone(UTC).replace(microsecond=0).isoformat()


def fra_iso(s: str) -> datetime:
    dt = datetime.fromisoformat(s.replace("Z", "+00:00"))
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    return dt.astimezone(UTC)


class Database:
    def __init__(self, sti: Path):
        self.sti = sti
        self.con = sqlite3.connect(str(sti), check_same_thread=False)
        self.con.row_factory = sqlite3.Row
        self.con.execute("PRAGMA journal_mode=WAL")
        self.con.executescript(SKJEMA)
        self.con.execute("PRAGMA user_version = 1")
        self.con.commit()

    # ---- hjelpere -------------------------------------------------------
    @staticmethod
    def _rad(r: sqlite3.Row | None) -> dict | None:
        if r is None:
            return None
        d = dict(r)
        d["detaljer"] = json.loads(d.get("detaljer") or "{}")
        return d

    # ---- skriving -------------------------------------------------------
    def opprett(self, kategori: str, start: datetime, slutt: datetime | None,
                detaljer: dict | None = None, av: str | None = None) -> dict:
        if kategori not in KATEGORIER:
            raise ValueError(f"Ukjent kategori: {kategori}")
        t = til_iso(naa())
        cur = self.con.execute(
            "INSERT INTO hendelser (kategori, start, slutt, detaljer, av, opprettet, endret) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (kategori, til_iso(start), til_iso(slutt) if slutt else None,
             json.dumps(detaljer or {}, ensure_ascii=False), av, t, t),
        )
        self.con.commit()
        return self.hent(cur.lastrowid)

    def oppdater(self, hid: int, **felt) -> dict | None:
        tillatt = {"start", "slutt", "detaljer", "av"}
        sett, verdier = [], []
        for k, v in felt.items():
            if k not in tillatt:
                continue
            if k in ("start", "slutt") and isinstance(v, datetime):
                v = til_iso(v)
            if k == "detaljer":
                v = json.dumps(v or {}, ensure_ascii=False)
            sett.append(f"{k} = ?")
            verdier.append(v)
        if not sett:
            return self.hent(hid)
        sett.append("endret = ?")
        verdier.append(til_iso(naa()))
        verdier.append(hid)
        self.con.execute(f"UPDATE hendelser SET {', '.join(sett)} WHERE id = ?", verdier)
        self.con.commit()
        return self.hent(hid)

    def slett(self, hid: int) -> bool:
        cur = self.con.execute("DELETE FROM hendelser WHERE id = ?", (hid,))
        self.con.commit()
        return cur.rowcount > 0

    # ---- lesing ---------------------------------------------------------
    def hent(self, hid: int) -> dict | None:
        return self._rad(self.con.execute("SELECT * FROM hendelser WHERE id = ?", (hid,)).fetchone())

    def pagaende(self, kategori: str) -> dict | None:
        """Siste hendelse i kategorien som pågår (slutt = NULL).

        Punkt-hendelser (bleier, flaske) lagres alltid med slutt = start,
        så NULL betyr alltid «pågår»."""
        r = self.con.execute(
            "SELECT * FROM hendelser WHERE kategori = ? AND slutt IS NULL "
            "ORDER BY start DESC LIMIT 1",
            (kategori,),
        ).fetchone()
        return self._rad(r)

    def siste(self, kategori: str, hvor: str = "", parametre: tuple = ()) -> dict | None:
        sql = f"SELECT * FROM hendelser WHERE kategori = ? {hvor} ORDER BY start DESC LIMIT 1"
        return self._rad(self.con.execute(sql, (kategori, *parametre)).fetchone())

    def i_tidsrom(self, fra: datetime, til: datetime) -> list[dict]:
        """Alle hendelser som overlapper [fra, til)."""
        rader = self.con.execute(
            "SELECT * FROM hendelser WHERE start < ? AND (slutt IS NULL OR slutt >= ?) "
            "ORDER BY start ASC",
            (til_iso(til), til_iso(fra)),
        ).fetchall()
        return [self._rad(r) for r in rader]

    # ---- målinger -------------------------------------------------------
    def ny_maaling(self, type_: str, verdi: float, tid: datetime, notat: str | None, av: str | None) -> dict:
        cur = self.con.execute(
            "INSERT INTO maalinger (type, verdi, tid, notat, av, opprettet) VALUES (?, ?, ?, ?, ?, ?)",
            (type_, verdi, til_iso(tid), notat, av, til_iso(naa())),
        )
        self.con.commit()
        return self.maaling(cur.lastrowid)

    def maaling(self, mid: int) -> dict | None:
        r = self.con.execute("SELECT * FROM maalinger WHERE id = ?", (mid,)).fetchone()
        return dict(r) if r else None

    def maalinger(self) -> list[dict]:
        return [dict(r) for r in self.con.execute("SELECT * FROM maalinger ORDER BY tid")]

    def endre_maaling(self, mid: int, verdi: float, tid: datetime, notat: str | None) -> dict | None:
        self.con.execute("UPDATE maalinger SET verdi = ?, tid = ?, notat = ? WHERE id = ?",
                         (verdi, til_iso(tid), notat, mid))
        self.con.commit()
        return self.maaling(mid)

    def slett_maaling(self, mid: int) -> bool:
        cur = self.con.execute("DELETE FROM maalinger WHERE id = ?", (mid,))
        self.con.commit()
        return cur.rowcount > 0

    # ---- innstillinger --------------------------------------------------
    def les_innstillinger(self) -> dict:
        return {r["nokkel"]: json.loads(r["verdi"]) for r in self.con.execute("SELECT * FROM innstillinger")}

    def lagre_innstillinger(self, d: dict) -> None:
        self.con.executemany(
            "INSERT INTO innstillinger (nokkel, verdi) VALUES (?, ?) "
            "ON CONFLICT(nokkel) DO UPDATE SET verdi = excluded.verdi",
            [(k, json.dumps(v, ensure_ascii=False)) for k, v in d.items()],
        )
        self.con.commit()

    def alle(self) -> list[dict]:
        return [self._rad(r) for r in self.con.execute("SELECT * FROM hendelser ORDER BY start").fetchall()]
