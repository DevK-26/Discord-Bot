# 🔮 CodeSensei

> Your **friendly coding mentor** Discord bot. Quiz your community with MCQs,
> share dev resources, and reward learning with **aura** ✨.

CodeSensei is a gamified learning bot for coding/study communities. Members
answer multiple-choice questions to earn **aura**, climb the leaderboard, and
discover hand-picked developer resources — all wrapped in clean, colorful embeds.

---

## 🆕 What's new (Tier 1)

- ⚡ **Slash commands** — every command now works as `/ask` **and** the legacy `!ask` (hybrid). Includes **category autocomplete**.
- 🔘 **Interactive answer buttons** — questions come with clickable **A / B / C / D** buttons; your result is shown **privately (ephemeral)** so nobody sees if you were right. Buttons disable on a timer and reveal the answer.
- 🧩 **Cog architecture** — the bot is split into `cogs/` (`quiz`, `resources`, `profile`, `admin`, `events`) for maintainability.
- 📝 **Real logging** — console + rotating `bot.log` file, level from `LOGGING_LEVEL`.
- 🧪 **Tests + migrations** — a `pytest` suite for the pure logic and a non-destructive `migrate.py`.

> **Upgrading an existing install?** Run `python migrate.py` once before launching. Tier 1 changes no schema, so your `app.db` and all data are preserved.

---

## ✨ Features

- 🧠 **MCQ quiz system** — A/B/C/D questions with categories, difficulty, and point values, answered via buttons.
- 📚 **Resource library** — save and randomly fetch dev resources (title, URL, category, tags, upvotes).
- 🔮 **Points / gamification** — earn **aura** for correct answers; tracks correct vs. total and accuracy. One scored attempt per question (no farming).
- 🪪 **Profiles** — rich embed with avatar, aura, correct count, and accuracy.
- 🏆 **Leaderboard** — top 10 learners with 🥇🥈🥉 medals.
- 🗂️ **Categories listing** — all distinct quiz + resource categories.
- 👋 **Mention responder** — @mention the bot for a friendly mentor reply.
- 🎨 **Rich embeds** everywhere, color-coded by purpose.
- 🛡️ **Global error handling** for both prefix and slash commands, ephemeral where it keeps channels clean.
- 🥚 **Easter egg** — one configured user always gets the right answer + bonus aura.

---

## 🧰 Tech stack

