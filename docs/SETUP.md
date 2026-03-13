# AniHermes Setup Guide

## Prerequisites

1. **Hermes Agent** — Install from [github.com/NousResearch/hermes-agent](https://github.com/NousResearch/hermes-agent)
2. **Python 3.8+** — All scripts use stdlib only, no pip packages needed
3. **qbittorrent** with WebUI enabled

### Installing qbittorrent

| Platform | Command |
|----------|---------|
| Arch Linux | `sudo pacman -S qbittorrent` |
| Ubuntu/Debian | `sudo apt install qbittorrent` |
| macOS | `brew install --cask qbittorrent` |
| Other | [qbittorrent.org/download](https://www.qbittorrent.org/download) |

### Enabling qbittorrent WebUI

1. Open qbittorrent
2. Go to **Tools → Options → Web UI**
3. Check **"Web User Interface (Remote Control)"**
4. Set port (default: `8081`)
5. Set username and password
6. Click OK

Verify it works: open `http://localhost:8081` in your browser.

## Installation

```bash
git clone https://github.com/YOUR_USERNAME/anihermes.git
cd anihermes
./install.sh
```

The installer will prompt you for:

| Setting | Default | Description |
|---------|---------|-------------|
| Anime storage path | `~/Anime` | Where episodes are saved |
| qbittorrent WebUI URL | `http://localhost:8081` | qbittorrent API endpoint |
| Preferred quality | `1080p` | 480p, 720p, or 1080p |
| Anilist username | (empty) | For watchlist sync (optional) |
| qbittorrent username | `admin` | WebUI credentials |
| qbittorrent password | `adminadmin` | WebUI credentials |
| Anilist OAuth token | (empty) | For write access (optional) |

## What Gets Installed

| File | Location |
|------|----------|
| Config | `~/.hermes/anihermes/config.yaml` |
| Scripts | `~/.hermes/scripts/anihermes_*.py` |
| Skill | `~/.hermes/skills/media/anime-media-server/SKILL.md` |
| Secrets | `~/.hermes/.env` (appended) |

## Post-Install Verification

```bash
# Test SubsPlease search
python3 ~/.hermes/scripts/anihermes_subsplease.py search "Frieren"

# Test Anilist search
python3 ~/.hermes/scripts/anihermes_anilist_api.py search "Frieren"

# Test library scan
python3 ~/.hermes/scripts/anihermes_library_manager.py stats

# Test via Hermes
hermes "What anime is airing today?"
```

## Configuration Reference

Config file: `~/.hermes/anihermes/config.yaml`

```yaml
storage:
  anime_path: ~/Anime           # Where episodes are stored
  organize_by: series/season     # Folder structure

torrent:
  client: qbittorrent            # Only qbittorrent supported
  webui_url: http://localhost:8081

sources:
  preferred: subsplease          # Primary source
  fallbacks:
    - nyaa                       # Searched via delegate_task
  quality: 1080p                 # Default quality

anilist:
  username: ""                   # Public watchlist access

notifications:
  platform: telegram             # Where to send alerts
```

### Environment Variables (Secrets)

Set in `~/.hermes/.env`:

| Variable | Description |
|----------|-------------|
| `QBIT_USERNAME` | qbittorrent WebUI username |
| `QBIT_PASSWORD` | qbittorrent WebUI password |
| `ANILIST_OAUTH_TOKEN` | Anilist OAuth token (optional) |

## Troubleshooting

### "Config not found"
Run `./install.sh` again, or manually copy `config.example.yaml` to `~/.hermes/anihermes/config.yaml`.

### "Cannot connect to qbittorrent"
- Ensure qbittorrent is running with WebUI enabled
- Check the URL and port in config.yaml match your qbittorrent settings
- Verify credentials in `~/.hermes/.env`

### "No results found" on SubsPlease
- SubsPlease only hosts currently-airing shows
- For older/completed series, use: `hermes "Find {series} from multiple sources"`

### Scripts fail with import error
Ensure `config.py` exists in `~/.hermes/scripts/`. Re-run `./install.sh` if needed.

## Uninstall

```bash
rm -rf ~/.hermes/anihermes/
rm -rf ~/.hermes/skills/media/anime-media-server/
rm ~/.hermes/scripts/anihermes_*.py
# Remove AniHermes lines from ~/.hermes/.env manually
```
