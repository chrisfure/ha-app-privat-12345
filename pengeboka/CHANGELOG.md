# Endringslogg

## 0.6.0

- Automatisk henting fra banken via Enable Banking (open banking, bare lesetilgang): oppsett under Innstillinger, tilkobling med BankID, henting hver natt og på «Hent nå».
- Kontoer kobles på kontonummer. Kjøp som allerede er importert fra fil, blir ikke dobbelt – heller ikke når en fil importeres etter banken.
- Varsel under «Trenger dere» før samtykket går ut, og hvis hentingen feiler.

## 0.5.1

- Kategorisering og import går omtrent fem ganger raskere.

## 0.5.0

- Flere kategorier: Kollektivtransport, Hus og hage, Klær og sko, Personlig pleie, Kafé og kiosk, Renter og gebyrer, Gaver og Kjæledyr. «Hjem og klær» heter nå «Hjem og interiør», og «Bil og transport» heter «Bil».
- Kjenner igjen rundt 100 flere butikker og tjenester, også når banken kutter navnet («Clas ohl», «7Eleven», «Mcd») eller betalingen går via Vipps, PayPal eller Zettle.
- Steder som «… trelast», «… bar» og «… spiseri» får kategori, men beholder sitt eget navn.
- Ved oppgradering sorteres det appen har kategorisert på nytt. Det dere har valgt selv og egne regler, beholdes.

## 0.4.0

- Kobling mot Matplan: dagligvarekjøp får «🧾 Kvittering» eller «Ingen kvittering», med varene fra kvitteringen når du åpner kjøpet.
- Nytt filter for kvittering i Transaksjoner, og «X av Y med kvittering» under Dagligvarer i Oversikt.
- Matplan får vite hvilken konto hver kvittering ble betalt fra. Bankdataene blir i Pengeboka.

## 0.3.0

- Egen PC-visning: sidemeny, oversikten i to kolonner med kommende faste trekk, transaksjoner som tabell, budsjett og faste trekk i to kolonner, redigering i et panel til høyre og tydelige hover-effekter.
- Hurtigtaster: 1–5 for fanene, / for søk og piltaster for måned.

## 0.2.0

- Importer flere filer på én gang. Appen finner kontoen selv: fra kontonummeret i filen (eller filnavnet), ellers fra transaksjoner den har importert før. Ukjente kontonumre gir forslag til ny konto med navn og type.
- Kontonummeret lagres på kontoen, og en fil som ikke passer kontoen stoppes.
- Overføringer til egne kontoer kjennes igjen på kontonummeret, også før den andre kontoen er importert.
- Utført dato brukes foran bokført dato, og reserverte kjøp hoppes over til de er bokført.

## 0.1.0

- Første versjon: import av kontoutskrifter (CSV og Excel) med automatisk kolonnegjenkjenning, forhåndsvisning og duplikatsjekk.
- Rydder banktekst til pene navn og sorterer i kategorier med innebygde regler for vanlige norske butikker og regninger, pluss egne regler.
- Kjenner igjen overføringer mellom egne kontoer, også skjulte. Sparing telles som sparing, kredittkortbetaling telles ikke dobbelt.
- Oversikt per måned, «Trenger dere»-liste, budsjett med forslag ut fra snitt, prognose for måneden og faste trekk med varsel om prisendring.
