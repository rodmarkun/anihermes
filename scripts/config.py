"""
AniHermes configuration loader.
Reads non-sensitive settings from config.yaml, secrets from environment variables.
"""

import json
import os
import re

DEFAULT_CONFIG_PATH = os.path.expanduser("~/.hermes/anihermes/config.yaml")


def _parse_yaml_simple(text):
    """Minimal YAML parser for our flat config. Falls back to PyYAML if available."""
    try:
        import yaml
        return yaml.safe_load(text)
    except ImportError:
        pass

    # Simple parser for our known config structure
    result = {}
    current_section = None
    current_list_key = None

    for line in text.split("\n"):
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue

        # Remove inline comments
        stripped = re.sub(r'\s+#.*$', '', stripped)

        indent = len(line) - len(line.lstrip())

        if indent == 0 and stripped.endswith(":"):
            current_section = stripped[:-1]
            result[current_section] = {}
            current_list_key = None
        elif indent == 0 and ":" in stripped:
            # Top-level key: value (scalar, not a section)
            key, val = stripped.split(":", 1)
            key = key.strip()
            val = val.strip()
            if val.startswith('"') and val.endswith('"'):
                val = val[1:-1]
            elif val.startswith("'") and val.endswith("'"):
                val = val[1:-1]
            result[key] = val
            current_section = None
            current_list_key = None
        elif indent > 0 and current_section:
            if stripped.startswith("- "):
                # List item
                if current_list_key:
                    result[current_section][current_list_key].append(stripped[2:].strip())
            elif ":" in stripped:
                key, val = stripped.split(":", 1)
                key = key.strip()
                val = val.strip()
                if not val:
                    # Empty value might be start of a list
                    result[current_section][key] = []
                    current_list_key = key
                else:
                    current_list_key = None
                    # Remove quotes
                    if val.startswith('"') and val.endswith('"'):
                        val = val[1:-1]
                    elif val.startswith("'") and val.endswith("'"):
                        val = val[1:-1]
                    result[current_section][key] = val

    return result


def load_config(config_path=None):
    """Load configuration from YAML file and environment variables."""
    path = config_path or os.environ.get("ANIHERMES_CONFIG", DEFAULT_CONFIG_PATH)
    path = os.path.expanduser(path)

    if not os.path.exists(path):
        raise FileNotFoundError(
            f"Config not found at {path}. Run install.sh or copy config.example.yaml"
        )

    with open(path, "r") as f:
        config = _parse_yaml_simple(f.read())

    # Expand ~ in paths
    if "storage" in config and "anime_path" in config["storage"]:
        config["storage"]["anime_path"] = os.path.expanduser(
            config["storage"]["anime_path"]
        )

    # Ensure sections exist
    config.setdefault("torrent", {})
    config.setdefault("anilist", {})
    config.setdefault("mal", {})
    config.setdefault("sources", {})
    config.setdefault("notifications", {})

    # Inject secrets from environment (never stored in config.yaml)
    config["torrent"]["username"] = os.environ.get("QBIT_USERNAME", "")
    config["torrent"]["password"] = os.environ.get("QBIT_PASSWORD", "")
    config["anilist"]["oauth_token"] = os.environ.get("ANILIST_OAUTH_TOKEN", "")
    config["mal"]["client_id"] = os.environ.get("MAL_CLIENT_ID", "")
    config["mal"]["oauth_token"] = os.environ.get("MAL_OAUTH_TOKEN", "")

    return config


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="AniHermes config utility")
    sub = parser.add_subparsers(dest="command")
    sub.add_parser("show", help="Print loaded config as JSON (secrets redacted)")
    sub.add_parser("get", help="Get a single config value").add_argument("key", help="Dot-notation key, e.g. tracker, anilist.username, storage.anime_path")

    args = parser.parse_args()
    if not args.command:
        parser.print_help()
        raise SystemExit(1)

    cfg = load_config()

    if args.command == "show":
        # Redact secrets
        safe = json.loads(json.dumps(cfg, default=str))
        for section in ("torrent", "anilist", "mal"):
            if section in safe:
                for secret_key in ("password", "oauth_token"):
                    if safe[section].get(secret_key):
                        safe[section][secret_key] = "***"
        print(json.dumps(safe, indent=2))

    elif args.command == "get":
        parts = args.key.split(".")
        val = cfg
        for p in parts:
            if isinstance(val, dict):
                val = val.get(p)
            else:
                val = None
                break
        # Redact known secret keys
        secret_keys = {"password", "oauth_token"}
        if val is not None and len(parts) >= 2 and parts[-1] in secret_keys:
            print("***")
        elif val is not None:
            print(val if isinstance(val, str) else json.dumps(val))
        else:
            print(f"Key '{args.key}' not found", file=__import__("sys").stderr)
            raise SystemExit(1)
