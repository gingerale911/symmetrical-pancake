#!/usr/bin/env python3
"""
copilot-wrap-pro :: extract.py
==============================

Reads YOUR OWN local GitHub Copilot CLI history and emits ``data/wrap-data.json``
(the shape ``build.py`` consumes). Everything is local & offline — no cloud, no
network, no privileged tooling. Any user with the Copilot CLI installed can run it.

Data sources (per user, on their machine):
  * ``~/.copilot/session-store.db``        -> sessions (repo / cwd / branch) + turns (messages)
  * ``~/.copilot/session-state/<id>/events.jsonl`` -> tool calls (file edits + git signal)

It groups sessions by repository (falling back to the working-folder name when a
session has no repo), reconstructs per-repo metrics, languages, most-edited files,
"deeds" (from session summaries) and git contributions, then writes the feed.

Usage:
  python scripts/extract.py [--out PATH] [--top N] [--min-turns N] [--user NAME]
                            [--store PATH] [--state-dir PATH]
"""
from __future__ import annotations

import argparse
import ast
import collections
import glob
import json
import os
import re
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# extension -> (display language, swatch colour)
EXT2LANG = {
    ".cs": ("C#", "#9d6cff"), ".csx": ("C#", "#9d6cff"),
    ".ts": ("TypeScript", "#3178c6"), ".tsx": ("TSX", "#4ec9b0"),
    ".js": ("JavaScript", "#f1e05a"), ".jsx": ("JSX", "#f7df1e"), ".mjs": ("JavaScript", "#f1e05a"),
    ".py": ("Python", "#3572A5"), ".md": ("Markdown", "#9fb3c8"), ".mdx": ("Markdown", "#9fb3c8"),
    ".json": ("JSON", "#cbcb41"), ".jsonc": ("JSON", "#cbcb41"),
    ".css": ("CSS", "#563d7c"), ".scss": ("SCSS", "#c6538c"), ".less": ("Less", "#1d365d"),
    ".html": ("HTML", "#e34c26"), ".cshtml": ("Razor", "#512be4"),
    ".go": ("Go", "#00ADD8"), ".rs": ("Rust", "#dea584"), ".java": ("Java", "#b07219"),
    ".rb": ("Ruby", "#701516"), ".php": ("PHP", "#4F5D95"), ".swift": ("Swift", "#F05138"),
    ".kt": ("Kotlin", "#A97BFF"), ".c": ("C", "#555555"), ".cpp": ("C++", "#f34b7d"),
    ".cc": ("C++", "#f34b7d"), ".h": ("C header", "#6e7681"), ".hpp": ("C++ header", "#6e7681"),
    ".sh": ("Shell", "#89e051"), ".bash": ("Shell", "#89e051"), ".ps1": ("PowerShell", "#5391fe"),
    ".yml": ("YAML", "#cb171e"), ".yaml": ("YAML", "#cb171e"), ".toml": ("TOML", "#9c4221"),
    ".sql": ("SQL", "#e38c00"), ".xml": ("XML", "#0060ac"), ".csproj": ("csproj", "#68a063"),
    ".props": ("props", "#c98a3a"), ".targets": ("targets", "#c98a3a"),
    ".txt": ("Text", "#9fb3c8"), ".bicep": ("Bicep", "#519aba"), ".tf": ("Terraform", "#844FBA"),
    ".vue": ("Vue", "#41b883"), ".svelte": ("Svelte", "#ff3e00"), ".dart": ("Dart", "#00B4AB"),
}
DEFAULT_COLOR = "#8b93a7"
WRITE_TOOLS = {"create", "edit", "str_replace", "str_replace_editor", "apply_patch", "multi_edit", "write"}
SHELL_TOOLS = {"powershell", "bash", "shell", "sh", "cmd", "zsh"}

RE_COMMIT = re.compile(r"\bgit\s+commit\b")
RE_PUSH = re.compile(r"\bgit\s+push\b")
RE_PR = re.compile(r"\bgh\s+pr\s+create\b")
RE_ISSUE = re.compile(r"\bgh\s+issue\s+create\b")


def slugify(name: str) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
    return s or "repo"


def as_obj(v):
    """events.jsonl 'data'/'arguments' may be a dict, a JSON string, or a py-repr string."""
    if isinstance(v, dict):
        return v
    if isinstance(v, str):
        for parse in (json.loads, ast.literal_eval):
            try:
                r = parse(v)
                if isinstance(r, dict):
                    return r
            except Exception:
                pass
    return {}


