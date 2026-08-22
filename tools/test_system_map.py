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
