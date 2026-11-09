"""Tester for program, progresjon og økter. Kjør: python3 -m pytest styrkeboka/tests"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "app"))

import ai  # noqa: E402
import program as P  # noqa: E402
from db import Database  # noqa: E402
from logikk import Feil, Styrkeboka  # noqa: E402
from ovelser import BIBLIOTEK, MONSTER, UTSTYR  # noqa: E402


@pytest.fixture
def sb(tmp_path):
    s = Styrkeboka(Database(tmp_path / "t.db"))
    s.lagre_profil({"navn": "Testperson", "maal": ["muskelvekst", "generell"], "dager_per_uke": 3, "okt_minutter": 60})
    return s


def test_alle_ovelser_har_instruksjon():
    from instruksjoner import INSTRUKSJONER
    nokler = {o["nokkel"] for o in BIBLIOTEK}
    assert nokler == set(INSTRUKSJONER), nokler ^ set(INSTRUKSJONER)
    for k, i in INSTRUKSJONER.items():
        assert i["start"] and len(i["steg"]) >= 2 and i["feil"] and i["pust"], k


def test_egen_ovelse_med_instruksjon(sb):
    o = sb.lagre_egen_ovelse({"navn": "Min øvelse", "monster": "kjerne", "type": "kroppsvekt", "instruksjon": "Steg en\nSteg to"})
    assert o["instruksjon"]["steg"] == ["Steg en", "Steg to"]
    assert sb.ovelse("planke")["instruksjon"]["steg"]


def test_bibliotek_gyldig():
    for o in BIBLIOTEK:
        assert o["monster"] in MONSTER, o["nokkel"]
        assert set(o["utstyr"]) <= set(UTSTYR), o["nokkel"]
        assert o["tips"], o["nokkel"]


@pytest.mark.parametrize("dager", [1, 2, 3, 4, 5, 6])
@pytest.mark.parametrize("utstyr", [None, set(), {"manualer", "strikk"}, {"manualer", "benk"}])
def test_program_for_alle_oppsett(dager, utstyr):
    prof = {"dager_per_uke": dager, "okt_minutter": 45, "erfaring": "noe", "maal": ["generell"]}
    prog = P.lag_program(prof, BIBLIOTEK, utstyr)
    assert len(prog["dager"]) == dager
    for d in prog["dager"]:
        assert 3 <= len(d["ovelser"]) <= 5
        nokler = [o["ovelse"] for o in d["ovelser"]]
        assert len(nokler) == len(set(nokler))


def test_rehab_velger_skansomt():
    prof = {"dager_per_uke": 2, "okt_minutter": 60, "erfaring": "nybegynner", "maal": ["rehab"]}
    prog = P.lag_program(prof, BIBLIOTEK, None)
    idx = {o["nokkel"]: o for o in BIBLIOTEK}
    for d in prog["dager"]:
        for o in d["ovelser"]:
            assert idx[o["ovelse"]]["skansom"], o["ovelse"]
            assert o["rir"] >= 3
            assert o["reps_maks"] >= 15


def _sett(kg, reps, rir=None):
    return {"vekt": kg, "reps": reps, "rir": rir}


def test_progresjon():
    stang = next(o for o in BIBLIOTEK if o["nokkel"] == "knebøy-stang")
    plan = {"sett": 3, "reps_min": 8, "reps_maks": 12, "rir": 2}
    assert P.foreslaa(stang, plan, [])["trend"] == "ny"
    opp = P.foreslaa(stang, plan, [[_sett(60, 12), _sett(60, 12), _sett(60, 12)]])
    assert opp["trend"] == "opp" and opp["kg"] == 62.5
    likt = P.foreslaa(stang, plan, [[_sett(60, 10), _sett(60, 9), _sett(60, 8)]])
    assert likt["trend"] == "likt" and likt["kg"] == 60 and likt["reps"] == 11
    ned = P.foreslaa(stang, plan, [[_sett(60, 6)], [_sett(60, 7)]])
    assert ned["trend"] == "ned" and ned["kg"] < 60
    # én dårlig økt gir ikke nedtrapping
    assert P.foreslaa(stang, plan, [[_sett(60, 6)], [_sett(60, 10)]])["trend"] == "likt"


def test_okt_flyt(sb):
    pid = sb.profiler()[0]["id"]
    prog = sb.lagre_program(pid, sb.foreslaa_program(pid), kilde="mal")
    assert prog["aktiv"] == 1
    dag = sb.neste_dag(pid)
    assert dag["id"] == prog["dager"][0]["id"]
    okt = sb.start_okt(pid, dag["id"])
    assert len(okt["ovelser"]) == len(dag["ovelser"])
    with pytest.raises(Feil):
        sb.avslutt_okt(okt["id"], {})
    forste = okt["ovelser"][0]
    for _ in range(3):
        sb.logg_sett(okt["id"], {"okt_ovelse_id": forste["id"], "vekt": "40", "reps": forste["reps_maks"], "rir": 2})
    res = sb.avslutt_okt(okt["id"], {"opplevd": 3})
    assert res["okt"]["nokkeltall"]["sett"] == 3
    assert sb.neste_dag(pid)["id"] == prog["dager"][1]["id"]
    # neste gang samme dag: forslag om mer vekt
    for d in prog["dager"][1:]:
        o2 = sb.start_okt(pid, d["id"])
        sb.logg_sett(o2["id"], {"okt_ovelse_id": o2["ovelser"][0]["id"], "vekt": 10, "reps": 10})
        sb.avslutt_okt(o2["id"], {})
    o3 = sb.start_okt(pid, prog["dager"][0]["id"])
    assert o3["ovelser"][0]["forslag_kg"] > 40
    assert sb.historikk(pid)
    h = sb.ovelse_historikk(pid, forste["ovelse"])
    assert h["punkter"][0]["topp_kg"] == 40


def test_bytte_lagres_i_program(sb):
    pid = sb.profiler()[0]["id"]
    prog = sb.lagre_program(pid, sb.foreslaa_program(pid), kilde="mal")
    okt = sb.start_okt(pid, prog["dager"][0]["id"])
    oo = okt["ovelser"][0]
    alt = next(a for a in sb.alternativer(oo["ovelse"], None) if a["tilgjengelig"])
    sb.endre_okt_ovelse(oo["id"], {"ovelse": alt["nokkel"], "ogsa_program": True})
    ny = sb.aktivt_program(pid)
    assert ny["dager"][0]["ovelser"][0]["ovelse"] == alt["nokkel"]
    assert len(sb.versjoner(ny["id"])) == 2


def test_hjemme_bytter_ut_utilgjengelig(sb):
    pid = sb.profiler()[0]["id"]
    gym, hjemme = sb.utstyrsprofiler()
    prog = sb.lagre_program(pid, sb.foreslaa_program(pid, gym["id"]), kilde="mal")
    okt = sb.start_okt(pid, prog["dager"][0]["id"], upid=hjemme["id"])
    tilgj = sb.utstyr_for(hjemme["id"])
    for oo in okt["ovelser"]:
        assert set(oo["info"]["utstyr"]) <= tilgj or oo["erstattet_fra"] is None


def test_ai_tolk_program(sb):
    svar = """Her er programmet:
