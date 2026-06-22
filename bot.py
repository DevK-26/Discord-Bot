"""
bot.py
======
The heart of CodeSensei: intents, the Bot instance, lifecycle events, the global
error handler, and every command.

Conventions used throughout:
  - Each command opens its own DB session with get_session() and ALWAYS closes
    it in a `finally` block.
  - get_or_create_user() runs first in any command that needs the caller's row.
  - Every user-facing reply is a rich embed (built in utils.py), except very
    short confirmations.
"""

from __future__ import annotations

import logging

import discord
from discord.ext import commands
from sqlalchemy import func

import utils
from config import Config
from db import (
    add_question,
    add_resource,
    get_or_create_user,
    get_session,
    record_answer,
)
from models import Question, Resource, User

log = logging.getLogger("codesensei")


# ---------------------------------------------------------------------------
# Intents & Bot instance
# ---------------------------------------------------------------------------
# message_content + members are PRIVILEGED intents — they must also be enabled
# in the Discord Developer Portal (see README).
intents = discord.Intents.default()
intents.message_content = True  # needed to read command text
intents.members = True  # needed to resolve @mentions to members

# We pass help_command=None so we can provide our own pretty !help embed.
bot = commands.Bot(
    command_prefix=Config.PREFIX,
    intents=intents,
    help_command=None,
    case_insensitive=True,
)


# ---------------------------------------------------------------------------
# Lifecycle events
# ---------------------------------------------------------------------------


@bot.event
async def on_ready() -> None:
    """Called once the bot has connected and is ready to receive events."""
    log.info("%s is online as %s (id: %s)", Config.BOT_NAME, bot.user, bot.user.id)
    # A little status so members can see what to do.
    await bot.change_presence(
        activity=discord.Game(name=f"{Config.PREFIX}help • teaching code")
    )


@bot.event
async def on_message(message: discord.Message) -> None:
    """Handle @mentions, then let the command framework process commands."""
    # Never respond to ourselves or other bots — prevents loops.
    if message.author.bot:
        return

    # If the bot is directly @-mentioned (not via @everyone/@here), say hi.
    if bot.user in message.mentions and not message.mention_everyone:
        embed = utils.simple_embed(
            f"👋 Hey {message.author.display_name}!",
            utils.random_mention_line(),
            utils.COLOR_BLUE,
        )
        await message.channel.send(embed=embed)

    # Crucial: without this, none of the !commands would ever run.
    await bot.process_commands(message)


# ---------------------------------------------------------------------------
# Global error handler
# ---------------------------------------------------------------------------


@bot.event
async def on_command_error(ctx: commands.Context, error: commands.CommandError) -> None:
    """One place to turn framework errors into friendly emoji-prefixed embeds."""
    # Unwrap errors raised inside command bodies.
    error = getattr(error, "original", error)

    if isinstance(error, commands.CommandNotFound):
        embed = utils.simple_embed(
            "🤔 Unknown command",
            f"I don't know that one. Try `{Config.PREFIX}help` to see what I can do!",
            utils.COLOR_RED,
        )
    elif isinstance(error, commands.MissingRequiredArgument):
        embed = utils.simple_embed(
            "✋ Missing something",
            f"You left out `{error.param.name}`. "
            f"Check `{Config.PREFIX}help` for the right format.",
            utils.COLOR_RED,
        )
    elif isinstance(error, commands.BadArgument):
        embed = utils.simple_embed(
            "⚠️ That didn't look right",
            f"One of your arguments was the wrong type. "
            f"See `{Config.PREFIX}help` for examples.",
            utils.COLOR_RED,
        )
    else:
        # Anything unexpected: log the full traceback, show a calm message.
        log.exception("Unhandled command error in %s", ctx.command, exc_info=error)
        embed = utils.simple_embed(
            "💥 Something went wrong",
            "I hit an unexpected snag. The issue has been logged — try again!",
            utils.COLOR_RED,
        )

    await ctx.send(embed=embed)


# ---------------------------------------------------------------------------
# Commands — Help
# ---------------------------------------------------------------------------


@bot.command(name="help")
async def help_command(ctx: commands.Context) -> None:
    """Show the grouped command guide."""
    await ctx.send(embed=utils.help_embed())


# ---------------------------------------------------------------------------
# Commands — Quiz
# ---------------------------------------------------------------------------


