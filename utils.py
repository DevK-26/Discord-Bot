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

from config import Config

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


def question_embed(question) -> discord.Embed:
    """Blue embed presenting a question and its four options."""
    embed = discord.Embed(
        title=f"🧠 Quiz #{question.id}: {question.title}",
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
    embed.add_field(
        name="Reward",
        value=f"{question.points} {Config.CURRENCY_NAME} {Config.CURRENCY_EMOJI}",
        inline=True,
    )
    embed.set_footer(text=FOOTER)
    return embed


def correct_answer_embed(question, points_awarded: int, bonus: int = 0) -> discord.Embed:
    """Green embed celebrating a correct answer."""
    embed = discord.Embed(
        title="✅ Correct! Nicely done.",
        description=f"**{question.title}** — option **{question.correct_option}** was right!",
        color=COLOR_GREEN,
    )
    total = points_awarded + bonus
    value = f"+{points_awarded} {Config.CURRENCY_NAME} {Config.CURRENCY_EMOJI}"
    if bonus:
        value += f"  (+{bonus} bonus! ✨)"
    embed.add_field(name="Reward", value=value, inline=False)
    embed.add_field(name="Total this answer", value=str(total), inline=False)
    embed.set_footer(text=FOOTER)
    return embed


def wrong_answer_embed(question, chosen_letter: str) -> discord.Embed:
    """Red embed for a wrong answer that reveals the correct option."""
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
    embed.add_field(
        name="Keep going",
        value=f"Try another with `{Config.PREFIX}ask`. You've got this! 💪",
        inline=False,
    )
    embed.set_footer(text=FOOTER)
    return embed


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


def profile_embed(user, display_name: str, avatar_url: str | None) -> discord.Embed:
    """Gold embed showing a user's stats with their avatar as a thumbnail."""
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
    embed.add_field(name="Correct", value=str(user.correct_answers), inline=True)
    embed.add_field(name="Answered", value=str(user.total_answers), inline=True)
    embed.add_field(name="Accuracy", value=f"{user.accuracy:.1f}%", inline=True)
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
            "`/profile [@user]` — view a full profile\n"
            f"`/{Config.CURRENCY_NAME.lower()} [@user]` — quick {Config.CURRENCY_NAME} readout\n"
            "`/leaderboard` — top 10 learners\n"
            "`/categories` — list all categories"
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
