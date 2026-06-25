# Copilot Wrapped (pro) 🔥

A clean, modern **"Copilot Wrapped"** — a Spotify-Wrapped–style recap of your year
with the GitHub Copilot CLI that also **roasts you at every repo**.

No fantasy theming, no 3D castles — just real repo names, real numbers, and real
(data-driven) burns. Built as a polished, scroll-snapping web experience.

> This is the professional companion to the cinematic 3D version in `../copilot-wrap/`.
> Both are kept side-by-side; this one is the "just the facts (and the roast)" cut.

---

## What it shows

A vertical, scroll-snap deck of full-screen panels:

1. **Cover** — big "Copilot Wrapped" title, date range, and headline stat chips.
2. **Overview** — animated count-up of your totals (repos, sessions, messages, files, commits, PRs).
3. **Repository graph** — a "constellation" of your repos as **adaptive cards** orbiting a
   central **YOU** hub, with activity-weighted edges. Click a repo card to dive in (see below).
4. **Per-repo panels** (one per repo) — stats grid, language bars, "what you actually did"
   deeds, and a **🔥 THE ROAST** card with savage, data-driven one-liners.
5. **Superlatives** — "the awards nobody asked for" (Most Needy, Biggest Cowboy, The Ghost, …).
6. **Final verdict** — one closing burn, plus a **Copy the roast** button.

Each repo carries its own accent gradient that re-themes the whole page as you scroll.

### Repository graph — two interaction modes

The graph (panel 3) renders each repo as an **adaptive card** node connected to a central
**YOU** hub; edge thickness scales with how much you talked to Copilot in that repo. A toggle
("On click") lets you choose what a card-click does — **both are wired so you can compare and
finalise on one**:

- **Scroll to page** — smoothly scrolls/snaps to that repo's full detail panel.
- **Enlarge card** — opens an in-place modal lightbox with the repo's full detail
  (stats, language bars, deeds, roast) without leaving the graph. Close with `✕`, `Esc`,
  or by clicking the backdrop.

The chosen mode is remembered (localStorage). On mobile the graph gracefully degrades to a
stacked list of the same cards.

### The data (from your local session history)
Pulled from the Copilot CLI session store — sessions, turns (messages), files touched,
active days, languages, and git signal (commits / pushes / PRs derived from tool calls).
The repo ships a **synthetic sample** (below) so the demo shows something without your data;
running `wrap.py` replaces it with your own.

| Repo (sample) | Sessions | Messages | Files | Commits | PRs |
|------|---------:|---------:|------:|--------:|----:|
| acme-web         | 38 | 742 | 156 | 64 | 3 |
| payments-api     | 19 | 333 |  88 | 41 | 6 |
| infra-terraform  |  9 | 121 |  47 | 18 | 1 |
| weekend-bot      |  4 |  36 |  22 |  0 | 0 |
| **Totals**       | **70** | **1,232** | **313** | **123** | **10** |

---

## How the roast works

`scripts/build.py` is the roast engine. It:

1. Maps each repo to a clean display name + accent gradient.
2. Derives extra metrics (messages/session, push:PR ratio, doc ratio, top language, …).
3. Generates **roasts** by blending two sources:
   - `CURATED` — hand-written savage lines for the known repos.
   - `rule_roasts()` — threshold-based burns that generalise to **any** data
     (heavy committers, doc-hoarders, ghosts who touch files but never commit, etc.).
4. Builds repo-wide **superlatives** and a final **verdict**.
5. Writes `web/wrap-data.js` (`window.WRAP_DATA`) and `data/wrap-data.json`.

Because the rule-based layer is data-driven, the wrap still produces sensible roasts
for users with many commits / PRs / repos — not just this dataset.

---

## Run it

**One command — generate from *your* history and open it:**

```bash
python scripts/wrap.py
```

That runs the whole pipeline **quietly** (the scan/build noise is hidden) and instead
plays a **festive terminal celebration** — confetti rain, a gradient "WRAPPED" banner, and
a quick stats teaser — then opens the full web experience in your browser.
(Windows: `bin\copilot-wrap.cmd`; macOS/Linux: `bin/copilot-wrap`.)

