#!/usr/bin/env python3
"""Build the Ember Age GM screen from the campaign markdown under docs/.

Outputs:
  gm-screen.html           — standalone full document (open from disk, works offline)
  gm-screen.artifact.html  — the same app as artifact body-content (published to claude.ai,
                             where the platform wraps it in its own document skeleton)

Internal wiki links are resolved into in-app navigation (data-nav specs); the app can
republish itself with its saved state via the artifact runtime, so the template's
HEAD/SKELETON fragments are also embedded as JS constants for renderDocument().
"""
import json
import posixpath
import re
from datetime import date
from pathlib import Path

import markdown

ROOT = Path(__file__).resolve().parent.parent
DOCS = ROOT / "docs"
TEMPLATE = ROOT / "tools" / "gm-screen-template.html"
OUT_FULL = ROOT / "gm-screen.html"
OUT_ARTIFACT = ROOT / "gm-screen.artifact.html"
CHARACTERS = ROOT / "docs/setting/characters.json"

MD = markdown.Markdown(extensions=["tables"])

ADM_RE = re.compile(r'^!!!\s+(\w+)(?:\s+"([^"]*)")?\s*$')


def preprocess_admonitions(text: str) -> str:
    out, lines, i = [], text.splitlines(), 0
    while i < len(lines):
        m = ADM_RE.match(lines[i])
        if not m:
            out.append(lines[i])
            i += 1
            continue
        kind = m.group(1).lower()
        title = m.group(2) if m.group(2) is not None else kind.capitalize()
        i += 1
        body = []
        while i < len(lines) and (lines[i].startswith("    ") or lines[i].strip() == ""):
            if lines[i].strip() == "" and (i + 1 >= len(lines) or not (lines[i + 1].startswith("    ") or lines[i + 1].strip() == "")):
                break
            body.append(lines[i][4:] if lines[i].startswith("    ") else "")
            i += 1
        MD.reset()
        body_html = MD.convert("\n".join(body))
        out.append("")
        out.append(f'<div class="adm adm-{kind}">'
                   + (f'<p class="adm-title">{title}</p>' if title else "")
                   + body_html + "</div>")
        out.append("")
    return "\n".join(out)


# -------------------------------------------------------------- link routing
# docs-relative path -> in-app navigation spec understood by navTo()
NAV_MAP = {
    "index.md": "page:setting:home",
    "setting/timeline.md": "page:setting:timeline",
    "setting/galaxy.md": "page:setting:galaxy",
    "setting/awakening.md": "page:setting:awakening",
    "setting/glossary.md": "page:setting:glossary",
    "setting/geography.md": "page:setting:geography",
    "factions/index.md": "page:setting:factions",
    "factions/republic.md": "page:setting:republic",
    "factions/jedi-order.md": "page:setting:jedi",
    "factions/admiralty.md": "page:setting:admiralty",
    "factions/vigil.md": "page:setting:vigil",
    "factions/inheritors.md": "page:setting:inheritors",
    "factions/lamplighters.md": "page:setting:lamplighters",
    "factions/kajidics.md": "page:setting:kajidics",
    "factions/bounty-hunters-guild.md": "page:setting:guild",
    "factions/mandalorians.md": "page:setting:mandalorians",
    "campaign/index.md": "page:setting:structure",
    "campaign/act-1.md": "page:setting:act-1",
    "campaign/act-2.md": "page:setting:act-2",
    "campaign/act-3.md": "page:setting:act-3",
    "campaign/session-one.md": "page:setting:session-one",
    "campaign/session-log.md": "tab:log",
    "mechanics/index.md": "tab:reference",
    "mechanics/character-creation.md": "page:reference:character-creation",
    "mechanics/obligation.md": "page:reference:obligation",
    "mechanics/lore-fragments.md": "page:reference:lore-fragments",
    "mechanics/beacon-relighting.md": "page:reference:beacon-relighting",
    "mechanics/force.md": "page:reference:force",
    "mechanics/dice-results.md": "page:reference:dice-results",
    "mechanics/ships.md": "npcs:group:ships",
    "gm/index.md": "tab:trackers",
    "gm/truths.md": "tab:truths",
    "gm/npcs/index.md": "page:reference:primer",
    "gm/npcs/session-one.md": "npcs:group:session-one",
    "gm/npcs/republic-admiralty.md": "npcs:group:republic-admiralty",
    "gm/npcs/vigil-inheritors.md": "npcs:group:vigil-inheritors",
    "gm/npcs/lanes-ledgers.md": "npcs:group:lanes-ledgers",
    "gm/npcs/reaches.md": "npcs:group:reaches",
    "gm/npcs/keepers.md": "npcs:group:keepers",
    "gm/tools/fragment-tracker.md": "tab:trackers",
    "gm/tools/beacon-map.md": "tab:trackers",
    "gm/tools/faction-clocks.md": "tab:trackers",
    "gm/modules/01-the-light-on-vesta-9.md": "tab:run",
}

