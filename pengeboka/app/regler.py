"""Butikknavn og kategorier – rene regler, ingen AI.

Teksten fra banken er full av støy («Visa 4925 12.10 NOK 249,00 KIWI 505 SENTRUM Kurs: 1.0000»).
rydd() fjerner støyen, motpart() finner et pent navn («Kiwi»), og kategoriser() bruker
først familiens egne regler, så de innebygde.
"""
from __future__ import annotations

import re
import unicodedata

# ---------------------------------------------------------------- kategorier
# (navn, ikon, gruppe). Gruppe: utgift | inntekt | sparing | overforing
KATEGORIER = [
    ("Dagligvarer", "🛒", "utgift"),
    ("Bolig", "🏠", "utgift"),
    ("Lån", "🏦", "utgift"),
    ("Strøm", "⚡", "utgift"),
    ("Bil og transport", "🚗", "utgift"),
    ("Barn", "🧸", "utgift"),
    ("Forsikring", "🛡️", "utgift"),
    ("Abonnementer", "📺", "utgift"),
    ("Helse", "💊", "utgift"),
    ("Hjem og klær", "👕", "utgift"),
    ("Mat ute og kos", "🍕", "utgift"),
    ("Fritid og ferie", "✈️", "utgift"),
    ("Annet", "📦", "utgift"),
    ("Lønn", "💼", "inntekt"),
    ("Stønader", "👶", "inntekt"),
    ("Annen inntekt", "💰", "inntekt"),
    ("Sparing", "🐷", "sparing"),
    ("Overføring", "🔁", "overforing"),
]
OVERFORING = "Overføring"
SPARING = "Sparing"
LAN = "Lån"

