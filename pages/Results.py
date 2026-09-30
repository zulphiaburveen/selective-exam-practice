from pathlib import Path

import pandas as pd
import streamlit as st

from utils.storage import *

st.set_page_config(page_title="Results", page_icon="🏆", layout="wide")
st.title("🏆 Results & Self Review")
init_db()

conn = get_connection()
cur = conn.cursor()
student = st.session_state.get("student", "Rishan")


def parse_answer(value):
    if not value:
        return []
    return [part.strip() for part in value.split(",") if part.strip()]


def load_options(question_id):
    cur.execute(
        """
        SELECT option_letter, option_text, is_correct
        FROM options
        WHERE question_id = ?
        ORDER BY option_letter
        """,
        (question_id,),
    )
    return cur.fetchall()


def answer_text(selected_answer, options):
    letters = parse_answer(selected_answer)
    if not letters:
        return "Not Answered"
    lookup = {row["option_letter"]: row["option_text"] for row in options}
    return ", ".join(f"{letter}. {lookup.get(letter, '')}" for letter in letters)


def load_attempt_answers(attempt_id):
    cur.execute(
        """
        SELECT aa.id AS attempt_answer_id,
               aa.question_id,
               aa.selected_answer,
               aa.is_correct,
               q.question_number,
               q.question_html,
               q.question_image,
               q.question_type,
               q.passage_id,
               p.title AS passage_title,
               p.content AS passage_content,
               p.image AS passage_image
        FROM attempt_answers aa
        JOIN questions q ON q.id = aa.question_id
        LEFT JOIN passages p ON p.id = q.passage_id
        WHERE aa.attempt_id = ?
        ORDER BY q.question_number
        """,
        (attempt_id,),
    )
    return cur.fetchall()


def latest_review_status(attempt_id):
    cur.execute(
        """
        SELECT ra.id, ra.review_number, ra.score, ra.total, ra.review_date
        FROM review_attempts ra
        WHERE ra.attempt_id = ?
        ORDER BY ra.review_number DESC, ra.id DESC
        LIMIT 1
        """,
        (attempt_id,),
    )
    return cur.fetchone()


def corrected_question_ids(attempt_id):
    cur.execute(
        """
        SELECT DISTINCT rans.question_id
        FROM review_answers rans
        JOIN review_attempts ra ON ra.id = rans.review_attempt_id
        WHERE ra.attempt_id = ? AND rans.is_correct = 1
        """,
        (attempt_id,),
    )
    return {row["question_id"] for row in cur.fetchall()}


def attempt_number_for(row):
    cur.execute(
        """
        SELECT COUNT(*)
        FROM attempts
        WHERE paper_id = ? AND student = ? AND id <= ?
        """,
        (row["paper_id"], student, row["id"]),
    )
    return cur.fetchone()[0]


# -------------------------------------------------------
# LOAD ATTEMPTS
# -------------------------------------------------------
cur.execute(
    """
    SELECT a.id, a.paper_id, a.score, a.total, a.percentage,
           a.time_taken, a.timer_minutes, a.attempt_date, p.name AS paper_name,
           p.subject, p.year
    FROM attempts a
    JOIN papers p ON p.id = a.paper_id
    WHERE a.student = ?
    ORDER BY a.id DESC
    """,
    (student,),
)
attempts = cur.fetchall()

if not attempts:
    st.info("No completed exam attempts yet.")
    if st.button("📝 Go to Exam", use_container_width=True):
        st.switch_page("Exam.py")
    conn.close()
    st.stop()

latest_attempt = attempts[0]

# -------------------------------------------------------
# TABS
# -------------------------------------------------------
latest_tab, progress_tab = st.tabs(["🏆 Latest Result", "📈 Progress & History"])

