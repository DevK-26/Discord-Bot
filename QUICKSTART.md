# ⚡ CodeSensei — 5-Minute Quickstart

Get your friendly coding-mentor bot online fast.

### 1. Get a bot token (2 min)
1. Open the [Discord Developer Portal](https://discord.com/developers/applications) → **New Application** → name it `CodeSensei`.
2. **Bot** tab → enable **Message Content Intent** and **Server Members Intent**.
3. **Reset Token** → **Copy** it.

### 2. Invite it to your server (1 min)
- **OAuth2 → URL Generator** → scope `bot` → permissions: *Send Messages, Read Message History, Embed Links, View Channels*.
- Open the generated URL → pick your server → **Authorize**.

### 3. Run it locally (2 min)
```bash
python -m venv venv && source venv/bin/activate   # Windows: venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env          # then paste your token into DISCORD_TOKEN
python admin.py init          # create the database
python seed.py                # optional: load sample questions + resources
python main.py                # 🚀 go!
```

### 4. Try it in Discord
```text
!help
!ask
!answer 1 B
!resource
!profile
!leaderboard
```

That's it — you're live! 🔮  For full details see **README.md**.
