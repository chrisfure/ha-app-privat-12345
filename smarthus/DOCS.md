# Smarthus

Hele huset i én app: rom med egne faner, alle lys, all varme og en «Mer»-side for bil, strøm, kamera, media og resten. Appen er laget for å være enkel for alle i huset, og har en redigeringsmodus der den som styrer oppsettet kan endre alt uten å skrive kode.

- **Hjem** – hilsen, vær og strømpris, statusbrikker, hurtigknapper og rommene.
- **Rom** – hvert rom kan ha flere faner, for eksempel *Lys*, *Klima*, *Media* og en egen fane for mer avanserte ting som støvsugeren.
- **Lys** – alle lys som er på, eller alle lys rom for rom.
- **Varme** – alle termostater samlet, med strømprisen øverst.
- **Mer** – store kort for det viktigste (f.eks. bil og strøm) og små ruter for resten.
- **Lys/mørk modus** – følger telefonen, eller velges manuelt under *Mer*. Valget huskes per person.

## Installering

1. Installer og start appen **Smarthus**. Den legger grensesnittet på plass i Home Assistant og stopper seg selv.
2. Gå til **Innstillinger → Dashbord → ⋮ → Ressurser** og legg til
   `/local/smarthus/loader.js` som **JavaScript-modul**. Dette gjøres bare én gang – nye versjoner lastes automatisk.
3. Lag et nytt dashbord, velg visningstypen **Panel (ett kort)** og legg inn kortet:

   ```yaml
   type: custom:smarthus-app
   ```

4. Vil du at appen skal åpne seg når Home Assistant åpnes, setter du dashbordet som standard under **Innstillinger → Dashbord**, og/eller under **Dashbord** i brukerprofilen på hver telefon.

## Redigeringsmodus

Under **Mer → Rediger appen** kan du:

- flytte rom, faner og elementer opp og ned,
- legge til og fjerne rom, faner og elementer,
- velge type, enhet, navn, ikon og bredde for hvert element,
- skjule rom, faner eller elementer for bestemte personer,
- kreve bekreftelse før en handling,
- redigere alt som tekst (for større endringer eller sikkerhetskopi).

Trykk **Lagre** for å lagre i dashbordet. Endringene gjelder alle telefoner med en gang.

Hvem som kan redigere styres med `editors` (bruker-ID-er). Er den tom, kan alle administratorer redigere.

## Bruk i hverdagen

- **Lys:** dra på stripen for lysstyrke, trykk for av/på, hold inne for farger og flere valg.
- **Hold inne** på et element åpner Home Assistants egen detaljvisning – der finnes alle innstillinger for enheten.
- **Varme:** trykk – eller + for å justere. Endringen sendes når du slutter å trykke.

## Elementtyper

| Type | Brukes til |
|---|---|
| `light` | Lys med lysstyrke (stripe) |
| `toggle` | Av/på for brytere, automasjoner og lignende |
| `climate` | Termostat, med `modes` og `presets` som valg |
| `value` | En verdi, med `graph` (timer), `bar` (`min`/`max`), `attribute`, `map` og `alert` |
| `button` | Scene, skript, knapp eller en egen `action` |
| `media` | Høyttaler/TV med volum (`max_volume`) |
| `vacuum` | Støvsuger med `status`, `battery`, `error` og sugekraft |
| `areaclean` | Velg flere rom (`areas`: navn + område-ID) og støvsug |
| `select`, `number`, `time`, `input` | Hjelpere og innstillinger |
| `cover`, `lock`, `camera`, `timer` | Port, lås, kamera/bilde og nedtelling |
| `todo` | Handleliste eller annen liste |
| `calendar` | Kalendere med farger (`entities`, `days`) |
| `weather` | Værmelding (`forecast`: `hourly`/`daily`) |
| `graph` | Graf over én eller flere sensorer (`hours`) |
| `pricechart` | Strømpris fra en Nord Pool-sensor |
| `text` | Tekst fra en enhet eller en mal (`content`) |
| `link` | Snarvei til en side i Home Assistant (`path`) |
| `heading` | Overskrift |
| `updates`, `batteries`, `lightson` | Automatiske lister |
| `card` | Et hvilket som helst vanlig Home Assistant-kort (`card: {...}`) |

Felles for alle: `name`, `icon`, `w` (bredde av 6: 2, 3, 4 eller 6), `confirm`, `hide_for`, `show_for` og `when` (vis bare når en enhet har en bestemt tilstand).

## Eksempel

```yaml
type: custom:smarthus-app
home:
  weather: weather.home
  chips:
    - type: lights
      open: lights
  quick:
    - type: button
      name: Kveld
      icon: mdi:weather-night
      entity: scene.kveld
rooms:
  - id: stue
    name: Stue
    icon: mdi:sofa
    main: light.stue
    temp: sensor.stue_temperatur
    tabs:
      - name: Lys
        items:
          - type: light
            entity: light.stue
      - name: Støvsuger
        items:
          - type: vacuum
            entity: vacuum.stovsuger
heat:
  items:
    - type: climate
      entity: climate.stue
more:
  - id: strom
    name: Strøm
    icon: mdi:flash
    size: large
    big: sensor.effekt
    tabs:
      - name: Nå
        items:
          - type: pricechart
            entity: sensor.nordpool
```

Ingen personlige opplysninger ligger i koden – alt oppsett lagres i ditt eget Home Assistant.
