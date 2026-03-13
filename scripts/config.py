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
    config["torrent"]["username"] = os.environ.get("QBIT_USERNAME", "admin")
    config["torrent"]["password"] = os.environ.get("QBIT_PASSWORD", "adminadmin")
    config["anilist"]["oauth_token"] = os.environ.get("ANILIST_OAUTH_TOKEN", "")
    config["mal"].setdefault("client_id", os.environ.get("MAL_CLIENT_ID", ""))
    config["mal"]["oauth_token"] = os.environ.get("MAL_OAUTH_TOKEN", "")

    return config
