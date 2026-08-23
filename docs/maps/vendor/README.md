# Vendored map data

- `planets.json` — the SWGalacticMap dataset (github.com/parzivail/SWGalacticMap): every Legends planet with
  Atlas grid square and sub-grid position. Community-compiled; no license stated; vendored here for a private GM tool.
- `hyperlanes_db.json` — hyperlane route sequences from StarWarsMap (github.com/Wason1797/StarWarsMap):
  ~60 named routes as ordered lists of the systems along them. Same caveat.

`tools/build-system-map.py` turns these into the map's background planets, route polylines and the
Plot Course navigation graph. The reference plates (`../GFFA-high.jpg`, `../galaxy_map.png`) stay untracked.
