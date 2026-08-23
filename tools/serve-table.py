#!/usr/bin/env python3
"""Serve the table files over the local network so players can open them on their own devices.

    python tools/serve-table.py            # player-safe files only, http://<lan-ip>:8080/
    python tools/serve-table.py --gm       # ALSO the GM screen and GM map, under /gm/  (same Wi-Fi can reach it)
    python tools/serve-table.py --port 9000

Prints the address to read out at the table. Windows will ask once whether Python may accept
connections — allow it on private networks. Ctrl+C stops the server.
"""
import argparse
import html
import socket
import sys
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# url path -> (file, label). Order is the index order. Everything else is refused.
PLAYER = [
    ("system-map.html", ("player-aids/system-map.html", "System Map — the nav chart")),
    ("welcome.html", ("player-aids/welcome-to-the-ember-age.html", "Welcome to the Ember Age")),
    ("pocket-primer.html", ("player-aids/pocket-primer.html", "Pocket Primer")),
    ("reading-the-dice.html", ("player-aids/reading-the-dice.html", "Reading the Dice")),
    ("combat-primer.html", ("player-aids/combat-primer.html", "Combat Primer")),
    ("ship-primer.html", ("player-aids/ship-primer.html", "Starship Primer")),
    ("ship-sheet.html", ("player-aids/ship-sheet.html", "Ship Sheet")),
    ("sheet-style.css", ("player-aids/sheet-style.css", None)),
]
GM = [
    ("gm/system-map.html", ("system-map.html", "System Map — GM edition")),
    ("gm/gm-screen.html", ("gm-screen.html", "GM Screen")),
    ("gm/gm-sheet.html", ("player-aids/gm-sheet.html", "GM Sheet")),
]


def lan_ip() -> str:
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("10.255.255.255", 1))  # no packet is sent; picks the interface with a default route
        return s.getsockname()[0]
    except OSError:
        return "127.0.0.1"
    finally:
        s.close()


def index_html(routes: list, gm: bool) -> bytes:
    items = "".join(f'<li><a href="/{p}">{html.escape(lbl)}</a></li>' for p, (_, lbl) in routes if lbl and not p.startswith("gm/"))
    gm_items = "".join(f'<li><a href="/{p}">{html.escape(lbl)}</a></li>' for p, (_, lbl) in routes if lbl and p.startswith("gm/"))
    gm_block = f"<h2>GM</h2><ul>{gm_items}</ul>" if gm else ""
    return f"""<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>The Ember Age — table</title>
<style>body{{background:#050a10;color:#d7ecf8;font:18px/1.5 system-ui,"Segoe UI",Roboto,sans-serif;margin:0;padding:2rem 1.2rem;max-width:40rem}}
h1{{color:#5fc3ff;letter-spacing:.15em;text-transform:uppercase;font-size:1.1rem;margin:0 0 .2rem}}h2{{color:#e07b39;font-size:.85rem;letter-spacing:.2em;text-transform:uppercase;margin:1.6rem 0 .4rem}}
p{{color:#7fa3bb;margin:.2rem 0 1rem}}ul{{list-style:none;padding:0;margin:0}}li a{{display:block;padding:.8rem 1rem;margin:.4rem 0;border:1px solid #2a5f80;color:#d7ecf8;text-decoration:none;border-radius:.3rem}}li a:active{{border-color:#ffb454}}</style></head>
<body><h1>The Ember Age</h1><p>Table handouts — 90 AR</p><ul>{items}</ul>{gm_block}</body></html>""".encode("utf-8")


class Handler(SimpleHTTPRequestHandler):
    routes: dict = {}
    gm: bool = False

    def do_GET(self):
        path = self.path.split("?", 1)[0].split("#", 1)[0].lstrip("/")
        if path in ("", "index.html"):
            body = index_html(list(self.routes.items()), self.gm)
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        if path not in self.routes:
            self.send_error(404, "Not on the table")
            return
        self.path = "/" + self.routes[path][0]
        super().do_GET()

    def log_message(self, fmt, *args):
        sys.stderr.write("  %s  %s\n" % (self.client_address[0], fmt % args))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--gm", action="store_true", help="also serve the GM screen and GM map under /gm/")
    ap.add_argument("--port", type=int, default=8080)
    args = ap.parse_args()
    routes = dict(PLAYER + (GM if args.gm else []))
    missing = [f for f, _ in routes.values() if not (ROOT / f).exists()]
    if missing:
        print("missing files (build first: make build):", ", ".join(missing), file=sys.stderr)
        return 1
    Handler.routes, Handler.gm = routes, args.gm
    handler = partial(Handler, directory=str(ROOT))
    srv = ThreadingHTTPServer(("0.0.0.0", args.port), handler)
    ip = lan_ip()
    print(f"\n  Table is up:  http://{ip}:{args.port}/\n")
    print("  Players on this Wi-Fi open that address. Ctrl+C to stop.")
    if args.gm:
        print(f"\n  GM material is ALSO served at http://{ip}:{args.port}/gm/  — anyone on the Wi-Fi who guesses the path can read it.")
    print(flush=True)
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        print("\n  Table closed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
