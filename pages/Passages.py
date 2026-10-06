import os
from pathlib import Path

import streamlit as st
from streamlit_quill import st_quill

from utils.storage import *

st.set_page_config(page_title="Passages", page_icon="📖", layout="wide")
st.title("📖 Passage Editor")
init_db()

papers = get_papers()
if not papers:
    st.warning("No papers available.")
    st.info("Create a paper first from Admin.")
    st.stop()

paper_lookup = {f"{p['name']} ({p['year']})": p for p in papers}
selected_name = st.selectbox("Paper", list(paper_lookup.keys()), key="passage_paper")
paper = paper_lookup[selected_name]
paper_id = paper["id"]
paper_folder = paper["folder"]
st.info(f"Paper: {paper['name']} • {paper['subject']} • {paper['year']}")

st.session_state.setdefault("passage_edit_id", None)
st.session_state.setdefault("passage_editor_version", 0)
edit_id = st.session_state.passage_edit_id
edit_row = get_passage(edit_id) if edit_id is not None else None

if edit_id is not None and edit_row is None:
    st.session_state.passage_edit_id = None
    edit_id = None

next_order = next_passage_order(paper_id)

if edit_row:
    default_title = edit_row["title"] or ""
    default_content = edit_row["content"] or ""
    default_order = int(edit_row["display_order"])
    existing_image = edit_row["image"]
    st.header(f"✏️ Edit {default_title}")
else:
    default_title = f"Passage {next_order}"
    default_content = ""
    default_order = int(next_order)
    existing_image = None
    st.header("➕ Add Passage")

version = st.session_state.passage_editor_version
form_key = f"passage_form_{edit_id or 'new'}_{version}"

with st.form(form_key):
    passage_title = st.text_input("Passage Title", value=default_title)
    st.markdown("### Passage Content")
    passage_content = st_quill(
        value=default_content,
        html=True,
        placeholder="Paste the passage from Word or type it here...",
        key=f"passage_content_{edit_id or 'new'}_{version}",
    )

    st.markdown("### Passage Image")
    current_image = displayable_file(existing_image)
    if current_image:
        st.caption("Current image")
        st.image(current_image, width=600)

    passage_image = st.file_uploader(
        "Replace / upload passage image (optional)",
        type=["png", "jpg", "jpeg"],
        key=f"passage_image_{edit_id or 'new'}_{version}",
    )

    remove_image = False
    if edit_row and existing_image:
        remove_image = st.checkbox("Remove current image")

    display_order = st.number_input(
        "Display Order", min_value=1, value=default_order, step=1
    )

    if edit_row:
        c1, c2 = st.columns(2)
        with c1:
            save = st.form_submit_button(
                "💾 Update Passage", type="primary", width="stretch"
            )
        with c2:
            cancel = st.form_submit_button("Cancel", width="stretch")
        save_new = False
    else:
        c1, c2 = st.columns(2)
        with c1:
            save = st.form_submit_button("💾 Save", width="stretch")
        with c2:
            save_new = st.form_submit_button(
                "💾 Save & New Passage", width="stretch"
            )
        cancel = False

if cancel:
    st.session_state.passage_edit_id = None
    st.session_state.passage_editor_version += 1
    st.rerun()

