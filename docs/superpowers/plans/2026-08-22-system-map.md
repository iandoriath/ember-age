# System Map Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** An interactive, zoomable holo-chart of the Ember Age geography, built as two self-contained HTML files — a GM edition with a GM layer, and a player edition with GM data stripped at build time.

**Architecture:** A JSON data file (`docs/setting/systems.json`) describes systems and lanes. A Python builder embeds it into an HTML/SVG/vanilla-JS template and writes two outputs; the player output has every `gm` key deleted from the data and the `<!-- GM:start -->…<!-- GM:end -->` template regions removed. The template renders an SVG chart with viewBox pan/zoom, a HUD, a detail panel, and lit-beacon state (localStorage + `?lit=` URL).

**Tech Stack:** Python 3.12 (stdlib only for the builder; pytest 7 for tests), HTML + SVG + vanilla JS, Google Fonts (Rajdhani) as the only external reference.

**Spec:** `docs/superpowers/specs/2026-08-22-system-map-design.md`

## Global Constraints

- Outputs: `system-map.html` (GM edition) and `player-aids/system-map.html` (player edition).
- Player edition must contain **no** `"gm"` data, no GM switch, no Import control — stripped at build time, never hidden by CSS.
- Both outputs self-contained: no scripts/styles from external hosts except the Rajdhani Google Fonts stylesheet (same as `gm-screen.html`).
- Palette: holo-blue chrome (`--holo:#5fc3ff`, `--holo-dim:#2a5f80`, `--bg:#050a10`); ember/gold for lit beacons and living lanes (`--ember:#e07b39`, `--gold:#ffb454`). Display font Rajdhani.
- Lit state load order: `?lit=` URL param → localStorage key `ember-age.system-map.lit` → default (`bannistar` only).
- Lane kinds: `living | dark | smuggler | far | fraying`. Regions: `reach | hydian | far`.
- Run Python as `python` (Windows); Makefile uses `python3` like existing targets.

---

### Task 1: System data file + validation test

**Files:**
- Create: `docs/setting/systems.json`
- Create: `tools/test_system_map.py`

**Interfaces:**
- Produces: `docs/setting/systems.json` with shape `{"systems":[...], "lanes":[...]}`. System fields: `id, name, sub?, x, y, region, beacon, alwaysLit, hop?, blurb, gm?{seed, canon, factions[]}`. Lane fields: `from, to, kind, name?`.

- [ ] **Step 1: Write the failing validation test**

```python
# tools/test_system_map.py
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "docs/setting/systems.json"


def load():
    return json.loads(DATA.read_text(encoding="utf-8"))


def test_ids_unique_and_lanes_resolve():
    d = load()
    ids = [s["id"] for s in d["systems"]]
    assert len(ids) == len(set(ids))
    for lane in d["lanes"]:
        assert lane["from"] in ids, lane
        assert lane["to"] in ids, lane
        assert lane["kind"] in {"living", "dark", "smuggler", "far", "fraying"}, lane


def test_required_fields_and_regions():
    d = load()
    for s in d["systems"]:
        for k in ("id", "name", "x", "y", "region", "beacon", "alwaysLit", "blurb"):
            assert k in s, (s.get("id"), k)
        assert s["region"] in {"reach", "hydian", "far"}, s["id"]


def test_chain_hops_are_complete():
    d = load()
    hops = sorted(s["hop"] for s in d["systems"] if "hop" in s)
    assert hops == list(range(0, 8)), hops  # Bannistar (0) .. Jutrand (7)
```

- [ ] **Step 2: Run it to verify it fails**

Run: `python -m pytest tools/test_system_map.py -v`
Expected: FAIL — `FileNotFoundError` for systems.json.

- [ ] **Step 3: Write the data file**

