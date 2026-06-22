"""
bot.py
======
Bootstrap for CodeSensei. After the Tier 1 upgrade this file is intentionally
small — the actual commands live in cogs under ``cogs/``.

Responsibilities:
  - configure real logging (console + rotating file) from LOGGING_LEVEL
  - build the Bot subclass with the right intents
  - load every cog dynamically in ``setup_hook``
  - sync the slash-command tree (guild-scoped if GUILD_ID is set, else global)
  - expose ``run_bot()`` for main.py, raising clearly if the token is missing
"""

from __future__ import annotations

import logging
from logging.handlers import RotatingFileHandler

import discord
from discord.ext import commands

from config import Config

log = logging.getLogger("codesensei")

# Every cog the bot loads on startup. Add new cogs here as the project grows.
INITIAL_COGS = (
    "cogs.events",
    "cogs.quiz",
    "cogs.resources",
    "cogs.profile",
    "cogs.admin",
)


def setup_logging() -> None:
    """Send logs to both the console and a rotating ``bot.log`` file.

    Replaces the old ``print()`` calls in the bot runtime. The level comes from
    the LOGGING_LEVEL env var (DEBUG / INFO / WARNING / ...).
    """
    level = Config.log_level()
    fmt = logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s")

    console = logging.StreamHandler()
    console.setFormatter(fmt)

    # Roll over at ~1 MB, keep 3 old files so logs never grow unbounded.
    file_handler = RotatingFileHandler(
        Config.LOG_FILE, maxBytes=1_000_000, backupCount=3, encoding="utf-8"
    )
    file_handler.setFormatter(fmt)

    root = logging.getLogger()
    root.setLevel(level)
    root.handlers = [console, file_handler]  # replace any default handlers

    # discord.py's own logger is chatty; keep it to warnings unless we're debugging.
    logging.getLogger("discord").setLevel(
        logging.DEBUG if level <= logging.DEBUG else logging.WARNING
    )


class CodeSensei(commands.Bot):
    """The bot. Subclassing lets us use ``setup_hook`` for clean async startup."""

    def __init__(self) -> None:
        # message_content + members are PRIVILEGED — enable them in the portal too.
        intents = discord.Intents.default()
        intents.message_content = True
        intents.members = True
        super().__init__(
            command_prefix=Config.PREFIX,
            intents=intents,
            help_command=None,  # we ship our own /help
            case_insensitive=True,
        )

    async def setup_hook(self) -> None:
        """Runs once before the bot connects: load cogs, then sync slash commands."""
        for ext in INITIAL_COGS:
            await self.load_extension(ext)
            log.info("Loaded cog: %s", ext)

        if Config.GUILD_ID:
            # Guild-scoped sync — instant, perfect for development.
            guild = discord.Object(id=int(Config.GUILD_ID))
            self.tree.copy_global_to(guild=guild)
            synced = await self.tree.sync(guild=guild)
            log.info("Synced %d slash command(s) to guild %s", len(synced), Config.GUILD_ID)
        else:
            # Global sync — works everywhere, but can take up to ~1 hour to show.
            synced = await self.tree.sync()
            log.info("Globally synced %d slash command(s) (may take up to ~1h)", len(synced))


def run_bot() -> None:
    """Configure logging and start the bot. Raises if the token is missing."""
    setup_logging()

    if not Config.DISCORD_TOKEN:
        raise RuntimeError(
            "DISCORD_TOKEN is not set. Copy .env.example to .env and paste your "
            "bot token from the Discord Developer Portal."
        )

    bot = CodeSensei()
    # log_handler=None because we configured logging ourselves above.
    bot.run(Config.DISCORD_TOKEN, log_handler=None)
