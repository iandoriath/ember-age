import json
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "docs/setting/systems.json"


_CACHED = None


def load_built():
    global _CACHED
    if _CACHED is None:
        _CACHED = bsm.load_data()
    return _CACHED


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
    for token in ('id="chart"', 'id="hud"', 'id="status"', 'id="panel"', "Frame the Run", "Frame the Road", "fonts.googleapis.com/css2?family=Rajdhani"):
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
    assert 'id:"road", label:"Frame the Road", box:{x:2950, y:3330, w:2800, h:3870}' in tpl


def test_committed_outputs_match_fresh_build():
    tpl = (ROOT / "tools/system-map-template.html").read_text(encoding="utf-8")
    d = load_built()
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


def test_wookieepedia_merge_is_player_safe():
    d = load()
    wp = {"enarc": {"title": "Enarc/Legends", "url": "https://x/Enarc", "facts": {"region": "Outer Rim", "affiliation": "SECRET-EMPIRE"},
                    "lead": "SECRET-LEAD Enarc was a planet.", "image": {"mime": "image/jpeg", "data": "QUJD"}},
          "veshet": {"missing": True}}
    merged = bsm.merge_wookieepedia(d, wp)
    enarc = next(s for s in merged["systems"] if s["id"] == "enarc")
    assert enarc["wp"] == {"title": "Enarc/Legends", "url": "https://x/Enarc", "facts": {"region": "Outer Rim"}, "image": {"mime": "image/jpeg", "data": "QUJD"}}
    assert enarc["gm"]["wpLead"].startswith("SECRET-LEAD")
    assert enarc["gm"]["wpFacts"] == {"affiliation": "SECRET-EMPIRE"}
    assert "wp" not in next(s for s in merged["systems"] if s["id"] == "veshet")
    tpl = (ROOT / "tools/system-map-template.html").read_text(encoding="utf-8")
    player, gm = bsm.build("player", merged, tpl), bsm.build("gm", merged, tpl)
    assert "SECRET-LEAD" not in player and "wpLead" not in player and "SECRET-EMPIRE" not in player
    assert "SECRET-LEAD" in gm and "Wookieepedia lead" in gm
    assert '"data": "QUJD"' in player and "Outer Rim" in player and "Wookieepedia" in player


def test_no_off_chart_exits_remain():
    d = load()
    assert not any(s.get("offChart") for s in d["systems"])
    assert not any("hutt-space" in (l["from"], l["to"]) for l in d["lanes"])
    tpl = (ROOT / "tools/system-map-template.html").read_text(encoding="utf-8")
    assert "offChart" not in tpl and 'class:"arrow"' not in tpl


def test_regions_are_well_formed():
    d = load()
    for r in d["regions"]:
        assert r["name"] and r["kind"] in {"nebula", "text"}, r
        assert "label" in r and len(r["label"]) == 2, r
        if r["kind"] != "text":
            for k in ("cx", "cy", "rx", "ry"):
                assert k in r, (r["name"], k)


def test_galaxy_layer_embedded_and_deduped():
    tpl = (ROOT / "tools/system-map-template.html").read_text(encoding="utf-8")
    d = load_built()
    assert len(d.get("galaxy", [])) > 1900
    names = {g[0].lower() for g in d["galaxy"]}
    for s in d["systems"]:
        assert s["name"].lower() not in names, s["name"]
    out = bsm.build("player", d, tpl)
    assert '"galaxy":' in out and "gdot" in out


def test_route_network_embedded():
    d = load_built()
    assert len(d["routes"]) >= 50
    majors = {r["n"] for r in d["routes"] if r["major"]}
    assert {"Hydian Way", "Perlemian Trade Route", "Rimma Trade Route", "Corellian Run", "Corellian Trade Spine"} <= majors
    assert len(d["nav"]["edges"]) > 2000
    names = {g[0].lower() for g in d["galaxy"]}
    assert "kashyyk" not in names and "darkknell" not in names  # aliased/hero names deduped
    kinds = {e[2] for e in d["nav"]["edges"]}
    assert "dark" in kinds and "route" in kinds
    tpl = (ROOT / "tools/system-map-template.html").read_text(encoding="utf-8")
    out = bsm.build("player", d, tpl)
    assert "Plot Course" in out and '"routes":' in out