@bot.command(name="ask")
async def ask(ctx: commands.Context, category: str | None = None) -> None:
    """Send a random active question, optionally filtered by category."""
    session = get_session()
    try:
        question = utils.get_random_question(session, category)
        if question is None:
            where = f" in **{category}**" if category else ""
            await ctx.send(
                embed=utils.simple_embed(
                    "📭 No questions yet",
                    f"I couldn't find an active question{where}. "
                    f"Add one with `{Config.PREFIX}addquestion`!",
                    utils.COLOR_RED,
                )
            )
            return
        await ctx.send(embed=utils.question_embed(question))
    finally:
        session.close()


@bot.command(name="answer")
async def answer(ctx: commands.Context, question_id: int, option: str) -> None:
    """Check an A/B/C/D answer, award aura if correct, reveal answer if wrong."""
    option = option.strip().upper()
    if option not in {"A", "B", "C", "D"}:
        await ctx.send(
            embed=utils.simple_embed(
                "⚠️ Pick A, B, C, or D",
                f"Usage: `{Config.PREFIX}answer {question_id} <A/B/C/D>`",
                utils.COLOR_RED,
            )
        )
        return

    session = get_session()
    try:
        question = session.get(Question, question_id)
        if question is None or not question.is_active:
            await ctx.send(
                embed=utils.simple_embed(
                    "🔍 Question not found",
                    f"There's no active question #{question_id}. "
                    f"Try `{Config.PREFIX}ask` to get one.",
                    utils.COLOR_RED,
                )
            )
            return

        user = get_or_create_user(session, ctx.author.id, ctx.author.display_name)

        # --- Easter egg: one lucky user always answers "correctly" + bonus ---
        bonus = 0
        if Config.EASTER_EGG_USER_ID and str(ctx.author.id) == Config.EASTER_EGG_USER_ID:
            # Auto-correct their choice to the right option before recording.
            option = question.correct_option
            bonus = Config.EASTER_EGG_BONUS

        _, is_correct = record_answer(
            session, user=user, question=question, chosen_letter=option
        )

        # Apply easter-egg bonus aura on top of the normal award.
        if bonus:
            user.points += bonus

        session.commit()

        if is_correct:
            await ctx.send(
                embed=utils.correct_answer_embed(question, question.points, bonus)
            )
        else:
            await ctx.send(embed=utils.wrong_answer_embed(question, option))
    finally:
        session.close()


@bot.command(name="addquestion")
async def addquestion(ctx: commands.Context, *, payload: str) -> None:
    """Add a question from a `|`-delimited string.

    Format: title | desc | category | optA | optB | optC | optD | correct
    """
    parts = [p.strip() for p in payload.split("|")]
    if len(parts) != 8:
        await ctx.send(
            embed=utils.simple_embed(
                "✋ Wrong format",
                "Use exactly 8 `|`-separated fields:\n"
                f"`{Config.PREFIX}addquestion title | desc | category | A | B | C | D | correct`",
                utils.COLOR_RED,
            )
        )
        return

    title, desc, category, opt_a, opt_b, opt_c, opt_d, correct = parts
    correct = correct.upper()
    if correct not in {"A", "B", "C", "D"}:
        await ctx.send(
            embed=utils.simple_embed(
                "⚠️ Bad correct option",
                "The final field (correct option) must be one of A, B, C, or D.",
                utils.COLOR_RED,
            )
        )
        return

    session = get_session()
    try:
        question = add_question(
            session,
            title=title,
            description=desc,
            category=category,
            option_a=opt_a,
            option_b=opt_b,
            option_c=opt_c,
            option_d=opt_d,
            correct_option=correct,
            asked_by=str(ctx.author.id),
        )
        session.commit()
        await ctx.send(
            embed=utils.simple_embed(
                "✅ Question added!",
                f"Saved **{title}** as quiz #{question.id} in **{category}**. Thanks for contributing!",
                utils.COLOR_GREEN,
            )
        )
    finally:
        session.close()


# ---------------------------------------------------------------------------
# Commands — Resources
# ---------------------------------------------------------------------------


@bot.command(name="resource")
async def resource(ctx: commands.Context, category: str | None = None) -> None:
    """Fetch a random resource, optionally filtered by category."""
    session = get_session()
    try:
        query = session.query(Resource)
        if category:
            query = query.filter(func.lower(Resource.category) == category.lower())
        item = query.order_by(func.random()).first()

        if item is None:
            where = f" in **{category}**" if category else ""
            await ctx.send(
                embed=utils.simple_embed(
                    "📭 No resources yet",
                    f"I couldn't find a resource{where}. "
                    f"Add one with `{Config.PREFIX}addresource`!",
                    utils.COLOR_RED,
                )
            )
            return
        await ctx.send(embed=utils.resource_embed(item))
    finally:
        session.close()