```json
{
  "systems": [
    {"id":"bannistar","name":"Bannistar Station","sub":"Okrent's Drift","x":200,"y":700,"region":"reach","beacon":true,"alwaysLit":false,"hop":0,
     "blurb":"The great fuel gantries, and Okrent's Drift — the port that grew on their back. The frayed end of the living Duros Space Run. Its beacon, Vesta-9, was relit in 90 AR — nobody admits to lighting it.",
     "gm":{"seed":"Session One — The Light on Vesta-9","canon":"Canonically a massive refueling depot (attested in Clone Wars-era sources, 900 years later — use freely). Vesta-9 is the beacon here; certified by Chartmistress Bel Nerra (Lamplighters).","factions":["vigil","admiralty","lamplighters"]}},
    {"id":"enarc","name":"Enarc","x":330,"y":640,"region":"reach","beacon":true,"alwaysLit":false,"hop":1,
     "blurb":"A dark crossroads: the Enarc Run (toward Naboo and the Rimma) and the Hutt-ringed Triellus both once met the Run here.",
     "gm":{"seed":"The Toll","canon":"Real junction: Enarc Run + Triellus (Hutt space ring) — natural Kajidic chokepoint.","factions":["kajidics"]}},
    {"id":"alui","name":"Alui","x":450,"y":660,"region":"reach","beacon":true,"alwaysLit":false,"hop":2,
     "blurb":"First of the deep-Reach worlds.",
     "gm":{"seed":"","canon":"Route stop; blank canvas.","factions":[]}},
    {"id":"verdanth","name":"Verdanth","x":560,"y":720,"region":"reach","beacon":true,"alwaysLit":false,"hop":3,
     "blurb":"Jungle world.",
     "gm":{"seed":"The Oracle of Brel (Brel = a settlement moon here?)","canon":"Jungle world; otherwise blank.","factions":[]}},
    {"id":"aplooine","name":"Aplooine","x":660,"y":650,"region":"reach","beacon":true,"alwaysLit":false,"hop":4,
     "blurb":"Quiet agrarian survivor.",
     "gm":{"seed":"The Ration Engine or The Five Systems","canon":"Blank canvas.","factions":["provisional-republic"]}},
    {"id":"sanrafsix","name":"Sanrafsix","x":760,"y":700,"region":"reach","beacon":true,"alwaysLit":false,"hop":5,
     "blurb":"The great dead hub — its bazaars thrived on the last war's economy and died with it. Junction of the smugglers' Sanrafsix Corridor.",
     "gm":{"seed":"The Memory Market","canon":"Great dead trade hub of the New Sith Wars economy — provenance bazaars fit perfectly. Don't crater it: alive in later-era sources.","factions":["kajidics","bounty-hunters-guild"]}},
    {"id":"heptooine","name":"Heptooine","x":880,"y":680,"region":"reach","beacon":true,"alwaysLit":false,"hop":6,
     "blurb":"The Run's last waystop.",
     "gm":{"seed":"The Mausoleum Yards","canon":"Route stop.","factions":[]}},
    {"id":"jutrand","name":"Jutrand","x":1040,"y":700,"region":"reach","beacon":true,"alwaysLit":false,"hop":7,
     "blurb":"City-planet; capital of a dead Sith principality, haunted by its own grandeur.",
     "gm":{"seed":"The Sealed Enclave or The Dead Letter","canon":"Ex-Bactranate capital — haunted grandeur. Inherit the Knight Errant (1032 BBY) state.","factions":["inheritors","vigil"]}},
    {"id":"darkknell","name":"Darkknell","x":1250,"y":620,"region":"reach","beacon":true,"alwaysLit":true,
     "blurb":"The lights come back on: a trinary-sun trade city that never stopped, the Hydian Way's local anchor.",
     "gm":{"seed":"Act 1 finish line","canon":"Never withered. 'An important trading center for millennia,' trinary suns. Wither around it, never through it.","factions":["admiralty","provisional-republic"]}},
    {"id":"eriadu","name":"Eriadu","x":1300,"y":790,"region":"reach","beacon":true,"alwaysLit":true,
     "blurb":"One Hydian hop south: an old, modest world of shellwork jewelry sitting on the most valuable crossroads in the southern Rim — the Hydian Way, the Rimma Trade Route and the minor Lipsec Run. Rumors of coreward money.",
     "gm":{"seed":"Act 2 stakes","canon":"At 910 BBY modest and ancient. The Quintad (Corulag oligarch families) canonically arrive ~900 BBY. The crew's relit corridor is part of why the money comes.","factions":["admiralty","provisional-republic","kajidics"]}},

    {"id":"fostin-nine","name":"Fostin Nine","x":800,"y":850,"region":"reach","beacon":false,"alwaysLit":false,
     "blurb":"First stop down the Sanrafsix Corridor, a notorious smugglers' road.","gm":{"seed":"","canon":"Sanrafsix Corridor.","factions":["kajidics"]}},
    {"id":"syned","name":"Syned","x":880,"y":960,"region":"reach","beacon":false,"alwaysLit":false,
     "blurb":"Corridor waypoint.","gm":{"seed":"","canon":"Sanrafsix Corridor.","factions":[]}},
    {"id":"omwat","name":"Omwat","x":980,"y":1040,"region":"reach","beacon":false,"alwaysLit":false,
     "blurb":"The Corridor runs on past here into Hutt-adjacent space.","gm":{"seed":"","canon":"Sanrafsix Corridor.","factions":[]}},
    {"id":"veshet","name":"Veshet","x":700,"y":900,"region":"reach","beacon":false,"alwaysLit":false,
     "blurb":"A settlement off a dead spur of the Corridor.","gm":{"seed":"Yenna Sar's Veshet","canon":"Off a dead spur of the Sanrafsix Corridor.","factions":["lamplighters"]}},
    {"id":"chelloa","name":"Chelloa","x":520,"y":520,"region":"reach","beacon":false,"alwaysLit":false,
     "blurb":"A dead principality spur. Baradium-scarred.","gm":{"seed":"The Scar (candidate)","canon":"Devastated in Knight Errant (1032 BBY). Floor, not ceiling.","factions":[]}},
    {"id":"byllura","name":"Byllura","x":640,"y":480,"region":"reach","beacon":false,"alwaysLit":false,
     "blurb":"A dead principality spur.","gm":{"seed":"","canon":"The Dyarchy fell here (Knight Errant).","factions":["inheritors"]}},
    {"id":"aquilaris","name":"Aquilaris","x":900,"y":520,"region":"reach","beacon":false,"alwaysLit":false,
     "blurb":"A dead principality spur.","gm":{"seed":"","canon":"Knight Errant world.","factions":[]}},
    {"id":"gazzari","name":"Gazzari","x":1050,"y":450,"region":"reach","beacon":false,"alwaysLit":false,
     "blurb":"A dead principality spur — an old battlefield.","gm":{"seed":"The Scar (candidate)","canon":"Knight Errant battlefield.","factions":[]}},
    {"id":"naboo","name":"Naboo","sub":"Enarc Run, off-chart","x":120,"y":430,"region":"hydian","beacon":false,"alwaysLit":true,
     "blurb":"Where the Enarc Run leads, eventually — toward the Rimma.","gm":{"seed":"","canon":"Off-chart endpoint; living galaxy.","factions":[]}},
    {"id":"hutt-space","name":"Hutt Space","sub":"Triellus, off-chart","x":300,"y":900,"region":"hydian","beacon":false,"alwaysLit":true,
     "blurb":"The Triellus ring — Kajidic country.","gm":{"seed":"","canon":"Off-chart endpoint; Hutt ring.","factions":["kajidics"]}},

    {"id":"malastare","name":"Malastare","x":1350,"y":480,"region":"hydian","beacon":false,"alwaysLit":true,
     "blurb":"A raw colony barely older than the Withering, coreward on the Hydian.","gm":{"seed":"","canon":"~90-year-old Gran colony among Dug natives — a mirror of the era, not an established power.","factions":["provisional-republic"]}},
    {"id":"denon","name":"Denon","x":1420,"y":330,"region":"hydian","beacon":false,"alwaysLit":true,
     "blurb":"Hydian Way, coreward.","gm":{"seed":"","canon":"Hydian waypoint.","factions":[]}},
    {"id":"brentaal","name":"Brentaal","x":1500,"y":180,"region":"far","beacon":false,"alwaysLit":true,
     "blurb":"Where the Hydian crosses the Perlemian Trade Route.","gm":{"seed":"Act 3 turn","canon":"Hydian × Perlemian junction.","factions":["admiralty"]}},
    {"id":"lantillies","name":"Lantillies","x":1700,"y":240,"region":"far","beacon":false,"alwaysLit":true,
     "blurb":"Rimward down the Perlemian; the Randon Run begins here.","gm":{"seed":"","canon":"Perlemian → Randon Run.","factions":[]}},
    {"id":"kashyyyk","name":"Kashyyyk","x":1850,"y":360,"region":"far","beacon":false,"alwaysLit":true,
     "blurb":"The Randon Run passes the Wookiee homeworld.","gm":{"seed":"","canon":"Randon Run waypoint.","factions":[]}},
    {"id":"teraab","name":"Teraab","sub":"stellar nursery","x":1930,"y":470,"region":"far","beacon":false,"alwaysLit":false,
     "blurb":"Off the charts: nebulae quietly eating the last lanes to Ruusan since the war ended.","gm":{"seed":"Act 3 — the hardest astrogation of the campaign; fragments are the only charts.","canon":"The Valley is a 'lost world' by 11 BBY.","factions":[]}},
    {"id":"ruusan","name":"Ruusan","sub":"the Valley","x":1990,"y":570,"region":"far","beacon":false,"alwaysLit":false,
     "blurb":"Every child knows the armies reached Ruusan seven times, so the road exists.","gm":{"seed":"Act 3 finale","canon":"Valley of the Jedi.","factions":["inheritors","vigil"]}}
  ],
  "lanes": [
    {"from":"bannistar","to":"enarc","kind":"dark","name":"Duros Space Run"},
    {"from":"enarc","to":"alui","kind":"dark","name":"Duros Space Run"},
    {"from":"alui","to":"verdanth","kind":"dark","name":"Duros Space Run"},
    {"from":"verdanth","to":"aplooine","kind":"dark","name":"Duros Space Run"},
    {"from":"aplooine","to":"sanrafsix","kind":"dark","name":"Duros Space Run"},
    {"from":"sanrafsix","to":"heptooine","kind":"dark","name":"Duros Space Run"},
    {"from":"heptooine","to":"jutrand","kind":"dark","name":"Duros Space Run"},
    {"from":"jutrand","to":"darkknell","kind":"dark","name":"Duros Space Run"},
    {"from":"darkknell","to":"eriadu","kind":"living","name":"Hydian Way"},
    {"from":"darkknell","to":"malastare","kind":"living","name":"Hydian Way"},
    {"from":"malastare","to":"denon","kind":"living","name":"Hydian Way"},
    {"from":"denon","to":"brentaal","kind":"living","name":"Hydian Way"},
    {"from":"brentaal","to":"lantillies","kind":"far","name":"Perlemian Trade Route"},
    {"from":"lantillies","to":"kashyyyk","kind":"far","name":"Randon Run"},
    {"from":"kashyyyk","to":"teraab","kind":"fraying","name":"Randon Run"},
    {"from":"teraab","to":"ruusan","kind":"fraying","name":"off the charts"},
    {"from":"enarc","to":"naboo","kind":"dark","name":"Enarc Run"},
    {"from":"enarc","to":"hutt-space","kind":"dark","name":"Triellus"},
    {"from":"sanrafsix","to":"fostin-nine","kind":"smuggler","name":"Sanrafsix Corridor"},
    {"from":"fostin-nine","to":"syned","kind":"smuggler","name":"Sanrafsix Corridor"},
    {"from":"syned","to":"omwat","kind":"smuggler","name":"Sanrafsix Corridor"},
    {"from":"fostin-nine","to":"veshet","kind":"dark","name":"dead spur"},
    {"from":"alui","to":"chelloa","kind":"dark","name":"dead spur"},
    {"from":"verdanth","to":"byllura","kind":"dark","name":"dead spur"},
    {"from":"heptooine","to":"aquilaris","kind":"dark","name":"dead spur"},
    {"from":"jutrand","to":"gazzari","kind":"dark","name":"dead spur"}
  ]
}
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `python -m pytest tools/test_system_map.py -v`
Expected: 3 passed.

- [ ] **Step 5: Commit**

```bash
git add docs/setting/systems.json tools/test_system_map.py
git commit -m "System Map: system/lane data with validation tests"
```

---

### Task 2: Builder with GM-stripping, against a stub template

**Files:**
- Create: `tools/build-system-map.py`
- Create: `tools/system-map-template.html` (stub; replaced in Task 3)
- Modify: `tools/test_system_map.py` (append tests)

**Interfaces:**
- Produces: `build_system_map.build(edition: str, data: dict, template: str) -> str` and `main()` writing `system-map.html` and `player-aids/system-map.html`.
- Template contract: contains the literal tokens `__DATA__` (replaced with JSON), `__EDITION__` (replaced with `gm` or `player`), and zero or more `<!-- GM:start -->…<!-- GM:end -->` regions (removed in the player edition; markers alone removed in the GM edition).

- [ ] **Step 1: Append failing builder tests**

```python
# append to tools/test_system_map.py
import importlib.util
import re