with latest_tab:
    attempt = latest_attempt
    attempt_id = attempt["id"]
    st.session_state.current_attempt_id = attempt_id

    st.info(
        f"**{attempt['paper_name']}**  \n"
        f"{attempt['subject']} • {attempt['year']}"
    )

    attempt_number = attempt_number_for(attempt)
    m1, m2, m3 = st.columns(3)
    with m1:
        st.metric("Score", f"{attempt['score']}/{attempt['total']}")
    with m2:
        st.metric("Percentage", f"{attempt['percentage']}%")
    with m3:
        minutes, seconds = divmod(attempt["time_taken"], 60)
        st.metric("Time Taken", f"{minutes:02d}:{seconds:02d}")
    st.caption(f"Attempt #{attempt_number} • {attempt['attempt_date']}")

    answers = load_attempt_answers(attempt_id)
    original_incorrect = [row for row in answers if not row["is_correct"]]
    corrected_ids = corrected_question_ids(attempt_id)
    remaining = [row for row in original_incorrect if row["question_id"] not in corrected_ids]

    original_correct = len(answers) - len(original_incorrect)
    corrected_count = len(original_incorrect) - len(remaining)
    reviewed_score = original_correct + corrected_count
    reviewed_percentage = round(reviewed_score / len(answers) * 100, 1) if answers else 0
    improvement_pp = round(reviewed_percentage - float(attempt["percentage"]), 1)

    st.divider()
    st.markdown("### Exam → Self-Review Progress")
    r1, r2, r3 = st.columns(3)
    with r1:
        st.metric("Original Exam", f"{attempt['score']}/{attempt['total']}", f"{attempt['percentage']}%")
    with r2:
        st.metric("After Self Review", f"{reviewed_score}/{len(answers)}", f"{reviewed_percentage}%")
    with r3:
        st.metric("Improvement", f"+{corrected_count} question(s)", f"{improvement_pp:+.1f} pp")

    c1, c2, c3 = st.columns(3)
    with c1:
        st.metric("✅ Correct in Exam", original_correct)
    with c2:
        st.metric("🔁 Corrected in Review", corrected_count)
    with c3:
        st.metric("❌ Still to Review", len(remaining))

    last_review = latest_review_status(attempt_id)
    if last_review:
        st.caption(
            f"Latest self-review: #{last_review['review_number']} • "
            f"{last_review['score']}/{last_review['total']} corrected in that review • "
            f"{last_review['review_date']}"
        )

    if not original_incorrect:
        st.success("All questions were correct in this exam. No self-review is needed.")
    elif not remaining:
        st.success("All questions that were incorrect in the exam have now been corrected through self-review.")
    else:
        review_mode = st.session_state.get("review_mode", False)

        if not review_mode:
            st.markdown("### Questions to Review")
            st.write(
                "Incorrect questions: "
                + ", ".join(str(row["question_number"]) for row in remaining)
            )
            st.caption(
                "The correct answers stay hidden. Review all remaining questions, choose new answers, "
                "then submit the whole review together."
            )
            if st.button(
                f"🔍 Start Self Review — {len(remaining)} Question(s)",
                type="primary",
                use_container_width=True,
            ):
                st.session_state.review_mode = True
                st.session_state.review_version = st.session_state.get("review_version", 0) + 1
                st.rerun()
        else:
            st.markdown("## 🔍 Self Review")
            st.info(
                "Re-read each question and answer all of them before submitting. "
                "No right/wrong feedback is shown until the complete review is submitted."
            )

            review_version = st.session_state.get("review_version", 0)
            review_responses = {}

            for row in remaining:
                qn = row["question_number"]
                st.divider()
                st.markdown(f"## Question {qn}")

                if row["passage_id"]:
                    st.markdown(f"### 📖 {row['passage_title'] or 'Passage'}")
                    if row["passage_content"]:
                        st.markdown(row["passage_content"], unsafe_allow_html=True)
                    if row["passage_image"]:
                        passage_path = Path(row["passage_image"])
                        if passage_path.exists():
                            st.image(str(passage_path), use_container_width=True)
                    st.divider()

                if row["question_html"]:
                    st.markdown(row["question_html"], unsafe_allow_html=True)
                if row["question_image"]:
                    question_path = Path(row["question_image"])
                    if question_path.exists():
                        st.image(str(question_path), width=600)

                options = load_options(row["question_id"])
                st.warning(f"Your exam answer: **{answer_text(row['selected_answer'], options)}**")
                option_letters = [option["option_letter"] for option in options]
                option_lookup = {option["option_letter"]: option["option_text"] for option in options}
                base_key = f"batch_review_{attempt_id}_{review_version}_{row['question_id']}"

                if row["question_type"] == "single":
                    selected = st.radio(
                        "Choose your new answer",
                        option_letters,
                        index=None,
                        format_func=lambda letter, lookup=option_lookup: f"{letter}. {lookup[letter]}",
                        key=f"{base_key}_single",
                    )
                    review_responses[row["question_id"]] = [selected] if selected else []
                else:
                    st.write("**Select all answers that apply:**")
                    chosen = []
                    for option in options:
                        letter = option["option_letter"]
                        if st.checkbox(
                            f"{letter}. {option['option_text']}",
                            key=f"{base_key}_{letter}",
                        ):
                            chosen.append(letter)
                    review_responses[row["question_id"]] = chosen

            st.divider()
            submit_col, cancel_col = st.columns(2)
            with submit_col:
                if st.button("✅ Submit Self Review", type="primary", use_container_width=True):
                    unanswered = [
                        row["question_number"]
                        for row in remaining
                        if not review_responses.get(row["question_id"])
                    ]
                    if unanswered:
                        st.error(
                            "Answer every review question before submitting. Missing: "
                            + ", ".join(map(str, unanswered))
                        )
                    else:
                        cur.execute(
                            "SELECT COUNT(*) FROM review_attempts WHERE attempt_id = ?",
                            (attempt_id,),
                        )
                        review_number = cur.fetchone()[0] + 1
                        evaluated = []
                        review_score = 0

                        for row in remaining:
                            options = load_options(row["question_id"])
                            correct_letters = {
                                option["option_letter"] for option in options if option["is_correct"]
                            }
                            selected = review_responses[row["question_id"]]
                            is_correct = set(selected) == correct_letters
                            if is_correct:
                                review_score += 1
                            evaluated.append((row, selected, is_correct))

                        cur.execute(
                            """
                            INSERT INTO review_attempts(attempt_id, review_number, score, total)
                            VALUES (?, ?, ?, ?)
                            """,
                            (attempt_id, review_number, review_score, len(remaining)),
                        )
                        review_attempt_id = cur.lastrowid

                        for row, selected, is_correct in evaluated:
                            cur.execute(
                                """
                                INSERT INTO review_answers(
                                    review_attempt_id, question_id, selected_answer, is_correct
                                ) VALUES (?, ?, ?, ?)
                                """,
                                (
                                    review_attempt_id,
                                    row["question_id"],
                                    ",".join(sorted(selected)),
                                    1 if is_correct else 0,
                                ),
                            )

                        conn.commit()
                        st.session_state.review_mode = False
                        st.session_state.review_result = {
                            "number": review_number,
                            "score": review_score,
                            "total": len(remaining),
                            "items": [
                                (row["question_number"], is_correct)
                                for row, _, is_correct in evaluated
                            ],
                        }
                        st.rerun()

            with cancel_col:
                if st.button("Cancel Review", use_container_width=True):
                    st.session_state.review_mode = False
                    st.rerun()

    review_result = st.session_state.pop("review_result", None)
    if review_result:
        st.divider()
        st.markdown(f"### Self Review #{review_result['number']} Result")
        st.success(
            f"Corrected **{review_result['score']} of {review_result['total']}** "
            "questions in this review."
        )
        for qn, is_correct in review_result["items"]:
            st.write(f"{'✅' if is_correct else '❌'} Question {qn} — {'Corrected' if is_correct else 'Still needs review'}")
        st.caption("Correct answers remain hidden for questions that still need review.")

    st.divider()
    if st.button("📝 Take Exam Again", use_container_width=True):
        st.session_state.started = False
        st.session_state.show_results = False
        st.session_state.paper_id = None
        st.session_state.paper_name = None
        st.session_state.question_index = 0
        st.session_state.responses = {}
        st.session_state.start_time = None
        st.session_state.confirm_finish = False
        st.session_state.review_mode = False
        st.switch_page("Exam.py")


