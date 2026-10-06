import os
from pathlib import Path

import streamlit as st
from streamlit_quill import st_quill

from utils.storage import *

st.set_page_config(page_title="Question Editor", page_icon="✏️", layout="wide")
st.title("✏️ Question Editor")
init_db()

papers = get_papers()
if not papers:
    st.warning("No papers available.")
    st.info("Create a paper first from Admin.")
    st.stop()

paper_lookup = {p["name"]: p for p in papers}
selected_paper = st.selectbox("Paper", list(paper_lookup.keys()), key="question_paper")
paper = paper_lookup[selected_paper]
paper_id = paper["id"]

passage_rows = get_passages(paper_id)
passage_lookup = {"No Passage": None}
for passage in passage_rows:
    passage_lookup[passage["title"]] = passage["id"]

st.session_state.setdefault("editor_version", 0)
st.session_state.setdefault("question_edit_id", None)
edit_id = st.session_state.question_edit_id
edit_row = get_question(edit_id) if edit_id is not None else None
edit_options = get_options(edit_id) if edit_row else []

if edit_id is not None and edit_row is None:
    st.session_state.question_edit_id = None
    edit_id = None

next_question = next_question_number(paper_id)

if edit_row:
    question_number = int(edit_row["question_number"])
    default_html = edit_row["question_html"] or ""
    default_image = edit_row["question_image"]
    default_type = "Single Choice" if edit_row["question_type"] == "single" else "Multiple Choice"
    default_passage_id = edit_row["passage_id"]
    option_count_default = max(2, len(edit_options))
    option_defaults = {o["option_letter"]: o["option_text"] or "" for o in edit_options}
    correct_defaults = {o["option_letter"] for o in edit_options if o["is_correct"]}
    st.header(f"✏️ Edit Question {question_number}")
else:
    question_number = int(next_question)
    default_html = ""
    default_image = None
    default_type = "Single Choice"
    default_passage_id = None
    option_count_default = 4
    option_defaults = {}
    correct_defaults = set()

passage_names = list(passage_lookup.keys())
default_passage_name = "No Passage"
for name, pid in passage_lookup.items():
    if pid == default_passage_id:
        default_passage_name = name
        break

selected_passage = st.selectbox(
    "Passage",
    passage_names,
    index=passage_names.index(default_passage_name),
    key=f"passage_select_{edit_id or 'new'}_{st.session_state.editor_version}",
)
passage_id = passage_lookup[selected_passage]

st.info(f"Paper: {selected_paper}")
st.metric("Question Number", question_number)

version = st.session_state.editor_version
form_key = f"question_form_{edit_id or 'new'}_{version}"

with st.form(form_key):
    st.subheader("Question")
    question_html = st_quill(
        value=default_html,
        html=True,
        placeholder="Paste question from Word...",
        key=f"question_editor_{edit_id or 'new'}_{version}",
    )

    st.divider()
    st.subheader("Question Image")
    current_image = displayable_file(default_image)
    if current_image:
        st.caption("Current image")
        st.image(current_image, width=450)

    question_image = st.file_uploader(
        "Replace / upload image",
        type=["png", "jpg", "jpeg"],
        key=f"question_image_{edit_id or 'new'}_{version}",
    )

    remove_image = st.checkbox("Remove current image", value=False) if edit_row and default_image else False

    st.divider()
    type_options = ["Single Choice", "Multiple Choice"]
    question_type = st.radio(
        "Question Type",
        type_options,
        index=type_options.index(default_type),
        horizontal=True,
        key=f"question_type_{edit_id or 'new'}_{version}",
    )

    st.divider()
    st.subheader("Answer Options")
    st.caption("Dynamic options are supported. For True/False use A = True and B = False.")

    option_count = st.number_input(
        "Number of Options",
        min_value=2,
        max_value=12,
        value=option_count_default,
        step=1,
        key=f"option_count_{edit_id or 'new'}_{version}",
    )

    letters = [chr(65 + i) for i in range(int(option_count))]
    option_values = {}
    correct_answers = []

    if question_type == "Single Choice":
        for letter in letters:
            c1, c2 = st.columns([1, 12])
            with c1:
                st.markdown(f"### {letter}")
            with c2:
                option_values[letter] = st.text_area(
                    f"Option {letter}",
                    value=option_defaults.get(letter, ""),
                    key=f"option_{letter}_{edit_id or 'new'}_{version}",
                    label_visibility="collapsed",
                    height=80,
                )

        default_correct = next(iter(correct_defaults), None)
        default_index = letters.index(default_correct) if default_correct in letters else None
        correct_single = st.radio(
            "Correct Answer",
            letters,
            index=default_index,
            horizontal=True,
            key=f"correct_single_{edit_id or 'new'}_{version}",
        )
        if correct_single:
            correct_answers = [correct_single]
    else:
        for letter in letters:
            c1, c2, c3 = st.columns([1, 10, 2])
            with c1:
                st.markdown(f"### {letter}")
            with c2:
                option_values[letter] = st.text_area(
                    f"Option {letter}",
                    value=option_defaults.get(letter, ""),
                    key=f"option_{letter}_{edit_id or 'new'}_{version}",
                    label_visibility="collapsed",
                    height=80,
                )
            with c3:
                checked = st.checkbox(
                    "Correct",
                    value=(letter in correct_defaults),
                    key=f"correct_{letter}_{edit_id or 'new'}_{version}",
                )
                if checked:
                    correct_answers.append(letter)

    st.divider()
    st.subheader("Option Preview")
    valid_preview = {k: v for k, v in option_values.items() if v and v.strip()}
    if valid_preview:
        for letter, text in valid_preview.items():
            if letter in correct_answers:
                st.markdown(f"**{letter}. {text}** ✓")
            else:
                st.markdown(f"{letter}. {text}")
    else:
        st.caption("Enter the answer options above.")

    st.divider()
    if edit_row:
        c1, c2 = st.columns(2)
        with c1:
            save = st.form_submit_button("💾 Update Question", type="primary", width="stretch")
        with c2:
            cancel = st.form_submit_button("Cancel", width="stretch")
        save_new = False
    else:
        c1, c2 = st.columns(2)
        with c1:
            save = st.form_submit_button("💾 Save", width="stretch")
        with c2:
            save_new = st.form_submit_button("💾 Save & New Question", width="stretch")
        cancel = False

