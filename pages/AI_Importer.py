import base64
import io
import json
import re
from pathlib import Path

import httpx
import pandas as pd
import streamlit as st
from streamlit_quill import st_quill
from docx import Document
from docx.table import Table
from docx.text.paragraph import Paragraph
import pymupdf
from openai import OpenAI

from utils.storage import *


st.set_page_config(page_title="AI Importer", page_icon="🤖", layout="wide")
st.title("🤖 AI Paper Importer")
st.caption(
    "Extract into a review screen first. Nothing is written to the exam tables "
    "until you approve the import."
)

init_db()


# =======================================================
# SESSION STATE
# =======================================================

st.session_state.setdefault("ai_import_result", None)
st.session_state.setdefault("ai_import_source_name", None)


# =======================================================
# HELPERS
# =======================================================

QUESTION_RE = re.compile(r"^\s*(\d+)\.\s*(.+)", re.S)
OPTION_RE = re.compile(r"^\s*([A-L])\.\s*(.+)", re.S)


def strip_json_fence(text):
    value = (text or "").strip()
    if value.startswith("```"):
        value = re.sub(r"^```(?:json)?\s*", "", value, flags=re.I)
        value = re.sub(r"\s*```$", "", value)
    return value.strip()


def html_from_text(text):
    value = (text or "").strip()
    if not value:
        return ""
    # Preserve simple diagrams/tables as line breaks without allowing arbitrary HTML.
    import html
    return "<p>" + html.escape(value).replace("\n", "<br>") + "</p>"


DATA_IMAGE_RE = re.compile(
    r"data:image/(?P<kind>png|jpeg|jpg|gif|webp);base64,(?P<data>[A-Za-z0-9+/=\s]+)",
    re.I,
)


def persist_inline_images(html_value, paper_id, object_prefix):
    """
    Quill may embed pasted clipboard images as base64 data URIs.
    Move those images to Supabase Storage and replace the data URIs
    with permanent public URLs before saving HTML to the database.
    """
    html_value = html_value or ""
    if not html_value:
        return ""

    matches = list(DATA_IMAGE_RE.finditer(html_value))
    if not matches:
        return html_value

    updated = html_value

    for index, match in enumerate(matches, start=1):
        kind = match.group("kind").lower()
        encoded = re.sub(r"\s+", "", match.group("data"))

        if kind == "jpg":
            kind = "jpeg"

        extension = ".jpg" if kind == "jpeg" else f".{kind}"
        content_type = f"image/{kind}"

        image_bytes = base64.b64decode(encoded)

        object_path = (
            f"papers/{paper_id}/imported/"
            f"{object_prefix}_inline_{index}{extension}"
        )

        public_url = upload_file_bytes(
            object_path,
            image_bytes,
            content_type,
            upsert=True,
        )

        updated = updated.replace(
            match.group(0),
            public_url,
            1,
        )

    return updated


def parse_answer_letters(value):
    if value is None:
        return []
    text = str(value).upper().strip()
    return re.findall(r"\b[A-L]\b", text)


def answer_key_from_csv(file_bytes):
    if not file_bytes:
        return {}
    df = pd.read_csv(io.BytesIO(file_bytes))
    required = {"Question", "Answer"}
    if not required.issubset(set(df.columns)):
        raise ValueError("Answer CSV must contain Question and Answer columns.")

    result = {}
    for _, row in df.iterrows():
        qn = int(row["Question"])
        result[qn] = {
            "answers": parse_answer_letters(row["Answer"]),
            "skill": str(row.get("Skill", "") or ""),
            "explanation": str(row.get("Explanation", "") or ""),
        }
    return result


def iter_docx_blocks(doc):
    """Yield Paragraph/Table objects in their true document order."""
    parent = doc.element.body
    for child in parent.iterchildren():
        if child.tag.endswith("}p"):
            yield Paragraph(child, doc)
        elif child.tag.endswith("}tbl"):
            yield Table(child, doc)


def table_text(table):
    rows = []
    for row in table.rows:
        cells = [re.sub(r"\s+", " ", cell.text.strip()) for cell in row.cells]
        rows.append(" | ".join(cells))
    return "\n".join(rows)


def option_cells(table):
    found = []
    for row in table.rows:
        for cell in row.cells:
            text = re.sub(r"\s+", " ", cell.text.strip())
            match = OPTION_RE.match(text)
            if match:
                found.append({"letter": match.group(1), "text": match.group(2).strip()})
    return found


