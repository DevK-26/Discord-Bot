"""
cogs/moderation.py
==================
Mod-only content management (Tier 3): edit/delete questions & resources,
per-guild configuration, and data export. Every command here is gated by
``permissions.mod_only`` (Manage Server, the global mod role, or the per-guild
admin role).
"""

from __future__ import annotations

import io
import json
import logging

import discord
from discord import app_commands
from discord.ext import commands

import permissions
import utils
from db import get_or_create_guild_config, get_session
from models import Question, Resource, ResourceVote

log = logging.getLogger("codesensei.moderation")

# /editquestion field -> model attribute, with light validation.
QUESTION_FIELDS = {
    "title": "title",
    "description": "description",
    "category": "category",
    "difficulty": "difficulty",
    "explanation": "explanation",
    "points": "points",
    "a": "option_a",
    "b": "option_b",
    "c": "option_c",
    "d": "option_d",
    "correct": "correct_option",
}
RESOURCE_FIELDS = {
    "title": "title",
    "url": "url",
    "category": "category",
    "description": "description",
    "tags": "tags",
}


def _extract_id(raw: str | None) -> str | None:
    """Pull a bare numeric id out of a mention like <@&123> / <#123> / 123."""
    if not raw:
        return None
    digits = "".join(ch for ch in raw if ch.isdigit())
    return digits or None


