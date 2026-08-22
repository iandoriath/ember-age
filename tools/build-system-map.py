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

GM_REGION = re.compile(r"<!-- GM:start -->.*?<!-- GM:end -->", re.S)


def strip_gm(data: dict) -> dict:
    d = copy.deepcopy(data)
    for s in d["systems"]:
        s.pop("gm", None)
    return d


def build(edition: str, data: dict, template: str) -> str:
    if edition == "player":
        data = strip_gm(data)
        template = GM_REGION.sub("", template)
    else:
        template = template.replace("<!-- GM:start -->", "").replace("<!-- GM:end -->", "")
    payload = json.dumps(data, ensure_ascii=False).replace("</", "<\\/")
    return template.replace("__DATA__", payload).replace("__EDITION__", edition)


def main():
    data = json.loads(DATA.read_text(encoding="utf-8"))
    template = TEMPLATE.read_text(encoding="utf-8")
    OUT_GM.write_text(build("gm", data, template), encoding="utf-8")
    OUT_PLAYER.write_text(build("player", data, template), encoding="utf-8")
    print(f"wrote {OUT_GM.relative_to(ROOT)} and {OUT_PLAYER.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
