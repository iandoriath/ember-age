#!/usr/bin/env python3
"""Batch-pull Wookieepedia (Legends) infobox facts + lead paragraphs for the
chart's background planets — pure MediaWiki API, no LLM anywhere, no images.

    python tools/fetch-wookieepedia-galaxy.py                    # Reach neighbourhood (default box)
    python tools/fetch-wookieepedia-galaxy.py --box 3900 5600 5450 7250
    python tools/fetch-wookieepedia-galaxy.py --names Fiviune,Arbra
    python tools/fetch-wookieepedia-galaxy.py --all              # every named dot on the chart
    python tools/fetch-wookieepedia-galaxy.py --refresh --limit 50

Titles resolve in batches of 50 per HTTP request ("Name/Legends" sweep, then
plain "Name"); wikitext comes back 20 pages per request. Reruns skip names
already in docs/setting/wookieepedia-galaxy.json (--refresh to redo). The map
builder merges the file player-safe: facts subset for everyone, era-spanning
leads GM-only. Text is CC BY-SA (Wookieepedia contributors).
"""
import argparse
import importlib.util
import json
import re
import sys
import time
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "docs/setting/wookieepedia-galaxy.json"
IMG_DIR = ROOT / "player-aids/wp"
THUMB = 320
LEAD_MAX = 600
SLEEP = 0.6


def _load(modname, path):
    spec = importlib.util.spec_from_file_location(modname, path)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


wp = _load("fetch_wookieepedia", ROOT / "tools/fetch-wookieepedia.py")


def api(**params):
    params.setdefault("maxlag", 5)
    return wp.api(**params)


def batches(seq, n):
    for i in range(0, len(seq), n):
        yield seq[i:i + n]


def resolve_many(names):
    """Map chart name -> canonical article title. Tries Name/Legends, then Name."""
    resolved, remaining = {}, list(names)
    for suffix in ("/Legends", ""):
        if not remaining:
            break
        still = []
        for group in batches(remaining, 50):
            r = api(action="query", titles="|".join(n + suffix for n in group),
                    redirects=1, prop="info")
            q = r["query"]
            norm = {x["from"]: x["to"] for x in q.get("normalized", [])}
            redir = {x["from"]: x["to"] for x in q.get("redirects", [])}
            exists = {p["title"] for p in q.get("pages", []) if not p.get("missing")}
            for n in group:
                t = n + suffix
                t = norm.get(t, t)
                t = redir.get(t, t)
                if t in exists:
                    resolved[n] = t
                else:
                    still.append(n)
            time.sleep(SLEEP)
        remaining = still
    return resolved, remaining


GRID_RE = re.compile(r"(?:coordinates|grid)\s*=[^\n]*?([A-Z]-\d{1,2})")


def backfill_grids(out):
    """Add facts.grid (Standard Galactic Grid square) to entries fetched before it was parsed."""
    todo = {n: e for n, e in out.items() if not e.get("missing") and "grid" not in (e.get("facts") or {}) and not e.get("nogrid")}
    inv = {}
    for n, e in todo.items():
        inv.setdefault(e["title"], []).append(n)
    got = 0
    titles = sorted(inv)
    for i, group in enumerate(batches(titles, 20)):
        r = api(action="query", titles="|".join(group), prop="revisions", rvprop="content", rvslots="main", redirects=1)
        q = r["query"]
        back = {}
        for x in q.get("normalized", []) + q.get("redirects", []):
            back[x["to"]] = back.get(x["from"], x["from"])
        for page in q.get("pages", []):
            if page.get("missing") or not page.get("revisions"):
                continue
            src = back.get(page["title"], page["title"])
            gm = GRID_RE.search(page["revisions"][0]["slots"]["main"]["content"])
            for n in inv.get(src, inv.get(page["title"], [])):
                if gm:
                    out[n].setdefault("facts", {})["grid"] = gm.group(1); got += 1
                else:
                    out[n]["nogrid"] = True
        if i % 20 == 0:
            print(f"  … grids {got} ({(i + 1) * 20}/{len(titles)} titles)")
        time.sleep(SLEEP)
    return got


def fetch_many(title_by_name):
    """Fetch + parse wikitext for every resolved title, 20 pages per request."""
    inv = {}
    for n, t in title_by_name.items():
        inv.setdefault(t, []).append(n)
    out = {}
    titles = sorted(inv)
    for group in batches(titles, 20):
        r = api(action="query", titles="|".join(group), prop="revisions|info",
                rvprop="content", rvslots="main", inprop="url", redirects=1)
        q = r["query"]
        back = {}
        for x in q.get("normalized", []) + q.get("redirects", []):
            back[x["to"]] = back.get(x["from"], x["from"])
        for page in q.get("pages", []):
            if page.get("missing") or not page.get("revisions"):
                continue
            src_title = back.get(page["title"], page["title"])
            wt = page["revisions"][0]["slots"]["main"]["content"]
            lead = wp.parse_lead(wt)
            if len(lead) > LEAD_MAX:
                cut = lead.rfind(". ", 0, LEAD_MAX)
                lead = lead[:cut + 1] if cut > 200 else lead[:LEAD_MAX].rstrip() + "…"
            facts = wp.parse_facts(wt)
            gm = GRID_RE.search(wt)
            if gm:
                facts["grid"] = gm.group(1)
            entry = {"title": page["title"], "url": page["fullurl"],
                     "facts": facts, "lead": lead,
                     "fetched": date.today().isoformat()}
            for n in inv.get(src_title, inv.get(page["title"], [])):
                out[n] = entry
        done = len(out)
        print(f"  … {done}/{len(title_by_name)} articles parsed")
        time.sleep(SLEEP)
    return out


