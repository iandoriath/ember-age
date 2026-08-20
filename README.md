# The Ember Age — Campaign Wiki

*A homebrew Star Wars campaign for FFG (Edge of the Empire / Age of Rebellion / Force and Destiny), set 90 years After Ruusan.*

> Nobody broke the galaxy — everyone just stopped holding it up.

This repository is the campaign's management tool: the full planning material as a searchable wiki, a session/fragment/beacon tracking system, and an FFG-rules-correct NPC library.

## The tool

The wiki runs on **[MkDocs](https://github.com/mkdocs/mkdocs) + [Material for MkDocs](https://github.com/squidfunk/mkdocs-material)** — the most widely used open-source engine for TTRPG campaign wikis. Chosen over server-based campaign managers (e.g. Kanka) because everything lives as plain Markdown **in this repo**: versioned in git, readable directly on GitHub with no setup, and buildable into a proper site with search, dark mode, and navigation.

### Two editions, one source

| Edition | Config | Contains |
|---|---|---|
| **GM** | `mkdocs.yml` | Everything, including `docs/gm/` — Part V (GM Truths), the NPC library, the trackers |
| **Player** | `mkdocs.players.yml` | Everything **except** `docs/gm/`, excluded mechanically via `exclude_docs` — the GM section cannot leak |

CI builds both editions in strict mode on every push and fails if GM content ever appears in the player build.

## Quickstart

```bash
pip install -r requirements.txt   # or: make install
make gm                           # GM edition  → http://127.0.0.1:8000
make serve-players                # player edition → http://127.0.0.1:8001  (hand players this one)
make build                        # strict-build both editions
```

To publish the **player** edition to GitHub Pages: run the `wiki` workflow manually from the Actions tab with "Deploy the PLAYER edition" checked (one-time repo setup: Settings → Pages → Source: GitHub Actions). The GM edition is never deployed.

## Layout

```
docs/
├── index.md                 # campaign home
├── setting/                 # the Withering timeline, the galaxy at 90 AR, the Awakening, glossary
├── factions/                # the six answers + two standing powers
├── campaign/                # three acts, session one, session log
├── mechanics/               # character creation, Obligation, Lore Fragments,
│                            # beacon relighting, the Force, ships
└── gm/                      # ── GM EDITION ONLY ──
    ├── truths.md            # Part V: the three dials (players never see this)
    ├── npcs/                # the NPC library
    └── tools/               # fragment tracker, beacon map, faction clocks
```

## The NPC library

Every stat block is an **official published FFG adversary pulled as printed** and re-skinned for the era — new name and flavor, same numbers. Each block carries:

- **Chassis:** the printed adversary and book it comes from.
- **Adjustments:** every mechanical deviation, explicitly declared (almost always "none").

No fan-made/homebrew stat blocks are used anywhere. Minion/Rival/Nemesis mechanics follow the core rules; the library index (`docs/gm/npcs/index.md`) carries a one-screen rules primer.

## House content

The Ember Age's own subsystems — **Lore Fragments**, **beacon relighting**, the **Wellspring** and **witness** rules — are homebrew by design and documented under `docs/mechanics/`.
