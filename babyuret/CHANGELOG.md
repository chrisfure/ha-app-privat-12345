# Endringslogg

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
