#!/usr/bin/env python3
"""
AniHermes - Nyaa.si Search & Magnet Extractor
Searches Nyaa.si RSS feed for anime torrents and extracts magnet links.

Usage:
  python3 nyaa.py search "Frieren 1080p"
  python3 nyaa.py search "Frieren S02E08" --sort seeders
  python3 nyaa.py best "Frieren S02E08 1080p"
"""

import argparse
import sys
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET

NYAA_RSS = "https://nyaa.si/rss"
# Category 1_2 = Anime - English-translated
DEFAULT_CATEGORY = "1_2"
NYAA_NS = "https://nyaa.si/xmlns/nyaa"


def search(query, category=DEFAULT_CATEGORY, sort="seeders"):
    """Search Nyaa.si via RSS. Returns list of results sorted by seeders desc."""
    params = {"q": query, "c": category, "f": "0"}
    url = NYAA_RSS + "?" + urllib.parse.urlencode(params)

    req = urllib.request.Request(url)
    req.add_header("User-Agent", "AniHermes/1.0")

    try:
        response = urllib.request.urlopen(req, timeout=15)
        data = response.read()
    except Exception as e:
        print(f"ERROR: Nyaa search failed: {e}", file=sys.stderr)
        return []

    try:
        root = ET.fromstring(data)
    except ET.ParseError as e:
        print(f"ERROR: Failed to parse Nyaa RSS: {e}", file=sys.stderr)
        return []

    results = []
    for item in root.findall(".//item"):
        title = item.findtext("title", "")
        link = item.findtext("link", "")
        guid = item.findtext("guid", "")
        pub_date = item.findtext("pubDate", "")

        seeders = int(item.findtext(f"{{{NYAA_NS}}}seeders", "0") or "0")
        leechers = int(item.findtext(f"{{{NYAA_NS}}}leechers", "0") or "0")
        downloads = int(item.findtext(f"{{{NYAA_NS}}}downloads", "0") or "0")
        info_hash = item.findtext(f"{{{NYAA_NS}}}infoHash", "")
        size = item.findtext(f"{{{NYAA_NS}}}size", "")
        trusted = item.findtext(f"{{{NYAA_NS}}}trusted", "No") == "Yes"

        # Build magnet link from infoHash
        magnet = ""
        if info_hash:
            magnet = (
                f"magnet:?xt=urn:btih:{info_hash}"
                f"&dn={urllib.parse.quote(title)}"
                f"&tr=http%3A%2F%2Fnyaa.tracker.wf%3A7777%2Fannounce"
                f"&tr=udp%3A%2F%2Fopen.stealth.si%3A80%2Fannounce"
                f"&tr=udp%3A%2F%2Ftracker.opentrackr.org%3A1337%2Fannounce"
            )

        results.append({
            "title": title,
            "link": link,
            "guid": guid,
            "pub_date": pub_date,
            "seeders": seeders,
            "leechers": leechers,
            "downloads": downloads,
            "info_hash": info_hash,
            "size": size,
            "trusted": trusted,
            "magnet": magnet,
        })

    # Sort by seeders descending
    if sort == "seeders":
        results.sort(key=lambda r: r["seeders"], reverse=True)
    elif sort == "date":
        pass  # RSS is already date-sorted

    return results


def best_result(query, category=DEFAULT_CATEGORY):
    """Get the single best result (most seeders) for a query."""
    results = search(query, category)
    if not results:
        return None
    # Prefer trusted uploaders, then most seeders
    trusted = [r for r in results if r["trusted"]]
    if trusted:
        return trusted[0]
    return results[0]


def main():
    parser = argparse.ArgumentParser(description="AniHermes Nyaa.si Client")
    sub = parser.add_subparsers(dest="command")

    search_p = sub.add_parser("search", help="Search Nyaa.si")
    search_p.add_argument("query", help="Search query")
    search_p.add_argument("--sort", default="seeders", choices=["seeders", "date"])
    search_p.add_argument("--limit", type=int, default=10, help="Max results")

    best_p = sub.add_parser("best", help="Get best single result")
    best_p.add_argument("query", help="Search query")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return 1

    if args.command == "search":
        results = search(args.query)
        if not results:
            print(f"No results for '{args.query}'")
            return 1
        print(f"Nyaa results for '{args.query}':")
        for r in results[: args.limit]:
            trusted_str = " [TRUSTED]" if r["trusted"] else ""
            print(f"  {r['title']}")
            print(f"    {r['size']} | {r['seeders']}S/{r['leechers']}L{trusted_str}")
            if r["magnet"]:
                print(f"    Magnet: {r['magnet'][:80]}...")
            print()

    elif args.command == "best":
        r = best_result(args.query)
        if not r:
            print(f"No results for '{args.query}'")
            return 1
        trusted_str = " [TRUSTED]" if r["trusted"] else ""
        print(f"Best: {r['title']}")
        print(f"Size: {r['size']}")
        print(f"Seeders: {r['seeders']} | Leechers: {r['leechers']}{trusted_str}")
        if r["magnet"]:
            print(f"Magnet: {r['magnet']}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
