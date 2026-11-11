# Pengeboka

Husholdningsøkonomi for hele familien: importer kontoutskrifter fra nettbanken, og se hva dere har brukt, hva som er igjen, budsjett og faste trekk. Alt regnes ut med faste regler – ingen AI, og ingenting sendes ut av Home Assistant.

## Kom i gang

1. Last ned transaksjonene fra nettbanken som **CSV eller Excel**, én fil per konto (felleskonto, brukskontoer, kredittkort, sparekontoer, lån). Ta gjerne med de siste 3–6 månedene første gang, så får appen noe å regne snitt og faste trekk ut fra.
2. Åpne Pengeboka fra sidemenyen, gå til **Import** og velg alle filene på én gang.
3. Appen viser ett kort per fil og finner kontoen selv:
   * Har filen kontonummer (f.eks. kolonnene «Fra konto» og «Til konto»), kjennes kontoen igjen. Er nummeret nytt, foreslår appen en ny konto – gi den et navn og sjekk typen.
   * Har filen ikke kontonummer, velger du kontoen første gang. Neste gang kjenner appen den igjen på transaksjonene den har sett før.
4. Trykk **Importer**.

Etter det holder det å importere én gang i måneden. Det gjør ingenting om periodene overlapper – det som finnes fra før, hoppes over.

## Månedsrutinen (ca. fem minutter)

1. Last ned og importer en fil per konto.
2. Gå gjennom **Trenger dere** på Oversikt. Er lista tom, er alt i orden.
3. Gi kategori til det som mangler. Velg «Gjelder alle fra …» så slipper dere samme spørsmål neste gang.

## Faner

* **Oversikt** – denne måneden: brukt så langt (eller hva som ble igjen for en ferdig måned), inn, ut og spart, prognose for resten av måneden, lista over det som trenger dere, og hver kategori med budsjett eller snitt. Trykk på en kategori for å se transaksjonene.
* **Transaksjoner** – søk og filtrer på måned, kategori og konto. Trykk på en transaksjon for å endre kategori, skrive notat eller si at den ikke er en overføring.
* **Budsjett** – et beløp per kategori i måneden. **Foreslå** fyller ut snittet av de tre siste hele månedene, rundet opp. Trykk på et kategorinavn for å endre navn og ikon eller skjule den.
* **Faste** – abonnementer og regninger appen har funnet selv, med neste trekk og hva det koster i måneden og året.
* **Import** – nye filer og tidligere importer. En import kan angres.
* **⚙️ Innstillinger** – kontoer, egne regler og eksport av alt som CSV.

## På PC

På en bred skjerm får appen sidemeny til venstre, oversikten i to kolonner med kommende faste trekk, transaksjoner som en tabell (mottaker, konto, kategori, beløp) og redigering i et panel til høyre.

| Tast | Gjør |
|---|---|
| 1–5 | Bytt mellom Oversikt, Transaksjoner, Budsjett, Faste og Import |
| / | Søk i transaksjonene |
| ← → | Forrige og neste måned på Oversikt |
| Esc | Lukk panelet |

## Kontoer, skjulte kontoer og overføringer

Ta med alle kontoene, også de dere sjelden ser på. Da kan appen se pengene gå fra én konto og komme inn på en annen.

* **Overføring:** samme beløp ut av én egen konto og inn på en annen innen fire dager. Telles ikke som forbruk. Har filen kontonummeret pengene gikk til, og det er en av deres egne kontoer, regnes det som overføring selv om den andre kontoen ikke er importert ennå.
* **Sparekonto:** penger *til* sparekontoen telles som **sparing**, penger *fra* den trekkes fra sparingen.
* **Kredittkort:** kjøpene på kortet telles i sine kategorier. Betalingen av kortregningen fra brukskontoen er en overføring og telles ikke en gang til.
* **Lån:** betaling til en lånekonto telles som **Lån**.
* **Skjult konto:** vises ikke i oversikten eller lista, men brukes fortsatt til å kjenne igjen overføringer. Fint for sparekontoer og lån som ellers bare roter til oversikten.

Har appen paret noe som ikke er en overføring, åpne transaksjonen og trykk **Ikke en overføring**.

## Kategorier og regler