# ---------------------------------------------------------------- kjente navn
# (mønster i ryddet tekst, pent navn, kategori). Lengste mønster vinner.
KJENTE: list[tuple[str, str, str]] = [
    # Dagligvarer
    ("kiwi", "Kiwi", "Dagligvarer"), ("rema 1000", "Rema 1000", "Dagligvarer"), ("rema", "Rema 1000", "Dagligvarer"),
    ("coop extra", "Coop Extra", "Dagligvarer"), ("coop mega", "Coop Mega", "Dagligvarer"),
    ("coop prix", "Coop Prix", "Dagligvarer"), ("coop obs bygg", "Obs Bygg", "Hjem og klær"),
    ("obs bygg", "Obs Bygg", "Hjem og klær"), ("coop obs", "Obs", "Dagligvarer"),
    ("coop marked", "Coop Marked", "Dagligvarer"), ("extra", "Coop Extra", "Dagligvarer"),
    ("coop", "Coop", "Dagligvarer"), ("meny", "Meny", "Dagligvarer"), ("eurospar", "Spar", "Dagligvarer"),
    ("spar", "Spar", "Dagligvarer"), ("joker", "Joker", "Dagligvarer"), ("bunnpris", "Bunnpris", "Dagligvarer"),
    ("oda", "Oda", "Dagligvarer"), ("matkroken", "Matkroken", "Dagligvarer"),
    ("nærbutikken", "Nærbutikken", "Dagligvarer"), ("narbutikken", "Nærbutikken", "Dagligvarer"),
    ("holdbart", "Holdbart", "Dagligvarer"), ("gigaboks", "Gigaboks", "Dagligvarer"),
    # Strøm
    ("tibber", "Tibber", "Strøm"), ("fjordkraft", "Fjordkraft", "Strøm"), ("norgesnett", "Norgesnett", "Strøm"),
    ("elvia", "Elvia", "Strøm"), ("hafslund", "Hafslund", "Strøm"), ("fortum", "Fortum", "Strøm"),
    ("lyse", "Lyse", "Strøm"), ("tensio", "Tensio", "Strøm"), ("glitre", "Glitre", "Strøm"),
    ("agva", "Agva", "Strøm"), ("bkk", "BKK", "Strøm"), ("motkraft", "Motkraft", "Strøm"),
    ("ishavskraft", "Ishavskraft", "Strøm"), ("kildenett", "Kildenett", "Strøm"),
    # Bil og transport
    ("circle k", "Circle K", "Bil og transport"), ("esso", "Esso", "Bil og transport"),
    ("shell", "Shell", "Bil og transport"), ("uno-x", "Uno-X", "Bil og transport"), ("unox", "Uno-X", "Bil og transport"),
    ("st1", "St1", "Bil og transport"), ("yx", "YX", "Bil og transport"), ("tesla", "Tesla", "Bil og transport"),
    ("teslemetry", "Teslemetry", "Abonnementer"),
    ("easypark", "EasyPark", "Bil og transport"), ("apcoa", "Apcoa", "Bil og transport"),
    ("onepark", "OnePark", "Bil og transport"), ("aimo park", "Aimo Park", "Bil og transport"),
    ("autopass", "AutoPASS", "Bil og transport"), ("fjellinjen", "Fjellinjen", "Bil og transport"),
    ("ferde", "Ferde", "Bil og transport"), ("skyttel", "Skyttel", "Bil og transport"),
    ("bompenger", "Bompenger", "Bil og transport"), ("ruter", "Ruter", "Bil og transport"),
    ("flytoget", "Flytoget", "Bil og transport"), ("vy", "Vy", "Bil og transport"),
    ("entur", "Entur", "Bil og transport"), ("mekonomen", "Mekonomen", "Bil og transport"),
    ("biltema", "Biltema", "Bil og transport"), ("vianor", "Vianor", "Bil og transport"),
    ("dekkmann", "Dekkmann", "Bil og transport"), ("statens vegvesen", "Statens vegvesen", "Bil og transport"),
    ("mer", "Mer", "Bil og transport"), ("recharge", "Recharge", "Bil og transport"),
    ("ionity", "Ionity", "Bil og transport"), ("kople", "Kople", "Bil og transport"),
    # Forsikring
    ("gjensidige", "Gjensidige", "Forsikring"), ("fremtind", "Fremtind", "Forsikring"),
    ("tryg", "Tryg", "Forsikring"), ("if skadeforsikring", "If", "Forsikring"), ("if forsikring", "If", "Forsikring"),
    ("storebrand forsikring", "Storebrand", "Forsikring"), ("frende", "Frende", "Forsikring"),
    ("codan", "Codan", "Forsikring"), ("eika forsikring", "Eika", "Forsikring"), ("forsikring", "Forsikring", "Forsikring"),
    # Abonnementer
    ("netflix", "Netflix", "Abonnementer"), ("spotify", "Spotify", "Abonnementer"), ("viaplay", "Viaplay", "Abonnementer"),
    ("disney", "Disney+", "Abonnementer"), ("hbo", "Max", "Abonnementer"), ("tv 2 play", "TV 2 Play", "Abonnementer"),
    ("tv2 play", "TV 2 Play", "Abonnementer"), ("apple.com/bill", "Apple", "Abonnementer"), ("apple.com", "Apple", "Abonnementer"),
    ("google", "Google", "Abonnementer"), ("youtube", "YouTube", "Abonnementer"), ("telia", "Telia", "Abonnementer"),
    ("telenor", "Telenor", "Abonnementer"), ("talkmore", "Talkmore", "Abonnementer"), ("chili mobil", "Chili", "Abonnementer"),
    ("mycall", "MyCall", "Abonnementer"), ("ice.no", "Ice", "Abonnementer"), ("ice norge", "Ice", "Abonnementer"),
    ("altibox", "Altibox", "Abonnementer"), ("strim", "Strim", "Abonnementer"), ("storytel", "Storytel", "Abonnementer"),
    ("bookbeat", "BookBeat", "Abonnementer"), ("nabu casa", "Nabu Casa", "Abonnementer"), ("anthropic", "Anthropic", "Abonnementer"),
    ("claude.ai", "Claude", "Abonnementer"), ("openai", "OpenAI", "Abonnementer"), ("microsoft", "Microsoft", "Abonnementer"),
    ("dropbox", "Dropbox", "Abonnementer"), ("aftenposten", "Aftenposten", "Abonnementer"), ("vg+", "VG+", "Abonnementer"),
    ("schibsted", "Schibsted", "Abonnementer"), ("amedia", "Amedia", "Abonnementer"), ("sats", "SATS", "Abonnementer"),
    ("evo fitness", "EVO", "Abonnementer"), ("fresh fitness", "Fresh Fitness", "Abonnementer"),
    # Helse
    ("apotek 1", "Apotek 1", "Helse"), ("vitusapotek", "Vitusapotek", "Helse"), ("boots", "Boots", "Helse"),
    ("apotek", "Apotek", "Helse"), ("legesenter", "Legesenter", "Helse"), ("legevakt", "Legevakt", "Helse"),
    ("tannlege", "Tannlege", "Helse"), ("tannhelse", "Tannhelse", "Helse"), ("fysioterapi", "Fysioterapi", "Helse"),
    ("optiker", "Optiker", "Helse"), ("specsavers", "Specsavers", "Helse"), ("brilleland", "Brilleland", "Helse"),
    # Hjem og klær
    ("h&m", "H&M", "Hjem og klær"), ("cubus", "Cubus", "Hjem og klær"), ("kappahl", "KappAhl", "Hjem og klær"),
    ("lindex", "Lindex", "Hjem og klær"), ("dressmann", "Dressmann", "Hjem og klær"), ("zara", "Zara", "Hjem og klær"),
    ("bik bok", "Bik Bok", "Hjem og klær"), ("carlings", "Carlings", "Hjem og klær"), ("ikea", "IKEA", "Hjem og klær"),
    ("jysk", "Jysk", "Hjem og klær"), ("clas ohlson", "Clas Ohlson", "Hjem og klær"), ("jula", "Jula", "Hjem og klær"),
    ("europris", "Europris", "Hjem og klær"), ("nille", "Nille", "Hjem og klær"), ("normal", "Normal", "Hjem og klær"),
    ("rusta", "Rusta", "Hjem og klær"), ("kid interiør", "Kid", "Hjem og klær"), ("princess", "Princess", "Hjem og klær"),
    ("elkjøp", "Elkjøp", "Hjem og klær"), ("elkjop", "Elkjøp", "Hjem og klær"), ("power", "Power", "Hjem og klær"),
    ("komplett", "Komplett", "Hjem og klær"), ("byggmakker", "Byggmakker", "Hjem og klær"), ("maxbo", "Maxbo", "Hjem og klær"),
    ("montér", "Montér", "Hjem og klær"), ("monter", "Montér", "Hjem og klær"), ("felleskjøpet", "Felleskjøpet", "Hjem og klær"),
    ("plantasjen", "Plantasjen", "Hjem og klær"), ("skeidar", "Skeidar", "Hjem og klær"), ("bohus", "Bohus", "Hjem og klær"),
    ("zalando", "Zalando", "Hjem og klær"), ("boozt", "Boozt", "Hjem og klær"), ("temu", "Temu", "Hjem og klær"),
    ("amazon", "Amazon", "Hjem og klær"), ("xxl", "XXL", "Fritid og ferie"), ("intersport", "Intersport", "Fritid og ferie"),
    ("sport 1", "Sport 1", "Fritid og ferie"), ("anton sport", "Anton Sport", "Fritid og ferie"),
    # Barn
    ("barnehage", "Barnehage", "Barn"), ("sfo", "SFO", "Barn"), ("aktivitetsskole", "AKS", "Barn"),
    ("jollyroom", "Jollyroom", "Barn"), ("babyshop", "Babyshop", "Barn"), ("lekia", "Lekia", "Barn"),
    ("br-leker", "BR-Leker", "Barn"), ("br leker", "BR-Leker", "Barn"), ("ringo", "Ringo", "Barn"),
    ("lekekassen", "Lekekassen", "Barn"), ("name it", "Name It", "Barn"), ("polarn", "Polarn O. Pyret", "Barn"),
    ("spond", "Spond", "Barn"), ("idrettslag", "Idrettslag", "Barn"), ("korps", "Korps", "Barn"),
    # Mat ute og kos
    ("mcdonald", "McDonald's", "Mat ute og kos"), ("burger king", "Burger King", "Mat ute og kos"),
    ("max burger", "Max", "Mat ute og kos"), ("peppes", "Peppes", "Mat ute og kos"), ("dolly dimple", "Dolly Dimple's", "Mat ute og kos"),
    ("egon", "Egon", "Mat ute og kos"), ("foodora", "Foodora", "Mat ute og kos"), ("wolt", "Wolt", "Mat ute og kos"),
    ("just eat", "Just Eat", "Mat ute og kos"), ("starbucks", "Starbucks", "Mat ute og kos"),
    ("espresso house", "Espresso House", "Mat ute og kos"), ("kaffebrenneriet", "Kaffebrenneriet", "Mat ute og kos"),
    ("narvesen", "Narvesen", "Mat ute og kos"), ("7-eleven", "7-Eleven", "Mat ute og kos"), ("7 eleven", "7-Eleven", "Mat ute og kos"),
    ("deli de luca", "Deli de Luca", "Mat ute og kos"), ("vinmonopolet", "Vinmonopolet", "Mat ute og kos"),
    ("sushi", "Sushi", "Mat ute og kos"), ("pizza", "Pizza", "Mat ute og kos"), ("kebab", "Kebab", "Mat ute og kos"),
    ("restaurant", "Restaurant", "Mat ute og kos"), ("cafe", "Kafé", "Mat ute og kos"), ("kafe", "Kafé", "Mat ute og kos"),
    ("bakeri", "Bakeri", "Mat ute og kos"), ("bakeriet", "Bakeri", "Mat ute og kos"),
    # Fritid og ferie
    ("kino", "Kino", "Fritid og ferie"), ("nordisk film", "Nordisk Film Kino", "Fritid og ferie"),
    ("odeon", "Odeon", "Fritid og ferie"), ("ticketmaster", "Ticketmaster", "Fritid og ferie"),
    ("billettservice", "Billettservice", "Fritid og ferie"), ("norwegian air", "Norwegian", "Fritid og ferie"),
    ("sas ", "SAS", "Fritid og ferie"), ("widerøe", "Widerøe", "Fritid og ferie"), ("wideroe", "Widerøe", "Fritid og ferie"),
    ("booking.com", "Booking.com", "Fritid og ferie"), ("airbnb", "Airbnb", "Fritid og ferie"),
    ("hotel", "Hotell", "Fritid og ferie"), ("hotell", "Hotell", "Fritid og ferie"), ("scandic", "Scandic", "Fritid og ferie"),
    ("thon", "Thon", "Fritid og ferie"), ("strawberry", "Strawberry", "Fritid og ferie"),
    ("steam", "Steam", "Fritid og ferie"), ("playstation", "PlayStation", "Fritid og ferie"),
    ("nintendo", "Nintendo", "Fritid og ferie"), ("lego", "LEGO", "Fritid og ferie"),
    ("tusenfryd", "Tusenfryd", "Fritid og ferie"), ("badeland", "Badeland", "Fritid og ferie"),
    # Lån og bolig
    ("boliglån", "Boliglån", "Lån"), ("boliglan", "Boliglån", "Lån"), ("billån", "Billån", "Lån"),
    ("lånekassen", "Lånekassen", "Lån"), ("lanekassen", "Lånekassen", "Lån"), ("studielån", "Studielån", "Lån"),
    ("husleie", "Husleie", "Bolig"), ("felleskost", "Felleskostnader", "Bolig"),
    ("kommunale avgifter", "Kommunale avgifter", "Bolig"), ("eiendomsskatt", "Eiendomsskatt", "Bolig"),
    ("obos", "OBOS", "Bolig"), ("usbl", "USBL", "Bolig"), ("boligbyggelag", "Boligbyggelag", "Bolig"),
    ("feiing", "Feiing", "Bolig"), ("renovasjon", "Renovasjon", "Bolig"), ("verisure", "Verisure", "Bolig"),
    ("sector alarm", "Sector Alarm", "Bolig"),
    # Inntekt
    ("lønn", "Lønn", "Lønn"), ("lonn", "Lønn", "Lønn"), ("barnetrygd", "Barnetrygd", "Stønader"),
    ("kontantstøtte", "Kontantstøtte", "Stønader"), ("foreldrepenger", "Foreldrepenger", "Stønader"),
    ("nav", "NAV", "Stønader"), ("skatteetaten", "Skatteetaten", "Annen inntekt"),
]

