"""
services.py
===========
Higher-level operations that tie the models + scoring + achievements together.

``process_answer`` is the single source of truth for "what happens when someone
answers a question". Both the answer buttons (views.py) and the /answer text
fallback (cogs/quiz.py) call it, so scoring, streaks, and achievements behave
identically everywhere.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone

import achievements as ach
import scoring
from config import Config
from models import Achievement, Answer, Question, User


def _utc_today():
    return datetime.now(timezone.utc).date()


@dataclass
class AnswerOutcome:
    """Everything the UI needs to render feedback after an answer."""

    status: str  # "ok" or "already"
    is_correct: bool = False
    base_points: int = 0
    egg_bonus: int = 0
    streak_bonus: int = 0
    total_awarded: int = 0
    counted_daily: bool = False
    current_streak: int = 0
    old_level: int = 0
    new_level: int = 0
    leveled_up: bool = False
    new_achievements: list[Achievement] = field(default_factory=list)
    existing_letter: str | None = None


def process_answer(
    session,
    *,
    user: User,
    question: Question,
    chosen_letter: str,
    is_daily: bool = False,
    is_easter_egg: bool = False,
) -> AnswerOutcome:
    """Score an answer, update the user, grant achievements. Caller commits."""
    # One scored attempt per user per question.
    existing = (
        session.query(Answer)
        .filter_by(user_id=user.id, question_id=question.id)
        .first()
    )
    if existing is not None:
        return AnswerOutcome(
            status="already",
            existing_letter=existing.answer_text,
            current_streak=user.current_streak or 0,
        )

    old_level = scoring.level_for_points(user.points or 0)

    # Easter egg: the lucky user's pick is auto-corrected before scoring.
    effective = question.correct_option if is_easter_egg else chosen_letter
    is_correct = effective.strip().upper() == question.correct_option.upper()

    base_points = scoring.points_for(question.points, question.difficulty) if is_correct else 0
    egg_bonus = Config.EASTER_EGG_BONUS if (is_easter_egg and is_correct) else 0

    streak_bonus = 0
    counted_daily = False
    if is_daily:
        today = _utc_today()
        # Only the FIRST daily completion each day advances the streak / pays a
        # bonus — this stops anyone re-rolling /daily to farm bonuses.
        if user.last_daily_date != today:
            new_streak = scoring.next_streak(
                user.last_daily_date, user.current_streak or 0, today
            )
            user.current_streak = new_streak
            user.longest_streak = max(user.longest_streak or 0, new_streak)
            user.last_daily_date = today
            counted_daily = True
            if is_correct:
                streak_bonus = scoring.streak_bonus(new_streak)

    total = base_points + egg_bonus + streak_bonus

    session.add(
        Answer(
            question_id=question.id,
            user_id=user.id,
            answer_text=chosen_letter.strip().upper()[:1],
            is_correct=is_correct,
            points_awarded=total,
        )
    )
    user.total_answers = (user.total_answers or 0) + 1
    if is_correct:
        user.correct_answers = (user.correct_answers or 0) + 1
    user.points = (user.points or 0) + total
    session.flush()  # so achievement predicates see fresh counters

    new_level = scoring.level_for_points(user.points)
    new_achievements = ach.evaluate_and_grant(session, user)

    return AnswerOutcome(
        status="ok",
        is_correct=is_correct,
        base_points=base_points,
        egg_bonus=egg_bonus,
        streak_bonus=streak_bonus,
        total_awarded=total,
        counted_daily=counted_daily,
        current_streak=user.current_streak or 0,
        old_level=old_level,
        new_level=new_level,
        leveled_up=new_level > old_level,
        new_achievements=new_achievements,
    )
