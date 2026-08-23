import json
from pathlib import Path

import pytest

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
    blurb = "bad </script> tag and <!--<script comment"
    d["systems"][0]["blurb"] = blurb
    out = bsm.build("player", d, STUB)
    # neither sequence may reach the HTML tokenizer verbatim
    assert "</script> tag" not in out
    assert "<!--<script" not in out
    assert "<\\/script> tag" in out
    assert "<\\u0021--<script comment" in out
    # ...and both escapes must be valid JSON that round-trips to the original text
    embedded = json.loads(re.search(r'type="application/json">(.*?)</script>', out, re.S).group(1))
    assert embedded["systems"][0]["blurb"] == blurb


def test_unbalanced_gm_markers_are_rejected():
    with pytest.raises(SystemExit):
        bsm.build("player", load(), STUB.replace("<!-- GM:end -->", ""))
    with pytest.raises(SystemExit):
        bsm.build("gm", load(), STUB.replace("<!-- GM:end -->", ""))


def test_template_has_hud_controls_and_edition_split():
    tpl = (ROOT / "tools/system-map-template.html").read_text(encoding="utf-8")
    out = bsm.build("player", load(), tpl)
    for token in ('id="chart"', 'id="hud"', 'id="status"', 'id="panel"', "Frame the Reach", "Frame the Road", "fonts.googleapis.com/css2?family=Rajdhani"):
        assert token in out, token
    assert "gm-switch" not in out and "Import save" not in out
    gm = bsm.build("gm", load(), tpl)
    assert "gm-switch" in gm and "Import save" in gm
    assert not re.search(r'<script[^>]+src="https?://', out)


def test_template_has_state_and_share_code():
    tpl = (ROOT / "tools/system-map-template.html").read_text(encoding="utf-8")
    out = bsm.build("player", load(), tpl)
    for token in ("ember-age.system-map.lit", 'searchParams.get("lit")', "replaceState", "clipboard.writeText", "function toggleLit"):
        assert token in out, token
    assert "importSave" not in out and "toggleGM" not in out
    gm = bsm.build("gm", load(), tpl)
    assert "function importSave" in gm and "function toggleGM" in gm


def test_coruscant_is_the_coreward_end_of_the_road():
    d = load()
    c = next(s for s in d["systems"] if s["id"] == "coruscant")
    assert c["region"] == "far" and c["alwaysLit"] is True and c["beacon"] is False
    lane = next(l for l in d["lanes"] if {l["from"], l["to"]} == {"brentaal", "coruscant"})
    assert lane["kind"] == "living" and lane["name"] == "Perlemian Trade Route"
    tpl = (ROOT / "tools/system-map-template.html").read_text(encoding="utf-8")
    assert "road:{x:0, y:0, w:2100, h:1200}" in tpl


def test_committed_outputs_match_fresh_build():
    tpl = (ROOT / "tools/system-map-template.html").read_text(encoding="utf-8")
    d = load()
    assert (ROOT / "system-map.html").read_text(encoding="utf-8") == bsm.build("gm", d, tpl)
    assert (ROOT / "player-aids/system-map.html").read_text(encoding="utf-8") == bsm.build("player", d, tpl)


def test_real_player_build_is_gm_free_and_complete():
    tpl = (ROOT / "tools/system-map-template.html").read_text(encoding="utf-8")
    d = load()
    player, gm = bsm.build("player", d, tpl), bsm.build("gm", d, tpl)
    for token in ('"gm":', "episode seed", "GM — canon", "factions present", "ftag", 'class="fac"', "gm-on",
                  "toggleGM", "importSave", "gm-switch", "Import save", "GM:start", "GM:end"):
        assert token not in player, token
    for s in d["systems"]:
        assert f'"id": "{s["id"]}"' in player, s["id"]
        assert f'"id": "{s["id"]}"' in gm, s["id"]