@bot.command(name="addresource")
async def addresource(ctx: commands.Context, *, payload: str) -> None:
    """Add a resource from a `|`-delimited string.

    Format: title | url | category | [description]
    """
    parts = [p.strip() for p in payload.split("|")]
    if len(parts) < 3:
        await ctx.send(
            embed=utils.simple_embed(
                "✋ Wrong format",
                "Use at least 3 `|`-separated fields:\n"
                f"`{Config.PREFIX}addresource title | url | category | [description]`",
                utils.COLOR_RED,
            )
        )
        return

    title, url, category = parts[0], parts[1], parts[2]
    description = parts[3] if len(parts) >= 4 and parts[3] else None

    session = get_session()
    try:
        item = add_resource(
            session,
            title=title,
            url=url,
            category=category,
            description=description,
            added_by=str(ctx.author.id),
        )
        session.commit()
        await ctx.send(
            embed=utils.simple_embed(
                "✅ Resource added!",
                f"Saved **{title}** (#{item.id}) in **{category}**. The community thanks you! 🙌",
                utils.COLOR_GREEN,
            )
        )
    finally:
        session.close()


# ---------------------------------------------------------------------------
# Commands — Progress (profile / aura / leaderboard / categories)
# ---------------------------------------------------------------------------


@bot.command(name="profile")
async def profile(ctx: commands.Context, member: discord.Member | None = None) -> None:
    """Show a full profile embed for yourself or a mentioned user."""
    target = member or ctx.author
    session = get_session()
    try:
        user = get_or_create_user(session, target.id, target.display_name)
        session.commit()
        avatar_url = target.display_avatar.url if target.display_avatar else None
        await ctx.send(
            embed=utils.profile_embed(user, target.display_name, avatar_url)
        )
    finally:
        session.close()


# The aura command. (Rename this if you change CURRENCY_NAME in config.)
@bot.command(name=Config.CURRENCY_NAME, aliases=["points"])
async def aura(ctx: commands.Context, member: discord.Member | None = None) -> None:
    """Quick one-line readout of someone's aura."""
    target = member or ctx.author
    session = get_session()
    try:
        user = get_or_create_user(session, target.id, target.display_name)
        session.commit()
        await ctx.send(
            f"{Config.CURRENCY_EMOJI} **{target.display_name}** has "
            f"**{user.points}** {Config.CURRENCY_NAME} "
            f"({user.accuracy:.0f}% accuracy)."
        )
    finally:
        session.close()


@bot.command(name="leaderboard", aliases=["lb", "top"])
async def leaderboard(ctx: commands.Context) -> None:
    """Show the top 10 users by points."""
    session = get_session()
    try:
        rows = (
            session.query(User)
            .order_by(User.points.desc(), User.correct_answers.desc())
            .limit(10)
            .all()
        )
        await ctx.send(embed=utils.leaderboard_embed(rows))
    finally:
        session.close()


@bot.command(name="categories", aliases=["cats"])
async def categories(ctx: commands.Context) -> None:
    """List all distinct question and resource categories."""
    session = get_session()
    try:
        q_cats = [
            c[0]
            for c in session.query(Question.category).distinct().order_by(Question.category)
        ]
        r_cats = [
            c[0]
            for c in session.query(Resource.category).distinct().order_by(Resource.category)
        ]
        await ctx.send(embed=utils.categories_embed(q_cats, r_cats))
    finally:
        session.close()


# ---------------------------------------------------------------------------
# Entry point used by main.py
# ---------------------------------------------------------------------------


def run_bot() -> None:
    """Configure logging and start the bot. Raises if the token is missing."""
    logging.basicConfig(
        level=Config.log_level(),
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    if not Config.DISCORD_TOKEN:
        # Fail loudly and clearly rather than letting discord.py throw a vague error.
        raise RuntimeError(
            "DISCORD_TOKEN is not set. Copy .env.example to .env and paste your "
            "bot token from the Discord Developer Portal."
        )

    bot.run(Config.DISCORD_TOKEN, log_handler=None)
