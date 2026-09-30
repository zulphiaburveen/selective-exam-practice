import sqlite3
from pathlib import Path

DB_PATH = "data/practice.db"


def get_connection():
    Path("data").mkdir(exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
    CREATE TABLE IF NOT EXISTS papers(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        folder TEXT NOT NULL UNIQUE,
        subject TEXT,
        year TEXT,
        filename TEXT,
        published INTEGER DEFAULT 0,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP
    )
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS passages(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        paper_id INTEGER,
        title TEXT,
        content TEXT,
        image TEXT,
        display_order INTEGER,
        FOREIGN KEY(paper_id) REFERENCES papers(id)
    )
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS questions(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        paper_id INTEGER,
        passage_id INTEGER,
        question_number INTEGER,
        question_html TEXT,
        question_image TEXT,
        question_type TEXT,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY(paper_id) REFERENCES papers(id),
        FOREIGN KEY(passage_id) REFERENCES passages(id)
    )
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS options(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        question_id INTEGER,
        option_letter TEXT,
        option_text TEXT,
        is_correct INTEGER DEFAULT 0,
        FOREIGN KEY(question_id) REFERENCES questions(id)
    )
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS attempts(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        paper_id INTEGER,
        student TEXT,
        score INTEGER,
        total INTEGER,
        percentage REAL,
        time_taken INTEGER,
        timer_minutes INTEGER,
        attempt_date DATETIME DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY(paper_id) REFERENCES papers(id)
    )
    """)

    # Stores the student's answers for each completed attempt.
    # This makes Results/Review persistent even after a browser refresh.
    cur.execute("""
    CREATE TABLE IF NOT EXISTS attempt_answers(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        attempt_id INTEGER NOT NULL,
        question_id INTEGER NOT NULL,
        selected_answer TEXT,
        is_correct INTEGER DEFAULT 0,
        review_answer TEXT,
        review_correct INTEGER,
        reviewed_at DATETIME,
        FOREIGN KEY(attempt_id) REFERENCES attempts(id),
        FOREIGN KEY(question_id) REFERENCES questions(id),
        UNIQUE(attempt_id, question_id)
    )
    """)

    # One row per submitted self-review session.
    cur.execute("""
    CREATE TABLE IF NOT EXISTS review_attempts(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        attempt_id INTEGER NOT NULL,
        review_number INTEGER NOT NULL,
        score INTEGER NOT NULL,
        total INTEGER NOT NULL,
        review_date DATETIME DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY(attempt_id) REFERENCES attempts(id)
    )
    """)

    # Answers submitted together in a self-review session.
    cur.execute("""
    CREATE TABLE IF NOT EXISTS review_answers(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        review_attempt_id INTEGER NOT NULL,
        question_id INTEGER NOT NULL,
        selected_answer TEXT,
        is_correct INTEGER DEFAULT 0,
        FOREIGN KEY(review_attempt_id) REFERENCES review_attempts(id),
        FOREIGN KEY(question_id) REFERENCES questions(id),
        UNIQUE(review_attempt_id, question_id)
    )
    """)

    # Migration for databases created before timer_minutes was added.
    cur.execute("PRAGMA table_info(attempts)")
    attempt_columns = {row[1] for row in cur.fetchall()}
    if "timer_minutes" not in attempt_columns:
        cur.execute("ALTER TABLE attempts ADD COLUMN timer_minutes INTEGER")

    conn.commit()
    conn.close()


def add_paper(name, folder, subject, year, filename):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        """
        INSERT INTO papers(name, folder, subject, year, filename)
        VALUES(?,?,?,?,?)
        """,
        (name, folder, subject, year, filename),
    )
    conn.commit()
    conn.close()


def get_papers():
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        SELECT *
        FROM papers
        ORDER BY created_at DESC
    """)
    rows = cur.fetchall()
    conn.close()
    return rows


def publish_paper(paper_id):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("UPDATE papers SET published = 0")
    cur.execute(
        "UPDATE papers SET published = 1 WHERE id=?",
        (paper_id,),
    )
    conn.commit()
    conn.close()


def get_published_paper():
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        SELECT *
        FROM papers
        WHERE published=1
        LIMIT 1
    """)
    row = cur.fetchone()
    conn.close()
    return row


def delete_paper(paper_id):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("DELETE FROM papers WHERE id=?", (paper_id,))
    conn.commit()
    conn.close()
