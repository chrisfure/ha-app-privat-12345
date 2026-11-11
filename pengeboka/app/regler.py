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
    ("Renter og gebyrer", "🧾", "utgift"),
    ("Strøm", "⚡", "utgift"),
    ("Bil", "🚗", "utgift"),
    ("Kollektivtransport", "🚌", "utgift"),
    ("Barn", "🧸", "utgift"),
    ("Forsikring", "🛡️", "utgift"),
    ("Abonnementer", "📺", "utgift"),
    ("Helse", "💊", "utgift"),
    ("Personlig pleie", "💇", "utgift"),
    ("Klær og sko", "👕", "utgift"),
    ("Hjem og interiør", "🛋️", "utgift"),
    ("Hus og hage", "🔨", "utgift"),
    ("Mat ute og kos", "🍕", "utgift"),
    ("Kafé og kiosk", "☕", "utgift"),
    ("Fritid og ferie", "✈️", "utgift"),
    ("Gaver", "🎁", "utgift"),
    ("Kjæledyr", "🐾", "utgift"),
    ("Annet", "📦", "utgift"),
    ("Lønn", "💼", "inntekt"),
    ("Stønader", "👶", "inntekt"),
    ("Annen inntekt", "💰", "inntekt"),
    ("Sparing", "🐷", "sparing"),
    ("Overføring", "🔁", "overforing"),
]
# Kategorier som har byttet navn (gammelt → nytt). Brukes når en eldre database oppgraderes.
NYTT_NAVN = {"Hjem og klær": "Hjem og interiør", "Bil og transport": "Bil"}
KATEGORI_VERSJON = 2
OVERFORING = "Overføring"
SPARING = "Sparing"
LAN = "Lån"