```json
{"navn": "Test", "dager": [{"navn": "A", "ovelser": [
  {"ovelse": "goblet-knebøy", "sett": 3, "reps_min": 10, "reps_maks": 15},
  {"ovelse": "finnes-ikke", "sett": 3}
]}], "begrunnelse": "fordi"}
```"""
    data = ai.les_json(svar)
    pid = sb.profiler()[0]["id"]
    prog = sb.lagre_program(pid, data, kilde="ai")
    assert [o["ovelse"] for o in prog["dager"][0]["ovelser"]] == ["goblet-knebøy"]


def test_ai_kontekst_uten_navn(sb):
    pid = sb.profiler()[0]["id"]
    sb.lagre_profil({"hensyn": "Vond venstre skulder"}, pid)
    tekst = ai.profilkontekst(sb, pid)
    assert "Testperson" not in tekst
    assert "skulder" in tekst


def test_blokker(sb):
    from datetime import timedelta
    import program as P2
    pid = sb.profiler()[0]["id"]
    prog = sb.lagre_program(pid, sb.foreslaa_program(pid), kilde="mal")
    b = prog["blokk"]
    assert b["nr"] == 1 and b["uke"] == 1 and b["uker"] == 6 and not b["ferdig"]
    faste = {o["ovelse"] for d in prog["dager"] for o in d["ovelser"] if o["fast"]}
    assert faste and all(sb.ovelse(k)["monster"] in P2.HOVED for k in faste)
    # gjør én vanlig økt
    o = sb.start_okt(pid, prog["dager"][0]["id"])
    oo = o["ovelser"][0]
    sb.logg_sett(o["id"], {"okt_ovelse_id": oo["id"], "vekt": 50, "reps": 10})
    sb.avslutt_okt(o["id"], {})
    # spol til uke 6 = lettere uke
    start = (sb.lokal(sb_naa()) - timedelta(weeks=5)).date()
    start = start - timedelta(days=start.weekday())
    sb.db.kjor("UPDATE programmer SET blokk_start = ? WHERE id = ?", (start.isoformat(), prog["id"]))
    assert sb.program(prog["id"])["blokk"]["lett_naa"]
    lett = sb.start_okt(pid, prog["dager"][0]["id"])
    assert lett["lett"] == 1
    l_oo = lett["ovelser"][0]
    assert l_oo["sett_plan"] < oo["sett_plan"] and l_oo["forslag_kg"] == 50
    sb.logg_sett(lett["id"], {"okt_ovelse_id": l_oo["id"], "vekt": 50, "reps": 4})
    sb.avslutt_okt(lett["id"], {})
    # lette uker teller ikke i progresjonen
    assert sb.tidligere_sett(pid, oo["ovelse"])[0][0]["reps"] == 10
    # blokka ferdig -> ny blokk uten AI beholder faste øvelser
    sb.db.kjor("UPDATE programmer SET blokk_start = ? WHERE id = ?", ((start - timedelta(weeks=1)).isoformat(), prog["id"]))
    assert sb.program(prog["id"])["blokk"]["ferdig"]
    forslag = sb.foreslaa_ny_blokk(prog["id"])
    assert forslag["endringer"]
    ny = sb.start_ny_blokk(prog["id"], forslag, kilde="mal")
    assert ny["blokk"]["nr"] == 2 and ny["blokk"]["uke"] == 1
    nye_faste = {o["ovelse"] for d in ny["dager"] for o in d["ovelser"] if o["fast"]}
    assert faste <= nye_faste
    alle_gamle = {o["ovelse"] for d in prog["dager"] for o in d["ovelser"] if not o["fast"]}
    alle_nye = {o["ovelse"] for d in ny["dager"] for o in d["ovelser"] if not o["fast"]}
    assert alle_gamle != alle_nye


def test_sikre_faste_legger_tilbake(sb):
    pid = sb.profiler()[0]["id"]
    prog = sb.lagre_program(pid, sb.foreslaa_program(pid), kilde="mal")
    data = sb.program_data(prog["id"])
    fast = next(o for o in data["dager"][0]["ovelser"] if o["fast"])
    data["dager"][0]["ovelser"] = [o for o in data["dager"][0]["ovelser"] if o["ovelse"] != fast["ovelse"]]
    sikret = sb.sikre_faste(prog["id"], data)
    assert fast["ovelse"] in {o["ovelse"] for o in sikret["dager"][0]["ovelser"]}


def sb_naa():
    from db import naa
    return naa()


def test_startvekter(sb):
    pid = sb.profiler()[0]["id"]
    sb.lagre_program(pid, sb.foreslaa_program(pid), kilde="mal")
    assert sb.mangler_startvekt(pid) > 0
    r = sb.beregn_startvekter(pid, [{"ovelse": "benkpress", "kg": "80", "reps": 5}], "82")
    assert sb.profil(pid)["kroppsvekt"] == 82 and sb.mangler_startvekt(pid) == 0
    vekter = {f["ovelse"]: f["kg"] for f in r["forslag"] if f["kg"]}
    assert vekter
    # benkpress med manualer per manual skal være godt under stang
    import program as P2, ovelser as O2
    idx = {o["nokkel"]: o for o in O2.BIBLIOTEK}
    ref = P2.referanser([{"ovelse": "benkpress", "kg": 80, "reps": 5}])
    plan = {"reps_min": 8, "reps_maks": 12, "rir": 2}
    assert P2.anslaa_vekt(idx["benkpress-manualer"], plan, ref) < P2.anslaa_vekt(idx["benkpress"], plan, ref) / 2
    sb.lagre_startvekter(pid, vekter, "ai")
    prog = sb.aktivt_program(pid)
    okt = sb.start_okt(pid, prog["dager"][0]["id"])
    med_vekt = [oo for oo in okt["ovelser"] if oo["ovelse"] in vekter]
    assert med_vekt and all(oo["forslag_kg"] == vekter[oo["ovelse"]] for oo in med_vekt)
    assert "AI-treneren" in med_vekt[0]["forslag_tekst"]


def test_anslag_fra_logget_ovelse(sb):
    pid = sb.profiler()[0]["id"]
    sb.lagre_profil({"maal": ["muskelvekst"]}, pid)
    o = sb.start_okt(pid, None)
    sb.legg_til_ovelse(o["id"], {"ovelse": "benkpress"})
    oo = sb.okt(o["id"])["ovelser"][0]
    sb.logg_sett(o["id"], {"okt_ovelse_id": oo["id"], "vekt": 70, "reps": 8})
    sb.avslutt_okt(o["id"], {})
    f = sb.forslag(pid, sb.ovelse("skrå-benk-manualer"), {"reps_min": 8, "reps_maks": 12, "rir": 2}, [])
    assert f["kg"] and 10 <= f["kg"] <= 30 and "benkpress" in f["tekst"]


# ------------------------------------------------------------------ kropp og kondisjon
GARMIN_LOP = {"activityId": 111, "activityName": "Morgenløp", "activityType": "running", "distance": 5000.0, "duration": 1500.0,
              "averageHR": 150, "maxHR": 170, "steps": 4500, "moderateIntensityMinutes": 2, "vigorousIntensityMinutes": 22,
              "startLatitude": 1.0, "startLongitude": 2.0, "startTime": None}
GARMIN_GAA = {"activityId": 112, "activityName": "Gåtur", "activityType": "walking", "distance": 3000.0, "duration": 2400.0,
              "moderateIntensityMinutes": 30, "vigorousIntensityMinutes": 0, "startTime": None}


def _naa_iso(dager_siden=0):
    from datetime import timedelta
    from db import naa, til_iso
    return til_iso(naa() - timedelta(days=dager_siden))


def test_garmin_import_og_ukesminutter(sb):
    import kropp
    pid = sb.profiler()[0]["id"]
    lop = {**GARMIN_LOP, "startTime": _naa_iso(0)}
    assert kropp.importer_garmin(sb, pid, lop)
    assert not kropp.importer_garmin(sb, pid, lop)  # ingen duplikat
    assert kropp.importer_garmin(sb, pid, {**GARMIN_GAA, "startTime": _naa_iso(0)})
    rader = sb.db.alle("SELECT * FROM aktiviteter")
    assert "startLatitude" not in rader[0] and len(rader) == 2
    u = kropp.uker(sb, pid, 1)[-1]
    assert u["kondisjon_min"] == 2 + 2 * 22 + 30
    assert u["km_loping"] == 5.0 and u["km_gaing"] == 3.0
    a = kropp.aktiviteter(sb, pid)[0]
    assert a["tempo"] in ("5:00",) or kropp.aktiviteter(sb, pid)[1]["tempo"] == "5:00"


def test_maalinger_og_avledet(sb):
    import kropp
    pid = sb.profiler()[0]["id"]
    sb.lagre_profil({"fodselsaar": 1987, "hoyde_cm": "180", "kjonn": "mann"}, pid)
    kropp.lagre_maaling(sb, pid, "vekt", "80,0", "2026-10-01")
    kropp.lagre_maaling(sb, pid, "vekt", 78, "2026-10-31")
    assert sb.profil(pid)["kroppsvekt"] == 78
    # automatisk henting overskriver ikke manuell måling samme dag
    assert kropp.lagre_maaling(sb, pid, "vekt", 90, "2026-10-31", kilde="ha") is None
    assert kropp.lagre_maaling(sb, pid, "vekt", 500) is None
    av = kropp.avledet(sb, pid)
    assert av["bmi"] == round(78 / 1.8 ** 2, 1) and av["makspuls"] == round(211 - 0.64 * av["alder"])
    tekst = kropp.ai_tekst(sb, pid)
    assert "Vekt: 78 kg" in tekst and "Testperson" not in tekst


def test_ha_synk(sb, monkeypatch):
    import asyncio
    import types
    if "aiohttp" not in sys.modules:
        fake = types.ModuleType("aiohttp")
        fake.ClientTimeout = lambda **k: None
        fake.ClientError = Exception
        fake.ClientSession = object
        sys.modules["aiohttp"] = fake
    import ha
    pid = sb.profiler()[0]["id"]
    sb.lagre_profil({"navn": "Ola"}, pid)
    sb.lagre_profil({"navn": "Kari"})
    k = ha.HAKobling(sb)
    k.aktiv = True
    tilstander = [
        {"entity_id": "sensor.ola_last_activities", "state": "0", "attributes": {"friendly_name": "Ola Garmin Last activities",
         "last_activities": [{**GARMIN_LOP, "startTime": _naa_iso(1)}]}},
        {"entity_id": "sensor.ola_weight", "state": "81.2", "last_changed": _naa_iso(2),
         "attributes": {"friendly_name": "Ola Garmin Weight", "device_class": "weight", "unit_of_measurement": "kg"}},
        {"entity_id": "sensor.kari_weight", "state": "60", "last_changed": _naa_iso(2),
         "attributes": {"friendly_name": "Kari Garmin Weight", "device_class": "weight", "unit_of_measurement": "kg"}},
        {"entity_id": "sensor.ola_yesterday_steps", "state": "8000", "last_changed": _naa_iso(0), "attributes": {"friendly_name": "Ola Yesterday steps"}},
        {"entity_id": "sensor.ola_resting_heart_rate", "state": "55", "last_changed": _naa_iso(0), "attributes": {"friendly_name": "Ola Resting heart rate"}},
    ]

    async def fake_tilstander():
        return tilstander

    async def fake_hist(eid, dager, attributter=False):
        return [{"state": "83.0", "last_changed": _naa_iso(40)}] if eid == "sensor.ola_weight" else []
    monkeypatch.setattr(k, "_tilstander", fake_tilstander)
    monkeypatch.setattr(k, "_historikk", fake_hist)
    res = asyncio.run(k.kilder(sb.profil(pid)))
    assert res["forslag"]["vekt"] == "sensor.ola_weight" and res["forslag"]["aktiviteter"] == "sensor.ola_last_activities"
    sb.lagre_profil({"koblinger": res["forslag"]}, pid)
    r = asyncio.run(k.synk_profil(sb.profil(pid), historikk=True))
    assert r["importert"] == 1
    import kropp
    vekter = kropp.maalinger(sb, pid, "vekt")
    assert [v["verdi"] for v in vekter] == [83.0, 81.2]
    assert kropp.siste(sb, pid, "skritt")["verdi"] == 8000
    assert kropp.siste(sb, pid, "hvilepuls")["verdi"] == 55



def test_lopeperiode(sb):
    from datetime import timedelta
    import kropp
    import loping
    pid = sb.profiler()[0]["id"]
    i_dag = sb.lokal(sb_naa()).date()
    p = loping.lagre_periode(sb, pid, {"fra": (i_dag - timedelta(days=8)).isoformat(), "til": (i_dag + timedelta(weeks=7)).isoformat(),
                                       "okter_per_uke": 3, "niva": "vanlig", "maal": "10km"})
    s = loping.status(sb, pid)
    a = s["aktiv"]
    assert a and a["uke"] in (2, 3) and len(a["plan"]) == 3 and a["gjort"] == 0
    assert [o["type"] for o in a["plan"]] == ["rolig", "intervall", "langtur"]
    kropp.importer_garmin(sb, pid, {**GARMIN_LOP, "startTime": _naa_iso(0)})
    assert loping.status(sb, pid)["aktiv"]["gjort"] == 1
    # nybegynner får løp/gå, 4. uke er lettere
    assert loping.ukeplan({"okter_per_uke": 2, "niva": "nybegynner"}, 1)[0]["type"] == "lopgaa"
    assert loping.ukeplan({"okter_per_uke": 1, "niva": "vanlig"}, 4)[0]["minutter"] < loping.ukeplan({"okter_per_uke": 3, "niva": "vanlig"}, 5)[2]["minutter"]
    # juster styrke: hjelpeøvelse for bein får ett sett mindre, faste øvelser ikke
    assert loping.juster_plan(sb, pid, {"sett": 3}, "utfall", False)["sett"] == 2
    assert loping.juster_plan(sb, pid, {"sett": 3}, "kne", True)["sett"] == 3
    assert "Løpeperiode aktiv" in loping.ai_tekst(sb, pid)


def test_oppvarming_per_kroppsdel(sb):
    pid = sb.profiler()[0]["id"]
    prog = sb.lagre_program(pid, sb.foreslaa_program(pid), kilde="mal")
    sb.lagre_startvekter(pid, {o["ovelse"]: 60 for d in prog["dager"] for o in d["ovelser"]}, "manuell")
    okt = sb.start_okt(pid, prog["dager"][0]["id"])
    med = [oo for oo in okt["ovelser"] if oo["oppvarming"]]
    assert len(med) >= 2 and okt["generell_oppvarming"]["bevegelser"]



def test_garmin_eksport(sb, monkeypatch):
    import asyncio
    import types
    from datetime import timedelta
    if "aiohttp" not in sys.modules:
        fake = types.ModuleType("aiohttp")
        fake.ClientTimeout = lambda **k: None
        fake.ClientError = Exception
        fake.ClientSession = object
        sys.modules["aiohttp"] = fake
    import ha
    import kropp
    import loping
    pid = sb.profiler()[0]["id"]
    sb.lagre_profil({"koblinger": {"aktiviteter": "sensor.x_last_activities"}, "garmin_eksport": {"okter": True, "loping": True}}, pid)
    k = ha.HAKobling(sb)
    k.aktiv = True
    kall = []

    async def fake_tjeneste(domene, tjeneste, data, svar=False):
        kall.append((tjeneste, data))
        return {"workout_id": 100 + len(kall), "schedule_id": 1} if svar else None
    monkeypatch.setattr(k, "_tjeneste", fake_tjeneste)
    # styrkeøkt sendes én gang
    o = sb.start_okt(pid, None)
    sb.legg_til_ovelse(o["id"], {"ovelse": "benkpress"})
    oo = sb.okt(o["id"])["ovelser"][0]
    sb.logg_sett(o["id"], {"okt_ovelse_id": oo["id"], "vekt": 60, "reps": 8})
    sb.avslutt_okt(o["id"], {})
    assert asyncio.run(k.send_okt_til_garmin(o["id"]))
    assert not asyncio.run(k.send_okt_til_garmin(o["id"]))
    assert kall[0][0] == "create_activity" and kall[0][1]["activity_type"] == "fitness_equipment"
    # og den importeres ikke tilbake som egen aktivitet
    assert not kropp.importer_garmin(sb, pid, {"activityId": 5, "activityName": "Styrketrening: Fri økt", "activityType": "fitness_equipment", "startTime": _naa_iso(0)})
    # løpeturer legges i kalenderen, uten duplikater
    i_dag = sb.lokal(sb_naa()).date()
    per = loping.lagre_periode(sb, pid, {"fra": i_dag.isoformat(), "til": (i_dag + timedelta(weeks=6)).isoformat(), "lopedager": [0, 2, 4, 6], "niva": "vanlig"})
    assert per["okter_per_uke"] == 3 and per["lopedager"] == [0, 2, 4]
    kall.clear()
    r = asyncio.run(k.synk_garmin_lopeokter(sb.profil(pid)))
    assert r["lagt_inn"] >= 3 and all(c[0] == "create_workout" for c in kall)
    assert asyncio.run(k.synk_garmin_lopeokter(sb.profil(pid))) == {"lagt_inn": 0, "fjernet": 0}
    # endrer perioden -> gamle fjernes og nye legges inn
    loping.lagre_periode(sb, pid, {**per, "lopedager": [1]}, per["id"])
    r = asyncio.run(k.synk_garmin_lopeokter(sb.profil(pid)))
    assert r["fjernet"] >= 3 and r["lagt_inn"] >= 1
    # slår av -> alt fremtidig fjernes
    sb.lagre_profil({"garmin_eksport": {"okter": True, "loping": False}}, pid)
    r = asyncio.run(k.synk_garmin_lopeokter(sb.profil(pid)))
    assert r["lagt_inn"] == 0 and not sb.db.alle("SELECT * FROM garmin_okter")
    steg = loping.garmin_okt({"type": "intervall", "tittel": "Intervall 4×4 min", "beskrivelse": "", "minutter": 35})["workoutSegments"][0]["workoutSteps"]
    assert steg[1]["numberOfIterations"] == 4 and steg[1]["workoutSteps"][0]["zoneNumber"] == 4



def test_klokke_styrke_og_puls(sb):
    from datetime import timedelta
    import kropp
    from db import fra_iso, til_iso
    pid = sb.profiler()[0]["id"]
    o = sb.start_okt(pid, None)
    sb.legg_til_ovelse(o["id"], {"ovelse": "benkpress"})
    oo = sb.okt(o["id"])["ovelser"][0]
    for _ in range(3):
        sb.logg_sett(o["id"], {"okt_ovelse_id": oo["id"], "vekt": 60, "reps": 8})
    sb.avslutt_okt(o["id"], {})
    okt = sb.okt(o["id"])
    start = fra_iso(okt["startet"]) - timedelta(minutes=2)
    # spre settene utover 6 minutter
    for i, s in enumerate(sb.db.alle("SELECT id FROM sett WHERE okt_id = ? ORDER BY id", (o["id"],))):
        sb.db.kjor("UPDATE sett SET tid = ? WHERE id = ?", (til_iso(start + timedelta(minutes=2 + 2 * i)), s["id"]))
    assert kropp.importer_garmin(sb, pid, {"activityId": 77, "activityName": "Styrke", "activityType": "strength_training",
                                           "startTime": til_iso(start), "duration": 900, "averageHR": 110, "maxHR": 150,
                                           "hrTimeInZone_1": 300, "hrTimeInZone_2": 400, "hrTimeInZone_3": 200})
    assert kropp.koble_styrke(sb, pid) == 1
    a = sb.db.en("SELECT * FROM aktiviteter WHERE ekstern_id = 'garmin-77'")
    assert a["okt_id"] == o["id"] and a["soner"][1] == 400
    # koblet styrke vises ikke i aktivitetslista og teller ikke dobbelt
    assert not [x for x in kropp.aktiviteter(sb, pid) if x["type"] == "styrke"]
    # pulskurve: topp rundt hvert sett, lav puls i pausene
    serie = []
    for sek in range(0, 900, 5):
        naer_sett = any(abs(sek - (120 + 120 * i)) < 30 for i in range(3))
        serie.append([sek, 145 if naer_sett else 100, None])
    kropp.lagre_puls(sb, a["id"], til_iso(start), serie)
    k = sb.okt(o["id"])["klokke"]
    assert k["snittpuls"] == 110 and k["puls"] and len(k["sett_tider"]) == 3
    pa = k["analyse"]["per_ovelse"]["benkpress"]
    assert pa["topp"] == 145 and pa["foer_neste"] == 100
    import ai
    assert "PULS FRA KLOKKA" in ai.oppgave_oppsummering(sb, o["id"], [])


def test_les_tcx_uten_gps():
    import kropp
    punkter = "".join(f'<Trackpoint><Time>2026-11-09T10:00:{i:02d}Z</Time><Position><LatitudeDegrees>59.8</LatitudeDegrees></Position>'
                      f'<HeartRateBpm><Value>{100 + i}</Value></HeartRateBpm></Trackpoint>' for i in range(12))
    tcx = ('<TrainingCenterDatabase xmlns="http://www.garmin.com/xmlschemas/TrainingCenterDatabase/v2"><Activities><Activity><Lap><Track>'
           + punkter + '</Track></Lap></Activity></Activities></TrainingCenterDatabase>')
    start, serie = kropp.les_tcx(tcx)
    assert start.startswith("2026-11-09T10:00:00") and serie[0] == [0, 102, None] and len(serie) == 3
    assert all(len(p) == 3 for p in serie)


def test_garmin_styrkeokter(sb, monkeypatch):
    import asyncio
    import types
    if "aiohttp" not in sys.modules:
        fake = types.ModuleType("aiohttp")
        fake.ClientTimeout = lambda **k: None
        fake.ClientError = Exception
        fake.ClientSession = object
        sys.modules["aiohttp"] = fake
    import garmin
    import ha
    from ovelser import BIBLIOTEK as BIB
    pid = sb.profiler()[0]["id"]
    prog = sb.lagre_program(pid, sb.foreslaa_program(pid), kilde="mal")
    sb.lagre_startvekter(pid, {"knebøy-stang": 80, "benkpress": 62.5}, "manuell")
    sb.lagre_profil({"koblinger": {"aktiviteter": "sensor.x"}, "garmin_eksport": {"styrke": True}}, pid)
    k = ha.HAKobling(sb)
    k.aktiv = True
    kall = []

    async def fake_tjeneste(domene, tjeneste, data, svar=False):
        kall.append((tjeneste, data))
        return {"workout_id": 500 + len(kall), "schedule_id": 900 + len(kall)} if svar else None
    monkeypatch.setattr(k, "_tjeneste", fake_tjeneste)
    r = asyncio.run(k.synk_garmin_styrke(sb.profil(pid)))
    assert r["nye"] == len(prog["dager"]) and r["planlagt"]
    w = next(c[1]["workout"] for c in kall if c[0] == "create_workout")
    steg = w["workoutSegments"][0]["workoutSteps"]
    assert w["sportType"]["sportTypeKey"] == "strength_training"
    oppv = [s for s in steg if s["type"] == "ExecutableStepDTO" and s["stepType"]["stepTypeKey"] == "warmup"]
    assert oppv and oppv[0]["exerciseName"] == "BARBELL_BACK_SQUAT"
    gruppe = next(s for s in steg if s["type"] == "RepeatGroupDTO")
    assert gruppe["workoutSteps"][0]["weightValue"] == 80 and gruppe["workoutSteps"][1]["stepType"]["stepTypeKey"] == "rest"
    assert sum(1 for c in kall if c[0] == "schedule_workout") == 1
    # ingen endring -> ingen kall
    kall.clear()
    asyncio.run(k.synk_garmin_styrke(sb.profil(pid)))
    assert not kall
    # etter en økt endres vekten -> update_workout, og neste økt planlegges på nytt
    o = sb.start_okt(pid, prog["dager"][0]["id"])
    for _ in range(3):
        sb.logg_sett(o["id"], {"okt_ovelse_id": o["ovelser"][0]["id"], "vekt": 80, "reps": o["ovelser"][0]["reps_maks"]})
    sb.avslutt_okt(o["id"], {})
    kall.clear()
    asyncio.run(k.synk_garmin_styrke(sb.profil(pid)))
    typer = [c[0] for c in kall]
    assert "update_workout" in typer and "unschedule_workout" in typer and "schedule_workout" in typer
    # alle øvelser har gyldig kategori
    for o in BIB:
        assert garmin.kategori(o)[0], o["nokkel"]
    # slått av -> alt slettes
    sb.lagre_profil({"garmin_eksport": {"styrke": False}}, pid)
    kall.clear()
    r = asyncio.run(k.synk_garmin_styrke(sb.profil(pid)))
    assert r["fjernet"] == len(prog["dager"]) and not sb.db.alle("SELECT * FROM garmin_styrke")


def test_dagsform(sb):
    from datetime import date, timedelta
    import dagsform
    import kropp
    pid = sb.profiler()[0]["id"]
    assert dagsform.status(sb, pid) is None
    i_dag = date.fromisoformat(kropp.lokal_dato(sb))
    for i in range(1, 10):
        kropp.lagre_maaling(sb, pid, "hrv", 45, (i_dag - timedelta(days=i)).isoformat(), "ha")
        kropp.lagre_maaling(sb, pid, "hvilepuls", 55, (i_dag - timedelta(days=i)).isoformat(), "ha")
    kropp.lagre_maaling(sb, pid, "beredskap", 85, kilde="ha")
    kropp.lagre_maaling(sb, pid, "sovn_score", 85, kilde="ha")
    assert dagsform.status(sb, pid)["niva"] == "god"
    kropp.lagre_maaling(sb, pid, "beredskap", 30, kilde="ha")
    kropp.lagre_maaling(sb, pid, "sovn_score", 50, kilde="ha")
    kropp.lagre_maaling(sb, pid, "hrv", 30, kilde="ha")
    s = dagsform.status(sb, pid)
    assert s["niva"] == "lav" and any("HRV" in g for g in s["grunner"])
    assert "DAGSFORM" in dagsform.ai_tekst(sb, pid)
    # lettere økt
    prog = sb.lagre_program(pid, sb.foreslaa_program(pid), kilde="mal")
    o = sb.start_okt(pid, prog["dager"][0]["id"])
    for_ = o["ovelser"][1]["sett_plan"]
    o2 = sb.lettere_okt(o["id"])
    assert o2["ovelser"][1]["sett_plan"] < for_


def test_ukeplan_rundt_kalender(sb):
    from datetime import timedelta
    import ukeplan
    pid = sb.profiler()[0]["id"]
    sb.lagre_profil({"dager_per_uke": 3}, pid)
    prog = sb.lagre_program(pid, sb.foreslaa_program(pid), kilde="mal")
    i_dag = sb.lokal(sb_naa()).date()
    reise_fra, reise_til = i_dag + timedelta(days=1), i_dag + timedelta(days=3)
    sb.db.lagre_innstilling(f"kalender-{pid}", {"tid": "x", "hendelser": [
        {"kalender": "calendar.tripit", "tittel": "Reise - Bergen", "start": reise_fra.isoformat(), "slutt": reise_til.isoformat(),
         "heldag": True, "sted": "Bergen"},
        {"kalender": "calendar.jobb", "tittel": "Vakt", "start": f"{(i_dag + timedelta(days=4)).isoformat()}T07:00:00+01:00",
         "slutt": f"{(i_dag + timedelta(days=4)).isoformat()}T19:00:00+01:00", "heldag": False, "sted": ""}]})
    plan = ukeplan.lokal_plan(sb, pid)
    styrke = [d for d in plan["dager"] if any(o["type"] == "styrke" for o in d["okter"])]
    datoer = {d["dato"] for d in styrke}
    assert len(styrke) == 3
    assert reise_fra.isoformat() not in datoer and (reise_fra + timedelta(days=1)).isoformat() not in datoer
    assert (i_dag + timedelta(days=4)).isoformat() not in datoer
    assert styrke[0]["okter"][0]["dag_id"] == sb.neste_dag(pid)["id"]
    assert "BORTE" in ukeplan.kalender_tekst(sb, pid)
    # AI-plan valideres mot programmet
    ai_plan = ukeplan.valider_ai_plan(sb, pid, {"oppsummering": "ok", "dager": [
        {"dato": i_dag.isoformat(), "okter": [{"type": "styrke", "dag_id": prog["dager"][0]["id"]}, {"type": "styrke", "dag_id": 99999}]}]})
    assert len(ai_plan["dager"][0]["okter"]) == 1 and len(ai_plan["dager"]) == 7
    ukeplan.lagre(sb, pid, ai_plan)
    assert ukeplan.hent(sb, pid)["kilde"] == "ai"
    assert ukeplan.neste_styrkedato(sb, pid, prog["dager"][0]["id"]) == i_dag.isoformat()
