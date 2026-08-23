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


def load_data() -> dict:
    data = json.loads(DATA.read_text(encoding="utf-8"))
    if WOOKIEEPEDIA.exists():
        data = merge_wookieepedia(data, json.loads(WOOKIEEPEDIA.read_text(encoding="utf-8")))
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
