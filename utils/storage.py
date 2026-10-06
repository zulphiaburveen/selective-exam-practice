import streamlit as st
from pathlib import Path
import truststore
from supabase import create_client


# =======================================================
# SSL / WINDOWS CERTIFICATE TRUST
# =======================================================

truststore.inject_into_ssl()


# =======================================================
# SUPABASE CLIENT
# =======================================================

@st.cache_resource
def get_supabase():

    return create_client(
        st.secrets["SUPABASE_URL"],
        st.secrets["SUPABASE_KEY"],
    )


# =======================================================
# DATABASE INITIALISATION
# =======================================================

def init_db():
    """
    Database schema already exists in Supabase.

    Do NOT perform a network request here because init_db()
    is called whenever Streamlit reruns a page.
    """
    return None


# =======================================================
# CACHE
# =======================================================

def clear_data_cache():

    st.cache_data.clear()


# =======================================================
# HELPERS
# =======================================================

def _first(data):

    return data[0] if data else None


# =======================================================
# PAPERS
# =======================================================

@st.cache_data(
    ttl=60,
    show_spinner=False
)
def get_papers():

    return (
        get_supabase()
        .table("papers")
        .select("*")
        .order(
            "published",
            desc=True
        )
        .order(
            "year",
            desc=True
        )
        .order("name")
        .execute()
        .data
    )


@st.cache_data(
    ttl=60,
    show_spinner=False
)
def get_paper(paper_id):

    return _first(
        get_supabase()
        .table("papers")
        .select("*")
        .eq(
            "id",
            paper_id
        )
        .limit(1)
        .execute()
        .data
    )


def add_paper(
    name,
    folder,
    subject,
    year,
    filename
):

    row = (
        get_supabase()
        .table("papers")
        .insert(
            {
                "name": name,
                "folder": folder,
                "subject": subject,
                "year": str(year),
                "filename": filename,
                "published": False,
            }
        )
        .execute()
        .data[0]
    )

    clear_data_cache()

    return row


def publish_paper(paper_id):

    sb = get_supabase()

    # ---------------------------------------------------
    # ONLY ONE PAPER MAY BE PUBLISHED
    # ---------------------------------------------------

    sb.table(
        "papers"
    ).update(
        {
            "published": False
        }
    ).neq(
        "id",
        -1
    ).execute()

    sb.table(
        "papers"
    ).update(
        {
            "published": True
        }
    ).eq(
        "id",
        paper_id
    ).execute()

    clear_data_cache()


@st.cache_data(
    ttl=30,
    show_spinner=False
)
def get_published_paper():

    return _first(
        get_supabase()
        .table("papers")
        .select("*")
        .eq(
            "published",
            True
        )
        .limit(1)
        .execute()
        .data
    )


def delete_paper(paper_id):

    get_supabase().table(
        "papers"
    ).delete().eq(
        "id",
        paper_id
    ).execute()

    clear_data_cache()


@st.cache_data(
    ttl=30,
    show_spinner=False
)
def paper_name_exists(name):

    rows = (
        get_supabase()
        .table("papers")
        .select("id")
        .eq(
            "name",
            name
        )
        .limit(1)
        .execute()
        .data
    )

    return bool(rows)


@st.cache_data(
    ttl=30,
    show_spinner=False
)
def paper_counts(paper_id):

    passages = get_passages(
        paper_id
    )

    questions = get_questions(
        paper_id
    )

    return (
        len(passages),
        len(questions)
    )


# =======================================================
# PASSAGES
# =======================================================

@st.cache_data(
    ttl=60,
    show_spinner=False
)
def get_passages(paper_id):

    return (
        get_supabase()
        .table("passages")
        .select("*")
        .eq(
            "paper_id",
            paper_id
        )
        .order(
            "display_order"
        )
        .execute()
        .data
    )


@st.cache_data(
    ttl=60,
    show_spinner=False
)
def get_passage(passage_id):

    if passage_id is None:

        return None

    return _first(
        get_supabase()
        .table("passages")
        .select("*")
        .eq(
            "id",
            passage_id
        )
        .limit(1)
        .execute()
        .data
    )


