# Tracker Procedures (Anilist / MAL)

**IMPORTANT:** Before running any tracker command, determine which tracker is configured:
```
terminal("python3 -c \"from config import load_config; c=load_config(); print(c.get('tracker','anilist'))\"")
```

Then use the corresponding script:
- `anilist` → `anihermes_anilist_api.py`
- `mal` → `anihermes_mal_api.py`

Both scripts have identical CLI interfaces (same subcommands and arguments).

## Sync Watchlist

**Triggers:** "Sync my Anilist", "Sync my MAL", "Import my watchlist", "What am I watching?"

```
1. Determine tracker:
   terminal("python3 -c \"from config import load_config; c=load_config(); print(c.get('tracker','anilist'))\"")
   - If "anilist": SCRIPT=anihermes_anilist_api.py
   - If "mal": SCRIPT=anihermes_mal_api.py

2. Get watchlist:
   terminal("python3 ~/.hermes/scripts/{SCRIPT} watchlist")

3. Get current CRON jobs:
   list_cronjobs(include_disabled=false)
   - Filter for "AniHermes:" prefix

4. Compare:
   - For each "Watching"/"CURRENT" entry NOT tracked by CRON:
     - Offer to create CRON job
   - For each CRON job with no matching tracker entry:
     - Flag as "tracked locally but not on tracker"

5. If user confirms, create missing CRON jobs (use Track procedure in references/tracking.md)

6. Report summary:
   - Already synced: X series
   - Newly tracked: Y series
   - Only local: Z series
```

## Smart Recommendation Engine

**Triggers:** "What should I watch next?", "Recommend anime like {series}", "Recommend something", "What's good?"

This showcases Hermes's `delegate_task` for parallel analysis and `memory` for taste learning.

```
1. Determine tracker and SCRIPT (see top of this file)

2. If recommending based on a SPECIFIC series:
   - Get ID: terminal("python3 ~/.hermes/scripts/{SCRIPT} search '{series}'")
   - Get recommendations: terminal("python3 ~/.hermes/scripts/{SCRIPT} recommendations {media_id}")
   - Skip to step 6

3. If GENERAL recommendation ("what should I watch next?"):
   Use delegate_task to gather data in parallel:

   delegate_task("Get the user's taste profile:
     terminal('python3 ~/.hermes/scripts/{SCRIPT} completed')
     Analyze: top genres, highest-rated shows, average score. Return a summary of their taste.")

   delegate_task("Get current seasonal anime:
     terminal('python3 ~/.hermes/scripts/{SCRIPT} seasonal {current_year} {current_season}')
     Return the full list with scores and genres.")

   delegate_task("Get the user's current watchlist and library:
     terminal('python3 ~/.hermes/scripts/{SCRIPT} watchlist')
     terminal('python3 ~/.hermes/scripts/anihermes_library_manager.py list')
     Return all titles the user is already watching or has downloaded.")

4. Cross-reference:
   - Filter seasonal anime to only shows matching user's top genres
   - Exclude anything already on watchlist or in library
   - Sort by: genre match strength + community score
   - Also get recommendations from user's top 3 highest-rated completed shows:
     terminal("python3 ~/.hermes/scripts/{SCRIPT} recommendations {top_rated_id}")

5. Save taste profile to memory for future sessions:
   memory("User's anime taste profile: top genres are {genres}, average score {avg}, prefers {patterns}")

6. Present results:
   - "Based on your taste (you love {genres} and rated {top_show} highest):"
   - Top 5 picks with: title, score, genre overlap, why it matches
   - "Currently airing picks:" (from seasonal)
   - "Similar to your favorites:" (from recommendations)

7. Offer: "Want me to track any of these?" or "Want me to download episode 1?"
```

## Anime Season Preview

**Triggers:** "What's good this season?", "What's airing?", "Season preview", "What anime is new?"

```
1. Determine tracker and SCRIPT (see top of this file)

2. Determine current season:
   - Use execute_code to get current month → map to season:
     Jan-Mar = WINTER/winter, Apr-Jun = SPRING/spring, Jul-Sep = SUMMER/summer, Oct-Dec = FALL/fall

3. Fetch seasonal anime:
   terminal("python3 ~/.hermes/scripts/{SCRIPT} seasonal {year} {season}")

4. Fetch user's taste profile (for personalized ranking):
   terminal("python3 ~/.hermes/scripts/{SCRIPT} completed")
   - Extract top genres and average scores

5. Fetch user's current watchlist (to mark what they're already watching):
   terminal("python3 ~/.hermes/scripts/{SCRIPT} watchlist")

6. Cross-reference SubsPlease schedule for availability:
   terminal("python3 ~/.hermes/scripts/anihermes_subsplease.py schedule")

7. Present organized preview:
   "## {SEASON} {YEAR} Anime Preview"

   "### Already Watching:"
   - List seasonal shows the user is tracking, with progress

   "### Recommended For You:" (matches user's genres)
   - Top picks sorted by genre match + score
   - Mark which are on SubsPlease (easy download)

   "### Popular This Season:" (everything else worth noting)
   - High-scoring shows outside user's usual genres
   - "Expand your horizons" picks

8. Offer: "Want me to track any of these?" / "Download episode 1 of {show}?"
```

## Season Mapping (Absolute ↔ Relative Episodes)

**When to use:** Any time you need to convert between SubsPlease absolute episode numbers and tracker per-season numbers.

```
1. Determine tracker (see step 1 above)

2. Get season map:
   terminal("python3 ~/.hermes/scripts/{SCRIPT} seasons '{series}'")

Output example:
  S1: Frieren: Beyond Journey's End [154587]
    Episodes: 28, Status: FINISHED
    Absolute range: 1-28
  S2: Frieren: Beyond Journey's End Season 2 [182255]
    Episodes: 10, Status: RELEASING (8 aired)
    Absolute range: 29-38

To convert:
  absolute_ep = season_start_absolute + (relative_ep - 1)
  relative_ep = absolute_ep - season_start_absolute + 1

IMPORTANT: For RELEASING/currently_airing seasons, "aired" count may be less than total episodes.
Only episodes up to the aired count are available for download.
```
