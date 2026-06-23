"""
config.py
=========
Loads all runtime configuration from environment variables (via a .env file).

CodeSensei reads three values:
  - DISCORD_TOKEN : the secret bot token from the Discord Developer Portal
  - DB_URL        : SQLAlchemy database URL (SQLite by default, Postgres-swappable)
  - LOGGING_LEVEL : how chatty the logs are (DEBUG / INFO / WARNING / ...)

Keeping config in one small class means the rest of the code never has to touch
`os.environ` directly — it just imports `Config`.
"""

import os
import logging

from dotenv import load_dotenv

# Read the .env file (if present) and push its keys into the process environment.
# This is a no-op in production where real env vars are already set.
load_dotenv()


def _parse_level_roles(raw: str) -> dict[int, str]:
    """Parse 'LEVEL_ROLES' like '1:Novice,5:Adept' into {1: 'Novice', 5: 'Adept'}."""
    mapping: dict[int, str] = {}
    for pair in raw.split(","):
        pair = pair.strip()
        if not pair or ":" not in pair:
            continue
        lvl, _, name = pair.partition(":")
        try:
            mapping[int(lvl.strip())] = name.strip()
        except ValueError:
            continue
    return mapping


class Config:
    """Central, read-only configuration for the whole bot."""

    # The bot's display identity. Change these to re-skin the personality.
    BOT_NAME: str = "CodeSensei"
    # The single character that prefixes every command, e.g. "!ask".
    PREFIX: str = "!"
    # What we call points everywhere in the UI.
    CURRENCY_NAME: str = "aura"
    # A nice emoji to pair with the currency in embeds.
    CURRENCY_EMOJI: str = "🔮"

    # --- Secrets / connection strings (from environment) ---------------------

    # The bot token. We deliberately do NOT provide a default — a missing token
    # is a hard error that should stop startup (see bot.run_bot()).
    DISCORD_TOKEN: str | None = os.getenv("DISCORD_TOKEN")

    # Default to a local SQLite file. Swap to PostgreSQL by changing only this
    # env var, e.g. DB_URL=postgresql+psycopg://user:pass@localhost/codesensei
    DB_URL: str = os.getenv("DB_URL", "sqlite:///app.db")

    # Logging verbosity, read as a string like "INFO" and resolved to a level.
    LOGGING_LEVEL: str = os.getenv("LOGGING_LEVEL", "INFO")
    # Where the rotating log file is written.
    LOG_FILE: str = os.getenv("LOG_FILE", "bot.log")

    # --- Slash commands ------------------------------------------------------
    # If GUILD_ID is set, slash commands sync INSTANTLY to that one server
    # (ideal for development). If left blank, they sync GLOBALLY, which can take
    # up to ~1 hour to appear but works in every server the bot joins.
    GUILD_ID: str = os.getenv("GUILD_ID", "")

    # How many seconds the A/B/C/D answer buttons stay clickable before they
    # disable themselves and the embed reveals the correct option.
    ANSWER_TIMEOUT: float = float(os.getenv("ANSWER_TIMEOUT", "120"))

    # --- Tier 2: scoring, levels, streaks, cooldowns -------------------------

    # Point multiplier per difficulty. Each is overridable via its own env var.
    DIFFICULTY_MULTIPLIERS: dict[str, float] = {
        "easy": float(os.getenv("DIFF_EASY", "1.0")),
        "medium": float(os.getenv("DIFF_MEDIUM", "1.5")),
        "hard": float(os.getenv("DIFF_HARD", "2.0")),
    }

    # Levels: level = floor(sqrt(points / LEVEL_POINTS_BASE)).
    LEVEL_POINTS_BASE: int = int(os.getenv("LEVEL_POINTS_BASE", "100"))

    # Daily streak bonus: +N points per consecutive day, capped.
    STREAK_BONUS_PER_DAY: int = int(os.getenv("STREAK_BONUS_PER_DAY", "5"))
    STREAK_BONUS_CAP: int = int(os.getenv("STREAK_BONUS_CAP", "50"))

    # Per-user cooldown (seconds) on /ask to discourage point-spamming.
    ASK_COOLDOWN_SECONDS: float = float(os.getenv("ASK_COOLDOWN_SECONDS", "10"))

    # Optional level -> role auto-assignment. Format in .env:
    #   LEVEL_ROLES=1:Novice,3:Apprentice,5:Adept,10:Sensei
    # The bot creates/assigns the role for the highest level a member has reached
    # (requires the Manage Roles permission; silently skipped if missing/blank).
    LEVEL_ROLES: dict[int, str] = _parse_level_roles(os.getenv("LEVEL_ROLES", ""))

    # --- Easter egg ----------------------------------------------------------
    # If you want one specific user to always get their answer auto-corrected
    # plus bonus aura, put their Discord ID here (as a string). Leave it as an
    # empty string to disable the easter egg entirely.
    #
    # How to find an ID: enable Developer Mode in Discord (User Settings ->
    # Advanced), then right-click a user -> "Copy User ID".
    EASTER_EGG_USER_ID: str = os.getenv("EASTER_EGG_USER_ID", "123456789012345678")
    # Extra aura granted to the lucky user on every answer.
    EASTER_EGG_BONUS: int = 5

    @classmethod
    def log_level(cls) -> int:
        """Translate the LOGGING_LEVEL string into a logging module constant."""
        return getattr(logging, cls.LOGGING_LEVEL.upper(), logging.INFO)
