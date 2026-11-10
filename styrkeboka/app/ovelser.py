"""Øvelsesbibliotek for Styrkeboka.

Hver øvelse har en fast nøkkel (brukes i database og av AI), et bevegelsesmønster
(brukes til å bytte øvelse og bygge program), utstyr som kreves og korte teknikkpunkter.

Utstyr (alle må være tilgjengelige):
  stang      – vektstang med skiver        stativ    – knebøystativ / rack
  benk       – treningsbenk                 manualer  – manualer
  kettlebell – kettlebell                   kabel     – kabelapparat / kryss
  maskiner   – vanlige apparater (beinpress, nedtrekk, beincurl …)
  trekkstang – stang for pull-ups           strikk    – treningsstrikk
Kroppsvektøvelser har tom utstyrsliste.

Type styrer vektsteg ved progresjon:
  stang 2,5 kg · manualer 2 kg (vekt per manual) · maskin 5 kg · kabel 2,5 kg
  kettlebell 4 kg · kroppsvekt/strikk: flere reps eller tyngre variant
"""
from __future__ import annotations

UTSTYR = {
    "stang": "Vektstang og skiver",
    "stativ": "Knebøystativ",
    "benk": "Treningsbenk",
    "manualer": "Manualer",
    "kettlebell": "Kettlebell",
    "kabel": "Kabelapparat",
    "maskiner": "Apparater (beinpress, nedtrekk o.l.)",
    "trekkstang": "Stang for pull-ups",
    "strikk": "Treningsstrikk",
    "tredemolle": "Tredemølle",
}

MONSTER = {
    "kne": "Knebøy",
    "hofte": "Hoftehengsel",
    "utfall": "Ettbeins",
    "sete": "Sete",
    "press_hor": "Press fremover",
    "press_vert": "Press over hodet",
    "trekk_hor": "Roing",
    "trekk_vert": "Nedtrekk",
    "kjerne": "Kjerne",
    "skulderhelse": "Skulderhelse",
    "skuldre_iso": "Skuldre",
    "biceps": "Biceps",
    "triceps": "Triceps",
    "bakside_iso": "Bakside lår",
    "forside_iso": "Forside lår",
    "legger": "Legger",
    "bryst_iso": "Bryst",
    "kondisjon": "Kondisjon",
}

MUSKLER = {
    "lar_forside": "Forside lår", "lar_bakside": "Bakside lår", "sete": "Sete", "legger": "Legger",
    "bryst": "Bryst", "rygg": "Rygg", "korsrygg": "Korsrygg", "skuldre": "Skuldre",
    "biceps": "Biceps", "triceps": "Triceps", "kjerne": "Kjerne",
}

STEG = {"stang": 2.5, "manualer": 2.0, "maskin": 5.0, "kabel": 2.5, "kettlebell": 4.0, "kroppsvekt": 0.0, "strikk": 0.0}


def _o(nokkel, navn, monster, typ, utstyr, muskler, niva, skansom, sammensatt, tips):
    return {
        "nokkel": nokkel, "navn": navn, "monster": monster, "type": typ, "utstyr": list(utstyr),
        "muskler": list(muskler), "niva": niva, "skansom": skansom, "sammensatt": sammensatt,
        "tips": list(tips), "egen": False,
    }


