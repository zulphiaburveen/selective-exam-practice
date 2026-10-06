import time
from pathlib import Path

import streamlit as st
from streamlit_autorefresh import st_autorefresh

from utils.storage import *


# =======================================================
# PAGE
# =======================================================

st.set_page_config(
    page_title="Exam",
    page_icon="📝",
    layout="wide"
)

st.title("📝 Selective Exam Practice")

init_db()


# =======================================================
# SESSION STATE
# =======================================================

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
    "exam_bundle": None,
    "go_to_results": False,
    "finish_saved_attempt_id": None,
}

for key, value in DEFAULTS.items():

    if key not in st.session_state:

        st.session_state[key] = value


# =======================================================
# NAVIGATE TO RESULTS
# =======================================================

# Important:
# Do the page switch at the beginning of a fresh rerun,
# rather than from inside the Finish button callback.




# =======================================================
# ANSWER HELPERS
# =======================================================

def normalise_answer(
    question_type,
    answer
):

    if question_type == "single":

        return (
            {answer}
            if answer
            else set()
        )

    return set(
        answer or []
    )


def serialise_answer(
    question_type,
    answer
):

    if question_type == "single":

        return (
            answer
            or ""
        )

    return ",".join(
        sorted(
            answer or []
        )
    )


# =======================================================
# CLEAR QUESTION WIDGETS
# =======================================================

def clear_exam_widget_state():

    for key in list(
        st.session_state.keys()
    ):

        if (
            key.startswith(
                "exam_single_"
            )
            or
            key.startswith(
                "exam_multi_"
            )
        ):

            del st.session_state[
                key
            ]


# =======================================================
# RESET EXAM
# =======================================================

def reset_exam():

    clear_exam_widget_state()

    st.session_state.started = False

    st.session_state.paper_id = None

    st.session_state.paper_name = None

    st.session_state.question_index = 0

    st.session_state.responses = {}

    st.session_state.start_time = None

    st.session_state.confirm_finish = False

    st.session_state.current_attempt_id = None

    st.session_state.exam_bundle = None

    st.session_state.go_to_results = False
    st.session_state.finish_saved_attempt_id = None


# =======================================================
# FINISH EXAM
# =======================================================

def finish_exam():

    # If a previous click already saved this exam, never create a duplicate.
    if st.session_state.get("finish_saved_attempt_id"):
        st.session_state.current_attempt_id = st.session_state.finish_saved_attempt_id
        st.session_state.started = False
        st.session_state.confirm_finish = False
        st.session_state.go_to_results = True
        st.rerun()

    # ---------------------------------------------------
    # GET EXISTING EXAM BUNDLE
    # ---------------------------------------------------

    bundle = st.session_state.get(
        "exam_bundle"
    )

    # Normally this is already in memory.
    # Only reload if it somehow disappeared.

    if not bundle:

        with st.spinner(
            "Loading exam..."
        ):

            bundle = get_exam_bundle(
                st.session_state.paper_id
            )

        st.session_state[
            "exam_bundle"
        ] = bundle

    questions = bundle[
        "questions"
    ]

    options_by_question = bundle[
        "options"
    ]

    # ---------------------------------------------------
    # CALCULATE SCORE LOCALLY
    # ---------------------------------------------------

    score = 0

    answer_rows = []

    for question in questions:

        question_id = question[
            "id"
        ]

        options = (
            options_by_question.get(
                question_id,
                []
            )
        )

        correct_answers = {
            option[
                "option_letter"
            ]
            for option
            in options
            if option[
                "is_correct"
            ]
        }

        user_answer = (
            st.session_state.responses.get(
                question_id
            )
        )

        selected_answers = (
            normalise_answer(
                question[
                    "question_type"
                ],
                user_answer
            )
        )

        is_correct = (
            selected_answers
            ==
            correct_answers
        )

        if is_correct:

            score += 1

        answer_rows.append(
            {
                "question_id":
                    question_id,

                "selected_answer":
                    serialise_answer(
                        question[
                            "question_type"
                        ],
                        user_answer
                    ),

                "is_correct":
                    is_correct,
            }
        )

    # ---------------------------------------------------
    # RESULT VALUES
    # ---------------------------------------------------

    total = len(
        questions
    )

    percentage = (
        round(
            score
            /
            total
            *
            100,
            1
        )
        if total
        else 0
    )

    elapsed_seconds = int(
        time.time()
        -
        st.session_state.start_time
    )

    # ---------------------------------------------------
    # SAVE ATTEMPT
    # ---------------------------------------------------

    try:

        with st.spinner(
            "Saving your exam result..."
        ):

            attempt = create_attempt(
                paper_id=(
                    st.session_state.paper_id
                ),
                student=(
                    st.session_state.student
                ),
                score=score,
                total=total,
                percentage=percentage,
                time_taken=(
                    elapsed_seconds
                ),
                timer_minutes=(
                    st.session_state.timer_minutes
                ),
                answer_rows=(
                    answer_rows
                ),
            )

    except Exception as e:

        st.error(
            "The exam could not be saved."
        )

        st.exception(
            e
        )

        return

    # ---------------------------------------------------
    # SAVE ATTEMPT ID
    # ---------------------------------------------------

    st.session_state[
        "current_attempt_id"
    ] = attempt["id"]

    # Idempotency guard: even if navigation is interrupted, a second
    # click cannot create another attempt.
    st.session_state.finish_saved_attempt_id = attempt["id"]

    # ---------------------------------------------------
    # END EXAM
    # ---------------------------------------------------

    st.session_state.started = False

    st.session_state.confirm_finish = False

    st.session_state.exam_bundle = None

    clear_exam_widget_state()

    # ---------------------------------------------------
    # NAVIGATE ON NEXT CLEAN RERUN
    # ---------------------------------------------------

    st.session_state[
        "go_to_results"
    ] = True

    st.rerun()