LINK_RE = re.compile(r'<a href="([^"]*\.md)(?:#[^"]*)?"[^>]*>(.*?)</a>', re.S)


def resolve_links(html: str, src_rel_dir: str) -> str:
    def sub(m):
        href, text = m.group(1), m.group(2)
        target = posixpath.normpath(posixpath.join(src_rel_dir, href)) if not href.startswith("/") else href.lstrip("/")
        spec = NAV_MAP.get(target)
        if spec:
            return f'<a href="#" class="xin" data-nav="{spec}">{text}</a>'
        return f'<span class="xref">{text}</span>'
    return LINK_RE.sub(sub, html)


def render(md_text: str, src_rel_dir: str) -> str:
    MD.reset()
    html = MD.convert(preprocess_admonitions(md_text))
    return resolve_links(html, src_rel_dir)


def render_file(relpath: str) -> str:
    return render((DOCS / relpath).read_text(encoding="utf-8"), posixpath.dirname(relpath))


def plain(md_text: str) -> str:
    t = re.sub(r"[*_`#>|]", " ", md_text)
    return re.sub(r"\s+", " ", t).strip().lower()


# ---------------------------------------------------------------- NPC library
NPC_FILES = [
    ("session-one", "Vesta-9 & the Crew's Orbit", "gm/npcs/session-one.md"),
    ("republic-admiralty", "Republic & Admiralty", "gm/npcs/republic-admiralty.md"),
    ("vigil-inheritors", "Vigil & Inheritors", "gm/npcs/vigil-inheritors.md"),
    ("lanes-ledgers", "Lanes & Ledgers", "gm/npcs/lanes-ledgers.md"),
    ("reaches", "The Reaches", "gm/npcs/reaches.md"),
    ("keepers", "Keepers of the Flame 🔒", "gm/npcs/keepers.md"),
    ("ships", "Ships of the Ember Age", "mechanics/ships.md"),
]

TYPE_WORDS = ("Nemesis", "Rival", "Minion")


def parse_npcs():
    npcs, groups = [], []
    for slug, label, relpath in NPC_FILES:
        src_dir = posixpath.dirname(relpath)
        text = (DOCS / relpath).read_text(encoding="utf-8")
        parts = re.split(r"(?m)^### ", text)
        groups.append({"slug": slug, "label": label, "intro": render(parts[0], src_dir)})
        for chunk in parts[1:]:
            name, _, body = chunk.partition("\n")
            name = re.sub(r"\*+", "", name).strip()
            typ, faction, role = "", "", ""
            for line in body.splitlines():
                ls = line.strip()
                if ls.startswith("|") or ls.startswith("**"):
                    break
                if ls.startswith("*") and not ls.startswith("**"):
                    bits = [b.strip() for b in re.split(r"\s+—\s+", ls.replace("*", "").strip())]
                    typ = bits[0] if bits else ""
                    faction = bits[1] if len(bits) > 1 else ""
                    role = bits[2] if len(bits) > 2 else ""
                    break
            if slug == "ships" or typ.startswith("Vehicle"):
                kind = "Vehicle"
            elif "hazard" in typ.lower() or "hazard" in name.lower():
                kind = "Hazard"
            else:
                kind = next((w for w in TYPE_WORDS if typ.startswith(w)), "Special")
            derived = re.search(r"\*\*((?:Soak|Defense|Silhouette).+?)\*\*", body)
            npcs.append({
                "id": f"{slug}--{re.sub(r'[^a-z0-9]+', '-', name.lower()).strip('-')}",
                "name": name,
                "kind": kind,
                "typeline": typ,
                "faction": faction,
                "role": role,
                "derived": derived.group(1) if derived else "",
                "group": slug,
                "html": render(body, src_dir),
                "search": plain(name + " " + body),
            })
    # Vehicles statted inside GM-only NPC files (e.g. the Sith line's fighter in
    # keepers.md) are shelved with the other ships. ships.md itself stays
    # player-safe, so this is the only place they meet. A hull the ships file
    # already carries (the Steadfast, mirrored for the session-one markers) keeps
    # its home group rather than appearing twice under Ships.
    ship_names = {n["name"] for n in npcs if n["group"] == "ships"}
    for n in npcs:
        if n["kind"] == "Vehicle" and n["group"] != "ships" and n["name"] not in ship_names:
            n["group"] = "ships"
    return npcs, groups


