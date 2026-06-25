#!/usr/bin/env python3
"""
copilot-wrap-pro :: celebrate.py
================================

A festive terminal celebration for "Copilot Wrapped" — confetti, ribbons, a
gradient block-letter banner, and a quick stats teaser. This is what the user
*sees* when they run the wrap (the cloning/setup stays quiet).

Key trick: when this is launched by an **agent** (whose shell tool captures
stdout), the party would be hidden inside a collapsed output block. So we write
the celebration straight to the **controlling terminal device** — `CONOUT$` on
Windows, `/dev/tty` on Unix — which bypasses stdout capture and shows up live in
the user's real terminal. Falls back to stdout when no terminal is available.

The animation is **append-only** (lines scroll by) so it never fights a TUI and
works on any terminal. `--no-anim` prints the same thing instantly.

Run standalone:  python scripts/celebrate.py [path/to/web/wrap-data.json] [--no-anim]
"""
from __future__ import annotations

import json
import os
import random
import shutil
import sys
import time

ESC = "\x1b"
RESET = ESC + "[0m"


# ── terminal plumbing ───────────────────────────────────────────────────────
def _enable_vt_on(stream) -> None:
    """Enable ANSI/VT processing on a specific stream's console handle (Windows)."""
    if os.name != "nt":
        return
    try:
        import ctypes
        import msvcrt

        h = msvcrt.get_osfhandle(stream.fileno())
        k = ctypes.windll.kernel32
        mode = ctypes.c_uint()
        if k.GetConsoleMode(ctypes.c_void_p(h), ctypes.byref(mode)):
            k.SetConsoleMode(ctypes.c_void_p(h), mode.value | 0x0004)
    except Exception:
        pass


def _terminal_out():
    """
    Return (stream, is_terminal). Prefer the real controlling terminal so the
    celebration is visible even when the launching agent captured stdout.
    """
    try:
        if sys.stdout.isatty():
            return sys.stdout, True
    except Exception:
        pass
    # stdout is piped/captured — try to reach the actual console/tty
    dev = "CONOUT$" if os.name == "nt" else "/dev/tty"
    try:
        f = open(dev, "w", encoding="utf-8", errors="replace")
        return f, True
    except Exception:
        return sys.stdout, False


# ── colour ──────────────────────────────────────────────────────────────────
def _fg(rgb) -> str:
    r, g, b = rgb
    return f"{ESC}[38;2;{r};{g};{b}m"


def _lerp(c1, c2, t):
    return tuple(round(c1[i] + (c2[i] - c1[i]) * t) for i in range(3))


_STOPS = [(167, 139, 250), (244, 114, 182), (251, 146, 60), (250, 204, 21)]


def _grad(t: float):
    t = max(0.0, min(1.0, t))
    seg = t * (len(_STOPS) - 1)
    i = min(int(seg), len(_STOPS) - 2)
    return _lerp(_STOPS[i], _STOPS[i + 1], seg - i)


def _gradient_line(text: str, t0: float = 0.0, t1: float = 1.0) -> str:
    n = max(1, len(text) - 1)
    out, last = [], None
    for i, ch in enumerate(text):
        if ch == " ":
            out.append(" ")
            continue
        col = _grad(t0 + (t1 - t0) * (i / n))
        if col != last:
            out.append(_fg(col))
            last = col
        out.append(ch)
    out.append(RESET)
    return "".join(out)


CONFETTI = "✦✧❄❅*∗•·°⋆+"


def _confetti_row(W: int, rng: random.Random, density: float = 0.16) -> str:
    cells = [" "] * W
    for _ in range(max(1, int(W * density))):
        cells[rng.randrange(W)] = rng.choice(CONFETTI)
    out, last = [], None
    for ch in cells:
        if ch == " ":
            if last is not None:
                out.append(RESET)
                last = None
            out.append(" ")
        else:
            col = _grad(rng.random())
            out.append(_fg(col))
            out.append(ch)
            last = col
    if last is not None:
        out.append(RESET)
    return "".join(out)


# ── 5-row block font (only the letters in WRAPPED) ──────────────────────────
_FONT = {
    "W": ["█   █", "█   █", "█ █ █", "██▄██", "█   █"],
    "R": ["███▙", "█  █", "███▛", "█ █ ", "█  █"],
    "A": ["▟██▙", "█  █", "████", "█  █", "█  █"],
    "P": ["███▙", "█  █", "███▛", "█   ", "█   "],
    "E": ["████", "█   ", "███ ", "█   ", "████"],
    "D": ["███▙", "█  █", "█  █", "█  █", "███▛"],
    " ": ["  ", "  ", "  ", "  ", "  "],
}


