"""
utils.py
========
Pure helper functions: picking random questions, checking answers, and — most
importantly — building all the Discord embeds.

Keeping every embed in one place means the bot's look-and-feel is consistent and
easy to re-theme. CodeSensei's color scheme:
  - blue   -> questions / help
  - green  -> resources / success
  - red    -> wrong answers / errors
  - gold   -> profiles
  - purple -> leaderboard
"""

from __future__ import annotations

import random
from datetime import datetime, timezone

import discord
from sqlalchemy import func
from sqlalchemy.orm import Session

import scoring
from config import Config


def progress_bar(fraction: float, slots: int = 10) -> str:
    """Render a text progress bar like ▰▰▰▰▱▱▱▱▱▱ for a 0..1 fraction."""
    fraction = max(0.0, min(1.0, fraction))
    filled = round(fraction * slots)
    return "▰" * filled + "▱" * (slots - filled)

# --- Color palette ----------------------------------------------------------
COLOR_BLUE = discord.Color.blue()
COLOR_GREEN = discord.Color.green()
COLOR_RED = discord.Color.red()
COLOR_GOLD = discord.Color.gold()
COLOR_PURPLE = discord.Color.purple()

# A consistent footer tag on every embed reinforces the bot's identity.
FOOTER = f"{Config.BOT_NAME} • your friendly coding mentor"

# Friendly one-liners CodeSensei says when someone @-mentions it.
MENTION_LINES = [
    "Hey there, future 10x dev! 👋 Type `!help` and let's level up together.",
    "Ready to train? 🧠 Try `!ask` for a quiz or `!resource` for something to read.",
    "Every expert was once a beginner. Keep going — I believe in you! 💪",
    "Stuck? That just means you're about to learn something. Try `!ask`!",
    f"Collect some {Config.CURRENCY_NAME} {Config.CURRENCY_EMOJI} with `!ask` — knowledge is the real reward.",
    "Pro tip from your sensei: consistency beats intensity. One quiz a day! 🌱",
    "I'm here whenever you need a question, a resource, or a little encouragement. 🤗",
]


def random_mention_line() -> str:
    """Return a random friendly mention reply matching CodeSensei's vibe."""
    return random.choice(MENTION_LINES)


# ---------------------------------------------------------------------------
# Quiz logic helpers
# ---------------------------------------------------------------------------


def get_random_question(session: Session, category: str | None = None):
    """Return a random *active* question, optionally filtered by category.

    Returns None if there are no matching questions.
    """
    from models import Question

    query = session.query(Question).filter(Question.is_active.is_(True))
    if category:
        # Case-insensitive category match so "dsa" finds "DSA".
        query = query.filter(func.lower(Question.category) == category.lower())

    # ORDER BY RANDOM() is fine for a community-sized table.
    return query.order_by(func.random()).first()


def check_answer(question, chosen_letter: str) -> bool:
    """True if the chosen letter (A/B/C/D, any case) matches the correct option."""
    return chosen_letter.strip().upper() == question.correct_option.upper()


def _timestamp() -> datetime:
    return datetime.now(timezone.utc)


# ---------------------------------------------------------------------------
# Embed builders
# ---------------------------------------------------------------------------


def question_embed(question, *, is_daily: bool = False) -> discord.Embed:
    """Blue embed presenting a question and its four options."""
    title = (
        f"🗓️ Daily Challenge #{question.id}: {question.title}"
        if is_daily
        else f"🧠 Quiz #{question.id}: {question.title}"
    )
    embed = discord.Embed(
        title=title,
        description=question.description or "Pick the best answer below.",
        color=COLOR_BLUE,
    )
    embed.add_field(name="🅰️ A", value=question.option_a, inline=False)
    embed.add_field(name="🅱️ B", value=question.option_b, inline=False)
    embed.add_field(name="🇨 C", value=question.option_c, inline=False)
    embed.add_field(name="🇩 D", value=question.option_d, inline=False)
    embed.add_field(
        name="How to answer",
        value="Click a button below (🅰️/🅱️/🇨/🇩). Your result is private!",
        inline=False,
    )
    embed.add_field(name="Category", value=question.category, inline=True)
    embed.add_field(name="Difficulty", value=question.difficulty.title(), inline=True)
    reward = scoring.points_for(question.points, question.difficulty)
    embed.add_field(
        name="Reward",
        value=f"{reward} {Config.CURRENCY_NAME} {Config.CURRENCY_EMOJI}",
        inline=True,
    )
    embed.set_footer(text=FOOTER)
    return embed