def test_svg_geometry_governs():
    d = load_built()
    pos = {s["name"]: (s["x"], s["y"]) for s in d["systems"]}
    # the chain is projected onto the drawn Duros Space Run: canonical order holds along the arc
    assert pos["Naboo"] != pos["Enarc"]
    hero_edges = {tuple(sorted((a, b))) for a, b, k, r in d["nav"]["edges"]}
    assert tuple(sorted(("Jutrand", "Darkknell"))) in hero_edges
    assert any(rp["kind"] == "hutt" for rp in d["regionPaths"])


def test_sector_label_tier():
    d = load_built()
    secs = {s[0]: s[3] for s in d["sectors"]}
    assert len(secs) > 80 and all(n >= 2 for n in secs.values())
    assert "Grumani" in secs
    tpl = (ROOT / "tools/system-map-template.html").read_text(encoding="utf-8")
    out = bsm.build("player", d, tpl)
    assert "sectlbl" in out and "data-labels" in out


def test_galaxy_wookieepedia_merge_is_player_safe():
    d = load_built()
    tpl = (ROOT / "tools/system-map-template.html").read_text(encoding="utf-8")
    assert "openGalaxyPanel" in tpl and "wpdot" in tpl
    if "gwp" not in d:
        return  # no background pulls fetched yet
    names = {g[0] for g in d["galaxy"]}
    assert set(d["gwp"]) <= names
    for e in d["gwp"].values():
        assert set(e.get("f", {})) <= bsm.PLAYER_FACTS
    player = bsm.build("player", d, tpl)
    assert '"gwpGm"' not in player


def test_search_feature_present_in_both_editions():
    d = load_built()
    tpl = (ROOT / "tools/system-map-template.html").read_text(encoding="utf-8")
    for ed in ("gm", "player"):
        out = bsm.build(ed, d, tpl)
        assert 'id="q"' in out and "doSearch" in out and "qPick" in out
        assert "__WPBASE__" not in out and ('WPBASE = "wp/"' in out if ed == "player" else 'WPBASE = "player-aids/wp/"' in out)


def test_deep_zoom_mode():
    tpl = (ROOT / "tools/system-map-template.html").read_text(encoding="utf-8")
    assert "Math.max(vb.w / factor, 90)" in tpl and "function cullLabels" in tpl and "vector-effect:non-scaling-stroke" in tpl
    d = load_built()
    assert all(len(g) == 7 for g in d["galaxy"])  # no static show flag any more


def test_meta_defaults_keep_ember_age_chrome():
    tpl = (ROOT / "tools/system-map-template.html").read_text(encoding="utf-8")
    out = bsm.build("player", load(), tpl)
    for token in ("const META = Object.assign(", 'id:"reach", label:"Frame the Run", box:{x:4060, y:5680, w:1120, h:1280}',
                  'id:"road", label:"Frame the Road", box:{x:2950, y:3330, w:2800, h:3870}', 'id:"galaxy", label:"Galaxy"',
                  'regionLabels: {reach:"The Duros Run", hydian:"The living galaxy", far:"The far road"}',
                  'homeBox: {x0:3950, x1:5350, y0:6050, y1:null}', "features: {beacons:true, history:true, plot:true, share:true, plotDots:false}",
                  '<span id="views"></span>', "90 AR · beacon status live", "if (!META.features.beacons)", "META.link",
                  "#views{display:contents}", "META.views = DEFAULT_VIEWS", "(VIEWS.galaxy || GALAXY_BOX)",
                  "plotDots:false", "META.features.plotDots"):
        assert token in out, token
    assert "onclick=\"frame('reach')\">Frame the Run" not in out  # buttons are built from META.views now


def test_meta_is_embedded_verbatim():
    tpl = (ROOT / "tools/system-map-template.html").read_text(encoding="utf-8")
    d = load()
    d["meta"] = {"title": "Republic Survey", "views": [{"id": "home", "label": "Frame the Core", "box": {"x": 1, "y": 2, "w": 3, "h": 4}}],
                 "features": {"beacons": False}, "link": "/worlds/{name}"}
    out = bsm.build("player", d, tpl)
    embedded = json.loads(re.search(r'type="application/json">(.*?)</script>', out, re.S).group(1))
    assert embedded["meta"]["title"] == "Republic Survey" and embedded["meta"]["link"] == "/worlds/{name}"


