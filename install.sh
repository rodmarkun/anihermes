#!/bin/bash
# AniHermes Installer
# Sets up AniHermes for use with Hermes Agent

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
HERMES_DIR="${HOME}/.hermes"
ANIHERMES_DIR="${HERMES_DIR}/anihermes"
SKILLS_DIR="${HERMES_DIR}/skills/media/anihermes"
SCRIPTS_DIR="${HERMES_DIR}/scripts"
SKINS_DIR="${HERMES_DIR}/skins"
OLD_SKILL_DIR="${HERMES_DIR}/skills/media/anime-server-workflow"

echo "========================================"
echo "  AniHermes Installer"
echo "  Natural Language Anime Media Server"
echo "========================================"
echo ""

# Check if hermes is installed
if ! command -v hermes &>/dev/null; then
    echo "ERROR: Hermes Agent not found."
    echo "Install it from: https://github.com/NousResearch/hermes-agent"
    echo "Then run this installer again."
    exit 1
fi
echo "[OK] Hermes Agent found"

# Check Python 3
if ! command -v python3 &>/dev/null; then
    echo "ERROR: Python 3 not found. Please install Python 3.8+."
    exit 1
fi
echo "[OK] Python 3 found"

# Check qbittorrent
if command -v qbittorrent &>/dev/null || [ -f "${HOME}/.local/bin/qbittorrent.AppImage" ]; then
    echo "[OK] qbittorrent found"
else
    echo "[WARN] qbittorrent not found. Install it for torrent downloads."
    echo "  Arch: sudo pacman -S qbittorrent"
    echo "  Ubuntu: sudo apt install qbittorrent"
    echo "  Or download AppImage from https://www.qbittorrent.org/download"
fi

echo ""
echo "--- Configuration ---"
echo ""

# Anime storage path
read -rp "Anime storage path [~/Anime]: " anime_path
anime_path="${anime_path:-${HOME}/Anime}"
anime_path="${anime_path/#\~/$HOME}"

# Create path if it doesn't exist
if [ ! -d "$anime_path" ]; then
    read -rp "Directory '$anime_path' doesn't exist. Create it? [Y/n]: " create_dir
    if [ "${create_dir,,}" != "n" ]; then
        mkdir -p "$anime_path"
        echo "Created: $anime_path"
    fi
fi

# qbittorrent WebUI URL
read -rp "qbittorrent WebUI URL [http://localhost:8081]: " qbit_url
qbit_url="${qbit_url:-http://localhost:8081}"

# Quality preference
echo "Quality options: 480p, 720p, 1080p"
read -rp "Preferred quality [1080p]: " quality
quality="${quality:-1080p}"

# Anime tracker choice
echo ""
echo "Which anime tracker do you use?"
echo "  1) Anilist (anilist.co)"
echo "  2) MyAnimeList (myanimelist.net)"
echo "  3) Both"
echo "  4) Neither"
read -rp "Choice [1]: " tracker_choice
tracker_choice="${tracker_choice:-1}"

tracker=""
anilist_user=""
anilist_token=""
mal_user=""
mal_client_id=""
mal_token=""

