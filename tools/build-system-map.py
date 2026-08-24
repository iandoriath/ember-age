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


SVG_MAP = ROOT / "docs/maps/vendor/svg_map.json"
SVG_SCALE = 9.0
SVG_ALIASES = {"Kashyyk": "Kashyyyk"}  # svg name -> our name
MAJOR_ROUTES = {"Perlemian Trade Route", "Corellinan Run", "Corellian Trade Spine", "Hydian Way", "Rimma Trade Route"}
ROUTE_RENAME = {"Corellinan Run": "Corellian Run", "Triellus Trade Run": "Triellus Trade Route"}
# canonical stop orders used to project undrawn systems onto their drawn routes
CHAINS = [
    ("Duros Space Run", ["New Cov", "Churba", "Kalarba", "Glom Tho", "Triffis", "Bannistar Station", "Enarc",
                          "Alui", "Verdanth", "Aplooine", "Sanrafsix", "Heptooine", "Jutrand", "Darkknell"]),
    ("Hydian Way", ["Darkknell", "Eriadu", "Sluis Van"]),
    ("Salin Corridor", ["Kashyyyk", "Teraab", "Ruusan"]),
    ("Randon Run", ["Kashyyyk", "Teraab", "Ruusan"]),
]


def _grid_to_colrow(grid):
    m = re.match(r"^([A-V])-(\d{1,2})$", grid or "")
    return (ord(m.group(1)) - 64, int(m.group(2))) if m else None


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

    # ---- hero positions: snap to the drawing; project the undrawn onto their routes
    hero_pos = {}
    svg_matched = set()
    for s in data["systems"]:
        hit = svg_by_name.get(s["name"].lower())
        if hit:
            hero_pos[s["name"]] = (hit["x"], hit["y"])
            svg_matched.add(s["name"])
    all_polys = [(r["pts"], r["arcs"]) for r in routes]

    def best_poly_for_pair(pa, pb, maxd=14.0):
        best, score = None, 1e18
        for pts, arcs in all_polys:
            da, arca, _, _ = _nearest_on_poly(pts, arcs, *pa)
            db, arcb, _, _ = _nearest_on_poly(pts, arcs, *pb)
            s = da ** 0.5 + db ** 0.5
            if da ** 0.5 < maxd and db ** 0.5 < maxd and s < score and abs(arca - arcb) > 1.0:
                best, score = (pts, arcs, arca, arcb), s
        return best

    for cname, members in CHAINS:
        known_idx = [i for i, m in enumerate(members) if m in hero_pos]
        for ia, ib in zip(known_idx, known_idx[1:]):
            if ib - ia < 2:
                continue  # no missing members between this pair
            pa, pb = hero_pos[members[ia]], hero_pos[members[ib]]
            pick = best_poly_for_pair(pa, pb)
            for j in range(ia + 1, ib):
                if members[j] in hero_pos:
                    continue
                frac = (j - ia) / (ib - ia)
                if pick:
                    pts, arcs, arca, arcb = pick
                    x, y = _point_at_arc(pts, arcs, arca + frac * (arcb - arca))
                else:
                    x, y = pa[0] + frac * (pb[0] - pa[0]), pa[1] + frac * (pb[1] - pa[1])
                hero_pos[members[j]] = (round(x, 2), round(y, 2))
        # members hanging off either end of the known span: nudge off the end anchor toward the next known point on the same heading
        if known_idx:
            first, last = known_idx[0], known_idx[-1]
            for j in range(first - 1, -1, -1):
                if members[j] in hero_pos:
                    continue
                ax, ay = hero_pos[members[j + 1]]
                bx, by = hero_pos[members[min(j + 2, len(members) - 1)]]
                hero_pos[members[j]] = (round(ax + (ax - bx) * 0.8, 2), round(ay + (ay - by) * 0.8, 2))
            for j in range(last + 1, len(members)):
                if members[j] in hero_pos:
                    continue
                ax, ay = hero_pos[members[j - 1]]
                bx, by = hero_pos[members[max(j - 2, 0)]]
                hero_pos[members[j]] = (round(ax + (ax - bx) * 0.8, 2), round(ay + (ay - by) * 0.8, 2))
    # region-anchored stragglers (no drawn route): place near a fitted grid position
    placed_by_fit = set()
    for s in data["systems"]:
        if s["name"] not in hero_pos:
            g = _grid_to_colrow(s.get("grid"))
            if g:
                x, y = fit(g[0] - 0.5, g[1] - 0.5)
                hero_pos[s["name"]] = (round(x, 2), round(y, 2))
                placed_by_fit.add(s["name"])
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
        galaxy.append([nm, wx, wy, pv[2], sector, region, 0])
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
