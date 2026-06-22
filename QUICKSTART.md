# ⚡ CodeSensei — 5-Minute Quickstart

Get your friendly coding-mentor bot online fast.

### 1. Get a bot token (2 min)
1. Open the [Discord Developer Portal](https://discord.com/developers/applications) → **New Application** → name it `CodeSensei`.
2. **Bot** tab → enable **Message Content Intent** and **Server Members Intent**.
3. **Reset Token** → **Copy** it.

### 2. Invite it to your server (1 min)
- **OAuth2 → URL Generator** → scopes `bot` **and** `applications.commands` → permissions: *Send Messages, Read Message History, Embed Links, View Channels*.
- Open the generated URL → pick your server → **Authorize**.

### 3. Run it locally (2 min)
```bash
python -m venv venv && source venv/bin/activate   # Windows: venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env          # paste your token into DISCORD_TOKEN
#                              # (optional) set GUILD_ID=<your server id> for instant slash commands
python admin.py init          # create the database
python migrate.py             # upgrade an existing db (no-op on a fresh one)
python seed.py                # optional: load sample questions + resources
python main.py                # 🚀 go!
```

### 4. Try it in Discord
```text
/help
/ask            → then click an A/B/C/D button
/resource
/profile
/leaderboard
```
(Each also works with the `!` prefix, e.g. `!ask`.)

That's it — you're live! 🔮  For full details see **README.md**.