def parse_math_docx(file_bytes, answer_key):
    """
    Deterministic Word parser designed for the current Year 4 maths format:
    question paragraph -> optional diagram/table -> options table.
    It is intentionally conservative and goes through Review before import.
    """
    doc = Document(io.BytesIO(file_bytes))

    questions = []
    current = None

    for block in iter_docx_blocks(doc):
        if isinstance(block, Paragraph):
            text = block.text.strip()
            if not text:
                continue

            qmatch = QUESTION_RE.match(text)
            if qmatch:
                if current:
                    questions.append(current)
                qn = int(qmatch.group(1))
                current = {
                    "question_number": qn,
                    "passage_ref": None,
                    "question_text": qmatch.group(2).strip(),
                    "options": [],
                    "correct_answers": answer_key.get(qn, {}).get("answers", []),
                    "question_type": (
                        "multiple"
                        if len(answer_key.get(qn, {}).get("answers", [])) > 1
                        else "single"
                    ),
                    "skill": answer_key.get(qn, {}).get("skill", ""),
                    "explanation": answer_key.get(qn, {}).get("explanation", ""),
                }
                continue

            if current:
                current["question_text"] += "\n" + text

        elif isinstance(block, Table):
            if current is None:
                continue

            options = option_cells(block)
            if options:
                current["options"].extend(options)
            else:
                # Non-option tables are treated as a diagram/data table belonging
                # to the current question.
                txt = table_text(block).strip()
                if txt:
                    current["question_text"] += "\n" + txt

    if current:
        questions.append(current)

    # Remove accidental duplicate option letters from merged Word cells.
    for question in questions:
        dedup = {}
        for option in question["options"]:
            dedup[option["letter"]] = option["text"]
        question["options"] = [
            {"letter": letter, "text": text}
            for letter, text in sorted(dedup.items())
        ]

    return {
        "passages": [],
        "questions": questions,
        "warnings": [],
        "source_mode": "DOCX deterministic parser",
    }


def docx_to_text(file_bytes):
    doc = Document(io.BytesIO(file_bytes))
    parts = []
    for block in iter_docx_blocks(doc):
        if isinstance(block, Paragraph):
            text = block.text.strip()
            if text:
                parts.append(text)
        elif isinstance(block, Table):
            txt = table_text(block).strip()
            if txt:
                parts.append(txt)
    return "\n\n".join(parts)


def pdf_text_and_images(file_bytes, max_pages=20):
    doc = pymupdf.open(stream=file_bytes, filetype="pdf")
    pages = []
    for idx, page in enumerate(doc):
        if idx >= max_pages:
            break
        text = page.get_text("text")
        pix = page.get_pixmap(matrix=pymupdf.Matrix(1.5, 1.5), alpha=False)
        png = pix.tobytes("png")
        pages.append(
            {
                "page_number": idx + 1,
                "text": text,
                "image_b64": base64.b64encode(png).decode("ascii"),
            }
        )
    return pages


