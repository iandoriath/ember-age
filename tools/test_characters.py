import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
spec = importlib.util.spec_from_file_location("bc", ROOT / "tools/build-characters.py")
bc = importlib.util.module_from_spec(spec)
spec.loader.exec_module(bc)

SAMPLE = {
    "Name": "Tést Pilot", "Characteristics": {"Brawn": "2", "Agility": "3", "Intellect": "2", "Cunning": "2", "Willpower": "2", "Presence": "3"},
    "Species": {"Name": "Human", "SkillModifiers": {"Key": "MECH", "RankStart": "1", "RankLimit": "2"}, "OptionChoices": []},
    "Career": {"Name": "Smuggler"}, "Specializations": [{"Name": "Pilot"}],
    "CareerSkills": ["Piloting (Space)", "Charm"], "SpecSkills": ["Gunnery"], "CareerRanks": ["Piloting (Space)", "Piloting (Space)"], "SpecRanks": ["Gunnery"],
    "Skills": [{"Key": "PILOTSP", "skill": "Piloting (Space)", "characteristic": "Agility", "type": "General"},
               {"Key": "GUNN", "skill": "Gunnery", "characteristic": "Agility", "type": "Combat"},
               {"Key": "MECH", "skill": "Mechanics", "characteristic": "Intellect", "type": "General"},
               {"Key": "LORE", "skill": "Lore", "characteristic": "Intellect", "type": "Knowledge"}],
    "Weapons": [{"Key": "BLASTPST", "Name": "Blaster Pistol", "SkillKey": "RANGLT", "Damage": "6", "Crit": "3", "Range": "Medium", "Qualities": [{"Key": "STUNSETTING"}], "Equipped": True},
                {"Key": "UNARMED", "Name": "Unarmed", "DamageAdd": 0, "Crit": 5, "SkillKey": "BRAWL", "Range": "Engaged", "Qualities": [{"Key": "KNOCKDOWN"}]}],
    "UsedQualities": [{"Key": "STUNSETTING", "Name": "Stun Setting Quality"}, {"Key": "KNOCKDOWN", "Name": "Knockdown Quality"}],
    "Armor": [], "Gear": [], "Vehicles": [], "BoughtTalents": [{"key": "GRIT", "data": {"Name": "Grit", "Description": "Gain +1 strain threshold", "ActivationValue": "Passive"}, "count": "1"},
                                                             {"key": "DEDI", "data": {"Name": "Dedication"}, "count": "0"}],
    "Obligations": [{"Name": "Debt", "Text": "Ship lease", "Toggle": True, "Total": "15"}], "Duties": [], "Motivations": [],
    "Morality": {"Toggle": False, "Score": "50"}, "Wounds": "12", "Strain": "13", "Soak": "2", "Defense": {"Ranged": "0", "Melee": "0"},
    "EncumbranceCurrent": "3", "ForceRating": "0", "Credits": "100", "Modifiers": {"Skills": {}},
}


def test_ranks_pools_and_slug():
    c = bc.normalize(SAMPLE)
    assert c["slug"] == "test-pilot"
    sk = {s["name"]: s for s in c["skills"]}
    assert sk["Piloting (Space)"]["rank"] == 2 and sk["Piloting (Space)"]["career"]
    assert (sk["Piloting (Space)"]["proficiency"], sk["Piloting (Space)"]["ability"]) == (2, 1)  # Agility 3, rank 2
    assert sk["Gunnery"]["rank"] == 1 and sk["Mechanics"]["rank"] == 1 and not sk["Mechanics"]["career"]
    assert sk["Knowledge (Lore)"]["rank"] == 0 and sk["Knowledge (Lore)"]["ability"] == 2
    assert c["encumbrance"]["threshold"] == 7 and c["wounds"] == 12


def test_weapons_talents_and_obligation():
    c = bc.normalize(SAMPLE)
    w = {x["name"]: x for x in c["weapons"]}
    assert w["Blaster Pistol"]["qualities"] == ["Stun Setting"] and w["Blaster Pistol"]["skill"] == "Ranged (Light)"
    assert w["Unarmed"]["damage"] == "2" and w["Unarmed"]["equipped"]
    assert [t["name"] for t in c["talents"]] == ["Grit"]  # zero-count tree nodes dropped
    assert c["obligations"] == [{"type": "Debt", "text": "Ship lease", "total": 15}]


