#!/usr/bin/env python3
"""Build the Ember Age system map from docs/setting/systems.json.

Outputs:
  system-map.html              — GM edition (GM layer + Import save)
  player-aids/system-map.html  — player edition: every `gm` key removed from the
                                 embedded data and every <!-- GM:start -->…<!-- GM:end -->
                                 template region deleted. Nothing GM-only survives in the file.
"""
import copy
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "docs/setting/systems.json"
TEMPLATE = ROOT / "tools/system-map-template.html"
OUT_GM = ROOT / "system-map.html"
OUT_PLAYER = ROOT / "player-aids/system-map.html"
WOOKIEEPEDIA = ROOT / "docs/setting/wookieepedia.json"
GALAXY_CSV = ROOT / "docs/maps/Star Wars Galaxy Map Grid Coordinates - planets.csv"
VENDOR_PLANETS = ROOT / "docs/maps/vendor/planets.json"
VENDOR_LANES = ROOT / "docs/maps/vendor/hyperlanes_db.json"
HERO_ALIASES = {"Brentaal IV": "Brentaal", "Bannistar Station": "Bannistar Station"}  # dataset name -> hero name
SQ = 340.0
REGION_NORM = {"Core": "Core", "Deep Core": "Deep Core", "Colonies": "Colonies", "Inner Rim Territories": "Inner Rim",
               "Expansion Region": "Expansion Region", "Mid Rim Territories": "Mid Rim", "Outer Rim Territories": "Outer Rim",
               "Hutt Space": "Hutt Space", "Wild Space": "Wild Space", "Unknown Regions": "Unknown Regions"}
# Timeless geography goes to everyone; era-stamped facts (who ruled it, how many lived there) are GM-only.
PLAYER_FACTS = {"region", "sector", "system", "routes", "climate", "terrain", "species", "language"}

GM_REGION = re.compile(r"<!-- GM:start -->.*?<!-- GM:end -->", re.S)


def merge_wookieepedia(data: dict, wp: dict) -> dict:
    """Attach Wookieepedia pulls: image + infobox facts for everyone (`wp`), lead paragraph GM-only (`gm.wpLead`)."""
    d = copy.deepcopy(data)
    for s in d["systems"]:
        e = wp.get(s["id"])
        if not e or e.get("missing"):
            continue
        facts = e.get("facts", {})
        s["wp"] = {k: e[k] for k in ("title", "url", "image") if k in e}
        s["wp"]["facts"] = {k: v for k, v in facts.items() if k in PLAYER_FACTS}
        gm_facts = {k: v for k, v in facts.items() if k not in PLAYER_FACTS}
        if e.get("lead") or gm_facts:
            gm = s.setdefault("gm", {})
            if e.get("lead"):
                gm["wpLead"] = e["lead"]
            if gm_facts:
                gm["wpFacts"] = gm_facts
    return d