def test_title_and_focus_knobs():
    """META.title also names the browser tab; ?focus=<name> deep-links to a world. Both no-ops for Ember Age."""
    tpl = (ROOT / "tools/system-map-template.html").read_text(encoding="utf-8")
    for ed in ("player", "gm"):
        out = bsm.build(ed, load(), tpl)
        assert "if (META.title) { document.title = META.title;" in out   # guarded, so Ember Age's own tab is untouched
        assert "<title>Ember Age — System Map</title>" in out            # ...and the markup title still stands
        assert 'searchParams.get("focus")' in out
        # the deep link resolves off the search index, prefers a hero system, and runs after the boot render
        assert "sIndex.filter(e => e.l === k)" in out and "if (hit) qPick(hit)" in out
        assert out.index('searchParams.get("focus")') > out.rindex("render();")


def test_state_styling_is_wired():
    tpl = (ROOT / "tools/system-map-template.html").read_text(encoding="utf-8")
    d = load()
    d["systems"][0]["state"] = "hub"
    d["galaxy"] = [["Ghostworld", 1.0, 2.0, "A-1", "", "Core", 0, "archived"]]
    d["routes"] = [{"n": "Old Road", "major": False, "pts": [[0, 0], [1, 1]], "state": "archived"}]
    out = bsm.build("player", d, tpl)
    embedded = json.loads(re.search(r'type="application/json">(.*?)</script>', out, re.S).group(1))
    assert embedded["systems"][0]["state"] == "hub" and embedded["galaxy"][0][7] == "archived"
    for token in ('(s.state ? " st-" + s.state : "")', ".sys.st-hub .core", ".sys.st-foothold .core",
                  "ghost:state === \"archived\"", "GHOST_A", 'rt.state === "charted"', 'rt.state === "archived"',
                  '(g.wp || (META.link && !g.ghost)) ? "pointer"', '(META.link && !e.ghost)'):
        assert token in out, token


def test_build_wpbase_override():
    tpl = STUB + '<script>const WPBASE = "__WPBASE__";</script>'
    assert 'WPBASE = "/wp/"' in bsm.build("player", load(), tpl, wpbase="/wp/")
    assert 'WPBASE = "wp/"' in bsm.build("player", load(), tpl)
    assert 'WPBASE = "player-aids/wp/"' in bsm.build("gm", load(), tpl)
    assert 'WPBASE = ""' in bsm.build("player", load(), tpl, wpbase="")


def test_embed_contract_is_wired_when_meta_asks_for_it():
    """meta.embed: the chart runs in a campaign shell's iframe and talks to it by postMessage."""
    tpl = (ROOT / "tools/system-map-template.html").read_text(encoding="utf-8")
    d = load()
    d["meta"] = {"embed": True, "link": "/worlds/{name}"}
    for ed in ("player", "gm"):
        out = bsm.build(ed, d, tpl)
        for token in ("if (META.embed)", 'window.parent.postMessage(m, "*")', 'post({type:"swm:ready"})',
                      '{type:"swm:world", name:name}', 'd.type !== "swm:focus"', 'd.type === "swm:hello"',
                      'addEventListener("message"', "document.body.getBoundingClientRect().width",
                      "e.button !== 0 || e.ctrlKey || e.metaKey || e.shiftKey || e.altKey",
                      "e.preventDefault()", "if (hit) qPick(hit)",
                      # only the frame that holds this chart may drive it, and with no frame there
                      # is nobody to hand a campaign link to, so the link is left to the browser
                      "if (ev.source !== window.parent) return;",
                      "if (window.parent === window) return;"):
            assert token in out, token
        assert "EMBED:start" not in out and "EMBED:end" not in out  # markers stripped, like the GM ones
        # the campaign link is intercepted rather than followed; the world name comes back out of META.link's own href
        assert "linkedName" in out and "decodeURIComponent" in out


