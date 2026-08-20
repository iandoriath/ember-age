# The Ember Age — GM tools

.PHONY: install screen wiki build clean

install:
	pip install -r requirements.txt

## Build the GM screen (single-file interactive app) -> gm-screen.html
screen:
	python3 tools/build-gm-screen.py

## Serve the GM wiki locally (optional reference view of the same content)
wiki:
	mkdocs serve -f mkdocs.yml

## Strict-build wiki + GM screen (what CI runs)
build:
	mkdocs build --strict -f mkdocs.yml
	python3 tools/build-gm-screen.py

clean:
	rm -rf site-gm gm-screen.html
