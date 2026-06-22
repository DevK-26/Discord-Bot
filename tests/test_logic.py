"""
tests/test_logic.py
====================
A minimal pytest suite for the pure logic that doesn't need a live Discord
connection. Run with:

    pytest

Today this covers answer-checking and the accuracy calculation. As later tiers
add streak and level functions, add their tests here too.
"""

import pytest

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