spec = importlib.util.spec_from_file_location("bsm", ROOT / "tools/build-system-map.py")
bsm = importlib.util.module_from_spec(spec)
spec.loader.exec_module(bsm)

STUB = ('<p>ED:__EDITION__</p><!-- GM:start --><button id="gm-switch">GM</button>'
        '<!-- GM:end --><script id="data" type="application/json">__DATA__</script>')


def test_player_edition_strips_gm():
    out = bsm.build("player", load(), STUB)
    assert '"gm"' not in out
    assert "gm-switch" not in out
    assert "GM:start" not in out
    assert "ED:player" in out
    embedded = json.loads(re.search(r'type="application/json">(.*?)</script>', out, re.S).group(1))
    assert all("gm" not in s for s in embedded["systems"])


def test_gm_edition_keeps_gm():
    out = bsm.build("gm", load(), STUB)
    assert "gm-switch" in out and "GM:start" not in out
    assert "ED:gm" in out
    assert '"seed"' in out


def test_embedded_json_is_script_safe():
    d = load()
    d["systems"][0]["blurb"] = "bad </script> tag"
    out = bsm.build("player", d, STUB)
    assert "</script> tag" not in out
    assert "<\\/script> tag" in out
```

- [ ] **Step 2: Run to verify failure**

Run: `python -m pytest tools/test_system_map.py -v`
Expected: FAIL — file `tools/build-system-map.py` not found.

- [ ] **Step 3: Write the builder and a stub template**

```python
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
```

Stub template (`tools/system-map-template.html`) for now:

```html
<!doctype html><html><body>ED:__EDITION__<!-- GM:start --><button id="gm-switch">GM</button><!-- GM:end -->
<script id="data" type="application/json">__DATA__</script></body></html>
```

- [ ] **Step 4: Run tests**

Run: `python -m pytest tools/test_system_map.py -v`
Expected: 6 passed.

- [ ] **Step 5: Commit**

```bash
git add tools/build-system-map.py tools/system-map-template.html tools/test_system_map.py
git commit -m "System Map: builder writes GM and player editions, strips gm data"
```

---

### Task 3: The chart template — rendering, pan/zoom, HUD

**Files:**
- Replace: `tools/system-map-template.html`
- Modify: `tools/test_system_map.py` (append an output test)

**Interfaces:**
- Consumes: template tokens from Task 2.
- Produces: globals used by Task 4: `DATA`, `EDITION`, `byId` (Map id→system), `lit` (Set), `isLit(s)`, `render()` (full redraw), `renderStatus()`, `setView(vb)`, `frame(name)` (`"reach"|"road"`), `toast(msg)`, `closePanel()`, and element ids `#chart`, `#hud`, `#status`, `#panel`, `#panel-body`, `#toast`, `#gm-switch` (GM only). Systems render as `<g class="sys" data-id=…>`, lanes as `<line class="lane" data-from data-to data-kind>`.