def test_embed_contract_is_absent_without_meta():
    """Ember Age's own build carries no embed code at all — not even the message names."""
    tpl = (ROOT / "tools/system-map-template.html").read_text(encoding="utf-8")
    d = load()
    for ed in ("player", "gm"):
        out = bsm.build(ed, d, tpl)
        for token in ("swm:ready", "swm:world", "swm:focus", "swm:hello", "META.embed", "window.parent", "EMBED:start", "EMBED:end"):
            assert token not in out, token
    d["meta"] = {"title": "Republic Survey", "link": "/worlds/{name}"}  # other meta, no embed: still dormant
    out = bsm.build("player", d, tpl)
    assert "swm:ready" not in out and "META.embed" not in out
    assert "Open in campaign" in out  # ...while the campaign link itself is unaffected


def test_unbalanced_embed_markers_are_rejected():
    tpl = (ROOT / "tools/system-map-template.html").read_text(encoding="utf-8")
    with pytest.raises(SystemExit):
        bsm.build("player", load(), tpl.replace("<!-- EMBED:end -->", ""))


def embed_script(tpl, edition="player"):
    """The chart's own inline script, built with the embed contract switched on."""
    d = load()
    d["meta"] = {"embed": True, "link": "/worlds/{name}"}
    out = bsm.build(edition, d, tpl)
    return out[out.rindex("<script>") + len("<script>"): out.rindex("</script>")]


def test_embed_build_javascript_parses(tmp_path):
    """The block is dead code in this repo: nothing here would notice a stray brace, but swmarches' whole map would die."""
    node = shutil.which("node")
    if not node:
        pytest.skip("node not available")
    tpl = (ROOT / "tools/system-map-template.html").read_text(encoding="utf-8")
    for ed in ("player", "gm"):
        p = tmp_path / f"{ed}.js"
        p.write_text(embed_script(tpl, ed), encoding="utf-8")
        r = subprocess.run([node, "--check", str(p)], capture_output=True, text=True)
        assert r.returncode == 0, r.stdout + r.stderr


# Drives the shipped block under a fake DOM: reads the block on argv[2], exits non-zero on any failed check.
EMBED_HARNESS = r"""
const block = require("fs").readFileSync(process.argv[2], "utf8");
const posted = [], picked = [];
let clickHandler = null, msgHandler = null, bodyWidth = 1200;
const META = {embed: true, link: "/worlds/{name}"};
const window = {parent: {postMessage: (m, o) => posted.push([m, o])},
                addEventListener: (t, h) => { if (t === "message") msgHandler = h; }};
const document = {getElementById: id => ({addEventListener: (t, h) => { if (id === "panel-body" && t === "click") clickHandler = h; }}),
                  body: {getBoundingClientRect: () => ({width: bodyWidth})}};
let sIndex = null;
const INDEX = [{n:"Coruscant", l:"coruscant", k:0}, {n:"Coruscant", l:"coruscant", k:2}, {n:"Bogden 3", l:"bogden 3", k:2}];
const buildIndex = () => { sIndex = INDEX; };
const qPick = e => picked.push(e);
eval(block);

const click = (href, mod) => { let prevented = false;
  clickHandler(Object.assign({target: {closest: () => (href === null ? null : {getAttribute: k => (k === "href" ? href : null)})},
                              preventDefault: () => { prevented = true; }, button: 0}, mod || {}));
  return prevented; };
const T = [], ok = (n, c) => T.push([n, c]);
// Every real message from the shell arrives with the shell's window as its source; the block reads
// that before it reads anything else, so the driver has to speak the same way a browser does.
const shell = window.parent;
const say = d => msgHandler({source: shell, data: d});

ok("ready posted once, target *", JSON.stringify(posted) === '[[{"type":"swm:ready"},"*"]]'); posted.length = 0;
ok("campaign link intercepted, name recovered", click("/worlds/Coruscant") && JSON.stringify(posted.pop()[0]) === '{"type":"swm:world","name":"Coruscant"}');
ok("percent-encoded name decoded", click("/worlds/Bogden%203") && posted.pop()[0].name === "Bogden 3");
ok("slash in a name survives", click("/worlds/Nal%2FHutta") && posted.pop()[0].name === "Nal/Hutta");
ok("keyboard activation (button 0, no modifiers) still posts", click("/worlds/Coruscant") && posted.pop()[0].name === "Coruscant");
for (const [n, m] of [["ctrl", {ctrlKey:true}], ["meta", {metaKey:true}], ["shift", {shiftKey:true}], ["alt", {altKey:true}], ["middle", {button:1}]])
  ok(n + "-click is left to the browser", click("/worlds/Coruscant", m) === false && posted.length === 0);
ok("wookieepedia link left alone", click("https://starwars.fandom.com/wiki/Enarc") === false && posted.length === 0);
ok("non-anchor click ignored", click(null) === false && posted.length === 0);
ok("bare pattern (empty name) ignored", click("/worlds/") === false && posted.length === 0);
ok("malformed percent-escape ignored", click("/worlds/%E0%A4%A") === false && posted.length === 0);

say({type:"swm:hello"});
ok("hello re-posts ready", JSON.stringify(posted.pop()) === '[{"type":"swm:ready"},"*"]' && posted.length === 0);
say({type:"swm:focus", name:"Coruscant"});
ok("focus picks the hero entry over the galaxy dot", picked.length === 1 && picked[0].k === 0);
say({type:"swm:focus", name:"  BOGDEN 3 "});
ok("focus is trimmed and case-insensitive", picked.length === 2 && picked[1].n === "Bogden 3");
for (const bad of [{type:"swm:focus", name:"Nowhere"}, {type:"swm:focus"}, {type:"swm:focus", name:null}, {type:"other", name:"Coruscant"},
                   null, "s", 42, {}, {type:"swm:focus", name:""}])
  say(bad);
ok("unknown and foreign messages are silent no-ops", picked.length === 2 && posted.length === 0);
// Only the frame that holds this one may drive it. Without the source check, any other frame on
// the host — or a page that opened this chart in a window it kept a handle on — could pan the
// camera and open panels in it; the shell posts with target "*", so this side is the one that can
// tell who spoke. A window.open'd chart is the case that makes it more than housekeeping.
for (const stranger of [{}, null, undefined, {postMessage(){}}])
  msgHandler({source: stranger, data: {type:"swm:focus", name:"Coruscant"}});
ok("a focus from anything but the parent frame is ignored", picked.length === 2);
msgHandler({source: undefined, data: {type:"swm:hello"}});
ok("...and so is a hello, so nothing else can even make it announce itself", posted.length === 0);
bodyWidth = 0;
say({type:"swm:focus", name:"Coruscant"});
ok("focus into an unlaid-out frame is a no-op", picked.length === 2);
bodyWidth = 1200;
say({type:"swm:focus", name:"Coruscant"});
ok("focus works again once the frame has width", picked.length === 3);

for (const [n, c] of T) console.log((c ? "PASS  " : "FAIL  ") + n);
const bad = T.filter(([, c]) => !c).length;
console.log(bad ? bad + " FAILED of " + T.length : "all " + T.length + " checks pass");
process.exit(bad ? 1 : 0);
"""


