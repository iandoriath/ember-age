#!/usr/bin/env python3
"""Turn Hyperdrive character-creator exports (hyperdrive/*.json) into table-ready pieces.

Outputs:
  docs/setting/characters.json              — normalized crew roster (the GM screen embeds it as its Crew tab)
  player-aids/characters/<slug>.html        — printable player character sheet, one per export
  player-aids/characters/index.html         — the crew list players land on

Hyperdrive stores skill ranks indirectly (species start rank, free career/spec ranks, purchased
ranks); this script recomputes them and renders the dice pool per skill. Re-run after every
export: `make characters`.
"""
import html
import json
import re
import sys
import unicodedata
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "hyperdrive"
OUT_JSON = ROOT / "docs/setting/characters.json"
OUT_DIR = ROOT / "player-aids/characters"

CHARS = ["Brawn", "Agility", "Intellect", "Cunning", "Willpower", "Presence"]
SKILL_BY_KEY = {"ASTRO": "Astrogation", "ATHL": "Athletics", "BRAWL": "Brawl", "CHARM": "Charm", "COERC": "Coercion",
                "COMP": "Computers", "COOL": "Cool", "COORD": "Coordination", "DECEP": "Deception", "DISC": "Discipline",
                "GUNN": "Gunnery", "LEAD": "Leadership", "LTSABER": "Lightsaber", "MECH": "Mechanics", "MED": "Medicine",
                "MELEE": "Melee", "NEG": "Negotiation", "PERC": "Perception", "PILOTPL": "Piloting (Planetary)",
                "PILOTSP": "Piloting (Space)", "RANGHVY": "Ranged (Heavy)", "RANGLT": "Ranged (Light)", "RESIL": "Resilience",
                "SKUL": "Skulduggery", "STEAL": "Stealth", "SW": "Streetwise", "SURV": "Survival", "VIGIL": "Vigilance",
                "CORE": "Core Worlds", "EDU": "Education", "LORE": "Lore", "OUT": "Outer Rim", "UND": "Underworld",
                "WARF": "Warfare", "XEN": "Xenology"}
KNOWLEDGE = {"Core Worlds", "Education", "Lore", "Outer Rim", "Underworld", "Warfare", "Xenology"}
VEHICLE_WEAPONS = {"LASERMED": "Medium laser cannon", "LASERLT": "Light laser cannon", "LASERHVY": "Heavy laser cannon",
                   "LASERQUAD": "Quad laser cannon", "IONLT": "Light ion cannon", "IONMED": "Medium ion cannon",
                   "CONCMIS": "Concussion missile launcher", "PROTORP": "Proton torpedo launcher", "BLASTLT": "Light blaster cannon",
                   "BLASTHVY": "Heavy blaster cannon", "TURBOLT": "Light turbolaser", "AUTOBLAST": "Auto-blaster"}


def num(x, default=0):
    try:
        return int(float(x))
    except (TypeError, ValueError):
        return default


def as_list(x) -> list:
    """Hyperdrive's XML-derived JSON collapses a one-item collection into a bare dict (a Human's
    single OptionChoices entry, a lone weapon quality, one obligation); always iterate a list."""
    if x is None:
        return []
    return x if isinstance(x, list) else [x]


def slugify(name: str) -> str:
    ascii_name = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode()
    s = re.sub(r"[^a-z0-9]+", "-", ascii_name.lower()).strip("-")
    return s or "character"


def quality_name(q: dict, used: dict) -> str:
    key = q.get("Key", "")
    label = used.get(key, key.title())
    label = label.replace(" Quality", "")
    count = q.get("Count")
    return f"{label} {count}" if count else label


def skill_ranks(d: dict) -> dict:
    ranks = {}
    sm = d.get("Species", {}).get("SkillModifiers") or {}
    if isinstance(sm, dict) and sm.get("Key"):
        ranks[SKILL_BY_KEY.get(sm["Key"], sm["Key"])] = num(sm.get("RankStart"))
    for name in as_list(d.get("CareerRanks")) + as_list(d.get("SpecRanks")):
        ranks[name] = ranks.get(name, 0) + 1
    for name, r in (d.get("Modifiers", {}).get("Skills") or {}).items():
        ranks[SKILL_BY_KEY.get(name, name)] = ranks.get(SKILL_BY_KEY.get(name, name), 0) + num(r)
    for s in as_list(d.get("Skills")):
        for k in ("rank", "Rank", "ranks", "Ranks"):
            if k in s:
                ranks[s["skill"]] = ranks.get(s["skill"], 0) + num(s[k])
    return ranks


