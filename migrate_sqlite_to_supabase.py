import sqlite3
from pathlib import Path

import streamlit as st
import truststore
from supabase import create_client

truststore.inject_into_ssl()

SQLITE_PATH = Path("data/practice.db")


def fetch_all(conn, table):
    try:
        return [dict(row) for row in conn.execute(f"SELECT * FROM {table} ORDER BY id").fetchall()]
    except sqlite3.OperationalError:
        return []


def main():
    if not SQLITE_PATH.exists():
        raise SystemExit(f"SQLite database not found: {SQLITE_PATH}")

    sb = create_client(
        st.secrets["SUPABASE_URL"],
        st.secrets["SUPABASE_KEY"],
    )

    conn = sqlite3.connect(SQLITE_PATH)
    conn.row_factory = sqlite3.Row

    # Initial migration only. Clear destination children before parents.
    for table in [
        "review_answers",
        "review_attempts",
        "attempt_answers",
        "attempts",
        "options",
        "questions",
        "passages",
        "papers",
    ]:
        existing = sb.table(table).select("id").execute().data
        for row in existing:
            sb.table(table).delete().eq("id", row["id"]).execute()

    paper_map = {}
    passage_map = {}
    question_map = {}
    attempt_map = {}
    review_attempt_map = {}

    # Papers
    papers = fetch_all(conn, "papers")
    for row in papers:
        created = (
            sb.table("papers")
            .insert(
                {
                    "name": row["name"],
                    "folder": row["folder"],
                    "subject": row.get("subject"),
                    "year": str(row.get("year")) if row.get("year") is not None else None,
                    "filename": row.get("filename"),
                    "published": bool(row.get("published")),
                    "created_at": row.get("created_at"),
                }
            )
            .execute()
            .data[0]
        )
        paper_map[row["id"]] = created["id"]
    print(f"papers: migrated {len(papers)} row(s)")

    # Passages
    passages = fetch_all(conn, "passages")
    for row in passages:
        created = (
            sb.table("passages")
            .insert(
                {
                    "paper_id": paper_map[row["paper_id"]],
                    "title": row.get("title"),
                    "content": row.get("content"),
                    "image": row.get("image"),
                    "display_order": row.get("display_order"),
                }
            )
            .execute()
            .data[0]
        )
        passage_map[row["id"]] = created["id"]
    print(f"passages: migrated {len(passages)} row(s)")

    # Questions
    questions = fetch_all(conn, "questions")
    for row in questions:
        old_passage_id = row.get("passage_id")
        created = (
            sb.table("questions")
            .insert(
                {
                    "paper_id": paper_map[row["paper_id"]],
                    "passage_id": passage_map.get(old_passage_id) if old_passage_id else None,
                    "question_number": row.get("question_number"),
                    "question_html": row.get("question_html"),
                    "question_image": row.get("question_image"),
                    "question_type": row.get("question_type"),
                    "created_at": row.get("created_at"),
                }
            )
            .execute()
            .data[0]
        )
        question_map[row["id"]] = created["id"]
    print(f"questions: migrated {len(questions)} row(s)")

    # Options
    options = fetch_all(conn, "options")
    for row in options:
        sb.table("options").insert(
            {
                "question_id": question_map[row["question_id"]],
                "option_letter": row.get("option_letter"),
                "option_text": row.get("option_text"),
                "is_correct": bool(row.get("is_correct")),
            }
        ).execute()
    print(f"options: migrated {len(options)} row(s)")

    # Attempts
    attempts = fetch_all(conn, "attempts")
    for row in attempts:
        created = (
            sb.table("attempts")
            .insert(
                {
                    "paper_id": paper_map[row["paper_id"]],
                    "student": row.get("student"),
                    "score": row.get("score"),
                    "total": row.get("total"),
                    "percentage": row.get("percentage"),
                    "time_taken": row.get("time_taken"),
                    "timer_minutes": row.get("timer_minutes"),
                    "attempt_date": row.get("attempt_date"),
                }
            )
            .execute()
            .data[0]
        )
        attempt_map[row["id"]] = created["id"]
    print(f"attempts: migrated {len(attempts)} row(s)")

    # Attempt answers
    attempt_answers = fetch_all(conn, "attempt_answers")
    for row in attempt_answers:
        sb.table("attempt_answers").insert(
            {
                "attempt_id": attempt_map[row["attempt_id"]],
                "question_id": question_map[row["question_id"]],
                "selected_answer": row.get("selected_answer"),
                "is_correct": bool(row.get("is_correct")),
                "review_answer": row.get("review_answer"),
                "review_correct": (
                    bool(row.get("review_correct"))
                    if row.get("review_correct") is not None
                    else None
                ),
                "reviewed_at": row.get("reviewed_at"),
            }
        ).execute()
    print(f"attempt_answers: migrated {len(attempt_answers)} row(s)")

    # Review attempts
    review_attempts = fetch_all(conn, "review_attempts")
    for row in review_attempts:
        created = (
            sb.table("review_attempts")
            .insert(
                {
                    "attempt_id": attempt_map[row["attempt_id"]],
                    "review_number": row.get("review_number"),
                    "score": row.get("score"),
                    "total": row.get("total"),
                    "review_date": row.get("review_date"),
                }
            )
            .execute()
            .data[0]
        )
        review_attempt_map[row["id"]] = created["id"]
    print(f"review_attempts: migrated {len(review_attempts)} row(s)")

    # Review answers
    review_answers = fetch_all(conn, "review_answers")
    for row in review_answers:
        sb.table("review_answers").insert(
            {
                "review_attempt_id": review_attempt_map[row["review_attempt_id"]],
                "question_id": question_map[row["question_id"]],
                "selected_answer": row.get("selected_answer"),
                "is_correct": bool(row.get("is_correct")),
            }
        ).execute()
    print(f"review_answers: migrated {len(review_answers)} row(s)")

    conn.close()
    print("Migration completed successfully.")


if __name__ == "__main__":
    main()