BIBLIOTEK: list[dict] = [
    # ---------------------------------------------------------------- knebøy
    _o("knebøy-stang", "Knebøy med stang", "kne", "stang", ["stang", "stativ"], ["lar_forside", "sete", "kjerne"], 2, False, True,
       ["Pust inn og stram magen før du går ned", "Knærne følger tærne", "Gå så dypt du klarer med nøytral rygg"]),
    _o("frontknebøy", "Frontknebøy", "kne", "stang", ["stang", "stativ"], ["lar_forside", "sete", "kjerne"], 3, False, True,
       ["Albuene høyt", "Oppreist overkropp", "Press opp gjennom hele foten"]),
    _o("goblet-knebøy", "Goblet-knebøy", "kne", "manualer", ["manualer"], ["lar_forside", "sete", "kjerne"], 1, True, True,
       ["Hold manualen inntil brystet", "Albuene peker ned mellom knærne", "Rolig ned, bestemt opp"]),
    _o("goblet-knebøy-kb", "Goblet-knebøy med kettlebell", "kne", "kettlebell", ["kettlebell"], ["lar_forside", "sete", "kjerne"], 1, True, True,
       ["Hold kettlebellen inntil brystet", "Sitt mellom hælene", "Hold brystet oppe"]),
    _o("beinpress", "Beinpress", "kne", "maskin", ["maskiner"], ["lar_forside", "sete"], 1, True, True,
       ["Hele foten på platen", "Ikke lås knærne helt i toppen", "Korsryggen blir liggende mot setet"]),
    _o("knebøy-kroppsvekt", "Knebøy uten vekt", "kne", "kroppsvekt", [], ["lar_forside", "sete"], 1, True, True,
       ["Sitt bakover som mot en stol", "Vekten på hele foten", "Armene frem for balanse"]),
    _o("boks-knebøy", "Knebøy til benk", "kne", "kroppsvekt", ["benk"], ["lar_forside", "sete"], 1, True, True,
       ["Sett deg kontrollert ned til benken", "Reis deg uten å kaste overkroppen", "Godt utgangspunkt ved kneplager"]),

    # ---------------------------------------------------------------- hofte
    _o("markløft", "Markløft", "hofte", "stang", ["stang"], ["lar_bakside", "sete", "korsrygg", "rygg"], 2, False, True,
       ["Stangen tett inntil leggene", "Nøytral rygg – skyv gulvet vekk", "Stå helt oppreist i toppen uten å lene bakover"]),
    _o("rumensk-markløft", "Rumensk markløft", "hofte", "stang", ["stang"], ["lar_bakside", "sete", "korsrygg"], 2, False, True,
       ["Lett bøy i knærne", "Skyv hoftene bakover", "Kjenn strekk bak på lårene, stopp før ryggen runder"]),
    _o("rumensk-markløft-man", "Rumensk markløft med manualer", "hofte", "manualer", ["manualer"], ["lar_bakside", "sete", "korsrygg"], 1, True, True,
       ["Manualene glir langs lårene", "Hoftene bakover, ryggen rett", "Klem setet i toppen"]),
    _o("kettlebell-sving", "Kettlebell-sving", "hofte", "kettlebell", ["kettlebell"], ["sete", "lar_bakside", "kjerne"], 2, False, True,
       ["Bevegelsen kommer fra hofta, ikke armene", "Eksplosiv hoftestrekk", "Stram mage og sete i toppen"]),
    _o("kettlebell-markløft", "Markløft med kettlebell", "hofte", "kettlebell", ["kettlebell"], ["lar_bakside", "sete"], 1, True, True,
       ["Kettlebellen mellom føttene", "Hoftene bakover, rett rygg", "Reis deg ved å skyve hoftene frem"]),
    _o("ryggstrekk", "Ryggstrekk på benk", "hofte", "kroppsvekt", ["maskiner"], ["korsrygg", "sete", "lar_bakside"], 1, True, False,
       ["Bøy i hofta, ikke i ryggen", "Kontrollert tempo", "Ikke overstrekk i toppen"]),
    _o("good-morning-strikk", "Good morning med strikk", "hofte", "strikk", ["strikk"], ["lar_bakside", "sete"], 1, True, True,
       ["Strikken under føttene og bak nakken", "Hoftene bakover", "Rett rygg hele veien"]),

    # ---------------------------------------------------------------- ettbeins
    _o("bulgarsk-utfall", "Bulgarsk utfall", "utfall", "manualer", ["manualer", "benk"], ["lar_forside", "sete"], 2, False, True,
       ["Bakre fot på benken", "Gå rett ned", "Fremre kne følger tærne"]),
    _o("utfall-manualer", "Utfall med manualer", "utfall", "manualer", ["manualer"], ["lar_forside", "sete"], 1, True, True,
       ["Langt nok steg til at begge knær blir ca. 90°", "Oppreist overkropp", "Skyv fra med fremre fot"]),
    _o("step-up", "Step-up på benk", "utfall", "manualer", ["manualer", "benk"], ["lar_forside", "sete"], 1, True, True,
       ["Hele foten på benken", "Press opp med fremre bein, ikke sprett fra bakre", "Kontrollert ned"]),
    _o("utfall-kroppsvekt", "Utfall uten vekt", "utfall", "kroppsvekt", [], ["lar_forside", "sete"], 1, True, True,
       ["Kontrollert ned", "Knær i linje med tærne", "Hold balansen – bruk vegg ved behov"]),
    _o("bakoverutfall", "Bakoverutfall", "utfall", "manualer", ["manualer"], ["lar_forside", "sete"], 1, True, True,
       ["Skånsomt for knærne", "Ta et steg bakover og senk deg rolig", "Press opp gjennom fremre hæl"]),

    # ---------------------------------------------------------------- sete
    _o("hoftehev-stang", "Hip thrust med stang", "sete", "stang", ["stang", "benk"], ["sete", "lar_bakside"], 2, True, True,
       ["Skulderbladene mot benken", "Haka ned, press hoftene opp", "Klem setet i toppen"]),
    _o("setehev", "Setehev på gulv", "sete", "kroppsvekt", [], ["sete", "lar_bakside"], 1, True, False,
       ["Føttene nær setet", "Press opp gjennom hælene", "Hold et sekund i toppen"]),
    _o("setehev-ettbeins", "Setehev på ett bein", "sete", "kroppsvekt", [], ["sete", "lar_bakside"], 2, True, False,
       ["Hoftene holdes vannrett", "Press gjennom hælen", "Rolig ned"]),
    _o("hoftehev-manual", "Hip thrust med manual", "sete", "manualer", ["manualer", "benk"], ["sete", "lar_bakside"], 1, True, True,
       ["Manualen på hofteleddet", "Skulderbladene mot benken", "Klem setet i toppen"]),
    _o("sidegange-strikk", "Sidegange med strikk", "sete", "strikk", ["strikk"], ["sete"], 1, True, False,
       ["Strikk rundt knær eller ankler", "Lett bøy i knærne", "Små kontrollerte steg"]),

    # ---------------------------------------------------------------- press fremover
    _o("benkpress", "Benkpress", "press_hor", "stang", ["stang", "benk", "stativ"], ["bryst", "triceps", "skuldre"], 2, False, True,
       ["Skulderbladene sammen og ned", "Stangen ned mot nedre del av brystet", "Føttene godt i gulvet"]),
    _o("benkpress-manualer", "Benkpress med manualer", "press_hor", "manualer", ["manualer", "benk"], ["bryst", "triceps", "skuldre"], 1, True, True,
       ["Albuene ca. 45° ut fra kroppen", "Kontrollert ned til strekk i brystet", "Press opp og litt inn"]),
    _o("skrå-benk-manualer", "Skråbenk med manualer", "press_hor", "manualer", ["manualer", "benk"], ["bryst", "skuldre", "triceps"], 1, True, True,
       ["Benken på 30–45°", "Skulderbladene bakover", "Press rett opp over skuldrene"]),
    _o("brystpress-maskin", "Brystpress i apparat", "press_hor", "maskin", ["maskiner"], ["bryst", "triceps"], 1, True, True,
       ["Håndtakene i høyde med midten av brystet", "Skuldrene bort fra ørene", "Rolig tilbake"]),
    _o("armhevinger", "Armhevinger", "press_hor", "kroppsvekt", [], ["bryst", "triceps", "kjerne"], 1, True, True,
       ["Kroppen rett som en planke", "Albuene ca. 45° ut", "Lettere: hendene på benk eller knærne i gulvet"]),
    _o("brystpress-strikk", "Brystpress med strikk", "press_hor", "strikk", ["strikk"], ["bryst", "triceps"], 1, True, True,
       ["Strikken festet bak deg i brysthøyde", "Press frem og litt inn", "Kontrollert tilbake"]),

    # ---------------------------------------------------------------- press over hodet
    _o("stående-press", "Stående skulderpress", "press_vert", "stang", ["stang", "stativ"], ["skuldre", "triceps", "kjerne"], 2, False, True,
       ["Stram sete og mage", "Stangen tett forbi ansiktet", "Hodet frem under stangen i toppen"]),
    _o("skulderpress-manualer", "Skulderpress med manualer", "press_vert", "manualer", ["manualer"], ["skuldre", "triceps"], 1, True, True,
       ["Sittende eller stående", "Albuene litt foran kroppen", "Ikke svai i korsryggen"]),
    _o("landmine-press", "Ettarms press skrått opp", "press_vert", "manualer", ["manualer"], ["skuldre", "bryst", "triceps"], 1, True, True,
       ["Skånsom variant for skuldre", "Press skrått frem og opp", "Stram mage, ikke vri kroppen"]),
    _o("skulderpress-maskin", "Skulderpress i apparat", "press_vert", "maskin", ["maskiner"], ["skuldre", "triceps"], 1, True, True,
       ["Setet justert så håndtakene er i skulderhøyde", "Ryggen mot ryggstøtten", "Rolig ned"]),
    _o("pike-armhevinger", "Pike-armhevinger", "press_vert", "kroppsvekt", [], ["skuldre", "triceps"], 2, False, True,
       ["Hoftene høyt – kroppen som en omvendt V", "Hodet ned mellom hendene", "Kontrollert tempo"]),
    _o("skulderpress-strikk", "Skulderpress med strikk", "press_vert", "strikk", ["strikk"], ["skuldre", "triceps"], 1, True, True,
       ["Stå på strikken", "Press rett opp", "Stram mage"]),

    # ---------------------------------------------------------------- roing
    _o("roing-stang", "Roing med stang", "trekk_hor", "stang", ["stang"], ["rygg", "biceps", "korsrygg"], 2, False, True,
       ["Overkroppen ca. 45° frem", "Trekk stangen mot navlen", "Skulderbladene sammen"]),
    _o("ettarms-roing", "Ettarms roing med manual", "trekk_hor", "manualer", ["manualer", "benk"], ["rygg", "biceps"], 1, True, True,
       ["Støtt hånd og kne på benken", "Trekk albuen bakover mot hofta", "Ikke vri overkroppen"]),
    _o("sittende-roing", "Sittende roing i kabel", "trekk_hor", "kabel", ["kabel"], ["rygg", "biceps"], 1, True, True,
       ["Oppreist overkropp", "Trekk mot magen", "Skulderbladene sammen og ned"]),
    _o("roing-brystsupport", "Roing med brystsupport", "trekk_hor", "manualer", ["manualer", "benk"], ["rygg", "biceps"], 1, True, True,
       ["Ligg på magen på skråbenk", "Avlaster korsryggen", "Trekk albuene bakover"]),
    _o("roing-strikk", "Roing med strikk", "trekk_hor", "strikk", ["strikk"], ["rygg", "biceps"], 1, True, True,
       ["Strikken festet i brysthøyde", "Trekk albuene bakover", "Klem skulderbladene"]),
    _o("omvendt-roing", "Omvendt roing", "trekk_hor", "kroppsvekt", ["trekkstang"], ["rygg", "biceps"], 1, True, True,
       ["Kroppen rett", "Trekk brystet mot stangen", "Lettere jo mer oppreist du står"]),

    # ---------------------------------------------------------------- nedtrekk
    _o("pull-ups", "Pull-ups", "trekk_vert", "kroppsvekt", ["trekkstang"], ["rygg", "biceps"], 3, False, True,
       ["Start fra strake armer", "Trekk brystet mot stangen", "Lettere med strikk under føttene"]),
    _o("pull-ups-strikk", "Pull-ups med strikkhjelp", "trekk_vert", "strikk", ["trekkstang", "strikk"], ["rygg", "biceps"], 2, True, True,
       ["Strikken under knær eller føtter", "Kontrollert ned", "Tynnere strikk når det blir lett"]),
    _o("nedtrekk", "Nedtrekk", "trekk_vert", "maskin", ["maskiner"], ["rygg", "biceps"], 1, True, True,
       ["Grep litt bredere enn skuldrene", "Trekk stangen mot øvre del av brystet", "Lene lett bakover"]),
    _o("nedtrekk-strikk", "Nedtrekk med strikk", "trekk_vert", "strikk", ["strikk"], ["rygg", "biceps"], 1, True, True,
       ["Strikken festet høyt", "Trekk albuene ned mot sidene", "Skuldrene ned fra ørene"]),
    _o("pullover-manual", "Pullover med manual", "trekk_vert", "manualer", ["manualer", "benk"], ["rygg", "bryst"], 2, True, False,
       ["Lett bøy i albuene", "Senk manualen bak hodet til strekk", "Trekk tilbake over brystet"]),

    # ---------------------------------------------------------------- kjerne
    _o("planke", "Planke", "kjerne", "kroppsvekt", [], ["kjerne"], 1, True, False,
       ["Rett linje fra hode til hæl", "Stram sete og mage", "Reps = sekunder"]),
    _o("sideplanke", "Sideplanke", "kjerne", "kroppsvekt", [], ["kjerne"], 1, True, False,
       ["Albuen under skulderen", "Hoftene opp", "Reps = sekunder per side"]),
    _o("dead-bug", "Dead bug", "kjerne", "kroppsvekt", [], ["kjerne"], 1, True, False,
       ["Korsryggen presset mot gulvet", "Motsatt arm og bein ut", "Pust ut når du strekker"]),
    _o("pallof-press", "Pallof press", "kjerne", "kabel", ["kabel"], ["kjerne"], 1, True, False,
       ["Stå sidelengs til kabelen", "Press rett frem og hold", "Ikke la kroppen vri seg"]),
    _o("pallof-strikk", "Pallof press med strikk", "kjerne", "strikk", ["strikk"], ["kjerne"], 1, True, False,
       ["Stå sidelengs til festet", "Press rett frem og hold", "Motstå rotasjonen"]),
    _o("bondegange", "Bondegange", "kjerne", "manualer", ["manualer"], ["kjerne", "rygg"], 1, True, True,
       ["Tunge manualer, oppreist kropp", "Korte, rolige steg", "Reps = sekunder eller meter"]),
    _o("hengende-kneløft", "Hengende kneløft", "kjerne", "kroppsvekt", ["trekkstang"], ["kjerne"], 2, False, False,
       ["Unngå å svinge", "Rull bekkenet opp", "Kontrollert ned"]),
    _o("bird-dog", "Bird dog", "kjerne", "kroppsvekt", [], ["kjerne", "korsrygg"], 1, True, False,
       ["På alle fire", "Motsatt arm og bein ut", "Hold ryggen helt i ro"]),

    # ---------------------------------------------------------------- skulderhelse
    _o("face-pull", "Face pull", "skulderhelse", "kabel", ["kabel"], ["skuldre", "rygg"], 1, True, False,
       ["Tau i øyehøyde", "Trekk mot ansiktet med albuene høyt", "Roter hendene bakover i slutten"]),
    _o("face-pull-strikk", "Face pull med strikk", "skulderhelse", "strikk", ["strikk"], ["skuldre", "rygg"], 1, True, False,
       ["Strikken i øyehøyde", "Albuene høyt og ut", "Klem skulderbladene"]),
    _o("utadrotasjon", "Utadrotasjon med strikk", "skulderhelse", "strikk", ["strikk"], ["skuldre"], 1, True, False,
       ["Albuen inntil siden", "Roter underarmen utover", "Lett motstand, rolig tempo"]),
    _o("omvendt-flyes", "Omvendte flyes med manualer", "skulderhelse", "manualer", ["manualer"], ["skuldre", "rygg"], 1, True, False,
       ["Lent fremover med rett rygg", "Løft armene ut til siden", "Lette vekter"]),

    # ---------------------------------------------------------------- isolasjon
    _o("sidehev", "Sidehev med manualer", "skuldre_iso", "manualer", ["manualer"], ["skuldre"], 1, True, False,
       ["Lett bøy i albuene", "Løft til skulderhøyde", "Ingen sving"]),
    _o("sidehev-kabel", "Sidehev i kabel", "skuldre_iso", "kabel", ["kabel"], ["skuldre"], 1, True, False,
       ["Stå sidelengs til kabelen", "Løft til skulderhøyde", "Rolig ned"]),
    _o("sidehev-strikk", "Sidehev med strikk", "skuldre_iso", "strikk", ["strikk"], ["skuldre"], 1, True, False,
       ["Stå på strikken", "Løft til skulderhøyde", "Kontrollert ned"]),
    _o("bicepscurl", "Bicepscurl med manualer", "biceps", "manualer", ["manualer"], ["biceps"], 1, True, False,
       ["Albuene inntil kroppen", "Hele bevegelsesbanen", "Ingen sving"]),
    _o("hammercurl", "Hammercurl", "biceps", "manualer", ["manualer"], ["biceps"], 1, True, False,
       ["Tommelen opp", "Albuene i ro", "Rolig ned"]),
    _o("bicepscurl-kabel", "Bicepscurl i kabel", "biceps", "kabel", ["kabel"], ["biceps"], 1, True, False,
       ["Albuene inntil siden", "Klem i toppen", "Kontrollert ned"]),
    _o("bicepscurl-strikk", "Bicepscurl med strikk", "biceps", "strikk", ["strikk"], ["biceps"], 1, True, False,
       ["Stå på strikken", "Albuene i ro", "Rolig ned"]),
    _o("triceps-pushdown", "Triceps pushdown", "triceps", "kabel", ["kabel"], ["triceps"], 1, True, False,
       ["Albuene inntil siden", "Strekk helt ut", "Kontrollert opp"]),
    _o("fransk-press", "Fransk press med manualer", "triceps", "manualer", ["manualer", "benk"], ["triceps"], 2, False, False,
       ["Overarmene i ro", "Senk manualene mot pannen", "Strekk helt ut"]),
    _o("triceps-over-hodet", "Tricepsstrekk over hodet", "triceps", "manualer", ["manualer"], ["triceps"], 1, True, False,
       ["Én manual i begge hender", "Albuene peker frem", "Strekk helt opp"]),
    _o("dips-benk", "Dips på benk", "triceps", "kroppsvekt", ["benk"], ["triceps", "bryst"], 1, False, True,
       ["Hendene på benkekanten", "Albuene peker bakover", "Ikke lenger ned enn skuldrene tåler"]),
    _o("triceps-strikk", "Tricepspress med strikk", "triceps", "strikk", ["strikk"], ["triceps"], 1, True, False,
       ["Strikken festet høyt", "Albuene inntil siden", "Strekk helt ut"]),
    _o("beincurl", "Beincurl i apparat", "bakside_iso", "maskin", ["maskiner"], ["lar_bakside"], 1, True, False,
       ["Kneet i linje med apparatets akse", "Rolig tilbake", "Hele bevegelsesbanen"]),
    _o("nordic-light", "Nordic hamstring (lett)", "bakside_iso", "kroppsvekt", [], ["lar_bakside"], 3, False, False,
       ["Noen holder anklene", "Senk deg så sakte du klarer", "Ta imot med hendene"]),
    _o("beincurl-strikk", "Beincurl med strikk", "bakside_iso", "strikk", ["strikk"], ["lar_bakside"], 1, True, False,
       ["Ligg på magen, strikk rundt ankelen", "Bøy kneet mot setet", "Rolig tilbake"]),
    _o("beinspark", "Beinspark i apparat", "forside_iso", "maskin", ["maskiner"], ["lar_forside"], 1, True, False,
       ["Rolig tempo", "Hold et øyeblikk i toppen", "Juster setet så kneet er i aksen"]),
    _o("spansk-knebøy", "Spansk knebøy med strikk", "forside_iso", "strikk", ["strikk"], ["lar_forside"], 2, True, False,
       ["Strikk festet bak knærne", "Oppreist overkropp", "Ofte brukt ved kneplager"]),
    _o("tåhev", "Tåhev", "legger", "kroppsvekt", [], ["legger"], 1, True, False,
       ["På kanten av et trinn", "Helt opp og helt ned", "Én manual gjør det tyngre"]),
    _o("tåhev-maskin", "Tåhev i apparat", "legger", "maskin", ["maskiner"], ["legger"], 1, True, False,
       ["Hele bevegelsesbanen", "Pause i bunnen", "Rolig tempo"]),
    _o("flyes-manualer", "Flyes med manualer", "bryst_iso", "manualer", ["manualer", "benk"], ["bryst"], 1, True, False,
       ["Lett bøy i albuene", "Senk til god strekk", "Klem sammen over brystet"]),
    _o("kabelkryss", "Kabelkryss", "bryst_iso", "kabel", ["kabel"], ["bryst"], 1, True, False,
       ["Ett steg frem", "Lett bøy i albuene", "Klem hendene sammen foran deg"]),
    # ---------------------------------------------------------------- kondisjon og intervaller (brukes i HIIT, AMRAP og EMOM)
    _o("tredemolle-lop", "Løp på tredemølle", "kondisjon", "kroppsvekt", ["tredemolle"], ["lar_forside", "legger", "sete"], 1, True, False,
       ["1 % stigning ligner løping ute", "Se fram, ikke ned på båndet", "Korte, lette steg midt på båndet"]),
    _o("tredemolle-motbakke", "Motbakke på tredemølle", "kondisjon", "kroppsvekt", ["tredemolle"], ["sete", "legger", "lar_bakside"], 1, True, False,
       ["8–12 % stigning, rask gange", "Ikke hold i rekkverket", "Hele foten i båndet, press fra setet"]),
    _o("sprellemann", "Sprellemann", "kondisjon", "kroppsvekt", [], ["legger", "skuldre"], 1, True, False,
       ["Land mykt på fremre del av foten", "Armene helt opp", "Finn en jevn rytme"]),
    _o("jogg-pa-stedet", "Jogg på stedet", "kondisjon", "kroppsvekt", [], ["legger", "lar_forside"], 1, True, False,
       ["Lette, raske steg", "Armene med", "Rolig variant: gå på stedet"]),
    _o("hoye-knelloft", "Høye kneløft", "kondisjon", "kroppsvekt", [], ["lar_forside", "kjerne"], 1, False, False,
       ["Knærne til hoftehøyde", "Oppreist overkropp", "Raskt og lett på føttene"]),
    _o("fjellklatrer", "Fjellklatrer", "kondisjon", "kroppsvekt", [], ["kjerne", "skuldre", "lar_forside"], 1, True, False,
       ["Hendene under skuldrene", "Hoftene i linje med kroppen", "Dra knærne raskt mot brystet"]),
    _o("burpees", "Burpees", "kondisjon", "kroppsvekt", [], ["bryst", "lar_forside", "kjerne"], 2, False, True,
       ["Hendene i gulvet, hopp bena bakover", "Bryst ned eller rett planke", "Hopp opp med armene over hodet"]),
    _o("hoppknebøy", "Hoppknebøy", "kondisjon", "kroppsvekt", [], ["lar_forside", "sete", "legger"], 2, False, True,
       ["Sitt ned som i vanlig knebøy", "Eksploder opp", "Land mykt med bøyde knær"]),
    _o("hoppende-utfall", "Hoppende utfall", "kondisjon", "kroppsvekt", [], ["lar_forside", "sete"], 3, False, True,
       ["Bytt bein i luften", "Land mykt og kontrollert", "Kneet over foten"]),
    _o("skøyterhopp", "Skøyterhopp", "kondisjon", "kroppsvekt", [], ["sete", "lar_forside", "legger"], 2, False, False,
       ["Hopp sidelengs fra fot til fot", "Land på ett bein og stabiliser", "Lavere tempo gir mer kontroll"]),
    _o("thruster-manualer", "Thrusters med manualer", "kondisjon", "manualer", ["manualer"], ["lar_forside", "sete", "skuldre"], 2, False, True,
       ["Knebøy med manualene på skuldrene", "Bruk farten fra beina", "Press manualene rett opp"]),
    _o("step-up-kroppsvekt", "Step-up uten vekt", "utfall", "kroppsvekt", ["benk"], ["lar_forside", "sete"], 1, True, True,
       ["Hele foten på benken", "Press opp med beinet på benken", "Kontrollert ned"]),
    _o("sumoknebøy", "Sumoknebøy", "kne", "kroppsvekt", [], ["lar_forside", "sete"], 1, True, True,
       ["Bred fotstilling, tærne utover", "Knærne ut over tærne", "Klem setet i toppen"]),
    _o("eselspark", "Eselspark", "sete", "kroppsvekt", [], ["sete"], 1, True, False,
       ["På alle fire, bøyd kne", "Press hælen mot taket", "Ikke svai i korsryggen"]),
    _o("brannhydrant", "Sidehev på alle fire", "sete", "kroppsvekt", [], ["sete"], 1, True, False,
       ["På alle fire", "Løft kneet ut til siden", "Hold hoftene rolige"]),
    _o("sykkelcrunch", "Sykkelcrunch", "kjerne", "kroppsvekt", [], ["kjerne"], 1, True, False,
       ["Korsryggen i gulvet", "Albue mot motsatt kne", "Rolig og kontrollert vridning"]),
    _o("russisk-vri", "Russisk vri", "kjerne", "kroppsvekt", [], ["kjerne"], 2, False, False,
       ["Len deg litt bakover med rett rygg", "Vri fra side til side", "Føttene i gulvet for enklere variant"]),
    _o("saksespark", "Saksespark", "kjerne", "kroppsvekt", [], ["kjerne"], 2, False, False,
       ["Korsryggen presset mot gulvet", "Små, raske spark", "Høyere bein gir enklere variant"]),
    _o("planke-skulderklapp", "Planke med skulderklapp", "kjerne", "kroppsvekt", [], ["kjerne", "skuldre"], 2, True, False,
       ["Bred fotstilling for stabilitet", "Klapp motsatt skulder", "Hoftene stille"]),
]

_INDEKS = {o["nokkel"]: o for o in BIBLIOTEK}
assert len(_INDEKS) == len(BIBLIOTEK), "duplikate øvelsesnøkler"


def tilgjengelig(ovelse: dict, utstyr: set[str] | None) -> bool:
    """Kan øvelsen gjøres med dette utstyret? None = alt utstyr."""
    return utstyr is None or set(ovelse["utstyr"]) <= utstyr


def steg_for(ovelse: dict, vekt: float | None = None) -> float:
    typ = ovelse.get("type")
    s = STEG.get(typ, 2.5)
    if typ == "manualer" and vekt is not None and vekt < 10:
        return 1.0
    if typ == "maskin" and vekt is not None and vekt < 30:
        return 2.5
    return s


def vektbasert(ovelse: dict) -> bool:
    return ovelse.get("type") not in ("kroppsvekt", "strikk")


def sekunder(ovelse: dict) -> bool:
    """Øvelser der «reps» betyr sekunder (planker, bondegange)."""
    return ovelse.get("nokkel") in ("planke", "sideplanke", "bondegange")