# The `!head` guard, driven rather than read. META.link is the pattern the panel builds its campaign
# link from, and the block inverts it to get a world's name back out of an href. Given a pattern
# with no literal prefix — "{name}" — head and tail are both empty, and startsWith("")/endsWith("")
# are true of EVERY href: without the guard the block would take every link in the panel,
# Wookieepedia's included, preventDefault it, and post the whole URL to the shell as a world name.
# The same shipped block, one different META.
PREFIX_HARNESS = r"""
const block = require("fs").readFileSync(process.argv[2], "utf8");
const META = {embed: true, link: "{name}"};
const posted = [];
let clickHandler = null;
const window = {parent: {postMessage: (m, o) => posted.push([m, o])}, addEventListener: () => {}};
const document = {getElementById: id => ({addEventListener: (t, h) => { if (id === "panel-body" && t === "click") clickHandler = h; }}),
                  body: {getBoundingClientRect: () => ({width: 1200})}};
let sIndex = null;
const buildIndex = () => { sIndex = []; };
const qPick = () => {};
eval(block);
posted.length = 0;                        // drop the swm:ready the block posts as it initialises

let prevented = false;
clickHandler({target: {closest: () => ({getAttribute: k => (k === "href" ? "https://starwars.fandom.com/wiki/Enarc" : null)})},
              preventDefault: () => { prevented = true; }, button: 0});
const ok = !prevented && posted.length === 0;
console.log(ok ? "PASS  a link pattern with no literal prefix intercepts nothing"
               : "FAIL  every link in the panel was swallowed: prevented=" + prevented + " posted=" + JSON.stringify(posted));
process.exit(ok ? 0 : 1);
"""


