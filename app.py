import streamlit as st

pages = {
    "Practice": [
        st.Page(
            "pages/Exam.py",
            title="Exam",
            icon="📝",
            default=True
        ),
        st.Page(
            "pages/Results.py",
            title="Results",
            icon="🏆"
        ),
    ],
    "Admin": [
        st.Page(
            "pages/Admin.py",
            title="Admin",
            icon="⚙️"
        ),
        st.Page(
            "pages/Passages.py",
            title="Passages",
            icon="📖"
        ),
        st.Page(
            "pages/Question_Editor.py",
            title="Question Editor",
            icon="✏️"
        ),
    ],
}

navigation = st.navigation(pages)

navigation.run()