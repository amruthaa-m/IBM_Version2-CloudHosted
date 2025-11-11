"""
Streamlit app that processes the IBM_project notebook's student dataset logic.

Modified per user request:
- Final output files now include only these columns:
  ['Learning activity - Title', 'Learner - ID', 'Learning activity - ID', 'Learning activity - Duration', 'Completion Date']
  plus a final summary row showing the TOTAL duration.

Usage:
$ pip install streamlit pandas openpyxl
$ streamlit run streamlit_app_with_processing.py
"""

import streamlit as st
import pandas as pd
import os
import tempfile
import shutil
from pathlib import Path
from datetime import datetime

st.set_page_config(page_title="Student Activity Processor", page_icon="")


def _normalize_columns(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df.columns = df.columns.str.strip()
    return df


def _find_col(df, candidates):
    lc_map = {c.lower(): c for c in df.columns}
    for cand in candidates:
        if cand.lower() in lc_map:
            return lc_map[cand.lower()]
    for key in lc_map:
        for cand in candidates:
            if "".join(key.split()) == "".join(cand.lower().split()):
                return lc_map[key]
    raise ValueError(
        f"None of the candidate columns found: {candidates}. Available columns: {list(df.columns)}"
    )


def process_student_data(input_file: str, output_dir: str) -> int:
    os.makedirs(output_dir, exist_ok=True)

    suffix = Path(input_file).suffix.lower()
    if suffix in [".xlsx", ".xls"]:
        df = pd.read_excel(input_file, engine="openpyxl")
    elif suffix == ".csv":
        df = pd.read_csv(input_file)
    else:
        raise ValueError("Unsupported file type. Please upload .xlsx or .csv files.")

    df = _normalize_columns(df)

    try:
        col_transcript = _find_col(df, ["Transcript status"])
    except ValueError:
        col_transcript = None

    col_name = _find_col(df, ["Learner - Name"])
    col_learner = _find_col(df, ["Learner - ID"])
    col_date = _find_col(df, ["Completion Date"])
    col_duration = _find_col(df, ["Learning activity - Duration"])
    col_title = _find_col(df, ["Learning activity - Title"])
    col_activity_id = _find_col(df, ["Learning activity - ID"])

    if col_transcript:
        df[col_transcript] = df[col_transcript].astype(str).str.lower().str.strip()
        df = df[df[col_transcript] == "completed"]

    df[col_date] = pd.to_datetime(df[col_date], errors="coerce").dt.date.astype(str)

    grouped = df.groupby([col_learner, col_date])
    files_written = 0

    for (learner_id, date_str), group in grouped:
        if len(group) <= 50:
            continue

        learner_data = group[
            [col_name,col_title, col_learner, col_activity_id, col_duration, col_date]
        ].copy()
        learner_data[col_duration] = pd.to_numeric(
            learner_data[col_duration], errors="coerce"
        ).fillna(0)
        total_duration = learner_data[col_duration].sum()

        summary = pd.DataFrame({col_title: ["TOTAL"], col_duration: [total_duration]})
        learner_data = pd.concat([learner_data, summary], ignore_index=True)

        safe_learner = str(learner_id).replace(" ", "_")
        safe_date = str(date_str).replace(" ", "_").replace(":", "-")
        filename = f"learner_{safe_learner}_{safe_date}.xlsx"
        learner_data.to_excel(os.path.join(output_dir, filename), index=False)
        files_written += 1

    return files_written


# ----------------------
# Streamlit UI
# ----------------------

st.title("Upload & Run Student Activity Analyzer")
st.write(
    "Upload an `.xlsx` (or `.csv`) exported dataset. The app will run the analysis and produce one Excel file per qualifying learner (more than 50 activities in a day). Results are provided as a ZIP for download."
)

uploaded = st.file_uploader("Choose dataset file", type=["xlsx","csv"])

if uploaded is not None:
    st.success(f"File received: {uploaded.name}")

    if st.button("Run Analysis"):
        with st.spinner("Running analysis..."):
            with tempfile.TemporaryDirectory() as tmpdir:
                input_path = os.path.join(tmpdir, uploaded.name)
                with open(input_path, "wb") as f:
                    f.write(uploaded.getbuffer())

                output_dir = os.path.join(tmpdir, "output")
                try:
                    written = process_student_data(input_path, output_dir)
                except Exception as e:
                    st.error(f"Processing failed: {e}")
                    written = 0

                if written > 0:
                    zip_path = shutil.make_archive(
                        os.path.join(tmpdir, "results"), "zip", output_dir
                    )
                    st.success(f"Processing complete — {written} files created.")
                    with open(zip_path, "rb") as f:
                        st.download_button(
                            label=" Download results (ZIP)",
                            data=f,
                            file_name=f"results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.zip",
                            mime="application/zip",
                        )
                else:
                    st.info(
                        "No learners qualified (no groups with >50 activities). No files were created."
                    )