# ---------------------------------------------------------------- run modules
MODULE_FILES = [
    ("01", "gm/modules/01-the-light-on-vesta-9.md"),
]

CLOCK_FACTIONS = {"Republic", "Admiralty", "Vigil", "Inheritors",
                  "Lamplighters", "Kajidics", "The Awakening"}
FRAGMENT_TAGS = {"Jedi", "Sith", "Civic"}

ACTION_RE = re.compile(r"(?m)^@@action:(\w+)\s+(\{.*\})@@\s*$")
NPCREF_RE = re.compile(r"@@npc:([^@]+)@@")


def action_label(kind, args):
    if kind == "fragment":
        return (f"Issue fragment: {args.get('name','')}",
                f"{args.get('tag','')} · bears on “{args.get('question','')}”")
    if kind == "clock":
        d = args.get("delta", 1)
        return (f"Advance clock: {args.get('faction','')} {'+' if d >= 0 else ''}{d}",
                args.get("note", ""))
    if kind == "beacon":
        return (f"Update beacon map: {args.get('name','')}",
                f"{args.get('status','')} · {args.get('fee','')}")
    return (kind, "")


def parse_module(mid, relpath, name_to_id):
    import html as htmllib
    path = DOCS / relpath
    if not path.exists():
        return None
    src_dir = posixpath.dirname(relpath)
    text = path.read_text(encoding="utf-8")
    problems = []
    counter = [0]

    def sub_action(m):
        kind, raw = m.group(1), m.group(2)
        try:
            args = json.loads(raw)
        except json.JSONDecodeError as e:
            problems.append(f"action JSON invalid ({kind}): {e}")
            return ""
        if kind == "clock" and args.get("faction") not in CLOCK_FACTIONS:
            problems.append(f"unknown clock faction: {args.get('faction')}")
        if kind == "fragment" and args.get("tag") not in FRAGMENT_TAGS:
            problems.append(f"bad fragment tag: {args.get('tag')}")
        counter[0] += 1
        aid = f"m{mid}-{counter[0]}"
        label, desc = action_label(kind, args)
        payload = htmllib.escape(json.dumps(args, ensure_ascii=False), quote=True)
        return (f'\n<div class="runact" data-kind="{kind}" data-aid="{aid}" data-args="{payload}">'
                f'<button class="btn">{htmllib.escape(label)}</button>'
                f'<span class="runact-desc">{htmllib.escape(desc)}</span></div>\n')

    def sub_npc(m):
        name = m.group(1).strip()
        nid = name_to_id.get(name)
        if not nid:
            problems.append(f"unknown NPC reference: {name!r}")
            return name
        return f'<a href="#" class="xin" data-nav="npc:{nid}">{name}</a>'

    text = ACTION_RE.sub(sub_action, text)
    text = NPCREF_RE.sub(sub_npc, text)
    if problems:
        raise SystemExit(f"module {relpath}: " + "; ".join(problems))

    title_m = re.search(r"(?m)^# (.+)$", text)
    title = title_m.group(1).strip() if title_m else relpath
    body = text[title_m.end():] if title_m else text
    parts = re.split(r"(?m)^## ", body)
    intro = render(parts[0], src_dir)
    scenes = []
    for i, chunk in enumerate(parts[1:], 1):
        stitle, _, sbody = chunk.partition("\n")
        scenes.append({"sid": f"s{i}", "title": stitle.strip(), "html": render(sbody, src_dir)})
    return {"id": mid, "title": title, "intro": intro, "scenes": scenes}