```
  🎉  ✦ ✧ ✦   C O P I L O T   ✦ ✧ ✦

  █   █ ███▙ ▟██▙ ███▙ ███▙ ████ ███▙        ✦      ❄
  █   █ █  █ █  █ █  █ █  █ █    █  █     confetti rains here
  █ █ █ ███▛ ████ ███▛ ███▛ ███  █  █        ✧   *    ·
  ██▄██ █ █  █  █ █    █    █    █  █
  █   █ █  █ █  █ █    █    ████ ███▛

  @octocat   ·   01 Jan — 31 Dec, 2025
  4 repos   70 sessions   1,232 messages   313 files   123 commits   10 PRs
  🔥 You don't ship software. You confide in it.
```

Useful flags: `--port N` · `--top N` (max repos, default 6) · `--user NAME` ·
`--min-turns N` · `--no-open` · `--no-serve` (just regenerate the bundle) ·
`--no-anim` (static, non-animated celebration) · `--verbose` (show scan/build output).

<details>
<summary>Manual / step-by-step (or to serve the bundled demo)</summary>

```bash
python scripts/extract.py     # read ~/.copilot -> data/wrap-data.json
python scripts/build.py       # roast + write web/wrap-data.js
cd web && python -m http.server 8754
# open http://localhost:8754/index.html
```
</details>

Navigate with the mouse wheel / trackpad, the on-screen dots, or the keyboard
(`↑` / `↓` / `Space`, `Home`, `End`).

> Pure static HTML/CSS/JS — no build step, no JS dependencies, no network calls.
> The web bundle works offline straight from `file://` too. Only Python 3 (stdlib) is
> needed to *generate* it.

---

## Ship it — let anyone run their own `/wrap`

The whole point: **anyone with the Copilot CLI can generate their own Wrapped from
their own machine.** Here's how it's wired and how to distribute it.

### 1. Where the data comes from (100% local, private)

Every Copilot CLI user already has, on their own machine:

| Source | Gives us |
|--------|----------|
| `~/.copilot/session-store.db` (SQLite) | `sessions` (repo / cwd / branch) + `turns` (messages) |
| `~/.copilot/session-state/<id>/events.jsonl` | every tool call → file edits (→ files & languages) and git signal (`git commit` / `git push` / `gh pr create`) |

`scripts/extract.py` reads **only these local files** (read-only), groups sessions by
repository (falling back to the working-folder name when a session has no git repo),
reconstructs per-repo metrics, and writes `data/wrap-data.json`. No cloud, no API, no
account access — your history never leaves the machine.

```
extract.py  (read ~/.copilot)  →  data/wrap-data.json
build.py    (roast + theme)    →  web/wrap-data.js  +  web/index.html
wrap.py     = extract → build → celebrate → serve/open   ← the one-command entry point
```

`build.py` already generalises to **any** user: unknown repos get auto display-names,
rotating accent gradients, and rule-based roasts, so the experience is good whether you
have 1 repo or 20.

### 2. The `/wrap` entry point — ship it as a Copilot CLI **skill** (recommended)

The Copilot CLI's slash-commands are **built-in** (no user-defined `/wrap`), but it *does*
load custom **skills**. The cleanest "the CLI does the heavy lifting" distribution is a
single Markdown file — `skill/copilot-wrapped/SKILL.md` — that tells the agent where to
clone this generator and how to launch it. The user installs one file; the CLI then clones,
sets up, and runs everything on request.

**How it works:** the skill's `SKILL.md` has frontmatter (`name`, `description`,
`user-invocable: true`) plus step-by-step instructions. When the user asks for their
"Copilot Wrapped", the agent reads the skill and:
1. checks `git` + Python 3 are present,
2. **quietly** `git clone --quiet` (or `git pull --quiet`) this repo into `~/.copilot/tools/copilot-wrap`,
3. runs `python scripts/wrap.py --no-serve`, which plays a **festive terminal celebration**
   (confetti + "WRAPPED" banner + stats teaser) and opens the bundle — non-blocking,
4. drops one celebratory line.

The skill tells the agent **not** to narrate the clone/setup or dump logs — the terminal
celebration is meant to be the show, like a CLI app's splash, not a deployment trace.

**Distributing it (two steps):**

1. **Host the generator.** This `copilot-wrap-pro/` folder is parked on the branch
   `users/t-shreyanr/copilot-wrap` in the internal Azure DevOps repo
   `o365exchange/O365 Core/_git/Explainability` — the URL + branch set in `SKILL.md`.
   (Internal/Microsoft-only; requires repo access + Git credentials.)
