import streamlit as st
from pathlib import Path
import pandas as pd
import time
from streamlit_autorefresh import st_autorefresh

# ------------------------------------------------
# CONFIG
# ------------------------------------------------

st.set_page_config(
    page_title="Selective Exam Practice",
    page_icon="📘",
    layout="wide"
)

PASSAGE_FOLDER = Path("English2022/passages")
QUESTION_FOLDER = Path("English2022/questions")
ANSWER_FILE = Path("English2022/answers.csv")

# import json

# SETTINGS_FILE = Path("data/settings.json")

# with open(SETTINGS_FILE) as f:
#     settings = json.load(f)

# ACTIVE_PAPER = settings["active_paper"]

# PAPER_FOLDER = Path("papers") / ACTIVE_PAPER

# PASSAGE_FOLDER = PAPER_FOLDER / "passages"
# QUESTION_FOLDER = PAPER_FOLDER / "questions"
# ANSWER_FILE = PAPER_FOLDER / "answers.csv"

# ------------------------------------------------
# LOAD DATA
# ------------------------------------------------

passages = sorted(PASSAGE_FOLDER.glob("*.png"))
questions = sorted(QUESTION_FOLDER.glob("q*.png"))

answers_df = pd.read_csv(ANSWER_FILE)
correct_answers = dict(zip(answers_df.Question, answers_df.Answer))

# ------------------------------------------------
# SESSION STATE
# ------------------------------------------------

defaults = {
    "started": False,
    "show_results": False,
    "question": 1,
    "responses": {},
    "timer": 30,
    "start_time": None,
    "score": 0,
    "review": []
}

for key, value in defaults.items():
    if key not in st.session_state:
        st.session_state[key] = value

# ------------------------------------------------
# HOME PAGE
# ------------------------------------------------

if not st.session_state.started and not st.session_state.show_results:

    st.title("📘 Selective Exam Practice")

    st.subheader("Welcome Rishan!")

    st.success("ICAS English 2022")

    timer = st.radio(
        "Choose Timer",
        [30,20,10],
        horizontal=True
    )

    if st.button("🚀 Start Practice", use_container_width=True):

        st.session_state.started = True
        st.session_state.show_results = False
        st.session_state.question = 1
        st.session_state.responses = {}
        st.session_state.timer = timer
        st.session_state.start_time = time.time()

        st.rerun()

# ------------------------------------------------
# EXAM
# ------------------------------------------------

elif st.session_state.started:

    # Refresh every second
    st_autorefresh(interval=1000, key="timer_refresh")

    remaining = max(
    0,
    int(
        st.session_state.timer * 60
        - (time.time() - st.session_state.start_time)
    )
)

    if remaining <= 0:
        st.session_state.started = False
        st.session_state.show_results = True
        st.rerun()

    mins = int(remaining // 60)
    secs = int(remaining % 60)

    c1, c2 = st.columns([4,1])

    with c1:
        st.title(
            f"Question {st.session_state.question}/{len(questions)}"
        )

    with c2:
        st.metric(
            "Time Left",
            f"{mins:02d}:{secs:02d}"
        )

    st.progress(
        st.session_state.question / len(questions)
    )

    left, right = st.columns([1.4,1])

    with left:

        st.subheader("Reading Passage")

        for img in passages:
            st.image(img, use_container_width=True)

    with right:

        st.subheader("Question")

        st.image(
            QUESTION_FOLDER /
            f"q{st.session_state.question}.png",
            use_container_width=True
        )

        options = [
            "-- Select Answer --",
            "A",
            "B",
            "C",
            "D"
        ]

        current = st.session_state.responses.get(
            st.session_state.question,
            "-- Select Answer --"
        )

        answer = st.selectbox(
            "Answer",
            options,
            index=options.index(current),
            key=f"answer_{st.session_state.question}"
        )

        if answer == "-- Select Answer --":
            st.session_state.responses.pop(
                st.session_state.question,
                None
            )
        else:
            st.session_state.responses[
                st.session_state.question
            ] = answer

        col1,col2,col3 = st.columns(3)

        with col1:

            if st.button("⬅ Previous"):

                if st.session_state.question > 1:

                    st.session_state.question -= 1
                    st.rerun()

        with col2:

            if st.session_state.question < len(questions):

                if st.button("Next ➡"):

                    st.session_state.question += 1
                    st.rerun()

            else:

                st.button(
                    "Next ➡",
                    disabled=True
                )

        with col3:

            if st.button("🏁 Finish"):

                # Save current answer
                if answer != "-- Select Answer --":
                    st.session_state.responses[
                        st.session_state.question
                    ] = answer

                score = 0
                review = []

                for q in range(1, len(questions) + 1):

                    user = st.session_state.responses.get(
                        q,
                        "Not Answered"
                    )

                    correct = correct_answers.get(q, "")

                    result = user == correct

                    if result:
                        score += 1

                    review.append({
                        "Question": q,
                        "Your Answer": user,
                        "Correct Answer": correct,
                        "Result": "✅" if result else "❌"
                    })

                st.session_state.score = score
                st.session_state.review = review

                st.session_state.started = False
                st.session_state.show_results = True

                st.rerun()

# ------------------------------------------------
# RESULTS PAGE
# ------------------------------------------------

elif st.session_state.show_results:

    st.title("🏆 Exam Completed")

    st.success(
        f"Score: {st.session_state.score}/{len(questions)}"
    )

    percentage = round(
        st.session_state.score / len(questions) * 100,
        1
    )

    st.metric(
        "Percentage",
        f"{percentage}%"
    )

    st.divider()

    st.subheader("Review")

    review_df = pd.DataFrame(
        st.session_state.review
    )

    st.dataframe(
        review_df,
        hide_index=True,
        use_container_width=True
    )

    st.divider()

    if st.button(
        "🔄 Practice Again",
        use_container_width=True
    ):

        st.session_state.started = False
        st.session_state.show_results = False
        st.session_state.question = 1
        st.session_state.responses = {}
        st.session_state.score = 0
        st.session_state.review = []
        st.session_state.start_time = None

        st.rerun()