#!/usr/bin/env python3
"""Extract systems, hyperlane polylines and region borders from the vector galaxy map.

Reads docs/maps/"StarWars Galaxy Map.svg" (Inkscape layers: PrimarySystems, SubSystems,
Major Routes, Space Lanes, Regions, Hutts) and writes docs/maps/vendor/svg_map.json:

  {"systems": [{"name", "x", "y", "primary"}...],        # SVG user units, layer transforms applied
   "routes":  [{"pts": [[x,y]...], "major": bool}...],   # sampled from the path beziers
   "regions": [{"pts": [[x,y]...], "kind": "border"|"hutt"}...]}

No raster processing — the drawing's own geometry is the source of truth.
"""
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SVG = ROOT / "docs/maps/StarWars Galaxy Map.svg"
OUT = ROOT / "docs/maps/vendor/svg_map.json"

NUM = re.compile(r"[-+]?(?:\d*\.\d+|\d+\.?)(?:[eE][-+]?\d+)?")


def layer_blocks(text: str) -> dict:
    starts = [(m.start(), m.group(1)) for m in re.finditer(r'<g\b[^>]*inkscape:label="([^"]+)"[^>]*>', text)]
    starts.sort()
    blocks = {}
    for (s, label), nxt in zip(starts, starts[1:] + [(len(text), "END")]):
        blocks[label] = text[s:nxt[0]]
    return blocks


def layer_translate(block: str) -> tuple:
    m = re.search(r'transform="translate\(([^)]+)\)"', block[:block.index(">") + 1])
    if not m:
        return 0.0, 0.0
    parts = [float(x) for x in NUM.findall(m.group(1))]
    return (parts[0], parts[1] if len(parts) > 1 else 0.0)


def parse_systems(block: str, primary: bool) -> list:
    tx, ty = layer_translate(block)
    ells = [(float(m.group("cx")), float(m.group("cy")))
            for m in re.finditer(r'<ellipse\b[^>]*?\bcx="(?P<cx>[-\d.eE]+)"[^>]*?\bcy="(?P<cy>[-\d.eE]+)"', block, flags=re.S)]
    # ellipse attribute order varies; second pass for cy-before-cx forms
    for m in re.finditer(r'<ellipse\b(?P<attrs>[^>]*)>', block, flags=re.S):
        a = m.group("attrs")
        cx = re.search(r'\bcx="([-\d.eE]+)"', a)
        cy = re.search(r'\bcy="([-\d.eE]+)"', a)
        if cx and cy:
            pt = (float(cx.group(1)), float(cy.group(1)))
            ells.append(pt)
    # markers are drawn as concentric rings — same center repeated with float jitter;
    # collapse to one marker per center so ghost twins can't soak up label pairings
    dedup, seenc = [], set()
    for ex, ey in ells:
        key = (round(ex, 1), round(ey, 1))
        if key not in seenc:
            seenc.add(key)
            dedup.append((ex, ey))
    ells = dedup
    labels = []
    def attach(name, x, y):
        name = re.sub(r"\s+", " ", name).strip()
        if name:
            labels.append((name, x, y))

    for m in re.finditer(r'<text\b(?P<attrs>[^>]*)>(?P<inner>.*?)</text>', block, flags=re.S):
        a = m.group("attrs")
        xm = re.search(r'\bx="([-\d.eE]+)"', a)
        ym = re.search(r'\by="([-\d.eE]+)"', a)
        tspans = list(re.finditer(r'<tspan\b(?P<ta>[^>]*)>(?P<tc>[^<>]*)</tspan>', m.group("inner"), flags=re.S))
        placed = False
        for ts in tspans:
            ta, tc = ts.group("ta"), ts.group("tc")
            txm = re.search(r'\bx="([-\d.eE]+)"', ta)
            tym = re.search(r'\by="([-\d.eE]+)"', ta)
            if txm and tym and tc.strip():
                attach(tc, float(txm.group(1)), float(tym.group(1)))
                placed = True
        if not placed and xm and ym:
            joined = " ".join(s.group("tc").strip() for s in tspans if s.group("tc").strip()) or re.sub(r"<[^>]+>", " ", m.group("inner"))
            attach(joined, float(xm.group(1)), float(ym.group(1)))
    # exclusive one-to-one pairing: nearest label-ellipse pairs claim each other first,
    # so stacked tspans ("Corellia"/"Duro") and big-styled capitals can't steal a
    # neighbour's marker (Coruscant used to land on N'Zoth's ellipse).
    cand = []
    for li, (name, x, y) in enumerate(labels):
        for ei, (ex, ey) in enumerate(ells):
            d = (ex - x) ** 2 + (ey - y) ** 2
            if d < 30 ** 2:
                cand.append((d, li, ei))
    cand.sort()
    out, used_l, used_e = [], set(), set()
    def sweep(pairs):
        for d, li, ei in pairs:
            if li in used_l or ei in used_e:
                continue
            used_l.add(li); used_e.add(ei)
            name = labels[li][0]; ex, ey = ells[ei]
            out.append({"name": name, "x": round(ex + tx, 2), "y": round(ey + ty, 2), "primary": primary})
    sweep(cand)
    # leftovers (dense clusters, big-styled capital labels): nearest FREE ellipse, wider net
    wide = []
    for li, (name, x, y) in enumerate(labels):
        if li in used_l:
            continue
        for ei, (ex, ey) in enumerate(ells):
            if ei in used_e:
                continue
            d = (ex - x) ** 2 + (ey - y) ** 2
            if d < 60 ** 2:
                wide.append((d, li, ei))
    wide.sort()
    sweep(wide)
    return out


