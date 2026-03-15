# Download Procedures

## Download an Episode

**Triggers:** "Download {series}", "Get the latest {series}", "Download {series} episode {N}"

```
1. Search SubsPlease for the series:
   terminal("python3 ~/.hermes/scripts/anihermes_subsplease.py latest '{series}' --quality 1080p")

2. If SubsPlease has results with a magnet link:
   - Extract the magnet link from output
   - Proceed to step 4

3. If SubsPlease doesn't have it, search Nyaa:
   terminal("python3 ~/.hermes/scripts/anihermes_nyaa.py best '{series} episode {N} 1080p'")
   - Use the magnet link from the output

4. Download via qbittorrent (ALWAYS use this script — it reads anime_path from config):
   terminal("python3 ~/.hermes/scripts/anihermes_add_torrent.py add --series '{series}' --season '{season}' --magnet '{magnet_link}'")
   NEVER add torrents manually or with execute_code. NEVER write custom scripts. NEVER hardcode paths. The script reads the save path from config.yaml automatically.

5. Confirm to user:
   - Series name, episode number
   - Save location (from script output)
   - Monitor URL from config
```

## Download All Unwatched Episodes

**Triggers:** "Download all episodes I haven't seen of {series}", "Catch me up on {series}", "Download unwatched {series}"

**IMPORTANT: Episode number mapping**
SubsPlease uses ABSOLUTE episode numbers across all seasons (e.g. Frieren S2 ep 8 = absolute ep 36).
Anilist tracks progress PER SEASON. You MUST use the `seasons` command to map between them.

```
1. Get season map (absolute → relative episode mapping):
   terminal("python3 ~/.hermes/scripts/anihermes_anilist_api.py seasons '{series}'")
   - This returns each season with: episode count, aired count, absolute range
   - Example: S1 = abs 1-28 (28 eps), S2 = abs 29-38 (10 eps, 8 aired)

2. Get user's current progress from Anilist:
   terminal("python3 ~/.hermes/scripts/anihermes_anilist_api.py watchlist")
   - Find the entry matching the series
   - Note: progress is PER-SEASON (e.g. "5" means ep 5 of that specific season)
   - Identify WHICH season the user is on from the Anilist media ID

3. Calculate which episodes to download:
   - From the season map, find the user's current season
   - User has seen: episodes 1 through {progress} of that season
   - Episodes to download: {progress + 1} through {aired_episodes} of current season
   - CRITICAL: Do NOT download episodes beyond what has AIRED
     * For FINISHED seasons: all episodes are available
     * For RELEASING seasons: only download up to {aired_episodes}, NOT total {episodes}
   - If current season is complete, also check if next season has started

4. Convert needed episodes to absolute numbers for SubsPlease:
   - absolute_ep = season_start_absolute + (relative_ep - 1)
   - Example: S2 ep 9 = 29 + (9-1) = absolute 37

5. Get all available episodes with magnet links:
   terminal("python3 ~/.hermes/scripts/anihermes_subsplease.py episodes '{series}' --quality 1080")
   - This lists ALL episodes with their magnet links printed below each one
   - Match the absolute episode numbers you need from this output
   - NEVER write custom scripts to extract magnets — the episodes command already prints them
   - If SubsPlease has no results, try Nyaa:
     terminal("python3 ~/.hermes/scripts/anihermes_nyaa.py best '{series} {absolute_ep} 1080p'")

6. For each episode with a magnet:
   terminal("python3 ~/.hermes/scripts/anihermes_add_torrent.py --series '{series}' --season 'S{N}' --magnet '{magnet}'")

7. Report summary:
   - "Downloaded X episodes of {series} S{N} (eps {from}-{to})"
   - "Y episodes not yet aired (next airing: ...)"
   - Offer to update Anilist progress
```

## Multi-Source Smart Download

**Triggers:** "Find {series} from multiple sources", "Search everywhere for {series}"

```
1. Search both sources in parallel using delegate_task:

   delegate_task("Search SubsPlease for '{series}' episode {N}:
     terminal('python3 ~/.hermes/scripts/anihermes_subsplease.py latest \"{series}\" --quality 1080')
     Return the magnet link or 'NOT_FOUND'.")

   delegate_task("Search Nyaa for '{series}' episode {N}:
     terminal('python3 ~/.hermes/scripts/anihermes_nyaa.py best \"{series} S{season}E{ep} 1080p\"')
     Return the magnet link, seeders, and size, or 'NOT_FOUND'.")

2. Collect results from both subagents

3. Pick best source:
   - Prefer SubsPlease (consistent quality, known good subs)
   - Fall back to Nyaa (more variety, check seeder count)
   - Report which source was used and why

4. Download using the selected magnet link (see Download procedure)
```

## Check Download Status

**Triggers:** "Is my download done?", "Download status", "What's downloading?"

```
1. Check download status:
   terminal("python3 ~/.hermes/scripts/anihermes_add_torrent.py status")

   To see all torrents (including seeding/paused):
   terminal("python3 ~/.hermes/scripts/anihermes_add_torrent.py status --all")

2. Report status to user with progress, speed, and ETA
```