- [ ] **Step 1: Append a failing output test**

```python
def test_template_renders_every_system_and_hud_controls():
    tpl = (ROOT / "tools/system-map-template.html").read_text(encoding="utf-8")
    out = bsm.build("player", load(), tpl)
    for token in ('id="chart"', 'id="hud"', 'id="status"', 'id="panel"', "Frame the Reach", "Frame the Road", "fonts.googleapis.com/css2?family=Rajdhani"):
        assert token in out, token
    assert "gm-switch" not in out and "Import save" not in out
    gm = bsm.build("gm", load(), tpl)
    assert "gm-switch" in gm and "Import save" in gm
    assert not re.search(r'<script[^>]+src="https?://', out)
```

- [ ] **Step 2: Run to verify failure**

Run: `python -m pytest tools/test_system_map.py -v`
Expected: the new test FAILS (stub lacks `id="chart"`).

- [ ] **Step 3: Write the full template**

Write `tools/system-map-template.html` with exactly this content (Task 4 replaces the `/* TASK4:… */` markers; keep them):

```html
<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Ember Age — System Map</title>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Rajdhani:wght@500;600;700&display=swap">
<style>
  :root{
    --bg:#050a10; --holo:#5fc3ff; --holo-dim:#2a5f80; --holo-faint:#153246; --ink:#d7ecf8; --dim:#7fa3bb;
    --ember:#e07b39; --gold:#ffb454; --disp:"Rajdhani",system-ui,"Segoe UI",Roboto,sans-serif;
  }
  *{box-sizing:border-box} html,body{margin:0;height:100%;overflow:hidden;background:var(--bg);color:var(--ink);font:14px/1.45 var(--disp)}
  #chart{position:absolute;inset:0;width:100%;height:100%;display:block;cursor:grab;touch-action:none}
  #chart.dragging{cursor:grabbing}
  #chart text{font-family:var(--disp);fill:var(--holo);letter-spacing:.12em;text-transform:uppercase;pointer-events:none;paint-order:stroke;stroke:var(--bg);stroke-width:3px;stroke-linejoin:round}
  #chart .lbl{font-size:13px;font-weight:600}
  #chart .sub{font-size:9px;fill:var(--dim);letter-spacing:.18em}
  #chart .hop{font-size:9px;fill:var(--dim)}
  #chart .lanelbl{font-size:9px;fill:var(--holo-dim);letter-spacing:.25em}
  /* lanes */
  .lane{fill:none;stroke-linecap:round;transition:opacity .25s,stroke .25s}
  .lane[data-kind=dark]{stroke:var(--holo-dim);stroke-width:1.2;stroke-dasharray:6 7}
  .lane[data-kind=smuggler]{stroke:var(--holo-dim);stroke-width:1;stroke-dasharray:1.5 6}
  .lane[data-kind=living]{stroke:var(--ember);stroke-width:2;filter:url(#glow)}
  .lane[data-kind=far]{stroke:var(--holo-faint);stroke-width:1.2}
  .lane[data-kind=fraying]{stroke:var(--holo-faint);stroke-width:1.2;stroke-dasharray:10 6 6 8 3 12 2 16}
  .lane.relit{stroke:var(--ember);stroke-width:2;stroke-dasharray:none;filter:url(#glow)}
  /* systems */
  .sys{cursor:pointer;outline:none}
  .sys .core{fill:var(--holo-dim);stroke:var(--holo);stroke-width:1.2}
  .sys .ring{fill:none;stroke:var(--holo-dim);stroke-width:1;opacity:.8}
  .sys.beacon .core{fill:var(--bg);stroke:var(--holo-dim);stroke-width:1.5}
  .sys.beacon .ring{stroke-dasharray:2 3}
  .sys.lit .core{fill:var(--ember);stroke:var(--gold);filter:url(#glow)}
  .sys.lit .ring{stroke:var(--ember);stroke-dasharray:none;animation:pulse 3s ease-in-out infinite}
  .sys.always .core{fill:var(--gold);stroke:var(--gold);filter:url(#glow)}
  .sys.always .ring{stroke:var(--gold);opacity:.5;stroke-dasharray:none}
  .sys.lit text,.sys.always text{fill:var(--gold)}
  .sys .hit{fill:transparent}
  @keyframes pulse{0%,100%{opacity:.35;r:11}50%{opacity:.9;r:15}}
  /* hover dimming */
  #chart.hl .lane:not(.on),#chart.hl .sys:not(.on){opacity:.28}
  #chart.hl .lane.on{stroke:var(--holo)} #chart.hl .lane.on[data-kind=living],#chart.hl .lane.on.relit{stroke:var(--gold)}
  /* zoom-dependent label fade */
  .r-hydian,.r-far{transition:opacity .3s}
  #chart[data-zoom=reach] .r-hydian{opacity:.45} #chart[data-zoom=reach] .r-far{opacity:.15}
  #chart[data-zoom=wide] .r-far{opacity:.6}
  /* HUD */
  #hud{position:absolute;inset:0;pointer-events:none}
  #hud>*{pointer-events:auto}
  .frame{position:absolute;inset:10px;border:1px solid var(--holo-faint);pointer-events:none}
  .frame:before,.frame:after{content:"";position:absolute;width:22px;height:22px;border:2px solid var(--holo)}
  .frame:before{left:-1px;top:-1px;border-right:0;border-bottom:0}.frame:after{right:-1px;bottom:-1px;border-left:0;border-top:0}
  #title{position:absolute;left:26px;top:20px;pointer-events:none}
  #title h1{margin:0;font-size:1.35rem;font-weight:700;letter-spacing:.18em;color:var(--holo);text-transform:uppercase}
  #title h1 b{color:var(--ember)}
  #title small{display:block;color:var(--dim);letter-spacing:.3em;font-size:.7rem;text-transform:uppercase}
  #status{position:absolute;left:26px;bottom:22px;display:flex;gap:.6rem;align-items:flex-end;font-size:.7rem;letter-spacing:.15em;text-transform:uppercase;color:var(--dim)}
  #status .pip{display:flex;flex-direction:column;align-items:center;gap:.25rem;cursor:pointer}
  #status .pip i{width:10px;height:10px;border-radius:50%;border:1px solid var(--holo-dim);background:var(--bg)}
  #status .pip.lit i{background:var(--ember);border-color:var(--gold);box-shadow:0 0 8px var(--ember)}
  #status .pip.always i{background:var(--gold);border-color:var(--gold)}
  #status .pip:hover{color:var(--ink)}
  #status .cap{margin-right:.4rem;color:var(--holo)}
  #ctl{position:absolute;right:26px;top:20px;display:flex;gap:.4rem;flex-wrap:wrap;justify-content:flex-end}
  .hb{background:rgba(5,10,16,.7);border:1px solid var(--holo-dim);color:var(--holo);font:600 .75rem/1 var(--disp);letter-spacing:.15em;text-transform:uppercase;padding:.5rem .7rem;cursor:pointer;backdrop-filter:blur(3px)}
  .hb:hover,.hb:focus-visible{border-color:var(--holo);color:var(--ink);outline:none}
  .hb.on{background:var(--ember);border-color:var(--ember);color:#1b120a}
  #toast{position:absolute;right:26px;top:64px;color:var(--gold);font-size:.75rem;letter-spacing:.2em;text-transform:uppercase;opacity:0;transition:opacity .3s;pointer-events:none}
  #toast.show{opacity:1}
  /* scanlines + vignette */
  #fx{position:absolute;inset:0;pointer-events:none;background:
     repeating-linear-gradient(0deg,rgba(255,255,255,.025) 0 1px,transparent 1px 3px),
     radial-gradient(ellipse at center,transparent 55%,rgba(0,0,0,.75) 100%)}
  /* panel (Task 4 fills it) */
  #panel{position:absolute;right:26px;top:110px;bottom:70px;width:min(360px,calc(100% - 52px));background:rgba(5,10,16,.88);border:1px solid var(--holo-dim);padding:1rem 1.1rem;overflow:auto;transform:translateX(20px);opacity:0;pointer-events:none;transition:.25s;backdrop-filter:blur(4px)}
  #panel.open{transform:none;opacity:1;pointer-events:auto}
  #panel h2{margin:0;font-size:1.3rem;letter-spacing:.15em;text-transform:uppercase;color:var(--holo)}
  #panel h2.lit{color:var(--gold)}
  #panel .k{color:var(--dim);font-size:.7rem;letter-spacing:.25em;text-transform:uppercase;margin:.9rem 0 .2rem}
  #panel p{margin:.2rem 0;font-size:.95rem;font-family:system-ui,"Segoe UI",Roboto,sans-serif;line-height:1.5}
  #panel .x{position:absolute;right:.6rem;top:.5rem;background:none;border:0;color:var(--dim);font-size:1.2rem;cursor:pointer}
  #panel .gm{border-top:1px dashed var(--ember);margin-top:1rem;padding-top:.4rem;display:none}
  body.gm-on #panel .gm{display:block}
  #panel .gm .k{color:var(--ember)}
  .ftag{display:inline-block;border:1px solid var(--ember);color:var(--gold);font-size:.65rem;letter-spacing:.15em;text-transform:uppercase;padding:.1rem .4rem;margin:.15rem .2rem 0 0}
  #chart .fac{font-size:7px;fill:var(--ember);letter-spacing:.1em;display:none}
  body.gm-on #chart .fac{display:block}
</style>
</head>
<body>
<svg id="chart" xmlns="http://www.w3.org/2000/svg" data-zoom="reach" aria-label="System map"></svg>
<div id="fx"></div>
<div id="hud">
  <div class="frame"></div>
  <div id="title"><h1>Nav<b>·</b>Chart — The Grumani Reach</h1><small>Duros Space Run · 90 AR · beacon status live</small></div>
  <div id="ctl">
    <button class="hb" onclick="zoomBy(1.3)">+</button><button class="hb" onclick="zoomBy(1/1.3)">−</button>
    <button class="hb" onclick="frame('reach')">Frame the Reach</button>
    <button class="hb" onclick="frame('road')">Frame the Road</button>
    <button class="hb" onclick="share()">Share</button>
    <!-- GM:start -->
    <button class="hb" id="gm-switch" onclick="toggleGM()">GM</button>
    <label class="hb">Import save<input type="file" accept="application/json" style="display:none" onchange="importSave(this.files[0]);this.value=''"></label>
    <!-- GM:end -->
  </div>
  <div id="toast"></div>
  <div id="panel"><button class="x" onclick="closePanel()" aria-label="close">✕</button><div id="panel-body"></div></div>
  <div id="status"></div>
</div>
<script id="data" type="application/json">__DATA__</script>
<script>
const EDITION = "__EDITION__";
const DATA = JSON.parse(document.getElementById("data").textContent);
const byId = new Map(DATA.systems.map(s => [s.id, s]));
const SVG = "http://www.w3.org/2000/svg";
const chart = document.getElementById("chart");
const VIEWS = {reach:{x:60, y:380, w:1340, h:760}, road:{x:0, y:60, w:2100, h:1150}};
let vb = {...VIEWS.reach};

/* ---- lit state (Task 4 adds persistence) ---- */
let lit = new Set(["bannistar"]);
const isLit = s => s.alwaysLit || lit.has(s.id);
/* TASK4:state */

/* ---- rendering ---- */
function el(tag, attrs = {}, parent) {
  const n = document.createElementNS(SVG, tag);
  for (const [k, v] of Object.entries(attrs)) n.setAttribute(k, v);
  if (parent) parent.appendChild(n);
  return n;
}
function laneIsRelit(l) { return l.kind === "dark" && isLit(byId.get(l.from)) && isLit(byId.get(l.to)); }
function regionOf(a, b) { return (a.region === "reach" && b.region === "reach") ? "reach" : (a.region === "far" || b.region === "far") ? "far" : "hydian"; }

function render() {
  chart.innerHTML = "";
  const defs = el("defs", {}, chart);
  defs.innerHTML = `
    <filter id="glow" x="-50%" y="-50%" width="200%" height="200%"><feGaussianBlur stdDeviation="2.5" result="b"/><feMerge><feMergeNode in="b"/><feMergeNode in="SourceGraphic"/></feMerge></filter>
    <pattern id="grid" width="50" height="50" patternUnits="userSpaceOnUse"><path d="M50 0H0V50" fill="none" stroke="#0f2030" stroke-width=".6"/></pattern>
    <pattern id="grid2" width="250" height="250" patternUnits="userSpaceOnUse"><path d="M250 0H0V250" fill="none" stroke="#15304a" stroke-width=".8"/></pattern>`;
  el("rect", {x:-2000, y:-2000, width:6000, height:6000, fill:"url(#grid)"}, chart);
  el("rect", {x:-2000, y:-2000, width:6000, height:6000, fill:"url(#grid2)"}, chart);

  const gl = el("g", {id:"lanes"}, chart);
  for (const l of DATA.lanes) {
    const a = byId.get(l.from), b = byId.get(l.to);
    el("line", {class:"lane r-" + regionOf(a, b) + (laneIsRelit(l) ? " relit" : ""), x1:a.x, y1:a.y, x2:b.x, y2:b.y, "data-from":l.from, "data-to":l.to, "data-kind":l.kind}, gl);
  }
  // one label per named lane, on its longest segment
  const seen = new Map();
  for (const l of DATA.lanes) {
    if (!l.name || l.name === "dead spur") continue;
    const a = byId.get(l.from), b = byId.get(l.to), len = Math.hypot(b.x - a.x, b.y - a.y);
    if (!seen.has(l.name) || seen.get(l.name).len < len) seen.set(l.name, {a, b, len});
  }
  for (const [name, {a, b}] of seen) {
    const mx = (a.x + b.x) / 2, my = (a.y + b.y) / 2;
    let ang = Math.atan2(b.y - a.y, b.x - a.x) * 180 / Math.PI; if (ang > 90 || ang < -90) ang += 180;
    const t = el("text", {class:"lanelbl r-" + regionOf(a, b), x:mx, y:my - 6, "text-anchor":"middle", transform:`rotate(${ang} ${mx} ${my})`}, gl);
    t.textContent = name;
  }

  const gs = el("g", {id:"systems"}, chart);
  for (const s of DATA.systems) {
    const cls = `sys r-${s.region}` + (s.beacon ? " beacon" : "") + (s.alwaysLit ? " always" : lit.has(s.id) ? " lit" : "");
    const g = el("g", {class:cls, "data-id":s.id, transform:`translate(${s.x} ${s.y})`, tabindex:0, role:"button"}, gs);
    el("circle", {class:"hit", r:22}, g);
    if (s.beacon) el("circle", {class:"ring", r:12}, g);
    el("circle", {class:"core", r:s.beacon ? 5 : 3}, g);
    const lbl = el("text", {class:"lbl", x:16, y:4}, g); lbl.textContent = s.name;
    if (s.sub) { const sub = el("text", {class:"sub", x:16, y:16}, g); sub.textContent = s.sub; }
    if (s.hop !== undefined) { const h = el("text", {class:"hop", x:-10, y:-14, "text-anchor":"end"}, g); h.textContent = s.hop === 0 ? "⌂" : s.hop; }
    if (s.gm && s.gm.factions && s.gm.factions.length) {
      const f = el("text", {class:"fac", x:16, y:s.sub ? 27 : 16}, g);
      f.textContent = s.gm.factions.map(x => x.split("-").map(w => w[0]).join("")).join(" · ");
    }
    g.addEventListener("pointerenter", () => highlight(s.id));
    g.addEventListener("pointerleave", () => highlight(null));
    g.addEventListener("click", e => { e.stopPropagation(); if (!(drag && drag.moved)) openPanel(s.id); });
    g.addEventListener("keydown", e => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); openPanel(s.id); } });
  }
  renderStatus();
  applyView();
}

function highlight(id) {
  chart.classList.toggle("hl", !!id);
  chart.querySelectorAll(".on").forEach(n => n.classList.remove("on"));
  if (!id) return;
  const near = new Set([id]);
  chart.querySelectorAll(".lane").forEach(l => { if (l.dataset.from === id || l.dataset.to === id) { l.classList.add("on"); near.add(l.dataset.from); near.add(l.dataset.to); } });
  chart.querySelectorAll(".sys").forEach(g => { if (near.has(g.dataset.id)) g.classList.add("on"); });
}

function renderStatus() {
  const chain = DATA.systems.filter(s => s.hop !== undefined).sort((a, b) => a.hop - b.hop).concat([byId.get("darkknell"), byId.get("eriadu")]);
  document.getElementById("status").innerHTML = `<span class="cap">Beacons</span>` + chain.map(s =>
    `<span class="pip ${s.alwaysLit ? "always" : lit.has(s.id) ? "lit" : ""}" onclick="openPanel('${s.id}')" title="${s.name}"><i></i><span>${s.hop === 0 ? "⌂" : s.hop !== undefined ? s.hop : "★"}</span></span>`).join("");
}

/* ---- pan / zoom ---- */
function currentBox() { return chart.getAttribute("viewBox").split(" ").map(Number); }
function applyView() {
  const r = chart.getBoundingClientRect(), aspect = r.width / r.height;
  let {x, y, w, h} = vb;
  if (w / h < aspect) { const nw = h * aspect; x -= (nw - w) / 2; w = nw; } else { const nh = w / aspect; y -= (nh - h) / 2; h = nh; }
  chart.setAttribute("viewBox", `${x} ${y} ${w} ${h}`);
  chart.dataset.zoom = vb.w > 1700 ? "far" : vb.w > 1450 ? "wide" : "reach";
}
function setView(v) { vb = {...v}; applyView(); }
function frame(name) { setView(VIEWS[name]); }
function zoomAt(factor, cx, cy) {
  const r = chart.getBoundingClientRect();
  const [x0, y0, w0, h0] = currentBox();
  const px = x0 + (cx - r.left) / r.width * w0, py = y0 + (cy - r.top) / r.height * h0;
  const nw = Math.min(Math.max(vb.w / factor, 300), 4000), f = vb.w / nw;
  vb.w = nw; vb.h = vb.h / f;
  vb.x = px - (px - vb.x) / f; vb.y = py - (py - vb.y) / f;
  applyView();
}
function zoomBy(f) { const r = chart.getBoundingClientRect(); zoomAt(f, r.left + r.width / 2, r.top + r.height / 2); }
chart.addEventListener("wheel", e => { e.preventDefault(); zoomAt(e.deltaY < 0 ? 1.15 : 1 / 1.15, e.clientX, e.clientY); }, {passive:false});
let drag = null;
chart.addEventListener("pointerdown", e => { if (e.button !== 0) return; drag = {x:e.clientX, y:e.clientY, vx:vb.x, vy:vb.y, moved:false}; chart.setPointerCapture(e.pointerId); });
chart.addEventListener("pointermove", e => {
  if (!drag) return;
  const r = chart.getBoundingClientRect(), k = currentBox()[2] / r.width;
  const dx = (e.clientX - drag.x) * k, dy = (e.clientY - drag.y) * k;
  if (Math.abs(dx) + Math.abs(dy) > 2) { drag.moved = true; chart.classList.add("dragging"); }
  vb.x = drag.vx - dx; vb.y = drag.vy - dy; applyView();
});
chart.addEventListener("pointerup", () => { chart.classList.remove("dragging"); setTimeout(() => { drag = null; }, 0); });
chart.addEventListener("click", e => { if (!(drag && drag.moved) && (e.target === chart || e.target.tagName === "rect")) closePanel(); });
window.addEventListener("resize", applyView);

/* ---- panel / share / GM (Task 4) ---- */
function openPanel(id) { /* TASK4:panel */ }
function closePanel() { document.getElementById("panel").classList.remove("open"); }
function share() { /* TASK4:share */ }
function toast(msg) { const t = document.getElementById("toast"); t.textContent = msg; t.classList.add("show"); setTimeout(() => t.classList.remove("show"), 2200); }
/* TASK4:gm */

render();
</script>
</body>
</html>
```