# ---------------------------------------------------------------- kjente navn
# (mønster i ryddet tekst, pent navn, kategori). Lengste mønster vinner.
KJENTE: list[tuple[str, str, str]] = [
    # Dagligvarer
    ("kiwi", "Kiwi", "Dagligvarer"), ("rema 1000", "Rema 1000", "Dagligvarer"), ("rema", "Rema 1000", "Dagligvarer"),
    ("coop extra", "Coop Extra", "Dagligvarer"), ("coop mega", "Coop Mega", "Dagligvarer"),
    ("coop prix", "Coop Prix", "Dagligvarer"), ("coop obs bygg", "Obs Bygg", "Hus og hage"),
    ("obs bygg", "Obs Bygg", "Hus og hage"), ("coop obs", "Obs", "Dagligvarer"),
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
    ("circle k", "Circle K", "Bil"), ("esso", "Esso", "Bil"),
    ("shell", "Shell", "Bil"), ("uno-x", "Uno-X", "Bil"), ("unox", "Uno-X", "Bil"),
    ("st1", "St1", "Bil"), ("yx", "YX", "Bil"), ("tesla", "Tesla", "Bil"),
    ("teslemetry", "Teslemetry", "Abonnementer"),
    ("easypark", "EasyPark", "Bil"), ("apcoa", "Apcoa", "Bil"),
    ("onepark", "OnePark", "Bil"), ("aimo park", "Aimo Park", "Bil"),
    ("autopass", "AutoPASS", "Bil"), ("fjellinjen", "Fjellinjen", "Bil"),
    ("ferde", "Ferde", "Bil"), ("skyttel", "Skyttel", "Bil"),
    ("bompenger", "Bompenger", "Bil"), ("ruter", "Ruter", "Kollektivtransport"),
    ("flytoget", "Flytoget", "Kollektivtransport"), ("vy", "Vy", "Kollektivtransport"),
    ("entur", "Entur", "Kollektivtransport"), ("mekonomen", "Mekonomen", "Bil"),
    ("biltema", "Biltema", "Bil"), ("vianor", "Vianor", "Bil"),
    ("dekkmann", "Dekkmann", "Bil"), ("statens vegvesen", "Statens vegvesen", "Bil"),
    ("mer", "Mer", "Bil"), ("recharge", "Recharge", "Bil"),
    ("ionity", "Ionity", "Bil"), ("kople", "Kople", "Bil"),
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
    ("h&m", "H&M", "Klær og sko"), ("cubus", "Cubus", "Klær og sko"), ("kappahl", "KappAhl", "Klær og sko"),
    ("lindex", "Lindex", "Klær og sko"), ("dressmann", "Dressmann", "Klær og sko"), ("zara", "Zara", "Klær og sko"),
    ("bik bok", "Bik Bok", "Klær og sko"), ("carlings", "Carlings", "Klær og sko"), ("ikea", "IKEA", "Hjem og interiør"),
    ("jysk", "Jysk", "Hjem og interiør"), ("clas ohlson", "Clas Ohlson", "Hus og hage"), ("jula", "Jula", "Hus og hage"),
    ("europris", "Europris", "Hjem og interiør"), ("nille", "Nille", "Hjem og interiør"), ("normal", "Normal", "Personlig pleie"),
    ("rusta", "Rusta", "Hjem og interiør"), ("kid interiør", "Kid", "Hjem og interiør"), ("princess", "Princess", "Hjem og interiør"),
    ("elkjøp", "Elkjøp", "Hjem og interiør"), ("elkjop", "Elkjøp", "Hjem og interiør"), ("power", "Power", "Hjem og interiør"),
    ("komplett", "Komplett", "Hjem og interiør"), ("byggmakker", "Byggmakker", "Hus og hage"), ("maxbo", "Maxbo", "Hus og hage"),
    ("montér", "Montér", "Hus og hage"), ("monter", "Montér", "Hus og hage"), ("felleskjøpet", "Felleskjøpet", "Hus og hage"),
    ("plantasjen", "Plantasjen", "Hus og hage"), ("skeidar", "Skeidar", "Hjem og interiør"), ("bohus", "Bohus", "Hjem og interiør"),
    ("zalando", "Zalando", "Klær og sko"), ("boozt", "Boozt", "Klær og sko"), ("temu", "Temu", "Hjem og interiør"),
    ("amazon", "Amazon", "Hjem og interiør"), ("xxl", "XXL", "Fritid og ferie"), ("intersport", "Intersport", "Fritid og ferie"),
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
    ("just eat", "Just Eat", "Mat ute og kos"), ("starbucks", "Starbucks", "Kafé og kiosk"),
    ("espresso house", "Espresso House", "Kafé og kiosk"), ("kaffebrenneriet", "Kaffebrenneriet", "Kafé og kiosk"),
    ("narvesen", "Narvesen", "Kafé og kiosk"), ("7-eleven", "7-Eleven", "Kafé og kiosk"), ("7 eleven", "7-Eleven", "Kafé og kiosk"),
    ("deli de luca", "Deli de Luca", "Kafé og kiosk"), ("vinmonopolet", "Vinmonopolet", "Mat ute og kos"),
    ("sushi", "Sushi", "Mat ute og kos"), ("pizza", "Pizza", "Mat ute og kos"), ("kebab", "Kebab", "Mat ute og kos"),
    ("restaurant", "Restaurant", "Mat ute og kos"), ("cafe", "Kafé", "Kafé og kiosk"), ("kafe", "Kafé", "Kafé og kiosk"),
    ("bakeri", "Bakeri", "Kafé og kiosk"), ("bakeriet", "Bakeri", "Kafé og kiosk"),
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
    # Lagt til i 0.5.0
    ("obs", "Obs", "Dagligvarer"), ("gårdsbutikk", "Gårdsbutikk", "Dagligvarer"), ("gårdsbutikken", "Gårdsbutikk", "Dagligvarer"),
    ("gardsbutikken", "Gårdsbutikk", "Dagligvarer"), ("rema1000", "Rema 1000", "Dagligvarer"), ("kiwi minipris", "Kiwi", "Dagligvarer"),
    ("parkly", "Parkly", "Bil"), ("bilkey", "BilKey", "Bil"), ("parkering", "Parkering", "Bil"), ("tesla inc", "Tesla", "Bil"),
    ("zaptec", "Zaptec", "Bil"), ("elton", "Elton", "Bil"), ("fortum charge", "Fortum Charge", "Bil"),
    ("skyss", "Skyss", "Kollektivtransport"), ("kolumbus", "Kolumbus", "Kollektivtransport"), ("atb", "AtB", "Kollektivtransport"),
    ("brakar", "Brakar", "Kollektivtransport"), ("norled", "Norled", "Kollektivtransport"), ("fjord1", "Fjord1", "Kollektivtransport"),
    ("bastø", "Bastø Fosen", "Kollektivtransport"), ("basto", "Bastø Fosen", "Kollektivtransport"), ("flybussen", "Flybussen", "Kollektivtransport"),
    ("tv 2", "TV 2", "Abonnementer"), ("tv2", "TV 2", "Abonnementer"), ("google one", "Google One", "Abonnementer"),
    ("icloud", "iCloud", "Abonnementer"), ("adobe", "Adobe", "Abonnementer"), ("nrk", "NRK", "Abonnementer"),
    ("sunkost", "Sunkost", "Helse"), ("lege", "Lege", "Helse"), ("legekontor", "Legekontor", "Helse"),
    ("klinikk", "Klinikk", "Helse"), ("lungemedisinske", "Spesialist", "Helse"), ("sykehus", "Sykehus", "Helse"),
    ("psykolog", "Psykolog", "Helse"), ("kiropraktor", "Kiropraktor", "Helse"), ("naprapat", "Naprapat", "Helse"),
    ("vita", "Vita", "Personlig pleie"), ("kicks", "Kicks", "Personlig pleie"), ("frisør", "Frisør", "Personlig pleie"),
    ("frisor", "Frisør", "Personlig pleie"), ("cutters", "Cutters", "Personlig pleie"),
    ("hudpleie", "Hudpleie", "Personlig pleie"), ("lyko", "Lyko", "Personlig pleie"), ("bliss", "Bliss", "Personlig pleie"),
    ("eurosko", "Eurosko", "Klær og sko"), ("euro sko", "Eurosko", "Klær og sko"), ("skoringen", "Skoringen", "Klær og sko"),
    ("din sko", "DinSko", "Klær og sko"), ("dinsko", "DinSko", "Klær og sko"), ("sport outlet", "Sport Outlet", "Klær og sko"),
    ("northland", "Northland", "Klær og sko"), ("decades", "Decades", "Klær og sko"),
    ("jack & jones", "Jack & Jones", "Klær og sko"), ("vero moda", "Vero Moda", "Klær og sko"),
    ("weekday", "Weekday", "Klær og sko"), ("gina tricot", "Gina Tricot", "Klær og sko"),
    ("kitchn", "Kitchn", "Hjem og interiør"), ("tilbords", "Tilbords", "Hjem og interiør"), ("søstrene grene", "Søstrene Grene", "Hjem og interiør"),
    ("sostrene grene", "Søstrene Grene", "Hjem og interiør"), ("ellos", "Ellos", "Hjem og interiør"), ("netonnet", "NetOnNet", "Hjem og interiør"),
    ("clas ohl", "Clas Ohlson", "Hus og hage"), ("jernia", "Jernia", "Hus og hage"), ("megaflis", "Megaflis", "Hus og hage"),
    ("flisekompaniet", "Flisekompaniet", "Hus og hage"), ("elektroimportøren", "Elektroimportøren", "Hus og hage"),
    ("elektroimportoeren", "Elektroimportøren", "Hus og hage"), ("elektroimportør", "Elektroimportøren", "Hus og hage"),
    ("coop byggmix", "Coop Byggmix", "Hus og hage"), ("xl-bygg", "XL-Bygg", "Hus og hage"),
    ("xl bygg", "XL-Bygg", "Hus og hage"), ("trelast", "Trelast", "Hus og hage"), ("jernvare", "Jernvare", "Hus og hage"),
    ("jern", "Jernvare", "Hus og hage"), ("gjenvinningsstasjon", "Gjenvinningsstasjon", "Hus og hage"),
    ("gjenvinningsstasjo", "Gjenvinningsstasjon", "Hus og hage"), ("hagesenter", "Hagesenter", "Hus og hage"),
    ("gartneri", "Gartneri", "Hus og hage"), ("fargerike", "Fargerike", "Hus og hage"), ("flügger", "Flügger", "Hus og hage"),
    ("flugger", "Flügger", "Hus og hage"), ("jotun", "Jotun", "Hus og hage"), ("bauhaus", "Bauhaus", "Hus og hage"),
    ("mcd", "McDonald's", "Mat ute og kos"), ("subway", "Subway", "Mat ute og kos"), ("burger", "Burger", "Mat ute og kos"),
    ("spiseri", "Spiseri", "Mat ute og kos"), ("lunsj", "Lunsj", "Mat ute og kos"), ("bar", "Bar", "Mat ute og kos"),
    ("pub", "Pub", "Mat ute og kos"), ("bistro", "Bistro", "Mat ute og kos"), ("brasserie", "Brasserie", "Mat ute og kos"),
    ("grill", "Grill", "Mat ute og kos"), ("thai", "Thai", "Mat ute og kos"), ("taco", "Taco", "Mat ute og kos"),
    ("7eleven", "7-Eleven", "Kafé og kiosk"), ("kiosk", "Kiosk", "Kafé og kiosk"), ("kioskdrift", "Kiosk", "Kafé og kiosk"),
    ("backstube", "Backstube", "Kafé og kiosk"), ("baker hansen", "Baker Hansen", "Kafé og kiosk"), ("bakehuset", "Bakehuset", "Kafé og kiosk"),
    ("godt brød", "Godt Brød", "Kafé og kiosk"), ("w.b. samson", "W.B. Samson", "Kafé og kiosk"), ("joe & the juice", "Joe & The Juice", "Kafé og kiosk"),
    ("hmshost", "HMSHost", "Kafé og kiosk"), ("hmshost_norway", "HMSHost", "Kafé og kiosk"), ("pressbyrån", "Pressbyrån", "Kafé og kiosk"),
    ("bakst", "Bakeri", "Kafé og kiosk"),
    ("duty-free", "Duty Free", "Fritid og ferie"), ("duty free", "Duty Free", "Fritid og ferie"), ("travel retail", "Duty Free", "Fritid og ferie"),
    ("norli", "Norli", "Fritid og ferie"), ("ark", "Ark", "Fritid og ferie"), ("adlibris", "Adlibris", "Fritid og ferie"),
    ("eventer", "Eventer", "Fritid og ferie"), ("tise", "Tise", "Fritid og ferie"),
    ("interflora", "Interflora", "Gaver"), ("blomster", "Blomster", "Gaver"), ("blomsterbutikk", "Blomster", "Gaver"),
    ("gavekort", "Gavekort", "Gaver"),
    ("dyrebutikk", "Dyrebutikk", "Kjæledyr"), ("musti", "Musti", "Kjæledyr"), ("dyrlege", "Dyrlege", "Kjæledyr"),
    ("dyreklinikk", "Dyrlege", "Kjæledyr"),
    ("renter", "Renter", "Renter og gebyrer"), ("gebyr", "Gebyr", "Renter og gebyrer"), ("omkostninger", "Gebyr", "Renter og gebyrer"),
    ("årsavgift", "Årsavgift", "Renter og gebyrer"), ("arsavgift", "Årsavgift", "Renter og gebyrer"),
    ("purregebyr", "Purregebyr", "Renter og gebyrer"), ("inkasso", "Inkasso", "Renter og gebyrer"),
   
    # Inntekt
    ("lønn", "Lønn", "Lønn"), ("lonn", "Lønn", "Lønn"), ("barnetrygd", "Barnetrygd", "Stønader"),
    ("kontantstøtte", "Kontantstøtte", "Stønader"), ("foreldrepenger", "Foreldrepenger", "Stønader"),
    ("nav", "NAV", "Stønader"), ("skatteetaten", "Skatteetaten", "Annen inntekt"),
]

