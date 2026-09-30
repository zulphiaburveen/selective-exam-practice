import re
import shutil
from pathlib import Path

import streamlit as st

from utils.storage import *


# -------------------------------------------------------
# PAGE
# -------------------------------------------------------

st.set_page_config(
    page_title="Admin",
    page_icon="⚙️",
    layout="wide"
)

st.title("⚙️ Admin")

init_db()


# -------------------------------------------------------
# FOLDERS
# -------------------------------------------------------

PAPERS_FOLDER = Path("papers")

PAPERS_FOLDER.mkdir(
    parents=True,
    exist_ok=True
)


# -------------------------------------------------------
# DATABASE
# -------------------------------------------------------

conn = get_connection()
cur = conn.cursor()


# -------------------------------------------------------
# CREATE SAFE FOLDER NAME
# -------------------------------------------------------

def create_folder_name(name, year):

    base = f"{name}{year}"

    return re.sub(
        r"[^A-Za-z0-9_-]",
        "",
        base
    )


# =======================================================
# CREATE PAPER
# =======================================================

st.header("📄 Add New Paper")

st.caption(
    "Create a paper for manual entry, or optionally upload "
    "the original PDF/DOCX for AI import later."
)


with st.form(
    "create_paper_form",
    clear_on_submit=True
):

    paper_name = st.text_input(
        "Paper Name",
        placeholder="e.g. ICAS English 2022"
    )

    col1, col2 = st.columns(2)

    with col1:

        subject = st.selectbox(
            "Subject",
            [
                "English",
                "Mathematics",
                "Science",
                "Other"
            ]
        )

    with col2:

        year = st.number_input(
            "Year",
            min_value=2000,
            max_value=2100,
            value=2022,
            step=1
        )

    # ---------------------------------------------------
    # OPTIONAL SOURCE FILE
    # ---------------------------------------------------

    uploaded_file = st.file_uploader(
        "Original Paper (optional)",
        type=[
            "pdf",
            "docx"
        ],
        help=(
            "Leave this empty if you want to enter "
            "passages and questions manually."
        )
    )

    create_paper = st.form_submit_button(
        "➕ Create Paper",
        type="primary",
        use_container_width=True
    )


# =======================================================
# PROCESS CREATE PAPER
# =======================================================

if create_paper:

    errors = []

    clean_name = (
        paper_name.strip()
        if paper_name
        else ""
    )

    # ---------------------------------------------------
    # VALIDATION
    # ---------------------------------------------------

    if not clean_name:

        errors.append(
            "Paper name is required."
        )

    # ---------------------------------------------------
    # SHOW VALIDATION ERRORS
    # ---------------------------------------------------

    if errors:

        for error in errors:

            st.error(error)

    else:

        folder_name = create_folder_name(
            clean_name,
            int(year)
        )

        # ------------------------------------------------
        # CHECK DUPLICATE
        # ------------------------------------------------

        cur.execute(
            """
            SELECT id
            FROM papers
            WHERE name = ?
            """,
            (clean_name,)
        )

        existing = cur.fetchone()

        if existing:

            st.error(
                "A paper with this name already exists."
            )

        else:

            paper_path = (
                PAPERS_FOLDER /
                folder_name
            )

            passages_path = (
                paper_path /
                "passages"
            )

            questions_path = (
                paper_path /
                "questions"
            )

            try:

                # ----------------------------------------
                # CREATE FOLDERS
                # ----------------------------------------

                passages_path.mkdir(
                    parents=True,
                    exist_ok=True
                )

                questions_path.mkdir(
                    parents=True,
                    exist_ok=True
                )

                # ----------------------------------------
                # OPTIONAL ORIGINAL FILE
                # ----------------------------------------

                original_filename = None

                if uploaded_file is not None:

                    extension = Path(
                        uploaded_file.name
                    ).suffix.lower()

                    original_filename = (
                        f"original{extension}"
                    )

                    original_path = (
                        paper_path /
                        original_filename
                    )

                    with open(
                        original_path,
                        "wb"
                    ) as file:

                        file.write(
                            uploaded_file.getbuffer()
                        )

                # ----------------------------------------
                # INSERT PAPER AS DRAFT
                # ----------------------------------------

                cur.execute(
                    """
                    INSERT INTO papers
                    (
                        name,
                        folder,
                        subject,
                        year,
                        filename,
                        published
                    )
                    VALUES
                    (
                        ?, ?, ?, ?, ?, 0
                    )
                    """,
                    (
                        clean_name,
                        folder_name,
                        subject,
                        int(year),
                        original_filename
                    )
                )

                conn.commit()

                st.success(
                    f"{clean_name} created successfully."
                )

                st.rerun()

            except Exception as e:

                conn.rollback()

                # ----------------------------------------
                # REMOVE PARTIALLY CREATED FOLDER
                # ----------------------------------------

                if paper_path.exists():

                    try:

                        shutil.rmtree(
                            paper_path
                        )

                    except Exception:

                        pass

                st.error(
                    "Unable to create paper."
                )

                st.exception(e)


