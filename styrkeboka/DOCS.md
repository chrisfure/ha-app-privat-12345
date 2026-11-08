# Styrkeboka

Styrketrening med program, rask logging av sett, hviletimer og en AI-trener – og full historikk så du ser hvordan det har gått.

## Kom i gang

1. Åpne Styrkeboka fra sidemenyen.
2. Lag en profil: mål (generell form, muskelvekst, bli sterkere, rehab/skadeforebygging), erfaring, antall økter i uka, tid per økt, hvor du trener og eventuelle skader eller hensyn.
3. Trykk **Koble til meg** for å koble profilen til Home Assistant-brukeren din. Da åpnes riktig profil automatisk for hver av dere.
4. Lag et program – med AI-treneren eller med appens eget forslag – og juster det som du vil.

Alt lagres lokalt i appens egen database. Ingen navn eller treningsdata ligger i koden.

## Faner

* **Trening** – neste økt i programmet med foreslått vekt per øvelse, valg av treningssted, ukemål og «uker på rad». Start økten, velg en annen økt eller en fri økt.
* **Program** – det aktive programmet, «Juster med AI», redigering, tidligere versjoner og andre programmer.
* **Historikk** – alle økter (trykk for detaljer og endring), fremgang per øvelse med graf, økter per uke og harde sett per muskelgruppe.
* **Innstillinger** – profiler, treningssteder og utstyr, AI-treneren, hviletimer, egne øvelser og eksport.

## Under økta

* Én rad per sett: **kg**, **reps** og (valgfritt) **reps i reserve** – hvor mange reps du kunne klart til. Trykk ✓.
* Vekt og reps er forhåndsutfylt fra forrige sett eller fra forslaget. Manualvekt er per manual.
* Hviletimeren starter automatisk etter hvert sett (vibrasjon og valgfri lyd). Juster med −15/+15.
* **Slik gjør du** viser utgangsstilling, steg for steg, pust og vanlige feil for øvelsen. Hele biblioteket finner du under Program → Øvelsesbibliotek.
* **Bytt** gir øvelser med samme bevegelse. Velg om byttet bare gjelder i dag eller også i programmet.
* **Mer**: endre mål for dagen (sett, reps, hvile), notat, flytt eller fjern øvelsen. Legg til øvelser underveis.
* Oppvarmingssett foreslås for den første tunge øvelsen – trykk på dem for å logge.
* Økta lagres fortløpende, så du kan lukke appen og fortsette senere eller på en annen enhet.

## Programmet og progresjon

Programforslaget bygges ut fra mål, erfaring, tid og utstyr:

| Økter i uka | Oppsett |
|---|---|
| 1–3 | Helkropp A/B/C |
| 4 | Overkropp/underkropp × 2 |
| 5–6 | Overkropp/underkropp + helkropp |

Progresjonen er **dobbel progresjon**: når alle sett når toppen av rep-intervallet, foreslår appen mer vekt neste gang. Ellers beholder du vekten og sikter mot én rep til. Klarer du ikke bunnen av intervallet to økter på rad, foreslås ca. 10 % lettere.

Trener du et sted med mindre utstyr (f.eks. **Hjemme**), byttes øvelser som krever annet utstyr automatisk ut med en tilsvarende øvelse for den økta. Fremgangen følger øvelsen du faktisk gjør.

### Treningsblokker

Programmet går i blokker på **6 uker** (anbefalt; kan settes til 4–8 under Program → blokklinja).

* **Faste hovedøvelser** – knebøy, hoftehengsel, press og trekk er merket «Fast» og står uendret fra blokk til blokk, så du kan måle fremgangen over tid. Du kan endre hva som er fast i redigeringen.
* **Variasjon** – når blokka er ferdig, foreslår appen neste blokk der hjelpeøvelsene byttes med andre øvelser med samme bevegelse. Med AI-treneren ser den også på fremgangen i blokka og kan justere rep-intervaller ved stillstand. Du ser forslaget før noe lagres, og kan også velge «Behold som det er».
* **Lettere uke** – siste uke i blokka har halvparten av settene og samme vekt som sist (deload), så kroppen henter seg inn. Disse øktene telles ikke med i vektforslagene. Av som standard for nybegynnere, som sjelden trenger det.

Hver endring av programmet lagres som en versjon, så du alltid kan gå tilbake.

## AI-treneren

Bruker AI-en du har i Home Assistant (en «AI-oppgave»-entitet, `ai_task.*`, f.eks. fra Anthropic-integrasjonen). Velg hvilken under Innstillinger, eller la appen velge automatisk.

* **Lag program** og **Juster med AI** – du ser alltid forslaget (og hva som er endret) før noe lagres. AI-en kan bare velge øvelser fra biblioteket.
* **Tips før økta** – kort og konkret, ut fra forrige gang.
* **Oppsummering etter økta** – automatisk eller på knappen.
* **Spør treneren** – fra forsiden, under økta eller fra en øvelse.

AI-en får mål, erfaring, utstyr, hensyn du har skrevet og de siste øktene – **aldri navn**. Appen fungerer fullt ut uten AI.

## Home Assistant

* Sensor per profil: `sensor.styrkeboka_<navn>` med antall økter denne uka. Attributter: `plan_per_uke`, `uker_paa_rad`, `siste_okt`, `dager_siden`, `neste_okt`, `trener_naa`, `okter_totalt`.
* Hendelsen `styrkeboka_hendelse` med `handling: okt_startet` eller `okt_fullfort` (med minutter, sett, volum og rekorder).

Eksempel – påminnelse hvis det er gått fire dager:

```yaml
triggers:
  - trigger: template
    value_template: "{{ state_attr('sensor.styrkeboka_<navn>', 'dager_siden') | int(0) >= 4 }}"
actions:
  - action: notify.mobile_app_<telefon>
    data:
      message: "Det er {{ state_attr('sensor.styrkeboka_<navn>', 'dager_siden') }} dager siden sist – {{ state_attr('sensor.styrkeboka_<navn>', 'neste_okt') }} står for tur 💪"
```

## Kilder

* WHO (2020): *Guidelines on physical activity and sedentary behaviour* – muskelstyrkende aktivitet minst 2 dager i uka.
* Helsedirektoratet: *Fysisk aktivitet – råd for voksne* – styrketrening for de store muskelgruppene minst 2 dager i uka.
* ACSM (2009): *Progression models in resistance training for healthy adults* – 8–12 reps for nybegynnere og viderekomne, lettere belastning med 10–15 reps for eldre og ved opptrening.
* Schoenfeld, Ogborn & Krieger (2017): dose–respons for ukentlig volum og muskelvekst (≈10+ sett per muskelgruppe i uka).
* Bell m.fl. (2023): konsensus om lettere uker (deload) – redusert volum med omtrent samme belastning.
* Helms m.fl. (2016): RIR-skalaen («reps in reserve») for å styre hvor nær utmattelse settene går.

Appen og AI-treneren erstatter ikke fysioterapeut eller lege. Trening skal ikke gjøre vondt – stopp ved smerte.
