from pathlib import Path

import pandas as pd
import streamlit as st

from utils.storage import *

st.set_page_config(page_title="Results", page_icon="🏆", layout="wide")
st.title("🏆 Results & Self Review")
init_db()

student = st.session_state.get("student", "Rishan")


def parse_answer(value):
    if not value:
        return []
    return [part.strip() for part in value.split(",") if part.strip()]


def answer_text(selected_answer, options):
    letters = parse_answer(selected_answer)
    if not letters:
        return "Not Answered"

    lookup = {row["option_letter"]: row["option_text"] for row in options}
    return ", ".join(
        f"{letter}. {lookup.get(letter, '')}"
        for letter in letters
    )


# Always load the authoritative history for the student.
# Publishing a different paper must never change which historical attempts exist.
attempts = get_attempts(student)

if not attempts:
    st.info("No completed exam attempts yet.")
    if st.button("📝 Go to Exam", width="stretch"):
        st.switch_page("pages/Exam.py")
    st.stop()

# Latest Result means latest completed attempt across all papers.
latest_attempt = attempts[0]

latest_tab, progress_tab = st.tabs(["🏆 Latest Result", "📈 Progress & History"])

with latest_tab:
    attempt = latest_attempt
    attempt_id = attempt["id"]
    st.session_state.current_attempt_id = attempt_id

    st.info(
        f"**{attempt['paper_name']}**  \n"
        f"{attempt['subject']} • {attempt['year']}"
    )

    attempt_number = attempt_number_for(
        attempt["paper_id"],
        student,
        attempt_id,
    )

    m1, m2, m3 = st.columns(3)
    with m1:
        st.metric("Score", f"{attempt['score']}/{attempt['total']}")
    with m2:
        st.metric("Percentage", f"{attempt['percentage']}%")
    with m3:
        minutes, seconds = divmod(int(attempt["time_taken"]), 60)
        st.metric("Time Taken", f"{minutes:02d}:{seconds:02d}")

    st.caption(f"Attempt #{attempt_number} • {attempt['attempt_date']}")

    answers = get_attempt_answers(attempt_id)
    original_incorrect = [row for row in answers if not row["is_correct"]]

    is_just_finished = (
        attempt_id == st.session_state.get("current_attempt_id")
        and st.session_state.get("_latest_attempt_snapshot", {}).get("id") == attempt_id
    )

    corrected_ids = set() if is_just_finished else corrected_question_ids(attempt_id)
    remaining = [
        row
        for row in original_incorrect
        if row["question_id"] not in corrected_ids
    ]

    original_correct = len(answers) - len(original_incorrect)
    corrected_count = len(original_incorrect) - len(remaining)
    reviewed_score = original_correct + corrected_count
    reviewed_percentage = round(reviewed_score / len(answers) * 100, 1) if answers else 0
    improvement_pp = round(reviewed_percentage - float(attempt["percentage"]), 1)

    st.divider()
    st.markdown("### Exam → Self-Review Progress")

    r1, r2, r3 = st.columns(3)
    with r1:
        st.metric(
            "Original Exam",
            f"{attempt['score']}/{attempt['total']}",
            f"{attempt['percentage']}%",
        )
    with r2:
        st.metric(
            "After Self Review",
            f"{reviewed_score}/{len(answers)}",
            f"{reviewed_percentage}%",
        )
    with r3:
        st.metric(
            "Improvement",
            f"+{corrected_count} question(s)",
            f"{improvement_pp:+.1f} pp",
        )

    c1, c2, c3 = st.columns(3)
    with c1:
        st.metric("✅ Correct in Exam", original_correct)
    with c2:
        st.metric("🔁 Corrected in Review", corrected_count)
    with c3:
        st.metric("❌ Still to Review", len(remaining))

    last_review = None if is_just_finished else latest_review_status(attempt_id)
    if last_review:
        st.caption(
            f"Latest self-review: #{last_review['review_number']} • "
            f"{last_review['score']}/{last_review['total']} corrected in that review • "
            f"{last_review['review_date']}"
        )

    if not original_incorrect:
        st.success("All questions were correct in this exam. No self-review is needed.")
    elif not remaining:
        st.success(
            "All questions that were incorrect in the exam have now been corrected through self-review."
        )
    else:
        review_mode = st.session_state.get("review_mode", False)

        if not review_mode:
            st.markdown("### Questions to Review")
            st.write(
                "Incorrect questions: "
                + ", ".join(str(row["question_number"]) for row in remaining)
            )
            st.caption(
                "The correct answers stay hidden. Review all remaining questions, "
                "choose new answers, then submit the whole review together."
            )

            if st.button(
                f"🔍 Start Self Review — {len(remaining)} Question(s)",
                type="primary",
                width="stretch",
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
                        passage_image = displayable_file(row["passage_image"])
                        if passage_image:
                            st.image(passage_image, width="stretch")

                    st.divider()

                if row["question_html"]:
                    st.markdown(row["question_html"], unsafe_allow_html=True)

                if row["question_image"]:
                    question_image = displayable_file(row["question_image"])
                    if question_image:
                        st.image(question_image, width=600)

                options = get_options(row["question_id"])
                st.warning(
                    f"Your exam answer: **{answer_text(row['selected_answer'], options)}**"
                )

                option_letters = [option["option_letter"] for option in options]
                option_lookup = {
                    option["option_letter"]: option["option_text"]
                    for option in options
                }
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
                if st.button(
                    "✅ Submit Self Review",
                    type="primary",
                    width="stretch",
                ):
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
                        existing_reviews = get_review_attempts(attempt_id)
                        review_number = len(existing_reviews) + 1
                        review_score = 0
                        evaluated = []

                        for row in remaining:
                            options = get_options(row["question_id"])
                            correct_letters = {
                                option["option_letter"]
                                for option in options
                                if option["is_correct"]
                            }
                            selected = review_responses[row["question_id"]]
                            is_correct = set(selected) == correct_letters

                            if is_correct:
                                review_score += 1

                            evaluated.append(
                                {
                                    "question_id": row["question_id"],
                                    "question_number": row["question_number"],
                                    "selected_answer": ",".join(sorted(selected)),
                                    "is_correct": is_correct,
                                }
                            )

                        create_review_attempt(
                            attempt_id,
                            review_number,
                            review_score,
                            len(remaining),
                            evaluated,
                        )

                        st.session_state.review_mode = False
                        st.session_state.review_result = {
                            "number": review_number,
                            "score": review_score,
                            "total": len(remaining),
                            "items": [
                                (item["question_number"], item["is_correct"])
                                for item in evaluated
                            ],
                        }
                        st.rerun()

            with cancel_col:
                if st.button("Cancel Review", width="stretch"):
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
            st.write(
                f"{'✅' if is_correct else '❌'} Question {qn} — "
                f"{'Corrected' if is_correct else 'Still needs review'}"
            )
        st.caption("Correct answers remain hidden for questions that still need review.")

    st.divider()
    if st.button("📝 Take Exam Again", width="stretch"):
        st.session_state.started = False
        st.session_state.paper_id = None
        st.session_state.paper_name = None
        st.session_state.question_index = 0
        st.session_state.responses = {}
        st.session_state.start_time = None
        st.session_state.confirm_finish = False
        st.session_state.review_mode = False
        st.switch_page("pages/Exam.py")


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

    paper_attempts = [
        row
        for row in reversed(attempts)
        if row["paper_id"] == selected_paper_id
    ]

    history = []
    for i, row in enumerate(paper_attempts, start=1):
        minutes, seconds = divmod(int(row["time_taken"]), 60)
        timer_minutes = row.get("timer_minutes")
        time_used_percentage = (
            round(int(row["time_taken"]) / (int(timer_minutes) * 60) * 100, 1)
            if timer_minutes and int(timer_minutes) > 0
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
        "Compare them together rather than treating either measure alone as the goal."
    )

    comparison_df = chart_df[["Score %", "Time Used %"]]
    if comparison_df["Time Used %"].notna().any():
        st.line_chart(comparison_df)
    else:
        st.info(
            "Time comparison will appear for new attempts. Older attempts were saved before "
            "the selected exam duration was recorded."
        )
        st.line_chart(chart_df[["Score %"]])

    st.markdown("### Exam History")
    display_df = pd.DataFrame(history)[
        ["Attempt", "Date", "Score", "Score %", "Time", "Exam Time", "Time Used %"]
    ]
    st.dataframe(display_df.iloc[::-1], hide_index=True, width="stretch")
