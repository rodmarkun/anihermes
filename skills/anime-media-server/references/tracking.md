# Tracking & CRON Procedures

## Track a Series (CRON Job)

**Triggers:** "Track {series}", "Follow {series} weekly", "Auto-download {series}"

```
1. Check if already tracked:
   list_cronjobs(include_disabled=false)
   - Filter for jobs with "AniHermes:" prefix
   - If series already tracked: inform user, skip

2. Get series info:
   terminal("python3 ~/.hermes/scripts/anihermes_subsplease.py search '{series}'")

3. Create weekly CRON job:
   schedule_cronjob(
     prompt="AniHermes auto-download check for {series}:
       1. Run: terminal('python3 ~/.hermes/scripts/anihermes_subsplease.py latest \"{series}\" --quality 1080p')
       2. Check what episodes exist: terminal('python3 ~/.hermes/scripts/anihermes_library_manager.py info \"{series}\"')
       3. If new episode available that's not in library:
          - Download it: terminal('python3 ~/.hermes/scripts/anihermes_add_torrent.py --series \"{series}\" --season \"{season}\" --magnet \"{magnet}\"')
          - Update Anilist progress if configured: terminal('python3 ~/.hermes/scripts/anihermes_{TRACKER}_api.py update {media_id} {new_episode}')
          - Report: 'Downloaded {series} episode {N}'
       4. If no new episode and 3+ weeks since last release:
          - Series likely ended
          - Remove this CRON job
          - Update tracker status to COMPLETED/completed
          - Report: '{series} appears to have ended. CRON removed.'
       5. If up to date: Report '{series} is up to date'",
     schedule="every 1d",
     name="AniHermes: {series}"
   )

4. Update tracker (if configured):
   - Determine tracker: terminal("python3 -c \"from config import load_config; c=load_config(); print(c.get('tracker','anilist'))\"")
   - Anilist: terminal("python3 ~/.hermes/scripts/anihermes_anilist_api.py status {media_id} CURRENT")
   - MAL: terminal("python3 ~/.hermes/scripts/anihermes_mal_api.py status {anime_id} watching")

5. Confirm:
   - CRON job created with schedule
   - Anilist status updated (if applicable)
   - Next check time
```

## Drop a Series

**Triggers:** "I dropped {series}", "Stop tracking {series}", "Remove {series}"

```
1. Find and remove CRON job:
   list_cronjobs(include_disabled=false)
   - Find "AniHermes: {series}"
   - remove_cronjob("{job_id}")

2. Update tracker (if configured):
   - Anilist: terminal("python3 ~/.hermes/scripts/anihermes_anilist_api.py status {media_id} DROPPED")
   - MAL: terminal("python3 ~/.hermes/scripts/anihermes_mal_api.py status {anime_id} dropped")

3. Ask about files:
   "Do you want me to also delete the downloaded episodes? ({size} will be freed)"
   - If yes: terminal("python3 ~/.hermes/scripts/anihermes_library_manager.py cleanup '{series}' --confirm")
   - If no: keep files

4. Confirm all actions taken
```

## Daily Schedule Digest

**Triggers:** Set up via CRON — "Set up daily anime schedule"

```
schedule_cronjob(
  prompt="AniHermes daily digest:
    1. Get today's SubsPlease schedule: terminal('python3 ~/.hermes/scripts/anihermes_subsplease.py schedule')
    2. Get tracked series: list_cronjobs() and filter 'AniHermes:' prefix
    3. Cross-reference: which scheduled releases match tracked series?
    4. Get library status: terminal('python3 ~/.hermes/scripts/anihermes_library_manager.py list')
    5. Format digest:
       'Today's releases for your watchlist:
        - {Series A} ep {N} - releasing at {time} [not yet downloaded]
        - {Series B} ep {N} - releasing at {time} [already downloaded]
        No releases today for: {other tracked series}'
    6. Send digest to user",
  schedule="0 8 * * *",
  name="AniHermes: Daily Digest"
)
```