class Moderation(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    # --- 3.1 edit / delete questions ---------------------------------------

    @commands.hybrid_command(name="editquestion", description="(Mod) Edit one field of a question.")
    @permissions.mod_only()
    @app_commands.describe(question_id="Question id", field="Which field", value="New value")
    @app_commands.choices(
        field=[app_commands.Choice(name=f, value=f) for f in QUESTION_FIELDS]
    )
    async def editquestion(
        self, ctx: commands.Context, question_id: int, field: str, *, value: str
    ) -> None:
        field = field.lower()
        if field not in QUESTION_FIELDS:
            await self._err(ctx, f"Unknown field. Pick one of: {', '.join(QUESTION_FIELDS)}.")
            return

        # Per-field validation.
        if field == "correct" and value.strip().upper() not in {"A", "B", "C", "D"}:
            await self._err(ctx, "`correct` must be A, B, C, or D.")
            return
        if field == "difficulty" and value.strip().lower() not in {"easy", "medium", "hard"}:
            await self._err(ctx, "`difficulty` must be easy, medium, or hard.")
            return
        if field == "points":
            try:
                value_conv: object = int(value)
            except ValueError:
                await self._err(ctx, "`points` must be a whole number.")
                return
        elif field == "correct":
            value_conv = value.strip().upper()
        elif field == "difficulty":
            value_conv = value.strip().lower()
        else:
            value_conv = value

        session = get_session()
        try:
            q = session.get(Question, question_id)
            if q is None:
                await self._err(ctx, f"No question #{question_id}.")
                return
            setattr(q, QUESTION_FIELDS[field], value_conv)
            session.commit()
            await ctx.send(
                embed=utils.simple_embed(
                    "✏️ Question updated",
                    f"Set **{field}** on question #{question_id}.",
                    utils.COLOR_GREEN,
                )
            )
        finally:
            session.close()

    @commands.hybrid_command(
        name="deletequestion", description="(Mod) Soft-delete a question (hide it, keep history)."
    )
    @permissions.mod_only()
    @app_commands.describe(question_id="Question id to deactivate")
    async def deletequestion(self, ctx: commands.Context, question_id: int) -> None:
        session = get_session()
        try:
            q = session.get(Question, question_id)
            if q is None:
                await self._err(ctx, f"No question #{question_id}.")
                return
            q.is_active = False  # soft delete preserves answer history
            session.commit()
            await ctx.send(
                embed=utils.simple_embed(
                    "🗑️ Question removed",
                    f"Question #{question_id} is now inactive (history preserved).",
                    utils.COLOR_GREEN,
                )
            )
        finally:
            session.close()

    # --- 3.1 edit / delete resources ---------------------------------------

    @commands.hybrid_command(name="editresource", description="(Mod) Edit one field of a resource.")
    @permissions.mod_only()
    @app_commands.describe(resource_id="Resource id", field="Which field", value="New value")
    @app_commands.choices(
        field=[app_commands.Choice(name=f, value=f) for f in RESOURCE_FIELDS]
    )
    async def editresource(
        self, ctx: commands.Context, resource_id: int, field: str, *, value: str
    ) -> None:
        field = field.lower()
        if field not in RESOURCE_FIELDS:
            await self._err(ctx, f"Unknown field. Pick one of: {', '.join(RESOURCE_FIELDS)}.")
            return
        session = get_session()
        try:
            r = session.get(Resource, resource_id)
            if r is None:
                await self._err(ctx, f"No resource #{resource_id}.")
                return
            setattr(r, RESOURCE_FIELDS[field], value)
            session.commit()
            await ctx.send(
                embed=utils.simple_embed(
                    "✏️ Resource updated",
                    f"Set **{field}** on resource #{resource_id}.",
                    utils.COLOR_GREEN,
                )
            )
        finally:
            session.close()

    @commands.hybrid_command(name="deleteresource", description="(Mod) Delete a resource.")
    @permissions.mod_only()
    @app_commands.describe(resource_id="Resource id to delete")
    async def deleteresource(self, ctx: commands.Context, resource_id: int) -> None:
        session = get_session()
        try:
            r = session.get(Resource, resource_id)
            if r is None:
                await self._err(ctx, f"No resource #{resource_id}.")
                return
            # Remove its votes first so no rows are orphaned.
            session.query(ResourceVote).filter_by(resource_id=r.id).delete()
            session.delete(r)
            session.commit()
            await ctx.send(
                embed=utils.simple_embed(
                    "🗑️ Resource deleted", f"Resource #{resource_id} is gone.", utils.COLOR_GREEN
                )
            )
        finally:
            session.close()

    # --- 3.6 per-guild config ----------------------------------------------

    @commands.hybrid_command(
        name="config", description="(Mod) View or change this server's settings."
    )
    @permissions.mod_only()
    @app_commands.describe(
        setting="Which setting to change (omit to view all)",
        value="New value (omit to clear the setting)",
    )
    @app_commands.choices(
        setting=[
            app_commands.Choice(name="prefix", value="prefix"),
            app_commands.Choice(name="admin_role", value="admin_role"),
            app_commands.Choice(name="daily_channel", value="daily_channel"),
            app_commands.Choice(name="currency_label", value="currency_label"),
            app_commands.Choice(name="level_roles", value="level_roles"),
        ]
    )
    async def config(
        self,
        ctx: commands.Context,
        setting: str | None = None,
        *,
        value: str | None = None,
    ) -> None:
        if ctx.guild is None:
            await self._err(ctx, "Configuration is per-server — run this in a server.")
            return

        session = get_session()
        try:
            cfg = get_or_create_guild_config(session, ctx.guild.id)

            if setting is None:
                await ctx.send(embed=utils.guild_config_embed(ctx.guild, cfg))
                return

            setting = setting.lower()
            if setting in {"admin_role", "daily_channel"}:
                stored = _extract_id(value)  # accept a mention or a raw id
                setattr(cfg, "admin_role_id" if setting == "admin_role" else "daily_channel_id", stored)
            elif setting in {"prefix", "currency_label", "level_roles"}:
                setattr(cfg, setting, value or None)
            else:
                await self._err(ctx, "Unknown setting.")
                return
            session.commit()
            if setting == "prefix":
                from db import invalidate_prefix_cache

                invalidate_prefix_cache(ctx.guild.id)
            await ctx.send(
                embed=utils.simple_embed(
                    "⚙️ Config updated",
                    f"**{setting}** is now: {value or '_(cleared — using default)_'}",
                    utils.COLOR_GREEN,
                )
            )
        finally:
            session.close()

    # --- 3.5 export ---------------------------------------------------------

    @commands.hybrid_command(name="export", description="(Mod) Export questions or resources as JSON.")
    @permissions.mod_only()
    @app_commands.describe(what="What to export")
    @app_commands.choices(
        what=[
            app_commands.Choice(name="questions", value="questions"),
            app_commands.Choice(name="resources", value="resources"),
        ]
    )
    async def export(self, ctx: commands.Context, what: str) -> None:
        what = what.lower()
        session = get_session()
        try:
            if what == "questions":
                rows = session.query(Question).order_by(Question.id).all()
                data = [
                    {
                        "title": q.title, "description": q.description, "category": q.category,
                        "difficulty": q.difficulty, "option_a": q.option_a, "option_b": q.option_b,
                        "option_c": q.option_c, "option_d": q.option_d,
                        "correct_option": q.correct_option, "points": q.points,
                        "explanation": q.explanation, "is_active": q.is_active,
                    }
                    for q in rows
                ]
            elif what == "resources":
                rows = session.query(Resource).order_by(Resource.id).all()
                data = [
                    {
                        "title": r.title, "url": r.url, "category": r.category,
                        "description": r.description, "tags": r.tags, "upvotes": r.upvotes,
                    }
                    for r in rows
                ]
            else:
                await self._err(ctx, "Choose `questions` or `resources`.")
                return
        finally:
            session.close()

        buf = io.BytesIO(json.dumps(data, indent=2, default=str).encode("utf-8"))
        buf.seek(0)
        await ctx.send(
            content=f"📦 Exported {len(data)} {what}.",
            file=discord.File(buf, filename=f"codesensei_{what}.json"),
        )

    # --- helper -------------------------------------------------------------

    @staticmethod
    async def _err(ctx: commands.Context, message: str) -> None:
        await ctx.send(
            embed=utils.simple_embed("⚠️ Can't do that", message, utils.COLOR_RED),
            ephemeral=True,
        )


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Moderation(bot))
