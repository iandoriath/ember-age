# The Ember Age campaign wiki
# GM edition = full wiki (Part V, NPC library, trackers). Player edition mechanically excludes gm/.

.PHONY: install gm players serve serve-players build clean

install:
	pip install -r requirements.txt

## Serve the GM edition locally (default: http://127.0.0.1:8000)
serve: gm
gm:
	mkdocs serve -f mkdocs.yml

## Serve the player edition locally on a second port — hand THIS url to players
serve-players:
	mkdocs serve -f mkdocs.players.yml -a 127.0.0.1:8001

## Build both editions (strict: broken links and orphan pages fail the build)
build:
	mkdocs build --strict -f mkdocs.yml
	mkdocs build --strict -f mkdocs.players.yml

clean:
	rm -rf site-gm site-players
