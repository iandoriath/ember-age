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