# ---------------------------------------------------------------- pages
PAGES_SPEC = [
    ("reference", "primer", "Adversary Rules Primer", "gm/npcs/index.md"),
    ("reference", "dice-results", "Reading the Dice", "mechanics/dice-results.md"),
    ("reference", "lore-fragments", "Lore Fragments", "mechanics/lore-fragments.md"),
    ("reference", "beacon-relighting", "Relighting a Beacon", "mechanics/beacon-relighting.md"),
    ("reference", "force", "The Force in the Ember Age", "mechanics/force.md"),
    ("reference", "obligation", "Obligation", "mechanics/obligation.md"),
    ("reference", "character-creation", "Character Creation", "mechanics/character-creation.md"),
    ("setting", "home", "The Ember Age", "index.md"),
    ("setting", "timeline", "The Withering (Timeline)", "setting/timeline.md"),
    ("setting", "galaxy", "The Galaxy at 90 AR", "setting/galaxy.md"),
    ("setting", "awakening", "The Awakening", "setting/awakening.md"),
    ("setting", "glossary", "Terms of the Era", "setting/glossary.md"),
    ("setting", "geography", "The Road Back to the Hydian", "setting/geography.md"),
    ("setting", "factions", "Factions Overview", "factions/index.md"),
    ("setting", "republic", "The Republic", "factions/republic.md"),
    ("setting", "jedi", "The Jedi Order", "factions/jedi-order.md"),
    ("setting", "admiralty", "The Admiralty", "factions/admiralty.md"),
    ("setting", "vigil", "The Vigil", "factions/vigil.md"),
    ("setting", "inheritors", "The Inheritors", "factions/inheritors.md"),
    ("setting", "lamplighters", "The Lamplighters", "factions/lamplighters.md"),
    ("setting", "kajidics", "The Kajidics", "factions/kajidics.md"),
    ("setting", "guild", "The Bounty Hunters' Guild", "factions/bounty-hunters-guild.md"),
    ("setting", "mandalorians", "The Mandalorian Clans", "factions/mandalorians.md"),
    ("setting", "structure", "Campaign Structure", "campaign/index.md"),
    ("setting", "act-1", "Act 1 — Reconnection", "campaign/act-1.md"),
    ("setting", "act-2", "Act 2 — Convergence", "campaign/act-2.md"),
    ("setting", "act-3", "Act 3 — The Founding", "campaign/act-3.md"),
    ("setting", "session-one", "Session One — Vesta-9", "campaign/session-one.md"),
    ("truths", "truths", "GM Truths (Part V)", "gm/truths.md"),
]

SEED = {
    "questions": [
        "Why did the Jedi leave the Rim?",
        "What is the Valley?",
        "Who lit Vesta-9?",
        "What did the Adjournment actually adjourn?",
    ],
    "clocks": [
        {"faction": "Republic", "crack": "Recovered by adjourning the Rim; wants it back on its terms", "value": 0, "notes": ""},
        {"faction": "Admiralty", "crack": "The founding story requires an enemy → the Annexation", "value": 0, "notes": ""},
        {"faction": "Vigil", "crack": "Sacrilege vs. Order-reborn — custody of the Awakened → the Vigil breaks", "value": 0, "notes": ""},
        {"faction": "Inheritors", "crack": "Nobody knows whose hand is at the top → the Unveiling", "value": 0, "notes": "Hold the Vesta-9 file on the crew — and its gifted (Dial 3)."},
        {"faction": "Lamplighters", "crack": "The relighting order is for sale → Conclave of Charts (rigged: Denno Pike)", "value": 0, "notes": ""},
        {"faction": "Kajidics", "crack": "The young Hutts have run the numbers → clan war", "value": 0, "notes": ""},
        {"faction": "The Awakening", "crack": "Every public display raises the temperature → it goes public", "value": 0, "notes": ""},
    ],
    "beacons": [
        {"name": "Vesta-9", "status": "lit", "corridor": "the Grumani Reach (Duros Space Run, toward Enarc)",
         "certified": "Chartmistress Bel Nerra (Lamplighters)", "fee": "pending session one",
         "followed": "Vigil, Admiralty, Lamplighters — and one Inheritor observer (Dial 3)"},
    ],
    "fragments": [],
    "truthsFound": [],
    "corrupted": [],
    "sessions": [],
    "run": {},
    "rev": 0,
}


