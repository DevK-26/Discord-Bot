"""
cogs/events.py
==============
Cross-cutting listeners: ready/presence, the @-mention responder, and the global
error handlers for both prefix commands and slash (app) commands.

Important: the mention handler is a *listener* (added alongside the default
``on_message``), so the framework still processes commands automatically — we
must NOT call ``process_commands`` ourselves here, or commands would run twice.
"""

from __future__ import annotations

import logging

import discord
from discord import app_commands
from discord.ext import commands

import utils
from config import Config

log = logging.getLogger("codesensei.events")


class Events(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        # Route slash-command errors through our handler too.
        bot.tree.on_error = self.on_app_command_error

    # --- Lifecycle ----------------------------------------------------------

    @commands.Cog.listener()
    async def on_ready(self) -> None:
        log.info(
            "%s is online as %s (id: %s)",
            Config.BOT_NAME,
            self.bot.user,
            self.bot.user.id if self.bot.user else "?",
        )
        await self.bot.change_presence(
            activity=discord.Game(name="/help • teaching code")
        )

    # --- Mention responder --------------------------------------------------

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message) -> None:
        if message.author.bot:
            return
        if self.bot.user in message.mentions and not message.mention_everyone:
            await message.channel.send(
                embed=utils.simple_embed(
                    f"👋 Hey {message.author.display_name}!",
                    utils.random_mention_line(),
                    utils.COLOR_BLUE,
                )
            )
        # No process_commands() here — the default on_message already does it.

    # --- Error handlers -----------------------------------------------------

    @commands.Cog.listener()
    async def on_command_error(
        self, ctx: commands.Context, error: commands.CommandError
    ) -> None:
        """Friendly handling of *prefix* command errors."""
        error = getattr(error, "original", error)

        if isinstance(error, commands.CommandNotFound):
            await self._reply(
                ctx,
                "🤔 Unknown command",
                f"I don't know that one. Try `/help` to see what I can do!",
            )
        elif isinstance(error, commands.MissingRequiredArgument):
            await self._reply(
                ctx,
                "✋ Missing something",
                f"You left out `{error.param.name}`. Check `/help` for the format.",
            )
        elif isinstance(error, commands.BadArgument):
            await self._reply(
                ctx,
                "⚠️ That didn't look right",
                "One of your arguments was the wrong type. See `/help` for examples.",
            )
        elif isinstance(error, commands.CommandOnCooldown):
            await self._reply(
                ctx,
                "⏳ Slow down a sec",
                f"Try again in {error.retry_after:.1f}s.",
            )
        elif isinstance(error, (commands.MissingPermissions, commands.NotOwner, commands.CheckFailure)):
            await self._reply(
                ctx, "🔒 No permission", "You can't use that command."
            )
        else:
            log.exception("Unhandled prefix error in %s", ctx.command, exc_info=error)
            await self._reply(
                ctx, "💥 Something went wrong", "I hit an unexpected snag — try again!"
            )

    async def on_app_command_error(
        self, interaction: discord.Interaction, error: app_commands.AppCommandError
    ) -> None:
        """Friendly handling of *slash* command errors (always ephemeral)."""
        error = getattr(error, "original", error)

        if isinstance(error, app_commands.CommandOnCooldown):
            title, msg = "⏳ Slow down a sec", f"Try again in {error.retry_after:.1f}s."
        elif isinstance(error, (app_commands.MissingPermissions, app_commands.CheckFailure)):
            title, msg = "🔒 No permission", "You can't use that command."
        else:
            log.exception("Unhandled app-command error", exc_info=error)
            title, msg = "💥 Something went wrong", "I hit an unexpected snag — try again!"

        embed = utils.simple_embed(title, msg, utils.COLOR_RED)
        # Respond or follow up depending on whether we've already replied.
        if interaction.response.is_done():
            await interaction.followup.send(embed=embed, ephemeral=True)
        else:
            await interaction.response.send_message(embed=embed, ephemeral=True)

    @staticmethod
    async def _reply(ctx: commands.Context, title: str, description: str) -> None:
        await ctx.send(embed=utils.simple_embed(title, description, utils.COLOR_RED))


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Events(bot))
