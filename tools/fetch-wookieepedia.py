#!/usr/bin/env python3
"""Pull Wookieepedia (Legends) summaries and lead images for the systems in
docs/setting/systems.json, into docs/setting/wookieepedia.json.

The builder merges that file into both map editions: image + infobox facts for
everyone, the lead paragraph GM-only (it is era-spanning and spoils).

    python tools/fetch-wookieepedia.py            # all systems
    python tools/fetch-wookieepedia.py --only eriadu,ruusan
    python tools/fetch-wookieepedia.py --no-images

Per-system knobs in systems.json: "wpTitle": "Brentaal IV/Legends" to pin the
article, "wpSkip": true to leave a system alone. Title resolution otherwise
tries "<name>/Legends", then "<name>" (Legends-only articles have no suffix),
then a search for "<name>".

Text is CC BY-SA (Wookieepedia contributors); images are embedded as ~480px
thumbnails and belong to their rights holders — this is a private GM tool.
"""
import argparse
import base64
import html
import json
import re
import sys
import time
import urllib.parse
import urllib.request
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SYSTEMS = ROOT / "docs/setting/systems.json"
OUT = ROOT / "docs/setting/wookieepedia.json"
API = "https://starwars.fandom.com/api.php"
UA = "ember-age-map/1.0 (private GM tool; idelorey@gmail.com)"
THUMB = 480
FACT_KEYS = ["region", "sector", "system", "routes", "climate", "terrain", "population",
             "species", "language", "government", "capital", "affiliation"]
LEAD_MAX = 900
FACT_MAX = 160

# --------------------------------------------------------------------------- wikitext parsing


def _strip_pairs(text: str, open_: str, close: str) -> str:
    """Remove every balanced open_ … close block (nested-aware)."""
    out, i, depth = [], 0, 0
    while i < len(text):
        if text.startswith(open_, i):
            depth += 1
            i += len(open_)
        elif text.startswith(close, i) and depth:
            depth -= 1
            i += len(close)
        else:
            if not depth:
                out.append(text[i])
            i += 1
    return "".join(out)


def _render_links(text: str) -> str:
    def link(m):
        target, _, label = m.group(1).partition("|")
        if ":" in target and target.split(":", 1)[0].strip().lower() in ("file", "image", "category"):
            return ""
        return (label or target).strip()
    return re.sub(r"\[\[([^\]]*)\]\]", link, text)


def clean(value: str) -> str:
    """Render an infobox value or sentence to plain text."""
    value = re.sub(r"<ref[^>]*/>", "", value)
    value = re.sub(r"<ref[^>]*>.*?</ref>", "", value, flags=re.S)
    value = re.sub(r"<!--.*?-->", "", value, flags=re.S)
    value = re.sub(r"\{\{[Cc]\|([^{}]*)\}\}", r"(\1)", value)          # {{C|breathable}} -> (breathable)
    value = _strip_pairs(value, "{{", "}}")
    value = _render_links(value)
    value = re.sub(r"<[^>]+>", "", value)
    value = value.replace("'''", "").replace("''", "")
    value = html.unescape(value)
    items = [ln.strip().lstrip("*#").strip() for ln in value.splitlines()]
    items = [it for it in items if it]
    text = ", ".join(items) if len(items) > 1 else (items[0] if items else "")
    return re.sub(r"\s+", " ", text).strip(" ,")


def first_template(wikitext: str) -> dict:
    """Parameters of the first top-level template that carries a |name= or |image= field (the infobox)."""
    i = 0
    while True:
        i = wikitext.find("{{", i)
        if i < 0:
            return {}
        depth, j = 0, i
        while j < len(wikitext):
            if wikitext.startswith("{{", j):
                depth += 1
                j += 2
            elif wikitext.startswith("}}", j):
                depth -= 1
                j += 2
                if depth == 0:
                    break
            else:
                j += 1
        body = wikitext[i + 2:j - 2]
        params = _split_params(body)
        if "name" in params or "image" in params:
            return params
        i = j


def _split_params(body: str) -> dict:
    parts, cur, depth_t, depth_l = [], [], 0, 0
    k = 0
    while k < len(body):
        two = body[k:k + 2]
        if two == "{{":
            depth_t += 1; cur.append(two); k += 2; continue
        if two == "}}":
            depth_t -= 1; cur.append(two); k += 2; continue
        if two == "[[":
            depth_l += 1; cur.append(two); k += 2; continue
        if two == "]]":
            depth_l -= 1; cur.append(two); k += 2; continue
        if body[k] == "|" and not depth_t and not depth_l:
            parts.append("".join(cur)); cur = []; k += 1; continue
        cur.append(body[k]); k += 1
    parts.append("".join(cur))
    params = {}
    for p in parts[1:]:
        key, eq, val = p.partition("=")
        if eq:
            params[key.strip().lower()] = val.strip()
    return params


def parse_facts(wikitext: str) -> dict:
    box = first_template(wikitext)
    facts = {}
    for k in FACT_KEYS:
        v = clean(box.get(k, ""))
        if len(v) > FACT_MAX:
            cut = v.rfind(", ", 0, FACT_MAX)
            v = (v[:cut] if cut > 40 else v[:FACT_MAX].rstrip()) + " …"
        if v:
            facts[k] = v
    return facts


