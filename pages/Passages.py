import os
from pathlib import Path
import streamlit as st
from streamlit_quill import st_quill
from utils.storage import *

st.set_page_config(page_title="Passages", page_icon="📖", layout="wide")
st.title("📖 Passage Editor")
init_db()
conn = get_connection()
cur = conn.cursor()

# Papers
cur.execute("SELECT id,name,folder,subject,year FROM papers ORDER BY year DESC,name")
papers = cur.fetchall()
if not papers:
    st.warning("No papers available.")
    st.info("Create a paper first from Admin.")
    conn.close(); st.stop()

paper_lookup = {f"{p['name']} ({p['year']})": p for p in papers}
selected_name = st.selectbox("Paper", list(paper_lookup.keys()), key="passage_paper")
paper = paper_lookup[selected_name]
paper_id, paper_folder = paper["id"], paper["folder"]
st.info(f"Paper: {paper['name']} • {paper['subject']} • {paper['year']}")

# State
st.session_state.setdefault("passage_edit_id", None)
st.session_state.setdefault("passage_editor_version", 0)
edit_id = st.session_state.passage_edit_id

# Load edit record or defaults
edit_row = None
if edit_id is not None:
    cur.execute("SELECT id,title,content,image,display_order FROM passages WHERE id=? AND paper_id=?", (edit_id, paper_id))
    edit_row = cur.fetchone()
    if edit_row is None:
        st.session_state.passage_edit_id = None
        edit_id = None

cur.execute("SELECT COALESCE(MAX(display_order),0)+1 FROM passages WHERE paper_id=?", (paper_id,))
next_order = cur.fetchone()[0]

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
    if existing_image and Path(existing_image).exists():
        st.caption("Current image")
        st.image(existing_image, width=600)
    passage_image = st.file_uploader(
        "Replace / upload passage image (optional)",
        type=["png", "jpg", "jpeg"],
        key=f"passage_image_{edit_id or 'new'}_{version}",
    )
    remove_image = False
    if edit_row and existing_image:
        remove_image = st.checkbox("Remove current image")
    display_order = st.number_input("Display Order", min_value=1, value=default_order, step=1)

    if edit_row:
        c1, c2 = st.columns(2)
        with c1:
            save = st.form_submit_button("💾 Update Passage", type="primary", use_container_width=True)
        with c2:
            cancel = st.form_submit_button("Cancel", use_container_width=True)
        save_new = False
    else:
        c1, c2 = st.columns(2)
        with c1:
            save = st.form_submit_button("💾 Save", use_container_width=True)
        with c2:
            save_new = st.form_submit_button("💾 Save & New Passage", use_container_width=True)
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
    has_content = bool(passage_content and passage_content.strip() and passage_content.strip() not in ("<p><br></p>", "<p></p>"))
    has_existing_image = bool(existing_image and not remove_image)
    if not has_content and passage_image is None and not has_existing_image:
        errors.append("Add passage text or a passage image.")

    # Unique order, excluding current passage while editing
    if edit_row:
        cur.execute("SELECT id FROM passages WHERE paper_id=? AND display_order=? AND id<>?", (paper_id, int(display_order), edit_id))
    else:
        cur.execute("SELECT id FROM passages WHERE paper_id=? AND display_order=?", (paper_id, int(display_order)))
    if cur.fetchone():
        errors.append(f"Display order {display_order} already exists for this paper.")

    if errors:
        st.error("Please fix the following:")
        for e in errors: st.write(f"• {e}")
    else:
        try:
            saved_image = existing_image
            passage_dir = Path("papers") / paper_folder / "passages"
            passage_dir.mkdir(parents=True, exist_ok=True)

            if remove_image and existing_image:
                old = Path(existing_image)
                if old.exists():
                    try: old.unlink()
                    except Exception: pass
                saved_image = None

            if passage_image is not None:
                if existing_image:
                    old = Path(existing_image)
                    if old.exists():
                        try: old.unlink()
                        except Exception: pass
                ext = os.path.splitext(passage_image.name)[1].lower() or ".png"
                # id when editing prevents collisions; order is fine for new records
                stem = f"passage_{edit_id}" if edit_id else f"passage_{int(display_order)}"
                path = passage_dir / f"{stem}{ext}"
                path.write_bytes(passage_image.getbuffer())
                saved_image = str(path).replace("\\", "/")

            if edit_row:
                cur.execute(
                    "UPDATE passages SET title=?,content=?,image=?,display_order=? WHERE id=?",
                    (clean_title, passage_content, saved_image, int(display_order), edit_id),
                )
                msg = f"{clean_title} updated successfully."
            else:
                cur.execute(
                    "INSERT INTO passages(paper_id,title,content,image,display_order) VALUES(?,?,?,?,?)",
                    (paper_id, clean_title, passage_content, saved_image, int(display_order)),
                )
                msg = f"{clean_title} saved successfully."
            conn.commit()
            st.success(msg)
            if edit_row or save_new:
                st.session_state.passage_edit_id = None
                st.session_state.passage_editor_version += 1
                st.rerun()
        except Exception as e:
            conn.rollback(); st.error("Unable to save passage."); st.exception(e)

# Existing passages
st.divider(); st.header("📚 Existing Passages")
cur.execute("SELECT id,title,content,image,display_order FROM passages WHERE paper_id=? ORDER BY display_order", (paper_id,))
passages = cur.fetchall()
if not passages:
    st.info("No passages have been added to this paper yet.")
else:
    for p in passages:
        pid = p["id"]
        with st.expander(f"{p['display_order']}. {p['title']}"):
            if p["content"]: st.markdown(p["content"], unsafe_allow_html=True)
            if p["image"] and Path(p["image"]).exists(): st.image(p["image"], width=600)
            cur.execute("SELECT question_number FROM questions WHERE passage_id=? ORDER BY question_number", (pid,))
            linked = cur.fetchall()
            if linked:
                st.write("**Questions using this passage:** " + ", ".join(str(x["question_number"]) for x in linked))
            else:
                st.caption("No questions are linked to this passage yet.")

            c1, c2 = st.columns(2)
            with c1:
                if st.button("✏️ Edit Passage", key=f"edit_passage_{pid}", use_container_width=True):
                    st.session_state.passage_edit_id = pid
                    st.session_state.passage_editor_version += 1
                    st.rerun()
            with c2:
                if linked:
                    st.button("🗑️ Delete Passage", key=f"delete_disabled_{pid}", disabled=True, use_container_width=True)
                else:
                    confirm_key = f"confirm_delete_passage_{pid}"
                    if not st.session_state.get(confirm_key, False):
                        if st.button("🗑️ Delete Passage", key=f"delete_passage_{pid}", use_container_width=True):
                            st.session_state[confirm_key] = True; st.rerun()
                    else:
                        st.warning(f"Delete {p['title']}?")
                        y, n = st.columns(2)
                        with y:
                            if st.button("Yes, Delete", key=f"yes_delete_passage_{pid}", type="primary", use_container_width=True):
                                try:
                                    if p["image"] and Path(p["image"]).exists():
                                        try: Path(p["image"]).unlink()
                                        except Exception: pass
                                    cur.execute("DELETE FROM passages WHERE id=?", (pid,)); conn.commit()
                                    st.session_state.pop(confirm_key, None); st.rerun()
                                except Exception as e:
                                    conn.rollback(); st.error("Unable to delete passage."); st.exception(e)
                        with n:
                            if st.button("Cancel", key=f"cancel_delete_passage_{pid}", use_container_width=True):
                                st.session_state.pop(confirm_key, None); st.rerun()

conn.close()
