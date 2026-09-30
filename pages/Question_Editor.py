import os
from pathlib import Path
import streamlit as st
from streamlit_quill import st_quill
from utils.storage import *

st.set_page_config(page_title="Question Editor", page_icon="✏️", layout="wide")
st.title("✏️ Question Editor")
init_db()
conn = get_connection(); cur = conn.cursor()

# Papers
cur.execute("SELECT id,name,folder FROM papers ORDER BY name")
papers = cur.fetchall()
if not papers:
    st.warning("No papers available."); st.info("Create a paper first from Admin."); conn.close(); st.stop()
paper_lookup = {p["name"]: p for p in papers}
selected_paper = st.selectbox("Paper", list(paper_lookup.keys()), key="question_paper")
paper = paper_lookup[selected_paper]; paper_id = paper["id"]

# Passages for selected paper
cur.execute("SELECT id,title FROM passages WHERE paper_id=? ORDER BY display_order", (paper_id,))
passage_rows = cur.fetchall()
passage_lookup = {"No Passage": None}
for p in passage_rows: passage_lookup[p["title"]] = p["id"]

# State
st.session_state.setdefault("editor_version", 0)
st.session_state.setdefault("question_edit_id", None)
edit_id = st.session_state.question_edit_id
edit_row = None
edit_options = []
if edit_id is not None:
    cur.execute("SELECT * FROM questions WHERE id=? AND paper_id=?", (edit_id, paper_id))
    edit_row = cur.fetchone()
    if edit_row:
        cur.execute("SELECT option_letter,option_text,is_correct FROM options WHERE question_id=? ORDER BY option_letter", (edit_id,))
        edit_options = cur.fetchall()
    else:
        st.session_state.question_edit_id = None; edit_id = None

cur.execute("SELECT COALESCE(MAX(question_number),0)+1 FROM questions WHERE paper_id=?", (paper_id,))
next_question = cur.fetchone()[0]

# Defaults for add/edit
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
    default_html = ""; default_image = None; default_type = "Single Choice"; default_passage_id = None
    option_count_default = 4; option_defaults = {}; correct_defaults = set()

# Passage selector is part of editor so edit can reassign it
passage_names = list(passage_lookup.keys())
default_passage_name = "No Passage"
for name, pid in passage_lookup.items():
    if pid == default_passage_id: default_passage_name = name; break
selected_passage = st.selectbox("Passage", passage_names, index=passage_names.index(default_passage_name), key=f"passage_select_{edit_id or 'new'}_{st.session_state.editor_version}")
passage_id = passage_lookup[selected_passage]
st.info(f"Paper: {selected_paper}")
st.metric("Question Number", question_number)

