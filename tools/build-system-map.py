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
GWP = ROOT / "docs/setting/wookieepedia-galaxy.json"
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


def merge_galaxy_wookieepedia(data: dict, gwp: dict) -> None:
    """Background-planet pulls: player-safe facts for everyone (`gwp`), era-spanning
    leads + remaining facts GM-only (`gwpGm`, stripped from the player edition)."""
    names = {g[0] for g in data.get("galaxy", [])}
    pub, gm = {}, {}
    for n, e in gwp.items():
        if n not in names or e.get("missing"):
            continue
        facts = e.get("facts", {})
        entry = {"t": e["title"], "u": e["url"]}
        if e.get("image"):
            entry["i"] = {"f": e["image"]["file"], "w": e["image"].get("width"), "h": e["image"].get("height")}
        pf = {k: v for k, v in facts.items() if k in PLAYER_FACTS}
        if pf:
            entry["f"] = pf
        pub[n] = entry
        ge = {}
        gmf = {k: v for k, v in facts.items() if k not in PLAYER_FACTS}
        if e.get("lead"):
            ge["lead"] = e["lead"]
        if gmf:
            ge["f"] = gmf
        if ge:
            gm[n] = ge
    if pub:
        data["gwp"] = pub
    if gm:
        data["gwpGm"] = gm


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


SVG_MAP = ROOT / "docs/maps/vendor/svg_map.json"
SVG_SCALE = 9.0
SVG_ALIASES = {"Kashyyk": "Kashyyyk", "Eridau": "Eriadu"}  # svg name -> our name (typos on the drawn map)
MAJOR_ROUTES = {"Perlemian Trade Route", "Corellinan Run", "Corellian Trade Spine", "Hydian Way", "Rimma Trade Route"}
ROUTE_RENAME = {"Corellinan Run": "Corellian Run", "Triellus Trade Run": "Triellus Trade Route"}
def _fit_grid_to_svg(svg_by_name, vendor_planets):
    """Least-squares col,row -> svg x,y over name matches."""
    xs = []
    for e in vendor_planets:
        name = (e.get("Name") or "").strip()
        s = svg_by_name.get(name.lower())
        pv = _vendor_pos(e)
        if s and pv:
            col_row = ((pv[0] / SQ), (pv[1] / SQ))
            xs.append((col_row[0], col_row[1], s["x"], s["y"]))
    n = len(xs)
    sc = sum(x[0] for x in xs); sr = sum(x[1] for x in xs)
    sx = sum(x[2] for x in xs); sy = sum(x[3] for x in xs)
    scc = sum(x[0] * x[0] for x in xs); srr = sum(x[1] * x[1] for x in xs)
    scx = sum(x[0] * x[2] for x in xs); sry = sum(x[1] * x[3] for x in xs)
    ax = (n * scx - sc * sx) / (n * scc - sc * sc)
    bx = (sx - ax * sc) / n
    ay = (n * sry - sr * sy) / (n * srr - sr * sr)
    by = (sy - ay * sr) / n
    return lambda col, row: (ax * col + bx, ay * row + by), n


def _arc_positions(pts):
    acc, out = 0.0, [0.0]
    for (x1, y1), (x2, y2) in zip(pts, pts[1:]):
        acc += ((x2 - x1) ** 2 + (y2 - y1) ** 2) ** 0.5
        out.append(acc)
    return out


def _nearest_on_poly(pts, arcs, x, y):
    best = (1e18, 0.0, x, y)
    for i, ((x1, y1), (x2, y2)) in enumerate(zip(pts, pts[1:])):
        dx, dy = x2 - x1, y2 - y1
        L2 = dx * dx + dy * dy
        u = 0 if L2 == 0 else max(0.0, min(1.0, ((x - x1) * dx + (y - y1) * dy) / L2))
        px, py = x1 + u * dx, y1 + u * dy
        d2 = (x - px) ** 2 + (y - py) ** 2
        if d2 < best[0]:
            seg = ((dx * dx + dy * dy) ** 0.5)
            best = (d2, arcs[i] + u * seg, px, py)
    return best  # (d2, arc, px, py)


