"""Styrkeøkter som strukturerte Garmin-økter («workouts») med øvelse, sett, reps, vekt og hvile.

Garmin bruker egne øvelseskategorier og -navn (FIT-profilen). Der vi er sikre på det nøyaktige navnet,
sendes det; ellers bare kategorien, så klokka viser f.eks. «Roing» i stedet for den nøyaktige varianten.
Appens norske navn og vektforslaget legges i stegets beskrivelse.
"""
from __future__ import annotations

import hashlib
import json

# nøkkel → (kategori, nøyaktig navn eller None)
GARMIN_OVELSER: dict[str, tuple[str, str | None]] = {
    # knebøy
    "knebøy-stang": ("SQUAT", "BARBELL_BACK_SQUAT"), "frontknebøy": ("SQUAT", "BARBELL_FRONT_SQUAT"),
    "goblet-knebøy": ("SQUAT", "GOBLET_SQUAT"), "goblet-knebøy-kb": ("SQUAT", "GOBLET_SQUAT"),
    "beinpress": ("SQUAT", "LEG_PRESS"), "knebøy-kroppsvekt": ("SQUAT", None), "boks-knebøy": ("SQUAT", None),
    "spansk-knebøy": ("SQUAT", None),
    # hoftehengsel
    "markløft": ("DEADLIFT", "BARBELL_DEADLIFT"), "rumensk-markløft": ("DEADLIFT", "ROMANIAN_DEADLIFT"),
    "rumensk-markløft-man": ("DEADLIFT", None), "kettlebell-markløft": ("DEADLIFT", None),
    "good-morning-strikk": ("DEADLIFT", None), "kettlebell-sving": ("HIP_SWING", None), "ryggstrekk": ("HYPEREXTENSION", None),
    # ettbeins
    "bulgarsk-utfall": ("LUNGE", None), "utfall-manualer": ("LUNGE", None), "step-up": ("LUNGE", None),
    "utfall-kroppsvekt": ("LUNGE", None), "bakoverutfall": ("LUNGE", None),
    # sete
    "hoftehev-stang": ("HIP_RAISE", None), "setehev": ("HIP_RAISE", None), "setehev-ettbeins": ("HIP_RAISE", None),
    "hoftehev-manual": ("HIP_RAISE", None), "sidegange-strikk": ("HIP_STABILITY", None),
    # press
    "benkpress": ("BENCH_PRESS", "BARBELL_BENCH_PRESS"), "benkpress-manualer": ("BENCH_PRESS", "DUMBBELL_BENCH_PRESS"),
    "skrå-benk-manualer": ("BENCH_PRESS", "INCLINE_DUMBBELL_BENCH_PRESS"), "brystpress-maskin": ("BENCH_PRESS", None),
    "brystpress-strikk": ("BENCH_PRESS", None), "armhevinger": ("PUSH_UP", "PUSH_UP"),
    "stående-press": ("SHOULDER_PRESS", None), "skulderpress-manualer": ("SHOULDER_PRESS", None),
    "landmine-press": ("SHOULDER_PRESS", None), "skulderpress-maskin": ("SHOULDER_PRESS", None),
    "pike-armhevinger": ("SHOULDER_PRESS", None), "skulderpress-strikk": ("SHOULDER_PRESS", None),
    # trekk
    "roing-stang": ("ROW", None), "ettarms-roing": ("ROW", None), "sittende-roing": ("ROW", None),
    "roing-brystsupport": ("ROW", None), "roing-strikk": ("ROW", None), "omvendt-roing": ("ROW", None),
    "pull-ups": ("PULL_UP", "PULL_UP"), "pull-ups-strikk": ("PULL_UP", "PULL_UP"), "nedtrekk": ("PULL_UP", None),
    "nedtrekk-strikk": ("PULL_UP", None), "pullover-manual": ("PULL_UP", None),
    # kjerne
    "planke": ("PLANK", "PLANK"), "sideplanke": ("PLANK", "SIDE_PLANK"), "dead-bug": ("CORE", None),
    "pallof-press": ("CORE", None), "pallof-strikk": ("CORE", None), "bondegange": ("CARRY", "FARMERS_WALK"),
    "hengende-kneløft": ("LEG_RAISE", None), "bird-dog": ("HIP_STABILITY", None),
    # skuldre og armer
    "face-pull": ("SHOULDER_STABILITY", None), "face-pull-strikk": ("SHOULDER_STABILITY", None),
    "utadrotasjon": ("SHOULDER_STABILITY", None), "omvendt-flyes": ("FLYE", None),
    "sidehev": ("LATERAL_RAISE", None), "sidehev-kabel": ("LATERAL_RAISE", None), "sidehev-strikk": ("LATERAL_RAISE", None),
    "bicepscurl": ("CURL", None), "hammercurl": ("CURL", None), "bicepscurl-kabel": ("CURL", None), "bicepscurl-strikk": ("CURL", None),
    "triceps-pushdown": ("TRICEPS_EXTENSION", None), "fransk-press": ("TRICEPS_EXTENSION", None),
    "triceps-over-hodet": ("TRICEPS_EXTENSION", None), "dips-benk": ("TRICEPS_EXTENSION", None),
    "triceps-strikk": ("TRICEPS_EXTENSION", None),
    # bein isolert og bryst
    "beincurl": ("LEG_CURL", None), "nordic-light": ("LEG_CURL", None), "beincurl-strikk": ("LEG_CURL", None),
    "beinspark": ("SQUAT", None), "tåhev": ("CALF_RAISE", None), "tåhev-maskin": ("CALF_RAISE", None),
    "flyes-manualer": ("FLYE", None), "kabelkryss": ("FLYE", None),
}
MONSTER_KATEGORI = {
    "kne": "SQUAT", "hofte": "DEADLIFT", "utfall": "LUNGE", "sete": "HIP_RAISE", "press_hor": "BENCH_PRESS",
    "press_vert": "SHOULDER_PRESS", "trekk_hor": "ROW", "trekk_vert": "PULL_UP", "kjerne": "CORE",
    "skulderhelse": "SHOULDER_STABILITY", "skuldre_iso": "LATERAL_RAISE", "biceps": "CURL", "triceps": "TRICEPS_EXTENSION",
    "bakside_iso": "LEG_CURL", "forside_iso": "SQUAT", "legger": "CALF_RAISE", "bryst_iso": "FLYE",
}
SPORT = {"sportTypeId": 5, "sportTypeKey": "strength_training"}
KG = {"unitId": 8, "unitKey": "kilogram", "factor": 1000}
INGEN_MAAL = {"workoutTargetTypeId": 1, "workoutTargetTypeKey": "no.target"}


