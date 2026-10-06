import re
from pathlib import Path

import streamlit as st

from utils.storage import *

st.set_page_config(page_title="Admin", page_icon="⚙️", layout="wide")
st.title("⚙️ Admin")
init_db()

PAPERS_FOLDER = Path("papers")
PAPERS_FOLDER.mkdir(parents=True, exist_ok=True)


def create_folder_name(name, year):
    return re.sub(r"[^A-Za-z0-9_-]", "", f"{name}{year}")


st.header("📄 Add New Paper")
st.caption(
    "Create a paper for manual entry, or optionally upload "
    "the original PDF/DOCX for AI import later."
)

with st.form("create_paper_form", clear_on_submit=True):
    paper_name = st.text_input("Paper Name", placeholder="e.g. ICAS English 2022")
    c1, c2 = st.columns(2)
    with c1:
        subject = st.selectbox("Subject", ["English", "Mathematics", "Science", "Other"])
    with c2:
        year = st.number_input("Year", min_value=2000, max_value=2100, value=2022, step=1)

    uploaded_file = st.file_uploader(
        "Original Paper (optional)",
        type=["pdf", "docx"],
        help="Leave this empty if you want to enter passages and questions manually.",
    )

    create_paper = st.form_submit_button(
        "➕ Create Paper", type="primary", width="stretch"
    )

if create_paper:
    clean_name = (paper_name or "").strip()

    if not clean_name:
        st.error("Paper name is required.")
    elif paper_name_exists(clean_name):
        st.error("A paper with this name already exists.")
    else:
        folder_name = create_folder_name(clean_name, int(year))

        try:
            # Create the database row first so Storage can use the permanent paper ID.
            created = add_paper(clean_name, folder_name, subject, int(year), None)

            if uploaded_file is not None:
                extension = Path(uploaded_file.name).suffix.lower()
                object_path = f"papers/{created['id']}/original/original{extension}"
                file_url = upload_file_bytes(
                    object_path,
                    uploaded_file.getvalue(),
                    uploaded_file.type or None,
                )

                get_supabase().table("papers").update(
                    {"filename": file_url}
                ).eq("id", created["id"]).execute()
                clear_data_cache()

            st.success(f"{clean_name} created successfully.")
            st.rerun()

        except Exception as e:
            # If creation partially succeeded, remove the database row and Storage files.
            try:
                if "created" in locals() and created:
                    delete_storage_folder(f"papers/{created['id']}")
                    delete_paper(created["id"])
            except Exception:
                pass
            st.error("Unable to create paper.")
            st.exception(e)


st.divider()
st.header("📚 Paper Library")
papers = get_papers()

if not papers:
    st.info("No papers have been created yet.")
else:
    st.caption(f"{len(papers)} paper(s) available.")

    for paper in papers:
        paper_id = paper["id"]
        published = bool(paper["published"])
        status = "🟢 Current Paper" if published else "⚪ Draft"
        passage_count, question_count = paper_counts(paper_id)

        with st.expander(f"{paper['name']} — {paper['year']} — {status}"):
            c1, c2, c3 = st.columns(3)
            with c1:
                st.write(f"**Subject:** {paper['subject']}")
            with c2:
                st.write(f"**Year:** {paper['year']}")
            with c3:
                if published:
                    st.success("🟢 Current Paper")
                else:
                    st.write("**Status:** Draft")

            st.write(f"**Folder:** `papers/{paper['folder']}`")
            if paper.get("filename"):
                st.write("**Original source:** stored in Supabase Storage")
            else:
                st.write("**Original:** Manual entry — no source file")

            m1, m2 = st.columns(2)
            with m1:
                st.metric("Passages", passage_count)
            with m2:
                st.metric("Questions", question_count)

            st.divider()

            if published:
                st.success("This is the current exam paper.")
                st.caption("Publish another paper to replace this as the current exam.")
            elif question_count == 0:
                st.button(
                    "🚀 Publish as Current Paper",
                    key=f"publish_disabled_{paper_id}",
                    disabled=True,
                    width="stretch",
                )
                st.caption("Add at least one question before publishing.")
            else:
                if st.button(
                    "🚀 Publish as Current Paper",
                    key=f"publish_{paper_id}",
                    type="primary",
                    width="stretch",
                ):
                    publish_paper(paper_id)
                    st.rerun()

            st.divider()
            st.markdown("#### Danger Zone")

            if published:
                st.button(
                    "🗑️ Delete Paper",
                    key=f"delete_published_{paper_id}",
                    disabled=True,
                    width="stretch",
                )
                st.caption(
                    "The current published paper cannot be deleted. Publish another paper first."
                )
            else:
                confirm_key = f"confirm_delete_paper_{paper_id}"

                if not st.session_state.get(confirm_key, False):
                    if st.button(
                        "🗑️ Delete Paper",
                        key=f"delete_paper_{paper_id}",
                        width="stretch",
                    ):
                        st.session_state[confirm_key] = True
                        st.rerun()
                else:
                    st.error(f"Permanently delete '{paper['name']}'?")
                    st.warning("This deletes the paper and all related database records.")
                    yes_col, no_col = st.columns(2)

                    with yes_col:
                        if st.button(
                            "Yes, Delete Permanently",
                            key=f"yes_delete_{paper_id}",
                            type="primary",
                            width="stretch",
                        ):
                            try:
                                delete_storage_folder(f"papers/{paper_id}")
                                delete_paper(paper_id)
                                st.session_state.pop(confirm_key, None)
                                st.rerun()
                            except Exception as e:
                                st.error("Unable to delete paper.")
                                st.exception(e)

                    with no_col:
                        if st.button(
                            "Cancel",
                            key=f"cancel_delete_{paper_id}",
                            width="stretch",
                        ):
                            st.session_state.pop(confirm_key, None)
                            st.rerun()
