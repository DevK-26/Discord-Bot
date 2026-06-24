"""
cogs/quiz.py
============
The quiz cog: asking questions (with clickable answer buttons), the daily
challenge, a type-based answer fallback, adding questions, and listing
categories. All commands are **hybrid** (slash `/ask` + legacy `!ask`).
"""

from __future__ import annotations

import logging

import discord
from discord import app_commands
from discord.ext import commands
from sqlalchemy import func

import services
import utils
from config import Config
from db import add_question, get_or_create_user, get_session
from models import Answer, Question
from pagination import Paginator
from views import AnswerView, announce_extras, _is_easter_egg

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
    @commands.cooldown(1, Config.ASK_COOLDOWN_SECONDS, commands.BucketType.user)
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
            view = AnswerView(question)
            message = await ctx.send(embed=utils.question_embed(question), view=view)
            view.message = message
        finally:
            session.close()

    @commands.hybrid_command(
        name="daily", description="Your once-a-day challenge — keep your streak alive!"
    )
    async def daily(self, ctx: commands.Context) -> None:
        session = get_session()
        try:
            user = get_or_create_user(session, ctx.author.id, ctx.author.display_name)
            session.commit()

            from datetime import datetime, timezone

            today = datetime.now(timezone.utc).date()
            if user.last_daily_date == today:
                await ctx.send(
                    embed=utils.daily_done_embed(user.current_streak or 0), ephemeral=True
                )
                return

            # Pick a random active question the user hasn't answered yet.
            answered = session.query(Answer.question_id).filter_by(user_id=user.id)
            question = (
                session.query(Question)
                .filter(Question.is_active.is_(True), ~Question.id.in_(answered))
                .order_by(func.random())
                .first()
            )
            if question is None:
                await ctx.send(
                    embed=utils.simple_embed(
                        "🎉 You've answered them all!",
                        "There are no new questions left for your daily right now. "
                        "Add more with `/addquestion` or check back later!",
                        utils.COLOR_GREEN,
                    ),
                    ephemeral=True,
                )
                return

            view = AnswerView(question, is_daily=True)
            message = await ctx.send(
                embed=utils.question_embed(question, is_daily=True), view=view
            )
            view.message = message
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
            outcome = services.process_answer(
                session,
                user=user,
                question=question,
                chosen_letter=option,
                is_easter_egg=_is_easter_egg(ctx.author.id),
            )
            if outcome.status == "already":
                await ctx.send(
                    embed=utils.simple_embed(
                        "📝 Already answered",
                        f"You already answered #{question.id} (you chose "
                        f"**{outcome.existing_letter}**). Try a new one with `/ask`!",
                        utils.COLOR_GOLD,
                    ),
                    ephemeral=True,
                )
                return

            session.commit()
            await ctx.send(
                embed=utils.answer_feedback_embed(question, option, outcome),
                ephemeral=True,
            )
            await announce_extras(ctx.channel, ctx.author, ctx.guild, outcome)
        finally:
            session.close()

    @commands.hybrid_command(
        name="addquestion",
        description="Add a question: title | desc | category | A | B | C | D | correct | [explanation]",
    )
    @app_commands.describe(
        payload="8 | -separated fields ending in the correct letter, plus an optional 9th explanation"
    )
    async def addquestion(self, ctx: commands.Context, *, payload: str) -> None:
        parts = [p.strip() for p in payload.split("|")]
        # 8 fields required; an optional 9th field is the explanation.
        if len(parts) not in (8, 9):
            await ctx.send(
                embed=utils.simple_embed(
                    "✋ Wrong format",
                    "Use 8 `|`-separated fields (with an optional 9th explanation):\n"
                    "`/addquestion title | desc | category | A | B | C | D | correct | [explanation]`",
                    utils.COLOR_RED,
                ),
                ephemeral=True,
            )
            return

        title, desc, category, opt_a, opt_b, opt_c, opt_d, correct = parts[:8]
        explanation = parts[8] if len(parts) == 9 and parts[8] else None
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
                explanation=explanation,
                asked_by=str(ctx.author.id),
            )
            # Adding content can unlock the "Contributor" badge.
            user = get_or_create_user(session, ctx.author.id, ctx.author.display_name)
            session.flush()
            import achievements as ach

            new_badges = ach.evaluate_and_grant(session, user)
            session.commit()
            await ctx.send(
                embed=utils.simple_embed(
                    "✅ Question added!",
                    f"Saved **{title}** as quiz #{question.id} in **{category}**. Thanks!",
                    utils.COLOR_GREEN,
                )
            )
            if new_badges:
                await announce_extras(
                    ctx.channel,
                    ctx.author,
                    ctx.guild,
                    services.AnswerOutcome(status="ok", new_achievements=new_badges),
                )
        finally:
            session.close()

    @commands.hybrid_command(
        name="categories", description="List all quiz and resource categories."
    )
    async def categories(self, ctx: commands.Context) -> None:
        from models import Resource

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

    @commands.hybrid_command(
        name="questions", description="Browse the question bank (paginated)."
    )
    @app_commands.describe(category="Optional category to filter by")
    @app_commands.autocomplete(category=question_category_autocomplete)
    async def questions(self, ctx: commands.Context, category: str | None = None) -> None:
        session = get_session()
        try:
            from sqlalchemy import func as _func

            query = session.query(Question).filter(Question.is_active.is_(True))
            if category:
                query = query.filter(
                    _func.lower(Question.category) == category.lower()
                )
            rows = query.order_by(Question.id).all()
        finally:
            session.close()

        if not rows:
            await ctx.send(
                embed=utils.simple_embed(
                    "📭 No questions", "Nothing to browse yet. Add some with `/addquestion`!",
                    utils.COLOR_RED,
                ),
                ephemeral=True,
            )
            return

        embeds = utils.questions_browse_embeds(rows, category)
        view = Paginator(embeds, ctx.author.id)
        message = await ctx.send(embed=embeds[0], view=view)
        view.message = message


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Quiz(bot))