# ---- entity validation: a chart dot must resolve to a PLACE, not a same-named
# character/ship/species/object. Facts are the strong signal; otherwise the lead's
# first sentence must reach a place word before it reaches a non-place word.
PLACE_FACTS = {"region", "sector", "system", "grid", "suns", "moons", "terrain", "climate",
               "atmosphere", "population", "government", "capital", "routes", "points",
               "class", "diameter", "inhabitants", "rotation", "orbit"}
PLACE_RE = re.compile(
    r"\b(planet(?:oid)?s?|moons?|worlds?|homeworld|star systems?|astronomical objects?|"
    r"celestial bod(?:y|ies)|asteroids?|nebulae?|comets?|location|settlements?|colony|city|"
    r"outposts?|stations?|spaceports?|shipyards?|territory|gas giants?|dwarf planets?)\b", re.I)
NONPLACE_RE = re.compile(
    r"\b(species|sentients?|Humans?|male|female|Jedi|Sith|captain|lieutenant|commander|general|"
    r"hunter|smuggler|pirate|officer|soldier|clone|droid|trees?|plants?|insects?|creatures?|"
    r"animals?|vehicles?|speeders?|starfighters?|cruisers?|corvettes?|frigates?|carriers?|"
    r"Star Destroyers?|starships?|gemstones?|letter|toy|painting|company|corporation|law|act|"
    r"uprising|battle|attack|event|entity|leader|alias|wife|husband|father|mother|son|daughter|"
    r"sister|brother|queen|king|empress|emperor|commentator|companion|cook|group|organization)\b", re.I)


def is_place(entry):
    """Does this fetched entry describe somewhere a ship could go?"""
    if entry.get("missing"):
        return False
    if entry.get("title", "").endswith("(disambiguation)"):
        return False
    if set(entry.get("facts") or {}) & PLACE_FACTS:
        return True
    hay = entry.get("title", "") + ". " + (entry.get("lead") or "").split(". ")[0][:220]
    pm, nm = PLACE_RE.search(hay), NONPLACE_RE.search(hay)
    return bool(pm) and (not nm or pm.start() < nm.start())


VARIANTS = ("{} (planet)/Legends", "{} (planet)", "{} system/Legends", "{} system",
            "{} (moon)/Legends", "{} (moon)")


def resolve_variants(names):
    """For names whose bare title is a different entity: try the disambiguated place titles."""
    resolved, remaining = {}, list(names)
    for pat in VARIANTS:
        if not remaining:
            break
        still = []
        for group in batches(remaining, 50):
            r = api(action="query", titles="|".join(pat.format(n) for n in group),
                    redirects=1, prop="info")
            q = r["query"]
            norm = {x["from"]: x["to"] for x in q.get("normalized", [])}
            redir = {x["from"]: x["to"] for x in q.get("redirects", [])}
            exists = {pg["title"] for pg in q.get("pages", []) if not pg.get("missing")}
            for n in group:
                tt = pat.format(n)
                tt = norm.get(tt, tt)
                tt = redir.get(tt, tt)
                if tt in exists:
                    resolved[n] = tt
                else:
                    still.append(n)
            time.sleep(SLEEP)
        remaining = still
    return resolved, remaining


def repair(out):
    """Sweep every fetched entry; re-point non-place collisions at their (planet)/system
    articles, and mark the rest missing (the dot keeps its tooltip, loses the wrong panel)."""
    suspects = [n for n, e in out.items() if not e.get("missing") and not is_place(e)]
    print(f"{len(suspects)} entries are not places (title collisions / disambiguation pages)")
    if not suspects:
        return 0
    resolved, unresolved = resolve_variants(suspects)
    print(f"place-variant articles found for {len(resolved)}; no place article for {len(unresolved)}")
    if resolved:
        fetched = fetch_many(resolved)
        for n, e in fetched.items():
            if is_place(e):
                e.pop("missing", None)
                old = out.get(n, {})
                out[n] = e
                if "image" in old or old.get("noimage"):
                    pass  # image belonged to the wrong article: refetch below
            else:
                unresolved.append(n)
    for n in unresolved:
        out[n] = {"missing": True, "note": "bare title is a different entity; no place article found",
                  "fetched": date.today().isoformat()}
    return len(suspects)


def slug(name):
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")


EXT = {"image/jpeg": "jpg", "image/png": "png", "image/webp": "webp", "image/gif": "gif"}