- [ ] **Step 4: Run tests, build, and look at it**

Run: `python -m pytest tools/test_system_map.py -v` — Expected: 7 passed.
Run: `python tools/build-system-map.py` then open `system-map.html` in Chrome (`start system-map.html`).
Check: the Reach is framed; Bannistar glows ember; Darkknell/Eriadu gold; dark lanes dashed blue; wheel zooms at the cursor; drag pans; zooming out fades in the far-road labels; hovering a system dims everything but its neighbours; the status strip at the bottom shows ⌂ 1–7 ★ ★; no console errors. Fix anything visibly wrong before committing.

- [ ] **Step 5: Commit**

```bash
git add tools/system-map-template.html tools/test_system_map.py system-map.html player-aids/system-map.html
git commit -m "System Map: holo chart with pan/zoom, lanes, beacons, HUD"
```

---

### Task 4: Detail panel, lit-state persistence, share, GM layer, import

**Files:**
- Modify: `tools/system-map-template.html` (replace the `/* TASK4:… */` markers)
- Modify: `tools/test_system_map.py` (append a test)

**Interfaces:**
- Consumes: `DATA, byId, lit, isLit, render, renderStatus, toast, closePanel` from Task 3.
- Produces: `openPanel(id)`, `toggleLit(id)`, `share()`, `toggleGM()`, `importSave(file)`, `loadLit()`, `saveLit()`; localStorage key `ember-age.system-map.lit`; URL param `lit` (comma-separated ids).