def parse_events(path: str):
    """Return (file_events:list[path], git:dict, days:set) from one events.jsonl."""
    file_events, days = [], set()
    git = {"commits": 0, "pushes": 0, "prs": 0, "issues": 0}
    try:
        f = open(path, encoding="utf-8")
    except OSError:
        return file_events, git, days
    with f:
        for line in f:
            line = line.strip()
            if not line or '"tool.execution_start"' not in line:
                # cheap pre-filter; still need timestamps from any event though
                if not line:
                    continue
            try:
                ev = json.loads(line)
            except Exception:
                continue
            ts = ev.get("timestamp")
            if isinstance(ts, str) and len(ts) >= 10:
                days.add(ts[:10])
            if ev.get("type") != "tool.execution_start":
                continue
            data = as_obj(ev.get("data"))
            tool = (data.get("toolName") or data.get("tool") or "").lower()
            args = as_obj(data.get("arguments"))
            if tool in WRITE_TOOLS:
                p = args.get("path") or args.get("file_path") or args.get("filePath")
                if isinstance(p, str) and p.strip():
                    file_events.append(p.strip())
            elif tool in SHELL_TOOLS:
                cmd = args.get("command") or args.get("cmd") or ""
                if isinstance(cmd, list):
                    cmd = " ".join(str(x) for x in cmd)
                if isinstance(cmd, str) and cmd:
                    git["commits"] += len(RE_COMMIT.findall(cmd))
                    git["pushes"] += len(RE_PUSH.findall(cmd))
                    git["prs"] += len(RE_PR.findall(cmd))
                    git["issues"] += len(RE_ISSUE.findall(cmd))
    return file_events, git, days


def lang_for(path: str):
    ext = os.path.splitext(path)[1].lower()
    if ext in EXT2LANG:
        return EXT2LANG[ext]
    if ext:
        return (ext.lstrip("."), DEFAULT_COLOR)
    return (None, None)


def repo_key(repository, cwd):
    if repository and repository.strip():
        return repository.strip(), False
    base = os.path.basename(str(cwd or "").rstrip("/\\")) or "local-workspace"
    return base, True


