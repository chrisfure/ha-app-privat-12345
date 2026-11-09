"""Instruksjoner for øvelsene i biblioteket: utgangsstilling, gjennomføring steg for steg og vanlige feil.

Teksten er skrevet kort og praktisk, i tråd med vanlig teknikkopplæring i styrketrening.
"""
from __future__ import annotations

STANDARD_PUST = "Pust ut i den tunge delen av bevegelsen, inn i den lette. Ikke hold pusten lenge."
KONDIS = "Pust jevnt og rytmisk. Ikke hold pusten – senk tempoet hvis du blir for andpusten til å snakke i korte setninger."
STAG_PUST = "Pust inn og stram magen før hver rep, hold spenningen gjennom den tunge delen og pust ut i toppen."


def _i(start: str, steg: list[str], feil: list[str], pust: str | None = None) -> dict:
    return {"start": start, "steg": steg, "feil": feil, "pust": pust or STANDARD_PUST}


INSTRUKSJONER: dict[str, dict] = {
    # ------------------------------------------------------------------ knebøy
    "knebøy-stang": _i(
        "Stangen i stativet i høyde med øvre del av brystet. Gå under, legg stangen på øvre del av ryggen (ikke på nakken), grip litt bredere enn skuldrene og løft den ut. Ta to–tre steg bakover og stå med føttene i hoftebredde eller litt bredere, tærne lett utover.",
        ["Pust inn, stram magen og klem skulderbladene sammen.",
         "Bøy i hofter og knær samtidig og sitt rett ned mellom hælene.",
         "La knærne følge retningen til tærne – gjerne litt utover.",
         "Gå så dypt du klarer med nøytral rygg og hælene i gulvet (minst til lårene er vannrette om mobiliteten tillater det).",
         "Press opp gjennom hele foten til du står helt oppreist."],
        ["Knærne faller innover", "Hælene letter fra gulvet", "Korsryggen runder i bunnen", "Overkroppen faller langt fremover så det blir en «god morgen»"],
        STAG_PUST),
    "frontknebøy": _i(
        "Stangen hviler på fremsiden av skuldrene, tett inntil halsen. Fingrene under stangen og albuene peker rett frem og høyt. Føttene i hoftebredde, tærne lett utover.",
        ["Pust inn og stram magen.",
         "Sitt rett ned med oppreist overkropp – albuene holdes høyt hele veien.",
         "Gå så dypt du klarer uten at albuene synker eller ryggen runder.",
         "Press opp gjennom hele foten og led med albuene."],
        ["Albuene synker så stangen ruller frem", "Overkroppen faller fremover", "Vekten på tærne"],
        STAG_PUST),
    "goblet-knebøy": _i(
        "Hold én manual loddrett inntil brystet med begge hender under den øverste skiven. Føttene litt bredere enn hoftene, tærne lett utover.",
        ["Stram magen og hold brystet oppe.",
         "Sitt rett ned mellom hælene – albuene går ned på innsiden av knærne.",
         "Gå så dypt du klarer med rett rygg.",
         "Press opp gjennom hele foten til du står oppreist."],
        ["Manualen glir bort fra kroppen", "Knærne faller innover", "Hælene letter"]),
    "goblet-knebøy-kb": _i(
        "Hold kettlebellen i hornene (håndtaket) inntil brystet. Føttene litt bredere enn hoftene, tærne lett utover.",
        ["Stram magen og hold brystet oppe.",
         "Sitt rett ned mellom hælene med albuene på innsiden av knærne.",
         "Gå så dypt du klarer med rett rygg.",
         "Press opp gjennom hele foten."],
        ["Kettlebellen henger langt fra kroppen", "Knærne faller innover", "Runding i ryggen i bunnen"]),
    "beinpress": _i(
        "Sitt med ryggen og setet godt inntil setet i apparatet. Føttene midt på platen i hoftebredde. Løs ut sikringen.",
        ["Senk platen kontrollert ved å bøye knærne mot brystet.",
         "Stopp før setet og korsryggen begynner å løfte seg fra setet.",
         "Press platen opp gjennom hele foten.",
         "Stopp rett før knærne er helt strake."],
        ["Låser knærne helt i toppen", "Setet ruller opp fra setet i bunnen", "Knærne faller innover", "For kort bevegelse"]),
    "knebøy-kroppsvekt": _i(
        "Stå med føttene i hoftebredde eller litt bredere, tærne lett utover. Armene rett frem eller hendene samlet foran brystet.",
        ["Skyv hoftene bakover og bøy knærne som om du skal sette deg på en stol.",
         "Hold brystet oppe og vekten på hele foten.",
         "Gå så dypt du klarer med rett rygg.",
         "Reis deg ved å presse gulvet vekk."],
        ["Hælene letter", "Knærne faller innover", "Ryggen runder"]),
    "boks-knebøy": _i(
        "Stå med baksiden av leggene et lite stykke foran en benk eller stol. Føttene i hoftebredde.",
        ["Skyv hoftene bakover og sett deg kontrollert ned til du så vidt sitter.",
         "Hold spenningen – ikke slapp helt av på benken.",
         "Len deg litt frem og reis deg opp gjennom hele foten.",
         "Velg høyere benk om det er tungt eller ubehagelig i knærne, lavere når det blir lett."],
        ["Dumper ned på benken", "Svinger overkroppen for å komme opp", "Knærne faller innover"]),

    # ------------------------------------------------------------------ hoftehengsel
    "markløft": _i(
        "Stå med midtfoten under stangen, føttene i hoftebredde. Bøy deg ned og grip stangen rett utenfor leggene. Senk hoftene til leggene treffer stangen, brystet opp og ryggen rett.",
        ["Pust inn, stram magen og «stram» armene som om du skal bøye stangen.",
         "Skyv gulvet vekk med beina – stangen går rett opp langs leggene.",
         "Når stangen passerer knærne, skyv hoftene frem.",
         "Stå helt oppreist med sete og mage stramme.",
         "Senk ved å skyve hoftene bakover først, deretter bøy knærne når stangen passerer dem."],
        ["Runding i korsryggen", "Stangen glir bort fra kroppen", "Hoftene skyter opp først så det blir et ryggløft", "Lener seg bakover i toppen"],
        STAG_PUST),
    "rumensk-markløft": _i(
        "Stå oppreist med stangen i hendene foran lårene, grep i skulderbredde. Føttene i hoftebredde, lett bøy i knærne.",
        ["Skyv hoftene rett bakover – stangen glir ned langs lårene.",
         "Behold samme lille knebøy hele veien.",
         "Gå ned til du kjenner god strekk bak på lårene, normalt rundt knærne eller litt under.",
         "Skyv hoftene frem og klem setet til du står oppreist."],
        ["Runder ryggen for å komme lenger ned", "Bøyer knærne mer og mer så det blir knebøy", "Stangen glir frem fra beina"]),
    "rumensk-markløft-man": _i(
        "Stå oppreist med en manual i hver hånd foran lårene. Føttene i hoftebredde, lett bøy i knærne.",
        ["Skyv hoftene bakover – manualene glir ned langs lårene.",
         "Hold ryggen rett og knærne i samme lille bøy.",
         "Stopp når du kjenner god strekk bak på lårene.",
         "Skyv hoftene frem og klem setet i toppen."],
        ["Runding i ryggen", "Manualene henger langt fra beina", "For mye knebøy"]),
    "kettlebell-sving": _i(
        "Kettlebellen på gulvet et lite stykke foran deg. Føttene litt bredere enn hoftene. Skyv hoftene bakover, grip håndtaket med begge hender og vipp kettlebellen litt mot deg.",
        ["Sving kettlebellen bakover mellom beina – som en ballkaster i amerikansk fotball.",
         "Skyv hoftene eksplosivt frem så kettlebellen svinger opp til brysthøyde.",
         "Stå helt oppreist i toppen med stramt sete og stram mage – armene er bare «tau».",
         "La kettlebellen falle tilbake og ta imot ved å skyve hoftene bakover igjen."],
        ["Løfter med armene eller skuldrene", "Gjør en knebøy i stedet for hoftehengsel", "Lener seg bakover i toppen", "Runder ryggen i bunnen"],
        "Pust ut kraftig når hoftene skytes frem, pust inn når kettlebellen faller tilbake."),
    "kettlebell-markløft": _i(
        "Kettlebellen på gulvet mellom føttene. Føttene i hoftebredde eller litt bredere.",
        ["Skyv hoftene bakover og bøy knærne til du når håndtaket med rett rygg.",
         "Grip med begge hender, stram armene og magen.",
         "Reis deg ved å presse gulvet vekk og skyve hoftene frem.",
         "Senk på samme måte – hoftene bakover først."],
        ["Runding i ryggen", "Kettlebellen foran føttene i stedet for mellom", "Rykker i stedet for å presse"],
        STAG_PUST),
    "ryggstrekk": _i(
        "Still inn benken så hofteleddet er like over puten. Lås føttene under rullene. Kryss armene over brystet.",
        ["Bøy deg frem i hofta med rett rygg.",
         "Gå ned til du kjenner strekk bak på lårene.",
         "Løft deg opp med sete og bakside lår til kroppen er i rett linje.",
         "Stopp der – ikke bøy bakover."],
        ["Overstrekker korsryggen i toppen", "Runder ryggen nederst", "Bruker fart"]),
    "good-morning-strikk": _i(
        "Stå på strikken med føttene i hoftebredde og legg den andre enden bak nakken eller over skuldrene. Lett bøy i knærne.",
        ["Skyv hoftene bakover og bøy deg frem med rett rygg.",
         "Gå ned til overkroppen er nesten vannrett eller du kjenner god strekk bak på lårene.",
         "Skyv hoftene frem og reis deg opp."],
        ["Runder ryggen", "Bøyer knærne for mye", "Strikken glir opp på nakken"]),

    # ------------------------------------------------------------------ ettbeins
    "bulgarsk-utfall": _i(
        "Stå med ryggen mot en benk og legg vristen på det bakre beinet på benken. Fremre fot et godt steg frem. En manual i hver hånd.",
        ["Senk deg rett ned til det bakre kneet nesten treffer gulvet.",
         "Fremre kne følger tærne, og hele foten er i gulvet.",
         "Press opp gjennom fremre hæl.",
         "Ta alle repetisjonene på ett bein, så bytt."],
        ["For kort steg så kneet presses langt frem", "Fremre kne faller innover", "Skyver fra med det bakre beinet"]),
    "utfall-manualer": _i(
        "Stå oppreist med en manual i hver hånd langs sidene, føttene i hoftebredde.",
        ["Ta et langt steg frem.",
         "Senk deg til begge knærne er omtrent 90°, bakre kne like over gulvet.",
         "Hold overkroppen oppreist og fremre kne i linje med tærne.",
         "Skyv deg tilbake til start med fremre fot. Veksle bein eller ta alle på én side."],
        ["For kort steg", "Fremre kne faller innover", "Faller fremover med overkroppen"]),
    "step-up": _i(
        "Stå foran en stødig benk eller kasse i knehøyde eller lavere. En manual i hver hånd.",
        ["Sett hele den ene foten opp på benken.",
         "Press deg opp med det fremre beinet til du står oppreist på benken.",
         "Ikke sprett fra med det nederste beinet.",
         "Gå kontrollert ned igjen med samme bein først. Ta alle reps på én side, så bytt."],
        ["Sprett fra med bakre fot", "Bare tåen på benken", "Kneet faller innover på vei opp"]),
    "utfall-kroppsvekt": _i(
        "Stå oppreist med hendene på hoftene, føttene i hoftebredde.",
        ["Ta et langt steg frem.",
         "Senk deg kontrollert til bakre kne nesten treffer gulvet.",
         "Hold fremre kne i linje med tærne.",
         "Skyv deg tilbake til start. Hold i en vegg eller stol om balansen er vanskelig."],
        ["For kort steg", "Kneet faller innover", "Faller fremover"]),
    "bakoverutfall": _i(
        "Stå oppreist med en manual i hver hånd, føttene i hoftebredde.",
        ["Ta et langt steg bakover med det ene beinet.",
         "Senk deg rolig til bakre kne nesten treffer gulvet.",
         "Vekten skal ligge på fremre fot.",
         "Press opp gjennom fremre hæl og sett bakre fot ved siden av igjen."],
        ["Vekten på bakre bein", "Fremre kne faller innover", "For kort steg bakover"]),

    # ------------------------------------------------------------------ sete
    "hoftehev-stang": _i(
        "Sitt på gulvet med øvre del av ryggen (nedre kant av skulderbladene) mot langsiden av en benk. Rull stangen over beina til den ligger i hoftebøyen – bruk gjerne en pute. Føttene i hoftebredde, så nær at leggene blir loddrette i toppen.",
        ["Haka ned mot brystet og stram magen.",
         "Press gjennom hælene og løft hoftene til kroppen er rett fra knær til skuldre.",
         "Klem setet hardt et øyeblikk i toppen.",
         "Senk kontrollert til setet nesten treffer gulvet."],
        ["Svai i korsryggen i stedet for å strekke i hofta", "Føttene for langt frem eller bak", "Skyver med tærne"]),
    "setehev": _i(
        "Ligg på ryggen med knærne bøyd og føttene i gulvet i hoftebredde, nær setet. Armene langs siden.",
        ["Stram magen.",
         "Press gjennom hælene og løft hoftene til kroppen er rett fra knær til skuldre.",
         "Hold og klem setet ett sekund.",
         "Senk rolig ned."],
        ["Svaier i korsryggen", "Skyver med tærne", "Løfter for fort"]),
    "setehev-ettbeins": _i(
        "Ligg på ryggen med ett kne bøyd og foten i gulvet, det andre beinet strakt eller med kneet trukket mot brystet.",
        ["Press gjennom hælen på det bøyde beinet og løft hoftene.",
         "Hold hoftene vannrette – ikke la den ene siden synke.",
         "Klem setet i toppen og senk rolig. Ta alle reps på én side, så bytt."],
        ["Hofta vipper til siden", "Svai i korsryggen", "Bruker fart"]),
    "hoftehev-manual": _i(
        "Sitt med skulderbladene mot langsiden av en benk og legg en manual på tvers i hoftebøyen. Føttene i hoftebredde.",
        ["Hold manualen med begge hender og stram magen.",
         "Press gjennom hælene og løft hoftene til kroppen er rett fra knær til skuldre.",
         "Klem setet i toppen.",
         "Senk kontrollert."],
        ["Svai i korsryggen", "Manualen ruller", "Føttene for langt frem"]),
    "sidegange-strikk": _i(
        "Legg en minibånd-strikk rundt knærne eller anklene. Stå med føttene i hoftebredde og lett bøy i knær og hofter.",
        ["Ta et kontrollert steg til siden med den ene foten.",
         "Følg etter med den andre – men aldri helt inntil, så strikken holdes stram.",
         "Hold tærne pekende frem og overkroppen rolig.",
         "Gå et visst antall steg én vei, så tilbake. Reps = steg per retning."],
        ["Strikken blir slakk", "Vugger med overkroppen", "Knærne faller innover"]),

    # ------------------------------------------------------------------ press fremover
    "benkpress": _i(
        "Ligg på benken med øynene rett under stangen. Føttene godt plantet i gulvet. Grip stangen litt bredere enn skuldrene. Klem skulderbladene sammen og ned, og løft stangen ut til den er over skuldrene.",
        ["Pust inn og senk stangen kontrollert mot nedre del av brystet.",
         "Albuene ca. 45° ut fra kroppen.",
         "Berør brystet lett uten å sprette.",
         "Press stangen opp og litt tilbake mot skuldrene til armene er strake."],
        ["Albuene rett ut til siden (90°)", "Setet løfter seg fra benken", "Spretter stangen på brystet", "Skulderbladene slipper taket"],
        "Pust inn på vei ned, hold spenningen i bunnen og pust ut når du presser opp. Bruk en som passer på (spotter) ved tunge sett."),
    "benkpress-manualer": _i(
        "Sitt på enden av benken med manualene på lårene. Len deg bakover og løft manualene opp over brystet med strake armer. Skulderbladene sammen og ned, føttene i gulvet.",
        ["Senk manualene kontrollert ut til siden av brystet.",
         "Albuene ca. 45° ut fra kroppen.",
         "Stopp når du kjenner god strekk i brystet.",
         "Press opp og litt inn til armene er strake over brystet."],
        ["Albuene rett ut til siden", "Manualene slår sammen i toppen", "Mister kontrollen på vei ned"]),
    "skrå-benk-manualer": _i(
        "Still ryggen på benken til 30–45°. Sitt med manualene på lårene, len deg tilbake og løft dem opp over skuldrene.",
        ["Klem skulderbladene sammen og ned.",
         "Senk manualene til siden av øvre del av brystet.",
         "Press rett opp over skuldrene."],
        ["For bratt benk så det blir skulderpress", "Svai i korsryggen", "Albuene for langt ut"]),
    "brystpress-maskin": _i(
        "Juster setet så håndtakene er i høyde med midten av brystet. Ryggen inntil ryggstøtten, føttene i gulvet.",
        ["Grip håndtakene og klem skulderbladene lett sammen.",
         "Press frem til armene er nesten strake.",
         "Før vekten rolig tilbake til du kjenner strekk i brystet."],
        ["Skuldrene trekkes opp mot ørene", "Låser albuene hardt", "Vekten slår ned mellom reps"]),
    "armhevinger": _i(
        "Hendene i gulvet litt bredere enn skuldrene, rett under skuldrene. Strake bein, kroppen i rett linje fra hode til hæl.",
        ["Stram mage og sete.",
         "Senk brystet mot gulvet med albuene ca. 45° ut fra kroppen.",
         "Gå så langt ned du klarer med rett kropp.",
         "Press deg opp igjen.",
         "For lett variant: hendene på en benk eller knærne i gulvet. Tyngre: føttene høyere."],
        ["Hoftene henger ned", "Setet stikker opp", "Albuene rett ut til siden", "Halve repetisjoner"]),
    "brystpress-strikk": _i(
        "Fest strikken bak deg i brysthøyde (f.eks. rundt en dørkarm eller stolpe) og hold i en ende i hver hånd. Ta ett steg frem til strikken er stram.",
        ["Stå stødig med den ene foten litt foran.",
         "Press hendene frem og litt inn til armene er strake.",
         "Før kontrollert tilbake."],
        ["Lener seg frem i stedet for å presse", "Skuldrene opp mot ørene", "Slipper strikken fort tilbake"]),

    # ------------------------------------------------------------------ press over hodet
    "stående-press": _i(
        "Stangen hviler foran på skuldrene, grep litt bredere enn skuldrene. Føttene i hoftebredde.",
        ["Stram sete og mage – kroppen skal være stiv som en planke.",
         "Press stangen rett opp, og trekk hodet litt bakover så stangen kommer forbi ansiktet.",
         "Når stangen passerer hodet, skyv hodet frem under den.",
         "Lås armene over hodet, stangen over midtfoten.",
         "Senk kontrollert tilbake til skuldrene."],
        ["Svaier i korsryggen", "Stangen går i en bue rundt ansiktet", "Bruker beina (blir push press)"],
        STAG_PUST),
    "skulderpress-manualer": _i(
        "Sitt på en benk med ryggstøtte eller stå med føttene i hoftebredde. Manualene i skulderhøyde, håndflatene frem eller mot hverandre.",
        ["Stram magen.",
         "Press manualene rett opp til armene er strake.",
         "Albuene litt foran kroppen, ikke rett ut til siden.",
         "Senk kontrollert til skulderhøyde."],
        ["Svaier i korsryggen", "Slår manualene sammen i toppen", "For kort bevegelse"]),
    "landmine-press": _i(
        "Stå med én manual i den ene hånden ved skulderen, føttene i hoftebredde og den motsatte foten litt foran.",
        ["Stram mage og sete.",
         "Press manualen skrått frem og opp – ikke rett opp.",
         "Strekk armen helt uten å vri overkroppen.",
         "Senk kontrollert. Ta alle reps på én side, så bytt."],
        ["Vrir overkroppen", "Svaier i ryggen", "Trekker skulderen opp mot øret"]),
    "skulderpress-maskin": _i(
        "Juster setet så håndtakene er i skulderhøyde. Ryggen inntil ryggstøtten.",
        ["Grip håndtakene og stram magen.",
         "Press opp til armene er nesten strake.",
         "Senk rolig tilbake til skulderhøyde."],
        ["Ryggen slipper ryggstøtten", "Låser albuene hardt", "Vekten slår ned"]),
    "pike-armhevinger": _i(
        "Start i armhevingsposisjon og gå med føttene mot hendene så hoftene kommer høyt – kroppen som en omvendt V.",
        ["Bøy armene og senk hodet mot gulvet mellom hendene.",
         "Albuene peker bakover, ikke rett ut.",
         "Press deg opp igjen.",
         "Tyngre: føttene på en benk."],
        ["Hoftene synker så det blir vanlig armheving", "Albuene rett ut", "For kort bevegelse"]),
    "skulderpress-strikk": _i(
        "Stå på midten av strikken med føttene i hoftebredde. Hold endene ved skuldrene.",
        ["Stram magen.",
         "Press rett opp til armene er strake.",
         "Senk kontrollert til skulderhøyde."],
        ["Svaier i ryggen", "Strikken drar hendene bakover", "Slipper fort ned"]),

    # ------------------------------------------------------------------ roing
    "roing-stang": _i(
        "Grip stangen i skulderbredde. Stå med lett bøyde knær og skyv hoftene bakover til overkroppen er ca. 45° frem. Rett rygg, stangen henger under skuldrene.",
        ["Stram magen.",
         "Trekk stangen mot navlen ved å føre albuene bakover.",
         "Klem skulderbladene sammen i toppen.",
         "Senk kontrollert til armene er strake."],
        ["Reiser overkroppen for å få opp vekten", "Runding i ryggen", "Trekker med armene i stedet for ryggen"]),
    "ettarms-roing": _i(
        "Sett samme kne og hånd på en benk, den andre foten i gulvet. Ryggen rett og vannrett. Manualen i den frie hånden.",
        ["La manualen henge rett ned med strak arm.",
         "Trekk albuen bakover og opp mot hofta.",
         "Klem skulderbladet inn mot ryggraden i toppen.",
         "Senk kontrollert. Ta alle reps på én side, så bytt."],
        ["Vrir overkroppen for å få opp vekten", "Trekker mot skulderen i stedet for hofta", "Rykker"]),
    "sittende-roing": _i(
        "Sitt med føttene mot fotstøttene, lett bøy i knærne. Grip håndtaket og sitt oppreist med strake armer.",
        ["Trekk håndtaket mot magen ved å føre albuene bakover.",
         "Skulderbladene sammen og ned.",
         "Hold overkroppen i ro.",
         "Strekk armene kontrollert ut igjen og la skulderbladene gli frem."],
        ["Lener seg langt bakover og frem", "Skuldrene opp mot ørene", "Runding i ryggen"]),
    "roing-brystsupport": _i(
        "Still en benk på ca. 30–45° og ligg på magen med brystet mot ryggstøtten. En manual i hver hånd, armene rett ned.",
        ["Trekk albuene bakover og opp.",
         "Klem skulderbladene sammen i toppen.",
         "Senk kontrollert til armene er strake."],
        ["Løfter brystet fra benken", "Trekker skuldrene opp", "Rykker"]),
    "roing-strikk": _i(
        "Fest strikken foran deg i brysthøyde. Hold en ende i hver hånd og ta et steg bakover til den er stram.",
        ["Stå oppreist med lett bøyde knær.",
         "Trekk hendene mot magen ved å føre albuene bakover.",
         "Klem skulderbladene sammen.",
         "Før armene kontrollert frem igjen."],
        ["Lener seg bakover", "Skuldrene opp mot ørene", "Slipper strikken fort"]),
    "omvendt-roing": _i(
        "Still en stang i hoftehøyde (f.eks. i stativet). Legg deg under, grip stangen litt bredere enn skuldrene, strake bein og hælene i gulvet.",
        ["Stram mage og sete så kroppen er rett.",
         "Trekk brystet opp mot stangen.",
         "Klem skulderbladene sammen i toppen.",
         "Senk kontrollert.",
         "Lettere: bøy knærne eller still stangen høyere."],
        ["Hoftene henger", "Halv bevegelse", "Strekker nakken frem mot stangen"]),

    # ------------------------------------------------------------------ nedtrekk
    "pull-ups": _i(
        "Grip stangen med håndflatene vendt fra deg, litt bredere enn skuldrene. Heng med strake armer.",
        ["Trekk skuldrene ned fra ørene og stram magen.",
         "Trekk deg opp til haka er over stangen – tenk «albuene ned i lommene».",
         "Senk deg kontrollert helt ned."],
        ["Svinger og sparker", "Halve repetisjoner", "Skuldrene opp mot ørene i bunnen"]),
    "pull-ups-strikk": _i(
        "Fest en strikk i stangen og sett ett kne eller begge føttene i løkka. Grip stangen litt bredere enn skuldrene.",
        ["Start fra strake armer.",
         "Trekk deg opp til haka er over stangen.",
         "Senk deg kontrollert helt ned.",
         "Bytt til tynnere strikk når du klarer toppen av rep-intervallet."],
        ["Spretter i strikken", "Halve repetisjoner", "Svinger"]),
    "nedtrekk": _i(
        "Sitt med lårene under putene. Grip stangen litt bredere enn skuldrene.",
        ["Len deg lett bakover og stram magen.",
         "Trekk stangen ned mot øvre del av brystet.",
         "Før albuene ned og inn mot sidene.",
         "Slipp stangen kontrollert opp til armene er strake."],
        ["Trekker stangen bak nakken", "Lener seg langt bakover", "Rykker med kroppen"]),
    "nedtrekk-strikk": _i(
        "Fest strikken høyt (f.eks. i toppen av en dør eller trekkstang). Knel eller sitt under med en ende i hver hånd og strake armer.",
        ["Trekk skuldrene ned.",
         "Trekk albuene ned mot sidene.",
         "Før armene kontrollert opp igjen."],
        ["Skuldrene opp mot ørene", "Lener seg for mye bakover", "Slipper strikken fort"]),
    "pullover-manual": _i(
        "Ligg på ryggen på tvers eller på langs av en benk. Hold én manual med begge hender over brystet, lett bøy i albuene.",
        ["Stram magen så korsryggen ikke svaier.",
         "Senk manualen i en bue bak hodet til du kjenner god strekk.",
         "Trekk manualen tilbake over brystet i samme bue."],
        ["Bøyer og strekker albuene", "Svaier i korsryggen", "Går lenger enn skuldrene tåler"]),

    # ------------------------------------------------------------------ kjerne
    "planke": _i(
        "Albuene i gulvet rett under skuldrene, underarmene parallelle. Strake bein, tærne i gulvet.",
        ["Løft kroppen så den er rett fra hode til hæl.",
         "Stram mage og sete, og press albuene lett mot tærne.",
         "Hold posisjonen i det antallet sekunder som står i planen.",
         "Lettere: knærne i gulvet."],
        ["Hoftene henger ned", "Setet stikker opp", "Holder pusten"],
        "Pust rolig og jevnt gjennom hele holdet."),
    "sideplanke": _i(
        "Ligg på siden med albuen rett under skulderen og beina strake oppå hverandre (eller knærne bøyd for lettere variant).",
        ["Løft hoftene så kroppen er rett fra hode til føtter.",
         "Hold hofta fremover – ikke vri deg.",
         "Hold tiden som står i planen, så bytt side. Reps = sekunder per side."],
        ["Hofta synker", "Ruller fremover eller bakover", "Skulderen trekkes opp mot øret"],
        "Pust rolig og jevnt gjennom hele holdet."),
    "dead-bug": _i(
        "Ligg på ryggen med armene rett opp mot taket og hofter og knær bøyd 90°, leggene vannrette.",
        ["Press korsryggen mot gulvet og hold den der hele tiden.",
         "Strekk motsatt arm og bein sakte ut mot gulvet.",
         "Gå bare så langt du klarer uten at korsryggen løfter seg.",
         "Tilbake til start og bytt side. Reps = totalt antall eller per side som avtalt."],
        ["Korsryggen løfter seg", "Går for fort", "Holder pusten"],
        "Pust ut når du strekker ut, inn når du kommer tilbake."),
    "pallof-press": _i(
        "Still kabelen i brysthøyde. Stå sidelengs med håndtaket mot brystet i begge hender og ta et steg ut så kabelen er stram. Føttene i hoftebredde.",
        ["Stram mage og sete.",
         "Press håndtaket rett frem til armene er strake.",
         "Hold 1–2 sekunder uten å la kroppen vri seg mot kabelen.",
         "Før hendene tilbake til brystet. Ta alle reps, så bytt side."],
        ["Kroppen roterer mot kabelen", "Står for nær så det blir for lett", "Svaier i ryggen"]),
    "pallof-strikk": _i(
        "Fest strikken i brysthøyde. Stå sidelengs med strikken i begge hender inntil brystet og ta et steg ut til den er stram.",
        ["Stram mage og sete.",
         "Press hendene rett frem og hold 1–2 sekunder.",
         "Motstå at strikken drar deg rundt.",
         "Tilbake til brystet. Bytt side etter settet."],
        ["Roterer med strikken", "For slakk strikk", "Svaier i ryggen"]),
    "bondegange": _i(
        "Løft en tung manual i hver hånd med god teknikk (som et markløft). Stå oppreist med skuldrene ned og bak.",
        ["Stram magen.",
         "Gå med korte, rolige steg.",
         "Hold overkroppen oppreist uten å lene til noen side.",
         "Gå i antallet sekunder (eller meter) som står i planen, og sett vektene ned kontrollert."],
        ["Lener seg til siden eller bakover", "Skuldrene henger frem", "Løfter vektene med rund rygg"],
        "Pust rolig og jevnt mens du går."),
    "hengende-kneløft": _i(
        "Heng i trekkstangen med strake armer og skuldrene trukket litt ned.",
        ["Stram magen.",
         "Løft knærne mot brystet og rull bekkenet opp.",
         "Senk beina kontrollert uten å svinge."],
        ["Svinger frem og tilbake", "Løfter bare beina uten å rulle bekkenet", "Slipper beina fort ned"]),
    "bird-dog": _i(
        "Stå på alle fire med hendene under skuldrene og knærne under hoftene. Ryggen rett.",
        ["Stram magen.",
         "Strekk motsatt arm og bein ut til de er i linje med kroppen.",
         "Hold ryggen helt i ro – tenk at du har et vannglass på korsryggen.",
         "Hold 1–2 sekunder, tilbake og bytt side."],
        ["Svaier i ryggen", "Hofta vipper opp", "Går for fort"]),

    # ------------------------------------------------------------------ skulderhelse
    "face-pull": _i(
        "Still kabelen i øyehøyde med tau. Grip endene med tommelen mot deg og ta et steg bakover til armene er strake.",
        ["Stå oppreist med stram mage.",
         "Trekk tauet mot ansiktet med albuene høyt og ut til siden.",
         "Mot slutten: roter hendene bakover så de ender ved siden av ørene.",
         "Før kontrollert tilbake."],
        ["Albuene synker", "Lener seg bakover", "For tung vekt så det blir roing"]),
    "face-pull-strikk": _i(
        "Fest strikken i øyehøyde. Hold en ende i hver hånd og ta et steg bakover til den er stram.",
        ["Trekk hendene mot ansiktet med albuene høyt og ut.",
         "Klem skulderbladene sammen og roter hendene bakover.",
         "Før kontrollert tilbake."],
        ["Albuene synker", "Lener seg bakover", "Slipper strikken fort"]),
    "utadrotasjon": _i(
        "Fest strikken i albuehøyde. Stå sidelengs med albuen inntil siden og bøyd 90°, underarmen foran magen. Gjerne et lite håndkle mellom albue og kropp.",
        ["Hold albuen inntil kroppen.",
         "Roter underarmen utover så langt du klarer uten å flytte albuen.",
         "Før rolig tilbake.",
         "Bruk lett motstand – dette er en presisjonsøvelse. Bytt side etter settet."],
        ["Albuen glir ut fra kroppen", "For tung strikk", "Vrir overkroppen"]),
    "omvendt-flyes": _i(
        "Stå med lett bøyde knær og bøy deg frem med rett rygg til overkroppen er nesten vannrett. Lette manualer, armene henger rett ned med lett bøy i albuene.",
        ["Løft armene ut til siden i en bue.",
         "Klem skulderbladene sammen i toppen.",
         "Senk kontrollert."],
        ["For tung vekt", "Reiser overkroppen", "Trekker skuldrene opp mot ørene"]),

    # ------------------------------------------------------------------ skuldre isolert
    "sidehev": _i(
        "Stå oppreist med en manual i hver hånd langs sidene, lett bøy i albuene.",
        ["Løft armene ut til siden til skulderhøyde.",
         "Led med albuene, ikke hendene.",
         "Senk kontrollert."],
        ["Svinger med kroppen", "Løfter over skulderhøyde med trekking i nakken", "For tung vekt"]),
    "sidehev-kabel": _i(
        "Still kabelen nederst. Stå sidelengs og grip håndtaket med hånden lengst unna.",
        ["Løft armen ut til siden til skulderhøyde med lett bøy i albuen.",
         "Senk kontrollert.",
         "Ta alle reps, så bytt side."],
        ["Lener seg fra kabelen", "Svinger", "Skulderen trekkes opp"]),
    "sidehev-strikk": _i(
        "Stå på strikken med føttene i hoftebredde og hold en ende i hver hånd langs sidene.",
        ["Løft armene ut til siden til skulderhøyde.",
         "Senk kontrollert."],
        ["Svinger", "Skuldrene opp mot ørene", "Slipper fort ned"]),

    # ------------------------------------------------------------------ armer
    "bicepscurl": _i(
        "Stå oppreist med en manual i hver hånd, armene langs sidene og håndflatene frem.",
        ["Hold albuene inntil kroppen.",
         "Bøy armene og løft manualene mot skuldrene.",
         "Senk kontrollert helt ned."],
        ["Svinger med kroppen", "Albuene glir frem", "Halv bevegelse"]),
    "hammercurl": _i(
        "Stå oppreist med en manual i hver hånd, håndflatene mot kroppen (tommelen opp).",
        ["Hold albuene inntil kroppen.",
         "Bøy armene og løft manualene mot skuldrene med tommelen opp.",
         "Senk kontrollert."],
        ["Svinger", "Albuene glir frem", "Slipper fort ned"]),
    "bicepscurl-kabel": _i(
        "Still kabelen nederst med rett stang eller tau. Stå oppreist og grip med håndflatene opp.",
        ["Albuene inntil siden.",
         "Bøy armene og trekk mot skuldrene.",
         "Senk kontrollert til armene er strake."],
        ["Lener seg bakover", "Albuene glir frem", "Halv bevegelse"]),
    "bicepscurl-strikk": _i(
        "Stå på midten av strikken og hold endene med håndflatene frem.",
        ["Albuene inntil siden.",
         "Bøy armene mot skuldrene.",
         "Senk kontrollert."],
        ["Svinger", "Albuene glir frem", "Slipper fort ned"]),
    "triceps-pushdown": _i(
        "Still kabelen øverst med tau eller stang. Stå oppreist, lett frem, albuene inntil siden.",
        ["Press håndtaket ned til armene er helt strake.",
         "Albuene står i ro – bare underarmene beveger seg.",
         "Før kontrollert opp til underarmene er vannrette."],
        ["Albuene glir frem og bak", "Lener seg over så kroppsvekten hjelper", "Halv bevegelse"]),
    "fransk-press": _i(
        "Ligg på en benk med en manual i hver hånd og armene strake over skuldrene, håndflatene mot hverandre.",
        ["Hold overarmene i ro.",
         "Bøy albuene og senk manualene mot siden av hodet.",
         "Strekk armene helt ut igjen."],
        ["Albuene glir ut til siden", "Overarmene beveger seg", "For tung vekt nær hodet"]),
    "triceps-over-hodet": _i(
        "Sitt eller stå oppreist og hold én manual med begge hender over hodet, armene strake.",
        ["Stram magen så du ikke svaier.",
         "Bøy albuene og senk manualen bak hodet.",
         "Albuene peker frem og holdes nær hodet.",
         "Strekk armene helt opp igjen."],
        ["Albuene spriker ut", "Svaier i korsryggen", "Halv bevegelse"]),
    "dips-benk": _i(
        "Sitt på kanten av en benk med hendene ved siden av hoftene, fingrene frem. Skyv setet frem fra benken, beina bøyd (lettere) eller strake (tyngre).",
        ["Bøy armene og senk kroppen rett ned.",
         "Albuene peker bakover.",
         "Gå ikke lenger ned enn skuldrene tåler – stopp ved ubehag foran i skulderen.",
         "Press deg opp til armene er strake."],
        ["Går for dypt", "Albuene spriker ut", "Setet glir langt fra benken"]),
    "triceps-strikk": _i(
        "Fest strikken høyt. Stå vendt mot festet med en ende i hver hånd og albuene inntil siden.",
        ["Press hendene ned til armene er strake.",
         "Albuene står i ro.",
         "Før kontrollert opp."],
        ["Albuene glir frem", "Lener seg over", "Slipper fort opp"]),

    # ------------------------------------------------------------------ bein isolert
    "beincurl": _i(
        "Juster apparatet så kneleddet er i linje med apparatets dreiepunkt og puten ligger like over hælene.",
        ["Bøy knærne og trekk puten mot setet.",
         "Hold hoftene nede mot puten/setet.",
         "Før kontrollert tilbake til nesten strake knær."],
        ["Hoftene løfter seg", "Rykker", "Slipper vekten fort tilbake"]),
    "nordic-light": _i(
        "Knel på en pute med anklene festet under noe stødig eller holdt av en partner. Kroppen rett fra knær til hode.",
        ["Stram mage og sete.",
         "Senk overkroppen fremover så sakte du klarer, med rett linje fra knær til hode.",
         "Ta imot med hendene når du ikke klarer å bremse lenger.",
         "Skyv deg opp med hendene til start.",
         "Krevende øvelse – start med få reps og bygg gradvis opp."],
        ["Bøyer i hofta", "Faller fort ned", "For mange reps i starten (gir mye stølhet)"]),
    "beincurl-strikk": _i(
        "Ligg på magen og fest strikken rundt ankelen og i noe stødig foran føttene.",
        ["Bøy kneet og trekk hælen mot setet.",
         "Hold hofta nede mot gulvet.",
         "Før rolig tilbake. Bytt bein etter settet."],
        ["Hofta løfter seg", "Rykker", "Slipper fort tilbake"]),
    "beinspark": _i(
        "Juster setet så kneet er i linje med apparatets dreiepunkt og puten ligger foran på anklene.",
        ["Strekk beina til knærne er strake.",
         "Hold et øyeblikk i toppen.",
         "Senk kontrollert."],
        ["Rykker opp vekten", "Setet løfter seg", "Slipper fort ned"]),
    "spansk-knebøy": _i(
        "Fest en kraftig strikk rundt noe stødig i knehøyde og legg den bak begge knærne. Gå bakover til strikken er stram. Føttene i hoftebredde.",
        ["Len deg litt bakover mot strikken med oppreist overkropp.",
         "Bøy knærne rett frem mens leggene holdes nesten loddrette.",
         "Gå ned så langt det er komfortabelt.",
         "Strekk knærne opp igjen."],
        ["Lener seg frem", "For slakk strikk", "Går dypere enn det kjennes greit i kneet"]),
    "tåhev": _i(
        "Stå med fremre del av føttene på kanten av et trinn og hælene utenfor. Hold i noe for balanse.",
        ["Senk hælene så langt ned du kan.",
         "Press deg opp på tærne så høyt du kan.",
         "Hold et øyeblikk i toppen og senk rolig.",
         "Tyngre: én manual i hånden eller på ett bein."],
        ["Spretter", "Halv bevegelse", "Bøyer knærne for å hjelpe"]),
    "tåhev-maskin": _i(
        "Still apparatet så skuldrene eller hoftene er under putene og fremre del av føttene på kanten av platen.",
        ["Senk hælene så langt ned du kan.",
         "Pause et sekund i bunnen.",
         "Press opp på tærne så høyt du kan og senk rolig."],
        ["Spretter i bunnen", "Halv bevegelse", "Bøyer knærne"]),
    "flyes-manualer": _i(
        "Ligg på en flat benk med en manual i hver hånd over brystet, håndflatene mot hverandre og lett bøy i albuene.",
        ["Senk armene ut til siden i en bue til du kjenner god strekk i brystet.",
         "Behold den samme lille bøyen i albuene.",
         "Klem armene tilbake over brystet som en stor klem."],
        ["Bøyer og strekker albuene så det blir press", "Går for dypt med tung vekt", "Skuldrene ruller frem"]),
    "kabelkryss": _i(
        "Still begge kablene høyt. Grip et håndtak i hver hånd og ta ett steg frem med lett foroverlent overkropp.",
        ["Lett bøy i albuene.",
         "Før hendene ned og sammen foran deg i en bue.",
         "Klem brystet et øyeblikk.",
         "Før kontrollert tilbake til du kjenner strekk."],
        ["Bøyer og strekker albuene", "Lener seg for langt frem", "Slipper fort tilbake"]),
    # ------------------------------------------------------------------ kondisjon og intervaller
    "sprellemann": _i(
        "Stå oppreist med føttene samlet og armene langs siden.",
        ["Hopp ut til bred fotstilling og før armene ut og opp over hodet samtidig.",
         "Hopp tilbake til samlede føtter med armene ned langs siden.",
         "Hold en jevn, lett rytme og land på fremre del av foten."],
        ["Lander tungt på hælene", "Armene kommer bare halvveis opp"], KONDIS),
    "jogg-pa-stedet": _i(
        "Stå oppreist med lett bøyde armer.",
        ["Jogg på stedet med lette, raske steg.",
         "Bruk armene aktivt i takt med beina.",
         "Øk tempoet for mer puls, eller gå på stedet for en roligere variant."],
        ["Tunge steg på hælene", "Sammensunket overkropp"], KONDIS),
    "hoye-knelloft": _i(
        "Stå oppreist med føttene i hoftebredde.",
        ["Løft knærne vekselvis opp til hoftehøyde i høyt tempo.",
         "Bruk armene som når du løper.",
         "Hold overkroppen oppreist og magen stram."],
        ["Lener seg bakover", "Knærne kommer ikke høyt nok"], KONDIS),
    "fjellklatrer": _i(
        "Start i høy planke med hendene rett under skuldrene og kroppen i en rett linje.",
        ["Dra det ene kneet frem mot brystet.",
         "Bytt bein raskt, som om du løper i planke.",
         "Hold hoftene lave og skuldrene over hendene hele tiden."],
        ["Setet stikker høyt opp", "Skuldrene glir bakover bak hendene"], KONDIS),
    "burpees": _i(
        "Stå oppreist med føttene i hoftebredde.",
        ["Sett deg ned og plasser hendene i gulvet foran føttene.",
         "Hopp eller gå bena bakover til planke (og senk brystet mot gulvet om du vil).",
         "Hopp eller gå føttene inn mot hendene igjen.",
         "Reis deg og avslutt med et lite hopp med armene over hodet."],
        ["Svai i korsryggen i planken", "Lander stivt med strake knær"], KONDIS),
    "hoppknebøy": _i(
        "Stå med føttene i hoftebredde, tærne lett utover.",
        ["Sitt ned i en knebøy med brystet oppe.",
         "Eksploder opp og hopp rett opp.",
         "Land mykt på fremre del av foten, og gå rett ned i neste knebøy."],
        ["Knærne faller innover i landingen", "Lander med strake bein"], KONDIS),
    "hoppende-utfall": _i(
        "Stå i en utfallsstilling med ett bein foran og ett bak.",
        ["Senk deg ned i utfall.",
         "Hopp opp og bytt bein i luften.",
         "Land mykt i utfall med motsatt bein foran og gå rett ned igjen."],
        ["Fremre kne faller innover", "Ukontrollert, hard landing"], KONDIS),
    "skøyterhopp": _i(
        "Stå på ett bein med lett bøyd kne.",
        ["Hopp sidelengs over til det andre beinet.",
         "Land mykt og la det frie beinet krysse bak.",
         "Stabiliser kort før du hopper tilbake."],
        ["Lander på strakt kne", "Mister balansen i landingen"], KONDIS),
    "thruster-manualer": _i(
        "Stå med føttene i hoftebredde og en manual i hver hånd, hvilende på skuldrene.",
        ["Sitt ned i en knebøy med brystet oppe.",
         "Press deg opp med kraft fra beina.",
         "Bruk farten til å presse manualene rett over hodet.",
         "Senk manualene til skuldrene og gå rett ned i neste knebøy."],
        ["Svai i korsryggen når armene er over hodet", "Pressen starter før beina er ferdige"], STAG_PUST),
    "step-up-kroppsvekt": _i(
        "Stå foran en stødig benk eller kasse.",
        ["Sett hele den ene foten opp på benken.",
         "Press deg opp med beinet på benken til du står oppreist.",
         "Gå kontrollert ned igjen med samme bein først.",
         "Bytt bein, eller ta alle repetisjonene på én side først."],
        ["Skyver fra med bakre fot", "Kneet faller innover"]),
    "sumoknebøy": _i(
        "Stå med bred fotstilling og tærne pekende godt utover.",
        ["Sitt ned mellom hælene med oppreist overkropp.",
         "La knærne følge retningen til tærne.",
         "Press opp gjennom hælene og klem setet i toppen."],
        ["Knærne faller innover", "Overkroppen faller fremover"]),
    "eselspark": _i(
        "Stå på alle fire med hendene under skuldrene og knærne under hoftene.",
        ["Hold kneet bøyd 90 grader og press hælen opp mot taket.",
         "Stopp når låret er i linje med kroppen.",
         "Senk kontrollert og gjenta før du bytter side."],
        ["Svai i korsryggen", "Vrir hoftene for å komme høyere"]),
    "brannhydrant": _i(
        "Stå på alle fire med hendene under skuldrene og knærne under hoftene.",
        ["Løft det ene kneet ut til siden med bøyd kne.",
         "Hold hoftene og overkroppen så stille som mulig.",
         "Senk kontrollert og gjenta før du bytter side."],
        ["Lener hele kroppen til siden", "Raske, ukontrollerte løft"]),
    "sykkelcrunch": _i(
        "Ligg på ryggen med hendene lett bak hodet og bena løftet med bøyde knær.",
        ["Strekk det ene beinet mens du vrir motsatt albue mot det bøyde kneet.",
         "Bytt side i en rolig «sykkelbevegelse».",
         "Hold korsryggen i kontakt med gulvet."],
        ["Drar i nakken med hendene", "For høyt tempo uten vridning"]),
    "russisk-vri": _i(
        "Sitt med bøyde knær og len overkroppen litt bakover med rett rygg.",
        ["Vri overkroppen til den ene siden og før hendene mot gulvet.",
         "Vri over til den andre siden.",
         "Løft føttene fra gulvet for en tyngre variant."],
        ["Runder ryggen", "Bare armene beveger seg"]),
    "saksespark": _i(
        "Ligg på ryggen med hendene under setet og bena strake.",
        ["Løft bena litt fra gulvet.",
         "Spark vekselvis opp og ned i små, raske bevegelser.",
         "Hold korsryggen presset mot gulvet hele tiden."],
        ["Korsryggen løfter seg", "Holder pusten"]),
    "planke-skulderklapp": _i(
        "Start i høy planke med hendene under skuldrene og føttene litt fra hverandre.",
        ["Løft den ene hånden og klapp på motsatt skulder.",
         "Sett hånden ned og bytt side.",
         "Hold hoftene stille – ikke la dem vippe fra side til side."],
        ["Hoftene svinger fra side til side", "Setet stikker opp"]),
}


def instruksjon_for(nokkel: str) -> dict | None:
    return INSTRUKSJONER.get(nokkel)
