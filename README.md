# The Ember Age — GM Tools

*A homebrew Star Wars campaign for FFG (Edge of the Empire / Age of Rebellion / Force and Destiny), set 90 years After Ruusan.*

> Nobody broke the galaxy — everyone just stopped holding it up.

GM-only repository. Nothing here is deployed anywhere public.

## The GM Screen — the tool you actually run the campaign from

**`gm-screen.html`** — a single self-contained file. Download it (or grab it from a checkout), double-click, done: no install, no server, works offline.

- **NPCs** — all 57 stat blocks (14 nemeses, 23 rivals, 13 minion groups, 6 ships, 1 hazard), full-text searchable, filterable by type and group. Every block is an official published FFG adversary pulled as printed, cited on its `Chassis:` line.
- **Trackers** — faction clocks (each faction's crack, 0–6), the lore-fragment ledger (auto-flags when a Question hits 3 fragments and whether the tag mix upgrades the check), the beacon map, truths & corrupted conclusions.
- **Session Log** — template-driven entries, copy-out as markdown.
- **Reference** — Lore Fragments, beacon relighting, the Force rules, Obligation, the adversary primer, and a minion group-math calculator.
- **Setting** — the full campaign text: timeline, factions, acts, session one, glossary.
- **GM Truths** — Part V behind a click-to-reveal seal.

State (clocks, fragments, beacons, log) saves automatically in your browser. **Export save** writes a JSON you can move between machines or keep with your notes; **Import** loads it back.

### Rebuilding after editing content

The screen is generated from the markdown under `docs/`. Edit the content there, then:

```bash
pip install -r requirements.txt   # once
make screen                       # regenerates gm-screen.html
```

CI rebuilds it on every push and attaches it as a workflow artifact.

## The System Map — the chart you put on the table screen

**`system-map.html`** (GM edition) and **`player-aids/system-map.html`** (player edition) — a zoomable holo-chart of the Reach, the Hydian and the road to Ruusan. Click a system for its note; beacons toggle **Relight / Darken** and the lit set lives in the URL (`?lit=bannistar,enarc`), so **Share** copies a link that opens in the same state for the players.

The GM edition adds a **GM** switch (episode seeds, canon notes, faction presence) and **Import save**, which reads a GM-screen export and syncs beacon status. The player edition is built with all GM data removed from the file — send that one to the table.

Content lives in `docs/setting/systems.json`; `make map` rebuilds both files.

## What's in `docs/`

The campaign source of truth — also browsable as a local wiki (`make wiki`) if you prefer that view:

```
docs/
├── setting/      # the Withering timeline, the galaxy at 90 AR, the Awakening, glossary
├── factions/     # the six answers + two standing powers
├── campaign/     # three acts, session one
├── mechanics/    # character creation, Obligation, Lore Fragments, beacons, the Force, ships
└── gm/           # Part V (GM Truths), the NPC library, tracker templates
```

## NPC library sourcing

Every stat block is an **official published FFG adversary pulled as printed** and re-skinned — new name and flavor, same numbers. Each block carries a `Chassis:` citation (adversary + book, usually page) and an explicit adjustments note (almost always "none"). Numbers were verified against a book-and-page-cited transcription dataset of the official books. No fan-made/homebrew stat blocks anywhere. The campaign's own subsystems (Lore Fragments, beacon relighting, Wellsprings, the witness rule) are homebrew by design and live in `docs/mechanics/`.
