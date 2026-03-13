#!/usr/bin/env python3
"""
AniHermes - Anilist GraphQL API Client
Handles anime search, watchlist reads, and progress updates.

Usage:
  python3 anilist_api.py search "Frieren"
  python3 anilist_api.py watchlist <username>
  python3 anilist_api.py update <media_id> <episode>
  python3 anilist_api.py recommendations <media_id>
"""

import argparse
import json
import sys
import urllib.request

from config import load_config

ANILIST_API = "https://graphql.anilist.co"


def graphql_request(query, variables=None, token=None):
    """Make a GraphQL request to Anilist API."""
    payload = json.dumps({"query": query, "variables": variables or {}}).encode("utf-8")

    req = urllib.request.Request(ANILIST_API, data=payload, method="POST")
    req.add_header("Content-Type", "application/json")
    req.add_header("Accept", "application/json")
    req.add_header("User-Agent", "AniHermes/1.0")
    if token:
        req.add_header("Authorization", f"Bearer {token}")

    try:
        response = urllib.request.urlopen(req, timeout=15)
        return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        error_body = e.read().decode("utf-8")
        print(f"ERROR: Anilist API returned {e.code}: {error_body[:200]}")
        return None


def search_anime(title):
    """Search for an anime by title. Returns list of matches."""
    query = """
    query ($search: String) {
        Page(page: 1, perPage: 5) {
            media(search: $search, type: ANIME) {
                id
                title { romaji english native }
                status
                episodes
                averageScore
                genres
                seasonYear
                season
                format
                coverImage { large }
            }
        }
    }
    """
    result = graphql_request(query, {"search": title})
    if not result:
        return []
    return result.get("data", {}).get("Page", {}).get("media", [])


def get_user_watching(username):
    """Get a user's currently watching anime list. No auth needed for public lists."""
    query = """
    query ($username: String) {
        MediaListCollection(userName: $username, type: ANIME, status: CURRENT) {
            lists {
                entries {
                    media {
                        id
                        title { romaji english }
                        episodes
                        status
                        nextAiringEpisode { episode airingAt }
                    }
                    progress
                    score
                }
            }
        }
    }
    """
    result = graphql_request(query, {"username": username})
    if not result:
        return []
    lists = result.get("data", {}).get("MediaListCollection", {}).get("lists", [])
    entries = []
    for lst in lists:
        entries.extend(lst.get("entries", []))
    return entries


def get_user_completed(username):
    """Get a user's completed anime with scores. For taste analysis."""
    query = """
    query ($username: String) {
        MediaListCollection(userName: $username, type: ANIME, status: COMPLETED) {
            lists {
                entries {
                    media {
                        id
                        title { romaji english }
                        episodes
                        genres
                        averageScore
                    }
                    score
                }
            }
        }
    }
    """
    result = graphql_request(query, {"username": username})
    if not result:
        return []
    lists = result.get("data", {}).get("MediaListCollection", {}).get("lists", [])
    entries = []
    for lst in lists:
        entries.extend(lst.get("entries", []))
    return entries


def get_seasonal(year, season):
    """Get anime for a given season. season: WINTER, SPRING, SUMMER, FALL."""
    query = """
    query ($season: MediaSeason, $seasonYear: Int) {
        Page(page: 1, perPage: 25) {
            media(season: $season, seasonYear: $seasonYear, type: ANIME, sort: POPULARITY_DESC, format: TV) {
                id
                title { romaji english }
                episodes
                status
                averageScore
                genres
                nextAiringEpisode { episode airingAt }
                coverImage { large }
            }
        }
    }
    """
    result = graphql_request(query, {"season": season, "seasonYear": year})
    if not result:
        return []
    return result.get("data", {}).get("Page", {}).get("media", [])


def update_progress(media_id, episode, token):
    """Update episode progress on Anilist. Requires OAuth token."""
    if not token:
        print("ERROR: ANILIST_OAUTH_TOKEN not set. Cannot update progress.")
        return False

    query = """
    mutation ($mediaId: Int, $progress: Int) {
        SaveMediaListEntry(mediaId: $mediaId, progress: $progress) {
            id
            progress
            status
        }
    }
    """
    result = graphql_request(
        query, {"mediaId": media_id, "progress": episode}, token=token
    )
    if result and "data" in result:
        entry = result["data"]["SaveMediaListEntry"]
        print(f"Updated: episode {entry['progress']}, status: {entry['status']}")
        return True
    return False


def update_status(media_id, status, token):
    """Update anime status on Anilist (CURRENT, COMPLETED, DROPPED, PAUSED, PLANNING)."""
    if not token:
        print("ERROR: ANILIST_OAUTH_TOKEN not set.")
        return False

    query = """
    mutation ($mediaId: Int, $status: MediaListStatus) {
        SaveMediaListEntry(mediaId: $mediaId, status: $status) {
            id
            status
        }
    }
    """
    result = graphql_request(
        query, {"mediaId": media_id, "status": status}, token=token
    )
    if result and "data" in result:
        print(f"Status updated to: {result['data']['SaveMediaListEntry']['status']}")
        return True
    return False