# The same shipped block in a window that nothing framed, which is one right-click ("Open frame in
# new tab") away from any shell — and the address is in the shell's page source. `window.parent` is
# then this very window, so a swallowed click would post a world name to the chart's own listener,
# which handles hello and focus and nothing else: the link would simply stop working, silently, on
# a chart that otherwise looks fine. Unframed, the campaign link is left to the browser.
UNFRAMED_HARNESS = r"""
const block = require("fs").readFileSync(process.argv[2], "utf8");
const META = {embed: true, link: "/worlds/{name}"};
const posted = [];
let clickHandler = null, msgHandler = null;
const window = {addEventListener: (t, h) => { if (t === "message") msgHandler = h; },
                postMessage: (m, o) => posted.push([m, o])};
window.parent = window;                        // nothing framed this chart: the parent IS this window
const document = {getElementById: id => ({addEventListener: (t, h) => { if (id === "panel-body" && t === "click") clickHandler = h; }}),
                  body: {getBoundingClientRect: () => ({width: 1200})}};
let sIndex = null;
const picked = [];
const buildIndex = () => { sIndex = [{n:"Coruscant", l:"coruscant", k:0}]; };
const qPick = e => picked.push(e);
eval(block);
posted.length = 0;                             // the swm:ready it posted at itself on the way in

let prevented = false;
clickHandler({target: {closest: () => ({getAttribute: k => (k === "href" ? "/worlds/Coruscant" : null)})},
              preventDefault: () => { prevented = true; }, button: 0});
const T = [], ok = (n, c) => T.push([n, c]);
ok("an unframed chart does not swallow its own campaign links", prevented === false);
ok("...and posts nothing at itself in place of navigating", posted.length === 0);
// The camera still answers its own window, which is what `?focus=` already does on this chart.
msgHandler({source: window.parent, data: {type:"swm:focus", name:"Coruscant"}});
ok("a focus from its own window still works, so nothing else regressed", picked.length === 1);

for (const [n, c] of T) console.log((c ? "PASS  " : "FAIL  ") + n);
const bad = T.filter(([, c]) => !c).length;
console.log(bad ? bad + " FAILED of " + T.length : "all " + T.length + " checks pass");
process.exit(bad ? 1 : 0);
"""


def drive_embed_block(tmp_path, harness_js, name="harness"):
    """Run the shipped embed block under a fake DOM; the harness exits non-zero on a failed check."""
    node = shutil.which("node")
    if not node:
        pytest.skip("node not available")
    tpl = (ROOT / "tools/system-map-template.html").read_text(encoding="utf-8")
    js = embed_script(tpl)
    block = tmp_path / f"{name}-block.js"
    block.write_text(js[js.index("if (META.embed) {"):], encoding="utf-8")
    harness = tmp_path / f"{name}.js"
    harness.write_text(harness_js, encoding="utf-8")
    r = subprocess.run([node, str(harness), str(block)], capture_output=True, text=True)
    assert r.returncode == 0, r.stdout + r.stderr


def test_embed_block_behaves(tmp_path):
    """Execute the shipped block: ready, link interception (and the modifiers it must not steal), hello, focus."""
    drive_embed_block(tmp_path, EMBED_HARNESS)


def test_an_unframed_chart_leaves_its_campaign_links_alone(tmp_path):
    """`/map?embed=1` opened on its own is a chart with no shell above it.

    The embed build's whole job is to hand a click to the frame around it instead of navigating,
    and with no frame there is nobody to hand it to: `window.parent` is the chart's own window, so
    the post lands on its own listener, which speaks hello and focus and knows nothing about
    worlds. The click would be swallowed and nothing would happen — on a chart that looks entirely
    healthy, reached by one right-click on the shell's iframe.
    """
    drive_embed_block(tmp_path, UNFRAMED_HARNESS, "unframed")


def test_a_link_pattern_with_no_literal_prefix_intercepts_nothing(tmp_path):
    """The one branch the harness above cannot reach: it only ever supplies a well-formed pattern.

    An embedder that set `meta.link` to a bare "{name}" would, without the guard, turn the panel
    into a trap — every link in it, the Wookieepedia article most of all, would stop navigating and
    post its own URL to the parent frame as though it were the name of a world.
    """
    drive_embed_block(tmp_path, PREFIX_HARNESS, "prefix")
