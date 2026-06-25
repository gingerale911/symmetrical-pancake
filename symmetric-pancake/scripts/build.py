#!/usr/bin/env python3
"""
copilot-wrap-pro :: build.py
============================

Builds the data feed for a clean, modern **Copilot Wrapped** — a Spotify-Wrapped
style recap of your year with GitHub Copilot CLI that also *roasts* you at each repo.

No fantasy theming: real repo names, real numbers, real (data-driven) burns.

It:
  1. Maps each repo to a clean professional card (display name, accent gradient).
  2. Derives extra metrics (messages/session, push:PR ratio, doc ratio, …).
  3. Generates **roasts** — curated savage one-liners blended with rule-based burns
     (so it generalises to any data / heavy contributors).
  4. Builds realm-wide **superlatives** + a final **verdict**.
  5. Writes web/wrap-data.js (window.WRAP_DATA) + data/wrap-data.json.

Usage:  python scripts/build.py
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "data" / "wrap-data.json"

# Friendly display names + accent gradients (modern, vibrant, professional).
# Real repo names come straight from the repo path; these are just demo flavor.
DISPLAY: dict[str, str] = {}
ACCENTS: dict[str, list[str]] = {
    "acme-web": ["#a78bfa", "#7c3aed"],          # violet
    "payments-api": ["#22d3ee", "#0891b2"],      # cyan
    "infra-terraform": ["#fb923c", "#ea580c"],   # orange
    "weekend-bot": ["#34d399", "#059669"],       # green
}
FALLBACK_ACCENTS = [["#a78bfa", "#7c3aed"], ["#22d3ee", "#0891b2"],
                    ["#fb923c", "#ea580c"], ["#f472b6", "#db2777"], ["#34d399", "#059669"]]

# Curated, hand-written roasts keyed by repo id — these power the bundled SAMPLE demo
# (fictional repos). Real users are roasted by the data-driven rules in rule_roasts().
CURATED: dict[str, list[str]] = {
    "acme-web": [
        "742 messages across 38 sessions on a frontend. Copilot has seen more of your CSS than your family has.",
        "71 pushes, 3 pull requests. You don't do code review, you do `git push` and a prayer.",
        "Checkout.tsx, edited 47 times. The cart works now. Probably. You stopped looking.",
    ],
    "payments-api": [
        "A payments API whose most-edited file is the webhook handler. The money's fine; the webhooks are crying.",
        "41 commits into 6 PRs. Suspiciously respectable — for someone who asked Copilot 333 times.",
    ],
    "infra-terraform": [
        "An infra repo that's a third Markdown. You documented the cluster more than you tested it.",
        "12 pushes, 1 PR. `terraform apply` straight to staging is a lifestyle, not a mistake.",
    ],
    "weekend-bot": [
        "22 files, 0 commits. A weekend project that didn't survive the weekend.",
        "One day, one burst, zero commits. The bot is sentient now — and also abandoned.",
    ],
}
VERDICT: dict[str, str] = {
    "acme-web": "A beautiful UI held together by 47 edits and hope.",
    "payments-api": "Moves money in prod, moves blame in standup.",
    "infra-terraform": "Infrastructure as code. Incidents as tradition.",
    "weekend-bot": "A Discord bot nobody invited — including you.",
}


def is_uuid(name: str) -> bool:
    return bool(re.fullmatch(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}", name.lower()))


def short_repo(repo: str) -> str:
    return repo.split("/")[-1]


def derived_metrics(k: dict) -> dict:
    s = k["stats"]
    c = k.get("contributions", {"commits": 0, "pushes": 0, "prs": 0, "issues": 0})
    md = next((l["count"] for l in k["languages"] if l["name"].lower() in ("markdown", "md")), 0)
    total_lang = sum(l["count"] for l in k["languages"]) or 1
    return {
        "msgsPerSession": round(s["turns"] / max(s["sessions"], 1), 1),
        "filesPerDay": round(s["files"] / max(s["activeDays"], 1), 1),
        "pushPrRatio": round(c["pushes"] / c["prs"], 1) if c["prs"] else None,
        "commitPrRatio": round(c["commits"] / c["prs"], 1) if c["prs"] else None,
        "docRatio": round(md / total_lang, 2),
        "topLang": max(k["languages"], key=lambda l: l["count"])["name"] if k["languages"] else "nothing",
    }


def rule_roasts(k: dict, m: dict) -> list[str]:
    s, c = k["stats"], k.get("contributions", {})
    out: list[str] = []
    if m["msgsPerSession"] >= 18:
        out.append(f"{m['msgsPerSession']} messages per session on average. Copilot files that under \u201cclingy.\u201d")
    if c.get("commits", 0) == 0 and s["files"] >= 5:
        out.append(f"{s['files']} files touched and not one commit. Schr\u00f6dinger's code: it both exists and doesn't.")
    if m["pushPrRatio"] is not None and m["pushPrRatio"] >= 10:
        out.append(f"{c.get('pushes',0)} pushes to {c.get('prs',0)} PRs. Code review is a suggestion you've chosen to ignore.")
    if m["docRatio"] >= 0.3:
        out.append(f"{int(m['docRatio']*100)}% of your files were Markdown. Writing *about* the code is still not writing the code.")
    if s["activeDays"] <= 1 and s["files"] >= 10:
        out.append(f"A whole repo raised and abandoned in {s['activeDays']} day. Speedrun, any%.")
    if m["commitPrRatio"] is not None and m["commitPrRatio"] >= 20:
        out.append(f"{c.get('commits',0)} commits funnelled into {c.get('prs',0)} PR(s). You commit like you breathe and review like you hold it.")
    return out


def build_repo(k: dict, idx: int) -> dict:
    m = derived_metrics(k)
    roasts = list(CURATED.get(k["id"], []))
    for r in rule_roasts(k, m):
        if len(roasts) >= 5:
            break
        if r not in roasts:
            roasts.append(r)
    if not roasts:
        roasts.append("Suspiciously clean. Either you're a genius, or you didn't do much here.")
    sr = short_repo(k["repo"])
    unnamed = is_uuid(sr)
    name = DISPLAY.get(k["id"]) or (("untitled-repo") if unnamed else sr)
    accent = ACCENTS.get(k["id"]) or FALLBACK_ACCENTS[idx % len(FALLBACK_ACCENTS)]
    return {
        "id": k["id"],
        "name": name,
        "fullRepo": k["repo"],
        "shortRepo": ("#" + sr[:8] if unnamed else sr),
        "unnamed": unnamed,
        "rank": k.get("rank", idx + 1),
        "accent": accent[0],
        "accent2": accent[1],
        "stats": k["stats"],
        "contributions": k.get("contributions", {"commits": 0, "pushes": 0, "prs": 0, "issues": 0}),
        "languages": k["languages"],
        "deeds": k.get("deeds", []),
        "structures": k.get("structures", []),
        "derived": m,
        "roasts": roasts,
        "verdict": VERDICT.get(k["id"]) or f"{m['topLang']} and a dream.",
    }


def build_superlatives(repos: list[dict]) -> list[dict]:
    def C(r, key):
        return r["contributions"].get(key, 0)

    needy = max(repos, key=lambda r: r["stats"]["turns"])
    cowboy = max(repos, key=lambda r: C(r, "pushes") - 8 * C(r, "prs"))
    ghost = min(repos, key=lambda r: (C(r, "commits"), r["stats"]["files"]))
    workhorse = max(repos, key=lambda r: r["stats"]["files"])
    return [
        {"award": "Most Needy", "emoji": "📎", "repo": needy["name"], "accent": needy["accent"],
         "line": f"{needy['stats']['turns']} messages sent. Copilot is considering a restraining order."},
        {"award": "Biggest Cowboy", "emoji": "🤠", "repo": cowboy["name"], "accent": cowboy["accent"],
         "line": f"{C(cowboy,'pushes')} pushes, {C(cowboy,'prs')} PRs. `git push --force` is a personality."},
        {"award": "The Ghost", "emoji": "👻", "repo": ghost["name"], "accent": ghost["accent"],
         "line": f"{ghost['stats']['files']} files, {C(ghost,'commits')} commits. Came, saw, committed nothing."},
        {"award": "The Workhorse", "emoji": "🐎", "repo": workhorse["name"], "accent": workhorse["accent"],
         "line": f"{workhorse['stats']['files']} files wrangled. Somebody had to do the actual work."},
    ]


def final_verdict(t: dict) -> str:
    return (
        f"In {t['activeDays']} days you ran {t['sessions']} sessions and sent Copilot "
        f"{t['turns']} messages — but opened just {t.get('prs', 0)} pull requests. "
        f"You don't ship software. You confide in it."
    )


def main() -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

    ap = argparse.ArgumentParser(description="Build the Copilot Wrapped web feed from wrap-data.json")
    ap.add_argument("--src", default=str(SRC), help="source wrap-data.json")
    ap.add_argument("--web-dir", default=str(ROOT / "web"), help="output web directory")
    a = ap.parse_args()

    src = json.loads(Path(a.src).read_text(encoding="utf-8"))
    kingdoms = sorted(src["kingdoms"], key=lambda k: k.get("rank", 99))
    repos = [build_repo(k, i) for i, k in enumerate(kingdoms)]
    totals = src["meta"]["totals"]

    out = {
        "meta": {
            "title": "Copilot Wrapped",
            "subtitle": "Your year with Copilot — the good, the bad, and the roast.",
            "user": src["meta"].get("user", "you"),
            "dateRange": src["meta"].get("dateRange", ""),
            "source": src["meta"].get("source", "GitHub Copilot CLI session history"),
            "generatedAt": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
            "totals": totals,
        },
        "repos": repos,
        "superlatives": build_superlatives(repos),
        "finalVerdict": final_verdict(totals),
    }

    web = Path(a.web_dir)
    web.mkdir(parents=True, exist_ok=True)
    raw = json.dumps(out, ensure_ascii=False)
    (web / "wrap-data.js").write_text(f"window.WRAP_DATA = {raw};\n", encoding="utf-8")
    (web / "wrap-data.json").write_text(json.dumps(out, indent=2, ensure_ascii=False), encoding="utf-8")

    print("🔥 copilot-wrap-pro — roasts forged\n")
    for r in repos:
        print(f"   #{r['rank']} {r['name']:18s} {len(r['roasts'])} roasts | verdict: {r['verdict']}")
    print(f"\n   Superlatives: {', '.join(s['award'] for s in out['superlatives'])}")
    print(f"   Final verdict: {out['finalVerdict']}")
    print("\n   Wrote " + str(web / "wrap-data.js") + " + wrap-data.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
