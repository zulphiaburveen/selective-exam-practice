import streamlit as st
from pathlib import Path
import json

st.set_page_config(
    page_title="Admin",
    page_icon="⚙️"
)

st.title("⚙️ Admin")

PAPERS_FOLDER = Path("papers")
SETTINGS_FILE = Path("data/settings.json")

PAPERS_FOLDER.mkdir(exist_ok=True)
SETTINGS_FILE.parent.mkdir(exist_ok=True)

if not SETTINGS_FILE.exists():
    SETTINGS_FILE.write_text(
        json.dumps({"active_paper": ""}, indent=4)
    )

with open(SETTINGS_FILE) as f:
    settings = json.load(f)

papers = sorted(
    [p.name for p in PAPERS_FOLDER.iterdir() if p.is_dir()]
)

if not papers:
    st.warning("No papers found.")
    st.stop()

selected = st.selectbox(
    "Choose today's paper",
    papers,
    index=papers.index(settings["active_paper"])
    if settings["active_paper"] in papers
    else 0
)

if st.button("Publish"):

    settings["active_paper"] = selected

    with open(SETTINGS_FILE, "w") as f:
        json.dump(settings, f, indent=4)

    st.success(f"{selected} is now today's paper.")