- [ ] **Step 1: Append a failing test for the state/share code**

```python
def test_template_has_state_and_share_code():
    tpl = (ROOT / "tools/system-map-template.html").read_text(encoding="utf-8")
    out = bsm.build("player", load(), tpl)
    for token in ("ember-age.system-map.lit", 'searchParams.get("lit")', "replaceState", "clipboard.writeText", "function toggleLit"):
        assert token in out, token
    assert "importSave" not in out and "toggleGM" not in out
    gm = bsm.build("gm", load(), tpl)
    assert "function importSave" in gm and "function toggleGM" in gm
```

- [ ] **Step 2: Run to verify failure**

Run: `python -m pytest tools/test_system_map.py -v`
Expected: new test FAILS (`ember-age.system-map.lit` missing).

- [ ] **Step 3: Replace the markers**

Replace the `/* TASK4:state */` line with:

```js
const KEY = "ember-age.system-map.lit";
function loadLit() {
  const q = new URL(location.href).searchParams.get("lit");
  if (q !== null) return new Set(q.split(",").filter(id => byId.has(id)));
  try { const s = JSON.parse(localStorage.getItem(KEY)); if (Array.isArray(s)) return new Set(s.filter(id => byId.has(id))); } catch (e) {}
  return new Set(["bannistar"]);
}
function saveLit() {
  try { localStorage.setItem(KEY, JSON.stringify([...lit])); } catch (e) {}
  try { const u = new URL(location.href); u.searchParams.set("lit", [...lit].join(",")); history.replaceState(null, "", u); } catch (e) {}
}
function toggleLit(id) { if (lit.has(id)) lit.delete(id); else lit.add(id); saveLit(); render(); openPanel(id); }
lit = loadLit();
```