if save or save_new:
    errors = []
    clean_title = (passage_title or "").strip()

    if not clean_title:
        errors.append("Passage title is required.")

    has_content = bool(
        passage_content
        and passage_content.strip()
        and passage_content.strip() not in ("<p><br></p>", "<p></p>")
    )
    has_existing_image = bool(existing_image and not remove_image)

    if not has_content and passage_image is None and not has_existing_image:
        errors.append("Add passage text or a passage image.")

    if passage_order_exists(
        paper_id,
        int(display_order),
        exclude_id=edit_id if edit_row else None,
    ):
        errors.append(f"Display order {display_order} already exists for this paper.")

    if errors:
        st.error("Please fix the following:")
        for error in errors:
            st.write(f"• {error}")
    else:
        try:
            saved_image = existing_image

            if remove_image and existing_image:
                if is_remote_file(existing_image):
                    delete_storage_file_by_url(existing_image)
                else:
                    old = Path(existing_image)
                    if old.exists():
                        try:
                            old.unlink()
                        except Exception:
                            pass
                saved_image = None

            if passage_image is not None:
                if existing_image and is_remote_file(existing_image):
                    delete_storage_file_by_url(existing_image)

                extension = os.path.splitext(passage_image.name)[1].lower() or ".png"
                # Use edit ID when available; display order gives a stable name for new passages.
                stem = f"passage_{edit_id}" if edit_id else f"passage_{int(display_order)}"
                object_path = f"papers/{paper_id}/passages/{stem}{extension}"
                saved_image = upload_file_bytes(
                    object_path,
                    passage_image.getvalue(),
                    passage_image.type or None,
                )

            if edit_row:
                update_passage(
                    edit_id,
                    clean_title,
                    passage_content,
                    saved_image,
                    int(display_order),
                )
                message = f"{clean_title} updated successfully."
            else:
                add_passage(
                    paper_id,
                    clean_title,
                    passage_content,
                    saved_image,
                    int(display_order),
                )
                message = f"{clean_title} saved successfully."

            st.success(message)

            if edit_row or save_new:
                st.session_state.passage_edit_id = None
                st.session_state.passage_editor_version += 1
                st.rerun()

        except Exception as e:
            st.error("Unable to save passage.")
            st.exception(e)

st.divider()
st.header("📚 Existing Passages")
existing_passages = get_passages(paper_id)

if not existing_passages:
    st.info("No passages have been added to this paper yet.")
else:
    for passage in existing_passages:
        passage_id = passage["id"]
        with st.expander(f"{passage['display_order']}. {passage['title']}"):
            if passage["content"]:
                st.markdown(passage["content"], unsafe_allow_html=True)

            passage_image_url = displayable_file(passage["image"])
            if passage_image_url:
                st.image(passage_image_url, width=600)

            linked = questions_for_passage(passage_id)
            if linked:
                st.write(
                    "**Questions using this passage:** "
                    + ", ".join(str(row["question_number"]) for row in linked)
                )
            else:
                st.caption("No questions are linked to this passage yet.")

            c1, c2 = st.columns(2)
            with c1:
                if st.button(
                    "✏️ Edit Passage",
                    key=f"edit_passage_{passage_id}",
                    width="stretch",
                ):
                    st.session_state.passage_edit_id = passage_id
                    st.session_state.passage_editor_version += 1
                    st.rerun()

            with c2:
                if linked:
                    st.button(
                        "🗑️ Delete Passage",
                        key=f"delete_disabled_{passage_id}",
                        disabled=True,
                        width="stretch",
                    )
                else:
                    confirm_key = f"confirm_delete_passage_{passage_id}"
                    if not st.session_state.get(confirm_key, False):
                        if st.button(
                            "🗑️ Delete Passage",
                            key=f"delete_passage_{passage_id}",
                            width="stretch",
                        ):
                            st.session_state[confirm_key] = True
                            st.rerun()
                    else:
                        st.warning(f"Delete {passage['title']}?")
                        yes_col, no_col = st.columns(2)

                        with yes_col:
                            if st.button(
                                "Yes, Delete",
                                key=f"yes_delete_passage_{passage_id}",
                                type="primary",
                                width="stretch",
                            ):
                                try:
                                    if passage["image"]:
                                        if is_remote_file(passage["image"]):
                                            delete_storage_file_by_url(passage["image"])
                                        else:
                                            legacy = Path(passage["image"])
                                            if legacy.exists():
                                                try:
                                                    legacy.unlink()
                                                except Exception:
                                                    pass
                                    delete_passage(passage_id)
                                    st.session_state.pop(confirm_key, None)
                                    st.rerun()
                                except Exception as e:
                                    st.error("Unable to delete passage.")
                                    st.exception(e)

                        with no_col:
                            if st.button(
                                "Cancel",
                                key=f"cancel_delete_passage_{passage_id}",
                                width="stretch",
                            ):
                                st.session_state.pop(confirm_key, None)
                                st.rerun()