def sample_path(d: str, tx: float, ty: float, seg_samples: int = 14) -> list:
    tokens = re.findall(r"[MmLlHhVvCcSsQqTtAaZz]|" + NUM.pattern, d)
    i, cmd = 0, None
    cur = (0.0, 0.0); start = (0.0, 0.0); prev_ctrl = None
    polys, pts = [], []

    def flushpts():
        nonlocal pts
        if len(pts) > 1:
            polys.append(pts)
        pts = []

    def num():
        nonlocal i
        v = float(tokens[i]); i += 1
        return v

    def bez(p0, p1, p2, p3):
        for k in range(1, seg_samples + 1):
            u = k / seg_samples
            w = 1 - u
            x = w**3 * p0[0] + 3 * w * w * u * p1[0] + 3 * w * u * u * p2[0] + u**3 * p3[0]
            y = w**3 * p0[1] + 3 * w * w * u * p1[1] + 3 * w * u * u * p2[1] + u**3 * p3[1]
            pts.append((x, y))

    while i < len(tokens):
        tok = tokens[i]
        if re.match(r"^[MmLlHhVvCcSsQqTtAaZz]$", tok):
            cmd = tok; i += 1
            if cmd in "Zz":
                if pts and start:
                    pts.append(start)
                flushpts()
                cur = start
                continue
        if cmd is None:
            i += 1
            continue
        rel = cmd.islower()
        c = cmd.lower()
        if c == "m":
            x, y = num(), num()
            if rel:
                x += cur[0]; y += cur[1]
            flushpts()
            cur = (x, y); start = cur; pts = [cur]
            cmd = "l" if rel else "L"  # subsequent pairs are linetos
            prev_ctrl = None
        elif c == "l":
            x, y = num(), num()
            if rel:
                x += cur[0]; y += cur[1]
            cur = (x, y); pts.append(cur); prev_ctrl = None
        elif c == "h":
            x = num()
            if rel:
                x += cur[0]
            cur = (x, cur[1]); pts.append(cur); prev_ctrl = None
        elif c == "v":
            y = num()
            if rel:
                y += cur[1]
            cur = (cur[0], y); pts.append(cur); prev_ctrl = None
        elif c == "c":
            x1, y1, x2, y2, x, y = num(), num(), num(), num(), num(), num()
            if rel:
                x1 += cur[0]; y1 += cur[1]; x2 += cur[0]; y2 += cur[1]; x += cur[0]; y += cur[1]
            bez(cur, (x1, y1), (x2, y2), (x, y))
            prev_ctrl = (x2, y2); cur = (x, y)
        elif c == "s":
            x2, y2, x, y = num(), num(), num(), num()
            if rel:
                x2 += cur[0]; y2 += cur[1]; x += cur[0]; y += cur[1]
            x1, y1 = (2 * cur[0] - prev_ctrl[0], 2 * cur[1] - prev_ctrl[1]) if prev_ctrl else cur
            bez(cur, (x1, y1), (x2, y2), (x, y))
            prev_ctrl = (x2, y2); cur = (x, y)
        elif c == "q":
            x1, y1, x, y = num(), num(), num(), num()
            if rel:
                x1 += cur[0]; y1 += cur[1]; x += cur[0]; y += cur[1]
            c1 = (cur[0] + 2 / 3 * (x1 - cur[0]), cur[1] + 2 / 3 * (y1 - cur[1]))
            c2 = (x + 2 / 3 * (x1 - x), y + 2 / 3 * (y1 - y))
            bez(cur, c1, c2, (x, y))
            prev_ctrl = (x1, y1); cur = (x, y)
        elif c == "t":
            x, y = num(), num()
            if rel:
                x += cur[0]; y += cur[1]
            x1, y1 = (2 * cur[0] - prev_ctrl[0], 2 * cur[1] - prev_ctrl[1]) if prev_ctrl else cur
            c1 = (cur[0] + 2 / 3 * (x1 - cur[0]), cur[1] + 2 / 3 * (y1 - cur[1]))
            c2 = (x + 2 / 3 * (x1 - x), y + 2 / 3 * (y1 - y))
            bez(cur, c1, c2, (x, y))
            prev_ctrl = (x1, y1); cur = (x, y)
        elif c == "a":  # rare here; approximate with a line
            for _ in range(5):
                num()
            x, y = num(), num()
            if rel:
                x += cur[0]; y += cur[1]
            cur = (x, y); pts.append(cur); prev_ctrl = None
        else:
            i += 1
    flushpts()
    out = []
    for poly in polys:
        # decimate: keep every point but round; drop consecutive dupes
        clean = []
        for x, y in poly:
            p = (round(x + tx, 2), round(y + ty, 2))
            if not clean or (abs(clean[-1][0] - p[0]) + abs(clean[-1][1] - p[1])) > 0.75:
                clean.append(p)
        if len(clean) > 1:
            out.append([list(p) for p in clean])
    return out


