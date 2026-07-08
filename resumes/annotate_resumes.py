#!/usr/bin/env python3
"""
NER annotation script for resume text files (BIO scheme).
"""

import json
from pathlib import Path
from datetime import datetime, timezone
from collections import defaultdict

BASE        = Path("/sessions/epic-brave-thompson/mnt/ner-project/resumes")
UNANNOTATED = BASE / "unannotated"
ANNOTATED   = BASE / "annotated"
PROGRESS_LOG      = ANNOTATED / "progress_log.json"
ANNOTATIONS_JSONL = ANNOTATED / "annotations.jsonl"
RUN_LOG           = ANNOTATED / "run_log.txt"

def tokenize(text):
    return text.split()

def find_all_spans(tokens, span):
    hits = []
    n = len(span)
    for i in range(len(tokens) - n + 1):
        if tokens[i:i + n] == span:
            hits.append((i, i + n))
    return hits

def apply_entities(tokens, entity_list):
    tags = ["O"] * len(tokens)
    for span_tokens, label in entity_list:
        for start, end in find_all_spans(tokens, span_tokens):
            if all(tags[i] == "O" for i in range(start, end)):
                tags[start] = "B-" + label
                for i in range(start + 1, end):
                    tags[i] = "I-" + label
    return tags

def count_entities(tags):
    counts = defaultdict(int)
    for tag in tags:
        if tag.startswith("B-"):
            counts[tag[2:]] += 1
    return dict(counts)

# Exact token strings (whitespace-split). Use repr() or actual bytes for special chars.
SP = "SuperPro\xef\xac\x81le".encode().decode("utf-8")   # SuperProﬁle (fi ligature)
ZW_BTECH = "​B.Tech"                                 # zero-width space + B.Tech

