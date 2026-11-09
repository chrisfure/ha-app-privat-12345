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
* **Helse** – målinger med kurver, løping/gåing og annen aktivitet, aktivitetsminutter og kroppsprofil.
* **Mer** – profiler, treningssteder og utstyr, AI-treneren, hviletimer, egne øvelser og eksport.

## Under økta

* Én rad per sett: **kg**, **reps** og (valgfritt) **reps i reserve** – hvor mange reps du kunne klart til. Trykk ✓.
* Vekt og reps er forhåndsutfylt fra forrige sett eller fra forslaget. Manualvekt er per manual.
* Hviletimeren starter automatisk etter hvert sett (vibrasjon og valgfri lyd). Juster med −15/+15.
* **Slik gjør du** viser utgangsstilling, steg for steg, pust og vanlige feil for øvelsen. Hele biblioteket finner du under Program → Øvelsesbibliotek.
* **Bytt** gir øvelser med samme bevegelse. Velg om byttet bare gjelder i dag eller også i programmet.
* **Mer**: endre mål for dagen (sett, reps, hvile), notat, flytt eller fjern øvelsen. Legg til øvelser underveis.
* **Oppvarming:** øverst i økta står en generell oppvarming (5 min lett puls + bevegelighet for leddene som skal jobbe). Den første tunge øvelsen for underkroppen og for overkroppen får oppvarmingssett, og neste tunge øvelse et kort tilvenningssett – trykk på dem for å logge.
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

### Startvekter

Første gang du gjør en øvelse, foreslår appen vekt i denne rekkefølgen:

1. **Startvekt du har lagret** – under Trening («Finn startvekter»), Program → Startvekter eller i økt-menyen. Oppgi kroppsvekt og ett–to løft du kjenner (vekt × reps), så anslår AI-treneren (eller appen) vekt på alle øvelsene. Du justerer før du lagrer.
2. **Anslag fra andre øvelser du har logget** – f.eks. benkpress med stang → skråbenk med manualer, ut fra vanlige styrkeforhold mellom øvelser.
3. **Løftene eller kroppsvekten du har oppgitt.**

Anslagene er litt forsiktige med vilje. Etter første økt er det din egen fremgang som styrer forslagene.

### Løpeperioder

Under **Program → Løping i perioder** kan du legge inn en periode (f.eks. «Sommer (juni–august)» eller «8 uker fra mandag») og velge 1–3 faste løpedager:

* **Ukeplan på forsiden** – rolig tur, intervalløkt (4×4 min i sone 4, med kortere drag i starten) og langtur, med gradvis økning og en lettere uke hver fjerde uke. Nybegynnere får løp/gå-intervaller.
* **Pulssoner** regnes fra estimert makspuls (krever fødselsår i profilen).
* **Turer fra klokka krysses av automatisk.** Uten klokke: «Registrer løpetur selv».
* **Juster styrketreningen** (på som standard): ett sett mindre på hjelpeøvelser for bein i perioden. Hovedøvelsene endres ikke.
* Legg helst intervalløkta minst en dag før en tung beinøkt.

### Puls fra klokka

* **Styrkeøkter fra klokka kobles til økta i appen** når de starter omtrent samtidig. Økta i appen får da pulskurve med streker der settene ble logget, tid i pulssoner, kalorier og treningsbelastning – og «puls per øvelse»: snittet av pulstoppene i settene og pulsen rett før neste sett.
* **Løpeturer og andre aktiviteter** får pulskurve, tempo (min/km) og tid i soner.
* **AI-treneren** bruker pulsen i oppsummeringen av økta.
* Pulskurvene hentes med `garmin_connect.download_activity` (TCX-fil) for aktiviteter de siste tre ukene. Appen leser puls og fart og **sletter fila** etterpå, så GPS-sporet ikke blir liggende i Home Assistant eller i sikkerhetskopiene. Derfor har appen tilgang til Home Assistant-mappa (`homeassistant_config`), men den bruker bare `garmin_activities`.