# Kategorier som bare gir mening for penger inn (eller ut)
BARE_INN = {"Lønn", "Stønader", "Annen inntekt"}

# Ord som ofte står i overføringer mellom egne kontoer
OVERFORINGSORD = ("overføring", "overforing", "egen konto", "egne kontoer", "fra konto", "til konto",
                  "nettbank til", "nettbank fra", "mobilbank", "sparing", "innbetaling kredittkort",
                  "kredittkort", "betaling kort", "straksoverføring")

# ---------------------------------------------------------------- rydding
_STOY_START = re.compile(
    r"^(?:(?:varekjøp|varekjop|kortkjøp|kortkjop|reservasjon|visa|mastercard|bankaxept|debit|"
    r"avtalegiro|efaktura|e-faktura|nettgiro|giro|betaling|straksbetaling|kjøp|kjop|"
    r"apple pay|google pay|kontaktløs|kontaktlos)\b[\s:*]*)+", re.I)
_KORT = re.compile(r"\*?\b\d{4,}\b\*?")                       # kortnummer, butikknummer, referanser
_BELOP = re.compile(r"\b(?:nok|sek|eur|usd|dkk|gbp)\s*-?[\d\s.,]+", re.I)
_KURS = re.compile(r"\bkurs[:\s]*[\d.,]+", re.I)
_DATO = re.compile(r"\b\d{1,2}[./]\d{1,2}(?:[./]\d{2,4})?\b|\bdato\b|\bkl\.?\s*\d{1,2}[:.]\d{2}\b", re.I)
_TEGN = re.compile(r"[\s,;:*#|]+")