Appen kjenner igjen vanlige norske butikker, kjeder og regninger (Kiwi, Rema, Coop, Tibber, Gjensidige, Netflix, Ruter og mange flere) og rydder bankteksten til et kort navn: «Visa 4925 NOK 249,00 KIWI 505 SENTRUM» blir «Kiwi».

Når dere velger kategori på en transaksjon med **Gjelder alle fra …** slått på, lages en egen regel. Egne regler går foran de innebygde, gjelder også nye importer, og vises under Innstillinger der de kan slettes. En kategori dere har satt for hånd på én transaksjon, overstyres aldri.

## Trenger dere

| Hva | Når |
|---|---|
| Uten kategori | Transaksjoner appen ikke kjenner igjen |
| Prisendring | Et fast trekk med stabilt beløp har endret seg |
| Nytt fast trekk | Et trekk som har dukket opp de siste månedene |
| Uvanlig stort beløp | Mer enn dobbelt så mye som vanlig hos samme mottaker (minst 1 000 kr mer), eller over 5 000 kr hos en ny mottaker |
| Over budsjett / ligger an til å gå over | Basert på budsjettet og prognosen for måneden |
| På tide å importere | Siste transaksjon på en konto er over 35 dager gammel |

Trykk **OK** for å skjule et punkt.

## Prognose

For hver kategori ser appen på hvor stor del av månedsforbruket som pleier å være brukt innen samme dag i måneden de tre siste månedene. Er strømregningen allerede betalt den 5., regnes det ikke med mer strøm resten av måneden.

## Filformater

* CSV og TXT med semikolon, komma eller tabulator, i UTF-8 eller Windows-tegnsett.
* Excel (.xlsx).
* Datoer som 14.10.2026, 14.10.26 eller 2026-10-14. Beløp med desimalkomma eller -punktum.
* Beløp i én kolonne (minus = ut) eller ut og inn i hver sin kolonne.
* Nettbankens «Transaksjonsliste» med kontonumre, status og summer nederst. Reserverte kjøp hoppes over og kommer med i neste import når de er bokført.

Gjetter appen feil kolonner, åpne **Feil kolonner? Endre her** i forhåndsvisningen. PDF kan ikke leses.

## Kvitteringer fra Matplan

Bruker dere Matplan til kvitteringer, kan Pengeboka koble dem til dagligvarekjøpene i banken:

1. I Matplan: **Mer → Innstillinger → Pengeboka**, trykk **Kopier** på koblingskoden.
2. Her: **Innstillinger → Matplan**, lim inn koden og trykk **Koble til Matplan**.

Pengeboka finner kjøpet med samme beløp (innen 1 kr), samme kjede og dato innen 3 dager (Oda: 6 dager). Ingen AI. Da får dere:

* **🧾 Kvittering** på kjøpet. Trykk på kjøpet for å se varene på kvitteringen.
* **Ingen kvittering** på dagligvarekjøp uten kvittering (bare fra datoen den første kvitteringen kom inn).
* Filteret **Kvittering** i Transaksjoner, og «X av Y med kvittering» under Dagligvarer i Oversikt.
* I Matplan står det hvilken konto kvitteringen ble betalt fra, eller «Ikke i banken».

Koblingen oppdateres hver time og rett etter hver import. **Koble fra** sletter kopien av kvitteringene her.

## Personvern og sikkerhet

* Alt lagres i appens egen database i Home Assistant. Ingen kontonumre eller navn ligger i koden.
* Appen har ingen port ut og godtar bare forespørsler gjennom Home Assistants innlogging (ingress). Den har ikke tilgang til resten av Home Assistant og bruker ingen AI.
* Er Matplan koblet til, snakker Pengeboka bare med Matplan internt i Home Assistant, aldri med internett. Bankdataene blir her: Matplan får bare vite hvilken konto, dato og sum hver kvittering ble funnet med.
* Transaksjonene kommer med i sikkerhetskopiene av Home Assistant. **Bruk passord på sikkerhetskopiene**, særlig hvis de lagres i skyen.
* Slå på totrinnsinnlogging for brukerne i Home Assistant.
* **Last ned alt som CSV** under Innstillinger gir en kopi dere kan åpne i Excel.

## Senere

Automatisk henting fra banken (via en regulert tjeneste som Enable Banking) kan kobles på senere og bruker samme import, regler og oversikt.
