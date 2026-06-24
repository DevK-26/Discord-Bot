"""
cogs/resources.py
=================
The resource library cog: fetch a random resource and add new ones. Hybrid
commands (slash + `!` prefix), with category autocomplete on `/resource`.
"""

from __future__ import annotations

import logging

import discord
from discord import app_commands
from discord.ext import commands
from sqlalchemy import func

import achievements as ach
import services
import utils
from db import add_resource, get_or_create_user, get_session
from models import Resource, ResourceVote
from pagination import Paginator
from views import announce_extras

log = logging.getLogger("codesensei.resources")


async def resource_category_autocomplete(
    interaction: discord.Interaction, current: str
) -> list[app_commands.Choice[str]]:
    """Suggest distinct resource categories as the user types."""
    session = get_session()
    try:
        cats = [c[0] for c in session.query(Resource.category).distinct()]
    finally:
        session.close()
    current = (current or "").lower()
    return [
        app_commands.Choice(name=cat, value=cat)
        for cat in cats
        if current in cat.lower()
    ][:25]


class Resources(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @commands.hybrid_command(
        name="resource", description="Fetch a random developer resource."
    )
    @app_commands.describe(category="Optional category to filter by")
    @app_commands.autocomplete(category=resource_category_autocomplete)
    async def resource(
        self, ctx: commands.Context, category: str | None = None
    ) -> None:
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
                        f"I couldn't find a resource{where}. Add one with `/addresource`!",
                        utils.COLOR_RED,
                    ),
                    ephemeral=True,
                )
                return
            await ctx.send(embed=utils.resource_embed(item))
        finally:
            session.close()

    @commands.hybrid_command(
        name="resources",
        description="Browse resources by category/tag, sorted by top or new.",
    )
    @app_commands.describe(
        category="Filter by category", tag="Filter by tag", sort="top (most upvoted) or new"
    )
    @app_commands.autocomplete(category=resource_category_autocomplete)
    @app_commands.choices(
        sort=[
            app_commands.Choice(name="Top (most upvoted)", value="top"),
            app_commands.Choice(name="Newest", value="new"),
        ]
    )
    async def resources(
        self,
        ctx: commands.Context,
        category: str | None = None,
        tag: str | None = None,
        sort: str = "top",
    ) -> None:
        session = get_session()
        try:
            query = session.query(Resource)
            if category:
                query = query.filter(func.lower(Resource.category) == category.lower())
            if tag:
                # tags is a comma-separated string; case-insensitive substring match.
                query = query.filter(func.lower(Resource.tags).like(f"%{tag.lower()}%"))
            if sort == "new":
                query = query.order_by(Resource.created_at.desc(), Resource.id.desc())
            else:
                query = query.order_by(Resource.upvotes.desc(), Resource.id.asc())
            rows = query.all()
        finally:
            session.close()

        if not rows:
            await ctx.send(
                embed=utils.simple_embed(
                    "📭 No matching resources",
                    "Try a different category/tag, or add one with `/addresource`.",
                    utils.COLOR_RED,
                ),
                ephemeral=True,
            )
            return

        header = "Resources"
        if category:
            header += f" · {category}"
        if tag:
            header += f" · #{tag}"
        header += " · Newest" if sort == "new" else " · Top"

        embeds = utils.resources_list_embeds(rows, header)
        if len(embeds) == 1:
            await ctx.send(embed=embeds[0])
            return
        view = Paginator(embeds, ctx.author.id)
        message = await ctx.send(embed=embeds[0], view=view)
        view.message = message

    @commands.hybrid_command(
        name="upvote", description="Upvote a resource (one vote per user)."
    )
    @app_commands.describe(resource_id="The resource number to upvote")
    async def upvote(self, ctx: commands.Context, resource_id: int) -> None:
        session = get_session()
        try:
            res = session.get(Resource, resource_id)
            if res is None:
                await ctx.send(
                    embed=utils.simple_embed(
                        "🔍 Not found",
                        f"There's no resource #{resource_id}. Browse with `/resources`.",
                        utils.COLOR_RED,
                    ),
                    ephemeral=True,
                )
                return
            user = get_or_create_user(session, ctx.author.id, ctx.author.display_name)
            existing = (
                session.query(ResourceVote)
                .filter_by(resource_id=res.id, user_id=user.id)
                .first()
            )
            if existing is not None:
                await ctx.send(
                    embed=utils.simple_embed(
                        "🗳️ Already voted",
                        f"You've already upvoted **{res.title}**.",
                        utils.COLOR_GOLD,
                    ),
                    ephemeral=True,
                )
                return
            session.add(ResourceVote(resource_id=res.id, user_id=user.id))
            res.upvotes = (res.upvotes or 0) + 1
            session.commit()
            await ctx.send(
                embed=utils.simple_embed(
                    "👍 Upvoted!",
                    f"**{res.title}** now has **{res.upvotes}** upvote(s). Thanks!",
                    utils.COLOR_GREEN,
                )
            )
        finally:
            session.close()

    @commands.hybrid_command(
        name="addresource",
        description="Add a resource: title | url | category | [description]",
    )
    @app_commands.describe(
        payload="title | url | category | [description]  (3 or 4 |-separated fields)"
    )
    async def addresource(self, ctx: commands.Context, *, payload: str) -> None:
        parts = [p.strip() for p in payload.split("|")]
        if len(parts) < 3:
            await ctx.send(
                embed=utils.simple_embed(
                    "✋ Wrong format",
                    "Use at least 3 `|`-separated fields:\n"
                    "`/addresource title | url | category | [description]`",
                    utils.COLOR_RED,
                ),
                ephemeral=True,
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
            # Adding resources can unlock the "Resourceful" badge.
            user = get_or_create_user(session, ctx.author.id, ctx.author.display_name)
            session.flush()
            new_badges = ach.evaluate_and_grant(session, user)
            session.commit()
            await ctx.send(
                embed=utils.simple_embed(
                    "✅ Resource added!",
                    f"Saved **{title}** (#{item.id}) in **{category}**. Thanks! 🙌",
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


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Resources(bot))
