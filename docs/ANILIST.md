# Anilist Integration Setup

AniHermes integrates with [Anilist](https://anilist.co) for anime tracking, watchlist sync, and recommendations.

## Read-Only Access (No Auth Required)

Just set your username in the config:

```yaml
anilist:
  username: "your_anilist_username"
```

This enables:
- Viewing your public watchlist
- Syncing tracked series with your Anilist "Watching" list
- Getting recommendations based on your list
- Searching anime info

## Write Access (OAuth Token Required)

To update episode progress and change anime status from AniHermes, you need an OAuth token.

### Step 1: Create an Anilist API Client

1. Go to [anilist.co/settings/developer](https://anilist.co/settings/developer)
2. Click **"Create New Client"**
3. Fill in:
   - **Name**: `AniHermes`
   - **Redirect URL**: `https://anilist.co/api/v2/oauth/pin`
4. Save — note your **Client ID**

### Step 2: Get Your Token

Open this URL in your browser (replace `YOUR_CLIENT_ID`):

```
https://anilist.co/api/v2/oauth/authorize?client_id=YOUR_CLIENT_ID&response_type=token
```

1. Log in to Anilist if prompted
2. Click **"Authorize"**
3. You'll be redirected — copy the **access token** from the URL fragment

### Step 3: Configure the Token

Add it to `~/.hermes/.env`:

```bash
ANILIST_OAUTH_TOKEN=your_token_here
```

Or set it during `./install.sh` when prompted.

## What You Can Do

| Feature | Read-Only | With OAuth |
|---------|-----------|------------|
| Search anime | Yes | Yes |
| View your watchlist | Yes | Yes |
| Get recommendations | Yes | Yes |
| Update episode progress | No | Yes |
| Change status (watching/dropped/completed) | No | Yes |
| Auto-update on download | No | Yes |

## Usage Examples

```bash
# Search (no auth needed)
hermes "Search Anilist for Frieren"

# View watchlist (username in config)
hermes "What am I watching on Anilist?"

# Sync watchlist to CRON jobs
hermes "Sync my Anilist"

# Update progress (needs OAuth)
hermes "I just watched episode 5 of Frieren"

# Drop a series (needs OAuth)
hermes "I dropped Series X"

# Get recommendations
hermes "Recommend anime like Frieren"
```

## API Rate Limits

Anilist allows ~90 requests per minute. Normal usage won't hit this limit. If you do, the scripts will show an error and you can retry after a minute.

## Troubleshooting

### "No watching entries for username"
- Ensure your Anilist list is set to **public** (Settings → Lists → Public)
- Double-check the username spelling in config.yaml

### "ANILIST_OAUTH_TOKEN not set"
- Add your token to `~/.hermes/.env`
- Tokens expire — regenerate if it stopped working

### "Anilist API returned 401"
- Your OAuth token has expired. Repeat Step 2 to get a new one.
