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

import sys

from sqlalchemy import func

from config import Config
from db import Base, engine, init_db, session_scope
from models import Answer, Question, Resource, User


def cmd_init() -> None:
    init_db()
    print("✅ Database initialized (tables created if missing).")


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