if cancel:
    st.session_state.question_edit_id = None
    st.session_state.editor_version += 1
    st.rerun()

if save or save_new:
    errors = []

    if not question_html or not question_html.strip() or question_html.strip() in ("<p><br></p>", "<p></p>"):
        errors.append("Question text is required.")

    valid_options = {k: v.strip() for k, v in option_values.items() if v and v.strip()}

    if len(valid_options) < 2:
        errors.append("At least two answer options are required.")
    if not correct_answers:
        errors.append("Select at least one correct answer.")
    if question_type == "Single Choice" and len(correct_answers) != 1:
        errors.append("Single Choice must have exactly one correct answer.")
    for letter in correct_answers:
        if letter not in valid_options:
            errors.append(f"Correct option {letter} does not contain any text.")

    if errors:
        st.error("Please fix the following before saving:")
        for error in errors:
            st.write(f"• {error}")
    else:
        try:
            saved_image = default_image

            if remove_image and default_image:
                if is_remote_file(default_image):
                    delete_storage_file_by_url(default_image)
                else:
                    old = Path(default_image)
                    if old.exists():
                        try:
                            old.unlink()
                        except Exception:
                            pass
                saved_image = None

            if question_image is not None:
                if default_image and is_remote_file(default_image):
                    delete_storage_file_by_url(default_image)

                extension = os.path.splitext(question_image.name)[1].lower() or ".png"
                object_path = f"papers/{paper_id}/questions/q{question_number}{extension}"
                saved_image = upload_file_bytes(
                    object_path,
                    question_image.getvalue(),
                    question_image.type or None,
                )

            db_type = "single" if question_type == "Single Choice" else "multiple"

            if edit_row:
                update_question(edit_id, passage_id, question_html, saved_image, db_type)
                target_id = edit_id
            else:
                created = add_question(
                    paper_id,
                    passage_id,
                    question_number,
                    question_html,
                    saved_image,
                    db_type,
                )
                target_id = created["id"]

            option_payload = []
            for letter, text in valid_options.items():
                option_payload.append(
                    {
                        "question_id": target_id,
                        "option_letter": letter,
                        "option_text": text,
                        "is_correct": letter in correct_answers,
                    }
                )

            replace_options(target_id, option_payload)
            st.success(f"Question {question_number} {'updated' if edit_row else 'saved'} successfully.")

            if edit_row or save_new:
                st.session_state.question_edit_id = None
                st.session_state.editor_version += 1
                st.rerun()

        except Exception as e:
            st.error("Unable to save the question.")
            st.exception(e)

st.divider()
st.header("📚 Existing Questions")
questions = get_questions(paper_id)

if not questions:
    st.info("No questions have been added to this paper yet.")
else:
    for question in questions:
        question_id = question["id"]
        passage_title = question["passage_title"] or "No Passage"
        question_type_display = "Single Choice" if question["question_type"] == "single" else "Multiple Choice"

        with st.expander(
            f"Question {question['question_number']} — {passage_title} — {question_type_display}"
        ):
            if question["question_html"]:
                st.markdown(question["question_html"], unsafe_allow_html=True)

            question_image_url = displayable_file(question["question_image"])
            if question_image_url:
                st.image(question_image_url, width=450)

            options = get_options(question_id)
            st.markdown("#### Options")
            for option in options:
                if option["is_correct"]:
                    st.markdown(f"**{option['option_letter']}. {option['option_text']}** ✓")
                else:
                    st.markdown(f"{option['option_letter']}. {option['option_text']}")

            c1, c2 = st.columns(2)
            with c1:
                if st.button(
                    "✏️ Edit Question",
                    key=f"edit_question_{question_id}",
                    width="stretch",
                ):
                    st.session_state.question_edit_id = question_id
                    st.session_state.editor_version += 1
                    st.rerun()

            with c2:
                confirm_key = f"confirm_delete_{question_id}"
                if not st.session_state.get(confirm_key, False):
                    if st.button(
                        "🗑️ Delete Question",
                        key=f"delete_question_{question_id}",
                        width="stretch",
                    ):
                        st.session_state[confirm_key] = True
                        st.rerun()
                else:
                    st.warning(f"Delete Question {question['question_number']}?")
                    yes_col, no_col = st.columns(2)

                    with yes_col:
                        if st.button(
                            "Yes, Delete",
                            key=f"yes_delete_{question_id}",
                            type="primary",
                            width="stretch",
                        ):
                            try:
                                if question["question_image"]:
                                    if is_remote_file(question["question_image"]):
                                        delete_storage_file_by_url(question["question_image"])
                                    else:
                                        legacy = Path(question["question_image"])
                                        if legacy.exists():
                                            try:
                                                legacy.unlink()
                                            except Exception:
                                                pass
                                delete_question(question_id)
                                st.session_state.pop(confirm_key, None)
                                st.rerun()
                            except Exception as e:
                                st.error("Unable to delete the question.")
                                st.exception(e)

                    with no_col:
                        if st.button(
                            "Cancel",
                            key=f"cancel_delete_{question_id}",
                            width="stretch",
                        ):
                            st.session_state.pop(confirm_key, None)
                            st.rerun()