def ai_extract(source_name, file_bytes, answer_key):
    if "OPENAI_API_KEY" not in st.secrets:
        raise RuntimeError(
            "OPENAI_API_KEY is missing from Streamlit Secrets."
        )

    client = OpenAI(api_key=st.secrets["OPENAI_API_KEY"])
    model = st.secrets.get("OPENAI_MODEL", "gpt-6-luna")

    suffix = Path(source_name).suffix.lower()

    if suffix == ".docx":
        source_text = docx_to_text(file_bytes)
        content = [
            {
                "type": "input_text",
                "text": (
                    "Extract the assessment below into the required JSON.\n\n"
                    + source_text
                ),
            }
        ]
    elif suffix == ".pdf":
        pages = pdf_text_and_images(file_bytes)
        combined = "\n\n".join(
            f"--- PAGE {p['page_number']} TEXT ---\n{p['text']}"
            for p in pages
        )
        content = [
            {
                "type": "input_text",
                "text": (
                    "Extract the assessment from the page text and page images "
                    "into the required JSON.\n\n" + combined
                ),
            }
        ]
        for page in pages:
            content.append(
                {
                    "type": "input_image",
                    "image_url": f"data:image/png;base64,{page['image_b64']}",
                    "detail": "high",
                }
            )
    else:
        raise ValueError("Only PDF and DOCX sources are supported.")

    answer_key_text = json.dumps(
        {
            str(qn): data["answers"]
            for qn, data in answer_key.items()
        },
        ensure_ascii=False,
    )

    instructions = f"""
You extract school assessment papers.

Return JSON only, no markdown fence.

Required structure:
{{
  "passages": [
    {{
      "ref": "p1",
      "title": "Passage 1",
      "content": "full passage text"
    }}
  ],
  "questions": [
    {{
      "question_number": 1,
      "passage_ref": null,
      "question_text": "question stem including any essential textual diagram/table",
      "question_type": "single",
      "options": [
        {{"letter": "A", "text": "option text"}},
        {{"letter": "B", "text": "option text"}}
      ],
      "correct_answers": ["B"]
    }}
  ],
  "warnings": []
}}

Rules:
- Preserve the source wording. Do not rewrite or improve the questions.
- Preserve symbols, units, arrows, tables, simple diagrams and line breaks.
- Do not invent missing text.
- Keep options dynamic: A/B/C/D or however many exist in the source.
- passage_ref must be null for questions with no reading passage.
- For English-style papers, extract each reading passage once and link its questions.
- question_type is "single" unless more than one option itself must be selected.
- An option whose text contains multiple values is still a single option.
- Use the supplied answer key when present; it is authoritative.
- If the answer key and paper appear inconsistent, keep the paper wording and add a warning.
- If content cannot be read, add a warning rather than guessing.

Authoritative answer key by question number:
{answer_key_text}
"""

    response = client.responses.create(
        model=model,
        instructions=instructions,
        input=[{"role": "user", "content": content}],
        max_output_tokens=18000,
    )

    data = json.loads(strip_json_fence(response.output_text))

    # Re-apply CSV answers after AI extraction so AI cannot override them.
    for q in data.get("questions", []):
        qn = int(q["question_number"])
        if qn in answer_key and answer_key[qn]["answers"]:
            q["correct_answers"] = answer_key[qn]["answers"]
            q["question_type"] = (
                "multiple" if len(answer_key[qn]["answers"]) > 1 else "single"
            )
            q["skill"] = answer_key[qn]["skill"]
            q["explanation"] = answer_key[qn]["explanation"]
        else:
            q.setdefault("skill", "")
            q.setdefault("explanation", "")

    data["source_mode"] = f"OpenAI Responses API ({model})"
    return data


def fetch_stored_source(url):
    with httpx.Client(follow_redirects=True, timeout=60) as client:
        response = client.get(url)
        response.raise_for_status()
        return response.content


def commit_import(paper_id, extracted):
    existing = get_questions(paper_id)
    if existing:
        raise RuntimeError(
            "This paper already contains questions. Import is blocked to prevent duplicates."
        )

    sb = get_supabase()

    passage_map = {}
    passage_rows = extracted.get("passages", [])

    # ---------------------------------------------------
    # PASSAGES
    # ---------------------------------------------------

    for index, passage in enumerate(passage_rows, start=1):
        passage_html = passage.get("content_html")

        if not passage_html:
            passage_html = html_from_text(
                passage.get("content", "")
            )

        passage_html = persist_inline_images(
            passage_html,
            paper_id,
            f"passage_{index}",
        )

        created = (
            sb.table("passages")
            .insert(
                {
                    "paper_id": paper_id,
                    "title": passage.get("title") or f"Passage {index}",
                    "content": passage_html,
                    "image": None,
                    "display_order": index,
                }
            )
            .execute()
            .data[0]
        )

        passage_map[passage.get("ref")] = created["id"]

    # ---------------------------------------------------
    # QUESTIONS
    # ---------------------------------------------------

    question_payload = []

    for q in extracted.get("questions", []):
        qn = int(q["question_number"])

        question_html = q.get("question_html")

        if not question_html:
            question_html = html_from_text(
                q.get("question_text", "")
            )

        question_html = persist_inline_images(
            question_html,
            paper_id,
            f"q{qn}",
        )

        question_payload.append(
            {
                "paper_id": paper_id,
                "passage_id": passage_map.get(q.get("passage_ref")),
                "question_number": qn,
                "question_html": question_html,
                "question_image": None,
                "question_type": q.get("question_type", "single"),
            }
        )

    if not question_payload:
        raise RuntimeError("No approved questions to import.")

    created_questions = (
        sb.table("questions")
        .insert(question_payload)
        .execute()
        .data
    )

    by_number = {
        int(row["question_number"]): row["id"]
        for row in created_questions
    }

    # ---------------------------------------------------
    # OPTIONS
    # ---------------------------------------------------

    option_payload = []

    for q in extracted.get("questions", []):
        qn = int(q["question_number"])
        qid = by_number[qn]
        correct = set(q.get("correct_answers") or [])

        for option in q.get("options", []):
            option_payload.append(
                {
                    "question_id": qid,
                    "option_letter": option["letter"],
                    "option_text": option["text"],
                    "is_correct": option["letter"] in correct,
                }
            )

    if option_payload:
        sb.table("options").insert(option_payload).execute()

    clear_data_cache()

    return len(created_questions), len(passage_rows)