with progress_tab:
    st.subheader("📈 Progress & History")

    paper_rows = []
    seen = set()
    for row in attempts:
        if row["paper_id"] not in seen:
            seen.add(row["paper_id"])
            paper_rows.append(row)

    paper_lookup = {
        f"{row['paper_name']} ({row['year']})": row["paper_id"]
        for row in paper_rows
    }
    default_paper_id = latest_attempt["paper_id"]
    labels = list(paper_lookup.keys())
    default_label_index = next(
        (i for i, label in enumerate(labels) if paper_lookup[label] == default_paper_id),
        0,
    )
    selected_paper_label = st.selectbox(
        "Paper",
        labels,
        index=default_label_index,
        key="progress_paper",
    )
    selected_paper_id = paper_lookup[selected_paper_label]

    paper_attempts = [row for row in reversed(attempts) if row["paper_id"] == selected_paper_id]

    history = []
    for i, row in enumerate(paper_attempts, start=1):
        minutes, seconds = divmod(row["time_taken"], 60)
        timer_minutes = row["timer_minutes"]
        time_used_percentage = (
            round(row["time_taken"] / (timer_minutes * 60) * 100, 1)
            if timer_minutes and timer_minutes > 0
            else None
        )
        history.append(
            {
                "Attempt": i,
                "Date": row["attempt_date"],
                "Score": f"{row['score']}/{row['total']}",
                "Score %": float(row["percentage"]),
                "Time": f"{minutes:02d}:{seconds:02d}",
                "Exam Time": f"{timer_minutes} min" if timer_minutes else "Older attempt",
                "Time Used %": time_used_percentage,
            }
        )

    first_percentage = history[0]["Score %"]
    latest_percentage = history[-1]["Score %"]
    change = round(latest_percentage - first_percentage, 1)

    m1, m2, m3, m4 = st.columns(4)
    with m1:
        st.metric("Attempts", len(history))
    with m2:
        st.metric("First Attempt", f"{first_percentage}%")
    with m3:
        st.metric("Latest Attempt", f"{latest_percentage}%")
    with m4:
        st.metric("Change", f"{change:+.1f} pp")

    chart_df = pd.DataFrame(history).set_index("Attempt")
    st.markdown("### Score & Time Comparison")
    st.caption(
        "Score % shows accuracy. Time Used % shows how much of the selected exam time was used. "
        "Lower time use together with maintained or improving accuracy can indicate growing fluency."
    )
    comparison_df = chart_df[["Score %", "Time Used %"]]
    if comparison_df["Time Used %"].notna().any():
        st.line_chart(comparison_df)
    else:
        st.info(
            "Time comparison will appear for new attempts. Older attempts were saved before the selected exam duration was recorded."
        )
        st.line_chart(chart_df[["Score %"]])

    st.markdown("### Exam History")
    display_df = pd.DataFrame(history)[["Attempt", "Date", "Score", "Score %", "Time", "Exam Time", "Time Used %"]]
    st.dataframe(display_df.iloc[::-1], hide_index=True, use_container_width=True)

    st.caption(
        "Progress is shown from practice history. Compare accuracy and time together rather than treating either measure alone as the goal."
    )

conn.close()