def _norm(s: str) -> str:
    return unicodedata.normalize("NFC", s or "").strip()


def rydd(tekst: str) -> str:
    """Fjerner støy fra banktekst og gir små bokstaver. Brukes til regler og gruppering."""
    t = _norm(tekst).lower()
    t = _BELOP.sub(" ", t)
    t = _KURS.sub(" ", t)
    t = _DATO.sub(" ", t)
    t = _STOY_START.sub("", t.strip())
    t = _KORT.sub(" ", t)
    t = _STOY_START.sub("", t.strip())
    return _TEGN.sub(" ", t).strip()


def _sok(monster: str, tekst: str):
    """Mønsteret må stå som egne ord: «kiwi» treffer «kiwi sentrum», ikke «kiwiplanter»."""
    m = monster.strip().lower()
    if not m:
        return None
    return re.search(r"(?<![\wæøå])" + re.escape(m) + r"(?![\wæøå])", tekst)


def _treff(monster: str, tekst: str) -> bool:
    return _sok(monster, tekst) is not None


def kjent(ryddet: str) -> tuple[str, str] | None:
    """(pent navn, kategori) for kjente butikker og regninger. Første treff i teksten vinner,
    og ved likt sted det lengste mønsteret («rema 1000» før «rema»)."""
    best = None
    for monster, navn, kat in KJENTE:
        m = _sok(monster, ryddet)
        if m and (best is None or (m.start(), -len(monster)) < best[0]):
            best = ((m.start(), -len(monster)), navn, kat)
    return (best[1], best[2]) if best else None


