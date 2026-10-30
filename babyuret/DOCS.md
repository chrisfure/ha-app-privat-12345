# Babyuret

Registrer søvn, mat og bleier med ett trykk – fra telefonen, en fysisk knapp, en NFC-tag eller med stemmen.

## Innstillinger

Alt stilles inn i selve appen, under fanen **Innstillinger**:

* **Navn** og **fødselsdato eller termin** – før fødselen viser appen hvor lenge det er igjen.
* **Mating** – amming, flaske eller begge. Styrer valgene du får når du trykker «Mat».
* **Standard flaskemengde**.
* **Nattmodus** – tidsrom for mørk, rødtonet skjerm. Kan overstyres med månen øverst.

## Faner

* **Registrer** – status og de store knappene. Det eneste du trenger i hverdagen.
* **Dagbok** – nøkkeltall, døgnstripe og logg per dag. Bla mellom dager med pilene.
* **Innstillinger**.

## Bruk

* **Sover / Våknet** – ett trykk veksler.
* **Mat** – velg venstre/høyre (den som står for tur er merket «Neste») eller flaske. Amming kjører med stoppeklokke til du trykker «Ferdig» eller «Bytt side».
* **Tiss / Bæsj / Tiss + bæsj** – ett trykk.
* Etter hver registrering får du **Angre** og **Endre** nederst på skjermen.
* Trykk på en rad i Dagbok for å endre tid, side, mengde eller slette.
* Glemte du å trykke? Bruk «Legg inn noe som skjedde tidligere».

## Sensorer i Home Assistant

| Entitet | Innhold |
|---|---|
| `sensor.babyuret_status` | `sover`, `våken` eller `ammer` (attributt `varighet_min`) |
| `sensor.babyuret_sist_matet` | Tidspunkt, med `type`, `side`/`ml` og `neste_side` |
| `sensor.babyuret_sovn_i_dag` | Timer søvn i dag |
| `sensor.babyuret_maltider_i_dag` | Antall måltider (attributter `ml`, amming-minutter per side) |
| `sensor.babyuret_bleier_i_dag` | Antall bleier (attributter `tiss`, `baesj`) |
| `sensor.babyuret_skjermtekst` | Én linje til veggskjermen |

Sensorene oppdateres ved hver registrering og hvert minutt.

## Registrere fra knapper, NFC og Assist

Appen lytter på hendelsen `babyuret_registrer`. Feltet `handling` kan være:

`sovn_start`, `sovn_slutt`, `sovn_veksle`, `amming_start` (med `side: V/H`, ellers neste side), `amming_bytt`, `amming_slutt`, `flaske` (med `ml`), `tiss`, `baesj`, `begge`.

Valgfritt: `minutter_siden` (f.eks. `10`) og `av` (navnet som vises i loggen).

### Zigbee-knapp ved stellebordet

Ett klikk = tiss, dobbeltklikk = bæsj, langt trykk = begge. Bytt ut entiteten med din egen knapp.

```yaml
alias: Babyuret – knapp ved stellebordet
triggers:
  - trigger: state
    entity_id: event.stellebord_knapp_action
    attribute: event_type
conditions:
  - condition: template
    value_template: "{{ trigger.to_state.attributes.event_type in ['single', 'double', 'hold'] }}"
actions:
  - event: babyuret_registrer
    event_data:
      handling: >
        {{ {'single': 'tiss', 'double': 'baesj', 'hold': 'begge'}[trigger.to_state.attributes.event_type] }}
      av: Stellebordet
mode: queued
```

### NFC-tag på senga

```yaml
alias: Babyuret – NFC på senga
triggers:
  - trigger: tag
    tag_id: DIN-TAG-ID
actions:
  - event: babyuret_registrer
    event_data:
      handling: sovn_veksle
```

### Assist (stemme)

```yaml
alias: Babyuret – stemme
triggers:
  - trigger: conversation
    command:
      - "babyen sover"
      - "babyen sovnet"
    id: sovn_start
  - trigger: conversation
    command:
      - "babyen er våken"
      - "babyen våknet"
    id: sovn_slutt
  - trigger: conversation
    command: "bleie med tiss"
    id: tiss
actions:
  - event: babyuret_registrer
    event_data:
      handling: "{{ trigger.id }}"
      av: Assist
  - set_conversation_response: "Notert!"
```

## Veggskjermen

Et enkelt markdown-kort:

```yaml
type: markdown
content: "{{ states('sensor.babyuret_skjermtekst') }}"
```

## Reagere på registreringer

Ved hver endring sender appen hendelsen `babyuret_hendelse` (med `handling`, `kategori`, `detaljer` og `status`). Den kan brukes til f.eks. dempet nattlys når amming starter om natta – det kommer som ferdige eksempler i et senere steg.

## Data

Alt lagres lokalt i appen (`/data/babyuret.db`) og tas med i Home Assistant-backupen. Nederst i appen kan du laste ned alt som CSV.