- Python 3.10+
- [discord.py](https://discordpy.readthedocs.io/) 2.x (`discord.ext.commands`)
- [SQLAlchemy](https://www.sqlalchemy.org/) 2.x ORM
- SQLite by default (swap to PostgreSQL via the `DB_URL` env var — no code changes)
- [python-dotenv](https://pypi.org/project/python-dotenv/) for config

---

## 🛠️ Setup — Discord Developer Portal

1. Go to the [Discord Developer Portal](https://discord.com/developers/applications) and click **New Application**. Name it `CodeSensei`.
2. Open the **Bot** tab → **Add Bot**.
3. Under **Privileged Gateway Intents**, enable both:
   - ✅ **Message Content Intent**
   - ✅ **Server Members Intent**
4. Click **Reset Token** → **Copy** the token. You'll paste it into `.env` next.
5. Open **OAuth2 → URL Generator**:
   - **Scopes:** `bot` **and** `applications.commands`  ← the second one is required for slash commands!
   - **Bot Permissions:** `Send Messages`, `Read Message History`, `Embed Links`, `View Channels`
6. Copy the generated URL, open it in your browser, and **invite the bot** to your server.

> **Tip:** For instant slash-command updates while developing, set `GUILD_ID` in `.env` to your test
> server's ID (enable Developer Mode → right-click the server icon → **Copy Server ID**). Leave it
> blank to sync globally, which works everywhere but can take up to ~1 hour to propagate.

---

## 🚀 Setup — Run the bot

```bash
# 1. Create and activate a virtual environment
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate

# 2. Install dependencies
pip install -r requirements.txt

# 3. Configure your secrets
cp .env.example .env
#    -> open .env and paste your DISCORD_TOKEN

# 4. Initialize / migrate the database
python admin.py init        # first-time setup
python migrate.py           # safe to run anytime; upgrades an existing app.db

# 5. (Optional) Add sample questions + resources
python seed.py

# 6. (Optional) Run the tests
pytest

# 7. Launch!
python main.py
```

When it's running you'll see `🚀 Starting CodeSensei...`, a "Loaded cog" line per cog, and a
"Synced N slash command(s)" line. Logs also stream to `bot.log`.

---

## 💬 Command reference

Every command works as a **slash command** (`/ask`) *or* with the `!` prefix (`!ask`).

| Command | Args | Behavior |
|---|---|---|
| `/help` | – | Embed listing all commands by section. |
| `/ask` | `[category]` | Random active question with **A/B/C/D buttons** (category autocomplete). |
| `/answer` | `<id> <A/B/C/D>` | Text fallback for the buttons; ephemeral result. |
| `/addquestion` | `title \| desc \| category \| A \| B \| C \| D \| correct` | Add a question (8 `\|`-separated fields). |
| `/resource` | `[category]` | Random resource, optionally by category (autocomplete). |
| `/addresource` | `title \| url \| category \| [description]` | Add a resource. |
| `/profile` | `[@user]` | Full profile embed with avatar. |
| `/aura` | `[@user]` | Quick one-line aura readout. |
| `/leaderboard` | – | Top 10 by aura. |
| `/categories` | – | All quiz + resource categories. |
| `!sync` | – | *(Owner only, prefix only)* Manually re-sync slash commands. |

**Answering:** run `/ask`, then click **A / B / C / D** under the question. Your ✅/❌ result is
shown only to you. After the timeout the buttons lock and the embed reveals the correct option.

**Examples**

```text
/ask Algorithms
/addquestion What is 1+1? | basic math | Math | 1 | 2 | 3 | 4 | B
/addresource MDN Web Docs | https://developer.mozilla.org | Frontend | The web reference
/profile @teammate
```

---

## 🧩 Project structure

```
codesensei/
├── main.py          # entry point
├── bot.py           # Bot subclass, logging, cog loading, slash sync
├── config.py        # env-backed Config (token, DB_URL, GUILD_ID, timeouts, ...)
├── db.py            # engine, sessions, helper fns
├── models.py        # SQLAlchemy models
├── utils.py         # embed builders + quiz helpers
├── views.py         # AnswerView (the A/B/C/D buttons)
├── seed.py          # sample questions + resources
├── migrate.py       # non-destructive DB migrations
├── admin.py         # offline CLI (init/stats/reset)
├── cogs/            # quiz, resources, profile, admin, events
└── tests/           # pytest suite for pure logic
```

---

## 🗄️ Database schema

| Model | Key fields |
|---|---|
| **User** | `discord_id` (unique), `username`, `points`, `correct_answers`, `total_answers`, `created_at` → relationship to **answers** |
| **Question** | `title`, `description`, `category`, `difficulty`, `option_a/b/c/d`, `correct_option` (A/B/C/D), `points`, `is_active`, `asked_by`, `created_at` → **answers** |
| **Answer** | `question_id` (FK), `user_id` (FK), `answer_text`, `is_correct`, `points_awarded`, `created_at` |
| **Resource** | `title`, `url`, `category`, `description?`, `tags?` (CSV), `added_by`, `upvotes`, `created_at` |

- On a correct answer: `points` and `correct_answers` increment; `total_answers` always increments.
- **Accuracy** = `correct / total × 100` (guarded against divide-by-zero).

---

## 🧪 Admin CLI

```bash
python admin.py init        # create tables
python admin.py stats       # counts + top users
python admin.py questions   # list questions
python admin.py resources   # list resources
python admin.py reset       # DROP everything (asks to confirm)
```

---

## 🐘 Switching to PostgreSQL

No code changes needed — just set `DB_URL` in `.env`:

```env
DB_URL=postgresql+psycopg://user:password@localhost:5432/codesensei
```

Then `pip install "psycopg[binary]"`, run `python admin.py init`, and you're done.

---

## 🥚 Easter egg

Set `EASTER_EGG_USER_ID` in `.env` (or `config.py`) to a Discord user ID. That
user's `!answer` will always be auto-corrected to the right option and they'll
earn a small bonus aura. Leave it blank to disable.

---

## 🎨 Customizing the personality

Open `config.py` and tweak `BOT_NAME`, `PREFIX`, `CURRENCY_NAME`, and
`CURRENCY_EMOJI`. The mentor's mention replies live in `MENTION_LINES` in
`utils.py`. Embed colors and footers are all in `utils.py` too.

Happy learning! 🔮
