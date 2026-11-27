# Stjerneboka

Stjerner for rutiner og poeng for å hjelpe til hjemme – med en barneside på veggskjermen og ukepenger når dere er klare for det.

Appen har to deler:

| Del | Hvor | Hvem |
|---|---|---|
| **Administrasjon** | Stjerneboka i sidemenyen (ingress) | De voksne: oppgaver, barn, godkjenning, kort og innstillinger |
| **Barnesiden** | `http://<home-assistant>:8210/` på hjemmenettet | Barna – på veggskjermen eller et nettbrett |

## Kom i gang

1. Åpne Stjerneboka fra sidemenyen.
2. **Barn**: legg inn barna med navn, farge og gjerne en emoji.
3. **Oppgaver**: legg til fra forslagene eller lag egne. Velg hvilke barn som har hver oppgave.
4. **Innstillinger**: velg høyttaler og talemotor, og eventuelt veggskjermen (Browser Mod) og hvem som skal få godkjenningsvarsler.
5. Vis barnesiden på veggskjermen (se under).

Alt lagres lokalt i appens egen database. Ingen navn ligger i koden.

## Tre slags oppgaver

| Type | Eksempler | Gir |
|---|---|---|
| **Rutine** | Tannpuss, do, kle på seg | En stjerne – aldri penger |
| **Familiebidrag** | Ta av bordet, dekke bordet | 1–3 poeng, kan bli pengeoppgave |
| **Ekstra innsats** | Tømme oppvaskmaskinen | 1–3 poeng, gjerne med godkjenning |

Rutinene belønnes med ros og stjerner, ikke penger. Pengene knyttes til at barna bidrar i familien.

**Poeng** (1–3) sier hvor krevende oppgaven er: lett, middels eller krevende.

**Når vises den**: morgen, dag, kveld eller hele dagen. Tidene settes under Innstillinger (standard 04, 12 og 16).

**Hvor ofte kan den gjøres**:

* én gang per morgen/dag/kveld (tannpuss),
* én gang per dag (rydde rommet),
* med pause mellom (do – f.eks. 30 minutter),
* så ofte de vil.

**Godkjenning**: barnet trykker, og oppgaven står som «⏳ Venter på voksen» til en voksen godkjenner – i appen eller med knappene i varselet på mobilen. «Ikke helt ennå» lar barnet prøve igjen.

## Ukepenger

Ukepenger er av til dere slår dem på under **Innstillinger → Ukepenger**.

1. Gjør familiebidrag eller ekstra innsats om til pengeoppgaver med «💰 Teller i ukepenger».
2. Sett kroner per poeng.
3. Oversikten viser beløpet per barn og uke. Trykk «Betal ut» når pengene er gitt.

Ukepenger = poeng fra pengeoppgaver × kroner per poeng. Endrer dere kronebeløpet senere, trenger ingen oppgaver endres.

## Barnesiden og veggskjermen

Barnesiden viser oppgavene som gjelder nå, med ett felt per barn i barnets farge. Et trykk gir stjerne, rakett og «Bra jobba!» fra høyttaleren. Ferdige oppgaver får en stor stjerne. Et feiltrykk kan angres i to minutter.

Vis den på veggskjermen på én av disse måtene:

* et **nettsidekort** (iframe) i dashbordet med adressen `http://<ip-til-home-assistant>:8210/`,
* en **knapp som åpner en Browser Mod-popup** med samme adresse,
* eller la appen åpne den selv når et kort skannes (Innstillinger → Veggskjermen).

Barnesiden er bare for hjemmenettet. Ikke åpne porten mot internett. Porten (8210 som standard) kan endres under appens Nettverk-innstillinger i Home Assistant – husk da å endre adressen under Innstillinger → Veggskjermen.

## NFC-kort

Appen lytter på hendelsen `stjerneboka_skann` med feltet `uid`. Send kort-ID-en fra leseren dit, f.eks. med en automasjon:

```yaml
triggers:
  - trigger: mqtt
    topic: stue/tag          # emnet leseren din bruker
actions:
  - action: event.fire        # eller «Fire event» i automasjonsredigereren
    data:
      event_type: stjerneboka_skann
      event_data:
        uid: "{{ trigger.payload }}"
```

Bruker leseren Home Assistants egne tagger, kan du i stedet sende `{{ trigger.event.data.tag_id }}` fra hendelsen `tag_scanned`.

Skann et nytt kort – det dukker opp under **NFC-kort → Nye kort**. Trykk «Koble» og velg barn og oppgave, eller «Åpne barnesiden på veggskjermen».

## Til Home Assistant

**Sensorer**

* `sensor.stjerneboka_<navn>` – stjerner i dag. Attributter: `stjerner_uke`, `poeng_uke`, `kroner_uke`, `okt`, `mangler` (rutiner som gjenstår nå), `alt_ferdig`, `venter_godkjenning`.
* `sensor.stjerneboka_venter_godkjenning` – antall oppgaver som venter.

**Hendelser**

* `stjerneboka_hendelse` sendes ved hver stjerne (`handling: registrert`), oppgave som venter (`venter`), godkjenning (`godkjent`/`avvist`), sperre (`sperret`) og ukjent kort (`ukjent_kort`). Data: `barn`, `oppgave`, `poeng`, `stjerner_i_dag`, `melding`, `kilde`.
* Send `stjerneboka_registrer` med `barn` og `oppgave` (navn) for å registrere fra en knapp eller automasjon.

Eksempel – påminnelse ved leggetid hvis noe mangler:

```yaml
triggers:
  - trigger: time
    at: "19:30:00"
conditions:
  - condition: state
    entity_id: sensor.stjerneboka_<navn>
    attribute: alt_ferdig
    state: false
actions:
  - action: tts.speak
    ...
```

## Bilder

Oppgavene kan bruke de innebygde tegningene, en emoji eller et eget bilde (PNG, JPG, WEBP eller GIF, maks 5 MB). SVG brukes ikke på barnesiden fordi enkelte veggskjermer tegner flere SVG-bilder feil.
