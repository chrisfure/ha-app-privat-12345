# Endringslogg

## 0.15.0

- Økter gjort bare på klokka registreres: en styrkeaktivitet fra Garmin uten økt i appen blir en fullført økt som teller i ukemål, ringer og programmet. På forsiden bekrefter du hvilken økt det var – «Jeg fulgte planen» fører inn settene med vektene appen foreslo, eller du fører dem inn selv.
- Tredemølle er nytt utstyr: mølletips på løpeturene, to mølleintervaller («Mølle 1–1» og «Mølle 4×4») under Intervalløkt, oppvarming på mølla, og AI-treneren vet om den.
- Løping er enklere: eget «Løping»-kort øverst under Program og «Legg til løping» på forsiden. Velg antall turer og dager – ferdig. Varer til du skrur av (eller 8 uker / egne datoer), og sending til klokka velges samme sted.
- «Klokke og sensorer» er laget på nytt: gruppert etter hva det brukes til, viser hva hver sensor måler akkurat nå, hake på det som hentes, og søk blant alle sensorer når forslaget ikke stemmer. Egen inngang øverst under Helse og under Mer.
- Forsiden: dagsformen står nå rett over dagens økt, og kalendervalg kan åpnes direkte fra ukeplanen.
- Løpeturer fra før løpingen ble lagt inn krysser ikke lenger av ukas plan.

## 0.14.0

- Intervalløkter: HIIT, Tabata, sirkel, EMOM og AMRAP – lag din egen, velg en ferdig økt (bl.a. «Sete og bein», «Kjerne 10», «AMRAP 12», «Kettlebell-AMRAP») eller la treneren lage en ut fra dagsform og utstyr.
- Stor nedtellingsklokke i fullskjerm: fargekodet jobb/pause, nåværende og neste øvelse, runde og øvelse, oversikt over alle øvelsene, pip de siste sekundene, opplesning av øvelsene og skjermen holdes på. AMRAP teller runder med «Neste øvelse»-knappen og viser ny rekord.
- Gjennomførte intervalløkter teller som aktivitet (høy intensitet) i ringene og uke-kjeden. Kjører du samtidig økta på klokka, slås den sammen med Garmin-aktiviteten og får pulsen derfra.
- 18 nye øvelser: kondisjon (burpees, fjellklatrer, sprellemann, hoppknebøy, skøyterhopp, thrusters m.fl.), sete (eselspark, sidehev på alle fire, sumoknebøy) og kjerne (sykkelcrunch, russisk vri, saksespark, planke med skulderklapp).

## 0.13.0

- Egen AI til planlegging: velg en kraftigere modell (f.eks. Claude Sonnet) for program, justering, ny blokk, ukeplan og startvekter, mens tips, oppsummeringer og spørsmål bruker den raske og billige.

## 0.12.0

- AI-treneren får en treningsanalyse når den lager program, ny blokk, ukeplan eller svarer på spørsmål: oppmøte siste 12 uker, progresjon per øvelse (med stillstand markert), harde sett per muskelgruppe, opplevd tyngde og formtrend (søvn, HRV, hvilepuls, stress siste 7 mot 28 dager).

## 0.11.0

- Ny forside med ringer som skal lukkes hver uke: styrkeøkter, aktivitetsminutter og søvn (eller arbeidssett uten søvndata).
- Uke-kjede: én sirkel per dag – sirklene smelter sammen når du trener flere dager på rad, og planlagte økter vises stiplet.
- Nivå og XP for økter, sett, rekorder, ukemål og kondisjon, ukerekke med flamme, nye rekorder denne uka og 14 merker å samle – med feiring når du tar et nytt.
- Personvern: AI-treneren får ikke lenger titler eller steder fra kalenderen, bare status per dag (hjemme, borte, reisedag, opptatt fra–til).

## 0.10.2