def get_seasons(title):
    """Get all seasons/sequels of a franchise with episode counts.

    Searches for the anime, then follows SEQUEL relations to build a season map.
    Returns ordered list: [{season: 1, id: ..., title: ..., episodes: 24, status: ...}, ...]
    This is used to map absolute episode numbers (SubsPlease) to season-relative numbers.
    """
    # First, search to find an entry point
    results = search_anime(title)
    if not results:
        return []

    # Pick the best match (prefer first result)
    entry = results[0]

    # Now fetch relations to find the full chain
    query = """
    query ($id: Int) {
        Media(id: $id, type: ANIME) {
            id
            title { romaji english }
            episodes
            status
            nextAiringEpisode { episode }
            format
            relations {
                edges {
                    relationType
                    node {
                        id
                        title { romaji english }
                        episodes
                        status
                        nextAiringEpisode { episode }
                        format
                        relations {
                            edges {
                                relationType
                                node {
                                    id
                                    title { romaji english }
                                    episodes
                                    status
                                    nextAiringEpisode { episode }
                                    format
                                }
                            }
                        }
                    }
                }
            }
        }
    }
    """

    # Walk backwards to find the first season (no prequel)
    # Then walk forward collecting sequels
    visited = {}
    to_visit = [entry["id"]]

    while to_visit:
        mid = to_visit.pop()
        if mid in visited:
            continue
        result = graphql_request(query, {"id": mid})
        if not result or "data" not in result:
            continue
        media = result["data"]["Media"]
        visited[mid] = media
        for edge in media.get("relations", {}).get("edges", []):
            rel_type = edge.get("relationType")
            node = edge.get("node", {})
            nid = node.get("id")
            if rel_type in ("PREQUEL", "SEQUEL") and node.get("format") in ("TV", "TV_SHORT") and nid not in visited:
                to_visit.append(nid)

    if not visited:
        return []

    # Find the root (no prequel among visited)
    has_prequel = set()
    for mid, media in visited.items():
        for edge in media.get("relations", {}).get("edges", []):
            if edge.get("relationType") == "PREQUEL" and edge["node"]["id"] in visited:
                has_prequel.add(mid)

    # Order: start from root, follow sequels
    roots = [mid for mid in visited if mid not in has_prequel]
    if not roots:
        roots = [entry["id"]]

    ordered = []
    current = roots[0]
    season_num = 1
    while current and current in visited:
        media = visited[current]
        aired_eps = media.get("episodes") or 0
        # For airing shows, use nextAiringEpisode - 1 as aired count
        next_airing = media.get("nextAiringEpisode")
        if next_airing and media.get("status") == "RELEASING":
            aired_eps = next_airing["episode"] - 1

        title_str = media["title"].get("english") or media["title"].get("romaji", "Unknown")
        ordered.append({
            "season": season_num,
            "id": media["id"],
            "title": title_str,
            "episodes": media.get("episodes"),
            "aired_episodes": aired_eps,
            "status": media.get("status", "UNKNOWN"),
        })

        # Find sequel
        next_id = None
        for edge in media.get("relations", {}).get("edges", []):
            if edge.get("relationType") == "SEQUEL" and edge["node"]["id"] in visited:
                next_id = edge["node"]["id"]
                break
        current = next_id
        season_num += 1

    return ordered



    """Get recommendations for an anime."""
    query = """
    query ($id: Int) {
        Media(id: $id, type: ANIME) {
            title { romaji }
            recommendations(page: 1, perPage: 10, sort: RATING_DESC) {
                nodes {
                    mediaRecommendation {
                        id
                        title { romaji english }
                        averageScore
                        genres
                        status
                        episodes
                    }
                    rating
                }
            }
        }
    }
    """
    result = graphql_request(query, {"id": media_id})
    if not result:
        return []
    nodes = (
        result.get("data", {})
        .get("Media", {})
        .get("recommendations", {})
        .get("nodes", [])
    )
    return [n["mediaRecommendation"] for n in nodes if n.get("mediaRecommendation")]


def format_anime(anime):
    """Format anime info for display."""
    title = anime["title"].get("english") or anime["title"].get("romaji", "Unknown")
    score = anime.get("averageScore", "N/A")
    eps = anime.get("episodes", "?")
    status = anime.get("status", "Unknown")
    genres = ", ".join(anime.get("genres", [])[:3])
    return f"[{anime['id']}] {title} ({status}, {eps} eps, score: {score}) [{genres}]"


