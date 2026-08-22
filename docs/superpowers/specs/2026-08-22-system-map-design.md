# System Map — design

*Interactive, explorable holo-chart of the campaign's geography. GM edition with a GM layer; player edition built separately with GM data stripped.*

## Goal

A sleek, Star Wars nav-computer-style star chart of the Grumani Reach and the road beyond it. Players use it at the table as a prop; the GM uses the same chart with a hidden layer of seeds, canon notes and faction presence. Beacon lit/dark state is the thing that changes session to session and must be easy to flip and to share.

## Decisions (from brainstorming)

- **Audience:** both. One source, two build outputs. The player edition has GM content **removed at build time**, not hidden.
- **Extent:** the Reach in detail, zoomable out to the Hydian Way and the far road to Ruusan (faded, labels fade in with zoom).
- **State:** the map keeps its own lit-beacon set (localStorage), overridable by `?lit=` in the URL; Share copies a URL with the current state. GM edition can import the GM-screen save JSON to pick up beacon statuses.
- **Look:** hybrid — holo-blue chrome (grid, HUD, dark lanes, dark beacons) with the campaign's ember/gold reserved for lit beacons and living lanes. Relighting brings warmth into a cold chart.
- **Tech:** hand-placed SVG + vanilla JS, single self-contained HTML file per edition, no dependencies, works from disk.

## Components

### 1. Source data — `docs/setting/systems.json`

```json
{
  "systems": [
    {"id":"bannistar","name":"Bannistar Station","sub":"Okrent's Drift","x":..,"y":..,
     "region":"reach","beacon":true,"hop":0,"alwaysLit":false,
     "blurb":"player-safe text",
     "gm":{"seed":"Session One","canon":"...","factions":["vigil","admiralty"]}}
  ],
  "lanes": [ {"from":"bannistar","to":"enarc","kind":"dark","name":"Duros Space Run"} ]
}
```

- `region`: `reach` | `hydian` | `far`. Controls label fade thresholds and default framing.
- `beacon`: system has a beacon that can be lit/dark. `alwaysLit` for Darkknell/Eriadu and the living galaxy.
- `hop`: position in the Duros Space Run chain (0 = Bannistar … 7 = Jutrand); drives the HUD status strip.
- Lane `kind`: `living` | `dark` | `smuggler` | `far` | `fraying` (Teraab stretch).
- Content lifted from `docs/setting/geography.md` and `docs/gm/tools/beacon-map.md`. Systems: Bannistar, Enarc, Alui, Verdanth, Aplooine, Sanrafsix, Heptooine, Jutrand, Darkknell, Eriadu; Fostin Nine, Syned, Omwat (Sanrafsix Corridor); Chelloa, Byllura, Aquilaris, Gazzari (dead spurs); Veshet (off the Corridor); Malastare, Denon, Brentaal, Lantillies, Kashyyyk, Teraab, Ruusan (far road). Naboo marked as an Enarc Run endpoint off-chart.

### 2. Build — `tools/build-system-map.py` + `tools/system-map-template.html`

- Reads the template and the JSON, embeds the data as a `<script id="data" type="application/json">` block.
- Writes `system-map.html` (GM edition: full data, GM switch present).
- Writes `player-aids/system-map.html` (player edition: every `gm` key deleted from the data; the template's `<!-- GM:start -->…<!-- GM:end -->` regions removed; `EDITION = "player"`).
- `make map` target; added to the CI workflow alongside the screen build.
- Both outputs are self-contained (Google Fonts link for Rajdhani is the only external reference, as in the GM screen).

### 3. The chart (template)

- Full-viewport `<svg>` with `viewBox` pan/zoom: wheel/pinch zoom around the cursor, drag to pan, buttons for +/−, **Frame the Reach**, **Frame the Road**.
- Background: near-black, faint holo grid, radial vignette, subtle scanline overlay (CSS, not animated heavily).
- Lanes: hairlines. `living` ember solid; `dark` dim blue dashed; `smuggler` dim blue dotted; `far` faint blue; `fraying` blue with increasing dash gaps and opacity falloff.
- Systems: `dark` beacon = hollow cold-blue ring; `lit` = ember core, soft pulse, glow filter; `alwaysLit` = steady gold. Non-beacon systems = small blue dot. Hop numbers on the chain.
- Labels: Rajdhani, upper-case, letter-spaced; `hydian`/`far` labels fade in as zoom crosses thresholds.
- HUD (HTML over the SVG): title block; a **BEACON STATUS** strip listing the chain ⌂→7→★ with lit/dark pips; zoom/frame controls; **Share**; GM edition only: **GM** switch and **Import save**.

### 4. Interaction

- Hover: system + its lanes brighten; others dim slightly.
- Click: side panel slides in — name, sub-name, region, lanes, blurb, beacon status with **Relight / Darken** toggle (only for `beacon && !alwaysLit`). Escape/close returns.
- GM layer (GM edition, switch on): panel shows seed, canon notes, faction presence; chart draws small faction glyphs around systems with `gm.factions`.

### 5. State & share

- `lit` = Set of system ids. Load order: `?lit=a,b` in URL if present → else localStorage → else default (`vesta9` is not a chart system — Vesta-9 is the beacon at Bannistar; the chain's hop-0 beacon starts lit).
- Toggling writes localStorage and updates the URL via `history.replaceState` (so the address bar always shares correctly).
- **Share** copies `location.href` to the clipboard and flashes "copied".
- **Import save** (GM): reads the GM-screen export JSON; beacon statuses from its beacon tracker map to chart ids by name (exact key shape confirmed against `tools/gm-screen-template.html` during implementation). Unmatched names are ignored and reported in the HUD.

### 6. Testing

- `tools/test_build_system_map.py` (pytest): player output contains no `"gm"` key, no GM marker regions, no "Import save"; GM output contains them; both embed every system id; the JSON parses and every lane endpoint exists.
- Manual: open both editions from disk in Chrome; pan/zoom, toggle, share URL round-trip, GM switch.

## Out of scope

- Editing system data in the browser (edit the JSON and rebuild).
- Live sync with the GM screen (import is one-shot).
- Mobile-first layout (it should not break on a tablet, but the prop is a laptop/TV screen).
