"""
views.py
========
Interactive Discord UI components.

``AnswerView`` attaches A/B/C/D buttons under a question. Each click is scored
for the *clicking* user via services.process_answer (so difficulty scaling,
streaks, easter egg, and achievements all apply), answered **ephemerally**, and —
when something public-worthy happens (level up, new badge) — announced in the
channel. When the timer runs out the buttons disable and the embed reveals the
correct option.
"""

from __future__ import annotations

import logging

import discord

import roles
import services
import utils
from config import Config
from db import get_or_create_user, get_session
from models import Question

log = logging.getLogger("codesensei.views")


def _is_easter_egg(user_id: int) -> bool:
    return bool(Config.EASTER_EGG_USER_ID) and str(user_id) == Config.EASTER_EGG_USER_ID


async def announce_extras(channel, member, guild, outcome) -> None:
    """Post public level-up / achievement messages and assign level roles."""
    if channel is None:
        return
    if outcome.leveled_up:
        role_name = await roles.maybe_grant_level_role(member, guild, outcome.new_level)
        try:
            await channel.send(
                embed=utils.levelup_embed(
                    getattr(member, "display_name", "Someone"), outcome.new_level, role_name
                )
            )
        except discord.HTTPException:
            pass
    if outcome.new_achievements:
        try:
            await channel.send(
                embed=utils.achievements_unlocked_embed(
                    getattr(member, "display_name", "Someone"), outcome.new_achievements
                )
            )
        except discord.HTTPException:
            pass


class AnswerView(discord.ui.View):
    """Four buttons (A/B/C/D) attached to a posted question."""

    def __init__(self, question: Question, *, is_daily: bool = False, timeout: float | None = None):
        super().__init__(timeout=timeout if timeout is not None else Config.ANSWER_TIMEOUT)
        self.question_id = question.id
        self.correct_option = question.correct_option
        self.correct_text = question.option_text(question.correct_option)
        self.is_daily = is_daily
        self.message: discord.Message | None = None

    async def _answer(self, interaction: discord.Interaction, letter: str) -> None:
        session = get_session()
        try:
            question = session.get(Question, self.question_id)
            if question is None or not question.is_active:
                await interaction.response.send_message(
                    "⚠️ This question is no longer available.", ephemeral=True
                )
                return

            user = get_or_create_user(
                session, interaction.user.id, interaction.user.display_name
            )
            outcome = services.process_answer(
                session,
                user=user,
                question=question,
                chosen_letter=letter,
                is_daily=self.is_daily,
                is_easter_egg=_is_easter_egg(interaction.user.id),
            )

            if outcome.status == "already":
                await interaction.response.send_message(
                    embed=utils.simple_embed(
                        "📝 Already answered",
                        f"You already answered this one (you chose **{outcome.existing_letter}**).",
                        utils.COLOR_GOLD,
                    ),
                    ephemeral=True,
                )
                return

            session.commit()

            # Private result to the clicker.
            await interaction.response.send_message(
                embed=utils.answer_feedback_embed(question, letter, outcome),
                ephemeral=True,
            )
            # Public extras (level up, badges) + role assignment.
            await announce_extras(
                interaction.channel, interaction.user, interaction.guild, outcome
            )
        except Exception:
            log.exception("Error handling answer button")
            if not interaction.response.is_done():
                await interaction.response.send_message(
                    "💥 Something went wrong handling your answer.", ephemeral=True
                )
        finally:
            session.close()

    @discord.ui.button(label="A", style=discord.ButtonStyle.primary)
    async def btn_a(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._answer(interaction, "A")

    @discord.ui.button(label="B", style=discord.ButtonStyle.primary)
    async def btn_b(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._answer(interaction, "B")

    @discord.ui.button(label="C", style=discord.ButtonStyle.primary)
    async def btn_c(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._answer(interaction, "C")

    @discord.ui.button(label="D", style=discord.ButtonStyle.primary)
    async def btn_d(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._answer(interaction, "D")

    async def on_timeout(self) -> None:
        """Disable the buttons and reveal the correct answer on the message."""
        for child in self.children:
            child.disabled = True
        if self.message is None:
            return
        try:
            embed = self.message.embeds[0] if self.message.embeds else None
            if embed is not None:
                embed.add_field(
                    name="⏰ Time's up — correct answer",
                    value=f"**{self.correct_option}** — {self.correct_text}",
                    inline=False,
                )
                embed.color = utils.COLOR_GOLD
            await self.message.edit(embed=embed, view=self)
        except discord.HTTPException:
            pass
