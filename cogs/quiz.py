"""
cogs/quiz.py
============
The quiz cog: asking questions (with clickable answer buttons), a type-based
answer fallback, adding questions, and listing categories.

All commands are **hybrid** — they work as slash commands (`/ask`) and with the
legacy `!` prefix (`!ask`), so nothing breaks for existing users.
"""

from __future__ import annotations

import logging

import discord
from discord import app_commands
from discord.ext import commands

import utils
from config import Config
from db import add_question, get_or_create_user, get_session, record_answer
from models import Answer, Question
from views import AnswerView

log = logging.getLogger("codesensei.quiz")


async def question_category_autocomplete(
    interaction: discord.Interaction, current: str
) -> list[app_commands.Choice[str]]:
    """Suggest distinct question categories as the user types."""
    session = get_session()
    try:
        cats = [c[0] for c in session.query(Question.category).distinct()]
    finally:
        session.close()
    current = (current or "").lower()
    # Discord allows at most 25 autocomplete choices.
    return [
        app_commands.Choice(name=cat, value=cat)
        for cat in cats
        if current in cat.lower()
    ][:25]


class Quiz(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @commands.hybrid_command(
        name="ask", description="Get a random quiz question with answer buttons."
    )
    @app_commands.describe(category="Optional category to filter by")
    @app_commands.autocomplete(category=question_category_autocomplete)
    async def ask(self, ctx: commands.Context, category: str | None = None) -> None:
        session = get_session()
        try:
            question = utils.get_random_question(session, category)
            if question is None:
                where = f" in **{category}**" if category else ""
                await ctx.send(
                    embed=utils.simple_embed(
                        "📭 No questions yet",
                        f"I couldn't find an active question{where}. "
                        f"Add one with `/addquestion`!",
                        utils.COLOR_RED,
                    ),
                    ephemeral=True,
                )
                return

            # Post the question publicly with clickable A/B/C/D buttons.
            view = AnswerView(question)
            message = await ctx.send(embed=utils.question_embed(question), view=view)
            view.message = message  # let the view edit it on timeout
        finally:
            session.close()

    @commands.hybrid_command(
        name="answer", description="Answer a question by id (text fallback to buttons)."
    )
    @app_commands.describe(question_id="The question number", option="A, B, C, or D")
    async def answer(
        self, ctx: commands.Context, question_id: int, option: str
    ) -> None:
        option = option.strip().upper()
        if option not in {"A", "B", "C", "D"}:
            await ctx.send(
                embed=utils.simple_embed(
                    "⚠️ Pick A, B, C, or D",
                    f"Usage: `/answer {question_id} <A/B/C/D>`",
                    utils.COLOR_RED,
                ),
                ephemeral=True,
            )
            return

        session = get_session()
        try:
            question = session.get(Question, question_id)
            if question is None or not question.is_active:
                await ctx.send(
                    embed=utils.simple_embed(
                        "🔍 Question not found",
                        f"There's no active question #{question_id}. Try `/ask`.",
                        utils.COLOR_RED,
                    ),
                    ephemeral=True,
                )
                return

            user = get_or_create_user(session, ctx.author.id, ctx.author.display_name)

            # One scored attempt per user per question.
            existing = (
                session.query(Answer)
                .filter_by(user_id=user.id, question_id=question.id)
                .first()
            )
            if existing is not None:
                await ctx.send(
                    embed=utils.simple_embed(
                        "📝 Already answered",
                        f"You already answered #{question.id} (you chose "
                        f"**{existing.answer_text}**). Try a new one with `/ask`!",
                        utils.COLOR_GOLD,
                    ),
                    ephemeral=True,
                )
                return

            # Easter egg: one lucky user is auto-corrected + bonus.
            bonus = 0
            if Config.EASTER_EGG_USER_ID and str(ctx.author.id) == Config.EASTER_EGG_USER_ID:
                option = question.correct_option
                bonus = Config.EASTER_EGG_BONUS

            _, is_correct = record_answer(
                session, user=user, question=question, chosen_letter=option
            )
            if bonus:
                user.points += bonus
            session.commit()

            if is_correct:
                await ctx.send(
                    embed=utils.correct_answer_embed(question, question.points, bonus),
                    ephemeral=True,
                )
            else:
                await ctx.send(
                    embed=utils.wrong_answer_embed(question, option), ephemeral=True
                )
        finally:
            session.close()

    @commands.hybrid_command(
        name="addquestion",
        description="Add a question: title | desc | category | A | B | C | D | correct",
    )
    @app_commands.describe(
        payload="Eight | -separated fields ending in the correct letter (A/B/C/D)"
    )
    async def addquestion(self, ctx: commands.Context, *, payload: str) -> None:
        parts = [p.strip() for p in payload.split("|")]
        if len(parts) != 8:
            await ctx.send(
                embed=utils.simple_embed(
                    "✋ Wrong format",
                    "Use exactly 8 `|`-separated fields:\n"
                    "`/addquestion title | desc | category | A | B | C | D | correct`",
                    utils.COLOR_RED,
                ),
                ephemeral=True,
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
                ),
                ephemeral=True,
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
                    f"Saved **{title}** as quiz #{question.id} in **{category}**. Thanks!",
                    utils.COLOR_GREEN,
                )
            )
        finally:
            session.close()

    @commands.hybrid_command(
        name="categories", description="List all quiz and resource categories."
    )
    async def categories(self, ctx: commands.Context) -> None:
        from models import Resource  # local import keeps the resource cog independent

        session = get_session()
        try:
            q_cats = [
                c[0]
                for c in session.query(Question.category)
                .distinct()
                .order_by(Question.category)
            ]
            r_cats = [
                c[0]
                for c in session.query(Resource.category)
                .distinct()
                .order_by(Resource.category)
            ]
            await ctx.send(embed=utils.categories_embed(q_cats, r_cats))
        finally:
            session.close()


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Quiz(bot))