- Reiser over flere dager vises med hele perioden (og «siste dag»), så AI-treneren ser om du er på vei ut eller hjem.

## 0.10.1

- Kalenderforslag: Garmins egen øktkalender og arbeidsdag-kalendere foreslås ikke lenger som jobbkalender.

## 0.10.0

- Dagsform: søvn (score og lengde), HRV mot ditt eget snitt, Body Battery, stress, treningsberedskap og restitusjonstid hentes fra klokka. Forsiden viser dagsformen med råd, og «Gjør økta lettere» når formen er lav.
- Kalendere: velg jobb- og reisekalender. Ny ukeplan for de neste 7 dagene legger styrkeøkter og løpeturer rundt reiser, lange dager og dagsformen.
- «Planlegg uka med AI»: AI-treneren lager ukeplanen ut fra kalender, dagsform, løpeplan og ønskene dine.
- AI-treneren bruker dagsform og kalender i alle råd og svar.
- Neste styrkeøkt legges i Garmin-kalenderen på dagen fra ukeplanen.

## 0.9.0

- Styrkeøkter til klokka: hver økt i programmet ligger i Garmin som strukturert styrkeøkt med øvelser, sett, reps, vekt, hvile og oppvarmingssett – oppdatert med dagens vektforslag etter hver økt. Neste økt legges i Garmin-kalenderen, så klokka guider deg og Garmin-aktiviteten får øvelser og vekter.
- Øvelsene kobles til Garmins egne øvelseskategorier (og nøyaktige navn der de er sikre).
- «Send fullførte økter som aktivitet» er nå tydelig merket som et valg for deg som ikke starter økta på klokka.

## 0.8.0

- Styrkeøkter du starter på klokka kobles automatisk til økta i appen (samme tidspunkt). Appen har settene, klokka pulsen – nå ser du begge sammen.
- Pulskurve fra klokka i økta, med streker der hvert sett ble logget, tid i pulssoner, kalorier og treningsbelastning.
- Puls per øvelse: snittet av pulstoppene i settene og pulsen rett før neste sett (hvor mye du henter deg inn i pausene).
- Løpeturer og andre aktiviteter får pulskurve, tempo og tid i soner.
- AI-oppsummeringen bruker pulsen (f.eks. om hvilen var lang nok).
- Pulskurver hentes som aktivitetsfil (TCX) fra Garmin via Home Assistant; appen leser pulsen og sletter fila igjen, så GPS-spor ikke blir liggende. Krever lese/skrivetilgang til Home Assistant-mappa.
- «Send styrkeøkter til Garmin» er fortsatt tilgjengelig, men bør være av når du starter økta på klokka.

## 0.7.0

- Til Garmin Connect (via Home Assistant): fullførte styrkeøkter kan sendes som aktivitet, automatisk eller med «Send til Garmin» på en økt.
- Løpeturer til klokka: turene i løpeplanen legges i Garmin-kalenderen 2 uker fram som strukturerte økter (oppvarming, drag, pauser og pulssoner). Endrer du perioden, oppdateres kalenderen.
- Løpeperioder har nå faste løpedager (1–3 i uka), og ukeplanen viser hvilken dag hver tur er.

## 0.6.0

- Fanen «Kropp» heter nå «Helse».
- Oppvarming: generell oppvarming (5 min lett puls + bevegelighet tilpasset dagens øvelser) øverst i økta, og oppvarmingssett på første tunge øvelse for både underkropp og overkropp – med et kort tilvenningssett på neste tunge øvelse.
- Løpeperioder: legg inn en periode (f.eks. sommeren) med 1–3 løpeturer i uka. Ukeplan med rolig tur, intervaller (4×4-metoden) og langtur, gradvis økning, lettere uke hver 4. uke og pulssoner. Turer fra klokka krysses av automatisk. Valgfritt: ett sett mindre på hjelpeøvelser for bein i perioden.
- AI-treneren kjenner løpeperioden og ukas løpeturer.

