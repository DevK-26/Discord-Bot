"""
views.py
========
Interactive Discord UI components.

``AnswerView`` is the Tier 1 headline feature: instead of typing
``!answer 3 B``, members click an A/B/C/D button under the question. Each click
is checked for the *clicking* user, scored, recorded, and answered **ephemerally**
so nobody else sees whether they were right. When the timer runs out the buttons
disable and the embed reveals the correct option.
"""

from __future__ import annotations

import logging

import discord

import utils
from config import Config
from db import get_or_create_user, get_session, record_answer
from models import Answer, Question

log = logging.getLogger("codesensei.views")


class AnswerView(discord.ui.View):
    """Four buttons (A/B/C/D) attached to a posted question."""

    def __init__(self, question: Question, *, timeout: float | None = None):
        super().__init__(
            timeout=timeout if timeout is not None else Config.ANSWER_TIMEOUT
        )
        # Store only plain values — the ORM object would become detached once
        # its session closes, so we keep what we need as simple attributes.
        self.question_id = question.id
        self.correct_option = question.correct_option
        self.correct_text = question.option_text(question.correct_option)
        # Set by the command after the message is sent, so on_timeout can edit it.
        self.message: discord.Message | None = None

    async def _answer(self, interaction: discord.Interaction, letter: str) -> None:
        """Shared handler for all four buttons."""
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

            # One scored attempt per user per question — no farming / brute-forcing.
            existing = (
                session.query(Answer)
                .filter_by(user_id=user.id, question_id=question.id)
                .first()
            )
            if existing is not None:
                await interaction.response.send_message(
                    embed=utils.simple_embed(
                        "📝 Already answered",
                        f"You already answered this one (you chose **{existing.answer_text}**).",
                        utils.COLOR_GOLD,
                    ),
                    ephemeral=True,
                )
                return

            # --- Easter egg: one lucky user is always auto-corrected + bonus ---
            bonus = 0
            chosen = letter
            if (
                Config.EASTER_EGG_USER_ID
                and str(interaction.user.id) == Config.EASTER_EGG_USER_ID
            ):
                chosen = question.correct_option
                bonus = Config.EASTER_EGG_BONUS

            _, is_correct = record_answer(
                session, user=user, question=question, chosen_letter=chosen
            )
            if bonus:
                user.points += bonus
            session.commit()

            if is_correct:
                await interaction.response.send_message(
                    embed=utils.correct_answer_embed(question, question.points, bonus),
                    ephemeral=True,
                )
            else:
                await interaction.response.send_message(
                    embed=utils.wrong_answer_embed(question, letter),
                    ephemeral=True,
                )
        except Exception:  # never let a UI click crash silently
            log.exception("Error handling answer button")
            if not interaction.response.is_done():
                await interaction.response.send_message(
                    "💥 Something went wrong handling your answer.", ephemeral=True
                )
        finally:
            session.close()

    # Each button just forwards its letter to the shared handler.
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
            # Message may have been deleted; nothing we can do, and it's harmless.
            pass