version = st.session_state.editor_version
form_key = f"question_form_{edit_id or 'new'}_{version}"
with st.form(form_key):
    st.subheader("Question")
    question_html = st_quill(value=default_html, html=True, placeholder="Paste question from Word...", key=f"question_editor_{edit_id or 'new'}_{version}")

    st.divider(); st.subheader("Question Image")
    if default_image and Path(default_image).exists():
        st.caption("Current image"); st.image(default_image, width=450)
    question_image = st.file_uploader("Replace / upload image", type=["png","jpg","jpeg"], key=f"question_image_{edit_id or 'new'}_{version}")
    remove_image = st.checkbox("Remove current image", value=False) if edit_row and default_image else False

    st.divider()
    type_options = ["Single Choice", "Multiple Choice"]
    question_type = st.radio("Question Type", type_options, index=type_options.index(default_type), horizontal=True, key=f"question_type_{edit_id or 'new'}_{version}")

    st.divider(); st.subheader("Answer Options")
    st.caption("Dynamic options are supported. For True/False use A = True and B = False.")
    option_count = st.number_input("Number of Options", min_value=2, max_value=12, value=option_count_default, step=1, key=f"option_count_{edit_id or 'new'}_{version}")
    letters = [chr(65+i) for i in range(int(option_count))]
    option_values = {}; correct_answers = []

    if question_type == "Single Choice":
        for letter in letters:
            c1,c2 = st.columns([1,12])
            with c1: st.markdown(f"### {letter}")
            with c2:
                option_values[letter] = st.text_area(f"Option {letter}", value=option_defaults.get(letter,""), key=f"option_{letter}_{edit_id or 'new'}_{version}", label_visibility="collapsed", height=80)
        default_correct = next(iter(correct_defaults), None)
        default_index = letters.index(default_correct) if default_correct in letters else None
        correct_single = st.radio("Correct Answer", letters, index=default_index, horizontal=True, key=f"correct_single_{edit_id or 'new'}_{version}")
        if correct_single: correct_answers = [correct_single]
    else:
        # IMPORTANT: all multiple-choice option keys are versioned too.
        # The old file used fixed option_A/option_B keys here, which caused stale state.
        for letter in letters:
            c1,c2,c3 = st.columns([1,10,2])
            with c1: st.markdown(f"### {letter}")
            with c2:
                option_values[letter] = st.text_area(f"Option {letter}", value=option_defaults.get(letter,""), key=f"option_{letter}_{edit_id or 'new'}_{version}", label_visibility="collapsed", height=80)
            with c3:
                checked = st.checkbox("Correct", value=(letter in correct_defaults), key=f"correct_{letter}_{edit_id or 'new'}_{version}")
                if checked: correct_answers.append(letter)

    st.divider(); st.subheader("Option Preview")
    valid_preview = {k:v for k,v in option_values.items() if v and v.strip()}
    if valid_preview:
        for letter,text in valid_preview.items():
            st.markdown(f"**{letter}. {text}** ✓" if letter in correct_answers else f"{letter}. {text}")
    else:
        st.caption("Enter the answer options above.")

    st.divider()
    if edit_row:
        c1,c2 = st.columns(2)
        with c1: save = st.form_submit_button("💾 Update Question", type="primary", use_container_width=True)
        with c2: cancel = st.form_submit_button("Cancel", use_container_width=True)
        save_new = False
    else:
        c1,c2 = st.columns(2)
        with c1: save = st.form_submit_button("💾 Save", use_container_width=True)
        with c2: save_new = st.form_submit_button("💾 Save & New Question", use_container_width=True)
        cancel = False

if cancel:
    st.session_state.question_edit_id = None; st.session_state.editor_version += 1; st.rerun()

if save or save_new:
    errors = []
    if not question_html or not question_html.strip() or question_html.strip() in ("<p><br></p>", "<p></p>"):
        errors.append("Question text is required.")
    valid_options = {k:v.strip() for k,v in option_values.items() if v and v.strip()}
    if len(valid_options) < 2: errors.append("At least two answer options are required.")
    if not correct_answers: errors.append("Select at least one correct answer.")
    if question_type == "Single Choice" and len(correct_answers) != 1: errors.append("Single Choice must have exactly one correct answer.")
    for letter in correct_answers:
        if letter not in valid_options: errors.append(f"Correct option {letter} does not contain any text.")

    if errors:
        st.error("Please fix the following before saving:")
        for e in errors: st.write(f"• {e}")
    else:
        try:
            saved_image = default_image
            qdir = Path("papers") / paper["folder"] / "questions"; qdir.mkdir(parents=True, exist_ok=True)
            if remove_image and default_image:
                old = Path(default_image)
                if old.exists():
                    try: old.unlink()
                    except Exception: pass
                saved_image = None
            if question_image is not None:
                if default_image:
                    old = Path(default_image)
                    if old.exists():
                        try: old.unlink()
                        except Exception: pass
                ext = os.path.splitext(question_image.name)[1].lower() or ".png"
                path = qdir / f"q{question_number}{ext}"
                path.write_bytes(question_image.getbuffer())
                saved_image = str(path).replace("\\", "/")

            db_type = "single" if question_type == "Single Choice" else "multiple"
            if edit_row:
                cur.execute("UPDATE questions SET passage_id=?,question_html=?,question_image=?,question_type=? WHERE id=?", (passage_id,question_html,saved_image,db_type,edit_id))
                # Rebuild options atomically; simpler and avoids stale removed options.
                cur.execute("DELETE FROM options WHERE question_id=?", (edit_id,))
                target_id = edit_id
            else:
                cur.execute("INSERT INTO questions(paper_id,passage_id,question_number,question_html,question_image,question_type) VALUES(?,?,?,?,?,?)", (paper_id,passage_id,question_number,question_html,saved_image,db_type))
                target_id = cur.lastrowid

            for letter,text in valid_options.items():
                cur.execute("INSERT INTO options(question_id,option_letter,option_text,is_correct) VALUES(?,?,?,?)", (target_id,letter,text,1 if letter in correct_answers else 0))
            conn.commit()
            st.success(f"Question {question_number} {'updated' if edit_row else 'saved'} successfully.")
            if edit_row or save_new:
                st.session_state.question_edit_id = None
                st.session_state.editor_version += 1
                st.rerun()
        except Exception as e:
            conn.rollback(); st.error("Unable to save the question."); st.exception(e)

