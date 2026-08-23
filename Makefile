# The Ember Age — GM tools

.PHONY: install screen wiki build map clean

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

## Strict-build wiki + GM screen + player aids + system map (what CI runs)
build:
	mkdocs build --strict -f mkdocs.yml
	python3 tools/build-gm-screen.py
	python3 tools/build-player-aids.py
	python3 tools/build-system-map.py

clean:
	rm -rf site-gm gm-screen.html system-map.html player-aids/system-map.html