def answer_feedback_embed(question, chosen_letter: str, outcome) -> discord.Embed:
    """Ephemeral embed shown after a user answers (correct or wrong).

    `outcome` is a services.AnswerOutcome carrying the points breakdown,
    streak, and level-up info.
    """
    if outcome.is_correct:
        embed = discord.Embed(
            title="✅ Correct! Nicely done.",
            description=f"**{question.title}** — option **{question.correct_option}** was right!",
            color=COLOR_GREEN,
        )
        # Points breakdown.
        lines = [f"Base: **+{outcome.base_points}** {Config.CURRENCY_EMOJI}"]
        if outcome.egg_bonus:
            lines.append(f"Lucky bonus: **+{outcome.egg_bonus}** ✨")
        if outcome.streak_bonus:
            lines.append(f"Streak bonus: **+{outcome.streak_bonus}** 🔥")
        lines.append(f"**Total this answer: +{outcome.total_awarded}**")
        embed.add_field(name="Reward", value="\n".join(lines), inline=False)
    else:
        embed = discord.Embed(
            title="❌ Not quite — but that's how we learn!",
            description=f"You picked **{chosen_letter.upper()}** for **{question.title}**.",
            color=COLOR_RED,
        )
        embed.add_field(
            name="Correct answer",
            value=f"**{question.correct_option}** — {question.option_text(question.correct_option)}",
            inline=False,
        )

    if outcome.counted_daily:
        embed.add_field(
            name="Daily streak", value=f"🔥 {outcome.current_streak} day(s)", inline=True
        )
    if outcome.leveled_up:
        embed.add_field(
            name="Level up!", value=f"🎉 You reached **level {outcome.new_level}**!", inline=True
        )
    embed.set_footer(text=FOOTER)
    return embed


def levelup_embed(display_name: str, level: int, role_name: str | None = None) -> discord.Embed:
    """Public celebration when someone reaches a new level."""
    embed = discord.Embed(
        title="🎉 Level Up!",
        description=f"**{display_name}** just reached **level {level}**! 🚀",
        color=COLOR_PURPLE,
    )
    if role_name:
        embed.add_field(name="New role", value=f"🏷️ **{role_name}**", inline=False)
    embed.set_footer(text=FOOTER)
    return embed


def achievements_unlocked_embed(display_name: str, achievements) -> discord.Embed:
    """Public announcement listing newly-unlocked badges."""
    embed = discord.Embed(
        title="🏆 Achievement Unlocked!",
        description=f"Congrats, **{display_name}**!",
        color=COLOR_GOLD,
    )
    for a in achievements:
        embed.add_field(name=f"{a.emoji} {a.name}", value=a.description, inline=False)
    embed.set_footer(text=FOOTER)
    return embed


def daily_done_embed(current_streak: int) -> discord.Embed:
    """Shown when a user has already completed today's daily."""
    return simple_embed(
        "🗓️ Daily already done",
        f"You've completed today's challenge! 🔥 Current streak: **{current_streak}** day(s).\n"
        "Come back tomorrow (UTC) to keep it alive!",
        COLOR_BLUE,
    )


def resource_embed(resource) -> discord.Embed:
    """Green embed showing a single resource."""
    embed = discord.Embed(
        title=f"📚 {resource.title}",
        url=resource.url,
        description=resource.description or "A handy resource picked just for you.",
        color=COLOR_GREEN,
    )
    embed.add_field(name="Category", value=resource.category, inline=True)
    embed.add_field(name="Upvotes", value=f"👍 {resource.upvotes}", inline=True)
    if resource.tags:
        embed.add_field(name="Tags", value=resource.tags, inline=False)
    embed.add_field(name="Link", value=resource.url, inline=False)
    embed.set_footer(text=FOOTER)
    return embed


def profile_embed(
    user, display_name: str, avatar_url: str | None, achievements=None
) -> discord.Embed:
    """Gold embed showing a user's stats, level, streak, and badges."""
    embed = discord.Embed(
        title=f"🪪 {display_name}'s Profile",
        description="Here's how your training is going!",
        color=COLOR_GOLD,
    )
    if avatar_url:
        embed.set_thumbnail(url=avatar_url)

    embed.add_field(
        name=f"{Config.CURRENCY_NAME.title()} {Config.CURRENCY_EMOJI}",
        value=str(user.points),
        inline=True,
    )
    embed.add_field(name="Level", value=f"🎚️ {user.level}", inline=True)
    embed.add_field(
        name="Streak",
        value=f"🔥 {user.current_streak or 0} (best {user.longest_streak or 0})",
        inline=True,
    )
    embed.add_field(name="Correct", value=str(user.correct_answers), inline=True)
    embed.add_field(name="Answered", value=str(user.total_answers), inline=True)
    embed.add_field(name="Accuracy", value=f"{user.accuracy:.1f}%", inline=True)

    # Progress bar toward the next level.
    into, span, next_pts = scoring.level_progress(user.points or 0)
    bar = progress_bar(into / span if span else 0.0)
    embed.add_field(
        name=f"Progress to level {user.level + 1}",
        value=f"{bar}  {into}/{span} ({next_pts} {Config.CURRENCY_NAME} total)",
        inline=False,
    )

    if achievements:
        badges = " ".join(f"{a.emoji}" for a in achievements)
        names = ", ".join(a.name for a in achievements)
        embed.add_field(
            name=f"🏆 Badges ({len(achievements)})",
            value=f"{badges}\n{names}",
            inline=False,
        )
    else:
        embed.add_field(
            name="🏆 Badges (0)",
            value="None yet — answer questions and build streaks to earn some!",
            inline=False,
        )
    embed.set_footer(text=FOOTER)
    return embed


