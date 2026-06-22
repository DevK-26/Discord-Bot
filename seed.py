"""
seed.py
=======
Populate the database with starter content so the bot is fun from minute one.

Run it once after initializing the DB:

    python seed.py

It is idempotent-ish: it skips seeding if questions already exist, so running it
twice won't create duplicates.
"""

from db import init_db, session_scope, add_question, add_resource
from models import Question, Resource

# ~6 DSA-focused sample questions.
SAMPLE_QUESTIONS = [
    {
        "title": "Big-O of binary search",
        "description": "What is the worst-case time complexity of binary search on a sorted array?",
        "category": "Algorithms",
        "difficulty": "easy",
        "option_a": "O(n)",
        "option_b": "O(log n)",
        "option_c": "O(n log n)",
        "option_d": "O(1)",
        "correct_option": "B",
        "points": 10,
    },
    {
        "title": "Stack vs Queue",
        "description": "Which data structure follows First-In-First-Out (FIFO) ordering?",
        "category": "Data Structures",
        "difficulty": "easy",
        "option_a": "Stack",
        "option_b": "Queue",
        "option_c": "Hash map",
        "option_d": "Binary tree",
        "correct_option": "B",
        "points": 10,
    },
    {
        "title": "Hash map average lookup",
        "description": "What is the average-case time complexity of a lookup in a hash map?",
        "category": "Data Structures",
        "difficulty": "medium",
        "option_a": "O(1)",
        "option_b": "O(log n)",
        "option_c": "O(n)",
        "option_d": "O(n^2)",
        "correct_option": "A",
        "points": 15,
    },
    {
        "title": "Detect a cycle in a linked list",
        "description": "Which classic technique detects a cycle in a singly linked list in O(1) space?",
        "category": "DSA",
        "difficulty": "medium",
        "option_a": "Two-pointer (Floyd's tortoise & hare)",
        "option_b": "Recursion with memoization",
        "option_c": "Binary search",
        "option_d": "Topological sort",
        "correct_option": "A",
        "points": 15,
    },
    {
        "title": "Sorting stability",
        "description": "Which of these comparison sorts is NOT stable by default?",
        "category": "Algorithms",
        "difficulty": "hard",
        "option_a": "Merge sort",
        "option_b": "Insertion sort",
        "option_c": "Quicksort",
        "option_d": "Bubble sort",
        "correct_option": "C",
        "points": 20,
    },
    {
        "title": "Normalize this!",
        "description": "Which SQL normal form eliminates transitive dependencies on the primary key?",
        "category": "SQL",
        "difficulty": "medium",
        "option_a": "First Normal Form (1NF)",
        "option_b": "Second Normal Form (2NF)",
        "option_c": "Third Normal Form (3NF)",
        "option_d": "Boyce-Codd Normal Form",
        "correct_option": "C",
        "points": 15,
    },
]

# ~5 sample resources.
SAMPLE_RESOURCES = [
    {
        "title": "VisuAlgo — Algorithm Visualizations",
        "url": "https://visualgo.net/en",
        "category": "Algorithms",
        "description": "Interactive visualizations of sorting, graphs, trees, and more.",
        "tags": "visualization,algorithms,interactive",
    },
    {
        "title": "NeetCode — Coding Interview Patterns",
        "url": "https://neetcode.io/",
        "category": "DSA",
        "description": "Curated problem lists and clear video explanations.",
        "tags": "interview,leetcode,patterns",
    },
    {
        "title": "Big-O Cheat Sheet",
        "url": "https://www.bigocheatsheet.com/",
        "category": "Data Structures",
        "description": "Quick reference for time/space complexity of common structures.",
        "tags": "complexity,reference,cheatsheet",
    },
    {
        "title": "System Design Primer",
        "url": "https://github.com/donnemartin/system-design-primer",
        "category": "System Design",
        "description": "A massive, well-organized guide to designing scalable systems.",
        "tags": "scalability,architecture,interview",
    },
    {
        "title": "SQLBolt — Learn SQL Interactively",
        "url": "https://sqlbolt.com/",
        "category": "SQL",
        "description": "Hands-on lessons that teach SQL one query at a time.",
        "tags": "sql,databases,tutorial",
    },
]


def main() -> None:
    init_db()
    with session_scope() as session:
        existing_q = session.query(Question).count()
        existing_r = session.query(Resource).count()

        if existing_q:
            print(f"⏭️  Skipping questions — {existing_q} already in the DB.")
        else:
            for q in SAMPLE_QUESTIONS:
                add_question(session, **q)
            print(f"✅ Added {len(SAMPLE_QUESTIONS)} sample questions.")

        if existing_r:
            print(f"⏭️  Skipping resources — {existing_r} already in the DB.")
        else:
            for r in SAMPLE_RESOURCES:
                add_resource(session, **r)
            print(f"✅ Added {len(SAMPLE_RESOURCES)} sample resources.")

    print("🌱 Seeding complete!")


if __name__ == "__main__":
    main()
