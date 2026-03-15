#!/usr/bin/env python3
"""
AniHermes - Torrent Downloader & Status Checker
Adds anime torrents to qbittorrent via WebUI API and checks download status.

Usage:
  python3 add_torrent.py add --series "Frieren" --season "S2" --magnet "magnet:?xt=..."
  python3 add_torrent.py status
  python3 add_torrent.py status --all

Legacy (still works):
  python3 add_torrent.py --series "Frieren" --season "S2" --magnet "magnet:..."
"""

import argparse
import http.cookiejar
import json
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


def _qbit_login(config):
    """Login to qbittorrent and return (opener, base_url) or None on failure."""
    base_url = config["torrent"]["webui_url"].rstrip("/")
    username = config["torrent"]["username"]
    password = config["torrent"]["password"]
    cookie_jar = http.cookiejar.CookieJar()
    opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cookie_jar))

    try:
        data = urllib.parse.urlencode({"username": username, "password": password}).encode()
        req = urllib.request.Request(f"{base_url}/api/v2/auth/login", data, method="POST")
        req.add_header("Content-Type", "application/x-www-form-urlencoded")
        resp = opener.open(req, timeout=10)
        if resp.status != 200 or resp.read().decode().strip() != "Ok.":
            return None
        return opener, base_url
    except urllib.error.URLError:
        return None


def check_status(config, show_all=False):
    """Check qbittorrent download status."""
    result = _qbit_login(config)
    if not result:
        base_url = config["torrent"]["webui_url"]
        print(f"ERROR: Cannot connect to qbittorrent at {base_url}")
        print("Make sure qbittorrent is running with WebUI enabled.")
        return 1

    opener, base_url = result
    filter_param = "all" if show_all else "downloading"
    resp = opener.open(f"{base_url}/api/v2/torrents/info?filter={filter_param}", timeout=10)
    torrents = json.loads(resp.read())

    if not torrents:
        if show_all:
            print("No torrents in qbittorrent.")
        else:
            print("No active downloads.")
        return 0

    for t in torrents:
        progress = t["progress"] * 100
        state = t.get("state", "unknown")
        size_mb = t.get("size", 0) / 1024 / 1024

        if state in ("downloading", "stalledDL", "metaDL", "forcedDL"):
            speed = t.get("dlspeed", 0) / 1024 / 1024
            eta = t.get("eta", 0)
            eta_str = f"{eta // 60}m{eta % 60}s" if eta < 8640000 else "unknown"
            print(f"  [DOWNLOADING] {t['name']}")
            print(f"    Progress: {progress:.1f}% | Speed: {speed:.1f} MB/s | ETA: {eta_str} | Size: {size_mb:.0f} MB")
        elif state in ("uploading", "stalledUP", "forcedUP"):
            print(f"  [SEEDING] {t['name']}")
            print(f"    Size: {size_mb:.0f} MB | Ratio: {t.get('ratio', 0):.2f}")
        elif state == "pausedDL":
            print(f"  [PAUSED] {t['name']}")
            print(f"    Progress: {progress:.1f}% | Size: {size_mb:.0f} MB")
        elif state in ("checkingDL", "checkingUP", "checkingResumeData"):
            print(f"  [CHECKING] {t['name']}")
            print(f"    Progress: {progress:.1f}%")
        else:
            print(f"  [{state.upper()}] {t['name']}")
            print(f"    Progress: {progress:.1f}% | Size: {size_mb:.0f} MB")

    return 0


def main():
    parser = argparse.ArgumentParser(description="AniHermes Torrent Downloader & Status")
    sub = parser.add_subparsers(dest="command")

    # add subcommand
    add_p = sub.add_parser("add", help="Add a torrent to qbittorrent")
    add_p.add_argument("--series", required=True, help="Anime series name")
    add_p.add_argument("--season", required=True, help="Season (e.g. S1, S2)")
    add_p.add_argument("--magnet", required=True, help="Magnet link")

    # status subcommand
    status_p = sub.add_parser("status", help="Check download status")
    status_p.add_argument("--all", action="store_true", help="Show all torrents, not just downloading")

    # Legacy support: if --series is passed without subcommand, treat as "add"
    parser.add_argument("--series", help=argparse.SUPPRESS)
    parser.add_argument("--season", help=argparse.SUPPRESS)
    parser.add_argument("--magnet", help=argparse.SUPPRESS)
    parser.add_argument("--config", help="Config file path")

    args = parser.parse_args()

    # Legacy mode: no subcommand but --series/--season/--magnet provided
    if not args.command and args.series:
        args.command = "add"

    if not args.command:
        parser.print_help()
        return 1

    try:
        config = load_config(getattr(args, "config", None))
    except FileNotFoundError as e:
        print(f"ERROR: {e}")
        return 1

    if args.command == "add":
        if not args.series or not args.season or not args.magnet:
            print("ERROR: --series, --season, and --magnet are required for 'add'")
            return 1

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

    elif args.command == "status":
        return check_status(config, show_all=getattr(args, "all", False))


if __name__ == "__main__":
    sys.exit(main())