ENTITIES = {

    # ── File 1: ABHIJITH_R.txt ───────────────────────────────────────────────
    "ABHIJITH_R.txt": [
        (["+91-9496969017"],                              "CONTACT_DETAILS"),
        (["abhijithrcr7@gmail.com"],                     "CONTACT_DETAILS"),
        (["B.Tech", "(Information", "Technology)"],      "DEGREE"),
        (["Govt.", "Engineering", "College"],             "INSTITUTION"),
        (["Kendriya", "Vidyalaya", "Pattom"],            "INSTITUTION"),
        (["Kendriya", "Vidyalaya", "Pattom,"],           "INSTITUTION"),
        (["IIT", "Bombay."],                             "INSTITUTION"),
        (["Coursera"],                                   "INSTITUTION"),
        (["Mahindra", "Pride", "Classroom."],            "INSTITUTION"),
        (["Google", "Cloud,"],                           "TOOL_FRAMEWORK"),
        (["MySQL."],                                     "TOOL_FRAMEWORK"),
        (["Python."],                                    "PROGRAMMING_LANGUAGE"),
    ],

    # ── File 2: MONISHA_V_-_Python.txt ──────────────────────────────────────
    "MONISHA_V_-_Python.txt": [
        (["monishamanohar669@gmail.com"],                "CONTACT_DETAILS"),
        (["+", "91", "7012088863"],                      "CONTACT_DETAILS"),
        (["Palliyalil(Ho),Vadakumpuram(Po)", "Valancherry,Malappuram"], "CONTACT_DETAILS"),
        (["Cochin", "College", "of", "Engineering", "and", "Technology"], "INSTITUTION"),
        (["Kerala", "Board", "of", "Higher", "Secondary", "Education"], "INSTITUTION"),
        (["University", "of", "Calicut"],                "INSTITUTION"),
        (["B-Tech", "Computer", "Science", "and", "Engineering"], "DEGREE"),
        (["Junior", "Python", "Developer"],              "JOB_TITLE"),
        (["Python", "Trainee"],                          "JOB_TITLE"),
        (["Quest", "Innovative", "Solutions"],           "COMPANY"),
        (["Strokx", "Technologies"],                     "COMPANY"),
        (["Django"],                                     "TOOL_FRAMEWORK"),
        (["Bootstrap"],                                  "TOOL_FRAMEWORK"),
        (["Git"],                                        "TOOL_FRAMEWORK"),
        (["MySQL"],                                      "TOOL_FRAMEWORK"),
        (["SQlite"],                                     "TOOL_FRAMEWORK"),
        (["Jira"],                                       "TOOL_FRAMEWORK"),
        (["Python"],                                     "PROGRAMMING_LANGUAGE"),
    ],

    # ── File 3: Gouri_K_M_Python_Developer_2yrs_exp_linkedin.txt ────────────
    "Gouri_K_M_Python_Developer_2yrs_exp_linkedin.txt": [
        (["gourikm22@gmail.com"],                        "CONTACT_DETAILS"),
        (["+918547158691"],                              "CONTACT_DETAILS"),
        (["2", "years", "and", "2", "months", "of", "hands-on", "experience"],
                                                         "YEARS_OF_EXP"),
        (["CUSAT"],                                      "INSTITUTION"),
        (["GHSS", "Kunhimangalam"],                      "INSTITUTION"),
        (["Linkedin."],                                  "INSTITUTION"),
        (["Udemy."],                                     "INSTITUTION"),
        ([ZW_BTECH, "Computer", "Science", "Degree"],   "DEGREE"),
        (["Programmer", "Analyst"],                      "JOB_TITLE"),
        (["SysTalent", "Software", "Pvt", "Ltd"],       "COMPANY"),
        (["AWS", "QuickSight,"],                         "TOOL_FRAMEWORK"),
        (["AWS", "QuickSight."],                         "TOOL_FRAMEWORK"),
        (["AWS", "QuickSight"],                          "TOOL_FRAMEWORK"),
        (["AWS", "Lambda,"],                             "TOOL_FRAMEWORK"),
        (["Jupyter", "Notebook,"],                       "TOOL_FRAMEWORK"),
        (["Jupyter", "Notebook"],                        "TOOL_FRAMEWORK"),
        (["PostgreSQL"],                                 "TOOL_FRAMEWORK"),
        (["ReactJS"],                                    "TOOL_FRAMEWORK"),
        (["Reactjs."],                                   "TOOL_FRAMEWORK"),
        (["MySQL,PostgreSQL"],                           "TOOL_FRAMEWORK"),
        (["Numpy,"],                                     "TOOL_FRAMEWORK"),
        (["Pandas"],                                     "TOOL_FRAMEWORK"),
        (["PyCharm,"],                                   "TOOL_FRAMEWORK"),
        (["Anaconda."],                                  "TOOL_FRAMEWORK"),
        (["Anaconda,"],                                  "TOOL_FRAMEWORK"),
        (["Git,"],                                       "TOOL_FRAMEWORK"),
        (["Bitbucket"],                                  "TOOL_FRAMEWORK"),
        (["Django,"],                                    "TOOL_FRAMEWORK"),
        (["Django"],                                     "TOOL_FRAMEWORK"),
        (["JavaScript,"],                                "PROGRAMMING_LANGUAGE"),
        (["JavaScript"],                                 "PROGRAMMING_LANGUAGE"),
        (["Python,"],                                    "PROGRAMMING_LANGUAGE"),
        (["Python."],                                    "PROGRAMMING_LANGUAGE"),
        (["Python"],                                     "PROGRAMMING_LANGUAGE"),
        (["C++"],                                        "PROGRAMMING_LANGUAGE"),
        (["C#"],                                         "PROGRAMMING_LANGUAGE"),
        (["SQL."],                                       "PROGRAMMING_LANGUAGE"),
    ],

    # ── File 4: SriAiyshwar-Python.txt ──────────────────────────────────────
    "SriAiyshwar-Python.txt": [
        (["linkedin.com/in/aishwar790"],                 "CONTACT_DETAILS"),
        (["github.com/sreeaishwar"],                     "CONTACT_DETAILS"),
        (["+91", "7907319732"],                          "CONTACT_DETAILS"),
        (["sreeaishwar1996@gmail.com"],                  "CONTACT_DETAILS"),
        (["Data", "Science", "Academy"],                 "INSTITUTION"),
        (["Sree", "Narayana", "Gurukulam", "College", "of", "Engineering,"],
                                                         "INSTITUTION"),
        (["Chinmaya", "Vidyalaya,"],                     "INSTITUTION"),
        (["iROID", "Technologies"],                      "INSTITUTION"),  # certifying body
        (["Udemy"],                                      "INSTITUTION"),
        (["CBSE"],                                       "INSTITUTION"),
        (["MGU"],                                        "INSTITUTION"),
        (["Computer", "Science", "and", "Engineering,"], "DEGREE"),
        (["Digital", "Associate"],                       "JOB_TITLE"),
        (["CURVELOGICS", "ADVANCED", "TECHNOLOGY", "SOLUTIONS", "PVT", "LTD"],
                                                         "COMPANY"),
        (["Amazon", "inc."],                             "COMPANY"),
        (["IROID", "Technologies"],                      "COMPANY"),      # internship employer
        (["Android", "Studio"],                          "TOOL_FRAMEWORK"),
        (["Google", "Colab"],                            "TOOL_FRAMEWORK"),
        (["Jupyter", "Notebook,"],                       "TOOL_FRAMEWORK"),
        (["Scikit-Learn,"],                              "TOOL_FRAMEWORK"),
        (["Tensorflow,"],                                "TOOL_FRAMEWORK"),
        (["BeautifulSoup,"],                             "TOOL_FRAMEWORK"),
        (["TensorFlow"],                                 "TOOL_FRAMEWORK"),
        (["OpenCV)"],                                    "TOOL_FRAMEWORK"),
        (["PyTorch,"],                                   "TOOL_FRAMEWORK"),
        (["StarScream"],                                 "TOOL_FRAMEWORK"),
        (["Matplotlib"],                                 "TOOL_FRAMEWORK"),
        (["Pandas,"],                                    "TOOL_FRAMEWORK"),
        (["Pandas"],                                     "TOOL_FRAMEWORK"),
        (["Numpy,"],                                     "TOOL_FRAMEWORK"),
        (["Numpy"],                                      "TOOL_FRAMEWORK"),
        (["Keras,"],                                     "TOOL_FRAMEWORK"),
        (["Keras"],                                      "TOOL_FRAMEWORK"),
        (["Scikit"],                                     "TOOL_FRAMEWORK"),
        (["MYSQL"],                                      "TOOL_FRAMEWORK"),
        (["SQLite,"],                                    "TOOL_FRAMEWORK"),
        (["SQLite"],                                     "TOOL_FRAMEWORK"),
        (["Python,"],                                    "PROGRAMMING_LANGUAGE"),
        (["Python"],                                     "PROGRAMMING_LANGUAGE"),
        (["Java,"],                                      "PROGRAMMING_LANGUAGE"),
        (["Java"],                                       "PROGRAMMING_LANGUAGE"),
        (["C/C++,"],                                     "PROGRAMMING_LANGUAGE"),
        (["SQL,"],                                       "PROGRAMMING_LANGUAGE"),
    ],

    # ── File 5: Resume_Theertha_Krishna_DataScience.txt ─────────────────────
    "Resume_Theertha_Krishna_DataScience.txt": [
        (["theertha.krishna2021@gmail.com"],             "CONTACT_DETAILS"),
        (["(+91)", "99958", "57314"],                    "CONTACT_DETAILS"),
        (["linkedin.com/in/theertha-krishna"],           "CONTACT_DETAILS"),
        (["Vellore", "Institute", "of", "Technology,"],  "INSTITUTION"),
        (["The", "School", "of", "the", "Good", "Shepherd,"], "INSTITUTION"),
        (["Deloitte"],                                   "INSTITUTION"),
        (["B.Tech.", "Electronics", "and", "Computer", "Engineering"], "DEGREE"),
        (["Data", "Science", "Intern"],                  "JOB_TITLE"),
        (["Machine", "Learning", "Intern"],              "JOB_TITLE"),
        (["Data", "Analysis", "Intern"],                 "JOB_TITLE"),
        (["Totally", "Baked"],                           "COMPANY"),
        (["Cresendos"],                                  "COMPANY"),
        (["UST", "Global"],                              "COMPANY"),
        ([SP],                                           "COMPANY"),
        (["Hugging", "Face", "Transformers."],           "TOOL_FRAMEWORK"),
        (["Google", "Vertex", "AI,"],                    "TOOL_FRAMEWORK"),
        (["Google", "Gemini"],                           "TOOL_FRAMEWORK"),
        (["Qdrant", "VectorDB,"],                        "TOOL_FRAMEWORK"),
        (["OpenAI", "API,"],                             "TOOL_FRAMEWORK"),
        (["OpenAI", "Whisper."],                         "TOOL_FRAMEWORK"),
        (["Whisper", "AI,"],                             "TOOL_FRAMEWORK"),
        (["Groq", "API,"],                               "TOOL_FRAMEWORK"),
        (["Vertex", "AI,"],                              "TOOL_FRAMEWORK"),
        (["Llama", "3,"],                                "TOOL_FRAMEWORK"),
        (["Llama", "3.1"],                               "TOOL_FRAMEWORK"),
        (["Scikit-learn,"],                              "TOOL_FRAMEWORK"),
        (["LangChain,"],                                 "TOOL_FRAMEWORK"),
        (["FastAPI,"],                                   "TOOL_FRAMEWORK"),
        (["FastAPI"],                                    "TOOL_FRAMEWORK"),
        (["PyTorch,"],                                   "TOOL_FRAMEWORK"),
        (["TensorFlow,"],                                "TOOL_FRAMEWORK"),
        (["Streamlit,"],                                 "TOOL_FRAMEWORK"),
        (["Docker,"],                                    "TOOL_FRAMEWORK"),
        (["DSPy,"],                                      "TOOL_FRAMEWORK"),
        (["DSPy"],                                       "TOOL_FRAMEWORK"),
        (["MCP,"],                                       "TOOL_FRAMEWORK"),
        (["MCP"],                                        "TOOL_FRAMEWORK"),
        (["nnU-Net"],                                    "TOOL_FRAMEWORK"),
        (["Guardrails"],                                 "TOOL_FRAMEWORK"),
        (["Ollama,"],                                    "TOOL_FRAMEWORK"),
        (["Gemini,"],                                    "TOOL_FRAMEWORK"),
        (["Gemini"],                                     "TOOL_FRAMEWORK"),
        (["BiLSTM,"],                                    "TOOL_FRAMEWORK"),
        (["BiLSTM"],                                     "TOOL_FRAMEWORK"),
        (["Django"],                                     "TOOL_FRAMEWORK"),
        (["Azure,"],                                     "TOOL_FRAMEWORK"),
        (["Pandas,"],                                    "TOOL_FRAMEWORK"),
        (["NumPy."],                                     "TOOL_FRAMEWORK"),
        (["Git,"],                                       "TOOL_FRAMEWORK"),
        (["XGBoost"],                                    "TOOL_FRAMEWORK"),
        (["Python,"],                                    "PROGRAMMING_LANGUAGE"),
        (["Python"],                                     "PROGRAMMING_LANGUAGE"),
    ],
}

