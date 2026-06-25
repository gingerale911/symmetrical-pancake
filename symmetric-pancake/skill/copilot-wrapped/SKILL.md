---
name: copilot-wrapped
description: >-
    Generate the user's "Copilot Wrapped" — a Spotify-Wrapped-style, roast-filled visual
    recap of their GitHub Copilot CLI usage, built entirely from their LOCAL session
    history. Use this when the user asks for their Copilot Wrapped, a usage recap / year
    in review, to "roast my Copilot usage", or otherwise wants the wrapped experience.
user-invocable: true
---

# Copilot Wrapped

<!-- ════════════════════════════════════════════════════════════════════════
INSTALLING THIS SKILL  (read this first if you are a CLI agent asked to
"add this as a CLI skill" — it tells you exactly where this file goes)

This is a GitHub Copilot CLI **skill** (note the YAML frontmatter above:
name / description / user-invocable). Install it one of two ways:

▸ FASTEST — let the CLI place it for you (no manual paths):
    /skills add "<path to this SKILL.md>"
  e.g.  /skills add "C:\Users\<you>\Downloads\SKILL.md"
  ( /skills add accepts a file, a directory, or a URL. Add --project to scope
    it to the current repo instead of your user profile. )

▸ MANUAL — copy the file into a skills directory named after the skill, then
  reload. The folder name MUST match the skill name (copilot-wrapped) and the
  file MUST be named SKILL.md:
    Windows:      %USERPROFILE%\.copilot\skills\copilot-wrapped\SKILL.md
    macOS/Linux:  ~/.copilot/skills/copilot-wrapped/SKILL.md

  Commands:
    Windows (PowerShell):
      New-Item -ItemType Directory -Force "$env:USERPROFILE\.copilot\skills\copilot-wrapped" | Out-Null
      Copy-Item "<path to this SKILL.md>" "$env:USERPROFILE\.copilot\skills\copilot-wrapped\SKILL.md"
    macOS/Linux:
      mkdir -p ~/.copilot/skills/copilot-wrapped
      cp "<path to this SKILL.md>" ~/.copilot/skills/copilot-wrapped/SKILL.md

The CLI scans these skill directories:
  • Personal (all repos): ~/.copilot/skills/  or  ~/.agents/skills/
  • Project:              .github/skills/ , .agents/skills/ , or .claude/skills/
  • Custom:               anything added via  /skills add

AFTER INSTALLING:  run  /skills reload   then   /skills list
(you should see "copilot-wrapped").  Verify with  /skills info copilot-wrapped.
Then the user can just say "give me my Copilot Wrapped" to trigger it.
════════════════════════════════════════════════════════════════════════ -->

This skill builds and opens the user's personal **Copilot Wrapped** — a polished web recap
(repository constellation graph + per-repo stats + savage roasts) generated from their own
local Copilot CLI history. Everything runs locally and offline; nothing is uploaded.

The generator lives in a git repository. Your job is to clone (or update) it and run its
one-command entry point, then tell the user the result.

## Configuration

- **REPO_URL**: `https://o365exchange.visualstudio.com/O365%20Core/_git/Explainability`  (the repo that hosts the generator)
- **REPO_BRANCH**: `users/t-shreyanr/copilot-wrap`  (the generator lives on this branch, not the default branch)
- **INSTALL_DIR**:
  - macOS/Linux: `~/.copilot/tools/copilot-wrap`
  - Windows: `%USERPROFILE%\.copilot\tools\copilot-wrap`

> This repo is internal to Microsoft (Azure DevOps, O365 Core) and requires access +
> Git credentials to clone. The generator is parked on REPO_BRANCH.

## Presentation — keep the focus on the celebration, not the plumbing

**This is a celebration, not a deployment.** The user should watch a festive terminal
moment (confetti, a "WRAPPED" banner, their stats) — NOT a wall of git/clone/build logs.
So while you carry out the steps below:

