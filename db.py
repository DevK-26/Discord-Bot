"""
db.py
=====
Everything related to the database connection and the small set of helper
functions that the commands use to read/write data.

Design choices:
  - One SQLAlchemy `engine` for the whole process.
  - A `SessionLocal` factory; every command opens a fresh session and closes it.
  - `Base` is the declarative base that all models inherit from.
  - Helper functions (get_or_create_user, add_question, ...) keep the command
    code in bot.py short and readable.
"""

from __future__ import annotations

from contextlib import contextmanager
from typing import Iterator

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from config import Config


class Base(DeclarativeBase):
    """The shared declarative base for all ORM models."""


# SQLite needs a special flag to be usable across threads (discord.py runs
# callbacks on its event loop). For other databases we pass no extra args.
_engine_kwargs: dict = {}
if Config.DB_URL.startswith("sqlite"):
    _engine_kwargs["connect_args"] = {"check_same_thread": False}

# The single engine and session factory for the whole app.
engine = create_engine(Config.DB_URL, echo=False, future=True, **_engine_kwargs)
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def init_db() -> None:
    """Create all tables that don't exist yet. Safe to run repeatedly."""
    # Importing models here (not at top) avoids a circular import: models.py
    # imports Base from this module.
    import models  # noqa: F401  (imported for its side effect of registering tables)

    Base.metadata.create_all(bind=engine)


def get_session() -> Session:
    """Return a brand-new session. Caller is responsible for closing it.

    Commands use this directly and close in a `finally` block, e.g.:

        session = get_session()
        try:
            ...
        finally:
            session.close()
    """
    return SessionLocal()


@contextmanager
def session_scope() -> Iterator[Session]:
    """Convenience context manager used by scripts (seed.py, admin.py).

    Commits on success, rolls back on error, always closes.
    """
    session = get_session()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------
# These import models lazily inside each function for the same circular-import
# reason described in init_db().


def get_or_create_user(session: Session, discord_id: str, username: str):
    """Fetch the User row for this Discord ID, creating it on first sight.

    We also keep the stored username fresh in case the member renamed.
    The row is flushed (not committed) so it gets an `id` the caller can use;
    the caller decides when to commit.
    """
    from models import User

    user = session.query(User).filter_by(discord_id=str(discord_id)).first()
    if user is None:
        user = User(discord_id=str(discord_id), username=username)
        session.add(user)
        session.flush()  # assigns user.id without committing the transaction
    elif user.username != username:
        user.username = username
    return user


def add_question(
    session: Session,
    *,
    title: str,
    description: str,
    category: str,
    option_a: str,
    option_b: str,
    option_c: str,
    option_d: str,
    correct_option: str,
    difficulty: str = "medium",
    points: int = 10,
    explanation: str | None = None,
    asked_by: str = "system",
):
    """Insert a new Question and return it (not yet committed)."""
    from models import Question

    question = Question(
        title=title,
        description=description,
        category=category,
        option_a=option_a,
        option_b=option_b,
        option_c=option_c,
        option_d=option_d,
        correct_option=correct_option.upper(),
        difficulty=difficulty,
        points=points,
        explanation=explanation,
        asked_by=asked_by,
    )
    session.add(question)
    session.flush()
    return question


def add_resource(
    session: Session,
    *,
    title: str,
    url: str,
    category: str,
    description: str | None = None,
    tags: str | None = None,
    added_by: str = "system",
):
    """Insert a new Resource and return it (not yet committed)."""
    from models import Resource

    resource = Resource(
        title=title,
        url=url,
        category=category,
        description=description,
        tags=tags,
        added_by=added_by,
    )
    session.add(resource)
    session.flush()
    return resource


def get_guild_config(session: Session, guild_id):
    """Return the GuildConfig row for a guild, or None if it has no overrides."""
    from models import GuildConfig

    if guild_id is None:
        return None
    return session.query(GuildConfig).filter_by(guild_id=str(guild_id)).first()


def get_or_create_guild_config(session: Session, guild_id):
    """Fetch or create the GuildConfig row for a guild (flushed, not committed)."""
    from models import GuildConfig

    cfg = session.query(GuildConfig).filter_by(guild_id=str(guild_id)).first()
    if cfg is None:
        cfg = GuildConfig(guild_id=str(guild_id))
        session.add(cfg)
        session.flush()
    return cfg


# Small cache so we don't hit the DB for the command prefix on every message.
# /config invalidates it via invalidate_prefix_cache when the prefix changes.
_prefix_cache: dict[str, str | None] = {}


def resolve_prefix(guild_id) -> str:
    """Return the effective command prefix for a guild (cached)."""
    if guild_id is None:
        return Config.PREFIX
    gid = str(guild_id)
    if gid not in _prefix_cache:
        session = get_session()
        try:
            cfg = get_guild_config(session, gid)
            _prefix_cache[gid] = cfg.prefix if cfg else None
        finally:
            session.close()
    return _prefix_cache[gid] or Config.PREFIX


def invalidate_prefix_cache(guild_id=None) -> None:
    """Drop cached prefixes (all, or just one guild) after a /config change."""
    if guild_id is None:
        _prefix_cache.clear()
    else:
        _prefix_cache.pop(str(guild_id), None)


# Note: scoring an answer (points, streaks, achievements) lives in
# services.process_answer — it's richer than a simple insert and is the single
# path used by both the answer buttons and the /answer command.
