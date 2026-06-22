"""
models.py
=========
The SQLAlchemy ORM models — the shape of our database.

CodeSensei stores four kinds of things:
  - User      : one row per Discord member who has interacted with the bot
  - Question  : an MCQ quiz question with four options and a correct answer
  - Answer    : a record of one user answering one question
  - Resource  : a saved dev resource (link) that anyone can fetch at random

These classes use the SQLAlchemy 2.x "Mapped / mapped_column" typing style,
which is the modern, type-hint-friendly way to declare models.
"""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from db import Base


def _utcnow() -> datetime:
    """Timezone-aware 'now' in UTC. Used as the default for created_at columns."""
    return datetime.now(timezone.utc)


class User(Base):
    """A community member tracked by the bot."""

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)

    # Discord IDs are 64-bit numbers, but we store them as strings so we never
    # lose precision and never have to worry about integer overflow.
    discord_id: Mapped[str] = mapped_column(String(32), unique=True, index=True)
    username: Mapped[str] = mapped_column(String(100))

    # Gamification stats.
    points: Mapped[int] = mapped_column(Integer, default=0)
    correct_answers: Mapped[int] = mapped_column(Integer, default=0)
    total_answers: Mapped[int] = mapped_column(Integer, default=0)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)

    # One user has many answers. back_populates wires up the two-way link.
    answers: Mapped[list[Answer]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )

    @property
    def accuracy(self) -> float:
        """Percentage of answers that were correct (0.0 if they've never answered)."""
        if self.total_answers <= 0:  # guard against divide-by-zero
            return 0.0
        return (self.correct_answers / self.total_answers) * 100


class Question(Base):
    """A single multiple-choice quiz question."""

    __tablename__ = "questions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    title: Mapped[str] = mapped_column(String(200))
    description: Mapped[str] = mapped_column(Text)
    category: Mapped[str] = mapped_column(String(50), index=True)
    difficulty: Mapped[str] = mapped_column(String(20), default="medium")

    # The four options. Stored as text so long code snippets fit comfortably.
    option_a: Mapped[str] = mapped_column(Text)
    option_b: Mapped[str] = mapped_column(Text)
    option_c: Mapped[str] = mapped_column(Text)
    option_d: Mapped[str] = mapped_column(Text)

    # Exactly one of "A" / "B" / "C" / "D".
    correct_option: Mapped[str] = mapped_column(String(1))

    points: Mapped[int] = mapped_column(Integer, default=10)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    # Discord ID of whoever added the question (or "system" for seeded ones).
    asked_by: Mapped[str] = mapped_column(String(32), default="system")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)

    answers: Mapped[list[Answer]] = relationship(
        back_populates="question", cascade="all, delete-orphan"
    )

    def option_text(self, letter: str) -> str:
        """Return the option text for a given letter, e.g. option_text('C')."""
        return getattr(self, f"option_{letter.lower()}", "")


class Answer(Base):
    """A record that user X answered question Y with some choice."""

    __tablename__ = "answers"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    question_id: Mapped[int] = mapped_column(ForeignKey("questions.id"))
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))

    answer_text: Mapped[str] = mapped_column(String(1))  # the letter they chose
    is_correct: Mapped[bool] = mapped_column(Boolean, default=False)
    points_awarded: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)

    question: Mapped[Question] = relationship(back_populates="answers")
    user: Mapped[User] = relationship(back_populates="answers")


class Resource(Base):
    """A shared developer resource (article, video, tool, cheat sheet, ...)."""

    __tablename__ = "resources"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    title: Mapped[str] = mapped_column(String(200))
    url: Mapped[str] = mapped_column(String(500))
    category: Mapped[str] = mapped_column(String(50), index=True)

    # Optional bits of metadata.
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    tags: Mapped[str | None] = mapped_column(String(255), nullable=True)  # CSV

    added_by: Mapped[str] = mapped_column(String(32), default="system")
    upvotes: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)