### Til Garmin Connect

Er profilen koblet til Garmin (Helse → Hent data fra Home Assistant), finner du **Helse → Til Garmin Connect**:

* **Styrkeøkter til klokka** – hver økt i programmet ligger i Garmin som en strukturert styrkeøkt («Styrkeboka: Helkropp A») med øvelser, sett, reps, vekt, hvile og oppvarmingssett. Vektene oppdateres etter hver økt (og når du endrer program eller startvekter), og neste økt legges i Garmin-kalenderen – i dag, eller i morgen hvis du allerede har trent. Start den på klokka (Styrke → Treningskalender / Treningsøkter), så får Garmin-aktiviteten øvelser og vekter, og appen kobler pulsen til økta di. Logg likevel settene i appen – avvik du legger inn på klokka hentes ikke tilbake. Øvelsene vises med Garmins kategori (f.eks. «Roing») der vi ikke er sikre på det nøyaktige navnet.
* **Send fullførte økter som aktivitet** – for deg som *ikke* starter økta på klokka: fullførte økter legges inn som aktivitet med starttid og varighet.
* **Løpeturer til klokka** – turene i løpeplanen legges i Garmin-kalenderen to uker fram, som strukturerte økter med oppvarming, drag, pauser og pulssoner (klokkas egne soner). Start dem fra treningskalenderen på klokka. Endres eller slettes perioden, oppdateres kalenderen.

Bruker tjenestene `garmin_connect.create_activity`, `create_workout`, `update_workout`, `delete_workout`, `schedule_workout` og `unschedule_workout` fra Garmin Connect-integrasjonen.

### Treningsblokker

Programmet går i blokker på **6 uker** (anbefalt; kan settes til 4–8 under Program → blokklinja).

* **Faste hovedøvelser** – knebøy, hoftehengsel, press og trekk er merket «Fast» og står uendret fra blokk til blokk, så du kan måle fremgangen over tid. Du kan endre hva som er fast i redigeringen.
* **Variasjon** – når blokka er ferdig, foreslår appen neste blokk der hjelpeøvelsene byttes med andre øvelser med samme bevegelse. Med AI-treneren ser den også på fremgangen i blokka og kan justere rep-intervaller ved stillstand. Du ser forslaget før noe lagres, og kan også velge «Behold som det er».
* **Lettere uke** – siste uke i blokka har halvparten av settene og samme vekt som sist (deload), så kroppen henter seg inn. Disse øktene telles ikke med i vektforslagene. Av som standard for nybegynnere, som sjelden trenger det.

Hver endring av programmet lagres som en versjon, så du alltid kan gå tilbake.

## Helse: kropp og kondisjon

Fanen **Helse** samler kroppen og all aktivitet utenom styrketreningen:

* **Målinger med kurver** – vekt (med 7 dagers snitt), midjemål, fettprosent, hvilepuls, VO₂max, skritt og blodtrykk. Legg inn selv med «Ny måling», eller hent automatisk.
* **Løping, gåing og annen aktivitet** – distanse, tid, tempo, puls og høydemeter. Registrer manuelt eller hent fra klokka.
* **Aktivitetsminutter** – moderat + 2 × høy intensitet per uke, med styrkeøktene inkludert, mot anbefalingen på 150–300 minutter (WHO/Helsedirektoratet).
* **Kroppsprofil** – fødselsår, høyde og kjønn gir BMI, midje/høyde-forhold, estimert makspuls (HUNT-formelen: 211 − 0,64 × alder) og pulssoner.

### Automatisk henting fra Home Assistant

Har du f.eks. Garmin Connect-integrasjonen, trykk **Helse → Hent data automatisk** og velg sensorene som hører til profilen (appen foreslår ut fra navnene). Aktiviteter hentes fra sensoren med `last_activities`, og vekt, hvilepuls, VO₂max, skritt og fettprosent fra de vanlige sensorene. Første gang hentes også historikk bakover (så langt Home Assistant har den), deretter hvert kvarter.