# =======================================================
# TARGET PAPER
# =======================================================

papers = get_papers()
drafts = [paper for paper in papers if not paper["published"]]

if not drafts:
    st.warning("No draft paper is available. Create a draft paper in Admin first.")
    st.stop()

paper_lookup = {
    f"{p['name']} ({p['year']})": p
    for p in drafts
}

selected_label = st.selectbox("Target draft paper", list(paper_lookup))
paper = paper_lookup[selected_label]
paper_id = paper["id"]

existing_questions = get_questions(paper_id)
if existing_questions:
    st.error(
        f"This paper already has {len(existing_questions)} question(s). "
        "The importer will not append automatically because that could create duplicates."
    )
    st.stop()

st.info(
    f"Target: **{paper['name']}** • {paper['subject']} • {paper['year']}"
)


# =======================================================
# SOURCE
# =======================================================

st.markdown("### 1. Source paper")

stored_source = paper.get("filename")
use_stored = False

if stored_source and is_remote_file(stored_source):
    use_stored = st.checkbox(
        "Use the original file already stored for this paper",
        value=True,
    )

uploaded_source = None
if not use_stored:
    uploaded_source = st.file_uploader(
        "Upload PDF or DOCX",
        type=["pdf", "docx"],
        key="ai_source",
    )

answer_file = st.file_uploader(
    "Answer key CSV (optional but recommended)",
    type=["csv"],
    key="ai_answers",
    help="Expected columns: Question, Answer. Skill and Explanation are optional.",
)

mode = st.radio(
    "Extraction mode",
    [
        "Smart Word parser",
        "OpenAI AI extraction",
    ],
    horizontal=True,
)

if mode == "Smart Word parser":
    st.caption(
        "Fast and inexpensive. Best for structured DOCX papers like the uploaded Year 4 Maths sample."
    )
else:
    st.caption(
        "Uses the OpenAI Responses API. Recommended for PDFs, reading passages, and harder layouts."
    )


# =======================================================
# EXTRACT
# =======================================================

if st.button("🔍 Extract for Review", type="primary", width="stretch"):
    try:
        if use_stored:
            source_bytes = fetch_stored_source(stored_source)
            # Supabase URL retains the extension in the object name.
            source_name = stored_source.split("?")[0].split("/")[-1]
        elif uploaded_source is not None:
            source_bytes = uploaded_source.getvalue()
            source_name = uploaded_source.name
        else:
            st.error("Choose or upload a source paper.")
            st.stop()

        answers = answer_key_from_csv(
            answer_file.getvalue() if answer_file else None
        )

        with st.spinner("Extracting paper..."):
            if mode == "Smart Word parser":
                if Path(source_name).suffix.lower() != ".docx":
                    raise ValueError(
                        "Smart Word parser requires a DOCX. Use OpenAI AI extraction for PDF."
                    )
                extracted = parse_math_docx(source_bytes, answers)
            else:
                extracted = ai_extract(source_name, source_bytes, answers)

        st.session_state.ai_import_result = extracted
        st.session_state.ai_import_source_name = source_name
        st.success(
            f"Extracted {len(extracted.get('questions', []))} question(s). Review below."
        )
        st.rerun()

    except Exception as exc:
        st.error("Extraction failed.")
        st.exception(exc)


# =======================================================
# REVIEW
# =======================================================

extracted = st.session_state.get("ai_import_result")