def main() -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

    ap = argparse.ArgumentParser(description="Extract local Copilot CLI history into wrap-data.json")
    ap.add_argument("--out", default=str(ROOT / "data" / "wrap-data.json"))
    ap.add_argument("--top", type=int, default=6, help="max repositories to feature")
    ap.add_argument("--min-turns", type=int, default=4, help="ignore repos with fewer messages")
    ap.add_argument("--user", default=os.environ.get("USERNAME") or os.environ.get("USER") or "you")
    ap.add_argument("--store", default=os.path.expanduser("~/.copilot/session-store.db"))
    ap.add_argument("--state-dir", default=os.path.expanduser("~/.copilot/session-state"))
    a = ap.parse_args()

    if not os.path.exists(a.store):
        print(f"!! session-store.db not found at {a.store}", file=sys.stderr)
        print("   Is the GitHub Copilot CLI installed and used on this machine?", file=sys.stderr)
        return 2

    con = sqlite3.connect("file:" + a.store.replace("\\", "/") + "?mode=ro", uri=True)
    con.row_factory = sqlite3.Row
    cur = con.cursor()

    sessions = cur.execute(
        "SELECT id, repository, cwd, branch, summary, created_at FROM sessions").fetchall()
    turns_by_session = {r["session_id"]: r["n"] for r in cur.execute(
        "SELECT session_id, COUNT(*) n FROM turns GROUP BY session_id")}
    days_by_session = collections.defaultdict(set)
    for r in cur.execute("SELECT session_id, timestamp FROM turns WHERE timestamp IS NOT NULL"):
        ts = r["timestamp"]
        if isinstance(ts, str) and len(ts) >= 10:
            days_by_session[r["session_id"]].add(ts[:10])
    con.close()

    # group sessions into repos
    repos = {}  # key -> aggregate
    for s in sessions:
        key, unnamed = repo_key(s["repository"], s["cwd"])
        g = repos.setdefault(key, {
            "repo": key, "unnamed": unnamed, "sessions": 0, "turns": 0,
            "file_events": [], "git": collections.Counter(), "days": set(),
            "summaries": [], "session_ids": [],
        })
        g["sessions"] += 1
        g["turns"] += turns_by_session.get(s["id"], 0)
        g["days"] |= days_by_session.get(s["id"], set())
        g["session_ids"].append(s["id"])
        summ = (s["summary"] or "").strip()
        if summ:
            g["summaries"].append((turns_by_session.get(s["id"], 0), summ))

    # enrich each repo from its sessions' events.jsonl
    for key, g in repos.items():
        for sid in g["session_ids"]:
            ev_path = os.path.join(a.state_dir, sid, "events.jsonl")
            fe, git, days = parse_events(ev_path)
            g["file_events"].extend(fe)
            for k, v in git.items():
                g["git"][k] += v
            g["days"] |= days

    # turn aggregates into the build.py "kingdom" shape
    kingdoms = []
    for key, g in repos.items():
        if g["turns"] < a.min_turns:
            continue
        paths = g["file_events"]
        distinct_files = sorted(set(paths))
        lang_counts, lang_color = collections.Counter(), {}
        for p in paths:
            name, color = lang_for(p)
            if not name:
                continue
            lang_counts[name] += 1
            lang_color[name] = color
        languages = [{"name": n, "count": c, "color": lang_color[n]}
                     for n, c in lang_counts.most_common(8)]
        file_edit_counts = collections.Counter(os.path.basename(p) for p in paths)
        structures = [{"name": n, "edits": c} for n, c in file_edit_counts.most_common(5)]
        deeds = [s for _, s in sorted(g["summaries"], reverse=True)][:4]
        days = sorted(g["days"])
        kingdoms.append({
            "id": slugify(os.path.basename(key)),
            "repo": key,
            "stats": {
                "sessions": g["sessions"], "turns": g["turns"],
                "files": len(distinct_files), "fileEvents": len(paths),
                "activeDays": len(days) or 1,
                "firstDay": days[0] if days else "", "lastDay": days[-1] if days else "",
            },
            "contributions": {
                "commits": g["git"]["commits"], "pushes": g["git"]["pushes"],
                "prs": g["git"]["prs"], "issues": g["git"]["issues"],
            },
            "languages": languages,
            "deeds": deeds,
            "structures": structures,
        })

    # rank by an influence score and keep the top N
    def influence(k):
        s, c = k["stats"], k["contributions"]
        return s["turns"] + 6 * s["files"] + 10 * c["commits"] + 25 * c["prs"]

    kingdoms.sort(key=influence, reverse=True)
    kingdoms = kingdoms[: a.top]
    for i, k in enumerate(kingdoms):
        k["rank"] = i + 1

    # de-dupe ids
    seen = collections.Counter()
    for k in kingdoms:
        seen[k["id"]] += 1
        if seen[k["id"]] > 1:
            k["id"] = f"{k['id']}-{seen[k['id']]}"

    # totals across featured repos
    all_days = set()
    for k in kingdoms:
        s = k["stats"]
        if s["firstDay"]:
            all_days.add(s["firstDay"])
        if s["lastDay"]:
            all_days.add(s["lastDay"])
    # better: union the per-repo day sets we already computed
    union_days = set()
    for key, g in repos.items():
        if any(k["repo"] == key for k in kingdoms):
            union_days |= g["days"]
    totals = {
        "repos": len(kingdoms),
        "sessions": sum(k["stats"]["sessions"] for k in kingdoms),
        "turns": sum(k["stats"]["turns"] for k in kingdoms),
        "files": sum(k["stats"]["files"] for k in kingdoms),
        "activeDays": len(union_days) or 1,
        "commits": sum(k["contributions"]["commits"] for k in kingdoms),
        "pushes": sum(k["contributions"]["pushes"] for k in kingdoms),
        "prs": sum(k["contributions"]["prs"] for k in kingdoms),
        "issues": sum(k["contributions"]["issues"] for k in kingdoms),
    }
    date_range = ""
    if union_days:
        lo, hi = min(union_days), max(union_days)
        try:
            lo_d = datetime.strptime(lo, "%Y-%m-%d")
            hi_d = datetime.strptime(hi, "%Y-%m-%d")
            date_range = f"{lo_d.strftime('%d %b')} \u2014 {hi_d.strftime('%d %b, %Y')}"
        except Exception:
            date_range = f"{lo} \u2014 {hi}"

    out = {
        "meta": {
            "user": a.user,
            "dateRange": date_range,
            "source": "your local GitHub Copilot CLI session history",
            "generatedAt": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
            "totals": totals,
        },
        "kingdoms": kingdoms,
    }

    out_path = Path(a.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(out, indent=2, ensure_ascii=False), encoding="utf-8")

    print(f"\U0001f4e6 extracted {len(kingdoms)} repositories from your local Copilot history\n")
    for k in kingdoms:
        s, c = k["stats"], k["contributions"]
        print(f"   #{k['rank']} {k['repo'][:42]:42s} "
              f"sess={s['sessions']:<3d} msgs={s['turns']:<4d} files={s['files']:<4d} "
              f"commits={c['commits']:<3d} prs={c['prs']}")
    print(f"\n   Totals: {totals['sessions']} sessions, {totals['turns']} messages, "
          f"{totals['activeDays']} active days")
    print(f"   Wrote {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
