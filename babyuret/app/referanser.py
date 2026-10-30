"""Referanseverdier fra helsemyndigheter og anerkjente fagmiljøer.

Kun tall som står i kildene under. Appen bruker dem til å vise hva som
er vanlig for alderen – aldri som diagnose. Ved bekymring: kontakt
helsestasjonen eller lege.
"""
from __future__ import annotations

KILDER = {
    "helsenorge_sovn": {
        "navn": "Helsenorge: Søvn hos barn 0–2 år",
        "url": "https://www.helsenorge.no/barn/sovn-hos-barn/",
    },
    "hdir_vekt_nyfodt": {
        "navn": "Helsedirektoratet: Oppfølging av vekt hos friske, ammede nyfødte født til termin",
        "url": "https://www.helsedirektoratet.no/forebygging-diagnose-og-behandling/svangerskap-fodsel-og-barsel/amming-og-spedbarnsernaering/oppfolging-av-vekt-hos-friske-ammede-nyfodte-som-er-fodt-til-termin",
    },
    "hdir_veiing": {
        "navn": "Helsedirektoratet: Veiing og måling i helsestasjon (WHO-vekstkurver)",
        "url": "https://www.helsedirektoratet.no/retningslinjer/helsestasjons-og-skolehelsetjenesten/helsestasjon-05-ar/veiing-og-maling",
    },
    "who_vekst": {
        "navn": "WHO Child Growth Standards",
        "url": "https://www.who.int/tools/child-growth-standards",
    },
    "helsenorge_feber": {
        "navn": "Helsenorge: Feber hos barn",
        "url": "https://www.helsenorge.no/sykdom/barn/feber-hos-barn/",
    },
}

# Helsenorge: søvn per døgn. (fra_dag, til_dag, vanlig, normalområde) i timer.
SOVN_PER_DOGN = [
    (0, 91, (14, 17), (11, 19), "0–3 måneder"),
    (91, 183, (12, 15), (10, 18), "3–6 måneder"),
    (183, 365, (12, 15), (10, 18), "6–12 måneder"),
    (365, 731, (11, 14), (10, 16), "1–2 år"),
]

# Helsenorge: våkenperioder hos nyfødte varer ofte 30–60 minutter.
NYFODT_VAAKENPERIODE_MIN = (30, 60)
NYFODT_VAAKEN_TIL_DAG = 91  # brukes som startestimat de første tre månedene

# Helsenorge: nyfødte som ammes, spiser minst 8–12 ganger i døgnet.
NYFODT_AMMING_PER_DOGN = (8, 12)
NYFODT_TIL_DAG = 28

# Helsedirektoratet: vekttap etter fødsel.
VEKTTAP_NORMALT_PROSENT = 10    # inntil 10 % de første dagene regnes som normalt
VEKTTAP_TETTERE_PROSENT = 8     # fra 8 % kan tettere oppfølging av ammingen være aktuelt
FODSELSVEKT_IGJEN_DAG = 14      # ca. 90 % er tilbake på fødselsvekt innen 14 dager

# Helsenorge: feber = 38,0 °C eller mer målt i endetarmen. Kontakt lege ved
# feber hos barn som er 3 måneder eller yngre.
FEBER_GRENSE = 38.0
FEBER_LEGE_TIL_DAG = 92

# Helsedirektoratet anbefaler WHO-kurver med sju persentiler for vekt og lengde.
PERSENTILER = [3, 10, 25, 50, 75, 90, 97]


def sovn_referanse(alder_dager: int | None) -> dict | None:
    if alder_dager is None or alder_dager < 0:
        return None
    for fra, til, vanlig, normal, navn in SOVN_PER_DOGN:
        if fra <= alder_dager < til:
            return {
                "aldersgruppe": navn,
                "vanlig": list(vanlig),
                "normal": list(normal),
                "tekst": f"De fleste barn på {navn} sover {vanlig[0]}–{vanlig[1]} timer i døgnet, "
                         f"men {normal[0]}–{normal[1]} timer er også normalt.",
                "kilde": "helsenorge_sovn",
            }
    return None
