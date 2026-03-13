# Telegram Bot Setup

AniHermes can be controlled from Telegram via Hermes Agent's built-in Telegram integration.

## Step 1: Create a Telegram Bot

1. Open Telegram and search for **@BotFather**
2. Send `/newbot`
3. Choose a name (e.g., "AniHermes")
4. Choose a username (e.g., `anihermes_bot`)
5. BotFather gives you an **API token** — save it

## Step 2: Configure Hermes for Telegram

Hermes Agent handles Telegram integration natively. Follow the Hermes docs to connect your bot token to the Hermes gateway:

```bash
# In your Hermes config, add the Telegram bot token
# See: https://github.com/NousResearch/hermes-agent for gateway setup
```

## Step 3: Start Using It

Once connected, send messages to your bot:

| Message | What Happens |
|---------|--------------|
| "Download latest Frieren" | Searches SubsPlease → downloads via qbittorrent |
| "Track One Piece weekly" | Creates CRON job for auto-downloads |
| "What's in my library?" | Lists your anime collection |
| "Sync my Anilist" | Imports watchlist, creates missing trackers |
| Send a screenshot | Identifies the anime, offers to download |
| "What's airing today?" | Shows today's release schedule for your watchlist |
| "I dropped Series X" | Removes CRON, updates Anilist, offers to delete files |

## Tips

- **Notifications**: CRON jobs will send download confirmations to Telegram via `send_message`
- **Daily digest**: Ask Hermes to "Set up daily anime schedule" — you'll get a morning digest of today's releases
- **Screenshots**: Send any anime screenshot and Hermes will use `vision_analyze` to identify it
- **Group chats**: The bot works in group chats too — just mention it or reply to its messages

## Troubleshooting

### Bot doesn't respond
- Ensure the Hermes gateway is running
- Check that the bot token is correctly configured in Hermes
- Verify the bot is not blocked or deactivated

### Notifications not arriving
- Check `notifications.platform` is set to `telegram` in config.yaml
- Ensure CRON jobs are active: ask Hermes to "list my tracked anime"
