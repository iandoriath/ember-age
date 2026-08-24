#!/usr/bin/env python3
"""Serve the table files over the local network so players can open them on their own devices.

    python tools/serve-table.py            # player index + handouts + player map at http://<lan-ip>:8080/
    python tools/serve-table.py --gm       # ALSO the GM lander (index.html) at /gm/, with the GM screen, GM map and GM sheet
    python tools/serve-table.py --port 9000

The pages are the same index.html / player-aids/index.html you can double-click from disk; the
server only decides which files are reachable. Windows asks once whether Python may accept
connections — allow it on private networks. Ctrl+C stops the server.
"""
import argparse
import socket
import sys
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

PLAYER_FILES = ["index.html", "system-map.html", "welcome-to-the-ember-age.html", "pocket-primer.html",
                "reading-the-dice.html", "combat-primer.html", "conditions.html", "ship-primer.html", "ship-sheet.html", "sheet-style.css"]
GM_FILES = ["index.html", "gm-screen.html", "system-map.html"]


def character_files() -> list:
    d = ROOT / "player-aids/characters"
    return [f"characters/{p.name}" for p in sorted(d.glob("*.html"))] if d.exists() else []


def wp_files() -> list:
    d = ROOT / "player-aids/wp"
    return [f"wp/{p.name}" for p in sorted(d.iterdir()) if p.suffix in (".jpg", ".png", ".webp", ".gif")] if d.exists() else []


def routes(gm: bool) -> dict:
    """url path (no leading slash) -> repo-relative file. Anything not listed is refused."""
    r = {f: f"player-aids/{f}" for f in PLAYER_FILES + character_files() + wp_files()}
    r["characters/sheet-style.css"] = "player-aids/sheet-style.css"
    r[""] = "player-aids/index.html"
    if gm:
        r.update({f"gm/{f}": f for f in GM_FILES})
        r["gm/"] = "index.html"
        # the GM lander links to player-aids/<file> relatively, so those resolve under /gm/ too (incl. gm-sheet)
        for f in PLAYER_FILES + ["gm-sheet.html"] + character_files() + wp_files():
            r[f"gm/player-aids/{f}"] = f"player-aids/{f}"
    return r


def lan_ip() -> str:
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("10.255.255.255", 1))  # no packet is sent; picks the interface with a default route
        return s.getsockname()[0]
    except OSError:
        return "127.0.0.1"
    finally:
        s.close()


class Handler(SimpleHTTPRequestHandler):
    routes: dict = {}

    def do_GET(self):
        path = self.path.split("?", 1)[0].split("#", 1)[0].lstrip("/")
        if path == "gm" and "gm/" in self.routes:  # relative links on the lander need the trailing slash
            self.send_response(301)
            self.send_header("Location", "/gm/")
            self.end_headers()
            return
        if path not in self.routes:
            self.send_error(404, "Not on the table")
            return
        self.path = "/" + self.routes[path]
        super().do_GET()

    def log_message(self, fmt, *args):
        sys.stderr.write("  %s  %s\n" % (self.client_address[0], fmt % args))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--gm", action="store_true", help="also serve the GM lander, GM screen and GM map under /gm/")
    ap.add_argument("--port", type=int, default=8080)
    args = ap.parse_args()
    Handler.routes = routes(args.gm)
    missing = sorted({f for f in Handler.routes.values() if not (ROOT / f).exists()})
    if missing:
        print("missing files (build first: make build):", ", ".join(missing), file=sys.stderr)
        return 1
    srv = ThreadingHTTPServer(("0.0.0.0", args.port), partial(Handler, directory=str(ROOT)))
    ip = lan_ip()
    print(f"\n  Table is up:  http://{ip}:{args.port}/", flush=True)
    print("  Players on this Wi-Fi open that address. Ctrl+C to stop.", flush=True)
    if args.gm:
        print(f"\n  GM lander:    http://{ip}:{args.port}/gm/", flush=True)
        print("  Not linked from the player page — but anyone on the Wi-Fi who types it can read it.", flush=True)
    print(flush=True)
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        print("\n  Table closed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
