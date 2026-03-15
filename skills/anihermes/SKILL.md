---
name: anihermes
description: "Anything related to anime: downloads, watchlist, and more"
version: 1.0.0
author: AniHermes
license: MIT
platforms: [linux, macos]
metadata:
  hermes:
    tags: [anime, media-server, torrent, anilist, mal, myanimelist, subsplease, qbittorrent, episodes, watchlist, watching, unwatched, jujutsu, frieren, one-piece]
    related_skills: [anime-server-workflow]
---

# AniHermes - Anime Media Server

## When to Use

**ALWAYS use this skill** when the user mentions: anime, watching, watchlist, episodes, download anime, track series, Anilist, MAL, MyAnimeList, SubsPlease, Nyaa, anime library, or anime identification. Do NOT rely on memory/recall for anime questions — use the scripts and APIs below instead.

## Configuration

- **Config file:** `~/.hermes/anihermes/config.yaml`
- **Scripts directory:** `~/.hermes/scripts/`
- **Secrets:** Environment variables from `~/.hermes/.env`

### Tracker Selection

The config has a `tracker` field set to `anilist` or `mal`. **Always check which tracker is configured before running tracker commands.** Read it with:
```
terminal("python3 ~/.hermes/scripts/anihermes_config.py get tracker")
```

Then use the appropriate script:
- **Anilist:** `anihermes_anilist_api.py` — commands: search, watchlist, update, status, seasons, recommendations
- **MAL:** `anihermes_mal_api.py` — commands: search, watchlist, update, status, seasons, recommendations

Both scripts have the **same CLI interface** — same subcommands and arguments. The only differences:
- MAL status values are lowercase: `watching`, `completed`, `dropped`, `on_hold`, `plan_to_watch`
- Anilist status values are uppercase: `CURRENT`, `COMPLETED`, `DROPPED`, `PAUSED`, `PLANNING`

---

## Procedure Index

Load the reference file for the procedure you need:

| Request | Reference | Procedure |
|---------|-----------|-----------|
| Download an episode | `references/downloads.md` | Download an Episode |
| Download all unwatched | `references/downloads.md` | Download All Unwatched Episodes |
| Search multiple sources | `references/downloads.md` | Multi-Source Smart Download |
| Check download progress | `references/downloads.md` | Check Download Status |
| Track a series weekly | `references/tracking.md` | Track a Series |
| Stop tracking / drop | `references/tracking.md` | Drop a Series |
| Daily release digest | `references/tracking.md` | Daily Schedule Digest |
| Sync watchlist | `references/tracker.md` | Sync Watchlist |
| What should I watch next? | `references/tracker.md` | Smart Recommendation Engine |
| What's good this season? | `references/tracker.md` | Anime Season Preview |
| Map episode numbers | `references/tracker.md` | Season Mapping |
| Show my anime stats | (in SKILL.md) | Stats Card |
| Compare with friend | (in SKILL.md) | Friend Sync |
| Free up disk space | (in SKILL.md) | Storage Monitor & Auto-Cleanup |
| Start/stop media server | (in SKILL.md) | LAN Media Server |

**To load a procedure:** `skill_view("anihermes", "references/downloads.md")`

---

## Quick Procedures

These are small enough to live here directly.

### Library Management

**Triggers:** "What do I have?", "Show my library", "How much space left?"

```
1. List library:
   terminal("python3 ~/.hermes/scripts/anihermes_library_manager.py list")

2. For detailed info:
   terminal("python3 ~/.hermes/scripts/anihermes_library_manager.py info '{series}'")

3. For stats/space:
   terminal("python3 ~/.hermes/scripts/anihermes_library_manager.py stats")
```

### Conversational Watch Progress

**Triggers:** "I just finished {series}", "I watched episode {N} of {series}", "I'm on episode {N}", "Just watched {series}", "Finished {series}"

This is the "talk to your server like a person" experience. Infer intent from natural language.

