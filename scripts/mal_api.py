#!/usr/bin/env python3
"""
AniHermes - MyAnimeList API v2 Client
Handles anime search, watchlist reads, and progress updates.

Usage:
  python3 mal_api.py search "Frieren"
  python3 mal_api.py watchlist <username>
  python3 mal_api.py update <anime_id> <episode>
  python3 mal_api.py status <anime_id> <status>
  python3 mal_api.py seasons "Frieren"
"""

import argparse
import json
import os
import sys
import urllib.parse
import urllib.request

from config import load_config

MAL_API = "https://api.myanimelist.net/v2"


def mal_request(path, params=None, method="GET", data=None, token=None, client_id=None):
    """Make a request to MAL API v2."""
    url = MAL_API + path
    if params:
        url += "?" + urllib.parse.urlencode(params)

    if data and method == "PATCH":
        body = urllib.parse.urlencode(data).encode("utf-8")
    else:
        body = None

    req = urllib.request.Request(url, data=body, method=method)
    req.add_header("User-Agent", "AniHermes/1.0")

    if token:
        req.add_header("Authorization", f"Bearer {token}")
    elif client_id:
        req.add_header("X-MAL-CLIENT-ID", client_id)

    if method == "PATCH":
        req.add_header("Content-Type", "application/x-www-form-urlencoded")

    try:
        response = urllib.request.urlopen(req, timeout=15)
        return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        error_body = e.read().decode("utf-8")
        print(f"ERROR: MAL API returned {e.code}: {error_body[:200]}")
        return None


def search_anime(title, client_id):
    """Search for an anime by title."""
    result = mal_request(
        "/anime",
        params={
            "q": title,
            "limit": 5,
            "fields": "id,title,status,num_episodes,mean,genres,start_season,media_type",
        },
        client_id=client_id,
    )
    if not result:
        return []
    return [item["node"] for item in result.get("data", [])]


def get_user_watching(username, client_id):
    """Get a user's currently watching list. Only needs client_id for public lists."""
    result = mal_request(
        f"/users/{username}/animelist",
        params={
            "status": "watching",
            "limit": 100,
            "fields": "list_status,num_episodes,status",
        },
        client_id=client_id,
    )
    if not result:
        return []
    return result.get("data", [])


def get_user_completed(username, client_id):
    """Get a user's completed list with scores. For taste analysis."""
    result = mal_request(
        f"/users/{username}/animelist",
        params={
            "status": "completed",
            "limit": 100,
            "sort": "list_score",
            "fields": "list_status,num_episodes,genres,mean",
        },
        client_id=client_id,
    )
    if not result:
        return []
    return result.get("data", [])


def get_seasonal(year, season, client_id):
    """Get anime for a given season. season: winter, spring, summer, fall."""
    result = mal_request(
        f"/anime/season/{year}/{season}",
        params={
            "limit": 25,
            "sort": "anime_num_list_users",
            "fields": "id,title,num_episodes,status,mean,genres,start_season,media_type",
        },
        client_id=client_id,
    )
    if not result:
        return []
    return [item["node"] for item in result.get("data", [])]


def update_progress(anime_id, episode, token):
    """Update episode progress on MAL. Requires OAuth token."""
    if not token:
        print("ERROR: MAL_OAUTH_TOKEN not set. Cannot update progress.")
        return False

    result = mal_request(
        f"/anime/{anime_id}/my_list_status",
        method="PATCH",
        data={"num_episodes_watched": episode},
        token=token,
    )
    if result:
        print(f"Updated: episode {result.get('num_episodes_watched')}, status: {result.get('status')}")
        return True
    return False


def update_status(anime_id, status, token):
    """Update anime status on MAL (watching, completed, dropped, on_hold, plan_to_watch)."""
    if not token:
        print("ERROR: MAL_OAUTH_TOKEN not set.")
        return False

    result = mal_request(
        f"/anime/{anime_id}/my_list_status",
        method="PATCH",
        data={"status": status},
        token=token,
    )
    if result:
        print(f"Status updated to: {result.get('status')}")
        return True
    return False