_FORKORTELSER = {"as", "asa", "sfo", "nav", "aks", "sas", "dnb", "obos", "ikea", "xxl", "bkk", "usbl"}


def _pen(ord: str) -> str:
    if ord in _FORKORTELSER:
        return ord.upper()
    return "-".join(d[:1].upper() + d[1:] for d in ord.split("-"))


def motpart(tekst: str) -> str:
    """Et kort, pent navn på mottaker/avsender: «KIWI 505 SENTRUM» → «Kiwi»."""
    r = rydd(tekst)
    vipps = re.match(r"^vipps\W*(.*)$", r)
    if vipps:
        rest = [o for o in vipps.group(1).split() if o not in ("as", "asa")][:3]
        return "Vipps: " + " ".join(_pen(o) for o in rest) if rest else "Vipps"
    k = kjent(r)
    if k:
        return k[0]
    # Samme rydding som over, men tall blir et skille: ord etter butikknummeret er som regel stedet
    t = _norm(tekst).lower()
    t = _DATO.sub(" ", _KURS.sub(" ", _BELOP.sub(" ", t)))
    t = _STOY_START.sub("", t.strip())
    t = _KORT.sub(" | ", t)
    t = _STOY_START.sub("", t.strip(" |"))
    ordene: list[str] = []
    for o in t.split():
        if o == "|" or any(ch.isdigit() for ch in o):
            if ordene:
                break
            continue
        o = o.strip(",.;:*#")
        if o and not (ordene and o in ("as", "asa")):
            ordene.append(o)
        if len(ordene) == 3:
            break
    navn = " ".join(_pen(o) for o in ordene).strip()
    return navn or (_norm(tekst)[:40] or "Ukjent")


def kategoriser(tekst: str, belop_ore: int, egne: list[dict]) -> tuple[str | None, int | None]:
    """(kategorinavn, regel_id). egne = familiens regler [{id, monster, kategori}], lengste først."""
    r = rydd(tekst)
    lav = _norm(tekst).lower()
    for regel in egne:
        if _treff(regel["monster"], r) or _treff(regel["monster"], lav):
            return regel["kategori"], regel["id"]
    k = kjent(r)
    if k:
        kat = k[1]
        if kat in BARE_INN and belop_ore < 0:
            return None, None
        return kat, None
    return None, None


def ser_ut_som_overforing(tekst: str) -> bool:
    lav = _norm(tekst).lower()
    return any(o in lav for o in OVERFORINGSORD)