## 0.5.0

- Ny fane «Kropp»: vekt, midjemål, fettprosent, hvilepuls, VO₂max, skritt og blodtrykk med kurver over tid (vekt med 7 dagers snitt).
- Løping, gåing, sykling, ski m.m.: hentes automatisk fra klokke/Garmin Connect via Home Assistant, eller registreres manuelt. Tempo, distanse, puls og høydemeter.
- Aktivitetsminutter per uke (moderat + 2 × høy intensitet, inkl. styrkeøkter) mot anbefalingen på 150 minutter.
- Kroppsprofil med fødselsår, høyde og kjønn: BMI, midje/høyde-forhold, estimert makspuls og pulssoner.
- AI-treneren tar hensyn til alder, vektutvikling, hvilepuls, VO₂max og kondisjonstreningen de siste to ukene.
- Sensoren per profil har fått aktivitetsminutter, km løping/gåing og vekt.
- Fanen «Innstillinger» heter nå «Mer».

## 0.4.0

- Hviletimeren står stille: knappene tegnes ikke lenger på nytt hvert kvarter sekund, så de er lette å treffe.
- Startvekter: oppgi kroppsvekt og ett–to løft du kjenner (f.eks. benkpress 80 × 5), så anslår AI-treneren – eller appen selv – vekt på alle øvelsene i programmet. Du kan justere før du lagrer.
- Øvelser du ikke har gjort før får automatisk et vektforslag ut fra det du løfter i andre øvelser (styrkeforhold mellom øvelser).
- Alle vektforslag rundes til vekter som finnes (stang 2,5 kg, manualer 1–2 kg, apparat 2,5–5 kg).

## 0.3.1

- AI-treneren gir praktiske tips ved plager i stedet for standardforbehold, og henviser ikke til lege/fysioterapeut uten at du spør.
- Fjernet faste forbehold om smerte fra øvelsesinstruksjonene og appen.

## 0.3.0

- Treningsblokker: programmet går i blokker på 6 uker (kan settes til 4–8).
- Hovedøvelsene (knebøy, hoftehengsel, press og trekk) er låst som «Fast» og beholdes fra blokk til blokk; hjelpeøvelsene byttes ut for variasjon.
- Når en blokk er ferdig, foreslår appen (eller AI-treneren, ut fra fremgangen i blokka) neste blokk – du godkjenner før noe endres.
- Lettere uke (deload) som siste uke i blokka: halvparten av settene, samme vekt. Teller ikke med i vektforslagene. Av som standard for nybegynnere.
- «Fast hovedøvelse» kan slås av og på per øvelse i programmet.

## 0.2.0

- Instruksjoner for alle 80 øvelsene: utgangsstilling, steg for steg, pust og vanlige feil.
- «Slik gjør du» fra økta, programmet, øvelsesvelgeren, bytte-listen og fremgangen per øvelse.
- Øvelsesbibliotek under Program, med søk.
- Egne øvelser kan få sin egen steg-for-steg-instruksjon.
- Lenke for å søke etter video av øvelsen.

## 0.1.0

- Første versjon: profiler med mål, erfaring, tid, treningssted og hensyn – koblet til Home Assistant-brukeren.
- Programforslag ut fra mål og utstyr, redigering, versjonshistorikk og flere programmer per profil.
- Økt med forhåndsutfylte sett, reps i reserve, hviletimer, oppvarming, bytte av øvelse (i dag eller i programmet) og automatisk tilpasning til utstyret der du trener.
- Dobbel progresjon med forslag om mer vekt, likt eller nedtrapping.
- Historikk: alle økter (kan endres i etterkant), fremgang per øvelse med estimert 1RM, økter per uke og sett per muskelgruppe.
- AI-trener via Home Assistant (ai_task): lag og juster program, tips før økta, oppsummering etter og «spør treneren».
- Sensor per profil, hendelser og CSV-eksport.