def next_passage_order(paper_id):

    rows = get_passages(
        paper_id
    )

    return (
        max(
            (
                int(
                    row[
                        "display_order"
                    ]
                    or 0
                )
                for row
                in rows
            ),
            default=0
        )
        + 1
    )


def passage_order_exists(
    paper_id,
    display_order,
    exclude_id=None
):

    rows = (
        get_supabase()
        .table("passages")
        .select("id")
        .eq(
            "paper_id",
            paper_id
        )
        .eq(
            "display_order",
            int(display_order)
        )
        .execute()
        .data
    )

    if exclude_id is not None:

        rows = [
            row
            for row in rows
            if row["id"] != exclude_id
        ]

    return bool(rows)


def add_passage(
    paper_id,
    title,
    content,
    image,
    display_order
):

    row = (
        get_supabase()
        .table("passages")
        .insert(
            {
                "paper_id": paper_id,
                "title": title,
                "content": content,
                "image": image,
                "display_order": int(
                    display_order
                ),
            }
        )
        .execute()
        .data[0]
    )

    clear_data_cache()

    return row


def update_passage(
    passage_id,
    title,
    content,
    image,
    display_order
):

    result = (
        get_supabase()
        .table("passages")
        .update(
            {
                "title": title,
                "content": content,
                "image": image,
                "display_order": int(
                    display_order
                ),
            }
        )
        .eq(
            "id",
            passage_id
        )
        .execute()
        .data
    )

    clear_data_cache()

    return result


def delete_passage(passage_id):

    get_supabase().table(
        "passages"
    ).delete().eq(
        "id",
        passage_id
    ).execute()

    clear_data_cache()


@st.cache_data(
    ttl=30,
    show_spinner=False
)
def questions_for_passage(
    passage_id
):

    return (
        get_supabase()
        .table("questions")
        .select(
            "id,question_number"
        )
        .eq(
            "passage_id",
            passage_id
        )
        .order(
            "question_number"
        )
        .execute()
        .data
    )


# =======================================================
# QUESTIONS
# =======================================================

@st.cache_data(
    ttl=60,
    show_spinner=False
)
def get_questions(paper_id):

    questions = (
        get_supabase()
        .table("questions")
        .select("*")
        .eq(
            "paper_id",
            paper_id
        )
        .order(
            "question_number"
        )
        .execute()
        .data
    )

    # ---------------------------------------------------
    # LOAD PASSAGES ONCE
    # ---------------------------------------------------

    passage_lookup = {
        passage["id"]: passage
        for passage
        in get_passages(
            paper_id
        )
    }

    # ---------------------------------------------------
    # ATTACH PASSAGE DATA
    # ---------------------------------------------------

    for question in questions:

        passage = (
            passage_lookup.get(
                question.get(
                    "passage_id"
                )
            )
        )

        if passage:

            question[
                "passage_title"
            ] = passage.get(
                "title"
            )

            question[
                "passage_content"
            ] = passage.get(
                "content"
            )

            question[
                "passage_image"
            ] = passage.get(
                "image"
            )

        else:

            question[
                "passage_title"
            ] = None

            question[
                "passage_content"
            ] = None

            question[
                "passage_image"
            ] = None

    return questions


@st.cache_data(
    ttl=60,
    show_spinner=False
)
def get_question(question_id):

    if question_id is None:

        return None

    return _first(
        get_supabase()
        .table("questions")
        .select("*")
        .eq(
            "id",
            question_id
        )
        .limit(1)
        .execute()
        .data
    )


def next_question_number(
    paper_id
):

    rows = get_questions(
        paper_id
    )

    return (
        max(
            (
                int(
                    row[
                        "question_number"
                    ]
                    or 0
                )
                for row
                in rows
            ),
            default=0
        )
        + 1
    )


# =======================================================
# OPTIONS
# =======================================================

@st.cache_data(
    ttl=60,
    show_spinner=False
)
def get_options(question_id):

    return (
        get_supabase()
        .table("options")
        .select("*")
        .eq(
            "question_id",
            question_id
        )
        .order(
            "option_letter"
        )
        .execute()
        .data
    )


