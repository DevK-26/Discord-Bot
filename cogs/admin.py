"""
cogs/admin.py
=============
Utility / owner cog: the `/help` guide and an owner-only `!sync` command for
manually re-syncing slash commands during development (handy after you add or
rename a command and don't want to restart with a fresh guild sync).

NOTE: this is the cog used by the running bot. The separate top-level
``admin.py`` (init/stats/reset) is an offline CLI tool — different file, no clash.
"""

from __future__ import annotations

import logging

import discord
from discord.ext import commands

import utils
from config import Config

log = logging.getLogger("codesensei.admin")


class Admin(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @commands.hybrid_command(name="help", description="Show the command guide.")
    async def help_command(self, ctx: commands.Context) -> None:
        await ctx.send(embed=utils.help_embed())

    @commands.command(name="sync")
    @commands.is_owner()
    async def sync(self, ctx: commands.Context) -> None:
        """(Owner only, prefix only) Re-sync slash commands to this guild."""
        if Config.GUILD_ID:
            guild = discord.Object(id=int(Config.GUILD_ID))
            self.bot.tree.copy_global_to(guild=guild)
            synced = await self.bot.tree.sync(guild=guild)
            await ctx.send(f"✅ Synced {len(synced)} command(s) to this guild.")
        else:
            synced = await self.bot.tree.sync()
            await ctx.send(
                f"✅ Globally synced {len(synced)} command(s) (may take ~1h to appear)."
            )


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Admin(bot))