def normalize(d: dict, stem: str = "") -> dict:
    chars = {c: num(d["Characteristics"].get(c)) for c in CHARS}
    career_skills = set(as_list(d.get("CareerSkills"))) | set(as_list(d.get("SpecSkills"))) | set(as_list(d.get("ExtraCareerSkills")))
    ranks = skill_ranks(d)
    skills = []
    for s in as_list(d.get("Skills")):
        name, char = s["skill"], s["characteristic"]
        r, c = ranks.get(name, 0), chars.get(char, 0)
        skills.append({"name": f"Knowledge ({name})" if name in KNOWLEDGE else name, "characteristic": char, "rank": r,
                       "career": name in career_skills, "proficiency": min(r, c), "ability": max(r, c) - min(r, c),
                       "type": s.get("type", "General")})
    used_q = {q["Key"]: q["Name"] for q in as_list(d.get("UsedQualities")) if isinstance(q, dict)}
    weapons = []
    for w in as_list(d.get("Weapons")):
        skill_key = w.get("SkillKey", "")
        skill = SKILL_BY_KEY.get(skill_key, skill_key)
        if w.get("Key") == "UNARMED":
            dmg = f"{chars['Brawn'] + num(w.get('DamageAdd'))}"
        elif skill in ("Brawl", "Melee", "Lightsaber") and "DamageAdd" in w:
            dmg = f"{chars['Brawn'] + num(w.get('DamageAdd'))}"
        else:
            dmg = str(w.get("Damage", "—"))
        weapons.append({"name": w.get("Name", "?"), "skill": skill, "damage": dmg, "crit": str(w.get("Crit", "—")),
                        "range": w.get("Range", "—"), "qualities": [quality_name(q, used_q) for q in as_list(w.get("Qualities")) if isinstance(q, dict)],
                        "notes": (w.get("BaseMods") or {}).get("MiscDesc", "") if isinstance(w.get("BaseMods"), dict) else "",
                        "equipped": bool(w.get("Equipped")) or w.get("Key") == "UNARMED"})
    armor = [{"name": a.get("Name", "?"), "soak": num(a.get("Soak")), "defense": num(a.get("Defense")), "encumbrance": num(a.get("Encumbrance")),
              "equipped": bool(a.get("Equipped"))} for a in as_list(d.get("Armor"))]
    gear = []
    for g in as_list(d.get("Gear")):
        mods = as_list(g.get("BaseMods"))
        gear.append({"name": g.get("Name", "?"), "quantity": num(g.get("Quantity"), 1), "type": g.get("Type", ""),
                     "encumbrance": num(g.get("Encumbrance")), "notes": " ".join(m.get("MiscDesc", "") for m in mods if isinstance(m, dict)).strip()})
    vehicles = []
    for v in as_list(d.get("Vehicles")):
        weps = {}
        for vw in as_list(v.get("VehicleWeapons")):
            label = VEHICLE_WEAPONS.get(vw.get("Key"), vw.get("Key", "?")) + (" (turret)" if vw.get("Turret") else "")
            weps[label] = weps.get(label, 0) + 1
        vehicles.append({"name": v.get("Name", "?"), "type": v.get("Type", ""), "silhouette": num(v.get("Silhouette")), "speed": num(v.get("Speed")),
                         "handling": num(v.get("Handling")), "def_fore": num(v.get("DefFore")), "def_aft": num(v.get("DefAft")),
                         "armor": num(v.get("Armor")), "hull": num(v.get("HullTrauma")), "strain": num(v.get("SystemStrain")),
                         "hyperdrive": f"Class {v.get('HyperdrivePrimary', '?')} (backup {v.get('HyperdriveBackup', '?')})",
                         "crew": v.get("Crew", ""), "passengers": num(v.get("Passengers")), "encumbrance": num(v.get("EncumbranceCapacity")),
                         "consumables": v.get("Consumables", ""), "weapons": [f"{n}× {k}" if n > 1 else k for k, n in weps.items()]})
    talents = [{"name": t["data"].get("Name", t["key"]), "count": num(t.get("count")), "activation": t["data"].get("ActivationValue", ""),
                "description": t["data"].get("Description", "")} for t in as_list(d.get("BoughtTalents")) if isinstance(t, dict) and num(t.get("count")) > 0]
    species = d.get("Species", {})
    abilities = [{"name": o["Options"].get("Name", ""), "description": o["Options"].get("Description", "")}
                 for o in as_list(species.get("OptionChoices")) if isinstance(o, dict) and isinstance(o.get("Options"), dict)]
    obligations = [{"type": o.get("Name", ""), "text": o.get("Text", ""), "total": num(o.get("Total"))} for o in as_list(d.get("Obligations")) if isinstance(o, dict) and o.get("Toggle") and o.get("Name")]
    duties = [{"type": o.get("Name", ""), "text": o.get("Text", ""), "total": num(o.get("Total"))} for o in as_list(d.get("Duties")) if isinstance(o, dict) and o.get("Toggle") and o.get("Name")]
    motivation = None
    for m in as_list(d.get("Motivations")):
        sm = m.get("SpecificMotivation") or {}
        if sm.get("Name"):
            motivation = f"{m.get('Motivation', {}).get('Name', '')}: {sm['Name']}".strip(": ")
    morality = num(d.get("Morality", {}).get("Score"), 50) if d.get("Morality", {}).get("Toggle") else None
    name = d.get("Name") or stem or "Unnamed"   # a nameless draft is labeled by its export file (Dathomiri.json -> "Dathomiri")
    return {
        "slug": slugify(name), "name": name, "species": species.get("Name", ""), "species_abilities": abilities,
        "career": d.get("Career", {}).get("Name", ""), "specializations": [s.get("Name", "") for s in as_list(d.get("Specializations")) if isinstance(s, dict)],
        "characteristics": chars, "wounds": num(d.get("Wounds")), "strain": num(d.get("Strain")), "soak": num(d.get("Soak")),
        "defense": {"ranged": num(d.get("Defense", {}).get("Ranged")), "melee": num(d.get("Defense", {}).get("Melee"))},
        "encumbrance": {"threshold": 5 + chars["Brawn"], "current": num(d.get("EncumbranceCurrent"))},
        "force_rating": num(d.get("ForceRating")), "morality": morality, "credits": num(d.get("Credits")),
        "skills": skills, "talents": talents, "weapons": weapons, "armor": armor, "gear": gear, "vehicles": vehicles,
        "obligations": obligations, "duties": duties, "motivation": motivation, "background": (d.get("Background") or {}).get("Text", ""),
    }