def parse_lead(wikitext: str) -> str:
    text = re.sub(r"<ref[^>]*/>", "", wikitext)
    text = re.sub(r"<ref[^>]*>.*?</ref>", "", text, flags=re.S)
    text = re.sub(r"<!--.*?-->", "", text, flags=re.S)
    text = _strip_pairs(text, "{{", "}}")
    text = re.sub(r"\[\[(?:File|Image):[^\]]*\]\]", "", text, flags=re.I)
    text = _strip_pairs(text, "{|", "|}")
    for para in re.split(r"\n\s*\n", text):
        para = para.strip()
        if not para or para.startswith(("=", "*", "#", ":", "|", "!", "[[Category")):
            continue
        para = clean(para)
        if len(para) < 40:
            continue
        if len(para) > LEAD_MAX:
            cut = para.rfind(". ", 0, LEAD_MAX)
            para = para[:cut + 1] if cut > 200 else para[:LEAD_MAX].rstrip() + "…"
        return para
    return ""


def infobox_image(wikitext: str) -> str:
    m = re.search(r"\[\[(?:File|Image):([^\]|]+)", first_template(wikitext).get("image", ""), flags=re.I)
    return m.group(1).strip() if m else ""


def title_candidates(name: str, override: str | None = None) -> list[str]:
    return [override] if override else [f"{name}/Legends", name]

# --------------------------------------------------------------------------- API


def api(**params) -> dict:
    params.update(format="json", formatversion="2")
    req = urllib.request.Request(API + "?" + urllib.parse.urlencode(params), headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=40) as r:
        return json.load(r)


def fetch_bytes(url: str) -> tuple[bytes, str]:
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=60) as r:
        return r.read(), r.headers.get_content_type()


def resolve(name: str, override: str | None) -> tuple[str | None, list[str]]:
    tried = title_candidates(name, override)
    r = api(action="query", titles="|".join(tried), redirects=1, prop="info")
    found = {p["title"] for p in r["query"]["pages"] if not p.get("missing")}
    redirected = {x["from"]: x["to"] for x in r["query"].get("redirects", [])}
    for t in tried:
        t2 = redirected.get(t, t)
        if t2 in found:
            return t2, tried
    if override:
        return None, tried
    s = api(action="query", list="search", srsearch=f'"{name}"', srlimit=8)
    for hit in s["query"]["search"]:
        t = hit["title"]
        base = t.removesuffix("/Legends")
        if base.lower().startswith(name.lower()) and not re.search(r"\b(system|sector|star|nebula)\b", base[len(name):], re.I):
            tried.append(t)
            return t, tried
    return None, tried


def fetch_article(title: str, want_image: bool) -> dict:
    r = api(action="query", titles=title, prop="revisions|pageimages|info", rvprop="content", rvslots="main",
            piprop="thumbnail|name", pithumbsize=THUMB, inprop="url")
    page = r["query"]["pages"][0]
    wt = page["revisions"][0]["slots"]["main"]["content"]
    entry = {"title": page["title"], "url": page["fullurl"], "facts": parse_facts(wt), "lead": parse_lead(wt)}
    if want_image:
        thumb = page.get("thumbnail")
        src, file = (thumb or {}).get("source"), page.get("pageimage") or infobox_image(wt)
        if not src and file:
            ii = api(action="query", titles=f"File:{file}", prop="imageinfo", iiprop="url", iiurlwidth=THUMB)
            info = (ii["query"]["pages"][0].get("imageinfo") or [{}])[0]
            src = info.get("thumburl") or info.get("url")
        if src:
            data, mime = fetch_bytes(src)
            entry["image"] = {"file": file, "mime": mime, "data": base64.b64encode(data).decode("ascii"),
                              "width": (thumb or {}).get("width"), "height": (thumb or {}).get("height")}
    return entry

# --------------------------------------------------------------------------- main


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", help="comma-separated system ids")
    ap.add_argument("--no-images", action="store_true")
    args = ap.parse_args(argv)
    systems = json.loads(SYSTEMS.read_text(encoding="utf-8"))["systems"]
    existing = json.loads(OUT.read_text(encoding="utf-8")) if OUT.exists() else {}
    only = set(args.only.split(",")) if args.only else None
    out = dict(existing)
    for s in systems:
        if only and s["id"] not in only:
            continue
        if s.get("wpSkip"):
            out.pop(s["id"], None)
            print(f"{s['id']}: skipped")
            continue
        title, tried = resolve(s["name"], s.get("wpTitle"))
        if not title:
            out[s["id"]] = {"missing": True, "tried": tried, "fetched": date.today().isoformat()}
            print(f"{s['id']}: no article (tried {', '.join(tried)})")
            continue
        entry = fetch_article(title, not args.no_images)
        entry["fetched"] = date.today().isoformat()
        out[s["id"]] = entry
        print(f"{s['id']}: {entry['title']} — {len(entry['facts'])} facts, lead {len(entry['lead'])} chars, "
              f"{'image ' + str(len(entry['image']['data']) // 1024) + ' KB' if entry.get('image') else 'no image'}")
        time.sleep(0.3)
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"wrote {OUT.relative_to(ROOT)} ({OUT.stat().st_size // 1024} KB)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