def load_progress():
    if PROGRESS_LOG.exists():
        return json.loads(PROGRESS_LOG.read_text(encoding="utf-8"))
    return {"processed_files": []}

def save_progress(data):
    PROGRESS_LOG.write_text(json.dumps(data, indent=2), encoding="utf-8")

def main():
    progress = load_progress()
    done_set = set(progress.get("processed_files", []))

    candidates = [
        f for f in sorted(UNANNOTATED.glob("*.txt"))
        if f.name not in done_set
    ]
    batch = candidates[:5]

    if not batch:
        print("Nothing to process – all files already annotated.")
        return

    batch_entity_counts = defaultdict(int)
    processed_names = []

    with ANNOTATIONS_JSONL.open("a", encoding="utf-8") as out_fh:
        for txt_path in batch:
            fname = txt_path.name
            entities = ENTITIES.get(fname)
            if entities is None:
                print(f"  [SKIP] No entity definitions for {fname}")
                continue

            text   = txt_path.read_text(encoding="utf-8")
            tokens = tokenize(text)
            tags   = apply_entities(tokens, entities)

            record = {"tokens": tokens, "tags": tags}
            out_fh.write(json.dumps(record, ensure_ascii=False) + "\n")

            for label, cnt in count_entities(tags).items():
                batch_entity_counts[label] += cnt

            processed_names.append(fname)
            total_ents = sum(1 for t in tags if t.startswith("B-"))
            print(f"  [OK] {fname}  ({len(tokens)} tokens, {total_ents} entities)")

    # Update progress log
    progress["processed_files"] = sorted(done_set | set(processed_names))
    save_progress(progress)

    # Append run log line
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    entity_summary = ", ".join(
        f"{lbl}={cnt}" for lbl, cnt in sorted(batch_entity_counts.items())
    )
    log_line = (
        f"{ts} | files={','.join(processed_names)} | "
        f"entities_by_label=[{entity_summary}]\n"
    )
    with RUN_LOG.open("a", encoding="utf-8") as log_fh:
        log_fh.write(log_line)

    print(f"\nDone. {len(processed_names)} file(s) annotated.")
    print(f"Entity totals this run: {dict(sorted(batch_entity_counts.items()))}")

if __name__ == "__main__":
    main()