# Mønstre som sier hva slags sted det er, ikke hvilket. De gir kategori, men navnet hentes
# fra teksten («Byen trelast» → «Byen Trelast», ikke bare «Trelast»).
GENERISKE = {"trelast", "jernvare", "jern", "bar", "pub", "lunsj", "spiseri", "bistro", "brasserie", "grill", "thai",
             "taco", "burger", "kiosk", "kioskdrift", "cafe", "kafe", "restaurant", "bakeri", "bakeriet", "bakst", "sushi",
             "pizza", "kebab", "lungemedisinske", "klinikk", "gårdsbutikk", "gårdsbutikken", "gardsbutikken",
             "hagesenter", "gartneri", "blomster", "blomsterbutikk", "dyrebutikk", "dyreklinikk", "hotel", "hotell",
             "gjenvinningsstasjon", "gjenvinningsstasjo", "kino", "frisør", "frisor", "hudpleie", "legekontor", "lege",
             "tannlege", "fysioterapi", "optiker", "psykolog", "kiropraktor", "naprapat", "sykehus", "parkering"}

# Kategorier som bare gir mening for penger inn (eller ut)
BARE_INN = {"Lønn", "Stønader", "Annen inntekt"}
# Utgiftskategorier som blir noe annet når pengene kommer inn («Renter» på sparekontoen)
INN_SOM = {"Renter og gebyrer": "Annen inntekt"}