if extracted:
    st.divider()
    st.markdown("### 2. Review before import")

    st.caption(f"Source mode: {extracted.get('source_mode', 'Unknown')}")

    warnings = extracted.get("warnings") or []
    if warnings:
        for warning in warnings:
            st.warning(warning)

    passage_refs = [None] + [
        p.get("ref")
        for p in extracted.get("passages", [])
    ]

    for passage_index, passage in enumerate(extracted.get("passages", [])):
        with st.expander(
            f"📖 {passage.get('title') or f'Passage {passage_index + 1}'}",
            expanded=False,
        ):
            passage["title"] = st.text_input(
                "Title",
                value=passage.get("title", ""),
                key=f"imp_passage_title_{passage_index}",
            )
            if not passage.get("content_html"):
                passage["content_html"] = html_from_text(
                    passage.get("content", "")
                )

            st.markdown("**Passage content**")
            passage["content_html"] = st_quill(
                value=passage["content_html"],
                html=True,
                placeholder="Review the passage. You can paste images directly with Ctrl+V.",
                key=f"imp_passage_content_{passage_index}",
            )
            st.caption(
                "Tip: copy an image or screenshot, click inside the editor, then press Ctrl+V."
            )

    st.markdown(f"#### Questions ({len(extracted.get('questions', []))})")

    for index, q in enumerate(extracted.get("questions", [])):
        qn = int(q["question_number"])

        with st.expander(f"Question {qn}", expanded=(index < 2)):
            if not q.get("question_html"):
                q["question_html"] = html_from_text(
                    q.get("question_text", "")
                )

            st.markdown("**Question**")
            q["question_html"] = st_quill(
                value=q["question_html"],
                html=True,
                placeholder=(
                    "Review the question. Paste diagrams/screenshots directly "
                    "into this editor with Ctrl+V."
                ),
                key=f"imp_q_text_{qn}",
            )
            st.caption(
                "You can paste an image directly into the question editor. "
                "On import it will be moved to Supabase Storage automatically."
            )

            selected_passage = st.selectbox(
                "Passage",
                passage_refs,
                index=(
                    passage_refs.index(q.get("passage_ref"))
                    if q.get("passage_ref") in passage_refs
                    else 0
                ),
                format_func=lambda value: "No Passage" if value is None else value,
                key=f"imp_q_passage_{qn}",
            )
            q["passage_ref"] = selected_passage

            q["question_type"] = st.radio(
                "Question type",
                ["single", "multiple"],
                index=0 if q.get("question_type", "single") == "single" else 1,
                horizontal=True,
                key=f"imp_q_type_{qn}",
            )

            option_letters = []
            for opt_index, option in enumerate(q.get("options", [])):
                letter = option.get("letter", chr(65 + opt_index))
                option_letters.append(letter)
                option["letter"] = letter
                option["text"] = st.text_input(
                    f"{letter}",
                    value=option.get("text", ""),
                    key=f"imp_q_{qn}_opt_{letter}",
                )

            if q["question_type"] == "single":
                current = (q.get("correct_answers") or [None])[0]
                if option_letters:
                    selected = st.selectbox(
                        "Correct answer",
                        option_letters,
                        index=option_letters.index(current) if current in option_letters else 0,
                        key=f"imp_q_correct_{qn}",
                    )
                    q["correct_answers"] = [selected]
            else:
                q["correct_answers"] = st.multiselect(
                    "Correct answers",
                    option_letters,
                    default=[
                        x for x in q.get("correct_answers", [])
                        if x in option_letters
                    ],
                    key=f"imp_q_correct_multi_{qn}",
                )

            if q.get("skill"):
                st.caption(f"Skill: {q['skill']}")
            if q.get("explanation"):
                st.caption(f"Answer-key explanation: {q['explanation']}")

    st.divider()

    confirm = st.checkbox(
        "I reviewed the extracted questions and want to import them into this draft paper."
    )

    c1, c2 = st.columns(2)

    with c1:
        if st.button(
            "✅ Import Approved Content",
            type="primary",
            width="stretch",
            disabled=not confirm,
        ):
            try:
                with st.spinner("Saving passages, questions and options..."):
                    q_count, p_count = commit_import(paper_id, extracted)

                st.session_state.ai_import_result = None
                st.session_state.ai_import_source_name = None

                st.success(
                    f"Imported {q_count} questions and {p_count} passage(s). "
                    "Open Question Editor to make any final adjustments."
                )
                st.rerun()
            except Exception as exc:
                st.error("Import failed. No further import should be attempted until this error is checked.")
                st.exception(exc)

    with c2:
        if st.button("🗑️ Discard Extraction", width="stretch"):
            st.session_state.ai_import_result = None
            st.session_state.ai_import_source_name = None
            st.rerun()
