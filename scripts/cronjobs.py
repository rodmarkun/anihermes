#!/usr/bin/env python3
"""
AniHermes - Hermes CRON Job Viewer
Displays Hermes scheduled jobs with nice formatting.

Usage:
  python3 cronjobs.py list             # Show AniHermes jobs only
  python3 cronjobs.py list --all       # Show all Hermes CRON jobs
  python3 cronjobs.py show <job>       # Detailed view of a specific job
"""

import argparse
import json
import os
import sys
from datetime import datetime

# Constants
CRON_FILE = os.path.expanduser("~/.hermes/cron/jobs.json")
ANIHERMES_PREFIX = "AniHermes:"


def load_jobs():
    """Load CRON jobs from Hermes storage.

    Returns:
        list[dict]: List of job objects, or None if file doesn't exist/invalid
    """
    if not os.path.exists(CRON_FILE):
        return None

    try:
        with open(CRON_FILE, "r") as f:
            data = json.load(f)
            # Handle both list format and dict-with-jobs format
            if isinstance(data, list):
                return data
            elif isinstance(data, dict) and "jobs" in data:
                return data["jobs"]
            return []
    except (json.JSONDecodeError, IOError):
        return None


def format_timestamp(ts):
    """Format a timestamp (Unix or ISO) as human-readable.

    Args:
        ts: Unix timestamp (int), ISO string, or None

    Returns:
        str: Formatted datetime or "N/A"
    """
    if ts is None:
        return "N/A"

    try:
        if isinstance(ts, (int, float)):
            dt = datetime.fromtimestamp(ts)
        else:
            # Try parsing ISO format
            dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
        return dt.strftime("%Y-%m-%d %H:%M")
    except (ValueError, OSError, TypeError):
        return str(ts) if ts else "N/A"


def extract_series_name(name):
    """Extract series name from AniHermes job name.

    Args:
        name: Full job name like "AniHermes: Frieren"

    Returns:
        str: Series name or original name if not AniHermes format
    """
    if name and name.startswith(ANIHERMES_PREFIX):
        return name[len(ANIHERMES_PREFIX) :].strip()
    return name or "Unnamed"


def get_job_status(job):
    """Determine job status based on its properties.

    Args:
        job: Job dict with potential 'enabled', 'disabled', or 'paused' fields

    Returns:
        str: Status like "ACTIVE", "PAUSED", or "DISABLED"
    """
    # Different Hermes versions may use different field names
    if job.get("disabled", False):
        return "DISABLED"
    if job.get("paused", False):
        return "PAUSED"
    if job.get("enabled", True) is False:
        return "DISABLED"
    return "ACTIVE"


def is_anihermes_job(job):
    """Check if a job belongs to AniHermes.

    Args:
        job: Job dict

    Returns:
        bool: True if job name starts with "AniHermes:"
    """
    name = job.get("name", "")
    return name.startswith(ANIHERMES_PREFIX)


def list_jobs(show_all=False):
    """List CRON jobs in formatted output.

    Args:
        show_all: If True, show all Hermes jobs; if False, only AniHermes jobs

    Returns:
        int: Exit code (0 success, 1 error)
    """
    jobs = load_jobs()

    if jobs is None:
        print(f"No CRON jobs found ({CRON_FILE} does not exist or is invalid)")
        return 0

    if not jobs:
        print("No CRON jobs configured.")
        return 0

    # Filter jobs
    if show_all:
        filtered = jobs
        header = "Hermes CRON Jobs (all):"
    else:
        filtered = [j for j in jobs if is_anihermes_job(j)]
        header = "Tracked Series (AniHermes CRON Jobs):"

    if not filtered:
        if show_all:
            print("No CRON jobs found.")
        else:
            print("No AniHermes tracking jobs found.")
            print("Use --all to see all Hermes CRON jobs.")
        return 0

    print(header)

    for job in filtered:
        status = get_job_status(job)

        if is_anihermes_job(job):
            # Clean display name for AniHermes jobs
            display_name = extract_series_name(job.get("name", ""))
        else:
            # Show full name for non-AniHermes jobs
            display_name = job.get("name") or job.get("job_id", "Unnamed")

        schedule = job.get("schedule", "?")
        next_run = format_timestamp(job.get("next_run_at"))

        print(f"  [{status}] {display_name}")
        print(f"    Schedule: {schedule} | Next: {next_run}")

    print()
    print(f"{len(filtered)} job(s) total")
    return 0


def show_job(identifier):
    """Show detailed info for a specific job.

    Args:
        identifier: Job ID or name (partial match supported)

    Returns:
        int: Exit code (0 success, 1 not found)
    """
    jobs = load_jobs()

    if jobs is None:
        print(f"ERROR: Cannot read CRON jobs ({CRON_FILE})")
        return 1

    if not jobs:
        print("No CRON jobs found.")
        return 1

    # Find matching job (by ID or name, case-insensitive partial match)
    identifier_lower = identifier.lower()
    match = None

    for job in jobs:
        job_id = job.get("job_id", "")
        name = job.get("name", "")

        # Exact ID match
        if job_id == identifier:
            match = job
            break

        # Partial name match (case-insensitive)
        if identifier_lower in name.lower():
            match = job
            break

        # Also check without "AniHermes: " prefix
        series = extract_series_name(name)
        if identifier_lower in series.lower():
            match = job
            break

    if not match:
        print(f"No job found matching '{identifier}'")
        print("Use 'list --all' to see all available jobs.")
        return 1

    # Display detailed info
    name = match.get("name") or "Unnamed"
    job_id = match.get("job_id", "N/A")
    schedule = match.get("schedule", "N/A")
    next_run = format_timestamp(match.get("next_run_at"))
    status = get_job_status(match)
    repeat = match.get("repeat")
    skills = match.get("skills", [])
    prompt = match.get("prompt", "")

    print(f"Job: {name}")
    print(f"  ID: {job_id}")
    print(f"  Schedule: {schedule}")
    print(f"  Next run: {next_run}")
    print(f"  Status: {status}")

    if repeat is not None:
        print(f"  Repeat count: {repeat}")

    if skills:
        print(f"  Skills: {', '.join(skills)}")

    if prompt:
        print()
        print("  Prompt:")
        # Indent multi-line prompts
        for line in prompt.strip().split("\n"):
            print(f"    {line}")

    return 0


def main():
    parser = argparse.ArgumentParser(
        description="AniHermes CRON Job Viewer",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""Examples:
  %(prog)s list              Show AniHermes tracking jobs
  %(prog)s list --all        Show all Hermes CRON jobs
  %(prog)s show Frieren      Show details for Frieren tracking job
  %(prog)s show abc123       Show job by ID""",
    )

    sub = parser.add_subparsers(dest="command")

    # list subcommand
    list_p = sub.add_parser("list", help="List CRON jobs")
    list_p.add_argument(
        "--all", "-a", action="store_true", help="Show all Hermes jobs, not just AniHermes"
    )

    # show subcommand
    show_p = sub.add_parser("show", help="Show detailed info for a job")
    show_p.add_argument("job", help="Job ID or name (partial match supported)")

    args = parser.parse_args()

    if not args.command:
        # Default to list (AniHermes only)
        return list_jobs(show_all=False)

    if args.command == "list":
        return list_jobs(show_all=args.all)

    elif args.command == "show":
        return show_job(args.job)

    return 0


if __name__ == "__main__":
    sys.exit(main())