# --------------------------------------------------------------------------- HTML


def e(x) -> str:
    return html.escape(str(x))


TOKEN_CHIPS = {"SE": "se", "BO": "bo", "DI": "di", "CH": "ch", "AB": "ab", "PR": "pr", "FO": "f"}
TOKEN_WORDS = {"AD": "Advantage", "SU": "Success", "TR": "Triumph", "TH": "Threat", "FA": "Failure", "DE": "Despair",
               "LI": "light side", "DA": "dark side", "FP": "Force point"}


def fmt(x) -> str:
    """Escape text, then turn Hyperdrive's [SE]/[DI]/[AD]/[B]…[b] markup into dice chips, symbol words and bold."""
    s = html.escape(str(x))
    for tok, cls in TOKEN_CHIPS.items():
        s = s.replace(f"[{tok}]", f'<span class="d {cls}"></span>')
    for tok, word in TOKEN_WORDS.items():
        s = s.replace(f"[{tok}]", f'<span class="sy {"bad" if tok in ("TH", "FA", "DE", "DA") else "good"}">{word}</span>')
    s = re.sub(r"\[B\](.*?)\[b\]", r"<b>\1</b>", s)
    return s


def dice(sk: dict) -> str:
    return '<span class="d pr"></span>' * sk["proficiency"] + '<span class="d ab"></span>' * sk["ability"]