def kategori(ovelse: dict) -> tuple[str, str | None]:
    return GARMIN_OVELSER.get(ovelse["nokkel"]) or (MONSTER_KATEGORI.get(ovelse.get("monster"), "TOTAL_BODY"), None)


def _sett_steg(nr: int, barn: int | None, ovelse: dict, reps: int, kg: float | None, sekunder: bool,
               typ: str = "interval", beskrivelse: str = "") -> dict:
    kat, navn = kategori(ovelse)
    st = {"type": "ExecutableStepDTO", "stepOrder": nr,
          "stepType": {"stepTypeId": 1, "stepTypeKey": "warmup"} if typ == "warmup" else {"stepTypeId": 3, "stepTypeKey": "interval"},
          "endCondition": {"conditionTypeId": 2, "conditionTypeKey": "time"} if sekunder else {"conditionTypeId": 10, "conditionTypeKey": "reps"},
          "endConditionValue": int(reps), "category": kat, "targetType": INGEN_MAAL,
          "description": beskrivelse[:200]}
    if navn:
        st["exerciseName"] = navn
    if kg:
        st["weightValue"] = float(kg)
        st["weightUnit"] = KG
    if barn is not None:
        st["childStepId"] = barn
    return st


def _hvile(nr: int, barn: int | None, sek: int) -> dict:
    st = {"type": "ExecutableStepDTO", "stepOrder": nr, "stepType": {"stepTypeId": 5, "stepTypeKey": "rest"},
          "endCondition": {"conditionTypeId": 2, "conditionTypeKey": "time"}, "endConditionValue": int(sek), "targetType": INGEN_MAAL}
    if barn is not None:
        st["childStepId"] = barn
    return st


def bygg_workout(navn: str, ovelser: list[dict]) -> dict:
    """ovelser: [{ovelse (dict), sett, reps, kg, hvile_s, sekunder, oppvarming [{kg, reps}], tekst}]"""
    steg: list[dict] = []
    nr = 0
    barn = 0
    for o in ovelser:
        ov = o["ovelse"]
        for w in o.get("oppvarming") or []:
            nr += 1
            steg.append(_sett_steg(nr, None, ov, w["reps"], w["kg"], False, "warmup", f"Oppvarming {ov['navn']}"))
            nr += 1
            steg.append(_hvile(nr, None, 60))
        barn += 1
        nr += 1
        gruppe = {"type": "RepeatGroupDTO", "stepOrder": nr, "stepType": {"stepTypeId": 6, "stepTypeKey": "repeat"},
                  "numberOfIterations": int(o["sett"]), "smartRepeat": False, "childStepId": barn, "workoutSteps": []}
        nr += 1
        gruppe["workoutSteps"].append(_sett_steg(nr, barn, ov, o["reps"], o.get("kg"), o.get("sekunder", False),
                                                 beskrivelse=f"{ov['navn']}: {o.get('tekst') or ''}"))
        nr += 1
        gruppe["workoutSteps"].append(_hvile(nr, barn, o.get("hvile_s") or 90))
        steg.append(gruppe)
    return {"workoutName": f"Styrkeboka: {navn}"[:60], "description": "Laget av Styrkeboka – logg settene i appen.",
            "sportType": SPORT, "workoutSegments": [{"segmentOrder": 1, "sportType": SPORT, "workoutSteps": steg}]}


def fingeravtrykk(w: dict) -> str:
    return hashlib.sha1(json.dumps(w, sort_keys=True, ensure_ascii=False).encode()).hexdigest()[:16]