```
1. Determine tracker and SCRIPT (check config tracker field)

2. Parse the user's message:
   - "I just finished Frieren" → user completed the latest aired episode
   - "I watched episode 5 of Frieren" → update progress to ep 5
   - "I finished Frieren" (no episode) → could mean finished the series
   - "I'm on episode 5" (no series) → use memory/context to infer which series

3. If series is ambiguous, check memory for recently discussed series.
   If still unclear, ask.

4. Get current state:
   terminal("python3 ~/.hermes/scripts/{SCRIPT} watchlist")
   - Find the matching entry, note current progress

5. Update tracker:
   - If specific episode: terminal("python3 ~/.hermes/scripts/{SCRIPT} update {media_id} {episode}")
   - If "finished" with no episode: get season info to find latest aired episode
     terminal("python3 ~/.hermes/scripts/{SCRIPT} seasons '{series}'")
     Then update to the last aired episode

6. Check if this was a season finale:
   - If progress == total episodes and status is FINISHED:
     - terminal("python3 ~/.hermes/scripts/{SCRIPT} status {media_id} COMPLETED/completed")
     - Check for next season: terminal("python3 ~/.hermes/scripts/{SCRIPT} seasons '{series}'")
     - If next season exists: "Nice! Season {N+1} is available — want me to start tracking it?"
     - If not: terminal("python3 ~/.hermes/scripts/{SCRIPT} recommendations {media_id}")
       "You finished {series}! Here are some similar shows you might like:"

7. Save to memory: "User finished {series} on {date}" (for future context)
```

### Stats Card

**Triggers:** "Show my anime stats", "My anime profile", "How much anime have I watched?"

```
1. Determine tracker and SCRIPT (check config tracker field)

2. Gather data in parallel using delegate_task:

   delegate_task("Get completed anime stats:
     terminal('python3 ~/.hermes/scripts/{SCRIPT} completed')
     Count total series, extract top genres, highest rated shows, calculate total episodes watched.")

   delegate_task("Get library stats:
     terminal('python3 ~/.hermes/scripts/anihermes_library_manager.py stats')
     terminal('python3 ~/.hermes/scripts/anihermes_library_manager.py list')
     Return disk usage, series count, total episodes on disk.")

   delegate_task("Get currently watching:
     terminal('python3 ~/.hermes/scripts/{SCRIPT} watchlist')
     Count active series and total progress.")

3. Calculate derived stats:
   - Total episodes watched (from tracker completed + current progress)
   - Estimated hours watched (episodes × ~24 min)
   - Most-watched genre
   - Average rating given
   - Library vs tracker completion %

4. Present as formatted card:
   "## Your Anime Stats"
   "Completed: {N} series ({hours}h watched)"
   "Currently watching: {N} series"
   "Library: {size} across {N} series"
   "Top genres: {genre1}, {genre2}, {genre3}"
   "Highest rated: {show} ({score}/10)"
   "Disk: {free} free / {total}"
```

### Friend Sync

**Triggers:** "What is {friend} watching?", "Compare my list with {friend}", "What is {friend} watching that I'm not?"

```
1. Determine tracker and SCRIPT (check config tracker field)

2. Fetch both lists using delegate_task in parallel:

   delegate_task("Get my watchlist:
     terminal('python3 ~/.hermes/scripts/{SCRIPT} watchlist')
     Return list of series titles and IDs.")

   delegate_task("Get {friend}'s watchlist:
     terminal('python3 ~/.hermes/scripts/{SCRIPT} watchlist {friend_username}')
     Return list of series titles and IDs.")

3. Compute differences:
   - friend_only: series friend is watching that user is NOT
   - user_only: series user is watching that friend is NOT
   - shared: series both are watching (with progress comparison)

4. Present results:
   "## Comparing with {friend}"

   "### {friend} is watching (you're not):"
   - List with scores and episode count — these are discovery opportunities

   "### You're both watching:"
   - List with both users' progress — fun to see who's ahead

   "### Only you're watching:"
   - List for context

5. Offer: "Want me to start tracking any of {friend}'s shows?"
```

### Storage Monitor & Auto-Cleanup

**Triggers:** "I'm running low on space", "Clean up my library", "Free up disk space", "Storage check"

**SAFETY: This procedure can DELETE files. ALWAYS show what will be deleted and get EXPLICIT user confirmation before any deletion. NEVER auto-delete without asking.**