def _render_word(word: str):
    rows = ["", "", "", "", ""]
    for ch in word:
        g = _FONT.get(ch.upper(), _FONT[" "])
        w = max(len(r) for r in g)
        for i in range(5):
            rows[i] += g[i].ljust(w) + " "
    return [r.rstrip() for r in rows]


def _center(s: str, W: int) -> str:
    pad = max(0, (W - len(s)) // 2)
    return " " * pad + s


# ── data teaser ─────────────────────────────────────────────────────────────
def _fmt(n) -> str:
    try:
        return f"{int(n):,}"
    except Exception:
        return str(n)


def _load(feed) -> dict:
    try:
        return json.loads(open(feed, encoding="utf-8").read())
    except Exception:
        return {}


def _teaser(data: dict):
    """Return list of (text, kind) lines."""
    meta = data.get("meta", {})
    t = meta.get("totals", {})
    user = meta.get("user", "you")
    dr = meta.get("dateRange", "")
    repos = data.get("repos", [])
    sup = data.get("superlatives", [])

    lines = [(f"@{user}" + (f"   ·   {dr}" if dr else ""), "head"), ("", "x")]
    lines.append((f"{_fmt(t.get('repos',0))} repos     {_fmt(t.get('sessions',0))} sessions     {_fmt(t.get('turns',0))} messages", "stat"))
    lines.append((f"{_fmt(t.get('files',0))} files     {_fmt(t.get('commits',0))} commits     {_fmt(t.get('prs',0))} PRs", "stat"))
    if repos:
        top = repos[0]
        lines += [("", "x"), (f"★ Top repo: {top.get('name','')} — {top.get('verdict','')}", "top")]
    if sup:
        a = sup[0]
        lines.append((f"{a.get('emoji','🏆')} {a.get('award','')}: {a.get('repo','')}", "stat"))
    fv = data.get("finalVerdict", "")
    if fv:
        lines += [("", "x"), (f"🔥 {fv}", "verdict")]
    return lines


_KIND_COLOR = {
    "head": (167, 139, 250),
    "top": (250, 204, 21),
    "verdict": (251, 146, 60),
    "stat": (226, 232, 240),
}


# ── the show (append-only, terminal-directed) ───────────────────────────────
def _show(out, data: dict, animate: bool) -> None:
    try:
        W = shutil.get_terminal_size((80, 24)).columns
    except Exception:
        W = 80
    W = max(40, min(W - 2, 78))
    rng = random.Random()

    def emit(s: str = "", delay: float = 0.0):
        out.write(s + "\n")
        try:
            out.flush()
        except Exception:
            pass
        if animate and delay:
            time.sleep(delay)

    emit()
    for _ in range(4):
        emit("  " + _confetti_row(W - 4, rng), 0.07)

    emit()
    emit(_gradient_line(_center("✦ ✧ ✦   C O P I L O T   ✦ ✧ ✦", W)), 0.05)
    emit()
    for row in _render_word("WRAPPED"):
        emit(_gradient_line(_center(row, W), 0.12, 1.0), 0.09)
    emit()

    for _ in range(2):
        emit("  " + _confetti_row(W - 4, rng), 0.07)
    emit()

    for text, kind in _teaser(data):
        if not text:
            emit()
            continue
        col = _KIND_COLOR.get(kind, (226, 232, 240))
        emit("   " + _fg(col) + text + RESET, 0.05)

    emit()
    emit("  " + _confetti_row(W - 4, rng), 0.06)
    emit(_gradient_line(_center("🎉  Enjoy your Copilot Wrapped!  🎉", W)))
    emit()


def celebrate(feed: str, animate: bool = True) -> None:
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    data = _load(feed)
    out, is_term = _terminal_out()
    _enable_vt_on(out)
    if os.environ.get("NO_COLOR"):
        animate = False
    try:
        _show(out, data, animate=animate and is_term)
    except Exception:
        try:
            _show(sys.stdout, data, animate=False)
        except Exception:
            pass
    finally:
        if out is not sys.stdout:
            try:
                out.close()
            except Exception:
                pass


def main() -> int:
    args = sys.argv[1:]
    no_anim = "--no-anim" in args
    args = [a for a in args if not a.startswith("--")]
    import pathlib
    feed = args[0] if args else str(
        pathlib.Path(__file__).resolve().parent.parent / "web" / "wrap-data.json")
    celebrate(feed, animate=not no_anim)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