Replace `function openPanel(id) { /* TASK4:panel */ }` with:

```js
let panelId = null;
function openPanel(id) {
  const s = byId.get(id); if (!s) return;
  panelId = id;
  const lanes = [...new Set(DATA.lanes.filter(l => l.from === id || l.to === id).map(l => l.name || "dead spur"))];
  const status = s.alwaysLit ? "ALIVE — never withered" : s.beacon ? (lit.has(id) ? "LIT" : "DARK") : "no beacon";
  const esc = t => String(t).replace(/[&<>"]/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;"}[c]));
  const region = {reach:"The Grumani Reach", hydian:"The living galaxy", far:"The far road"}[s.region];
  let h = `<h2 class="${isLit(s) ? "lit" : ""}">${esc(s.name)}</h2>` + (s.sub ? `<div class="k">${esc(s.sub)}</div>` : "");
  h += `<div class="k">Region</div><p>${region}${s.hop !== undefined ? ` · hop ${s.hop}` : ""}</p>`;
  h += `<div class="k">Lanes</div><p>${lanes.map(esc).join(" · ") || "—"}</p>`;
  h += `<div class="k">Beacon</div><p>${status}${s.beacon && !s.alwaysLit ? ` &nbsp; <button class="hb ${lit.has(id) ? "on" : ""}" onclick="toggleLit('${id}')">${lit.has(id) ? "Darken" : "Relight"}</button>` : ""}</p>`;
  h += `<div class="k">Chart note</div><p>${esc(s.blurb)}</p>`;
  if (s.gm) {
    h += `<div class="gm"><div class="k">GM — episode seed</div><p>${esc(s.gm.seed || "—")}</p><div class="k">GM — canon</div><p>${esc(s.gm.canon || "—")}</p>`;
    h += `<div class="k">GM — factions present</div><p>${(s.gm.factions || []).map(f => `<span class="ftag">${esc(f.replace(/-/g, " "))}</span>`).join("") || "—"}</p></div>`;
  }
  document.getElementById("panel-body").innerHTML = h;
  document.getElementById("panel").classList.add("open");
}
```