# Existing questions
st.divider(); st.header("📚 Existing Questions")
cur.execute("""
SELECT q.id,q.question_number,q.question_html,q.question_image,q.question_type,p.title AS passage_title
FROM questions q LEFT JOIN passages p ON q.passage_id=p.id
WHERE q.paper_id=? ORDER BY q.question_number
""", (paper_id,))
questions = cur.fetchall()
if not questions:
    st.info("No questions have been added to this paper yet.")
else:
    for q in questions:
        qid=q["id"]; ptitle=q["passage_title"] or "No Passage"; qtype="Single Choice" if q["question_type"]=="single" else "Multiple Choice"
        with st.expander(f"Question {q['question_number']} — {ptitle} — {qtype}"):
            if q["question_html"]: st.markdown(q["question_html"], unsafe_allow_html=True)
            if q["question_image"] and Path(q["question_image"]).exists(): st.image(q["question_image"], width=450)
            cur.execute("SELECT option_letter,option_text,is_correct FROM options WHERE question_id=? ORDER BY option_letter", (qid,))
            opts=cur.fetchall()
            st.markdown("#### Options")
            for o in opts:
                st.markdown(f"**{o['option_letter']}. {o['option_text']}** ✓" if o["is_correct"] else f"{o['option_letter']}. {o['option_text']}")
            c1,c2=st.columns(2)
            with c1:
                if st.button("✏️ Edit Question", key=f"edit_question_{qid}", use_container_width=True):
                    st.session_state.question_edit_id=qid; st.session_state.editor_version += 1; st.rerun()
            with c2:
                confirm=f"confirm_delete_{qid}"
                if not st.session_state.get(confirm,False):
                    if st.button("🗑️ Delete Question", key=f"delete_question_{qid}", use_container_width=True):
                        st.session_state[confirm]=True; st.rerun()
                else:
                    st.warning(f"Delete Question {q['question_number']}?")
                    y,n=st.columns(2)
                    with y:
                        if st.button("Yes, Delete", key=f"yes_delete_{qid}", type="primary", use_container_width=True):
                            try:
                                cur.execute("DELETE FROM options WHERE question_id=?",(qid,)); cur.execute("DELETE FROM questions WHERE id=?",(qid,)); conn.commit()
                                if q["question_image"] and Path(q["question_image"]).exists():
                                    try: Path(q["question_image"]).unlink()
                                    except Exception: pass
                                st.session_state.pop(confirm,None); st.rerun()
                            except Exception as e:
                                conn.rollback(); st.error("Unable to delete the question."); st.exception(e)
                    with n:
                        if st.button("Cancel", key=f"cancel_delete_{qid}", use_container_width=True):
                            st.session_state.pop(confirm,None); st.rerun()

conn.close()