def main():
    parser = argparse.ArgumentParser(description="AniHermes Anilist API Client")
    parser.add_argument("--config", help="Config file path")
    sub = parser.add_subparsers(dest="command")

    search_p = sub.add_parser("search", help="Search for anime")
    search_p.add_argument("title", help="Anime title to search")

    watch_p = sub.add_parser("watchlist", help="Get user's watching list")
    watch_p.add_argument("username", nargs="?", help="Anilist username")

    update_p = sub.add_parser("update", help="Update episode progress")
    update_p.add_argument("media_id", type=int, help="Anilist media ID")
    update_p.add_argument("episode", type=int, help="Episode number")

    status_p = sub.add_parser("status", help="Update anime status")
    status_p.add_argument("media_id", type=int, help="Anilist media ID")
    status_p.add_argument(
        "new_status",
        choices=["CURRENT", "COMPLETED", "DROPPED", "PAUSED", "PLANNING"],
    )

    recs_p = sub.add_parser("recommendations", help="Get recommendations")
    recs_p.add_argument("media_id", type=int, help="Anilist media ID")

    seasons_p = sub.add_parser("seasons", help="Get all seasons with episode counts")
    seasons_p.add_argument("title", help="Anime title")

    completed_p = sub.add_parser("completed", help="Get user's completed list with scores")
    completed_p.add_argument("username", nargs="?", help="Anilist username")

    seasonal_p = sub.add_parser("seasonal", help="Get seasonal anime")
    seasonal_p.add_argument("year", type=int, help="Year (e.g. 2026)")
    seasonal_p.add_argument("season", choices=["WINTER", "SPRING", "SUMMER", "FALL"])

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return 1

    config = load_config(args.config)

    if args.command == "search":
        results = search_anime(args.title)
        if not results:
            print("No results found.")
            return 1
        print(f"Search results for '{args.title}':")
        for anime in results:
            print(f"  {format_anime(anime)}")

    elif args.command == "watchlist":
        username = args.username or config["anilist"]["username"]
        if not username:
            print("ERROR: No username. Set anilist.username in config or pass as argument.")
            return 1
        entries = get_user_watching(username)
        if not entries:
            print(f"No watching entries for {username}.")
            return 1
        print(f"Currently watching ({username}):")
        for entry in entries:
            title = (
                entry["media"]["title"].get("english")
                or entry["media"]["title"].get("romaji")
            )
            eps = entry["media"].get("episodes", "?")
            progress = entry["progress"]
            next_ep = entry["media"].get("nextAiringEpisode")
            next_str = f" (next: ep {next_ep['episode']})" if next_ep else ""
            print(f"  [{entry['media']['id']}] {title} - {progress}/{eps}{next_str}")

    elif args.command == "update":
        token = config["anilist"]["oauth_token"]
        success = update_progress(args.media_id, args.episode, token)
        return 0 if success else 1

    elif args.command == "status":
        token = config["anilist"]["oauth_token"]
        success = update_status(args.media_id, args.new_status, token)
        return 0 if success else 1

    elif args.command == "recommendations":
        recs = get_recommendations(args.media_id)
        if not recs:
            print("No recommendations found.")
            return 1
        print("Recommendations:")
        for anime in recs:
            print(f"  {format_anime(anime)}")

    elif args.command == "completed":
        username = args.username or config["anilist"]["username"]
        if not username:
            print("ERROR: No username. Set anilist.username in config or pass as argument.")
            return 1
        entries = get_user_completed(username)
        if not entries:
            print(f"No completed entries for {username}.")
            return 1
        # Sort by user score descending
        entries.sort(key=lambda e: e.get("score", 0), reverse=True)
        print(f"Completed ({username}, {len(entries)} total):")
        # Show genre stats
        genre_counts = {}
        for entry in entries:
            for g in entry["media"].get("genres", []):
                genre_counts[g] = genre_counts.get(g, 0) + 1
        top_genres = sorted(genre_counts.items(), key=lambda x: x[1], reverse=True)[:5]
        print(f"  Top genres: {', '.join(f'{g}({c})' for g, c in top_genres)}")
        print(f"  Top rated:")
        for entry in entries[:10]:
            title = entry["media"]["title"].get("english") or entry["media"]["title"].get("romaji")
            score = entry.get("score", "?")
            print(f"    [{entry['media']['id']}] {title} (score: {score}/10)")

    elif args.command == "seasonal":
        anime = get_seasonal(args.year, args.season)
        if not anime:
            print(f"No anime found for {args.season} {args.year}")
            return 1
        print(f"{args.season} {args.year} anime (top 25 by popularity):")
        for a in anime:
            print(f"  {format_anime(a)}")

    elif args.command == "seasons":
        seasons = get_seasons(args.title)
        if not seasons:
            print(f"No season data found for '{args.title}'")
            return 1
        print(f"Seasons for '{args.title}':")
        abs_start = 1
        for s in seasons:
            eps = s["episodes"] or "?"
            aired = s["aired_episodes"]
            abs_end = abs_start + (s["episodes"] - 1) if s["episodes"] else "?"
            status_str = s["status"]
            if status_str == "RELEASING":
                status_str = f"RELEASING ({aired} aired)"
            print(f"  S{s['season']}: {s['title']} [{s['id']}]")
            print(f"    Episodes: {eps}, Status: {status_str}")
            print(f"    Absolute range: {abs_start}-{abs_end}")
            if s["episodes"]:
                abs_start += s["episodes"]

    return 0


if __name__ == "__main__":
    sys.exit(main())