Replace `function share() { /* TASK4:share */ }` with:

```js
function share() {
  saveLit();
  const url = location.href;
  (navigator.clipboard ? navigator.clipboard.writeText(url) : Promise.reject()).then(() => toast("Link copied"), () => { prompt("Copy this link", url); });
}
```

Replace `/* TASK4:gm */` with (the marker comments must sit on their own lines — the builder deletes the region for the player edition and just the markers for the GM edition, so no HTML comment ever reaches the emitted JS):

```js
<!-- GM:start -->
function toggleGM() {
  const on = document.body.classList.toggle("gm-on");
  document.getElementById("gm-switch").classList.toggle("on", on);
  if (panelId && document.getElementById("panel").classList.contains("open")) openPanel(panelId);
}
function importSave(file) {
  if (!file) return;
  file.text().then(t => {
    const S = JSON.parse(t); const rows = Array.isArray(S.beacons) ? S.beacons : [];
    const norm = x => String(x || "").toLowerCase();
    let hit = 0; const miss = [];
    for (const b of rows) {
      const n = norm(b.name);
      const s = DATA.systems.find(x => x.beacon && !x.alwaysLit && (norm(x.name) === n || norm(x.sub) === n || (n && n.includes(norm(x.name)))))
        || (n.includes("vesta") ? byId.get("bannistar") : null);
      if (!s) { miss.push(b.name); continue; }
      if (b.status === "lit") lit.add(s.id); else lit.delete(s.id);
      hit++;
    }
    saveLit(); render();
    toast(`Imported ${hit} beacon${hit === 1 ? "" : "s"}` + (miss.length ? ` · unmatched: ${miss.join(", ")}` : ""));
  }).catch(() => toast("Could not read that save"));
}
<!-- GM:end -->
```

- [ ] **Step 4: Run tests, rebuild, and check both editions in Chrome**

Run: `python -m pytest tools/test_system_map.py -v` — Expected: 8 passed.
Run: `python tools/build-system-map.py`.
Check GM edition (`system-map.html`): click Enarc → panel opens → **Relight** → Enarc turns ember and the Bannistar–Enarc lane turns ember solid; the address bar now has `?lit=bannistar,enarc`; reload keeps it; **Share** shows "Link copied"; **GM** reveals seed/canon/factions in the panel and faction initials on the chart; **Import save** with a GM-screen export (Export save from `gm-screen.html`) maps Vesta-9 → Bannistar.
Check player edition (`player-aids/system-map.html`): no GM or Import buttons; open it with `?lit=bannistar,enarc` appended and confirm it opens lit; view-source contains no `"gm"` text.
No console errors in either edition.

- [ ] **Step 5: Commit**

```bash
git add tools/system-map-template.html tools/test_system_map.py system-map.html player-aids/system-map.html
git commit -m "System Map: detail panel, lit-state persistence, share links, GM layer, save import"
```

---

### Task 5: Wire into Makefile, CI, README

**Files:**
- Modify: `Makefile`
- Modify: `.github/workflows/wiki.yml`
- Modify: `README.md`

- [ ] **Step 1: Makefile** — add `map` to `.PHONY`, add this target, and append `python3 tools/build-system-map.py` to the `build` target after the player-aids line:

```make
## Build the system map (GM edition -> system-map.html, player edition -> player-aids/system-map.html)
map:
	python3 tools/build-system-map.py
```

- [ ] **Step 2: CI** — after the "Build GM screen" step in `.github/workflows/wiki.yml` add:

```yaml
      - name: Build system map
        run: python tools/build-system-map.py
      - name: Test system map build
        run: pip install pytest && python -m pytest tools/test_system_map.py -q
      - name: Upload system map artifacts
        uses: actions/upload-artifact@v4
        with:
          name: system-map
          path: |
            system-map.html
            player-aids/system-map.html
```

- [ ] **Step 3: README** — after the GM Screen section add:

```markdown
## The System Map — the chart you put on the table screen

**`system-map.html`** (GM edition) and **`player-aids/system-map.html`** (player edition) — a zoomable holo-chart of the Reach, the Hydian and the road to Ruusan. Click a system for its note; beacons toggle **Relight / Darken** and the lit set lives in the URL (`?lit=bannistar,enarc`), so **Share** copies a link that opens in the same state for the players.

The GM edition adds a **GM** switch (episode seeds, canon notes, faction presence) and **Import save**, which reads a GM-screen export and syncs beacon status. The player edition is built with all GM data removed from the file — send that one to the table.

Content lives in `docs/setting/systems.json`; `make map` rebuilds both files.
```

- [ ] **Step 4: Verify** — run `python tools/build-system-map.py && python -m pytest tools/test_system_map.py -q`. Expected: build prints both paths, 8 passed. Also `git diff --stat` shows only the three files above changed.

- [ ] **Step 5: Commit**

```bash
git add Makefile .github/workflows/wiki.yml README.md
git commit -m "System Map: make map target, CI build + tests, README"
```