def _point_at_arc(pts, arcs, s):
    s = max(0.0, min(arcs[-1], s))
    for i in range(len(arcs) - 1):
        if arcs[i + 1] >= s:
            seg = arcs[i + 1] - arcs[i]
            u = 0 if seg == 0 else (s - arcs[i]) / seg
            x1, y1 = pts[i]; x2, y2 = pts[i + 1]
            return (x1 + u * (x2 - x1), y1 + u * (y2 - y1))
    return pts[-1]


def build_network(data: dict) -> None:
    """Geometry, routes and the nav graph, all from the vector map (docs/maps/vendor/svg_map.json).
    The campaign contributes only era-state (which legs are beacon-dark), never connectivity."""
    svg = json.loads(SVG_MAP.read_text(encoding="utf-8"))
    vendor_planets = json.loads(VENDOR_PLANETS.read_text(encoding="utf-8")) if VENDOR_PLANETS.exists() else []
    vendor_lanes = json.loads(VENDOR_LANES.read_text(encoding="utf-8")) if VENDOR_LANES.exists() else {}
    W = lambda x, y: (round(x * SVG_SCALE, 1), round(y * SVG_SCALE, 1))

    svg_by_name = {}
    for s in svg["systems"]:
        disp = SVG_ALIASES.get(s["name"], s["name"])
        svg_by_name.setdefault(disp.lower(), s)
    fit, nfit = _fit_grid_to_svg(svg_by_name, vendor_planets)

    # ---- name the route polylines by voting with the vendor stop lists
    grid_pos = {}
    for e in vendor_planets:
        pv = _vendor_pos(e)
        name = (e.get("Name") or "").strip()
        if pv and name and name.lower() not in grid_pos:
            grid_pos[name.lower()] = fit(pv[0] / SQ, pv[1] / SQ)
    def stop_pos(name):
        s = svg_by_name.get(name.lower())
        if s:
            return (s["x"], s["y"])
        return grid_pos.get(name.lower())
    routes = []
    for r in svg["routes"]:
        pts = r["pts"]
        arcs = _arc_positions(pts)
        votes = {}
        for rname, stops in vendor_lanes.items():
            hit = 0
            for st in stops:
                pv = stop_pos(st)
                if pv and _nearest_on_poly(pts, arcs, pv[0], pv[1])[0] < 8 ** 2:
                    hit += 1
            if hit >= 3:
                votes[rname] = hit
        name = max(votes, key=votes.get) if votes else ""
        routes.append({"pts": pts, "arcs": arcs, "name": ROUTE_RENAME.get(name, name) or "hyperlane", "major": r["major"]})

    # ---- hero positions: the drawn map governs; the atlas fills in; four campaign
    # worlds are our own and sit in stated relation to real neighbours. Nothing is
    # placed by hand-drawn grid guesses any more.
    ATLAS_WRONG = {"Heptooine"}  # vendor lists a different Heptooine (B-9, Wild Space)
    RELATIONAL = [
        # (name, anchorA, anchorB, along, perp)  pos = A + along*(B-A) + perp*rot90(B-A)
        ("Heptooine", "Sanrafsix", "Jutrand", 0.5, 0.0),
        ("Kyrska", "Kalarba", "Glom Tho", 0.5, 0.0),  # user-invented Run stop; snaps onto the drawn Duros Space Run
        ("Fostin Nine", "Syned", "Sanrafsix", 0.5, 0.0),
        ("Veshet", "Syned", "Sanrafsix", 0.5, -0.28),
        ("Teraab", None, None, 605.6, 410.0),  # absolute: the Nursery nebula
    ]
    hero_pos = {}
    svg_matched = set()
    for s in data["systems"]:
        hit = svg_by_name.get(s["name"].lower())
        if hit:
            hero_pos[s["name"]] = (hit["x"], hit["y"])
            svg_matched.add(s["name"])
    for s in data["systems"]:
        nm = s["name"]
        if nm in hero_pos or nm in ATLAS_WRONG:
            continue
        gp = grid_pos.get(nm.lower())
        if gp:
            hero_pos[nm] = (round(gp[0], 2), round(gp[1], 2))
    for nm, an_a, an_b, along, perp in RELATIONAL:
        if nm in hero_pos:
            continue
        if an_a is None:
            hero_pos[nm] = (along, perp)
            continue
        if an_a not in hero_pos or an_b not in hero_pos:
            continue
        ax, ay = hero_pos[an_a]
        bx, by = hero_pos[an_b]
        dx, dy = bx - ax, by - ay
        hero_pos[nm] = (round(ax + along * dx - perp * dy, 2), round(ay + along * dy + perp * dx, 2))
    # a fit-placed hero that belongs to a drawn named route sits ON the stroke
    # (Eriadu is not drawn on the vector map, but the Hydian is)
    _byid0 = {s["id"]: s["name"] for s in data["systems"]}
    _want = {}
    for l in data["lanes"]:
        nm = l.get("name", "")
        if nm and nm not in ("dead spur", "off the charts"):
            for nid in (l["from"], l["to"]):
                _want.setdefault(_byid0[nid], set()).add(nm)
    for name in list(hero_pos):
        if name in svg_matched or name not in _want:
            continue
        px, py = hero_pos[name]
        best = None
        for r in routes:
            if r["name"] not in _want[name]:
                continue
            d2, arc, qx, qy = _nearest_on_poly(r["pts"], r["arcs"], px, py)
            if d2 ** 0.5 < 12 and (best is None or d2 < best[0]):
                best = (d2, qx, qy)
        if best and best[0] ** 0.5 > 0.05:
            hero_pos[name] = (round(best[1], 2), round(best[2], 2))
            print(f"  snapped {name} onto its route ({best[0] ** 0.5:.1f} units off)")
    missing = [s["name"] for s in data["systems"] if s["name"] not in hero_pos]
    if missing:
        print("WARNING unplaced heroes:", missing)
    for s in data["systems"]:
        if s["name"] in hero_pos:
            x, y = hero_pos[s["name"]]
            s["x"], s["y"] = W(x, y)

    # ---- background: the drawing's own systems (named tier) + vendor dust
    hero_names = {s["name"].lower() for s in data["systems"]}
    vendor_by_name = {}
    for e in vendor_planets:
        nm = (e.get("Name") or "").strip()
        if nm:
            vendor_by_name.setdefault(nm.lower(), e)
    def _lev1(a, b):
        la, lb = len(a), len(b)
        if abs(la - lb) > 1:
            return False
        i = j = diff = 0
        while i < la and j < lb:
            if a[i] == b[j]:
                i += 1; j += 1
                continue
            diff += 1
            if diff > 1:
                return False
            if la == lb:
                i += 1; j += 1
            elif la > lb:
                i += 1
            else:
                j += 1
        return diff + (la - i) + (lb - j) <= 1

    _hpos_w = {s["name"].lower(): (hero_pos[s["name"]][0] * SVG_SCALE, hero_pos[s["name"]][1] * SVG_SCALE)
               for s in data["systems"] if s["name"] in hero_pos}

    _ROMAN = re.compile(r"\s+(?:i|ii|iii|iv|v|vi|vii|viii|ix|x|xi|xii)$")

    def _is_ghost(nm, wx, wy):
        n = nm.lower()
        n2 = _ROMAN.sub("", n)
        for hname, (hx, hy) in _hpos_w.items():
            if (hx - wx) ** 2 + (hy - wy) ** 2 < 120 ** 2 and (_lev1(n, hname) or n2 == hname):
                return True
        return False

    galaxy, named = [], set()
    for s in svg["systems"]:
        disp = SVG_ALIASES.get(s["name"], s["name"])
        if disp.lower() in hero_names or disp.lower() in named:
            continue
        named.add(disp.lower())
        v = vendor_by_name.get(disp.lower(), {})
        pv = _vendor_pos(v) if v else None
        sector = (v.get("Sector") or "").replace(" Sector", "").strip() if v else ""
        region = REGION_NORM.get((v.get("Region") or "").strip(), (v.get("Region") or "").strip()) if v else ""
        wx, wy = W(s["x"], s["y"])
        if _is_ghost(disp, wx, wy):
            continue
        galaxy.append([disp, wx, wy, pv[2] if pv else "", sector, region, 1])
    for e in vendor_planets:
        nm = (e.get("Name") or "").strip()
        if not nm or nm.lower() in hero_names or nm.lower() in named:
            continue
        pv = _vendor_pos(e)
        if not pv:
            continue
        named.add(nm.lower())
        fx, fy = fit(pv[0] / SQ, pv[1] / SQ)
        wx, wy = W(fx, fy)
        sector = (e.get("Sector") or "").replace(" Sector", "").strip()
        region = REGION_NORM.get((e.get("Region") or "").strip(), (e.get("Region") or "").strip())
        if _is_ghost(nm, wx, wy):
            continue
        galaxy.append([nm, wx, wy, pv[2], sector, region, 0])
    # ---- worlds the atlas doesn't mark but the chart should (docs/setting/extra-worlds.json):
    # canon-era worlds, notable moons, stations. Each anchors to an existing dot/hero (or an
    # earlier extra) or to raw xy, plus an offset; grid/sector/region override the anchor's.
    # The sibling-gathering pass below then pulls same-system worlds together like any moon.
    EXTRA = ROOT / "docs/setting/extra-worlds.json"
    extras = json.loads(EXTRA.read_text(encoding="utf-8"))["worlds"] if EXTRA.exists() else []
    _gidx = {g[0].lower(): g for g in galaxy}
    for s in data["systems"]:
        _gidx.setdefault(s["name"].lower(), [s["name"], s["x"], s["y"], s.get("grid", ""), "", ""])
    n_extra = 0
    for e in extras:
        nm = e["name"]
        if nm.lower() in named or nm.lower() in hero_names:
            continue
        anc = e.get("anchor") or {}
        if "dot" in anc:
            a = _gidx.get(anc["dot"].lower())
            if not a:
                print(f"  ! extra world {nm}: anchor {anc['dot']!r} not on the chart — skipped")
                continue
            ax, ay, agrid, asec, areg = a[1], a[2], a[3], a[4], a[5]
        elif "xy" in anc:
            ax, ay = anc["xy"]; agrid = asec = areg = ""
        else:
            print(f"  ! extra world {nm}: no anchor — skipped")
            continue
        row = [nm, round(ax + e.get("dx", 0), 1), round(ay + e.get("dy", 0), 1),
               e.get("grid") or agrid, e.get("sector") or asec, e.get("region") or areg, 1 if e.get("tier") else 0]
        galaxy.append(row); named.add(nm.lower()); _gidx[nm.lower()] = row; n_extra += 1
    if n_extra:
        print(f"  {n_extra} extra worlds placed from {EXTRA.name}")
    bright_cfg = json.loads(EXTRA.read_text(encoding="utf-8")).get("bright") if EXTRA.exists() else None
    if bright_cfg:  # the bright tier is a curated allowlist, not the atlas's "major world" flag
        want = {n.lower() for L in bright_cfg.values() for n in L}
        for g in galaxy:
            g[6] = 1 if g[0].lower() in want else 0
        on = {g[0].lower() for g in galaxy if g[6]}
        missing = sorted(want - on - hero_names)
        print(f"  bright tier: {len(on)} worlds from the allowlist" + (f"; not on chart: {missing}" if missing else ""))
    # ---- sibling planets of one star system sit together: the atlas scatters them across
    # the sector with sub-grid guesses; on a chart a system is one tight cluster. System
    # membership comes from the Wookieepedia pulls ("system" fact); anchor = the hero or
    # dot bearing the system's name, else a drawn member, else the group's centroid.
    gwp_all = json.loads(GWP.read_text(encoding="utf-8")) if GWP.exists() else {}
    # ---- region from the world's own article when it has one: the atlas's region column is
    # wrong for ~900 of 5,500 dots (Lothal "Inner Rim", Nal Hutta "Mid Rim", Csilla "Wild Space")
    REGION_WP = [("Deep Core", "Deep Core"), ("Outer Rim", "Outer Rim"), ("Mid Rim", "Mid Rim"), ("Inner Rim", "Inner Rim"),
                 ("Expansion Region", "Expansion Region"), ("Colonies", "Colonies"), ("Core", "Core"),
                 ("Unknown Regions", "Unknown Regions"), ("Wild Space", "Wild Space"), ("Hutt Space", "Hutt Space"),
                 ("New Territories", "Outer Rim"), ("Western Reaches", "Outer Rim"), ("The Slice", None)]
    fixed = 0
    for g in galaxy:
        e = gwp_all.get(g[0])
        if not e or e.get("missing"):
            continue
        first = re.split(r"[,;]|\n", (e.get("facts") or {}).get("region", ""))[0].strip()
        reg = next((v for k, v in REGION_WP if first.startswith(k)), None)
        if reg and reg != g[5]:
            g[5] = reg; fixed += 1
    if fixed:
        print(f"  {fixed} dot regions corrected from their Wookieepedia articles")
    # ---- placement audit: the atlas drops some worlds thousands of units from their Standard
    # Galactic Grid square (Core worlds out past the Unknown Regions). Cell centroids are built
    # from dots whose atlas grid agrees with their article; any dot farther than ~1.2 cells from
    # its article's cell is moved into that cell (deterministic jitter so they don't stack).
    import hashlib
    def _agrid(g):
        e = gwp_all.get(g[0])
        return (e.get("facts") or {}).get("grid", "") if e and not e.get("missing") else ""
    cells = {}
    for g in galaxy:
        ag = _agrid(g)
        if ag and ag == g[3]:
            cells.setdefault(ag, []).append((g[1], g[2]))
    for g in galaxy:  # fallback: cells with no agreeing dots use every dot the atlas put there
        if g[3] and g[3] not in cells:
            cells.setdefault("~" + g[3], []).append((g[1], g[2]))
    cent = {k: (sum(p[0] for p in v) / len(v), sum(p[1] for p in v) / len(v)) for k, v in cells.items()}
    cent.update({k[1:]: v for k, v in cent.items() if k.startswith("~") and k[1:] not in cent})
    # cell size: median x-gap between horizontally adjacent lettered columns
    cols = {}
    for k, (cx, cy) in cent.items():
        if k[0] != "~" and "-" in k:
            cols.setdefault(k.split("-")[0], []).append(cx)
    colx = sorted((sum(v) / len(v), L) for L, v in cols.items() if len(v) >= 3)
    gaps = sorted(colx[i + 1][0] - colx[i][0] for i in range(len(colx) - 1))
    cell = gaps[len(gaps) // 2] if gaps else 380.0
    moved = 0
    for g in galaxy:
        ag = _agrid(g)
        if not ag or ag not in cent or ag == g[3]:
            continue
        cx, cy = cent[ag]
        if ((g[1] - cx) ** 2 + (g[2] - cy) ** 2) ** 0.5 <= 1.2 * cell:
            continue
        h = int(hashlib.md5(g[0].encode("utf-8")).hexdigest()[:8], 16)
        jx, jy = ((h & 0xffff) / 0xffff - 0.5) * 0.6 * cell, ((h >> 16) / 0xffff - 0.5) * 0.6 * cell
        g[1], g[2], g[3] = round(cx + jx, 1), round(cy + jy, 1), ag
        moved += 1
    if moved:
        print(f"  {moved} dots relocated into their article's grid square (cell ~{cell:.0f} units)")
    def _asec(g):
        e = gwp_all.get(g[0])
        s = (e.get("facts") or {}).get("sector", "") if e and not e.get("missing") else ""
        return re.sub(r"\s+sector$", "", s.split(",")[0].strip(), flags=re.I).lower()
    secs, regs = {}, {}
    for g in galaxy:
        ag = _agrid(g)
        if ag and ag == g[3]:  # only dots we trust
            s = _asec(g)
            if s:
                secs.setdefault(s, []).append((g[1], g[2]))
            if g[5]:
                regs.setdefault(g[5], []).append((g[1], g[2]))
    secc = {k: (sum(p[0] for p in v) / len(v), sum(p[1] for p in v) / len(v)) for k, v in secs.items() if len(v) >= 3}
    regc = {k: (sum(p[0] for p in v) / len(v), sum(p[1] for p in v) / len(v)) for k, v in regs.items() if len(v) >= 20}
    moved2 = 0
    for g in galaxy:
        if _agrid(g):
            continue  # handled above
        e = gwp_all.get(g[0])
        if not e or e.get("missing"):
            continue
        s = _asec(g)
        if s in secc:
            cx, cy = secc[s]; lim = 1.5 * cell
        elif g[5] in regc:
            cx, cy = regc[g[5]]; lim = 4.0 * cell  # regions are big; only rescue the absurd
        else:
            continue
        if ((g[1] - cx) ** 2 + (g[2] - cy) ** 2) ** 0.5 <= lim:
            continue
        h = int(hashlib.md5(g[0].encode("utf-8")).hexdigest()[:8], 16)
        jx, jy = ((h & 0xffff) / 0xffff - 0.5) * 0.8 * cell, ((h >> 16) / 0xffff - 0.5) * 0.8 * cell
        g[1], g[2], g[3] = round(cx + jx, 1), round(cy + jy, 1), ""
        moved2 += 1
    if moved2:
        print(f"  {moved2} gridless dots relocated by article sector/region")
    _base = lambda s: re.sub(r"\s+system$", "", s.strip(), flags=re.I).strip().lower()
    groups = {}
    for i, g in enumerate(galaxy):
        e = gwp_all.get(g[0])
        sysn = (e.get("facts") or {}).get("system") if e and not e.get("missing") else None
        if sysn and (sysn.lower().endswith("systems") or "," in sysn or "outlier" in sysn.lower()):
            sysn = None  # not a single star system
        if sysn:
            groups.setdefault(_base(sysn), []).append(i)
    name_idx = {g[0].lower(): i for i, g in enumerate(galaxy)}
    collapsed = 0
    sib_idx = set()  # dots that sit together because they share a star system (moons, co-orbitals)
    for sysname, idxs in groups.items():
        anchor_i = None
        if sysname in _hpos_w:
            ax, ay = _hpos_w[sysname]
        elif sysname in name_idx:
            anchor_i = name_idx[sysname]
            ax, ay = galaxy[anchor_i][1], galaxy[anchor_i][2]
        else:
            drawn = [i for i in idxs if galaxy[i][6]]
            if drawn:
                anchor_i = drawn[0]
                ax, ay = galaxy[anchor_i][1], galaxy[anchor_i][2]
            elif len(idxs) > 1:
                ax = sum(galaxy[i][1] for i in idxs) / len(idxs)
                ay = sum(galaxy[i][2] for i in idxs) / len(idxs)
            else:
                continue
        if len(idxs) > 1 or anchor_i is not None:
            sib_idx.update(idxs)
            if anchor_i is not None:
                sib_idx.add(anchor_i)
        for i in idxs:
            if i == anchor_i:
                continue
            if abs(galaxy[i][1] - ax) > 0.5 or abs(galaxy[i][2] - ay) > 0.5:
                galaxy[i][1], galaxy[i][2] = round(ax, 1), round(ay, 1)
                collapsed += 1
    if collapsed:
        print(f"  {collapsed} sibling planets gathered onto their systems ({len(groups)} systems known)")

    # ---- spread stacked background dots: several systems sharing one coarse vendor
    # coordinate render as one anonymous dot — fan them into a small ring instead
    from collections import defaultdict as _dd
    _stacks = _dd(list)
    for i, g in enumerate(galaxy):
        _stacks[(round(g[1], 1), round(g[2], 1))].append(i)
    import math as _math
    GA = _math.pi * (3 - 5 ** 0.5)  # golden angle
    for key, idxs in _stacks.items():
        if len(idxs) < 2:
            continue
        idxs.sort(key=lambda i: galaxy[i][0])
        tight = all(i in sib_idx for i in idxs)
        for k, i in enumerate(idxs):
            r = (2.5 + 1.6 * (k ** 0.5)) if tight else (7.0 + 4.5 * (k ** 0.5))
            a = k * GA
            galaxy[i][1] = round(galaxy[i][1] + r * _math.cos(a), 1)
            galaxy[i][2] = round(galaxy[i][2] + r * _math.sin(a), 1)

    data["galaxy"] = galaxy

    # ---- nav graph: systems snapped to each polyline in arc order
    node_pos = {s["name"]: (s["x"], s["y"]) for s in data["systems"]}
    for g in galaxy:
        node_pos.setdefault(g[0], (g[1], g[2]))
    by_id = {s["id"]: s["name"] for s in data["systems"]}
    lane_kind = {}
    for l in data["lanes"]:
        lane_kind[tuple(sorted((by_id[l["from"]], by_id[l["to"]])))] = l["kind"]
    edges, seen = [], set()
    SNAP = 7.5 * SVG_SCALE

    def poly_slice(pts, arcs, a, b):
        lo, hi = (a, b) if a <= b else (b, a)
        out = [list(_point_at_arc(pts, arcs, lo))]
        for pt, s in zip(pts, arcs):
            if lo < s < hi:
                out.append(list(pt))
        out.append(list(_point_at_arc(pts, arcs, hi)))
        if a > b:
            out.reverse()
        return [[round(x, 1), round(y, 1)] for x, y in out]
    for r in routes:
        pts_w = [[round(x * SVG_SCALE, 1), round(y * SVG_SCALE, 1)] for x, y in r["pts"]]
        arcs_w = _arc_positions(pts_w)
        onroute = []
        for name, (x, y) in node_pos.items():
            d2, arc, _, _ = _nearest_on_poly(pts_w, arcs_w, x, y)
            if d2 < SNAP ** 2:
                onroute.append((arc, name))
        onroute.sort()
        for (_, a2), (_, b2) in zip(onroute, onroute[1:]):
            if a2 == b2:
                continue
            key = tuple(sorted((a2, b2)))
            if key in seen:
                continue
            seen.add(key)
            WBOX = (4130, 6270, 5010, 6810)  # the withered interior of the Reach, world coords
            def _wb(n):
                x, y = node_pos[n]
                return WBOX[0] < x < WBOX[2] and WBOX[1] < y < WBOX[3]
            kind = lane_kind.get(key)
            if kind is None:
                kind = "dark" if (_wb(a2) and _wb(b2)) else "route"
            edges.append([a2, b2, kind, r["name"]])
        r["pts_w"] = pts_w
    for l in data["lanes"]:
        a2, b2 = by_id[l["from"]], by_id[l["to"]]
        key = tuple(sorted((a2, b2)))
        if key not in seen:
            seen.add(key)
            edges.append([a2, b2, l["kind"], l.get("name", "")])
    # campaign lanes ride the drawn route geometry wherever the vector map draws it;
    # short connectors bridge node-center to stroke (big ellipses stand off their strokes).
    LANE_ROUTE = {"Triellus": "Triellus Trade Route"}
    routes_w = []
    for r in routes:
        pw = [[round(x * SVG_SCALE, 1), round(y * SVG_SCALE, 1)] for x, y in r["pts"]]
        routes_w.append({"name": r["name"], "pts": pw, "arcs": _arc_positions(pw)})
    lane_segs = []
    for l in data["lanes"]:
        na, nb = by_id[l["from"]], by_id[l["to"]]
        pa, pb = node_pos[na], node_pos[nb]
        straight = ((pa[0] - pb[0]) ** 2 + (pa[1] - pb[1]) ** 2) ** 0.5
        lname = LANE_ROUTE.get(l.get("name", ""), l.get("name", ""))
        named = [r for r in routes_w if r["name"] == lname]
        lim = (52 if named else 9) * SVG_SCALE
        best = None
        for r in (named or routes_w):
            da, aa, _, _ = _nearest_on_poly(r["pts"], r["arcs"], *pa)
            db, ab, _, _ = _nearest_on_poly(r["pts"], r["arcs"], *pb)
            da, db = da ** 0.5, db ** 0.5
            if da > lim or db > lim:
                continue
            span = abs(aa - ab)
            # the ride must be worth it: node->stroke->node stays near straight-line,
            # and the on-stroke stretch is a real fraction of the trip
            if da + span + db > straight * 1.7 or span < straight * 0.15:
                continue
            if best is None or da + db < best[0]:
                best = (da + db, r, aa, ab)
        ends = [[round(pa[0], 1), round(pa[1], 1)], [round(pb[0], 1), round(pb[1], 1)]]
        if best:
            _, r, aa, ab = best
            pts = [ends[0]] + poly_slice(r["pts"], r["arcs"], aa, ab) + [ends[1]]
        else:
            pts = ends
        lane_segs.append({"from": l["from"], "to": l["to"], "kind": l["kind"], "name": l.get("name", ""), "pts": pts})
    data["laneSegs"] = lane_segs
    data["routes"] = [{"n": r["name"], "major": r["major"], "pts": r["pts_w"]} for r in routes]
    data["nav"] = {"pos": {n: [p[0], p[1]] for n, p in node_pos.items() if any(n in (e[0], e[1]) for e in edges)}, "edges": edges}
    data["regionPaths"] = [{"kind": rg["kind"], "pts": [[round(x * SVG_SCALE, 1), round(y * SVG_SCALE, 1)] for x, y in rg["pts"]]} for rg in svg.get("regions", [])]
    # sector centroids for the grouped-label zoom tier; 1-planet sectors count as sectorless
    sectors = {}
    for g in galaxy:
        if g[4]:
            sectors.setdefault(g[4], []).append((g[1], g[2]))
    for s in data["systems"]:
        wpf = (s.get("wp") or {}).get("facts") or {}
        sec = (wpf.get("sector") or "").replace(" sector", "").replace(" Sector", "").strip()
        if sec:
            sectors.setdefault(sec, []).append((s["x"], s["y"]))
    data["sectors"] = [[name, round(sum(x for x, _ in pts) / len(pts), 1), round(sum(y for _, y in pts) / len(pts), 1), len(pts)]
                       for name, pts in sorted(sectors.items()) if len(pts) >= 2]
    lone = {name for name, pts in sectors.items() if len(pts) < 2}
    for g in galaxy:
        if g[4] in lone:
            g[4] = ""
    print(f"svg build: fit over {nfit} names · {len(galaxy)} background ({sum(1 for g in galaxy if g[6])} named) · "
          f"{len(routes)} routes · {len(edges)} edges · majors: {sorted({r['name'] for r in routes if r['major']})}")
    anchors = {n: node_pos[n] for n in ("Coruscant", "Darkknell", "Bannistar Station", "Eriadu", "Enarc", "Ruusan", "Kashyyyk", "Corellia", "Naboo", "Omwat", "Terminus", "Bonadan") if n in node_pos}
    print("ANCHORS:", {k: (round(v[0]), round(v[1])) for k, v in anchors.items()})


def load_data() -> dict:
    data = json.loads(DATA.read_text(encoding="utf-8"))
    if WOOKIEEPEDIA.exists():
        data = merge_wookieepedia(data, json.loads(WOOKIEEPEDIA.read_text(encoding="utf-8")))
    build_network(data)
    if GWP.exists():
        merge_galaxy_wookieepedia(data, json.loads(GWP.read_text(encoding="utf-8")))
    # history presentations (player-safe): every JSON in docs/setting/presentations
    pdir = ROOT / "docs/setting/presentations"
    data["presentations"] = [json.loads(p.read_text(encoding="utf-8")) for p in sorted(pdir.glob("*.json"))] if pdir.exists() else []
    return data


def strip_gm(data: dict) -> dict:
    d = copy.deepcopy(data)
    for s in d["systems"]:
        s.pop("gm", None)
    d.pop("gwpGm", None)
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
    wpbase = "wp/" if edition == "player" else "player-aids/wp/"
    out = template.replace("__DATA__", payload).replace("__EDITION__", edition).replace("__WPBASE__", wpbase)
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