def leaderboard_embed(rows: list) -> discord.Embed:
    """Purple embed listing the top users. `rows` is an ordered list of User."""
    embed = discord.Embed(
        title="🏆 Leaderboard — Top Learners",
        description=f"Ranked by {Config.CURRENCY_NAME} {Config.CURRENCY_EMOJI}",
        color=COLOR_PURPLE,
    )
    if not rows:
        embed.description = "No one has earned any aura yet. Be the first with `!ask`!"
        embed.set_footer(text=FOOTER)
        return embed

    medals = ["🥇", "🥈", "🥉"]
    lines = []
    for index, user in enumerate(rows):
        rank = medals[index] if index < len(medals) else f"`#{index + 1}`"
        lines.append(
            f"{rank} **{user.username}** — {user.points} {Config.CURRENCY_NAME} "
            f"({user.accuracy:.0f}% acc.)"
        )
    embed.add_field(name="Rankings", value="\n".join(lines), inline=False)
    embed.set_footer(text=FOOTER)
    return embed


def categories_embed(question_cats: list[str], resource_cats: list[str]) -> discord.Embed:
    """Blue embed listing all distinct question and resource categories."""
    embed = discord.Embed(
        title="🗂️ Categories",
        description="Use these with `!ask <category>` or `!resource <category>`.",
        color=COLOR_BLUE,
    )
    embed.add_field(
        name="🧠 Quiz categories",
        value=", ".join(question_cats) if question_cats else "None yet",
        inline=False,
    )
    embed.add_field(
        name="📚 Resource categories",
        value=", ".join(resource_cats) if resource_cats else "None yet",
        inline=False,
    )
    embed.set_footer(text=FOOTER)
    return embed


def help_embed() -> discord.Embed:
    """Blue embed listing every command, grouped by section."""
    p = Config.PREFIX
    embed = discord.Embed(
        title=f"📖 {Config.BOT_NAME} — Command Guide",
        description=(
            "Hi! I'm your friendly coding mentor. Every command works as a slash "
            f"command (`/ask`) **or** with the `{p}` prefix (`{p}ask`). Test your "
            f"knowledge, share resources, and earn {Config.CURRENCY_NAME} {Config.CURRENCY_EMOJI}!"
        ),
        color=COLOR_BLUE,
    )
    embed.add_field(
        name="🧠 Quiz",
        value=(
            "`/ask [category]` — get a question with A/B/C/D **buttons** to click\n"
            "`/daily` — your once-a-day challenge (builds a 🔥 streak + bonus)\n"
            "`/answer <id> <A/B/C/D>` — type-based fallback to answer\n"
            "`/addquestion title | desc | category | A | B | C | D | correct`"
        ),
        inline=False,
    )
    embed.add_field(
        name="📚 Resources",
        value=(
            "`/resource [category]` — get a random resource\n"
            "`/addresource title | url | category | [description]`"
        ),
        inline=False,
    )
    embed.add_field(
        name="📊 Progress",
        value=(
            "`/profile [@user]` — level, streak, accuracy & badges\n"
            f"`/{Config.CURRENCY_NAME.lower()} [@user]` — quick {Config.CURRENCY_NAME} readout\n"
            "`/leaderboard` — top 10 learners\n"
            "`/categories` — list all categories"
        ),
        inline=False,
    )
    embed.add_field(
        name="✨ How you earn",
        value=(
            "Harder questions pay more (easy ×1, medium ×1.5, hard ×2). Do your "
            "`/daily` for streak 🔥 bonuses, climb **levels** 🎚️, and unlock "
            "**badges** 🏆 along the way!"
        ),
        inline=False,
    )
    embed.set_footer(text=FOOTER + "  •  Tip: @mention me anytime!")
    return embed


def simple_embed(title: str, description: str, color: discord.Color) -> discord.Embed:
    """A tiny generic embed used for confirmations and error messages."""
    embed = discord.Embed(title=title, description=description, color=color)
    embed.set_footer(text=FOOTER)
    return embed