@st.cache_data(
    ttl=60,
    show_spinner=False
)
def get_options_for_questions(
    question_ids_tuple
):

    ids = list(
        question_ids_tuple
    )

    if not ids:

        return {}

    rows = (
        get_supabase()
        .table("options")
        .select("*")
        .in_(
            "question_id",
            ids
        )
        .order(
            "option_letter"
        )
        .execute()
        .data
    )

    grouped = {
        question_id: []
        for question_id
        in ids
    }

    for row in rows:

        grouped.setdefault(
            row["question_id"],
            []
        ).append(
            row
        )

    return grouped


# =======================================================
# EXAM BUNDLE
# =======================================================

@st.cache_data(
    ttl=60,
    show_spinner=False
)
def get_exam_bundle(paper_id):

    questions = get_questions(
        paper_id
    )

    question_ids = tuple(
        question["id"]
        for question
        in questions
    )

    options = (
        get_options_for_questions(
            question_ids
        )
    )

    return {
        "questions": questions,
        "options": options,
    }


# =======================================================
# ADD QUESTION
# =======================================================

def add_question(
    paper_id,
    passage_id,
    question_number,
    question_html,
    question_image,
    question_type
):

    row = (
        get_supabase()
        .table("questions")
        .insert(
            {
                "paper_id": paper_id,
                "passage_id": passage_id,
                "question_number": int(
                    question_number
                ),
                "question_html": (
                    question_html
                ),
                "question_image": (
                    question_image
                ),
                "question_type": (
                    question_type
                ),
            }
        )
        .execute()
        .data[0]
    )

    clear_data_cache()

    return row


# =======================================================
# UPDATE QUESTION
# =======================================================

def update_question(
    question_id,
    passage_id,
    question_html,
    question_image,
    question_type
):

    result = (
        get_supabase()
        .table("questions")
        .update(
            {
                "passage_id": (
                    passage_id
                ),
                "question_html": (
                    question_html
                ),
                "question_image": (
                    question_image
                ),
                "question_type": (
                    question_type
                ),
            }
        )
        .eq(
            "id",
            question_id
        )
        .execute()
        .data
    )

    clear_data_cache()

    return result


# =======================================================
# REPLACE OPTIONS
# =======================================================

def replace_options(
    question_id,
    options
):

    sb = get_supabase()

    sb.table(
        "options"
    ).delete().eq(
        "question_id",
        question_id
    ).execute()

    if options:

        sb.table(
            "options"
        ).insert(
            options
        ).execute()

    clear_data_cache()


# =======================================================
# DELETE QUESTION
# =======================================================

def delete_question(question_id):

    get_supabase().table(
        "questions"
    ).delete().eq(
        "id",
        question_id
    ).execute()

    clear_data_cache()


# =======================================================
# CREATE EXAM ATTEMPT
# =======================================================

def create_attempt(
    paper_id, student, score, total, percentage,
    time_taken, timer_minutes, answer_rows
):
    sb = get_supabase()

    attempt = (
        sb.table("attempts")
        .insert({
            "paper_id": paper_id,
            "student": student,
            "score": int(score),
            "total": int(total),
            "percentage": float(percentage),
            "time_taken": int(time_taken),
            "timer_minutes": int(timer_minutes),
        })
        .execute()
        .data[0]
    )

    if answer_rows:
        payload = [
            {
                "attempt_id": attempt["id"],
                "question_id": row["question_id"],
                "selected_answer": row["selected_answer"],
                "is_correct": bool(row["is_correct"]),
            }
            for row in answer_rows
        ]
        sb.table("attempt_answers").insert(payload).execute()

    # Paper/question caches remain valid, but result/history caches must
    # be invalidated immediately so every paper's history stays accurate.
    get_attempts.clear()
    get_attempt.clear()
    attempt_number_for.clear()
    get_attempt_answers.clear()
    get_review_attempts.clear()
    corrected_question_ids.clear()

    st.session_state["_latest_attempt_snapshot"] = dict(attempt)
    st.session_state["_latest_answer_rows"] = [dict(row) for row in answer_rows]

    return attempt


# =======================================================
# ATTEMPTS
# =======================================================

@st.cache_data(ttl=30, show_spinner=False)
def get_attempt(attempt_id):
    rows = (
        get_supabase().table("attempts").select("*")
        .eq("id", attempt_id).limit(1).execute().data
    )
    if not rows:
        return None
    attempt = dict(rows[0])
    paper = get_paper(attempt["paper_id"]) or {}
    attempt["paper_name"] = paper.get("name", "Unknown Paper")
    attempt["subject"] = paper.get("subject")
    attempt["year"] = paper.get("year")
    return attempt


