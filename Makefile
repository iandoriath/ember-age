# The Ember Age — GM tools

.PHONY: install screen wiki build map wookieepedia characters table clean

install:
	pip install -r requirements.txt

## Build the GM screen (single-file interactive app) -> gm-screen.html
screen:
	python3 tools/build-gm-screen.py

## Serve the GM wiki locally (optional reference view of the same content)
wiki:
	mkdocs serve -f mkdocs.yml

## Rebuild the player-aid handouts (HTML; print to PDF from any browser)
aids:
	python3 tools/build-player-aids.py

## Build the system map (GM edition -> system-map.html, player edition -> player-aids/system-map.html)
map:
	python3 tools/build-system-map.py

## Build character sheets + the GM screen's crew roster from hyperdrive/*.json
characters:
	python3 tools/build-characters.py

## Refresh Wookieepedia summaries + lead images for the map (network; writes docs/setting/wookieepedia.json)
wookieepedia:
	python3 tools/fetch-wookieepedia.py

## Serve the player handouts + player map to devices on the local Wi-Fi (http://<lan-ip>:8080/); add GM=1 to also serve GM files under /gm/
table:
	python3 tools/serve-table.py $(if $(GM),--gm,)

## Strict-build wiki + GM screen + player aids + system map (what CI runs)
build:
	mkdocs build --strict -f mkdocs.yml
	python3 tools/build-player-aids.py
	python3 tools/build-characters.py
	python3 tools/build-gm-screen.py
	python3 tools/build-system-map.py

clean:
	rm -rf site-gm gm-screen.html system-map.html player-aids/system-map.html