# =======================================================
# PAPER LIBRARY
# =======================================================

st.divider()

st.header("📚 Paper Library")


cur.execute(
    """
    SELECT
        id,
        name,
        folder,
        subject,
        year,
        filename,
        published

    FROM papers

    ORDER BY
        published DESC,
        year DESC,
        name
    """
)

papers = cur.fetchall()


# -------------------------------------------------------
# NO PAPERS
# -------------------------------------------------------

if not papers:

    st.info(
        "No papers have been created yet."
    )

else:

    st.caption(
        f"{len(papers)} paper(s) available."
    )

    # ===================================================
    # DISPLAY EACH PAPER
    # ===================================================

    for paper in papers:

        paper_id = paper["id"]

        published = bool(
            paper["published"]
        )

        status = (
            "🟢 Current Paper"
            if published
            else
            "⚪ Draft"
        )

        # -----------------------------------------------
        # COUNTS
        # -----------------------------------------------

        cur.execute(
            """
            SELECT COUNT(*)
            FROM passages
            WHERE paper_id = ?
            """,
            (paper_id,)
        )

        passage_count = (
            cur.fetchone()[0]
        )


        cur.execute(
            """
            SELECT COUNT(*)
            FROM questions
            WHERE paper_id = ?
            """,
            (paper_id,)
        )

        question_count = (
            cur.fetchone()[0]
        )


        # ===============================================
        # PAPER EXPANDER
        # ===============================================

        with st.expander(
            f"{paper['name']} — "
            f"{paper['year']} — "
            f"{status}"
        ):

            # -------------------------------------------
            # PAPER DETAILS
            # -------------------------------------------

            col1, col2, col3 = (
                st.columns(3)
            )

            with col1:

                st.write(
                    f"**Subject:** "
                    f"{paper['subject']}"
                )

            with col2:

                st.write(
                    f"**Year:** "
                    f"{paper['year']}"
                )

            with col3:

                if published:

                    st.success(
                        "🟢 Current Paper"
                    )

                else:

                    st.write(
                        "**Status:** Draft"
                    )

            # -------------------------------------------
            # SOURCE
            # -------------------------------------------

            st.write(
                f"**Folder:** "
                f"`papers/{paper['folder']}`"
            )

            if paper["filename"]:

                st.write(
                    f"**Original:** "
                    f"{paper['filename']}"
                )

            else:

                st.write(
                    "**Original:** "
                    "Manual entry — no source file"
                )

            # -------------------------------------------
            # METRICS
            # -------------------------------------------

            metric1, metric2 = (
                st.columns(2)
            )

            with metric1:

                st.metric(
                    "Passages",
                    passage_count
                )

            with metric2:

                st.metric(
                    "Questions",
                    question_count
                )


            # ===========================================
            # CURRENT PUBLISHED PAPER
            # ===========================================

            st.divider()

            if published:

                st.success(
                    "This is the current exam paper."
                )

                st.caption(
                    "Publish another paper to replace "
                    "this as the current exam."
                )

            # ===========================================
            # PUBLISH DRAFT
            # ===========================================

            else:

                if question_count == 0:

                    st.button(
                        "🚀 Publish as Current Paper",
                        key=f"publish_disabled_{paper_id}",
                        disabled=True,
                        use_container_width=True
                    )

                    st.caption(
                        "Add at least one question "
                        "before publishing."
                    )

                else:

                    if st.button(
                        "🚀 Publish as Current Paper",
                        key=f"publish_{paper_id}",
                        type="primary",
                        use_container_width=True
                    ):

                        try:

                            # --------------------------------
                            # UNPUBLISH ALL PAPERS
                            # --------------------------------

                            cur.execute(
                                """
                                UPDATE papers
                                SET published = 0
                                """
                            )

                            # --------------------------------
                            # PUBLISH SELECTED PAPER
                            # --------------------------------

                            cur.execute(
                                """
                                UPDATE papers
                                SET published = 1
                                WHERE id = ?
                                """,
                                (paper_id,)
                            )

                            conn.commit()

                            st.success(
                                f"{paper['name']} is now "
                                "the current exam paper."
                            )

                            st.rerun()

                        except Exception as e:

                            conn.rollback()

                            st.error(
                                "Unable to publish paper."
                            )

                            st.exception(e)


            # ===========================================
            # DELETE PAPER
            # ===========================================

            st.divider()

            st.markdown(
                "#### Danger Zone"
            )

            # -------------------------------------------
            # CURRENT PAPER CANNOT BE DELETED
            # -------------------------------------------

            if published:

                st.button(
                    "🗑️ Delete Paper",
                    key=f"delete_published_{paper_id}",
                    disabled=True,
                    use_container_width=True
                )

                st.caption(
                    "The current published paper cannot "
                    "be deleted. Publish another paper "
                    "first."
                )

            # -------------------------------------------
            # DRAFT CAN BE DELETED
            # -------------------------------------------

            else:

                confirm_key = (
                    f"confirm_delete_paper_"
                    f"{paper_id}"
                )

                if not st.session_state.get(
                    confirm_key,
                    False
                ):

                    if st.button(
                        "🗑️ Delete Paper",
                        key=f"delete_paper_{paper_id}",
                        use_container_width=True
                    ):

                        st.session_state[
                            confirm_key
                        ] = True

                        st.rerun()

                # =======================================
                # DELETE CONFIRMATION
                # =======================================

                else:

                    st.error(
                        f"Permanently delete "
                        f"'{paper['name']}'?"
                    )

                    st.warning(
                        "This will delete the paper, "
                        "passages, questions, answer "
                        "options, attempts and files."
                    )

                    confirm_col, cancel_col = (
                        st.columns(2)
                    )

                    # -----------------------------------
                    # CONFIRM DELETE
                    # -----------------------------------

                    with confirm_col:

                        if st.button(
                            "Yes, Delete Permanently",
                            key=f"yes_delete_{paper_id}",
                            type="primary",
                            use_container_width=True
                        ):

                            try:

                                # -----------------------
                                # GET QUESTION IDS
                                # -----------------------

                                cur.execute(
                                    """
                                    SELECT id
                                    FROM questions
                                    WHERE paper_id = ?
                                    """,
                                    (paper_id,)
                                )

                                question_rows = (
                                    cur.fetchall()
                                )

                                question_ids = [
                                    row["id"]
                                    for row
                                    in question_rows
                                ]

                                # -----------------------
                                # DELETE OPTIONS
                                # -----------------------

                                for question_id in question_ids:

                                    cur.execute(
                                        """
                                        DELETE FROM options
                                        WHERE question_id = ?
                                        """,
                                        (question_id,)
                                    )

                                # -----------------------
                                # DELETE QUESTIONS
                                # -----------------------

                                cur.execute(
                                    """
                                    DELETE FROM questions
                                    WHERE paper_id = ?
                                    """,
                                    (paper_id,)
                                )

                                # -----------------------
                                # DELETE PASSAGES
                                # -----------------------

                                cur.execute(
                                    """
                                    DELETE FROM passages
                                    WHERE paper_id = ?
                                    """,
                                    (paper_id,)
                                )

                                # -----------------------
                                # DELETE ATTEMPTS
                                # -----------------------

                                cur.execute(
                                    """
                                    DELETE FROM attempts
                                    WHERE paper_id = ?
                                    """,
                                    (paper_id,)
                                )

                                # -----------------------
                                # DELETE PAPER
                                # -----------------------

                                cur.execute(
                                    """
                                    DELETE FROM papers
                                    WHERE id = ?
                                    """,
                                    (paper_id,)
                                )

                                conn.commit()

                                # -----------------------
                                # DELETE FOLDER
                                # -----------------------

                                paper_path = (
                                    PAPERS_FOLDER /
                                    paper["folder"]
                                )

                                if paper_path.exists():

                                    try:

                                        shutil.rmtree(
                                            paper_path
                                        )

                                    except Exception as folder_error:

                                        st.warning(
                                            "The database records "
                                            "were deleted, but the "
                                            "paper folder could not "
                                            "be removed."
                                        )

                                        st.write(
                                            folder_error
                                        )

                                # -----------------------
                                # CLEAR CONFIRMATION
                                # -----------------------

                                if (
                                    confirm_key
                                    in
                                    st.session_state
                                ):

                                    del st.session_state[
                                        confirm_key
                                    ]

                                st.success(
                                    f"{paper['name']} "
                                    "deleted successfully."
                                )

                                st.rerun()

                            except Exception as e:

                                conn.rollback()

                                st.error(
                                    "Unable to delete paper."
                                )

                                st.exception(e)

                    # -----------------------------------
                    # CANCEL DELETE
                    # -----------------------------------

                    with cancel_col:

                        if st.button(
                            "Cancel",
                            key=f"cancel_delete_{paper_id}",
                            use_container_width=True
                        ):

                            if (
                                confirm_key
                                in
                                st.session_state
                            ):

                                del st.session_state[
                                    confirm_key
                                ]

                            st.rerun()


# -------------------------------------------------------
# CLOSE DATABASE
# -------------------------------------------------------

conn.close()