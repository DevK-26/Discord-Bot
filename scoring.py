"""
scoring.py
==========
Pure, side-effect-free scoring math for Tier 2. No database, no Discord — just
numbers in, numbers out — which makes everything here trivially unit-testable
(see tests/test_logic.py).

Covers:
  - difficulty-scaled points  (easy x1, medium x1.5, hard x2 by default)
  - levels from total points  (level = floor(sqrt(points / base)))
  - level progress (for the profile progress bar)
  - daily streak advancement + the streak bonus
"""

from __future__ import annotations

import math
from datetime import date

from config import Config


# --- Difficulty-scaled scoring ---------------------------------------------


def difficulty_multiplier(difficulty: str | None) -> float:
    """Return the point multiplier for a difficulty (defaults to 1.0)."""
    if not difficulty:
        return 1.0
    return Config.DIFFICULTY_MULTIPLIERS.get(difficulty.lower(), 1.0)


def points_for(base_points: int, difficulty: str | None) -> int:
    """Difficulty-scaled point value for answering a question correctly."""
    return round(base_points * difficulty_multiplier(difficulty))


# --- Levels -----------------------------------------------------------------


def level_for_points(points: int) -> int:
    """Level = floor(sqrt(points / base)). Level 0 until the first threshold."""
    if points <= 0:
        return 0
    return int(math.isqrt(points // Config.LEVEL_POINTS_BASE))


def points_for_level(level: int) -> int:
    """Minimum total points required to *be* at a given level."""
    return level * level * Config.LEVEL_POINTS_BASE


def level_progress(points: int) -> tuple[int, int, int]:
    """Return (into_level, span, next_level_points) for a progress bar.

    into_level  = points earned since reaching the current level
    span        = points between the current and next level
    next_points = absolute points needed to reach the next level
    """
    level = level_for_points(points)
    floor_pts = points_for_level(level)
    next_pts = points_for_level(level + 1)
    return points - floor_pts, next_pts - floor_pts, next_pts


# --- Streaks ----------------------------------------------------------------


def next_streak(last_daily: date | None, current_streak: int, today: date) -> int:
    """Compute the new streak when a daily is completed `today`.

    - No history (or a gap of more than a day): streak resets to 1.
    - Completed yesterday: streak increments.
    - Completed today already: unchanged (caller normally guards this).
    """
    if last_daily is None:
        return 1
    delta = (today - last_daily).days
    if delta == 1:
        return current_streak + 1
    if delta == 0:
        return current_streak or 1
    return 1  # missed one or more days (or a clock went backwards)


def streak_bonus(streak: int) -> int:
    """Bonus points for a daily, scaling with streak length but capped."""
    if streak <= 0:
        return 0
    return min(streak * Config.STREAK_BONUS_PER_DAY, Config.STREAK_BONUS_CAP)
