"""
tests/test_logic.py
====================
A minimal pytest suite for the pure logic that doesn't need a live Discord
connection. Run with:

    pytest

Today this covers answer-checking and the accuracy calculation. As later tiers
add streak and level functions, add their tests here too.
"""

from datetime import date

import pytest

import scoring
import utils
from models import Question, User


def make_question(correct="B"):
    return Question(
        title="t",
        description="d",
        category="DSA",
        option_a="a",
        option_b="b",
        option_c="c",
        option_d="d",
        correct_option=correct,
        points=10,
    )


@pytest.mark.parametrize(
    "chosen,expected",
    [("B", True), ("b", True), (" b ", True), ("A", False), ("d", False)],
)
def test_check_answer_is_case_and_space_insensitive(chosen, expected):
    q = make_question(correct="B")
    assert utils.check_answer(q, chosen) is expected


def test_accuracy_normal():
    u = User(discord_id="1", username="x", correct_answers=3, total_answers=4)
    assert u.accuracy == pytest.approx(75.0)


def test_accuracy_zero_guard():
    # No answers yet must not divide by zero.
    u = User(discord_id="2", username="y", correct_answers=0, total_answers=0)
    assert u.accuracy == 0.0


def test_option_text_lookup():
    q = make_question(correct="C")
    assert q.option_text("C") == "c"
    assert q.option_text("a") == "a"  # case-insensitive


# --- Tier 2: difficulty-scaled scoring -------------------------------------


@pytest.mark.parametrize(
    "difficulty,expected",
    [("easy", 10), ("medium", 15), ("hard", 20), ("EASY", 10), (None, 10), ("weird", 10)],
)
def test_points_for_difficulty(difficulty, expected):
    assert scoring.points_for(10, difficulty) == expected


# --- Tier 2: levels ---------------------------------------------------------


@pytest.mark.parametrize(
    "points,level",
    [(0, 0), (50, 0), (99, 0), (100, 1), (399, 1), (400, 2), (900, 3), (10000, 10)],
)
def test_level_for_points(points, level):
    assert scoring.level_for_points(points) == level


def test_points_for_level_inverse():
    assert scoring.points_for_level(3) == 900
    assert scoring.level_for_points(scoring.points_for_level(5)) == 5


def test_level_progress():
    into, span, next_pts = scoring.level_progress(150)  # level 1 (100..400)
    assert into == 50
    assert span == 300
    assert next_pts == 400


# --- Tier 2: streaks --------------------------------------------------------


def test_next_streak_first_time():
    assert scoring.next_streak(None, 0, date(2026, 1, 10)) == 1


def test_next_streak_consecutive_day():
    assert scoring.next_streak(date(2026, 1, 9), 4, date(2026, 1, 10)) == 5


def test_next_streak_same_day_unchanged():
    assert scoring.next_streak(date(2026, 1, 10), 4, date(2026, 1, 10)) == 4


def test_next_streak_gap_resets():
    assert scoring.next_streak(date(2026, 1, 5), 9, date(2026, 1, 10)) == 1


@pytest.mark.parametrize(
    "streak,bonus",
    [(0, 0), (1, 5), (5, 25), (10, 50), (20, 50)],  # capped at 50 by default
)
def test_streak_bonus_scales_and_caps(streak, bonus):
    assert scoring.streak_bonus(streak) == bonus