```
1. Check current disk status:
   terminal("python3 ~/.hermes/scripts/anihermes_library_manager.py stats")
   - Note free space and usage percentage

2. Get cleanup suggestions (sorted by size, largest first):
   terminal("python3 ~/.hermes/scripts/anihermes_library_manager.py cleanup-suggestions")

3. Cross-reference with tracker to identify safe-to-delete candidates:
   - Determine tracker and SCRIPT
   - terminal("python3 ~/.hermes/scripts/{SCRIPT} watchlist")
   - Categorize each series:
     a. COMPLETED on tracker + all episodes downloaded → safest to delete
     b. DROPPED on tracker → safe to delete
     c. NOT on tracker at all → likely old/forgotten, ask user
     d. Currently WATCHING → DO NOT suggest deletion

4. Present tiered suggestions:
   "## Storage Cleanup"
   "Disk: {used}% used, {free} remaining"
   ""
   "### Safe to delete (completed/dropped):"
   - List with size, noting tracker status
   ""
   "### Ask first (not on tracker):"
   - List with size
   ""
   "### Not suggested (currently watching):"
   - List with size (for context only)

5. WAIT for user to explicitly name which series to delete.
   Do NOT proceed without explicit confirmation like "yes delete X" or "delete all completed".

6. For each confirmed deletion:
   - ALWAYS do a dry run first:
     terminal("python3 ~/.hermes/scripts/anihermes_library_manager.py cleanup '{series}'")
     Show the user: name, episode count, size, path
   - Ask ONE MORE TIME: "Delete {series} ({size})? This cannot be undone."
   - Only if confirmed:
     terminal("python3 ~/.hermes/scripts/anihermes_library_manager.py cleanup '{series}' --confirm")

7. After deletions:
   - Show new disk status: terminal("python3 ~/.hermes/scripts/anihermes_library_manager.py stats")
   - Summarize what was freed: "Freed {total_size} by removing {N} series"
```

### LAN Media Server

**Start triggers:** "Start the media server", "Start streaming", "Serve my library", "Stream anime on LAN", "Launch the server"

**Stop triggers:** "Stop the media server", "Turn off the server", "Shut down streaming", "Kill the server", "Stop streaming", "Close the server", "Take down the server", "Stop the server"

**Status triggers:** "Server status", "Is the server running?", "Media server status", "Check server", "Is streaming on?"

| Action | Command |
|--------|---------|
| Start | `terminal("python3 ~/.hermes/scripts/anihermes_media_server.py start")` |
| Stop | `terminal("python3 ~/.hermes/scripts/anihermes_media_server.py stop")` |
| Status | `terminal("python3 ~/.hermes/scripts/anihermes_media_server.py status")` |
| Custom port | `terminal("python3 ~/.hermes/scripts/anihermes_media_server.py start --port 9000")` |

The server provides a styled web UI at `http://LAN_IP:8888/` where any device on the WiFi can browse and stream episodes. Supports video seeking (HTTP Range), concurrent streams, and works with phones, laptops, and smart TVs.

### Anime Scene Identification

**Triggers:** User sends an image, "What anime is this?", "Identify this anime"

```
1. Analyze the image:
   vision_analyze(image, prompt="Identify this anime. Describe the characters, art style, and any recognizable elements.")

2. If identified with confidence:
   - Verify: web_search("{identified_anime} anime")
   - Search tracker: terminal("python3 ~/.hermes/scripts/anihermes_{tracker}_api.py search '{identified_anime}'")

3. If uncertain:
   - web_search("anime identification {description_from_vision}")

4. Present results and offer to download or track.
```

---

## Pitfalls

1. **qbittorrent not running** — Scripts fail if WebUI is down. Start it first.
2. **Storage path doesn't exist** — Verify anime_path in config before downloading.
3. **Tracker rate limiting** — Anilist: ~90 req/min. MAL: ~1000 req/day. Don't spam.
4. **SubsPlease API changes** — If search fails, fall back to web_extract on the site.
5. **Absolute vs relative episodes** — SubsPlease uses absolute numbering. Always use `seasons` command to map. See `references/tracker.md`.
6. **CRON job duplication** — Always check existing jobs before creating new ones.
7. **Check tracker before commands** — Always read config `tracker` field first. Don't assume Anilist.
8. **Storage cleanup is DESTRUCTIVE** — NEVER delete files without showing exactly what will be deleted and getting explicit user confirmation. Always dry-run first. Double-confirm before actual deletion.
9. **NEVER hardcode paths or URLs** — Always use `add_torrent.py` for downloads (it reads `anime_path` from config). Never use `execute_code` to add torrents directly. Never hardcode `http://localhost:8081` — read from config instead.
10. **Aired vs total episodes** — The watchlist output distinguishes between aired and total episodes. If a show says "(aired: 10/12, next ep 11 not yet released)" or "(still airing)", only count aired episodes as unwatched, NOT future unreleased ones. Example: progress 8/12, aired 10 → user has 2 unwatched (ep 9-10), NOT 4.

---

## Related Tools

- `web_search` / `web_extract` — Find anime info, scrape when API fails
- `delegate_task` — Parallel multi-source searches
- `vision_analyze` — Anime scene identification from images
- `schedule_cronjob` / `list_cronjobs` / `remove_cronjob` — Series tracking
- `send_message` — Cross-platform notifications
- `memory` — Remember user preferences