@st.cache_data(
    ttl=30,
    show_spinner=False
)
def get_attempts(student):

    attempts = (
        get_supabase()
        .table("attempts")
        .select("*")
        .eq(
            "student",
            student
        )
        .order(
            "id",
            desc=True
        )
        .execute()
        .data
    )

    papers = {
        paper["id"]: paper
        for paper
        in get_papers()
    }

    for attempt in attempts:

        paper = papers.get(
            attempt["paper_id"],
            {}
        )

        attempt[
            "paper_name"
        ] = paper.get(
            "name",
            "Unknown Paper"
        )

        attempt[
            "subject"
        ] = paper.get(
            "subject"
        )

        attempt[
            "year"
        ] = paper.get(
            "year"
        )

    return attempts


@st.cache_data(
    ttl=30,
    show_spinner=False
)
def attempt_number_for(
    paper_id,
    student,
    attempt_id
):

    rows = (
        get_supabase()
        .table("attempts")
        .select("id")
        .eq(
            "paper_id",
            paper_id
        )
        .eq(
            "student",
            student
        )
        .lte(
            "id",
            attempt_id
        )
        .execute()
        .data
    )

    return len(rows)


# =======================================================
# ATTEMPT ANSWERS
# =======================================================

@st.cache_data(
    ttl=30,
    show_spinner=False
)
def get_attempt_answers(
    attempt_id
):

    answers = (
        get_supabase()
        .table(
            "attempt_answers"
        )
        .select("*")
        .eq(
            "attempt_id",
            attempt_id
        )
        .execute()
        .data
    )

    if not answers:

        return []

    # ---------------------------------------------------
    # LOAD QUESTIONS IN ONE REQUEST
    # ---------------------------------------------------

    question_ids = tuple(
        answer["question_id"]
        for answer
        in answers
    )

    questions = (
        get_supabase()
        .table("questions")
        .select("*")
        .in_(
            "id",
            list(
                question_ids
            )
        )
        .execute()
        .data
    )

    question_lookup = {
        question["id"]:
        question
        for question
        in questions
    }

    # ---------------------------------------------------
    # LOAD PASSAGES IN ONE REQUEST
    # ---------------------------------------------------

    passage_ids = list(
        {
            question[
                "passage_id"
            ]
            for question
            in questions
            if question.get(
                "passage_id"
            )
        }
    )

    passages = []

    if passage_ids:

        passages = (
            get_supabase()
            .table("passages")
            .select("*")
            .in_(
                "id",
                passage_ids
            )
            .execute()
            .data
        )

    passage_lookup = {
        passage["id"]:
        passage
        for passage
        in passages
    }

    # ---------------------------------------------------
    # BUILD RESULT
    # ---------------------------------------------------

    result = []

    for answer in answers:

        question = (
            question_lookup.get(
                answer[
                    "question_id"
                ]
            )
        )

        if not question:

            continue

        passage = (
            passage_lookup.get(
                question.get(
                    "passage_id"
                )
            )
        )

        merged = dict(
            answer
        )

        merged.update(
            {
                "question_number":
                    question[
                        "question_number"
                    ],

                "question_html":
                    question[
                        "question_html"
                    ],

                "question_image":
                    question[
                        "question_image"
                    ],

                "question_type":
                    question[
                        "question_type"
                    ],

                "passage_id":
                    question[
                        "passage_id"
                    ],

                "passage_title":
                    (
                        passage[
                            "title"
                        ]
                        if passage
                        else None
                    ),

                "passage_content":
                    (
                        passage[
                            "content"
                        ]
                        if passage
                        else None
                    ),

                "passage_image":
                    (
                        passage[
                            "image"
                        ]
                        if passage
                        else None
                    ),
            }
        )

        result.append(
            merged
        )

    result.sort(
        key=lambda row:
        int(
            row[
                "question_number"
            ]
        )
    )

    return result


# =======================================================
# REVIEW ATTEMPTS
# =======================================================