def sheet_html(c: dict) -> str:
    spec = " / ".join(s for s in c["specializations"] if s)
    chars = "".join(f'<div class="char"><b>{v}</b><span>{k}</span></div>' for k, v in c["characteristics"].items())
    def skill_rows(kind):
        rows = [s for s in c["skills"] if s["type"] == kind] if kind != "Knowledge" else [s for s in c["skills"] if s["name"].startswith("Knowledge")]
        if kind == "General":
            rows = [s for s in rows if not s["name"].startswith("Knowledge")]
        return "".join(f'<tr class="{"ranked" if s["rank"] else ""}"><td>{"●" if s["career"] else ""}</td><td>{e(s["name"])}</td>'
                       f'<td class="c">{e(s["characteristic"][:3])}</td><td class="c">{s["rank"]}</td><td>{dice(s)}</td></tr>' for s in rows)
    talents = "".join(f'<li><b>{e(t["name"])}{" ×" + str(t["count"]) if t["count"] > 1 else ""}</b> <i>({e(t["activation"])})</i> {fmt(t["description"])}</li>' for t in c["talents"])
    abilities = "".join(f'<li><b>{e(a["name"])}</b> {fmt(a["description"])}</li>' for a in c["species_abilities"])
    weapons = "".join(f'<tr><td><b>{e(w["name"])}</b>{" <i>(not equipped)</i>" if not w["equipped"] else ""}</td><td>{e(w["skill"])}</td><td class="c">{e(w["damage"])}</td>'
                      f'<td class="c">{e(w["crit"])}</td><td>{e(w["range"])}</td><td>{e(", ".join(w["qualities"]))}{(" — " + fmt(w["notes"])) if w["notes"] else ""}</td></tr>' for w in c["weapons"])
    armor = "".join(f'<tr><td><b>{e(a["name"])}</b></td><td class="c">+{a["soak"]}</td><td class="c">{a["defense"] or "—"}</td><td class="c">{a["encumbrance"]}</td></tr>' for a in c["armor"])
    gear = "".join(f'<li><b>{e(g["name"])}</b>{" ×" + str(g["quantity"]) if g["quantity"] > 1 else ""}{(" — " + fmt(g["notes"])) if g["notes"] else ""}</li>' for g in c["gear"])
    ob = "".join(f'<li><b>{e(o["type"])} {o["total"]}</b>{(" — " + e(o["text"])) if o["text"] else ""}</li>' for o in c["obligations"]) or "<li>—</li>"
    duty = "".join(f'<li><b>{e(o["type"])} {o["total"]}</b>{(" — " + e(o["text"])) if o["text"] else ""}</li>' for o in c["duties"])
    ships = "".join(f'''<div class="ship"><b>{e(v["name"])}</b> <span class="muted">{e(v["type"])} · Sil {v["silhouette"]} · Speed {v["speed"]} · Handling {v["handling"]:+d}</span>
      <div class="shipstats"><span>Def <b>{v["def_fore"]}/{v["def_aft"]}</b></span><span>Armor <b>{v["armor"]}</b></span><span>Hull <b>{v["hull"]}</b></span><span>Strain <b>{v["strain"]}</b></span><span>{e(v["hyperdrive"])}</span></div>
      <div class="muted small">{e(v["crew"])} · {v["passengers"]} passengers · enc {v["encumbrance"]} · consumables {e(v["consumables"])}{" · " + e("; ".join(v["weapons"])) if v["weapons"] else ""}</div></div>''' for v in c["vehicles"])
    force = f'<span>Force Rating <b>{c["force_rating"]}</b></span>' if c["force_rating"] else ""
    morality = f'<span>Morality <b>{c["morality"]}</b></span>' if c["morality"] is not None else ""
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{e(c["name"])} — character sheet</title>
<link rel="stylesheet" href="../sheet-style.css">
<style>
  @page {{ size: Letter; margin: 9mm 9mm; }}
  .sheet{{max-width:8.5in;padding:14px 16px 10px}}
  .masthead h1{{white-space:nowrap}}
  .top{{display:flex;gap:8pt;align-items:stretch;margin:0 0 6pt}}
  .chars{{display:flex;gap:4pt;flex:1}}
  .char{{flex:1;border:1px solid var(--line);background:var(--wash);text-align:center;padding:3pt 2pt}}
  .char b{{display:block;font:800 15pt/1 var(--head);color:var(--ember)}}
  .char span{{font:700 6.4pt var(--head);text-transform:uppercase;letter-spacing:.08em;color:var(--gold)}}
  .derived{{display:flex;gap:4pt}}
  .derived div{{border:1px solid var(--line);text-align:center;padding:3pt 6pt;min-width:46pt}}
  .derived b{{display:block;font:800 13pt/1 var(--head);color:var(--ink)}}
  .derived span{{font:700 6.2pt var(--head);text-transform:uppercase;letter-spacing:.06em;color:var(--gold)}}
  table.sk td{{padding:.9pt 3pt}} table.sk tr.ranked td{{background:#fbf7ee}} table.sk td:first-child{{color:var(--ember);text-align:center;width:8pt}}
  .ship{{border:1px solid var(--line);padding:3pt 5pt;margin:2pt 0}}
  .shipstats{{display:flex;gap:8pt;font-size:7.8pt;margin:1.5pt 0}} .shipstats b{{color:var(--ember)}}
  .muted{{color:var(--dim)}} .small{{font-size:7.4pt}}
  .meta{{display:flex;gap:10pt;flex-wrap:wrap;font-size:8pt;margin:0 0 4pt}} .meta b{{color:var(--ember)}}
  .sec ul{{margin-left:9pt}} .sec li{{margin:1pt 0;font-size:8pt}}
</style>
</head>
<body>
<div class="sheet">
<div class="masthead">
  <h1>{e(c["name"]).upper()}</h1>
  <div class="sub">{e(c["species"])} · {e(c["career"])}{(" — " + e(spec)) if spec else ""}</div>
  <div class="spacer"></div>
  <div class="era">The Ember Age · character sheet</div>
</div>

<div class="top">
  <div class="chars">{chars}</div>
  <div class="derived">
    <div><b>{c["wounds"]}</b><span>Wounds</span></div>
    <div><b>{c["strain"]}</b><span>Strain</span></div>
    <div><b>{c["soak"]}</b><span>Soak</span></div>
    <div><b>{c["defense"]["ranged"]}/{c["defense"]["melee"]}</b><span>Def R/M</span></div>
    <div><b>{c["encumbrance"]["threshold"]}</b><span>Enc</span></div>
  </div>
</div>
<div class="meta"><span>Credits <b>{c["credits"]}</b></span>{force}{morality}<span>Motivation <b>{e(c["motivation"] or "—")}</b></span><span>Carrying <b>{c["encumbrance"]["current"]}</b> / {c["encumbrance"]["threshold"]}</span></div>

<div class="cols2">

<div class="sec">
<h2><span class="n">◆</span> Skills <span class="muted" style="font:italic 7pt var(--body);text-transform:none;letter-spacing:0">● = career skill · yellow <span class="d pr"></span> proficiency, green <span class="d ab"></span> ability</span></h2>
<table class="sk"><tr><th></th><th>General</th><th class="c">Char</th><th class="c">Rk</th><th>Pool</th></tr>{skill_rows("General")}</table>
<table class="sk"><tr><th></th><th>Combat</th><th class="c">Char</th><th class="c">Rk</th><th>Pool</th></tr>{skill_rows("Combat")}</table>
<table class="sk"><tr><th></th><th>Knowledge</th><th class="c">Char</th><th class="c">Rk</th><th>Pool</th></tr>{skill_rows("Knowledge")}</table>
</div>

<div class="sec">
<h2><span class="n">◆</span> Talents</h2>
<ul class="tight">{talents or "<li>—</li>"}</ul>
</div>

<div class="sec">
<h2><span class="n">◆</span> Species abilities — {e(c["species"])}</h2>
<ul class="tight">{abilities or "<li>—</li>"}</ul>
</div>

<div class="sec">
<h2><span class="n">◆</span> Weapons</h2>
<table><tr><th>Weapon</th><th>Skill</th><th class="c">Dmg</th><th class="c">Crit</th><th>Range</th><th>Qualities</th></tr>{weapons or "<tr><td colspan=6>—</td></tr>"}</table>
</div>

<div class="sec">
<h2><span class="n">◆</span> Armor &amp; gear</h2>
<table><tr><th>Armor</th><th class="c">Soak</th><th class="c">Def</th><th class="c">Enc</th></tr>{armor or "<tr><td colspan=4>—</td></tr>"}</table>
<ul class="tight">{gear or "<li>—</li>"}</ul>
</div>

<div class="sec">
<h2><span class="n">◆</span> Obligation{" &amp; Duty" if duty else ""}</h2>
<ul class="tight">{ob}{duty}</ul>
</div>

{('<div class="sec"><h2><span class="n">◆</span> Ship</h2>' + ships + '</div>') if ships else ""}

{('<div class="sec"><h2><span class="n">◆</span> Background</h2><p>' + e(c["background"]) + '</p></div>') if c["background"] else ""}

</div>
<div class="foot"><span>Built from the Hyperdrive export · numbers as exported, ranks recomputed (species + career + specialization + purchases).</span><span>The Ember Age</span></div>
</div>
</body>
</html>
"""


def index_html(crew: list) -> str:
    items = "".join(f'<li><a class="card" href="{e(c["slug"])}.html">{e(c["name"])}<small>{e(c["species"])} · {e(c["career"])}{(" — " + e(" / ".join(s for s in c["specializations"] if s))) if any(c["specializations"]) else ""}</small></a></li>' for c in crew)
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>The Ember Age — crew</title>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Rajdhani:wght@600;700&display=swap">
<style>
  :root{{--bg:#050a10;--ink:#d7ecf8;--dim:#7fa3bb;--holo:#5fc3ff;--holo-dim:#2a5f80;--ember:#e07b39;--gold:#ffb454}}
  *{{box-sizing:border-box}}html,body{{margin:0}}body{{background:var(--bg);color:var(--ink);font:18px/1.5 system-ui,"Segoe UI",Roboto,sans-serif;padding:2.2rem 1.4rem 4rem;max-width:40rem;margin:0 auto}}
  h1{{font:700 1.25rem/1.2 Rajdhani,system-ui,sans-serif;letter-spacing:.18em;text-transform:uppercase;color:var(--holo);margin:0}}
  .sub{{color:var(--dim);margin:.2rem 0 1.4rem;font-size:.85rem;letter-spacing:.2em;text-transform:uppercase}}
  ul{{list-style:none;padding:0;margin:0}}a.card{{display:block;padding:.9rem 1rem;margin:.45rem 0;border:1px solid var(--holo-dim);border-radius:.3rem;color:var(--ink);text-decoration:none;background:rgba(5,10,16,.7)}}
  a.card:hover,a.card:active{{border-color:var(--gold)}}a.card small{{display:block;color:var(--dim);font-size:.8rem}}
  p.back a{{color:var(--holo)}}
</style></head>
<body><h1>The crew</h1><p class="sub">Character sheets · print from the browser</p><ul>{items}</ul><p class="back"><a href="../index.html">← handouts</a></p></body></html>
"""


def main() -> int:
    files = sorted(SRC.glob("*.json")) if SRC.exists() else []
    crew = []
    for f in files:
        try:
            crew.append(normalize(json.loads(f.read_text(encoding="utf-8")), f.stem))
        except Exception as ex:  # one bad export should not sink the rest
            print(f"skipping {f.name}: {ex}", file=sys.stderr)
    crew.sort(key=lambda c: c["name"])
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    OUT_JSON.write_text(json.dumps(crew, ensure_ascii=False, indent=1), encoding="utf-8")
    for c in crew:
        (OUT_DIR / f"{c['slug']}.html").write_text(sheet_html(c), encoding="utf-8")
    (OUT_DIR / "index.html").write_text(index_html(crew), encoding="utf-8")
    print(f"{len(crew)} character(s): " + ", ".join(c["name"] for c in crew) + f" -> {OUT_JSON.relative_to(ROOT)}, {OUT_DIR.relative_to(ROOT)}/")
    return 0


if __name__ == "__main__":
    sys.exit(main())
