# Babyuret

Registrer søvn, mat og bleier med ett trykk – fra telefonen, en fysisk knapp, en NFC-tag eller med stemmen.

## Innstillinger

Alt stilles inn i selve appen, under fanen **Innstillinger**:

* **Navn** og **fødselsdato eller termin** – før fødselen viser appen hvor lenge det er igjen.
* **Kjønn** – brukes bare til å velge riktig WHO-vekstkurve.
* **Mating** – amming, flaske eller begge. Styrer valgene du får når du trykker «Mat».
* **Standard flaskemengde**.
* **Nattmodus** – tidsrom for mørk, rødtonet skjerm. Kan overstyres med månen øverst.

## Faner

* **Registrer** – status og de store knappene. Det eneste du trenger i hverdagen.
* **Dagbok** – søvn siste 24 timer sammenlignet med det som er vanlig for alderen, nøkkeltall, døgnstripe og logg per dag.
* **Målinger** – vekt, lengde, hodeomkrets og temperatur, med vekstkurver.
* **Innstillinger** – inkludert lenker til alle kilder.

## Søvnprognose

Statuskortet viser når babyen trolig sovner neste gang og hvor lenge søvnen pleier å vare – eller, når babyen sover, når den trolig våkner.

* Regnes ut lokalt fra deres egne registreringer de siste 7 dagene. Nyere dager teller mest, og dag og natt beregnes hver for seg (nattmodus-tidsrommet).
* Vises som et tidsvindu (midterste halvdel av babyens vanlige verdier), merket med hvor sikker den er.
* Helsemyndighetene gir ingen anbefalte «våkenvinduer». Det eneste offisielle tallet er Helsenorges beskrivelse av at nyfødte ofte er våkne 30–60 minutter av gangen. Det brukes som startestimat de første tre månedene og veies gradvis ned etter hvert som egne data kommer.

## Anbefalinger og kilder

Appen bruker bare tall fra helsemyndigheter og WHO:

| Hva | Kilde |
|---|---|
| Søvn per døgn per alder (0–3 mnd: 14–17 t, normalt 11–19 t osv.), våkenperioder hos nyfødte, amming 8–12 ganger i døgnet | [Helsenorge: Søvn hos barn 0–2 år](https://www.helsenorge.no/barn/sovn-hos-barn/) |
| Vekttap etter fødsel (inntil 10 % normalt, tilbake på fødselsvekt innen 14 dager, tettere oppfølging fra 8 %) | [Helsedirektoratet](https://www.helsedirektoratet.no/forebygging-diagnose-og-behandling/svangerskap-fodsel-og-barsel/amming-og-spedbarnsernaering/oppfolging-av-vekt-hos-friske-ammede-nyfodte-som-er-fodt-til-termin) |
| Vekstkurver for vekt og lengde (WHO, sju persentiler) | [Helsedirektoratet: Veiing og måling](https://www.helsedirektoratet.no/retningslinjer/helsestasjons-og-skolehelsetjenesten/helsestasjon-05-ar/veiing-og-maling), [WHO Child Growth Standards](https://www.who.int/tools/child-growth-standards) |
| Feber (38,0 °C i endetarmen, kontakt lege ved feber hos barn ≤ 3 mnd) | [Helsenorge: Feber hos barn](https://www.helsenorge.no/sykdom/barn/feber-hos-barn/) |

For hodeomkrets bruker helsestasjonen den norske kurven fra Vekststudien i Bergen. Den er ikke fritt tilgjengelig som data, så appen viser WHO-kurven – tallene kan avvike litt. Vekstkurvene gjelder barn født til termin.

Appen erstatter ikke helsestasjonen. Merknader i appen er nøytrale og viser til kilden; ved bekymring, kontakt helsestasjonen eller lege.

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
| `sensor.babyuret_prognose` | Mest sannsynlige tidspunkt for neste søvn (eller oppvåkning), med `fra`, `til`, `varighet_min` og `sikkerhet` |
| `sensor.babyuret_skjermtekst` | Én linje til veggskjermen (inkl. «Neste lur ca. …») |
| `sensor.babyuret_sted` | Babyens sted (`hjemme`, `hjemme_vogn`, `ute`, `reise`, `barnevakt_hjemme`, `barnevakt_ute`), med attributt `med` |
| `sensor.babyuret_lyd` | Tolkningen av siste lydmelding, med `kilde`, `poeng`, `grunn` og `forslag_venter` |

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

## Dagbok: dag, uke og måned

Øverst i Dagbok velger du **Dag**, **Uke** eller **Måned**.

* **Dag** er som før: siste 24 timer, dagens tall, tidslinje og alle registreringer.
* **Uke** (mandag–søndag) og **Måned** viser snitt per døgn for søvn, måltider, tiss og bæsj. Snittet regnes av hele døgn med registreringer; dagen i dag er med bare når den er den eneste.
* **Søvn per døgn** er et søylediagram med feltet for det som er vanlig for alderen. **Måltider per døgn** vises på samme måte.
* **Døgnrytme** viser én tidslinje per dag under hverandre, så du ser når babyen pleier å sove og spise.
* Trykk på en søyle eller en dag i døgnrytmen for å åpne den dagen. Pilene blar til forrige eller neste uke/måned.

## Lydgjenkjenning (gråt og rop)

Gråt og rop fra telefoner og nettbrett brukes som **data til søvnloggen**. Babyuret sender ingen varsler – bruk babycall til det. Slås på under **Innstillinger → Lydgjenkjenning**. Der finner du også **Slik bruker du det** – en trinnvis bruksanvisning med ferdig utfylte data for hver av enhetene deres.

### Lytteenheter

Hver enhet har et navn, en **kilde** (små bokstaver, f.eks. `barnerom`) og en rolle:

| Rolle | Brukes til | Vekt |
|---|---|---|
| Fast lytter | Står fast der babyen sover | 1,0 hjemme |
| Flyttbar | Følger babyen, f.eks. iPad på reise eller ved vogna | 1,0 når valgt som «med babyen», ellers 0,3 hjemme |
| Personlig telefon | Telefon som er med en voksen | 1,0 når valgt som «med babyen», ellers 0,3 hjemme |
| Motbevis (stua) | Hører den gråt samtidig, er det trolig TV | −1 poeng |

En **nett-sensor** (valgfritt) avgjør om enheten er hjemme: Wi-Fi-sensoren fra Home Assistant-appen sammenlignes med hjemmenettet, og en `device_tracker` som viser `home` (f.eks. fra UniFi) teller også. Uten nett-sensor regnes faste lyttere som hjemme, mens personlige og flyttbare enheter bare teller når de er valgt som «med babyen».

### Snarvei på iPhone/iPad

1. **Innstillinger → Tilgjengelighet → Lydgjenkjenning**: slå på *Baby som gråter* og *Roping*.
2. **Snarveier → Automatisering → Ny → Lydgjenkjenning → Baby som gråter → Kjør umiddelbart**.
3. Handling: Home Assistant → **Fire Event**, hendelse `babyuret_lyd`, data `{"type": "grat", "kilde": "barnerom"}`.
4. Lag en tilsvarende automasjon for *Roping* med `"type": "rop"`.

Snarveien kan i tillegg kalle et eget varsel-script – det påvirker ikke Babyuret.

### Gammel Android-telefon

Slå på **Lydvarsler** (appen Live Transcribe & Notifications) og sensoren *Last notification* i Home Assistant-appen. En automasjon sender videre til Babyuret:

```yaml
alias: Babyuret – lyd fra Android på barnerommet
triggers:
  - trigger: state
    entity_id: sensor.android_barnerom_last_notification
conditions:
  - condition: template
    value_template: "{{ 'baby' in (trigger.to_state.state | lower) or 'gråt' in (trigger.to_state.state | lower) }}"
actions:
  - event: babyuret_lyd
    event_data:
      type: grat
      kilde: android_barnerom
mode: queued
```

Teksten i varselet avhenger av språket på telefonen – sjekk hva sensoren viser og juster betingelsen.

### Babyens sted

Knappen øverst på forsiden viser hvor babyen er. Bare enheter der babyen er, teller:

* **Hjemme** og **Hjemme med barnevakt**: faste lyttere teller fullt, andre enheter på hjemmenettet teller lite.
* **Hjemme, i vogna ute**: bare enheter valgt som «ved babyen».
* **Ute**, **På reise** og **Ute med barnevakt**: bare enheter valgt som «med babyen», uansett nett. Er ingen valgt, registreres ingen lyd.

### Slik tolkes lyd

Hver melding går gjennom fire sperrer: kjent enhet → enheten er der babyen er → søvn pågår → forbi innsovningsvinduet (15 min). Meldinger som stoppes, lagres med grunn i lydloggen.

Deretter summeres treffene de siste 5 minuttene (vekt × type × sted, der rop teller halvt og stedsfaktoren er 1,0 hjemme, 0,8 i vogna og 0,5 ute), med tillegg:

* +1 når to enheter hører gråt innen 30 sekunder
* +1 nær forventet oppvåkning fra prognosen (±20 min)
* −1 per motbevis fra stua (maks −2)
* −1 når søvnen er under halvparten av forventet lengde

| Poeng | Tolkning |
|---|---|
| Under 2 | Uro i søvne |
| 2 til under 4 | Mulig oppvåkning |
| 4 eller mer | Trolig våknet → forslag på forsiden |

Er en støykilde valgt for søvnen (vifte, hvit støy, annet), økes terskelen for «trolig» med 1.

### Bekrefte

Forslaget «Våknet kl. …?» vises øverst på forsiden: **Våknet** avslutter søvnen ved første treff, **Sovnet igjen** og **Feil** lar søvnen fortsette. Ubesvart etter 30 minutter avsluttes søvnen automatisk og merkes «avsluttet automatisk» i dagboken, så den kan rettes. Trykker dere «Våknet» selv, regnes forslaget som riktig.

### Læring

Med læring på brukes de 30 siste svarene, hver for seg med og uten støykilde. Under 50 % riktige hever terskelen med 1, under 70 % med 0,5, og over 90 % (minst 10 svar) senker den med 0,5. Se **Lydlogg og treffsikkerhet** i innstillingene.

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
