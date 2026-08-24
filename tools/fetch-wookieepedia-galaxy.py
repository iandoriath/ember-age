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
import sys
import time
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "docs/setting/wookieepedia-galaxy.json"
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
            entry = {"title": page["title"], "url": page["fullurl"],
                     "facts": wp.parse_facts(wt), "lead": lead,
                     "fetched": date.today().isoformat()}
            for n in inv.get(src_title, inv.get(page["title"], [])):
                out[n] = entry
        done = len(out)
        print(f"  … {done}/{len(title_by_name)} articles parsed")
        time.sleep(SLEEP)
    return out


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--box", nargs=4, type=float, metavar=("X0", "Y0", "X1", "Y1"),
                    default=[3900.0, 5600.0, 5450.0, 7250.0],
                    help="world-coordinate box of chart dots to cover (default: the Reach neighbourhood)")
    ap.add_argument("--names", help="comma-separated chart names instead of a box")
    ap.add_argument("--all", action="store_true", help="every named dot on the chart")
    ap.add_argument("--refresh", action="store_true", help="refetch names already in the file")
    ap.add_argument("--limit", type=int, help="cap the number of new fetches this run")
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
    todo = [t for t in targets if args.refresh or t not in existing]
    if args.limit:
        todo = todo[:args.limit]
    print(f"{len(targets)} targets in scope, {len(todo)} to fetch")
    if not todo:
        print("nothing to do")
        return 0

    resolved, missing = resolve_many(todo)
    print(f"resolved {len(resolved)} articles; no article for {len(missing)}")
    entries = fetch_many(resolved)

    out = dict(existing)
    for n in missing:
        out[n] = {"missing": True, "fetched": date.today().isoformat()}
    out.update(entries)
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    got = sum(1 for e in out.values() if not e.get("missing"))
    print(f"wrote {OUT.relative_to(ROOT)} — {got} articles, {sum(1 for e in out.values() if e.get('missing'))} missing, "
          f"{OUT.stat().st_size // 1024} KB")
    return 0


if __name__ == "__main__":
    sys.exit(main())
