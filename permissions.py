"""
permissions.py
==============
Centralized moderator check used by every admin/mod command (Tier 3).

A member is treated as a moderator if **any** of these hold:
  1. They have the Manage Server (or Administrator) permission.
  2. They have the per-guild admin role configured via /config (GuildConfig).
  3. They have the global fallback role named by ADMIN_ROLE_NAME.
"""

from __future__ import annotations

import discord
from discord.ext import commands

from config import Config
from db import get_guild_config, get_session


def _guild_admin_role_id(guild_id) -> str | None:
    """The admin role id configured for this guild via /config, if any."""
    session = get_session()
    try:
        cfg = get_guild_config(session, guild_id)
        return cfg.admin_role_id if cfg else None
    finally:
        session.close()


def is_mod(member: discord.Member | None, guild: discord.Guild | None) -> bool:
    """True if the member should be allowed to run mod commands in this guild."""
    if member is None or guild is None:
        return False

    perms = getattr(member, "guild_permissions", None)
    if perms is not None and (perms.manage_guild or perms.administrator):
        return True

    roles = getattr(member, "roles", []) or []

    role_id = _guild_admin_role_id(guild.id)
    if role_id and any(str(r.id) == str(role_id) for r in roles):
        return True

    if Config.ADMIN_ROLE_NAME and any(r.name == Config.ADMIN_ROLE_NAME for r in roles):
        return True

    return False


def mod_only():
    """A command check (works on hybrid prefix + slash) gating mod commands."""

    async def predicate(ctx: commands.Context) -> bool:
        if is_mod(ctx.author, ctx.guild):
            return True
        # Raised as CheckFailure -> handled by the global error handlers.
        raise commands.CheckFailure("Moderator permission required.")

    return commands.check(predicate)