- Do **not** narrate the clone/setup or paste command output into the chat. No "Now I'll
  clone…", no progress dumps. Run the setup commands **quietly** and keep any of your own
  commentary to at most one short line like "Setting up… 🎁".
- Run git **quietly** (`git clone --quiet …`, `git -C … pull --quiet --ff-only`) and let
  the steps run without echoing their stdout back to the user.
- The visible payoff is produced by `wrap.py` itself — it prints the animated celebration
  (confetti + banner + a stats teaser) and then opens the browser. **Let that be the show.**
- After it finishes, add at most a one-line "Enjoy your Wrapped! 🎉" — don't re-summarize the
  steps you took.

## Do this (use your shell tool; pick commands for the user's OS — run quietly)

1. **Check prerequisites** (quietly). Confirm `git` is available and a Python 3 interpreter
   exists: try `python3 --version`, else `python --version`, and on Windows `py --version`.
   If no Python 3.8+ is found, tell the user to install it from https://python.org and stop.

2. **Clone or update the generator into INSTALL_DIR** (REPO_BRANCH only, shallow, quiet).
   - If INSTALL_DIR does **not** exist:
     `git clone --quiet --depth 1 --branch users/t-shreyanr/copilot-wrap REPO_URL "INSTALL_DIR"`
   - If it **does** exist:
     `git -C "INSTALL_DIR" pull --quiet --ff-only`  (if this fails, just continue with the existing copy)

3. **Run the wrap — it plays the celebration in the user's terminal and opens the browser**
   (non-blocking; builds the bundle, then prints a confetti + "WRAPPED" banner + stats teaser):
   - macOS/Linux: `python3 "INSTALL_DIR/scripts/wrap.py" --no-serve`
   - Windows: `py "INSTALL_DIR\scripts\wrap.py" --no-serve`
     (use `python` if `py` is unavailable)

   **IMPORTANT — do NOT pass `--no-anim`.** Run it plain so it animates. The celebration is
   written **directly to the user's terminal device** (`CONOUT$` / `/dev/tty`), so it shows
   up live in their terminal *even though you launched it from your shell tool and your
   tool captured stdout*. Your captured shell output will look almost empty — that's expected
   and correct; the party is happening in the user's actual terminal, not in your tool block.

   Notes:
   - Only add `--no-anim` if the user explicitly asks for no animation (prints instantly).
   - Prefer a local web server (nicer rendering)? Drop `--no-serve`; it serves on a local
     port and opens the browser, then runs until Ctrl+C — only if you can background it.

4. **Report back briefly + post a fallback banner.** As a safety net (in case the terminal
   device wasn't reachable), end your reply with a short celebratory block in the chat using
   the real numbers — read them from `INSTALL_DIR/web/wrap-data.json` (`meta.totals` +
   `finalVerdict`). Keep it to a few lines, e.g.:

   ```
   🎉  COPILOT WRAPPED  🎉
   @<user> · <N> repos · <N> sessions · <N> messages · <N> commits · <N> PRs
   🔥 <finalVerdict>
   ```
   Then one line: "Opened in your browser — scroll through and enjoy the roast. Re-run anytime."

## Options the user can ask for (pass through to wrap.py)

- `--top N` — feature at most N repositories (default 6)
- `--user NAME` — the @handle shown on the cover
- `--min-turns N` — ignore repos with fewer messages
- `--no-open` — build but don't open the browser
- `--no-anim` — skip the terminal animation (clean static celebration)
- `--verbose` — show the underlying scan/build output (hidden by default)
- `--port N` — (server mode only) the port to serve on

## Troubleshooting

- **"session-store.db not found"** → the user hasn't used the Copilot CLI on this machine yet,
  so there is no history to wrap. Let them know.
- **No browser opened** → give the user the printed file path / URL to open manually.
- **Privacy** → reassure: the tool reads only local files and the generated page contains only
  aggregate counts and roasts — no message text and no source code. Nothing leaves the machine.
