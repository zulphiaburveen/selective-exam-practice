import time
from pathlib import Path

import streamlit as st
from streamlit_autorefresh import st_autorefresh

from utils.storage import *

st.set_page_config(page_title="Exam", page_icon="📝", layout="wide")
st.title("📝 Selective Exam Practice")
init_db()

conn = get_connection()
cur = conn.cursor()

DEFAULTS = {
    "started": False,
    "paper_id": None,
    "paper_name": None,
    "question_index": 0,
    "responses": {},
    "timer_minutes": 60,
    "start_time": None,
    "student": "Rishan",
    "confirm_finish": False,
    "current_attempt_id": None,
}
for key, value in DEFAULTS.items():
    if key not in st.session_state:
        st.session_state[key] = value


def load_questions(paper_id):
    cur.execute(
        """
        SELECT q.id, q.question_number, q.question_html, q.question_image,
               q.question_type, q.passage_id,
               p.title AS passage_title, p.content AS passage_content,
               p.image AS passage_image
        FROM questions q
        LEFT JOIN passages p ON q.passage_id = p.id
        WHERE q.paper_id = ?
        ORDER BY q.question_number
        """,
        (paper_id,),
    )
    return cur.fetchall()


def load_options(question_id):
    cur.execute(
        """
        SELECT id, option_letter, option_text, is_correct
        FROM options
        WHERE question_id = ?
        ORDER BY option_letter
        """,
        (question_id,),
    )
    return cur.fetchall()


def normalise_answer(question_type, answer):
    if question_type == "single":
        return {answer} if answer else set()
    return set(answer or [])


def serialise_answer(question_type, answer):
    if question_type == "single":
        return answer or ""
    return ",".join(sorted(answer or []))


def clear_exam_widget_state():
    for key in list(st.session_state.keys()):
        if key.startswith("exam_single_") or key.startswith("exam_multi_"):
            del st.session_state[key]


def finish_exam():
    questions = load_questions(st.session_state.paper_id)
    score = 0
    answer_rows = []

    for question in questions:
        options = load_options(question["id"])
        correct_answers = {
            option["option_letter"] for option in options if option["is_correct"]
        }
        user_answer = st.session_state.responses.get(question["id"])
        selected_answers = normalise_answer(question["question_type"], user_answer)
        is_correct = selected_answers == correct_answers
        if is_correct:
            score += 1
        answer_rows.append(
            (
                question["id"],
                serialise_answer(question["question_type"], user_answer),
                1 if is_correct else 0,
            )
        )

    total = len(questions)
    percentage = round(score / total * 100, 1) if total else 0
    elapsed_seconds = int(time.time() - st.session_state.start_time)

    try:
        cur.execute(
            """
            INSERT INTO attempts
                (paper_id, student, score, total, percentage, time_taken, timer_minutes, attempt_date)
            VALUES (?, ?, ?, ?, ?, ?, ?, datetime('now'))
            """,
            (
                st.session_state.paper_id,
                st.session_state.student,
                score,
                total,
                percentage,
                elapsed_seconds,
                st.session_state.timer_minutes,
            ),
        )
        attempt_id = cur.lastrowid

        for question_id, selected_answer, is_correct in answer_rows:
            cur.execute(
                """
                INSERT INTO attempt_answers
                    (attempt_id, question_id, selected_answer, is_correct)
                VALUES (?, ?, ?, ?)
                """,
                (attempt_id, question_id, selected_answer, is_correct),
            )

        conn.commit()
    except Exception:
        conn.rollback()
        raise

    st.session_state.current_attempt_id = attempt_id
    st.session_state.started = False
    st.session_state.confirm_finish = False
    clear_exam_widget_state()
    st.switch_page("pages/Results.py")


# =======================================================
# START SCREEN
# =======================================================
if not st.session_state.started:
    st.subheader(f"Welcome {st.session_state.student}! 👋")

    cur.execute(
        """
        SELECT id, name, subject, year
        FROM papers
        WHERE published = 1
        LIMIT 1
        """
    )
    selected_paper = cur.fetchone()

    if selected_paper is None:
        st.warning("No published paper is currently available.")
        st.info("Publish a paper from Admin first.")
        conn.close()
        st.stop()

    st.markdown("### 📘 Current Paper")
    st.info(
        f"**{selected_paper['name']}**  \n"
        f"{selected_paper['subject']} • {selected_paper['year']}"
    )

    cur.execute("SELECT COUNT(*) FROM questions WHERE paper_id = ?", (selected_paper["id"],))
    question_count = cur.fetchone()[0]
    st.info(f"📝 {question_count} question(s)")

    st.markdown("### ⏱️ Choose Exam Time")
    timer_minutes = st.radio(
        "Exam Time",
        [60, 50, 45, 40, 30, 20, 10],
        horizontal=True,
        index=0,
        label_visibility="collapsed",
    )
    st.caption(f"You will have {timer_minutes} minutes to complete the exam.")

    if st.button(
        "🚀 Start Exam",
        type="primary",
        use_container_width=True,
        disabled=(question_count == 0),
    ):
        clear_exam_widget_state()
        st.session_state.paper_id = selected_paper["id"]
        st.session_state.paper_name = selected_paper["name"]
        st.session_state.question_index = 0
        st.session_state.responses = {}
        st.session_state.timer_minutes = timer_minutes
        st.session_state.start_time = time.time()
        st.session_state.started = True
        st.session_state.confirm_finish = False
        st.session_state.current_attempt_id = None
        st.rerun()

