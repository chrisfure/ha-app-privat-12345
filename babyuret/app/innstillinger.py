"""Leser app-innstillinger fra Home Assistant (/data/options.json).

Alle personlige verdier (navn, fødselsdato osv.) hører hjemme her –
aldri i koden.
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass
from datetime import date
from pathlib import Path


@dataclass
class Innstillinger:
    data_dir: Path
    baby_navn: str = ""
    fodselsdato: date | None = None
    mating: str = "begge"  # amming | flaske | begge
    standard_flaske_ml: int = 90
    nattmodus_fra: str = "21:00"
    nattmodus_til: str = "07:00"
    port: int = 8099

    def offentlig(self) -> dict:
        """Det frontend trenger å vite."""
        return {
            "baby_navn": self.baby_navn,
            "fodselsdato": self.fodselsdato.isoformat() if self.fodselsdato else None,
            "mating": self.mating,
            "standard_flaske_ml": self.standard_flaske_ml,
            "nattmodus_fra": self.nattmodus_fra,
            "nattmodus_til": self.nattmodus_til,
        }


def _dato(verdi: str | None) -> date | None:
    if not verdi:
        return None
    try:
        return date.fromisoformat(verdi.strip())
    except ValueError:
        return None


def les() -> Innstillinger:
    data_dir = Path(os.environ.get("BABYURET_DATA", "/data"))
    if not data_dir.exists():
        data_dir = Path(__file__).resolve().parent.parent / "data"
    data_dir.mkdir(parents=True, exist_ok=True)

    raw: dict = {}
    options = data_dir / "options.json"
    if options.exists():
        try:
            raw = json.loads(options.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            raw = {}

    mating = raw.get("mating", "begge")
    if mating not in ("amming", "flaske", "begge"):
        mating = "begge"

    return Innstillinger(
        data_dir=data_dir,
        baby_navn=(raw.get("baby_navn") or "").strip(),
        fodselsdato=_dato(raw.get("fodselsdato")),
        mating=mating,
        standard_flaske_ml=int(raw.get("standard_flaske_ml") or 90),
        nattmodus_fra=raw.get("nattmodus_fra") or "21:00",
        nattmodus_til=raw.get("nattmodus_til") or "07:00",
        port=int(os.environ.get("BABYURET_PORT", "8099")),
    )
