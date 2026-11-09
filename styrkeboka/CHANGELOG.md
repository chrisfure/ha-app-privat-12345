# Endringslogg

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
