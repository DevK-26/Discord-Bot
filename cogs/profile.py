"""
cogs/profile.py
===============
Progress-tracking cog: a rich profile embed, a quick aura readout, and the
leaderboard. Hybrid commands (slash + `!` prefix).
"""

from __future__ import annotations

import logging

import discord
from discord import app_commands
from discord.ext import commands

import utils
from config import Config
from db import get_or_create_user, get_session
from models import User

log = logging.getLogger("codesensei.profile")


class Profile(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @commands.hybrid_command(
        name="profile", description="Show a learner's points, accuracy, and stats."
    )
    @app_commands.describe(member="Whose profile to show (defaults to you)")
    async def profile(
        self, ctx: commands.Context, member: discord.Member | None = None
    ) -> None:
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

    # Command name comes from CURRENCY_NAME so it stays in sync with the theme.
    @commands.hybrid_command(
        name=Config.CURRENCY_NAME,
        aliases=["points"],
        description=f"Quick readout of someone's {Config.CURRENCY_NAME}.",
    )
    @app_commands.describe(member="Whose total to show (defaults to you)")
    async def aura(
        self, ctx: commands.Context, member: discord.Member | None = None
    ) -> None:
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

    @commands.hybrid_command(
        name="leaderboard",
        aliases=["lb", "top"],
        description="Show the top 10 learners by points.",
    )
    async def leaderboard(self, ctx: commands.Context) -> None:
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


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Profile(bot))