if [ "$tracker_choice" = "1" ] || [ "$tracker_choice" = "3" ]; then
    tracker="anilist"
    read -rp "Anilist username (for watchlist sync): " anilist_user

    echo ""
    echo "=== Anilist OAuth Setup (for updating progress) ==="
    echo ""
    echo "To update your watch progress from AniHermes, you need an OAuth token."
    echo ""
    echo "Step 1: Create an API client at https://anilist.co/settings/developer"
    echo "  - Click 'Create New Client'"
    echo "  - Name: AniHermes (or anything)"
    echo "  - Redirect URL: https://anilist.co/api/v2/oauth/pin  <-- IMPORTANT!"
    echo "  - Save and note your Client ID"
    echo ""
    read -rp "Enter your Anilist Client ID (or press Enter to skip OAuth): " anilist_client_id

    if [ -n "$anilist_client_id" ]; then
        echo ""
        echo "Step 2: Authorize the app"
        echo "  Open this URL in your browser:"
        echo ""
        echo "  https://anilist.co/api/v2/oauth/authorize?client_id=${anilist_client_id}&response_type=token"
        echo ""
        echo "Step 3: After clicking 'Authorize', you'll be redirected to a URL like:"
        echo "  https://anilist.co/api/v2/oauth/pin#access_token=eyJ...LONG_TOKEN...&token_type=Bearer"
        echo ""
        echo "  Copy the ENTIRE access_token value (starts with 'eyJ', ~1000 chars long)"
        echo ""
        read -rsp "Paste your token here (or Enter to skip): " anilist_token
        echo ""

        # Validate token format
        if [ -n "$anilist_token" ]; then
            if [[ ! "$anilist_token" =~ ^eyJ ]]; then
                echo "[WARN] Token doesn't look like a JWT (should start with 'eyJ')"
                echo "       You may have copied the wrong value. Update later in ~/.hermes/.env"
            elif [ ${#anilist_token} -lt 100 ]; then
                echo "[WARN] Token seems too short (${#anilist_token} chars, expected ~1000)"
                echo "       Make sure you copied the entire access_token value"
            else
                echo "[OK] Token looks valid (${#anilist_token} chars)"
            fi
        fi
    fi
fi

if [ "$tracker_choice" = "2" ] || [ "$tracker_choice" = "3" ]; then
    if [ -z "$tracker" ]; then
        tracker="mal"
    fi
    read -rp "MAL username (for watchlist sync): " mal_user

    echo ""
    echo "=== MyAnimeList API Setup ==="
    echo ""
    echo "MAL requires a Client ID for API access (even read-only)."
    echo ""
    echo "Step 1: Create an API client at https://myanimelist.net/apiconfig"
    echo "  - Click 'Create ID'"
    echo "  - App Type: 'other'"
    echo "  - App Redirect URL: http://localhost"
    echo "  - Save and copy your Client ID"
    echo ""
    read -rp "MAL Client ID: " mal_client_id

    if [ -n "$mal_client_id" ]; then
        echo ""
        echo "Step 2: Get an OAuth token (for updating progress)"
        echo ""
        echo "MAL uses PKCE OAuth. Here's how to get your token:"
        echo ""
        # Generate a random code verifier (43-128 chars, alphanumeric)
        code_verifier=$(head -c 64 /dev/urandom | base64 | tr -dc 'a-zA-Z0-9' | head -c 64)
        echo "  Your code verifier (save this!): $code_verifier"
        echo ""
        echo "  Open this URL in your browser:"
        echo ""
        echo "  https://myanimelist.net/v1/oauth2/authorize?response_type=code&client_id=${mal_client_id}&code_challenge=${code_verifier}&code_challenge_method=plain"
        echo ""
        echo "Step 3: After clicking 'Allow', you'll be redirected to:"
        echo "  http://localhost?code=AUTHORIZATION_CODE"
        echo ""
        echo "  Copy the 'code' value from the URL (everything after 'code=')"
        echo ""
        read -rp "Paste the authorization code here (or Enter to skip): " auth_code

        if [ -n "$auth_code" ]; then
            echo ""
            echo "Exchanging code for access token..."
            # Exchange the code for a token
            token_response=$(curl -s -X POST "https://myanimelist.net/v1/oauth2/token" \
                -H "Content-Type: application/x-www-form-urlencoded" \
                -d "client_id=${mal_client_id}&grant_type=authorization_code&code=${auth_code}&code_verifier=${code_verifier}" 2>/dev/null)

            # Extract access_token from JSON response
            mal_token=$(echo "$token_response" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('access_token',''))" 2>/dev/null)

            if [ -n "$mal_token" ]; then
                echo "[OK] Got MAL access token (${#mal_token} chars)"
            else
                error_msg=$(echo "$token_response" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('error','unknown error'))" 2>/dev/null)
                echo "[ERROR] Failed to get token: $error_msg"
                echo "        You can retry later or update ~/.hermes/.env manually"
                mal_token=""
            fi
        else
            echo ""
            echo "(Skipping OAuth - read-only access works with just the Client ID)"
        fi
    fi
fi

if [ "$tracker_choice" = "3" ]; then
    echo ""
    echo "Which tracker should be the primary (used for sync/progress)?"
    echo "  1) Anilist"
    echo "  2) MyAnimeList"
    read -rp "Primary tracker [1]: " primary_choice
    primary_choice="${primary_choice:-1}"
    if [ "$primary_choice" = "2" ]; then
        tracker="mal"
    else
        tracker="anilist"
    fi
fi

echo ""
echo "--- Secrets (stored in ~/.hermes/.env, never committed) ---"
echo ""

# qbittorrent credentials
read -rp "qbittorrent username [admin]: " qbit_user
qbit_user="${qbit_user:-admin}"
read -rsp "qbittorrent password [adminadmin]: " qbit_pass
qbit_pass="${qbit_pass:-adminadmin}"
echo ""

echo ""
echo "--- Installing ---"
echo ""

# Create directories
mkdir -p "$ANIHERMES_DIR"
mkdir -p "$SKILLS_DIR/references"
mkdir -p "$SCRIPTS_DIR"
mkdir -p "$SKINS_DIR"

# Generate config.yaml
cat > "${ANIHERMES_DIR}/config.yaml" <<EOF
# AniHermes Configuration (generated by install.sh)
storage:
  anime_path: ${anime_path}
  organize_by: series/season

torrent:
  client: qbittorrent
  webui_url: ${qbit_url}

sources:
  preferred: subsplease
  fallbacks:
    - nyaa
  quality: ${quality}

server:
  port: 8888
  bind: 0.0.0.0

tracker: ${tracker:-anilist}

anilist:
  username: "${anilist_user}"

mal:
  username: "${mal_user}"
  client_id: "${mal_client_id}"

notifications:
  platform: telegram
EOF
echo "[OK] Config written to ${ANIHERMES_DIR}/config.yaml"

# Build secrets block
secrets="# AniHermes secrets
QBIT_USERNAME=${qbit_user}
QBIT_PASSWORD=${qbit_pass}"

if [ -n "$anilist_token" ]; then
    secrets="${secrets}
ANILIST_OAUTH_TOKEN=${anilist_token}"
fi

if [ -n "$mal_client_id" ]; then
    secrets="${secrets}
MAL_CLIENT_ID=${mal_client_id}"
fi

if [ -n "$mal_token" ]; then
    secrets="${secrets}
MAL_OAUTH_TOKEN=${mal_token}"
fi

# Upsert secrets into .env (update existing, append new)
ENV_FILE="${HERMES_DIR}/.env"
touch "$ENV_FILE"
chmod 600 "$ENV_FILE"

upsert_env() {
    local key="$1" value="$2" file="$3"
    if grep -q "^${key}=" "$file" 2>/dev/null; then
        sed -i '' "s|^${key}=.*|${key}=${value}|" "$file"
    else
        echo "${key}=${value}" >> "$file"
    fi
}

upsert_env "QBIT_USERNAME" "$qbit_user" "$ENV_FILE"
upsert_env "QBIT_PASSWORD" "$qbit_pass" "$ENV_FILE"
[ -n "$anilist_token" ] && upsert_env "ANILIST_OAUTH_TOKEN" "$anilist_token" "$ENV_FILE"
[ -n "$mal_client_id" ] && upsert_env "MAL_CLIENT_ID" "$mal_client_id" "$ENV_FILE"
[ -n "$mal_token" ] && upsert_env "MAL_OAUTH_TOKEN" "$mal_token" "$ENV_FILE"
echo "[OK] Secrets updated in ${ENV_FILE}"

# Remove old skill if present (upgrade from anime-server-workflow)
if [ -d "$OLD_SKILL_DIR" ]; then
    echo "[INFO] Removing old anime-server-workflow skill..."
    rm -rf "$OLD_SKILL_DIR"
fi

# Copy scripts (all use Python stdlib only — no pip install needed)
for script in add_torrent.py anilist_api.py mal_api.py subsplease.py nyaa.py library_manager.py media_server.py cronjobs.py; do
    cp "${SCRIPT_DIR}/scripts/${script}" "${SCRIPTS_DIR}/anihermes_${script}"
done
# config.py must be importable by all scripts — install without prefix
cp "${SCRIPT_DIR}/scripts/config.py" "${SCRIPTS_DIR}/config.py"
# Also install with prefix so Hermes can call it directly as a CLI tool
cp "${SCRIPT_DIR}/scripts/config.py" "${SCRIPTS_DIR}/anihermes_config.py"
echo "[OK] Scripts installed to ${SCRIPTS_DIR}/"

# Install skill + references
cp "${SCRIPT_DIR}/skills/anihermes/SKILL.md" "${SKILLS_DIR}/SKILL.md"
cp "${SCRIPT_DIR}/skills/anihermes/references/"*.md "${SKILLS_DIR}/references/"
echo "[OK] Skill installed to ${SKILLS_DIR}/"

# Install skin
cp "${SCRIPT_DIR}/skins/anihermes.yaml" "${SKINS_DIR}/anihermes.yaml"
echo "[OK] Skin installed to ${SKINS_DIR}/"

# Auto-allowlist AniHermes scripts in Hermes config
HERMES_CONFIG="${HERMES_DIR}/config.yaml"
if [ -f "$HERMES_CONFIG" ]; then
    if ! grep -q "anihermes_" "$HERMES_CONFIG" 2>/dev/null; then
        echo ""
        echo "Hermes will ask permission every time it runs AniHermes scripts."
        read -rp "Auto-allowlist AniHermes commands? (no more permission prompts) [Y/n]: " allowlist_choice
        if [ "${allowlist_choice,,}" != "n" ]; then
            # Replace empty allowlist or append to existing one
            if grep -q "command_allowlist: \[\]" "$HERMES_CONFIG" 2>/dev/null; then
                sed -i 's/command_allowlist: \[\]/command_allowlist:\n- "python3 ~\/.hermes\/scripts\/anihermes_*"\n- "python3 -c \\"from config import*"\n- "cd ~\/.hermes\/scripts*"/' "$HERMES_CONFIG"
            elif grep -q "command_allowlist:" "$HERMES_CONFIG" 2>/dev/null; then
                sed -i '/command_allowlist:/a - "python3 ~\/.hermes\/scripts\/anihermes_*"\n- "python3 -c \\"from config import*"\n- "cd ~\/.hermes\/scripts*"' "$HERMES_CONFIG"
            fi
            echo "[OK] AniHermes commands allowlisted (no permission prompts)"
        else
            echo "[SKIP] You'll be prompted each time Hermes runs a script"
        fi
    else
        echo "[SKIP] AniHermes commands already allowlisted"
    fi
fi

# Offer to enable the skin
echo ""
read -rp "Enable the AniHermes skin now? (You can always do so with /skin anihermes) [Y/n]: " enable_skin
if [ "${enable_skin,,}" != "n" ]; then
    hermes "/skin anihermes" 2>/dev/null && echo "[OK] AniHermes skin enabled" || echo "[SKIP] Could not enable skin (enable manually with: /skin anihermes)"
fi

echo ""
echo "========================================"
echo "  AniHermes installed successfully!"
echo "========================================"
echo ""
echo "Try it out:"
echo "  hermes 'What anime do I have in my library?'"
echo "  hermes 'Search for Frieren on SubsPlease'"
echo "  hermes 'Download the latest episode of Frieren'"
echo ""
echo "From Telegram (if configured):"
echo "  'Track One Piece weekly'"
if [ -n "$anilist_user" ]; then
    echo "  'Sync my Anilist watchlist'"
fi
if [ -n "$mal_user" ]; then
    echo "  'Sync my MAL watchlist'"
fi
echo ""
echo "Skin: /skin anihermes"
echo ""