# Ord som ofte står i overføringer mellom egne kontoer
OVERFORINGSORD = ("overføring", "overforing", "egen konto", "egne kontoer", "fra konto", "til konto",
                  "nettbank til", "nettbank fra", "mobilbank", "sparing", "innbetaling kredittkort",
                  "kredittkort", "betaling kort", "straksoverføring")

# ---------------------------------------------------------------- rydding
_STOY_START = re.compile(
    r"^(?:(?:varekjøp|varekjop|kortkjøp|kortkjop|reservasjon|visa|mastercard|bankaxept|debit|"
    r"avtalegiro|efaktura|e-faktura|nettgiro|giro|betaling|straksbetaling|kjøp|kjop|"
    r"apple pay|google pay|kontaktløs|kontaktlos|paypal_?|zettle_?|izettle_?|sumup)\b[\s:*]*)+", re.I)
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


def kjent(ryddet: str, generiske: bool = True) -> tuple[str, str] | None:
    """(pent navn, kategori) for kjente butikker og regninger. Første treff i teksten vinner,
    og ved likt sted det lengste mønsteret («rema 1000» før «rema»)."""
    best = None
    for monster, navn, kat in KJENTE:
        if not generiske and monster in GENERISKE:
            continue
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
        k = kjent(vipps.group(1), generiske=False)
        if k:
            return k[0]
        rest = [o for o in vipps.group(1).split() if o not in ("as", "asa") and not o.isdigit()][:3]
        return "Vipps: " + " ".join(_pen(o) for o in rest) if rest else "Vipps"
    k = kjent(r, generiske=False)
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
        if belop_ore > 0 and kat in INN_SOM:
            return INN_SOM[kat], None
        return kat, None
    return None, None


def ser_ut_som_overforing(tekst: str) -> bool:
    lav = _norm(tekst).lower()
    return any(o in lav for o in OVERFORINGSORD)