def test_sheet_and_markup():
    c = bc.normalize(SAMPLE)
    html = bc.sheet_html(c)
    assert "TÉST PILOT" in html and 'class="d pr"' in html
    assert bc.fmt("Hard ([DI][DI][DI]) check; [B]bold[b] <x>") == 'Hard (<span class="d di"></span><span class="d di"></span><span class="d di"></span>) check; <b>bold</b> &lt;x&gt;'


def test_real_exports_build_and_committed_roster_is_fresh():
    files = sorted((ROOT / "hyperdrive").glob("*.json"))
    if not files:
        return
    crew = sorted((bc.normalize(json.loads(f.read_text(encoding="utf-8"))) for f in files), key=lambda c: c["name"])
    assert json.loads((ROOT / "docs/setting/characters.json").read_text(encoding="utf-8")) == crew
    for c in crew:
        assert (ROOT / "player-aids/characters" / f"{c['slug']}.html").read_text(encoding="utf-8") == bc.sheet_html(c)


def test_ichor_blade_applies_to_the_vibroknife():
    d = json.loads(json.dumps(SAMPLE))
    d["Weapons"] = [{"Key": "VIBKN", "Name": "Vibroknife", "SkillKey": "MELEE", "DamageAdd": 1, "Crit": 2, "Range": "Engaged",
                     "Qualities": [{"Key": "PIERCE", "Count": "2"}, {"Key": "VICIOUS", "Count": "1"}]}] + d["Weapons"]
    d["BoughtTalents"] = list(d["BoughtTalents"]) + [
        {"key": "ICHBLADECOTR", "data": {"Name": "Ichor Blade"}, "count": 1},
        {"key": "ICHORBI", "data": {"Name": "Ichor Blade (Improved)"}, "count": 1},
        {"key": "GRIT2", "data": {"Name": "Grit"}, "count": 0}]
    c = bc.normalize(d, "sample")
    vk = next(w for w in c["weapons"] if w["name"] == "Vibroknife")
    assert vk["crit"] == "1", vk
    assert vk["damage"] == str(2 + 1 + 2), vk       # Brawn 2 + DamageAdd 1 + Improved 2
    for q in ("Cortosis", "Sunder", "Defensive 1", "Pierce 2"):
        assert any(x.startswith(q) for x in vk["qualities"]), (q, vk["qualities"])
    assert any("Ichor Blade" in x for x in vk["qualities"])
    blaster = next(w for w in c["weapons"] if w["name"] == "Blaster Pistol")
    assert not any("Ichor" in x for x in blaster["qualities"])          # only the chosen weapon changes
    d2 = json.loads(json.dumps(SAMPLE))                                  # no talent -> no change
    c2 = bc.normalize(d2, "sample")
    assert not any("Ichor" in q for w in c2["weapons"] for q in w["qualities"])

test_ichor_blade_applies_to_the_vibroknife()
print("ichor test ok")


def test_ichor_blade_count_zero_is_not_bought():
    d = json.loads(json.dumps(SAMPLE))
    d["Weapons"] = [{"Key": "VIBKN", "Name": "Vibroknife", "SkillKey": "MELEE", "DamageAdd": 1, "Crit": 2, "Range": "Engaged",
                     "Qualities": [{"Key": "PIERCE", "Count": "2"}, {"Key": "VICIOUS", "Count": "1"}]}] + d["Weapons"]
    d["BoughtTalents"] = list(d["BoughtTalents"]) + [
        {"key": "ICHBLADECOTR", "data": {"Name": "Ichor Blade"}, "count": 1},
        {"key": "ICHORBI", "data": {"Name": "Ichor Blade (Improved)"}, "count": 0}]   # touched, refunded
    vk = next(w for w in bc.normalize(d, "sample")["weapons"] if w["name"] == "Vibroknife")
    assert vk["crit"] == "1" and any(q == "Cortosis" for q in vk["qualities"]), vk       # basic applies
    assert vk["damage"] == "3", vk                                                        # Brawn 2 + 1, no Improved +2
    assert not any("Sunder" in q or "Defensive" in q for q in vk["qualities"]), vk        # Improved does not
    assert any(x == "Ichor Blade" for x in vk["qualities"]), vk                           # tag without "(Improved)"
    d2 = json.loads(json.dumps(SAMPLE))
    d2["BoughtTalents"] = list(d2["BoughtTalents"]) + [{"key": "ICHBLADECOTR", "data": {}, "count": 0}]
    assert not any("Ichor" in q for w in bc.normalize(d2, "s")["weapons"] for q in w["qualities"])

test_ichor_blade_count_zero_is_not_bought()
print("count-gate test ok")