2. **The user installs the skill** (one file) — Copilot loads skills from these dirs:
   - Personal (all repos): `~/.copilot/skills/` or `~/.agents/skills/`
   - Project: `.github/skills/`, `.agents/skills/`, or `.claude/skills/`

   ADO has no anonymous raw URL, so clone the branch (shallow) and copy the skill file:
   ```bash
   git clone --depth 1 --branch users/t-shreyanr/copilot-wrap \
     "https://o365exchange.visualstudio.com/O365%20Core/_git/Explainability" \
     ~/.copilot/tools/copilot-wrap
   mkdir -p ~/.copilot/skills/copilot-wrapped
   cp ~/.copilot/tools/copilot-wrap/skill/copilot-wrapped/SKILL.md \
      ~/.copilot/skills/copilot-wrapped/SKILL.md
   ```
   ```powershell
   # PowerShell
   git clone --depth 1 --branch users/t-shreyanr/copilot-wrap `
     "https://o365exchange.visualstudio.com/O365%20Core/_git/Explainability" `
     "$env:USERPROFILE\.copilot\tools\copilot-wrap"
   New-Item -ItemType Directory -Force "$env:USERPROFILE\.copilot\skills\copilot-wrapped" | Out-Null
   Copy-Item "$env:USERPROFILE\.copilot\tools\copilot-wrap\skill\copilot-wrapped\SKILL.md" `
     "$env:USERPROFILE\.copilot\skills\copilot-wrapped\SKILL.md"
   ```

   Then in the CLI: `/skills reload` → `/skills list` (you should see `copilot-wrapped`).

**Using it:** in any Copilot CLI session the user just asks — *"give me my Copilot Wrapped"*
/ *"roast my Copilot usage"* — and the agent clones + runs it. (Manage with
`/skills list | info copilot-wrapped | reload`.)

#### Other entry points (if you don't want a skill)

- **Shell alias / function** — `wrap() { python3 /path/to/copilot-wrap-pro/scripts/wrap.py "$@"; }`
  (PowerShell: `function wrap { & "C:\path\to\copilot-wrap-pro\bin\copilot-wrap.cmd" $args }`).
- **Standalone CLI on PATH** — drop `bin/copilot-wrap` on `PATH`; later packageable as
  `pipx install copilot-wrap` / `npx copilot-wrap`.
- **MCP tool** — expose a `wrap` tool via an MCP server (`/mcp`), callable from within Copilot.

> A genuine literal built-in `/wrap` would need first-party support; the skill gives the
> closest "ask the CLI and it just does it" experience today.

### 3. Privacy

Everything runs locally and offline. The generated `web/` bundle contains only your
aggregate counts + the roasts — no message contents, no file contents, no code. Safe to
screenshot or share; nothing is uploaded.

---

## Layout

```
copilot-wrap-pro/
  scripts/extract.py      # read ~/.copilot local history -> data/wrap-data.json
  scripts/build.py        # roast engine + theming -> web feed (--src / --web-dir)
  scripts/celebrate.py    # festive terminal celebration (confetti + banner + teaser)
  scripts/wrap.py         # one-command: extract -> build -> celebrate -> serve/open
  bin/copilot-wrap(.cmd)  # cross-platform launchers (for a `wrap` alias / PATH)
  skill/copilot-wrapped/SKILL.md   # drop-in Copilot CLI skill (clones + runs this)
  data/wrap-data.json     # generated data feed (a curated demo ships by default)
  web/index.html          # the Copilot Wrapped experience (scroll-snap deck + graph)
  web/wrap-data.js        # generated: window.WRAP_DATA
  README.md
```

> `data/wrap-data.json` and the `web/wrap-data.*` feed are **generated**; running
> `wrap.py` / `extract.py` overwrites them with your own data. A curated 4-repo demo
> is what ships in the box.

## Customising the roasts

- Tune the savage lines in `CURATED` / `VERDICT` (per repo id) in `scripts/build.py`.
- Adjust the generic burns in `rule_roasts()` (thresholds + phrasing).
- Change accent gradients in `ACCENTS`, display names in `DISPLAY`.
- Re-run `python scripts/build.py` (or `wrap.py`) to regenerate the feed.