@st.cache_data(
    ttl=30,
    show_spinner=False
)
def get_review_attempts(
    attempt_id
):

    return (
        get_supabase()
        .table(
            "review_attempts"
        )
        .select("*")
        .eq(
            "attempt_id",
            attempt_id
        )
        .order(
            "review_number",
            desc=True
        )
        .execute()
        .data
    )


def latest_review_status(
    attempt_id
):

    rows = get_review_attempts(
        attempt_id
    )

    return (
        rows[0]
        if rows
        else None
    )


# =======================================================
# CORRECTED QUESTIONS
# =======================================================

@st.cache_data(
    ttl=30,
    show_spinner=False
)
def corrected_question_ids(
    attempt_id
):

    reviews = get_review_attempts(
        attempt_id
    )

    if not reviews:

        return set()

    review_ids = [
        review["id"]
        for review
        in reviews
    ]

    rows = (
        get_supabase()
        .table(
            "review_answers"
        )
        .select(
            "question_id,is_correct"
        )
        .in_(
            "review_attempt_id",
            review_ids
        )
        .eq(
            "is_correct",
            True
        )
        .execute()
        .data
    )

    return {
        row["question_id"]
        for row
        in rows
    }


# =======================================================
# CREATE SELF REVIEW
# =======================================================

def create_review_attempt(
    attempt_id,
    review_number,
    score,
    total,
    evaluated_rows
):

    sb = get_supabase()

    # ---------------------------------------------------
    # REVIEW SESSION
    # ---------------------------------------------------

    review = (
        sb.table(
            "review_attempts"
        )
        .insert(
            {
                "attempt_id":
                    attempt_id,

                "review_number":
                    int(
                        review_number
                    ),

                "score":
                    int(score),

                "total":
                    int(total),
            }
        )
        .execute()
        .data[0]
    )

    # ---------------------------------------------------
    # REVIEW ANSWERS
    # ---------------------------------------------------

    payload = [
        {
            "review_attempt_id":
                review["id"],

            "question_id":
                row[
                    "question_id"
                ],

            "selected_answer":
                row[
                    "selected_answer"
                ],

            "is_correct":
                bool(
                    row[
                        "is_correct"
                    ]
                ),
        }
        for row
        in evaluated_rows
    ]

    if payload:

        sb.table(
            "review_answers"
        ).insert(
            payload
        ).execute()

    clear_data_cache()

    return review

# =======================================================
# SUPABASE STORAGE
# =======================================================

STORAGE_BUCKET = "exam-files"


def is_remote_file(value):
    return bool(value) and str(value).lower().startswith(("http://", "https://"))


def storage_public_url(object_path):
    if not object_path:
        return None
    result = get_supabase().storage.from_(STORAGE_BUCKET).get_public_url(object_path)
    return result


def upload_file_bytes(object_path, file_bytes, content_type=None, upsert=True):
    options = {"upsert": "true" if upsert else "false"}
    if content_type:
        options["content-type"] = content_type

    get_supabase().storage.from_(STORAGE_BUCKET).upload(
        path=object_path,
        file=file_bytes,
        file_options=options,
    )
    return storage_public_url(object_path)


def delete_storage_file_by_url(file_url):
    if not is_remote_file(file_url):
        return
    marker = f"/storage/v1/object/public/{STORAGE_BUCKET}/"
    if marker not in file_url:
        return
    object_path = file_url.split(marker, 1)[1]
    get_supabase().storage.from_(STORAGE_BUCKET).remove([object_path])


def delete_storage_folder(prefix):
    bucket = get_supabase().storage.from_(STORAGE_BUCKET)
    # Supabase Storage list is folder based. Delete recursively for our
    # known three paper subfolders.
    for subfolder in ("original", "passages", "questions"):
        folder = f"{prefix}/{subfolder}"
        try:
            items = bucket.list(folder)
        except Exception:
            items = []
        paths = [
            f"{folder}/{item['name']}"
            for item in items
            if item.get("name")
        ]
        if paths:
            bucket.remove(paths)


def displayable_file(value):
    """Return a remote URL unchanged, or a valid local legacy path."""
    if not value:
        return None
    if is_remote_file(value):
        return value
    path = Path(value)
    return str(path) if path.exists() else None