def between(text, start, end):
    return text.split(start, 1)[1].split(end, 1)[0]


def main():
    tpl = TEMPLATE.read_text(encoding="utf-8")
    head_static = between(tpl, "<!--HEAD_STATIC_START-->", "<!--HEAD_STATIC_END-->").strip()
    style_block = "<style id=\"app-style\">" + between(tpl, '<style id="app-style">', "</style>") + "</style>"
    skeleton = between(tpl, "<!--SKELETON_START-->", "<!--SKELETON_END-->").strip()
    app_code = between(tpl, '<script id="app-code">', "</script>")

    npcs, groups = parse_npcs()
    pages = [{"section": s, "id": i, "title": t, "html": render_file(p)} for s, i, t, p in PAGES_SPEC]
    name_to_id = {n["name"]: n["id"] for n in npcs}
    modules = [m for m in (parse_module(mid, rp, name_to_id) for mid, rp in MODULE_FILES) if m]

    skeleton = skeleton.replace("__BUILDDATE__", date.today().isoformat())
    code = (app_code
            .replace("/*__NPCS__*/[]", json.dumps(npcs, ensure_ascii=False))
            .replace("/*__GROUPS__*/[]", json.dumps(groups, ensure_ascii=False))
            .replace("/*__PAGES__*/[]", json.dumps(pages, ensure_ascii=False))
            .replace("/*__MODULES__*/[]", json.dumps(modules, ensure_ascii=False))
            .replace("/*__SEED__*/{}", json.dumps(SEED, ensure_ascii=False))
            .replace("/*__CREW__*/[]", json.dumps(json.loads(CHARACTERS.read_text(encoding="utf-8")) if CHARACTERS.exists() else [], ensure_ascii=False))
            .replace('/*__HEAD__*/""', json.dumps(head_static, ensure_ascii=False))
            .replace('/*__SKEL__*/""', json.dumps(skeleton, ensure_ascii=False)))
    if "</scr" + "ipt" in code.lower():
        raise SystemExit("app code may not contain a literal script close tag")

    state_block = ('<script id="gm-state" type="application/json">'
                   + json.dumps(SEED, ensure_ascii=False).replace("<", "\\u003c")
                   + "</script>")
    code_block = '<script id="app-code">' + code + "</script>"

    body = skeleton + "\n" + state_block + "\n" + code_block

    full = ("<!doctype html>\n<html lang=\"en\">\n<head>\n" + head_static + "\n"
            + style_block + "\n</head>\n<body>\n" + body + "\n</body>\n</html>\n")
    artifact = head_static + "\n" + style_block + "\n" + body + "\n"

    OUT_FULL.write_text(full, encoding="utf-8")
    OUT_ARTIFACT.write_text(artifact, encoding="utf-8")

    kinds = {}
    for n in npcs:
        kinds[n["kind"]] = kinds.get(n["kind"], 0) + 1
    nav_specs = set(NAV_MAP.values())
    print(f"gm-screen.html: {OUT_FULL.stat().st_size // 1024} KB · artifact variant: "
          f"{OUT_ARTIFACT.stat().st_size // 1024} KB · {len(npcs)} blocks {kinds} · "
          f"{len(pages)} pages · {len(nav_specs)} nav routes · "
          f"{len(modules)} run module(s): " + ", ".join(f"{m['title']} ({len(m['scenes'])} scenes)" for m in modules))


if __name__ == "__main__":
    main()
