"""
admin.py
========
A tiny command-line companion for managing CodeSensei's database without Discord.

Usage:
    python admin.py init        # create tables
    python admin.py stats       # show counts and top users
    python admin.py questions   # list all questions
    python admin.py resources   # list all resources
    python admin.py reset       # DROP everything (asks to confirm first!)
"""

import json
import os
import sys

from sqlalchemy import func

import achievements as ach
from config import Config
from db import Base, add_question, add_resource, engine, init_db, session_scope
from models import Answer, Question, Resource, User


def cmd_init() -> None:
    init_db()
    with session_scope() as session:
        created = ach.sync_achievements(session)
    print("✅ Database initialized (tables created if missing).")
    print(f"🏆 Achievements synced ({created} new, {len(ach.CATALOG)} total).")


def cmd_stats() -> None:
    with session_scope() as session:
        users = session.query(func.count(User.id)).scalar()
        questions = session.query(func.count(Question.id)).scalar()
        resources = session.query(func.count(Resource.id)).scalar()
        answers = session.query(func.count(Answer.id)).scalar()

        print("📊 CodeSensei stats")
        print(f"   Users:     {users}")
        print(f"   Questions: {questions}")
        print(f"   Resources: {resources}")
        print(f"   Answers:   {answers}")

        top = (
            session.query(User)
            .order_by(User.points.desc())
            .limit(5)
            .all()
        )
        if top:
            print(f"\n🏆 Top users (by {Config.CURRENCY_NAME}):")
            for i, u in enumerate(top, start=1):
                print(
                    f"   {i}. {u.username} — {u.points} {Config.CURRENCY_NAME} "
                    f"({u.accuracy:.0f}% acc.)"
                )


def cmd_questions() -> None:
    with session_scope() as session:
        rows = session.query(Question).order_by(Question.id).all()
        if not rows:
            print("No questions yet. Run `python seed.py` to add samples.")
            return
        print(f"🧠 {len(rows)} question(s):")
        for q in rows:
            active = "active" if q.is_active else "inactive"
            print(
                f"   #{q.id} [{q.category}/{q.difficulty}] {q.title} "
                f"(correct={q.correct_option}, {q.points}pt, {active})"
            )


def cmd_resources() -> None:
    with session_scope() as session:
        rows = session.query(Resource).order_by(Resource.id).all()
        if not rows:
            print("No resources yet. Run `python seed.py` to add samples.")
            return
        print(f"📚 {len(rows)} resource(s):")
        for r in rows:
            print(f"   #{r.id} [{r.category}] {r.title} — {r.url} (👍 {r.upvotes})")


def cmd_import() -> None:
    """Bulk-load questions or resources from a JSON file (like /export output)."""
    if len(sys.argv) < 3:
        print("Usage: python admin.py import <file.json>")
        return
    path = sys.argv[2]
    if not os.path.exists(path):
        print(f"❌ File not found: {path}")
        return
    with open(path, encoding="utf-8") as fh:
        data = json.load(fh)
    if not isinstance(data, list) or not data:
        print("❌ Expected a non-empty JSON array of objects.")
        return

    sample = data[0]
    added = skipped = 0
    with session_scope() as session:
        if "correct_option" in sample:
            for item in data:
                try:
                    correct = str(item["correct_option"]).upper()
                    if correct not in {"A", "B", "C", "D"}:
                        skipped += 1
                        continue
                    if (
                        session.query(Question)
                        .filter_by(title=item["title"], category=item["category"])
                        .first()
                    ):
                        skipped += 1
                        continue
                    add_question(
                        session,
                        title=item["title"],
                        description=item.get("description", ""),
                        category=item["category"],
                        option_a=item["option_a"],
                        option_b=item["option_b"],
                        option_c=item["option_c"],
                        option_d=item["option_d"],
                        correct_option=correct,
                        difficulty=item.get("difficulty", "medium"),
                        points=int(item.get("points", 10)),
                        explanation=item.get("explanation"),
                    )
                    added += 1
                except (KeyError, ValueError, TypeError):
                    skipped += 1
            print(f"🧠 Questions import: {added} added, {skipped} skipped.")
        elif "url" in sample:
            for item in data:
                try:
                    if session.query(Resource).filter_by(url=item["url"]).first():
                        skipped += 1
                        continue
                    add_resource(
                        session,
                        title=item["title"],
                        url=item["url"],
                        category=item["category"],
                        description=item.get("description"),
                        tags=item.get("tags"),
                    )
                    added += 1
                except (KeyError, ValueError, TypeError):
                    skipped += 1
            print(f"📚 Resources import: {added} added, {skipped} skipped.")
        else:
            print("❌ Could not detect type (need 'correct_option' or 'url' keys).")


def cmd_reset() -> None:
    print("⚠️  This will DROP ALL TABLES and delete every row in:")
    print(f"   {Config.DB_URL}")
    confirm = input("Type 'yes' to confirm: ").strip().lower()
    if confirm != "yes":
        print("❌ Aborted. Nothing was changed.")
        return
    Base.metadata.drop_all(bind=engine)
    init_db()
    print("🧹 Database reset complete — tables recreated empty.")


COMMANDS = {
    "init": cmd_init,
    "stats": cmd_stats,
    "questions": cmd_questions,
    "resources": cmd_resources,
    "import": cmd_import,
    "reset": cmd_reset,
}


def main() -> None:
    if len(sys.argv) < 2 or sys.argv[1] not in COMMANDS:
        print("Usage: python admin.py <command>")
        print("Commands: " + " | ".join(COMMANDS))
        sys.exit(1)
    COMMANDS[sys.argv[1]]()


if __name__ == "__main__":
    main()
