"""
roles.py
========
Optional level -> Discord role auto-assignment (Tier 2.3).

Configured via the LEVEL_ROLES env var, e.g. `1:Novice,5:Adept,10:Sensei`.
When a member reaches a new level, the bot assigns the role for the highest
threshold they've passed (creating it if needed). Everything here is
best-effort: if LEVEL_ROLES is empty or the bot lacks Manage Roles, it quietly
does nothing.
"""

from __future__ import annotations

import logging

import discord

from config import Config

log = logging.getLogger("codesensei.roles")


def _role_name_for_level(level: int) -> str | None:
    """The configured role for the highest threshold <= level, if any."""
    eligible = [lvl for lvl in Config.LEVEL_ROLES if lvl <= level]
    if not eligible:
        return None
    return Config.LEVEL_ROLES[max(eligible)]


async def maybe_grant_level_role(
    member: discord.Member | None, guild: discord.Guild | None, level: int
) -> str | None:
    """Assign the level role to a member. Returns the role name if granted."""
    if not Config.LEVEL_ROLES or member is None or guild is None:
        return None

    role_name = _role_name_for_level(level)
    if role_name is None:
        return None

    # Need Manage Roles to create/assign.
    me = guild.me
    if me is None or not me.guild_permissions.manage_roles:
        log.debug("Skipping level role %r — missing Manage Roles", role_name)
        return None

    role = discord.utils.get(guild.roles, name=role_name)
    try:
        if role is None:
            role = await guild.create_role(name=role_name, reason="CodeSensei level role")
        if role in member.roles:
            return None  # already has it
        # Can't assign a role at/above the bot's top role.
        if role >= me.top_role:
            log.debug("Skipping level role %r — above bot's top role", role_name)
            return None
        await member.add_roles(role, reason=f"Reached level {level}")
        return role.name
    except discord.Forbidden:
        log.warning("Forbidden assigning level role %r", role_name)
    except discord.HTTPException:
        log.exception("Failed assigning level role %r", role_name)
    return None