# =======================================================
# EXAM
# =======================================================
else:
    questions = load_questions(st.session_state.paper_id)
    if not questions:
        st.error("This paper contains no questions.")
        st.session_state.started = False
        conn.close()
        st.stop()

    st_autorefresh(interval=1000, key="exam_timer_refresh")
    total_seconds = st.session_state.timer_minutes * 60
    elapsed_seconds = int(time.time() - st.session_state.start_time)
    remaining = max(0, total_seconds - elapsed_seconds)
    if remaining <= 0:
        finish_exam()

    mins, secs = divmod(remaining, 60)
    index = st.session_state.question_index
    question = questions[index]
    question_id = question["id"]
    options = load_options(question_id)

    header_left, header_right = st.columns([4, 1])
    with header_left:
        st.caption(st.session_state.paper_name)
        st.title(f"Question {index + 1} of {len(questions)}")
    with header_right:
        st.metric("⏱️ Time Left", f"{mins:02d}:{secs:02d}")

    st.progress((index + 1) / len(questions))

    if question["passage_id"]:
        st.subheader(question["passage_title"] or "Passage")
        if question["passage_content"]:
            st.markdown(question["passage_content"], unsafe_allow_html=True)
        if question["passage_image"]:
            passage_path = Path(question["passage_image"])
            if passage_path.exists():
                st.image(str(passage_path), use_container_width=True)
        st.divider()

    st.markdown(f"### Question {question['question_number']}")
    if question["question_html"]:
        st.markdown(question["question_html"], unsafe_allow_html=True)
    if question["question_image"]:
        image_path = Path(question["question_image"])
        if image_path.exists():
            st.image(str(image_path), width=600)
    st.divider()

    if question["question_type"] == "single":
        option_letters = [option["option_letter"] for option in options]
        option_lookup = {option["option_letter"]: option["option_text"] for option in options}
        current_answer = st.session_state.responses.get(question_id)
        selected_index = option_letters.index(current_answer) if current_answer in option_letters else None
        answer = st.radio(
            "Select your answer",
            option_letters,
            index=selected_index,
            format_func=lambda letter: f"{letter}. {option_lookup[letter]}",
            key=f"exam_single_{question_id}",
        )
        if answer is not None:
            st.session_state.responses[question_id] = answer
    else:
        st.write("**Select all answers that apply:**")
        current_answers = set(st.session_state.responses.get(question_id, []))
        selected_answers = []
        for option in options:
            letter = option["option_letter"]
            checked = st.checkbox(
                f"{letter}. {option['option_text']}",
                value=letter in current_answers,
                key=f"exam_multi_{question_id}_{letter}",
            )
            if checked:
                selected_answers.append(letter)
        if selected_answers:
            st.session_state.responses[question_id] = selected_answers
        else:
            st.session_state.responses.pop(question_id, None)

    answered_count = len(st.session_state.responses)
    st.caption(f"Answered: {answered_count} / {len(questions)}")
    st.divider()

    previous_col, next_col, finish_col = st.columns(3)
    with previous_col:
        if st.button("⬅ Previous", use_container_width=True, disabled=(index == 0)):
            st.session_state.question_index -= 1
            st.rerun()
    with next_col:
        if st.button(
            "Next ➡",
            use_container_width=True,
            disabled=(index == len(questions) - 1),
        ):
            st.session_state.question_index += 1
            st.rerun()
    with finish_col:
        if st.button("🏁 Finish Exam", type="primary", use_container_width=True):
            st.session_state.confirm_finish = True
            st.rerun()

    if st.session_state.confirm_finish:
        unanswered = len(questions) - answered_count
        if unanswered:
            st.warning(f"You still have {unanswered} unanswered question(s).")
        st.write("**Are you sure you want to finish the exam?**")
        confirm_col, cancel_col = st.columns(2)
        with confirm_col:
            if st.button("Yes, Finish", type="primary", use_container_width=True):
                finish_exam()
        with cancel_col:
            if st.button("Continue Exam", use_container_width=True):
                st.session_state.confirm_finish = False
                st.rerun()

conn.close()