def load_galaxy(exclude_names: set) -> list:
    """Every named planet of the galaxy gazetteer, positioned on the strict grid (340 units per square)
    with a deterministic in-square scatter. [name, x, y, grid, sector, region] per planet."""
    if not GALAXY_CSV.exists():
        return []
    import csv
    import hashlib
    out = []
    with open(GALAXY_CSV, encoding="utf-8-sig") as f:
        for row in csv.DictReader(f):
            name = row["Planet"].strip()
            m = re.match(r"^([A-V])(\d{1,2})$", row["Grid"].strip().upper().replace("-", ""))
            if not name or not m or name.lower() in exclude_names:
                continue
            col, rown = ord(m.group(1)) - 64, int(m.group(2))
            h = int(hashlib.md5(name.encode()).hexdigest(), 16)
            jx, jy = (h % 1000) / 1000 - 0.5, ((h // 1000) % 1000) / 1000 - 0.5
            out.append([name, round((col - 0.5) * 340 + jx * 290), round((rown - 0.5) * 340 + jy * 290),
                        f"{m.group(1)}-{rown}", row["Sector"].strip(), row["Region"].strip()])
    return out


def _vendor_pos(e):
    m = re.match(r"^([A-V])-(\d{1,2})$", str(e.get("Coord") or ""))
    if not m:
        return None
    col, row = ord(m.group(1)) - 64, int(m.group(2))
    if not 1 <= row <= 22:
        return None
    sx = e.get("SubGridX"); sy = e.get("SubGridY")
    sx = sx if isinstance(sx, (int, float)) else 0.5
    sy = sy if isinstance(sy, (int, float)) else 0.5
    return round((col - 1 + sx) * SQ), round((row - 1 + sy) * SQ), f"{m.group(1)}-{row}"


def load_vendor(exclude_names: set):
    """Background planets + named-route polylines + the nav graph, from the vendored
    SWGalacticMap planets.json and StarWarsMap hyperlanes_db.json."""
    planets = json.loads(VENDOR_PLANETS.read_text(encoding="utf-8"))
    galaxy, pos = [], {}
    for e in planets:
        name = (e.get("Name") or "").strip()
        pv = _vendor_pos(e)
        if not name or not pv:
            continue
        x, y, grid = pv
        if name not in pos:
            pos[name] = (x, y)
        alias = HERO_ALIASES.get(name, name)
        if name.lower() in exclude_names or alias.lower() in exclude_names:
            continue
        sector = (e.get("Sector") or "").replace(" Sector", "").strip()
        region = REGION_NORM.get((e.get("Region") or "").strip(), (e.get("Region") or "").strip())
        galaxy.append([name, x, y, grid, sector, region])
    lanes = json.loads(VENDOR_LANES.read_text(encoding="utf-8"))
    return galaxy, pos, lanes


MAJOR_ROUTES = {"Perlemian Trade Route", "Corellinan Run", "Corellian Trade Spine", "Hydian Way", "Rimma Trade Route"}
ROUTE_RENAME = {"Corellinan Run": "Corellian Run"}


def build_network(data: dict) -> None:
    """Attach data["galaxy"], data["routes"], data["nav"] from the vendor files (CSV fallback for galaxy)."""
    hero_pos = {s["name"]: (s["x"], s["y"]) for s in data["systems"]}
    exclude = {n.lower() for n in hero_pos}
    if not (VENDOR_PLANETS.exists() and VENDOR_LANES.exists()):
        data["galaxy"] = load_galaxy(exclude)
        data["routes"], data["nav"] = [], {"pos": {}, "edges": []}
        return
    galaxy, pos, lanes = load_vendor(exclude)
    data["galaxy"] = galaxy

    def resolve(name):
        alias = HERO_ALIASES.get(name, name)
        if alias in hero_pos:
            return alias, hero_pos[alias]
        if name in pos:
            return name, pos[name]
        return None, None

    routes, nav_pos, edges, seen_edges = [], {}, [], set()
    hero_names = set(hero_pos)
    by_id_pre = {s["id"]: s["name"] for s in data["systems"]}
    campaign_pairs = {tuple(sorted((by_id_pre[l["from"]], by_id_pre[l["to"]]))) for l in data["lanes"]}
    for rname, stops in lanes.items():
        pts, chain = [], []
        for s in stops:
            n, pv = resolve(s)
            if n:
                pts.append([pv[0], pv[1]])
                chain.append(n)
        if len(pts) < 2:
            continue
        disp = ROUTE_RENAME.get(rname, rname)
        routes.append({"n": disp, "major": rname in MAJOR_ROUTES, "pts": pts})
        for a, b in zip(chain, chain[1:]):
            if a == b:
                continue
            key = tuple(sorted((a, b)))
            if key in seen_edges or key in campaign_pairs:
                continue
            seen_edges.add(key)
            ax, ay = hero_pos.get(a) or pos[a]
            bx, by = hero_pos.get(b) or pos[b]
            in_reach = lambda x, y: 3900 < x < 5480 and 5230 < y < 6250
            both_in_reach = in_reach(ax, ay) and in_reach(bx, by)
            if both_in_reach and a in hero_names and b in hero_names:
                continue  # inside the Reach, the campaign's own lanes are the chart
            kind = "withered" if both_in_reach else "route"
            nav_pos[a] = [ax, ay]; nav_pos[b] = [bx, by]
            edges.append([a, b, kind, disp])
    by_id = {s["id"]: s["name"] for s in data["systems"]}
    for l in data["lanes"]:
        a, b = by_id[l["from"]], by_id[l["to"]]
        key = tuple(sorted((a, b)))
        seen_edges.add(key)
        nav_pos[a] = list(hero_pos[a]); nav_pos[b] = list(hero_pos[b])
        edges.append([a, b, l["kind"], l.get("name", "")])
    data["routes"] = routes
    data["nav"] = {"pos": nav_pos, "edges": edges}


def load_data() -> dict:
    data = json.loads(DATA.read_text(encoding="utf-8"))
    if WOOKIEEPEDIA.exists():
        data = merge_wookieepedia(data, json.loads(WOOKIEEPEDIA.read_text(encoding="utf-8")))
    build_network(data)
    return data


def strip_gm(data: dict) -> dict:
    d = copy.deepcopy(data)
    for s in d["systems"]:
        s.pop("gm", None)
    return d


def build(edition: str, data: dict, template: str) -> str:
    starts = template.count("<!-- GM:start -->")
    ends = template.count("<!-- GM:end -->")
    if starts != ends:
        raise SystemExit(f"GM marker mismatch: {starts} start / {ends} end")
    if edition == "player":
        data = strip_gm(data)
        template = GM_REGION.sub("", template)
    else:
        template = template.replace("<!-- GM:start -->", "").replace("<!-- GM:end -->", "")
    payload = json.dumps(data, ensure_ascii=False).replace("</", "<\\/").replace("<!--", "<\\u0021--")
    out = template.replace("__DATA__", payload).replace("__EDITION__", edition)
    if edition == "player" and ("GM:start" in out or "GM:end" in out or '"gm":' in out):
        raise SystemExit("GM content leaked into the player edition")
    return out


def main():
    data = load_data()
    template = TEMPLATE.read_text(encoding="utf-8")
    OUT_GM.write_text(build("gm", data, template), encoding="utf-8")
    OUT_PLAYER.write_text(build("player", data, template), encoding="utf-8")
    print(f"wrote {OUT_GM.relative_to(ROOT)} and {OUT_PLAYER.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
