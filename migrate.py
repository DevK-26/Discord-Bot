"""
migrate.py
==========
Non-destructive database migration runner.

Run this BEFORE launching a new version of the bot:

    python migrate.py

It (1) creates any missing tables and (2) applies a list of additive
``ALTER TABLE`` steps that are safe to run repeatedly — each step checks whether
a column already exists before adding it, so your existing ``app.db`` and all its
data are preserved.

Tier 1 introduces **no schema changes**, so today this just ensures the tables
exist. Later tiers (streaks, levels, explanations, ...) will append steps to the
MIGRATIONS list below, and this same command will upgrade old databases safely.
"""

from __future__ import annotations

from sqlalchemy import inspect, text

import achievements as ach
from db import engine, init_db, session_scope


def _columns(table: str) -> set[str]:
    """Return the set of existing column names for a table (empty if no table)."""
    inspector = inspect(engine)
    if table not in inspector.get_table_names():
        return set()
    return {col["name"] for col in inspector.get_columns(table)}


def add_column_if_missing(table: str, column: str, ddl_type: str) -> bool:
    """ALTER TABLE ... ADD COLUMN, but only if the column isn't already there.

    Returns True if it added the column, False if it was already present.
    `ddl_type` is the raw SQL type/default, e.g. "INTEGER DEFAULT 0".
    """
    if column in _columns(table):
        return False
    with engine.begin() as conn:
        conn.execute(text(f'ALTER TABLE {table} ADD COLUMN {column} {ddl_type}'))
    return True


# Each migration is (table, column, ddl_type). Add new rows in future tiers;
# already-applied ones are skipped automatically.
MIGRATIONS: list[tuple[str, str, str]] = [
    # Tier 2: daily-challenge streak tracking on the users table.
    ("users", "current_streak", "INTEGER DEFAULT 0"),
    ("users", "longest_streak", "INTEGER DEFAULT 0"),
    ("users", "last_daily_date", "DATE"),
]


def main() -> None:
    # 1. Make sure all tables defined in models.py exist (creates the new
    #    achievements / user_achievements tables on existing databases).
    init_db()
    print("✅ Tables ensured (created any that were missing).")

    # 2. Apply additive column migrations to pre-existing tables.
    if MIGRATIONS:
        applied = 0
        for table, column, ddl in MIGRATIONS:
            if add_column_if_missing(table, column, ddl):
                print(f"   + added {table}.{column}")
                applied += 1
            else:
                print(f"   = {table}.{column} already present, skipped")
        print(f"🧩 Columns: {applied} added.")
    else:
        print("ℹ️  No column migrations to apply for this version.")

    # 3. Sync the achievement catalog into the DB.
    with session_scope() as session:
        created = ach.sync_achievements(session)
    print(f"🏆 Achievements synced ({created} new, {len(ach.CATALOG)} total).")


if __name__ == "__main__":
    main()