# =======================================================
# START SCREEN
# =======================================================

if not st.session_state.started:

    st.subheader(
        f"Welcome "
        f"{st.session_state.student}! 👋"
    )

    # ---------------------------------------------------
    # GET CURRENT PUBLISHED PAPER
    # ---------------------------------------------------

    try:

        selected_paper = (
            get_published_paper()
        )

    except Exception as e:

        st.error(
            "Unable to load "
            "the current paper."
        )

        st.exception(
            e
        )

        st.stop()

    # ---------------------------------------------------
    # NO PAPER
    # ---------------------------------------------------

    if selected_paper is None:

        st.warning(
            "No published paper "
            "is currently available."
        )

        st.info(
            "Publish a paper "
            "from Admin first."
        )

        st.stop()

    # ---------------------------------------------------
    # CURRENT PAPER
    # ---------------------------------------------------

    st.markdown(
        "### 📘 Current Paper"
    )

    st.info(
        f"**{selected_paper['name']}**  \n"
        f"{selected_paper['subject']} "
        f"• "
        f"{selected_paper['year']}"
    )

    # ---------------------------------------------------
    # QUESTION COUNT
    # ---------------------------------------------------

    try:

        questions = get_questions(
            selected_paper[
                "id"
            ]
        )

        question_count = len(
            questions
        )

    except Exception as e:

        st.error(
            "Unable to load questions."
        )

        st.exception(
            e
        )

        st.stop()

    st.info(
        f"📝 "
        f"{question_count} "
        f"question(s)"
    )

    # ---------------------------------------------------
    # EXAM TIME
    # ---------------------------------------------------

    st.markdown(
        "### ⏱️ Choose Exam Time"
    )

    timer_minutes = st.radio(
        "Exam Time",
        [
            60,
            50,
            45,
            40,
            30,
            20,
            10
        ],
        horizontal=True,
        index=0,
        label_visibility="collapsed",
    )

    st.caption(
        f"You will have "
        f"{timer_minutes} minutes "
        f"to complete the exam."
    )

    # ---------------------------------------------------
    # START EXAM
    # ---------------------------------------------------

    if st.button(
        "🚀 Start Exam",
        type="primary",
        width="stretch",
        disabled=(
            question_count == 0
        ),
    ):

        clear_exam_widget_state()

        st.session_state.paper_id = (
            selected_paper[
                "id"
            ]
        )

        st.session_state.paper_name = (
            selected_paper[
                "name"
            ]
        )

        st.session_state.question_index = 0

        st.session_state.responses = {}

        st.session_state.timer_minutes = (
            timer_minutes
        )

        st.session_state.start_time = (
            time.time()
        )

        st.session_state.started = True

        st.session_state.confirm_finish = False

        st.session_state.current_attempt_id = None

        st.session_state.go_to_results = False

        st.session_state.finish_saved_attempt_id = None

        # -----------------------------------------------
        # LOAD COMPLETE EXAM ONCE
        # -----------------------------------------------

        try:

            with st.spinner(
                "Loading exam..."
            ):

                bundle = (
                    get_exam_bundle(
                        selected_paper[
                            "id"
                        ]
                    )
                )

                st.session_state[
                    "exam_bundle"
                ] = bundle

        except Exception as e:

            reset_exam()

            st.error(
                "Unable to load the exam."
            )

            st.exception(
                e
            )

            st.stop()

        st.rerun()