* Styrketrening registrert på klokka hoppes over – den logges i appen.
* GPS-posisjoner lagres ikke.
* Målinger du legger inn selv overskrives ikke av automatisk henting samme dag.

### Dagsform: søvn, HRV, stress og restitusjon

Kobler du også søvn, HRV, Body Battery, stress, treningsberedskap og restitusjonstid (Garmin-sensorene foreslås automatisk), viser forsiden et **dagsformkort** – god, middels eller lav – med grunnene og et konkret råd. HRV sammenlignes med ditt eget snitt de siste ukene. Er formen ikke god, kan du trykke **Gjør økta lettere** i økta (færre sett, litt lavere vekt).

### Ukeplan rundt kalenderen

Velg kalenderne dine (jobb, reiser, f.eks. TripIt) i samme ark. Forsiden viser **de neste 7 dagene** med styrkeøkter og løpeturer: dager du er borte (reise, kurs, ferie, hytte – eller heldagshendelser med sted) og svært lange dager hoppes over, og øktene spres med hvile mellom. Jobbvakter teller som opptatte timer, ikke som borte. **Planlegg uka med AI** lager en mer gjennomtenkt plan ut fra kalender, dagsform, løpeplan og ønsker du skriver. Neste styrkeøkt legges i Garmin-kalenderen på dagen fra ukeplanen.

Kalenderhendelsene (titler, tider og sted) sendes til AI-en når den planlegger – velg derfor bare kalendere du er komfortabel med.

## AI-treneren

Bruker AI-en du har i Home Assistant (en «AI-oppgave»-entitet, `ai_task.*`, f.eks. fra Anthropic-integrasjonen). Velg hvilken under Innstillinger, eller la appen velge automatisk.

* **Lag program** og **Juster med AI** – du ser alltid forslaget (og hva som er endret) før noe lagres. AI-en kan bare velge øvelser fra biblioteket.
* **Tips før økta** – kort og konkret, ut fra forrige gang.
* **Oppsummering etter økta** – automatisk eller på knappen.
* **Spør treneren** – fra forsiden, under økta eller fra en øvelse.

AI-en får mål, erfaring, utstyr, hensyn du har skrevet, de siste øktene, dagsformen og kalenderen for de neste 7 dagene – **aldri navn**. Appen fungerer fullt ut uten AI.

## Home Assistant

* Sensor per profil: `sensor.styrkeboka_<navn>` med antall økter denne uka. Attributter: `plan_per_uke`, `uker_paa_rad`, `siste_okt`, `dager_siden`, `neste_okt`, `trener_naa`, `okter_totalt`, `aktivitetsminutter_uke`, `km_loping_uke`, `km_gaing_uke`, `vekt`.
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

* Nes m.fl. (2013), HUNT: *Age-predicted maximal heart rate in healthy subjects* – makspuls ≈ 211 − 0,64 × alder.
* WHO (2020): *Guidelines on physical activity and sedentary behaviour* – muskelstyrkende aktivitet minst 2 dager i uka.
* Helsedirektoratet: *Fysisk aktivitet – råd for voksne* – styrketrening for de store muskelgruppene minst 2 dager i uka.
* ACSM (2009): *Progression models in resistance training for healthy adults* – 8–12 reps for nybegynnere og viderekomne, lettere belastning med 10–15 reps for eldre og ved opptrening.
* Schoenfeld, Ogborn & Krieger (2017): dose–respons for ukentlig volum og muskelvekst (≈10+ sett per muskelgruppe i uka).
* Bell m.fl. (2023): konsensus om lettere uker (deload) – redusert volum med omtrent samme belastning.
* Helms m.fl. (2016): RIR-skalaen («reps in reserve») for å styre hvor nær utmattelse settene går.
