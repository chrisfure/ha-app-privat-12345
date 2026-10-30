# Plasterboka

Sykdomslogg for barna: temperatur, medisin, symptomer og notater med ett trykk – og en sykehistorie som er lett å finne fram i senere.

## Kom i gang

1. Åpne Plasterboka fra sidemenyen og gå til **Innstillinger**.
2. Legg inn barna (navn, farge, fødselsdato eller termin). Et barn som ikke er født ennå kan skjules fra forsiden til det trengs.
3. Legg inn legemidlene dere bruker, og slå på dem som skal kunne velges for hvert barn.
4. Hvis du har eldre logger i kalendere i Home Assistant: **Importer fra kalendere** (se under).

Alt lagres lokalt i appens egen database. Ingen navn eller helsedata ligger i koden.

## Faner

* **Registrer** – status for hvert barn (syk/frisk, siste temperatur, symptomer siste døgn), fliser for temperatur, medisin, symptomer og notat, et kort per legemiddel og alt som er registrert siste døgn.
* **Historikk** – alle sykdomsepisoder per barn og år. Trykk på en episode for feberkurve med doser, oppsummering per dag og alle registreringer. Episoden kan få navn og notat (diagnose, legebesøk) og skrives ut eller lagres som PDF.
* **Innstillinger** – barn, legemidler, symptomliste, varsling, grenser, import, gjennomgang og eksport.

## Registrering

* Én registrering kan inneholde temperatur, en dose, symptomer og et notat samtidig. Trykk på en del for å ta den med eller fjerne den.
* Tidspunkt er «nå» som standard; velg «15 min siden», «30 min», «1 t» eller et eget tidspunkt.
* Mikstur med styrke (mg/ml) kan registreres i ml – appen lagrer også mg.
* Etter hver registrering kan du **angre** eller **endre**. Trykk på en rad for å endre eller slette den.

## Legemidler og døgndose

Hvert legemiddel har et **virkestoff**. Døgndosen summeres per virkestoff, så f.eks. paracetamol-mikstur og paracetamol-stikkpiller telles sammen.

Per barn kan du sette:

| Innstilling | Brukes til |
|---|---|
| Kan velges ved registrering | Bare påslåtte legemidler vises når du registrerer |
| Vanlig dose (mg) | Forhåndsutfyller dosen og gir «Gi»-knappen på kortet |
| Minste intervall (timer) | «Neste tidligst kl. …» og varsel ved for tidlig dose |
| Maks per døgn (mg) | Måler for siste 24 timer og varsel hvis dosen går over |
| Kur: doser per dag og siste dag | «Dose 2 av 4 i dag» så lenge kuren varer |

Døgndosen regnes **rullerende siste 24 timer**. Kortet viser også hvor mye som er gitt i dag.

Doser og grenser legger dere inn selv etter pakningsvedlegg eller resept. Appen regner ikke ut doser. Et varsel stopper ikke registreringen – du kan velge «Lagre likevel».

## Sykdomsepisoder

Registreringer grupperes automatisk: går det mer enn 72 timer uten registrering, starter en ny episode (kan endres i innstillingene). Et barn regnes som **sykt** så lenge siste registrering er mindre enn 48 timer gammel, eller til du trykker **Frisk igjen**.

Feber regnes fra 38,0 °C, slik [Helsenorge](https://www.helsenorge.no/sykdom/barn/feber-hos-barn/) beskriver det. For barn under 3 måneder med feber vises Helsenorges råd om å kontakte lege.

## Import fra kalendere

Importen leser hendelser fra valgte kalendere i Home Assistant og forstår de vanlige formatene, f.eks. `Paracetamol 250.0 mg`, `Navn: Paracetamol 250.0mg`, `Navn Temp: 38.7°C`, `Temperatur Navn: 39.8°C` og `Navn: Kun notat`. Beskrivelsen blir notat, og en temperatur i notatet («Temp: 38,7») hentes ut.

* **Duplikater** (samme tidspunkt og innhold) fjernes.
* Temperatur og dose registrert i samme minutt slås sammen til én registrering.
* Står barnets navn i teksten, brukes det. For hendelser uten navn velger du per kalender:
  * hvilket barn de tilhører,
  * om de skal **gjennomgås før en dato** (f.eks. datoen kalenderen ble tatt i bruk for bare ett barn), **gjennomgås alle** eller tildeles uten gjennomgang (merkes «antatt»).
* Mulige dobbeltregistreringer (samme legemiddel innen 90 minutter) og doser som avviker fra de andre dagene merkes «bør sjekkes».
* **Forhåndsvis** viser hva som vil skje før noe lagres. Importen kan kjøres flere ganger uten å lage dobbelt opp. Kalenderne endres ikke.

Under **Gjennomgang** velger du barn for hver sykdomsperiode uten navn (eller for alle på én gang), og beholder eller sletter registreringer som bør sjekkes.

## Sensorer i Home Assistant

| Entitet | Innhold |
|---|---|
| `sensor.plasterboka_<navn>` | `syk` eller `frisk`. Attributter: `siste_temperatur`, `siste_temperatur_tid`, `feber`, `symptomer`, `doser` (per virkestoff: `siste_kl`, `siste_mg`, `sum_24t_mg`, `maks_dogn_mg`, `neste_tidligst`), `neste_dose`, `episode_start`, `episode_dag`, `episode_navn`, `tekst` |
| `sensor.plasterboka_skjermtekst` | Én linje for syke barn til veggskjermen, ellers «Alle friske» |

Navnet i entiteten lages fra barnets navn (æ/ø/å blir ae/o/a) og vises under Innstillinger → Barn. Sensorene oppdateres ved hver endring og hvert minutt.

### Eksempel: vis bare på veggskjermen når noen er syke

```yaml
type: conditional
conditions:
  - condition: state
    entity: sensor.plasterboka_skjermtekst
    state_not: Alle friske
card:
  type: entity
  entity: sensor.plasterboka_skjermtekst
  name: Syke
  icon: mdi:bandage
```

## Varsling

Under Innstillinger → Varsling kan du skrive inn en notify-tjeneste (f.eks. en gruppe for begge foreldrene). Da sendes et varsel ved hver registrering, med hva som ble registrert, klokkeslett, notat og hvem som registrerte.

Appen sender også hendelsen `plasterboka_hendelse` med `handling`, `barn`, `tid`, `temperatur`, `feber`, `legemiddel`, `dose_mg`, `symptomer`, `notat` og `tekst`, som egne automasjoner kan bruke.

## Registrere fra knapper og automasjoner

Appen lytter på hendelsen `plasterboka_registrer`:

```yaml
# Steg i en automasjon eller et skript
- event: plasterboka_registrer
  event_data:
    barn: Navn
    temperatur: 38.6              # valgfritt
    legemiddel: Paracet mikstur   # valgfritt – bruker barnets vanlige dose
    dose_mg: 250                  # valgfritt, eller dose_ml
    symptomer: [Hoste]            # valgfritt
    notat: Sover urolig           # valgfritt
    minutter_siden: 10            # valgfritt
```

Registreringer fra Home Assistant lagres uten spørsmål om intervall og maks døgndose.

## Eksport

**Last ned alt som CSV** (Historikk eller Innstillinger) gir én rad per registrering, med barn, temperatur, legemiddel, dose, symptomer og notat.

Plasterboka erstatter ikke lege eller helsestasjon. Ved bekymring: fastlegen, legevakt (116 117) eller 113.