# =======================================================
# EXAM SCREEN
# =======================================================

else:

    # ---------------------------------------------------
    # LOAD EXAM FROM SESSION
    # ---------------------------------------------------

    bundle = st.session_state.get(
        "exam_bundle"
    )

    if not bundle:

        try:

            with st.spinner(
                "Loading exam..."
            ):

                bundle = (
                    get_exam_bundle(
                        st.session_state.paper_id
                    )
                )

                st.session_state[
                    "exam_bundle"
                ] = bundle

        except Exception as e:

            st.error(
                "Unable to load the exam."
            )

            st.exception(
                e
            )

            st.stop()

    questions = bundle[
        "questions"
    ]

    options_by_question = bundle[
        "options"
    ]

    # ---------------------------------------------------
    # NO QUESTIONS
    # ---------------------------------------------------

    if not questions:

        st.error(
            "This paper contains "
            "no questions."
        )

        reset_exam()

        st.stop()

    # ===================================================
    # TIMER
    # ===================================================

    # Do not auto-rerun while the Finish confirmation is visible.
    # Otherwise the 1-second timer refresh can race with the Yes button.
    if not st.session_state.confirm_finish:
        st_autorefresh(
            interval=1000,
            key="exam_timer_refresh"
        )

    total_seconds = (
        st.session_state.timer_minutes
        *
        60
    )

    elapsed_seconds = int(
        time.time()
        -
        st.session_state.start_time
    )

    remaining = max(
        0,
        total_seconds
        -
        elapsed_seconds
    )

    # ---------------------------------------------------
    # AUTO FINISH
    # ---------------------------------------------------

    if remaining <= 0:

        finish_exam()

        st.stop()

    mins, secs = divmod(
        remaining,
        60
    )

    # ===================================================
    # CURRENT QUESTION
    # ===================================================

    index = (
        st.session_state.question_index
    )

    # Safety bounds

    index = max(
        0,
        min(
            index,
            len(questions) - 1
        )
    )

    st.session_state[
        "question_index"
    ] = index

    question = questions[
        index
    ]

    question_id = question[
        "id"
    ]

    options = (
        options_by_question.get(
            question_id,
            []
        )
    )

    # ===================================================
    # HEADER
    # ===================================================

    header_left, header_right = (
        st.columns(
            [4, 1]
        )
    )

    with header_left:

        st.caption(
            st.session_state.paper_name
        )

        st.title(
            f"Question "
            f"{index + 1} "
            f"of "
            f"{len(questions)}"
        )

    with header_right:

        st.metric(
            "⏱️ Time Left",
            f"{mins:02d}:"
            f"{secs:02d}"
        )

    st.progress(
        (index + 1)
        /
        len(questions)
    )

    # ===================================================
    # PASSAGE
    # ===================================================

    if question.get(
        "passage_id"
    ):

        st.subheader(
            question.get(
                "passage_title"
            )
            or
            "Passage"
        )

        if question.get(
            "passage_content"
        ):

            st.markdown(
                question[
                    "passage_content"
                ],
                unsafe_allow_html=True
            )

        if question.get(
            "passage_image"
        ):

            passage_path = Path(
                question[
                    "passage_image"
                ]
            )

            if passage_path.exists():

                st.image(
                    str(
                        passage_path
                    ),
                    width="stretch"
                )

        st.divider()

    # ===================================================
    # QUESTION
    # ===================================================

    st.markdown(
        f"### Question "
        f"{question['question_number']}"
    )

    if question.get(
        "question_html"
    ):

        st.markdown(
            question[
                "question_html"
            ],
            unsafe_allow_html=True
        )

    # ---------------------------------------------------
    # QUESTION IMAGE
    # ---------------------------------------------------

    if question.get(
        "question_image"
    ):

        question_path = Path(
            question[
                "question_image"
            ]
        )

        if question_path.exists():

            st.image(
                str(
                    question_path
                ),
                width=600
            )

    st.divider()

    # ===================================================
    # SINGLE CHOICE
    # ===================================================

    if (
        question[
            "question_type"
        ]
        ==
        "single"
    ):

        option_letters = [
            option[
                "option_letter"
            ]
            for option
            in options
        ]

        option_lookup = {
            option[
                "option_letter"
            ]:
            option[
                "option_text"
            ]
            for option
            in options
        }

        current_answer = (
            st.session_state.responses.get(
                question_id
            )
        )

        selected_index = None

        if (
            current_answer
            in
            option_letters
        ):

            selected_index = (
                option_letters.index(
                    current_answer
                )
            )

        answer = st.radio(
            "Select your answer",
            option_letters,
            index=selected_index,
            format_func=(
                lambda letter:
                    f"{letter}. "
                    f"{option_lookup[letter]}"
            ),
            key=(
                f"exam_single_"
                f"{question_id}"
            ),
        )

        if answer is not None:

            st.session_state.responses[
                question_id
            ] = answer


    # ===================================================
    # MULTIPLE CHOICE
    # ===================================================

    else:

        st.write(
            "**Select all answers "
            "that apply:**"
        )

        current_answers = set(
            st.session_state.responses.get(
                question_id,
                []
            )
        )

        selected_answers = []

        for option in options:

            letter = option[
                "option_letter"
            ]

            checked = st.checkbox(
                f"{letter}. "
                f"{option['option_text']}",
                value=(
                    letter
                    in
                    current_answers
                ),
                key=(
                    f"exam_multi_"
                    f"{question_id}_"
                    f"{letter}"
                ),
            )

            if checked:

                selected_answers.append(
                    letter
                )

        if selected_answers:

            st.session_state.responses[
                question_id
            ] = selected_answers

        else:

            st.session_state.responses.pop(
                question_id,
                None
            )

    # ===================================================
    # ANSWER COUNT
    # ===================================================

    answered_count = len(
        st.session_state.responses
    )

    st.caption(
        f"Answered: "
        f"{answered_count} / "
        f"{len(questions)}"
    )

    st.divider()

    # ===================================================
    # NAVIGATION BUTTONS
    # ===================================================

    previous_col, next_col, finish_col = (
        st.columns(3)
    )

    # ---------------------------------------------------
    # PREVIOUS
    # ---------------------------------------------------

    with previous_col:

        if st.button(
            "⬅ Previous",
            width="stretch",
            disabled=(
                index == 0
            ),
        ):

            st.session_state[
                "question_index"
            ] -= 1

            st.rerun()

    # ---------------------------------------------------
    # NEXT
    # ---------------------------------------------------

    with next_col:

        if st.button(
            "Next ➡",
            width="stretch",
            disabled=(
                index
                ==
                len(questions) - 1
            ),
        ):

            st.session_state[
                "question_index"
            ] += 1

            st.rerun()

    # ---------------------------------------------------
    # FINISH
    # ---------------------------------------------------

    with finish_col:

        if st.button(
            "🏁 Finish Exam",
            type="primary",
            width="stretch",
        ):

            st.session_state[
                "confirm_finish"
            ] = True

            st.rerun()

    # ===================================================
    # FINISH CONFIRMATION
    # ===================================================

    if st.session_state[
        "confirm_finish"
    ]:

        unanswered = (
            len(questions)
            -
            answered_count
        )

        if unanswered:

            st.warning(
                f"You still have "
                f"{unanswered} "
                f"unanswered question(s)."
            )

        st.write(
            "**Are you sure you want "
            "to finish the exam?**"
        )

        confirm_col, cancel_col = (
            st.columns(2)
        )

        # ------------------------------------------------
        # YES FINISH
        # ------------------------------------------------

        with confirm_col:

            if st.button(
                "Yes, Finish",
                type="primary",
                width="stretch",
            ):

                finish_exam()

                st.stop()

        # ------------------------------------------------
        # CONTINUE EXAM
        # ------------------------------------------------

        with cancel_col:

            if st.button(
                "Continue Exam",
                width="stretch",
            ):

                st.session_state[
                    "confirm_finish"
                ] = False

                st.rerun()