def fill_images(out):
    """Lead images for entries that have none yet: pageimages 50 titles/request, thumbs saved
    under player-aids/wp/<slug>.<ext>; the map references them by file, never base64."""
    IMG_DIR.mkdir(parents=True, exist_ok=True)
    todo = {n: e for n, e in out.items() if not e.get("missing") and "image" not in e and not e.get("noimage")}
    if not todo:
        return 0
    by_title = {}
    for n, e in todo.items():
        by_title.setdefault(e["title"], []).append(n)
    got = 0
    titles = sorted(by_title)
    for group in batches(titles, 50):
        r = api(action="query", titles="|".join(group), prop="pageimages", piprop="thumbnail|name",
                pithumbsize=THUMB, redirects=1)
        q = r["query"]
        back = {}
        for x in q.get("normalized", []) + q.get("redirects", []):
            back[x["to"]] = back.get(x["from"], x["from"])
        seen = set()
        for page in q.get("pages", []):
            src_title = back.get(page["title"], page["title"])
            names = by_title.get(src_title) or by_title.get(page["title"]) or []
            seen.update(names)
            thumb = page.get("thumbnail")
            if not thumb or not thumb.get("source"):
                for n in names:
                    out[n]["noimage"] = True
                continue
            try:
                data, mime = wp.fetch_bytes(thumb["source"])
            except Exception as ex:  # keep going; retry next run
                print(f"  ! {names}: {ex}")
                continue
            ext = EXT.get(mime, "jpg")
            for n in names:
                fname = f"{slug(n)}.{ext}"
                (IMG_DIR / fname).write_bytes(data)
                out[n]["image"] = {"file": fname, "width": thumb.get("width"), "height": thumb.get("height")}
                got += 1
            time.sleep(0.25)
        for tt in group:
            for n in by_title.get(tt, []):
                if n not in seen and "image" not in out[n]:
                    out[n]["noimage"] = True
        print(f"  ... images {got}/{len(todo)}")
        time.sleep(SLEEP)
    return got


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--box", nargs=4, type=float, metavar=("X0", "Y0", "X1", "Y1"),
                    default=[3900.0, 5600.0, 5450.0, 7250.0],
                    help="world-coordinate box of chart dots to cover (default: the Reach neighbourhood)")
    ap.add_argument("--names", help="comma-separated chart names instead of a box")
    ap.add_argument("--all", action="store_true", help="every named dot on the chart")
    ap.add_argument("--refresh", action="store_true", help="refetch names already in the file")
    ap.add_argument("--limit", type=int, help="cap the number of new fetches this run")
    ap.add_argument("--no-images", action="store_true", help="skip the lead-image pass")
    ap.add_argument("--grids", action="store_true", help="backfill facts.grid for entries fetched before grids were parsed")
    ap.add_argument("--repair", action="store_true",
                    help="re-validate every fetched entry: fix title collisions (character/ship/species "
                         "articles on planet names), chase (planet)/system variants, drop the rest")
    args = ap.parse_args(argv)

    bsm = _load("bsm_for_fetch", ROOT / "tools/build-system-map.py")
    data = bsm.load_data()
    heroes = {s["name"].lower() for s in data["systems"]}
    if args.names:
        targets = [n.strip() for n in args.names.split(",") if n.strip()]
    else:
        x0, y0, x1, y1 = args.box
        targets = [g[0] for g in data["galaxy"] if args.all or (x0 <= g[1] <= x1 and y0 <= g[2] <= y1)]
    targets = sorted({t for t in targets if t.lower() not in heroes})

    existing = json.loads(OUT.read_text(encoding="utf-8")) if OUT.exists() else {}
    if args.grids:
        out = dict(existing)
        n = backfill_grids(out)
        OUT.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
        print(f"wrote {OUT.relative_to(ROOT)} — {n} grid squares added")
        return 0
    if args.repair:
        out = dict(existing)
        repair(out)
        OUT.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
        got = sum(1 for e in out.values() if not e.get("missing"))
        print(f"wrote {OUT.relative_to(ROOT)} — {got} articles, "
              f"{sum(1 for e in out.values() if e.get('missing'))} missing")
        return 0
    todo = [t for t in targets if args.refresh or t not in existing]
    if args.limit:
        todo = todo[:args.limit]
    print(f"{len(targets)} targets in scope, {len(todo)} to fetch")
    out = dict(existing)
    if todo:
        resolved, missing = resolve_many(todo)
        print(f"resolved {len(resolved)} articles; no article for {len(missing)}")
        for n in missing:
            out[n] = {"missing": True, "fetched": date.today().isoformat()}
        out.update(fetch_many(resolved))
        repair(out)
    if not args.no_images:
        n_img = fill_images(out)
        print(f"lead images saved: {n_img} (in {IMG_DIR.relative_to(ROOT)})")
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    got = sum(1 for e in out.values() if not e.get("missing"))
    print(f"wrote {OUT.relative_to(ROOT)} — {got} articles, {sum(1 for e in out.values() if e.get('missing'))} missing, "
          f"{OUT.stat().st_size // 1024} KB")
    return 0


if __name__ == "__main__":
    sys.exit(main())
