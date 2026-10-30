"""Innstillinger for Babyuret.

Alt redigeres inne i appen (fanen «Innstillinger») og lagres i appens
egen database. Personlige verdier (navn, fødselsdato) ligger dermed
aldri i koden.
"""
from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from datetime import date
from pathlib import Path

KL = re.compile(r"^([01]\d|2[0-3]):[0-5]\d$")


class UgyldigInnstilling(ValueError):
    pass


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
        return {
            "baby_navn": self.baby_navn,
            "fodselsdato": self.fodselsdato.isoformat() if self.fodselsdato else None,
            "mating": self.mating,
            "standard_flaske_ml": self.standard_flaske_ml,
            "nattmodus_fra": self.nattmodus_fra,
            "nattmodus_til": self.nattmodus_til,
        }

    def oppdater(self, d: dict) -> dict:
        """Valider og bruk nye verdier. Returnerer det som faktisk ble endret."""
        ny: dict = {}
        if "baby_navn" in d:
            navn = str(d["baby_navn"] or "").strip()
            if len(navn) > 40:
                raise UgyldigInnstilling("Navnet kan være maks 40 tegn")
            ny["baby_navn"] = navn
        if "fodselsdato" in d:
            v = d["fodselsdato"]
            if v in (None, ""):
                ny["fodselsdato"] = None
            else:
                try:
                    ny["fodselsdato"] = date.fromisoformat(str(v))
                except ValueError:
                    raise UgyldigInnstilling("Ugyldig dato")
        if "mating" in d:
            if d["mating"] not in ("amming", "flaske", "begge"):
                raise UgyldigInnstilling("Mating må være amming, flaske eller begge")
            ny["mating"] = d["mating"]
        if "standard_flaske_ml" in d:
            try:
                ml = int(d["standard_flaske_ml"])
            except (TypeError, ValueError):
                raise UgyldigInnstilling("Ugyldig mengde")
            if not 10 <= ml <= 400:
                raise UgyldigInnstilling("Flaskemengden må være mellom 10 og 400 ml")
            ny["standard_flaske_ml"] = ml
        for felt in ("nattmodus_fra", "nattmodus_til"):
            if felt in d:
                if not KL.match(str(d[felt] or "")):
                    raise UgyldigInnstilling("Klokkeslett må være på formen TT:MM")
                ny[felt] = d[felt]
        for k, v in ny.items():
            setattr(self, k, v)
        return ny

    def til_lagring(self) -> dict:
        return self.offentlig()


def les() -> Innstillinger:
    data_dir = Path(os.environ.get("BABYURET_DATA", "/data"))
    if not data_dir.exists():
        data_dir = Path(__file__).resolve().parent.parent / "data"
    data_dir.mkdir(parents=True, exist_ok=True)
    cfg = Innstillinger(data_dir=data_dir, port=int(os.environ.get("BABYURET_PORT", "8099")))

    # Eldre versjon (0.1.0) hadde innstillingene i HA – ta dem med hvis de finnes.
    options = data_dir / "options.json"
    if options.exists():
        try:
            gamle = json.loads(options.read_text(encoding="utf-8"))
            cfg.oppdater({k: v for k, v in gamle.items() if v not in (None, "")})
        except (OSError, json.JSONDecodeError, UgyldigInnstilling):
            pass
    return cfg