def get_seasons(title, client_id):
    """Get all seasons/sequels of a franchise with episode counts.

    Searches for the anime, then follows related_anime to build a season map.
    """
    results = search_anime(title, client_id)
    if not results:
        return []

    entry = results[0]

    # Fetch the entry with relations
    detail = mal_request(
        f"/anime/{entry['id']}",
        params={"fields": "id,title,num_episodes,status,related_anime,media_type"},
        client_id=client_id,
    )
    if not detail:
        return []

    # Walk relations to find all seasons
    visited = {}
    to_visit = [detail["id"]]

    while to_visit:
        aid = to_visit.pop()
        if aid in visited:
            continue

        info = mal_request(
            f"/anime/{aid}",
            params={"fields": "id,title,num_episodes,status,related_anime,media_type"},
            client_id=client_id,
        )
        if not info:
            continue

        visited[aid] = info

        for rel in info.get("related_anime", []):
            rel_type = rel.get("relation_type", "")
            node = rel.get("node", {})
            nid = node.get("id")
            if rel_type in ("prequel", "sequel") and nid not in visited:
                to_visit.append(nid)

    if not visited:
        return []

    # Find root (no prequel among visited)
    has_prequel = set()
    for aid, info in visited.items():
        for rel in info.get("related_anime", []):
            if rel.get("relation_type") == "prequel" and rel["node"]["id"] in visited:
                has_prequel.add(aid)

    roots = [aid for aid in visited if aid not in has_prequel]
    if not roots:
        roots = [entry["id"]]

    # Order by following sequels
    ordered = []
    current = roots[0]
    season_num = 1
    while current and current in visited:
        info = visited[current]
        eps = info.get("num_episodes", 0) or 0
        status = info.get("status", "unknown")

        # MAL status values: finished_airing, currently_airing, not_yet_aired
        ordered.append({
            "season": season_num,
            "id": info["id"],
            "title": info.get("title", "Unknown"),
            "episodes": eps if eps > 0 else None,
            "status": status,
        })

        # Find sequel
        next_id = None
        for rel in info.get("related_anime", []):
            if rel.get("relation_type") == "sequel" and rel["node"]["id"] in visited:
                next_id = rel["node"]["id"]
                break
        current = next_id
        season_num += 1

    return ordered


def get_recommendations(anime_id, client_id):
    """Get recommendations for an anime."""
    result = mal_request(
        f"/anime/{anime_id}",
        params={"fields": "recommendations"},
        client_id=client_id,
    )
    if not result:
        return []
    recs = result.get("recommendations", [])
    return [r["node"] for r in recs[:10]]


def format_anime(anime):
    """Format anime info for display."""
    title = anime.get("title", "Unknown")
    score = anime.get("mean", "N/A")
    eps = anime.get("num_episodes", "?")
    status = anime.get("status", "unknown")
    genres = ", ".join(g["name"] for g in anime.get("genres", [])[:3])
    return f"[{anime['id']}] {title} ({status}, {eps} eps, score: {score}) [{genres}]"


