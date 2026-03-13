# AniHermes

**Natural Language Anime Media Server** powered by [Hermes Agent](https://github.com/NousResearch/hermes-agent).

Talk to your anime server like it's a person — download episodes, track series, sync with Anilist, identify anime from screenshots, and manage your library. All through natural language, from Telegram, Discord, or CLI.

<!-- TODO: Add demo video/GIF here
[![Demo](docs/assets/demo-thumbnail.png)](https://youtube.com/watch?v=YOUR_VIDEO_ID)
-->

## What It Does

| Command | Result |
|---------|--------|
| "Download the latest Frieren" | Searches SubsPlease, grabs magnet, downloads via qbittorrent, organizes on disk |
| "Track One Piece weekly" | Creates a CRON job that auto-downloads new episodes |
| "Sync my Anilist" | Imports your watchlist, auto-tracks untracked series |
| "What anime is this?" + screenshot | Identifies anime using vision, offers to download |
| "Find this on multiple sources" | Parallel subagent search across SubsPlease & Nyaa |
| "What's in my library?" | Organized view of your collection with disk stats |
| "I dropped Series X" | Removes CRON, updates Anilist, optionally cleans files |
| "Recommend anime like Frieren" | Anilist-powered recommendations |

## Why Hermes Agent?

This isn't a script with a chatbot wrapper. Each feature uses Hermes Agent capabilities that can't be replicated with simple automation:

| Feature | Hermes Capability |
|---------|-------------------|
| Natural language commands | LLM understanding + tool orchestration |
| Multi-source download | `delegate_task` — parallel subagent searches |
| Anime identification | `vision_analyze` — image understanding |
| Auto-tracking | `schedule_cronjob` — NL-defined CRON jobs |
| Cross-platform | `send_message` — Telegram, Discord, CLI |
| Taste learning | `memory` — persistent preferences |
| Self-improving | Skills system — workflows improve over time |

## Quick Start

```bash
# 1. Install Hermes Agent (if you haven't)
# See: https://github.com/NousResearch/hermes-agent

# 2. Clone and install AniHermes
git clone https://github.com/YOUR_USERNAME/anihermes.git
cd anihermes
./install.sh

# 3. Start using it
hermes "What anime is airing this season?"
hermes "Download the latest episode of Frieren"
```

## Requirements

- [Hermes Agent](https://github.com/NousResearch/hermes-agent)
- Python 3.8+ (stdlib only, no pip packages needed)
- [qbittorrent](https://www.qbittorrent.org/) with WebUI enabled
- Storage for anime (any directory)

### Optional

- Telegram bot (for mobile access) — [setup guide](docs/TELEGRAM.md)
- Anilist account (for watchlist sync) — [setup guide](docs/ANILIST.md)

## Configuration

`install.sh` creates `~/.hermes/anihermes/config.yaml`:

```yaml
storage:
  anime_path: ~/Anime

torrent:
  client: qbittorrent
  webui_url: http://localhost:8081

sources:
  preferred: subsplease
  fallbacks: [nyaa]
  quality: 1080p

anilist:
  username: "your_username"
```

Secrets (qbittorrent password, Anilist OAuth token) are stored in `~/.hermes/.env`, never in config files.

See [docs/SETUP.md](docs/SETUP.md) for full configuration reference.

## Architecture

```
User (Telegram/CLI/Discord)
    |
    v
Hermes Agent (NL understanding + tool orchestration)
    |
    |-- web_search / web_extract --> SubsPlease, Nyaa
    |-- delegate_task -------------> Parallel source searches
    |-- vision_analyze ------------> Anime scene identification
    |-- terminal ------------------> scripts/*.py (config-driven)
    |-- schedule_cronjob ----------> Weekly episode checks
    |-- memory --------------------> User preferences
    |-- send_message --------------> Notifications
         |
         v
    qbittorrent --> Your anime library
    Anilist API --> Watch progress tracking
```

## Scripts

All scripts are standalone and can be used independently:

```bash
# Search SubsPlease
python3 ~/.hermes/scripts/anihermes_subsplease.py search "Frieren"
python3 ~/.hermes/scripts/anihermes_subsplease.py latest "Frieren"
python3 ~/.hermes/scripts/anihermes_subsplease.py schedule

# Search Anilist
python3 ~/.hermes/scripts/anihermes_anilist_api.py search "Frieren"
python3 ~/.hermes/scripts/anihermes_anilist_api.py watchlist your_username
python3 ~/.hermes/scripts/anihermes_anilist_api.py recommendations 154587

# Manage library
python3 ~/.hermes/scripts/anihermes_library_manager.py list
python3 ~/.hermes/scripts/anihermes_library_manager.py stats
python3 ~/.hermes/scripts/anihermes_library_manager.py info "Frieren"

# Download torrent
python3 ~/.hermes/scripts/anihermes_add_torrent.py --series "Frieren" --season "S2" --magnet "magnet:..."
```

## Documentation

- [Setup Guide](docs/SETUP.md) — Detailed installation and configuration
- [Telegram Setup](docs/TELEGRAM.md) — Telegram bot integration
- [Anilist Setup](docs/ANILIST.md) — Anilist OAuth and watchlist sync

## License

MIT
