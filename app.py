import streamlit as st


# =======================================================
# PAGE DEFINITIONS
# =======================================================

exam_page = st.Page(
    "pages/Exam.py",
    title="Exam",
    icon="📝",
    default=True
)

results_page = st.Page(
    "pages/Results.py",
    title="Results",
    icon="🏆"
)

admin_page = st.Page(
    "pages/Admin.py",
    title="Admin",
    icon="⚙️"
)

passages_page = st.Page(
    "pages/Passages.py",
    title="Passages",
    icon="📖"
)

question_editor_page = st.Page(
    "pages/Question_Editor.py",
    title="Question Editor",
    icon="✏️"
)


# =======================================================
# NAVIGATION
# =======================================================

pages = {
    "Practice": [
        exam_page,
        results_page,
    ],
    "Admin": [
        admin_page,
        passages_page,
        question_editor_page,
    ],
}


# =======================================================
# FINISHED EXAM -> RESULTS
# =======================================================

if st.session_state.get(
    "go_to_results",
    False
):

    st.session_state[
        "go_to_results"
    ] = False

    st.switch_page(
        results_page
    )

    st.stop()


# =======================================================
# RUN NAVIGATION
# =======================================================

navigation = st.navigation(
    pages
)

navigation.run()