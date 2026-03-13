#!/usr/bin/env python3
"""
AniHermes - Anime Library Manager
Scans local anime library, reports stats, and manages series.

Usage:
  python3 library_manager.py list
  python3 library_manager.py info "Frieren"
  python3 library_manager.py stats
  python3 library_manager.py cleanup "Series Name" --confirm
"""

import argparse
import os
import shutil
import sys

from config import load_config


def scan_library(anime_path):
    """Scan anime library and return structured data."""
    if not os.path.exists(anime_path):
        return []

    library = []
    for series in sorted(os.listdir(anime_path)):
        series_path = os.path.join(anime_path, series)
        if not os.path.isdir(series_path):
            continue

        seasons = []
        for season in sorted(os.listdir(series_path)):
            season_path = os.path.join(series_path, season)
            if not os.path.isdir(season_path):
                continue

            episodes = []
            total_size = 0
            for f in sorted(os.listdir(season_path)):
                fpath = os.path.join(season_path, f)
                if os.path.isfile(fpath) and f.endswith((".mkv", ".mp4", ".avi")):
                    size = os.path.getsize(fpath)
                    total_size += size
                    episodes.append({"filename": f, "size": size})

            seasons.append(
                {
                    "name": season,
                    "path": season_path,
                    "episodes": episodes,
                    "episode_count": len(episodes),
                    "total_size": total_size,
                }
            )

        library.append(
            {
                "name": series,
                "path": series_path,
                "seasons": seasons,
                "total_episodes": sum(s["episode_count"] for s in seasons),
                "total_size": sum(s["total_size"] for s in seasons),
            }
        )

    return library


def format_size(size_bytes):
    """Format bytes to human readable."""
    for unit in ["B", "KB", "MB", "GB", "TB"]:
        if size_bytes < 1024:
            return f"{size_bytes:.1f} {unit}"
        size_bytes /= 1024
    return f"{size_bytes:.1f} PB"


def suggest_cleanup(library, anime_path):
    """Suggest series to clean up, sorted by size descending. Does NOT delete anything."""
    if not library:
        return []

    suggestions = []
    for series in sorted(library, key=lambda s: s["total_size"], reverse=True):
        suggestions.append({
            "name": series["name"],
            "episodes": series["total_episodes"],
            "size": series["total_size"],
            "size_human": format_size(series["total_size"]),
            "path": series["path"],
        })
    return suggestions


def main():
    parser = argparse.ArgumentParser(description="AniHermes Library Manager")
    parser.add_argument("--config", help="Config file path")
    sub = parser.add_subparsers(dest="command")

    sub.add_parser("list", help="List all series")

    info_p = sub.add_parser("info", help="Info about a specific series")
    info_p.add_argument("series", help="Series name")

    sub.add_parser("stats", help="Library statistics")

    sub.add_parser("cleanup-suggestions", help="Suggest series to clean up by size")

    cleanup_p = sub.add_parser("cleanup", help="Remove a series from library")
    cleanup_p.add_argument("series", help="Series name to remove")
    cleanup_p.add_argument(
        "--confirm", action="store_true", help="Actually delete (dry run without)"
    )

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return 1

    config = load_config(args.config)
    anime_path = config["storage"]["anime_path"]
    library = scan_library(anime_path)

    if args.command == "list":
        if not library:
            print(f"Library is empty ({anime_path})")
            return 0
        print(f"Anime Library ({anime_path}):")
        for series in library:
            seasons = len(series["seasons"])
            eps = series["total_episodes"]
            size = format_size(series["total_size"])
            print(f"  {series['name']} ({seasons} season(s), {eps} episodes, {size})")

    elif args.command == "info":
        match = next((s for s in library if args.series.lower() in s["name"].lower()), None)
        if not match:
            print(f"Series '{args.series}' not found in library.")
            return 1
        print(f"{match['name']}:")
        print(f"  Path: {match['path']}")
        print(f"  Total size: {format_size(match['total_size'])}")
        for season in match["seasons"]:
            print(f"\n  {season['name']} ({season['episode_count']} episodes, {format_size(season['total_size'])}):")
            for ep in season["episodes"]:
                print(f"    {ep['filename']} ({format_size(ep['size'])})")

    elif args.command == "stats":
        total_series = len(library)
        total_eps = sum(s["total_episodes"] for s in library)
        total_size = sum(s["total_size"] for s in library)

        # Disk space
        try:
            disk = shutil.disk_usage(anime_path)
            free = format_size(disk.free)
            total_disk = format_size(disk.total)
            used_pct = (disk.used / disk.total) * 100
        except OSError:
            free = "N/A"
            total_disk = "N/A"
            used_pct = 0

        print(f"Library Statistics ({anime_path}):")
        print(f"  Series: {total_series}")
        print(f"  Total episodes: {total_eps}")
        print(f"  Library size: {format_size(total_size)}")
        print(f"  Disk: {free} free / {total_disk} total ({used_pct:.1f}% used)")

    elif args.command == "cleanup-suggestions":
        suggestions = suggest_cleanup(library, anime_path)
        if not suggestions:
            print("Library is empty, nothing to clean up.")
            return 0

        # Disk info
        try:
            disk = shutil.disk_usage(anime_path)
            free_pct = (disk.free / disk.total) * 100
            print(f"Disk: {format_size(disk.free)} free / {format_size(disk.total)} total ({free_pct:.1f}% free)")
            if free_pct < 10:
                print("WARNING: Less than 10% disk space remaining!")
            print()
        except OSError:
            pass

        print("Cleanup suggestions (largest first):")
        for i, s in enumerate(suggestions, 1):
            print(f"  {i}. {s['name']} — {s['episodes']} episodes, {s['size_human']}")
        print()
        print("To delete: python3 library_manager.py cleanup '{name}' --confirm")

    elif args.command == "cleanup":
        match = next((s for s in library if args.series.lower() in s["name"].lower()), None)
        if not match:
            print(f"Series '{args.series}' not found in library.")
            return 1

        print(f"Series: {match['name']}")
        print(f"  Episodes: {match['total_episodes']}")
        print(f"  Size: {format_size(match['total_size'])}")
        print(f"  Path: {match['path']}")

        if args.confirm:
            shutil.rmtree(match["path"])
            print(f"\nDELETED: {match['name']}")
        else:
            print(f"\nDry run. Add --confirm to actually delete.")

    return 0


if __name__ == "__main__":
    sys.exit(main())
