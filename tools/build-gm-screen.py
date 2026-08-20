#!/usr/bin/env python3
"""Build gm-screen.html — The Ember Age's single-file interactive GM screen.

Reads the campaign markdown under docs/, renders it, and injects it into
tools/gm-screen-template.html. Output: gm-screen.html at the repo root.
No network, no dependencies beyond Python-Markdown (installed with mkdocs).
"""
import json
import re
from datetime import date
from pathlib import Path

import markdown

ROOT = Path(__file__).resolve().parent.parent
DOCS = ROOT / "docs"
TEMPLATE = ROOT / "tools" / "gm-screen-template.html"
OUT = ROOT / "gm-screen.html"

MD = markdown.Markdown(extensions=["tables"])

ADM_RE = re.compile(r'^!!!\s+(\w+)(?:\s+"([^"]*)")?\s*$')


def preprocess_admonitions(text: str) -> str:
    """Convert mkdocs '!!! type "Title"' blocks into plain HTML divs."""
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


LINK_RE = re.compile(r'<a href="[^"]*\.md[^"]*"[^>]*>(.*?)</a>', re.S)


def render(md_text: str) -> str:
    MD.reset()
    html = MD.convert(preprocess_admonitions(md_text))
    return LINK_RE.sub(r'<span class="xref">\1</span>', html)


def plain(md_text: str) -> str:
    t = re.sub(r"[*_`#>|]", " ", md_text)
    return re.sub(r"\s+", " ", t).strip().lower()


# ---------------------------------------------------------------- NPC library
NPC_FILES = [
    ("session-one", "Vesta-9 & the Crew's Orbit", DOCS / "gm/npcs/session-one.md"),
    ("republic-admiralty", "Republic & Admiralty", DOCS / "gm/npcs/republic-admiralty.md"),
    ("vigil-inheritors", "Vigil & Inheritors", DOCS / "gm/npcs/vigil-inheritors.md"),
    ("lanes-ledgers", "Lanes & Ledgers", DOCS / "gm/npcs/lanes-ledgers.md"),
    ("reaches", "The Reaches", DOCS / "gm/npcs/reaches.md"),
    ("keepers", "Keepers of the Flame 🔒", DOCS / "gm/npcs/keepers.md"),
    ("ships", "Ships of the Ember Age", DOCS / "mechanics/ships.md"),
]

TYPE_WORDS = ("Nemesis", "Rival", "Minion")


def parse_npcs():
    npcs, groups = [], []
    for slug, label, path in NPC_FILES:
        text = path.read_text(encoding="utf-8")
        parts = re.split(r"(?m)^### ", text)
        preamble = parts[0]
        groups.append({"slug": slug, "label": label, "intro": render(preamble)})
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
            if slug == "ships":
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
                "html": render(body),
                "search": plain(name + " " + body),
            })
    return npcs, groups


# ---------------------------------------------------------------- pages
def page(section, pid, title, relpath):
    return {"section": section, "id": pid, "title": title,
            "html": render((DOCS / relpath).read_text(encoding="utf-8"))}


PAGES = [
    # Reference tab
    ("reference", "primer", "Adversary Rules Primer", "gm/npcs/index.md"),
    ("reference", "lore-fragments", "Lore Fragments", "mechanics/lore-fragments.md"),
    ("reference", "beacon-relighting", "Relighting a Beacon", "mechanics/beacon-relighting.md"),
    ("reference", "force", "The Force in the Ember Age", "mechanics/force.md"),
    ("reference", "obligation", "Obligation", "mechanics/obligation.md"),
    ("reference", "character-creation", "Character Creation", "mechanics/character-creation.md"),
    # Setting tab
    ("setting", "home", "The Ember Age", "index.md"),
    ("setting", "timeline", "The Withering (Timeline)", "setting/timeline.md"),
    ("setting", "galaxy", "The Galaxy at 90 AR", "setting/galaxy.md"),
    ("setting", "awakening", "The Awakening", "setting/awakening.md"),
    ("setting", "glossary", "Terms of the Era", "setting/glossary.md"),
    ("setting", "factions", "Factions Overview", "factions/index.md"),
    ("setting", "republic", "The Provisional Republic", "factions/provisional-republic.md"),
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
    # Truths tab
    ("truths", "truths", "GM Truths (Part V)", "gm/truths.md"),
]


SEED = {
    "questions": [
        "What ended the Order?",
        "What is the Valley?",
        "Who lit Vesta-9?",
        "What did the Adjournment actually adjourn?",
    ],
    "clocks": [
        {"faction": "Provisional Republic", "crack": "Custodians of the idea, terrified of being tested", "value": 0, "notes": ""},
        {"faction": "Admiralty", "crack": "The founding story requires an enemy → the Annexation", "value": 0, "notes": ""},
        {"faction": "Vigil", "crack": "Sacrilege vs. Order-reborn — custody of the Awakened → the Vigil breaks", "value": 0, "notes": ""},
        {"faction": "Inheritors", "crack": "Nobody knows whose hand is at the top → the Unveiling", "value": 0, "notes": "Hold the Vesta-9 file on the crew and Immi (Dial 3)."},
        {"faction": "Lamplighters", "crack": "The relighting order is for sale → Conclave of Charts (rigged: Denno Pike)", "value": 0, "notes": ""},
        {"faction": "Kajidics", "crack": "The young Hutts have run the numbers → clan war", "value": 0, "notes": ""},
        {"faction": "The Awakening", "crack": "Every public display raises the temperature → it goes public", "value": 0, "notes": ""},
    ],
    "beacons": [
        {"name": "Vesta-9", "status": "lit", "corridor": "the Q'ell Reach",
         "certified": "Chartmistress Bel Nerra (Lamplighters)", "fee": "pending session one",
         "followed": "Vigil, Admiralty, Lamplighters — and one Inheritor observer (Dial 3)"},
    ],
    "fragments": [],
    "truthsFound": [],
    "corrupted": [],
    "sessions": [],
}


def main():
    npcs, groups = parse_npcs()
    pages = [page(*p) for p in PAGES]
    tpl = TEMPLATE.read_text(encoding="utf-8")
    out = (tpl
           .replace("/*__NPCS__*/[]", json.dumps(npcs, ensure_ascii=False))
           .replace("/*__GROUPS__*/[]", json.dumps(groups, ensure_ascii=False))
           .replace("/*__PAGES__*/[]", json.dumps(pages, ensure_ascii=False))
           .replace("/*__SEED__*/{}", json.dumps(SEED, ensure_ascii=False))
           .replace("__BUILDDATE__", date.today().isoformat()))
    OUT.write_text(out, encoding="utf-8")
    kinds = {}
    for n in npcs:
        kinds[n["kind"]] = kinds.get(n["kind"], 0) + 1
    print(f"gm-screen.html written: {OUT.stat().st_size // 1024} KB, "
          f"{len(npcs)} blocks {kinds}, {len(pages)} pages")


if __name__ == "__main__":
    main()
