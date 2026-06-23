"""
achievements.py
===============
The badge catalog and the logic that grants badges.

Each achievement has a stable `key`, a display name + emoji, a description, and
a predicate ``check(user, session) -> bool`` that says whether the user now
qualifies. Granting is idempotent: a badge is only ever awarded once per user.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from sqlalchemy.orm import Session

import scoring
from models import Achievement, Question, Resource, User, UserAchievement


@dataclass(frozen=True)
class Badge:
    key: str
    name: str
    emoji: str
    description: str
    check: Callable[[User, Session], bool]


# The full catalog. Add new badges here — migrate.py / seed.py sync them to the DB.
CATALOG: list[Badge] = [
    Badge("first_correct", "First Blood", "🩸", "Answer your first question correctly.",
          lambda u, s: (u.correct_answers or 0) >= 1),
    Badge("correct_10", "Getting Warmed Up", "🔥", "Get 10 correct answers.",
          lambda u, s: (u.correct_answers or 0) >= 10),
    Badge("correct_50", "Quiz Adept", "🎯", "Get 50 correct answers.",
          lambda u, s: (u.correct_answers or 0) >= 50),
    Badge("correct_100", "Quiz Master", "🏅", "Get 100 correct answers.",
          lambda u, s: (u.correct_answers or 0) >= 100),
    Badge("streak_3", "On a Roll", "📈", "Reach a 3-day daily streak.",
          lambda u, s: (u.current_streak or 0) >= 3),
    Badge("streak_7", "Week Warrior", "🗓️", "Reach a 7-day daily streak.",
          lambda u, s: (u.current_streak or 0) >= 7),
    Badge("level_5", "Apprentice", "⭐", "Reach level 5.",
          lambda u, s: scoring.level_for_points(u.points or 0) >= 5),
    Badge("level_10", "Sensei in Training", "🌟", "Reach level 10.",
          lambda u, s: scoring.level_for_points(u.points or 0) >= 10),
    Badge("contributor_5", "Contributor", "✍️", "Add 5 quiz questions.",
          lambda u, s: s.query(Question).filter_by(asked_by=u.discord_id).count() >= 5),
    Badge("sharer_5", "Resourceful", "📚", "Add 5 resources.",
          lambda u, s: s.query(Resource).filter_by(added_by=u.discord_id).count() >= 5),
]

# Quick lookup by key.
_BY_KEY: dict[str, Badge] = {b.key: b for b in CATALOG}


def sync_achievements(session: Session) -> int:
    """Ensure every catalog badge has a row in the achievements table.

    Returns how many new rows were created. Caller commits.
    """
    existing = {a.key for a in session.query(Achievement).all()}
    created = 0
    for badge in CATALOG:
        if badge.key not in existing:
            session.add(
                Achievement(
                    key=badge.key,
                    name=badge.name,
                    emoji=badge.emoji,
                    description=badge.description,
                )
            )
            created += 1
    session.flush()
    return created


def _get_or_create_row(session: Session, badge: Badge) -> Achievement:
    """Fetch the Achievement row for a badge, creating it on the fly if needed."""
    row = session.query(Achievement).filter_by(key=badge.key).first()
    if row is None:
        row = Achievement(
            key=badge.key, name=badge.name, emoji=badge.emoji, description=badge.description
        )
        session.add(row)
        session.flush()
    return row


def earned_for(session: Session, user: User) -> list[Achievement]:
    """Return the Achievement rows a user has earned, in catalog order."""
    rows = (
        session.query(Achievement)
        .join(UserAchievement, UserAchievement.achievement_id == Achievement.id)
        .filter(UserAchievement.user_id == user.id)
        .all()
    )
    order = {b.key: i for i, b in enumerate(CATALOG)}
    return sorted(rows, key=lambda a: order.get(a.key, 999))


def evaluate_and_grant(session: Session, user: User) -> list[Achievement]:
    """Check every badge's predicate and grant any newly-qualified ones.

    Returns the list of *newly* earned Achievement rows (empty if none). Should
    be called after the user's stats have been flushed. Caller commits.
    """
    earned_keys = {
        a.key
        for a in session.query(Achievement.key)
        .join(UserAchievement, UserAchievement.achievement_id == Achievement.id)
        .filter(UserAchievement.user_id == user.id)
    }

    newly: list[Achievement] = []
    for badge in CATALOG:
        if badge.key in earned_keys:
            continue
        if badge.check(user, session):
            row = _get_or_create_row(session, badge)
            session.add(UserAchievement(user_id=user.id, achievement_id=row.id))
            newly.append(row)
    if newly:
        session.flush()
    return newly
