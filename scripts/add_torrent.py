#!/usr/bin/env python3
"""
AniHermes - Torrent Downloader
Adds anime torrents to qbittorrent via WebUI API.

Usage:
  python3 add_torrent.py --series "Frieren" --season "S2" --magnet "magnet:?xt=..."
  python3 add_torrent.py --series "Frieren" --season "S2" --magnet "magnet:..." --config /path/to/config.yaml
"""

import argparse
import http.cookiejar
import os
import sys
import urllib.parse
import urllib.request

from config import load_config


def make_request(url, data=None, cookie_jar=None):
    """Make HTTP POST request."""
    if data:
        data = urllib.parse.urlencode(data).encode("utf-8")

    req = urllib.request.Request(url, data=data, method="POST")
    req.add_header("Content-Type", "application/x-www-form-urlencoded")
    req.add_header("User-Agent", "AniHermes/1.0")

    if cookie_jar:
        opener = urllib.request.build_opener(
            urllib.request.HTTPCookieProcessor(cookie_jar)
        )
        response = opener.open(req, timeout=10)
    else:
        response = urllib.request.urlopen(req, timeout=10)

    return response.read().decode("utf-8"), response.status


def get_save_path(config, series, season):
    """Generate save path for anime series/season."""
    safe_series = series.replace("/", " ").replace(":", " -").strip()
    safe_season = season.replace("/", " ").strip()

    save_dir = os.path.join(config["storage"]["anime_path"], safe_series, safe_season)
    os.makedirs(save_dir, exist_ok=True)
    return save_dir


def add_torrent(config, magnet, save_path):
    """Add torrent to qbittorrent via WebUI API."""
    base_url = config["torrent"]["webui_url"].rstrip("/")
    username = config["torrent"]["username"]
    password = config["torrent"]["password"]
    cookie_jar = http.cookiejar.CookieJar()

    print(f"Connecting to qbittorrent at {base_url}...")

    # Login
    try:
        response_text, status = make_request(
            f"{base_url}/api/v2/auth/login",
            {"username": username, "password": password},
            cookie_jar,
        )

        if status != 200 or response_text.strip() != "Ok.":
            print(f"ERROR: Login failed (status {status})")
            return False

        print("Logged in to qbittorrent")

        # Add torrent
        response_text, status = make_request(
            f"{base_url}/api/v2/torrents/add",
            {"urls": magnet, "savepath": save_path, "paused": "false"},
            cookie_jar,
        )

        if status == 200:
            print(f"Torrent added! Save path: {save_path}")
            return True
        else:
            print(f"ERROR: Failed to add torrent (status {status})")
            return False

    except urllib.error.URLError:
        print(f"ERROR: Cannot connect to qbittorrent at {base_url}")
        print("Make sure qbittorrent is running with WebUI enabled.")
        return False


def main():
    parser = argparse.ArgumentParser(description="AniHermes Torrent Downloader")
    parser.add_argument("--series", required=True, help="Anime series name")
    parser.add_argument("--season", required=True, help="Season (e.g. S1, S2)")
    parser.add_argument("--magnet", required=True, help="Magnet link")
    parser.add_argument("--config", help="Config file path")
    args = parser.parse_args()

    try:
        config = load_config(args.config)
    except FileNotFoundError as e:
        print(f"ERROR: {e}")
        return 1

    # Check storage path exists
    anime_path = config["storage"]["anime_path"]
    if not os.path.exists(anime_path):
        print(f"ERROR: Anime storage path does not exist: {anime_path}")
        print("Create it or update anime_path in config.yaml")
        return 1

    save_path = get_save_path(config, args.series, args.season)
    success = add_torrent(config, args.magnet, save_path)

    if success:
        print(f"\nSUCCESS! Downloading {args.series} {args.season}")
        print(f"Location: {save_path}")
        print(f"Monitor: {config['torrent']['webui_url']}")
        return 0
    else:
        print("\nDownload failed.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