def main():
    parser = argparse.ArgumentParser(description="AniHermes MAL API Client")
    parser.add_argument("--config", help="Config file path")
    sub = parser.add_subparsers(dest="command")

    search_p = sub.add_parser("search", help="Search for anime")
    search_p.add_argument("title", help="Anime title to search")

    watch_p = sub.add_parser("watchlist", help="Get user's watching list")
    watch_p.add_argument("username", nargs="?", help="MAL username")

    update_p = sub.add_parser("update", help="Update episode progress")
    update_p.add_argument("anime_id", type=int, help="MAL anime ID")
    update_p.add_argument("episode", type=int, help="Episode number")

    status_p = sub.add_parser("status", help="Update anime status")
    status_p.add_argument("anime_id", type=int, help="MAL anime ID")
    status_p.add_argument(
        "new_status",
        choices=["watching", "completed", "dropped", "on_hold", "plan_to_watch"],
    )

    recs_p = sub.add_parser("recommendations", help="Get recommendations")
    recs_p.add_argument("anime_id", type=int, help="MAL anime ID")

    seasons_p = sub.add_parser("seasons", help="Get all seasons with episode counts")
    seasons_p.add_argument("title", help="Anime title")

    completed_p = sub.add_parser("completed", help="Get user's completed list with scores")
    completed_p.add_argument("username", nargs="?", help="MAL username")

    seasonal_p = sub.add_parser("seasonal", help="Get seasonal anime")
    seasonal_p.add_argument("year", type=int, help="Year (e.g. 2026)")
    seasonal_p.add_argument("season", choices=["winter", "spring", "summer", "fall"])

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return 1

    config = load_config(args.config)
    client_id = config.get("mal", {}).get("client_id") or os.environ.get("MAL_CLIENT_ID", "")
    token = os.environ.get("MAL_OAUTH_TOKEN", "")

    if not client_id and not token:
        print("ERROR: MAL_CLIENT_ID not set. Set mal.client_id in config or MAL_CLIENT_ID env var.")
        return 1

    if args.command == "search":
        results = search_anime(args.title, client_id)
        if not results:
            print("No results found.")
            return 1
        print(f"Search results for '{args.title}':")
        for anime in results:
            print(f"  {format_anime(anime)}")

    elif args.command == "watchlist":
        username = args.username or config.get("mal", {}).get("username", "")
        if not username:
            print("ERROR: No username. Set mal.username in config or pass as argument.")
            return 1
        entries = get_user_watching(username, client_id)
        if not entries:
            print(f"No watching entries for {username}.")
            return 1
        print(f"Currently watching ({username}):")
        for item in entries:
            anime = item["node"]
            ls = item.get("list_status", {})
            eps = anime.get("num_episodes", "?")
            progress = ls.get("num_episodes_watched", 0)
            status = anime.get("status", "")
            air_str = " (still airing — not all episodes released yet)" if status == "currently_airing" else ""
            print(f"  [{anime['id']}] {anime['title']} - {progress}/{eps}{air_str}")

    elif args.command == "update":
        success = update_progress(args.anime_id, args.episode, token)
        return 0 if success else 1

    elif args.command == "status":
        success = update_status(args.anime_id, args.new_status, token)
        return 0 if success else 1

    elif args.command == "recommendations":
        recs = get_recommendations(args.anime_id, client_id)
        if not recs:
            print("No recommendations found.")
            return 1
        print("Recommendations:")
        for anime in recs:
            print(f"  {format_anime(anime)}")

    elif args.command == "completed":
        username = args.username or config.get("mal", {}).get("username", "")
        if not username:
            print("ERROR: No username. Set mal.username in config or pass as argument.")
            return 1
        entries = get_user_completed(username, client_id)
        if not entries:
            print(f"No completed entries for {username}.")
            return 1
        # Sort by user score descending
        entries.sort(key=lambda e: e.get("list_status", {}).get("score", 0), reverse=True)
        print(f"Completed ({username}, {len(entries)} total):")
        genre_counts = {}
        for item in entries:
            for g in item["node"].get("genres", []):
                genre_counts[g["name"]] = genre_counts.get(g["name"], 0) + 1
        top_genres = sorted(genre_counts.items(), key=lambda x: x[1], reverse=True)[:5]
        print(f"  Top genres: {', '.join(f'{g}({c})' for g, c in top_genres)}")
        print(f"  Top rated:")
        for item in entries[:10]:
            anime = item["node"]
            score = item.get("list_status", {}).get("score", "?")
            print(f"    [{anime['id']}] {anime['title']} (score: {score}/10)")

    elif args.command == "seasonal":
        anime = get_seasonal(args.year, args.season, client_id)
        if not anime:
            print(f"No anime found for {args.season} {args.year}")
            return 1
        print(f"{args.season} {args.year} anime (top 25 by popularity):")
        for a in anime:
            print(f"  {format_anime(a)}")

    elif args.command == "seasons":
        seasons = get_seasons(args.title, client_id)
        if not seasons:
            print(f"No season data found for '{args.title}'")
            return 1
        print(f"Seasons for '{args.title}':")
        abs_start = 1
        for s in seasons:
            eps = s["episodes"] or "?"
            abs_end = abs_start + (s["episodes"] - 1) if s["episodes"] else "?"
            print(f"  S{s['season']}: {s['title']} [{s['id']}]")
            print(f"    Episodes: {eps}, Status: {s['status']}")
            print(f"    Absolute range: {abs_start}-{abs_end}")
            if s["episodes"]:
                abs_start += s["episodes"]

    return 0


if __name__ == "__main__":
    sys.exit(main())
