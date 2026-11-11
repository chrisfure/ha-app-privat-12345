# Endringslogg

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
