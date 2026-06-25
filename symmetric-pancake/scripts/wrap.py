#!/usr/bin/env python3
"""
copilot-wrap-pro :: wrap.py  (the one-command entry point)
==========================================================

Generates YOUR personal "Copilot Wrapped" from your local GitHub Copilot CLI
history and opens it in the browser. One command, fully local, no network:

    python scripts/wrap.py

Pipeline:  extract.py (read ~/.copilot) -> build.py (roast + web feed) -> serve -> open

This is the thing you'd wire to a ``wrap`` shell alias / ``/wrap``-style command
so anyone can run it on their own machine. See README "Ship it" for distribution.

Options:
    --port N        port to serve on (default 8799)
    --no-open       build + serve but don't auto-open the browser
    --no-serve      just (re)generate the data + web bundle, then exit
    --no-anim       skip the terminal celebration animation
    --verbose       show the underlying extract/build output (hidden by default)
    --top N         max repositories to feature (default 6)
    --user NAME     override the @handle shown on the cover
    --min-turns N   ignore repos with fewer messages (default 4)
"""
from __future__ import annotations

import argparse
import os
import subprocess
import sys
import threading
import webbrowser
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = ROOT / "scripts"
WEB = ROOT / "web"
DATA = ROOT / "data" / "wrap-data.json"

# soft palette for the few status lines we do show
_DIM = "\x1b[2m"
_RESET = "\x1b[0m"


def run(args: list[str], quiet: bool, step: str) -> int:
    """Run a pipeline step. Quiet by default — capture output, only show on failure."""
    if not quiet:
        print(f"{_DIM}» {' '.join(str(a) for a in args)}{_RESET}")
        return subprocess.call([sys.executable] + args)
    proc = subprocess.run([sys.executable] + args, capture_output=True, text=True,
                          encoding="utf-8", errors="replace")
    if proc.returncode != 0:
        sys.stderr.write(f"\n!! {step} failed:\n")
        sys.stderr.write((proc.stdout or "") + (proc.stderr or "") + "\n")
    return proc.returncode


def main() -> int:
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8")
        except Exception:
            pass

    ap = argparse.ArgumentParser(description="Generate & open your Copilot Wrapped (all local)")
    ap.add_argument("--port", type=int, default=8799)
    ap.add_argument("--no-open", action="store_true")
    ap.add_argument("--no-serve", action="store_true")
    ap.add_argument("--no-anim", action="store_true")
    ap.add_argument("--verbose", action="store_true")
    ap.add_argument("--top", type=int, default=6)
    ap.add_argument("--min-turns", type=int, default=4)
    ap.add_argument("--user", default=None)
    a = ap.parse_args()
    quiet = not a.verbose

    if quiet:
        print("\n  Unwrapping your year with Copilot…\n")

    # 1) extract local history -> data/wrap-data.json
    extract = [str(SCRIPTS / "extract.py"), "--out", str(DATA),
               "--top", str(a.top), "--min-turns", str(a.min_turns)]
    if a.user:
        extract += ["--user", a.user]
    if run(extract, quiet, "history scan") != 0:
        return 1

    # 2) build roasts + web feed
    if run([str(SCRIPTS / "build.py"), "--src", str(DATA), "--web-dir", str(WEB)], quiet, "build") != 0:
        return 1

    # 3) the celebration — this is what the user actually watches
    try:
        from celebrate import celebrate
    except Exception:
        sys.path.insert(0, str(SCRIPTS))
        try:
            from celebrate import celebrate
        except Exception:
            celebrate = None
    if celebrate is not None:
        celebrate(str(WEB / "wrap-data.json"), animate=not a.no_anim)

    if a.no_serve:
        index = WEB / "index.html"
        if not a.no_open:
            try:
                webbrowser.open(index.as_uri())
                print(f"  Opened in your browser ·  {index}\n")
            except Exception:
                print(f"  Open this in any browser:  {index}\n")
        else:
            print(f"  Built:  {index}\n")
        return 0

    # 4) serve web/ and open
    handler = partial(SimpleHTTPRequestHandler, directory=str(WEB))
    try:
        # quiet server: swallow the default request logging
        class _QuietHandler(SimpleHTTPRequestHandler):
            def log_message(self, *args):
                pass
        handler = partial(_QuietHandler, directory=str(WEB))
        httpd = ThreadingHTTPServer(("127.0.0.1", a.port), handler)
    except OSError as e:
        print(f"\n!! could not bind port {a.port}: {e}", file=sys.stderr)
        print(f"   Try a different --port, or just open {WEB / 'index.html'} directly.")
        return 1

    url = f"http://localhost:{a.port}/index.html"
    print(f"  Live at  {url}   ·   Ctrl+C to stop\n")
    if not a.no_open:
        threading.Timer(0.6, lambda: webbrowser.open(url)).start()
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\n  stopped.")
        httpd.shutdown()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
