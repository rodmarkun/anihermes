#!/usr/bin/env python3
"""
AniHermes - SubsPlease Search & Magnet Extractor
Searches SubsPlease for anime episodes and extracts magnet links.

Usage:
  python3 subsplease.py search "Frieren"
  python3 subsplease.py latest "Frieren"
  python3 subsplease.py episodes "Frieren"
  python3 subsplease.py schedule
"""

import argparse
import json
import sys
import urllib.parse
import urllib.request

SUBSPLEASE_API = "https://subsplease.org/api/"


def api_request(params):
    """Make a request to SubsPlease API."""
    url = SUBSPLEASE_API + "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url)
    req.add_header("User-Agent", "AniHermes/1.0")

    try:
        response = urllib.request.urlopen(req, timeout=15)
        data = response.read()
        if not data:
            return None
        return json.loads(data)
    except Exception as e:
        print(f"ERROR: SubsPlease API request failed: {e}", file=sys.stderr)
        return None


def search_show(title):
    """Search for episodes matching title. Returns unique show names and their latest episodes."""
    result = api_request({"f": "search", "tz": "Europe/Madrid", "s": title})
    if not result:
        return []

    # Deduplicate by show name, keep latest episode per show
    shows = {}
    for key, ep in result.items():
        if not isinstance(ep, dict) or "show" not in ep:
            continue
        show_name = ep["show"]
        if show_name not in shows or ep.get("episode", "") > shows[show_name].get("episode", ""):
            shows[show_name] = ep

    return list(shows.values())


def get_episodes(title, quality="1080"):
    """Get all episodes for a show via search API. Quality: 480, 720, 1080."""
    result = api_request({"f": "search", "tz": "Europe/Madrid", "s": title})
    if not result:
        return []

    episodes = []
    for key, ep in result.items():
        if not isinstance(ep, dict) or "show" not in ep:
            continue
        # Filter to matching show name
        if title.lower() not in ep["show"].lower():
            continue

        magnet = None
        for dl in ep.get("downloads", []):
            if dl.get("res") == quality:
                magnet = dl.get("magnet")
                break
        # Fallback to highest quality
        if not magnet:
            downloads = ep.get("downloads", [])
            if downloads:
                magnet = downloads[-1].get("magnet")

        episodes.append({
            "episode": ep.get("episode", ""),
            "show": ep.get("show", title),
            "release_date": ep.get("release_date", ""),
            "magnet": magnet,
            "page": ep.get("page", ""),
        })

    return sorted(episodes, key=lambda e: str(e["episode"]))


def get_latest_episode(title, quality="1080"):
    """Get the latest episode for a show."""
    episodes = get_episodes(title, quality)
    if not episodes:
        return None
    return episodes[-1]


def get_schedule():
    """Get release schedule."""
    result = api_request({"f": "schedule", "tz": "Europe/Madrid"})
    if not result or "schedule" not in result:
        return []

    schedule = []
    for day, shows in result["schedule"].items():
        for show in shows:
            schedule.append({
                "title": show.get("title", ""),
                "time": show.get("time", ""),
                "day": day,
                "aired": show.get("aired", False),
                "page": show.get("page", ""),
                "image_url": show.get("image_url", ""),
            })
    return schedule


def main():
    parser = argparse.ArgumentParser(description="AniHermes SubsPlease Client")
    sub = parser.add_subparsers(dest="command")

    search_p = sub.add_parser("search", help="Search for a show")
    search_p.add_argument("title", help="Show title")

    latest_p = sub.add_parser("latest", help="Get latest episode with magnet")
    latest_p.add_argument("title", help="Show title")
    latest_p.add_argument("--quality", default="1080", help="Quality: 480, 720, 1080")

    episodes_p = sub.add_parser("episodes", help="List all episodes")
    episodes_p.add_argument("title", help="Show title")
    episodes_p.add_argument("--quality", default="1080", help="Quality: 480, 720, 1080")

    sub.add_parser("schedule", help="Release schedule")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return 1

    if args.command == "search":
        shows = search_show(args.title)
        if not shows:
            print(f"No shows found for '{args.title}'")
            return 1
        print(f"Shows matching '{args.title}':")
        for show in shows:
            ep = show.get("episode", "?")
            print(f"  {show['show']} (latest: ep {ep})")

    elif args.command == "latest":
        ep = get_latest_episode(args.title, args.quality)
        if not ep:
            print(f"No episodes found for '{args.title}'")
            return 1
        print(f"Latest: {ep['show']} - Episode {ep['episode']}")
        print(f"Released: {ep['release_date']}")
        if ep["magnet"]:
            print(f"Magnet: {ep['magnet']}")
        else:
            print("No magnet link available")

    elif args.command == "episodes":
        episodes = get_episodes(args.title, args.quality)
        if not episodes:
            print(f"No episodes found for '{args.title}'")
            return 1
        print(f"Episodes for '{args.title}':")
        for ep in episodes:
            has_magnet = "has magnet" if ep["magnet"] else "no magnet"
            print(f"  Ep {ep['episode']} ({ep['release_date']}) [{has_magnet}]")

    elif args.command == "schedule":
        schedule = get_schedule()
        if not schedule:
            print("No schedule available")
            return 1
        print("SubsPlease Release Schedule:")
        current_day = ""
        for show in schedule:
            if show["day"] != current_day:
                current_day = show["day"]
                print(f"\n  {current_day}:")
            aired = " [AIRED]" if show["aired"] else ""
            print(f"    {show['time']} - {show['title']}{aired}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
