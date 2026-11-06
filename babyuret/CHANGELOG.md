# Endringslogg

## 0.4.1

* Bruksanvisning for lydgjenkjenning i appen (Innstillinger → Lydgjenkjenning → «Slik bruker du det»), med ferdig utfylte data for hver enhet og kopier-knapp.

## 0.4.0

* Lydgjenkjenning: gråt og rop fra lytteenheter (hendelsen `babyuret_lyd`) brukes som data til søvnloggen. Appen sender ingen varsler.
* Fire sperrer før lyd teller: kjent enhet, enheten er der babyen er, søvn pågår og innsovningsvinduet er passert.
* Poengsum over et glidende vindu med tillegg for flere enheter samtidig og nærhet til prognosen, og trekk for motbevis fra stua og kort søvn.
* «Våknet kl. …?» på forsiden: bekreft med Våknet, Sovnet igjen eller Feil. Ubesvarte forslag avslutter søvnen automatisk etter svarfristen, merket «avsluttet automatisk».
* Babyens sted: hjemme, i vogna ute, ute, på reise og barnevakt hjemme/ute, med valg av hvilke enheter som er med babyen.
* Søvn får sted (seng, vogn, bil, bæresele) og støykilde. Støykilde hever terskelen og huskes til neste søvn.
* Læring: terskelen justeres lokalt ut fra hvor ofte forslagene var riktige.
* Lytteenheter, hjemmenett og terskler stilles inn under Innstillinger → Lydgjenkjenning, med lydlogg og treffsikkerhet.
* Nye sensorer: `sensor.babyuret_sted` og `sensor.babyuret_lyd`.

## 0.3.1

- Retting: appen fant ikke tilgangsnøkkelen til Home Assistant, så sensorer og hendelser virket ikke.

## 0.3.0

* Søvnprognose: når babyen trolig sovner neste gang og hvor lenge, eller når den trolig våkner. Regnes lokalt fra egne data, med Helsenorges beskrivelse av nyfødte som startestimat.
* Dagbok: søvn siste 24 timer sammenlignet med Helsenorges normalområde for alderen.
* Ny fane Målinger: vekt, lengde, hodeomkrets og temperatur, med WHO-vekstkurver og persentil.
* Nøytrale merknader om vekttap etter fødsel (Helsedirektoratet) og feber hos de minste (Helsenorge).
* Ny innstilling: kjønn (kun for vekstkurve). Kildeliste i innstillingene.
* Ny sensor: `sensor.babyuret_prognose`.

## 0.2.0

* Tre faner: Registrer, Dagbok og Innstillinger.
* Navn, fødselsdato/termin, mating, flaskemengde og nattmodus stilles inn i appen (ikke lenger i HA-konfigurasjonen).
* Velkomstkort første gang, og nedtelling til termin.

## 0.1.0

* Første versjon: registrering av søvn, amming, flaske og bleier.
* Ett-trykks knapper med Angre/Endre, dagslogg, døgnstripe og nøkkeltall.
* Nattmodus (automatisk etter klokkeslett, kan overstyres).
* Sensorer til Home Assistant og hendelsen `babyuret_registrer` for knapper, NFC og Assist.
* CSV-eksport.