def parse_paths(block: str) -> list:
    tx, ty = layer_translate(block)
    polys = []
    for m in re.finditer(r'<path\b(?P<attrs>[^>]*?)/?>', block, flags=re.S):
        a = m.group("attrs")
        dm = re.search(r'(?<![a-z\-])d="([^"]+)"', a)
        if not dm:
            continue
        polys.extend(sample_path(dm.group(1), tx, ty))
    return polys


def main() -> int:
    text = SVG.read_text(encoding="utf-8", errors="replace")
    blocks = layer_blocks(text)
    systems = parse_systems(blocks["PrimarySystems"], True) + parse_systems(blocks["SubSystems"], False)
    majors = parse_paths(blocks["Major Routes"])
    lanes = parse_paths(blocks["Space Lanes"])
    regions = [{"pts": p, "kind": "border"} for p in parse_paths(blocks["Regions"])]
    regions += [{"pts": p, "kind": "hutt"} for p in parse_paths(blocks["Hutts"])]
    routes = [{"pts": p, "major": True} for p in majors] + [{"pts": p, "major": False} for p in lanes]
    OUT.write_text(json.dumps({"systems": systems, "routes": routes, "regions": regions}, ensure_ascii=False), encoding="utf-8")
    npts = sum(len(r["pts"]) for r in routes)
    print(f"systems: {len(systems)} ({sum(1 for s in systems if s['primary'])} primary) · route polylines: {len(routes)} ({npts} pts) · region paths: {len(regions)} -> {OUT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
