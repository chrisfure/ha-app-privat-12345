"""Målinger: vekt, lengde, hodeomkrets og temperatur."""
from __future__ import annotations

from datetime import datetime, timedelta

import referanser as ref
from db import fra_iso, naa

TYPER = {
    #  type        enhet  min    max     navn
    "vekt":       ("g",   400,   30000, "Vekt"),
    "lengde":     ("cm",  25,    130,   "Lengde"),
    "hode":       ("cm",  20,    60,    "Hodeomkrets"),
    "temperatur": ("°C",  33,    43,    "Temperatur"),
}


class UgyldigMaaling(ValueError):
    pass


def valider(type_: str, verdi, tid: str | None) -> tuple[float, datetime]:
    if type_ not in TYPER:
        raise UgyldigMaaling("Ukjent måletype")
    try:
        v = float(str(verdi).replace(",", "."))
    except (TypeError, ValueError):
        raise UgyldigMaaling("Ugyldig verdi")
    enhet, lo, hi, navn = TYPER[type_]
    if not lo <= v <= hi:
        raise UgyldigMaaling(f"{navn} må være mellom {lo} og {hi} {enhet}")
    t = fra_iso(tid) if tid else naa()
    if t > naa() + timedelta(minutes=5):
        raise UgyldigMaaling("Tidspunktet kan ikke være i fremtiden")
    return round(v, 2), t


def _k(v: float, des: int = 1) -> str:
    return f"{v:.{des}f}".replace(".", ",")


def vurderinger(bu) -> list[dict]:
    """Nøytrale merknader basert på offentlige anbefalinger."""
    ut: list[dict] = []
    alder = bu.alder()
    if not alder or alder["dager"] < 0:
        return ut
    dager = alder["dager"]
    fodsel = bu.cfg.fodselsdato
    alle = bu.db.maalinger()

    # --- vekttap etter fødsel (første tre uker)
    vekter = [m for m in alle if m["type"] == "vekt"]
    if vekter and dager <= 21:
        fodselsvekt = next(
            (m for m in vekter
             if (fra_iso(m["tid"]).astimezone(bu.tz).date() - fodsel).days <= 1), None)
        siste = vekter[-1]
        if fodselsvekt and siste["id"] != fodselsvekt["id"]:
            pst = (siste["verdi"] - fodselsvekt["verdi"]) / fodselsvekt["verdi"] * 100
            tekst = f"{_k(abs(pst))} % {'under' if pst < 0 else 'over'} fødselsvekt."
            niva = "info"
            if pst < 0:
                tekst += (f" Helsedirektoratet: vekttap på inntil {ref.VEKTTAP_NORMALT_PROSENT} % de første "
                          f"dagene regnes som normalt, og ca. 9 av 10 er tilbake på fødselsvekt innen "
                          f"{ref.FODSELSVEKT_IGJEN_DAG} dager.")
                if -pst >= ref.VEKTTAP_NORMALT_PROSENT or (dager >= ref.FODSELSVEKT_IGJEN_DAG):
                    niva = "kontakt"
                    tekst += " Ta kontakt med helsestasjonen eller barselavdelingen for oppfølging."
                elif -pst >= ref.VEKTTAP_TETTERE_PROSENT:
                    niva = "obs"
                    tekst += (f" Fra {ref.VEKTTAP_TETTERE_PROSENT} % kan tettere oppfølging av ammingen "
                              "være aktuelt – nevn det for jordmor eller helsestasjonen.")
            ut.append({"type": "vekt", "niva": niva, "tekst": tekst, "kilde": "hdir_vekt_nyfodt"})

    # --- feber hos de minste
    temp = [m for m in alle if m["type"] == "temperatur"]
    if temp:
        siste = temp[-1]
        fersk = naa() - fra_iso(siste["tid"]) < timedelta(hours=12)
        if fersk and siste["verdi"] >= ref.FEBER_GRENSE:
            if dager <= ref.FEBER_LEGE_TIL_DAG:
                ut.append({"type": "temperatur", "niva": "kontakt",
                           "tekst": f"{_k(siste['verdi'])} °C. Helsenorge: kontakt lege hvis et barn som er "
                                    "3 måneder eller yngre har feber (38,0 °C eller mer målt i endetarmen). "
                                    "Ved akutt fare: ring 113. Legevakt: 116 117.",
                           "kilde": "helsenorge_feber"})
            else:
                ut.append({"type": "temperatur", "niva": "obs",
                           "tekst": f"{_k(siste['verdi'])} °C regnes som feber (38,0 °C eller mer målt i endetarmen). "
                                    "Kontakt lege ved nedsatt allmenntilstand, f.eks. dårlig kontakt, lite å drikke "
                                    "eller få våte bleier.",
                           "kilde": "helsenorge_feber"})
    return ut
