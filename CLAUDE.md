# AniHermes

Hackathon entry for Hermes Agent. Natural language anime media server controlled via Telegram/CLI/Discord.

## What This Is

A Hermes Agent skill + supporting Python scripts that let users manage their anime library through conversation. Download episodes, track series, sync with Anilist/MAL, identify anime from screenshots, get recommendations, compare with friends.

## Architecture

```
User (Telegram/CLI) → Hermes Agent → SKILL.md procedures → scripts/*.py → qbittorrent / Anilist / MAL / SubsPlease / Nyaa
```

Hermes reads the skill from `~/.hermes/skills/media/anime-media-server/SKILL.md`, which references procedures in `references/*.md`. The skill tells Hermes which scripts to call via `terminal()`. Scripts read config from `~/.hermes/anihermes/config.yaml` and secrets from env vars in `~/.hermes/.env`.

## Project Structure

```
anihermes/
├── CLAUDE.md                 # This file
├── README.md                 # User-facing docs
├── LICENSE                   # MIT
├── install.sh                # Interactive installer — copies to ~/.hermes/
├── config.example.yaml       # Config template
├── requirements.txt          # No deps needed (stdlib only)
├── scripts/
│   ├── config.py             # Config loader (YAML parser + env secret injection)
│   ├── add_torrent.py        # Adds magnets to qbittorrent via WebUI API
│   ├── anilist_api.py        # Anilist GraphQL client (search, watchlist, update, seasons, completed, seasonal)
│   ├── mal_api.py            # MyAnimeList API v2 client (same CLI interface as anilist_api.py)
│   ├── subsplease.py         # SubsPlease API client (search, latest, episodes, schedule)
│   ├── nyaa.py               # Nyaa.si RSS search (search, best — returns magnets)
│   └── library_manager.py    # Local library scanner (list, info, stats, cleanup, cleanup-suggestions)
├── skills/
│   └── anime-media-server/
│       ├── SKILL.md           # Main skill — when-to-use, config, procedure index, quick procedures
│       └── references/
│           ├── downloads.md   # Download, batch download, multi-source, download status
│           ├── tracking.md    # Track series CRON, drop series, daily digest
│           └── tracker.md     # Anilist/MAL sync, recommendations, season preview, season mapping
└── docs/
    ├── SETUP.md              # Detailed setup guide
    ├── TELEGRAM.md           # Telegram bot setup
    └── ANILIST.md            # Anilist OAuth setup
```

## Key Design Decisions

- **All scripts use Python stdlib only** — no pip dependencies. Uses urllib, json, xml.etree.
- **Config-driven** — no hardcoded paths. Everything reads from `~/.hermes/anihermes/config.yaml`.
- **Secrets in env vars** — qbittorrent creds, OAuth tokens are in `~/.hermes/.env`, never in config files.
- **Tracker-agnostic** — `config.yaml` has a `tracker` field (`anilist` or `mal`). Both API scripts have identical CLI interfaces so the skill just swaps the script name.
- **install.sh copies files** — scripts go to `~/.hermes/scripts/anihermes_*.py`, skill goes to `~/.hermes/skills/media/anime-media-server/`. The `config.py` is installed without prefix so other scripts can `from config import load_config`.
- **Skill uses progressive disclosure** — SKILL.md is kept lean (~160 lines) with a procedure index. Full procedures live in `references/` and are loaded on demand via `skill_view()`.
- **Storage cleanup is triple-guarded** — dry run first, show what will be deleted, explicit confirmation required. Never auto-delete.

## How Scripts Relate

- `subsplease.py` and `nyaa.py` find torrents (magnets)
- `add_torrent.py` sends magnets to qbittorrent
- `anilist_api.py` and `mal_api.py` handle tracker reads/writes
- `library_manager.py` scans the local anime directory
- `config.py` is imported by all other scripts

## Script CLI Patterns

All scripts use argparse with subcommands. Examples:
```bash
python3 subsplease.py search "Frieren"
python3 subsplease.py latest "Frieren" --quality 1080
python3 nyaa.py best "Frieren S02E08 1080p"
python3 anilist_api.py search "Frieren"
python3 anilist_api.py watchlist
python3 anilist_api.py seasons "Frieren"
python3 anilist_api.py completed RodmarKun
python3 anilist_api.py seasonal 2026 WINTER
python3 mal_api.py search "Frieren"          # Same interface as anilist_api.py
python3 library_manager.py list
python3 library_manager.py cleanup-suggestions
python3 add_torrent.py --series "Frieren" --season "S2" --magnet "magnet:..."
```

## Hermes Tool Usage in Skill

The skill procedures use these Hermes tools:
- `terminal()` — runs scripts
- `delegate_task()` — parallel subagent work (multi-source search, recommendation engine)
- `vision_analyze()` — anime screenshot identification
- `schedule_cronjob()` / `list_cronjobs()` / `remove_cronjob()` — series tracking automation
- `send_message()` — Telegram/Discord notifications
- `memory()` — taste profiles, watch history across sessions
- `execute_code()` — inline computation (date math, episode mapping)

## Testing

```bash
# Test SubsPlease
python3 scripts/subsplease.py search "Frieren"
python3 scripts/subsplease.py schedule

# Test Nyaa
python3 scripts/nyaa.py best "Frieren 1080p"

# Test Anilist
python3 scripts/anilist_api.py search "Frieren"
python3 scripts/anilist_api.py seasons "Frieren"
python3 scripts/anilist_api.py seasonal 2026 WINTER

# Test Library
python3 scripts/library_manager.py stats

# Install and test via Hermes
./install.sh
hermes "What anime is airing this season?"
hermes "Download the latest Frieren"
```

## Common Tasks

**Adding a new script:** Create in `scripts/`, add to the `for` loop in `install.sh`, add procedures to the appropriate `references/*.md` file.

**Adding a new procedure:** If small, add to SKILL.md quick procedures. If large, add to the appropriate `references/*.md`. Update the procedure index table in SKILL.md.

**Changing config structure:** Update `config.example.yaml`, `config.py` (loader + defaults), and `install.sh` (prompts + generation).

**Supporting a new tracker:** Mirror the interface of `anilist_api.py` — same subcommands and arg names. Add to `install.sh` tracker choice. The skill already uses `{SCRIPT}` variable pattern.
