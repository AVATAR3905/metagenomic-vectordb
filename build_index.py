import os
import csv
import pickle
import json
from docx import Document
from PyPDF2 import PdfReader
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(DIR, "data")
INDEX_DIR = os.path.join(DIR, "search_index")


def read_docx(path):
    try:
        doc = Document(path)
        return "\n".join(p.text for p in doc.paragraphs if p.text.strip())
    except Exception:
        return ""


def read_pdf(path):
    try:
        reader = PdfReader(path)
        texts = []
        for page in reader.pages[:15]:
            t = page.extract_text()
            if t:
                texts.append(t)
        return "\n".join(texts)
    except Exception:
        return ""


def read_csv_metadata(path):
    rows = []
    try:
        with open(path, "r", encoding="utf-8-sig") as f:
            for row in csv.DictReader(f):
                rows.append(row)
    except Exception:
        pass
    return rows


COMMON_COLUMNS = [
    "run_accession", "study_accession", "study_title",
    "experiment_accession", "experiment_title", "experiment_desc",
    "organism_name", "library_strategy", "library_layout",
    "sample_accession", "sample_title", "bioproject",
    "instrument", "run_total_bases", "host", "isolation_source",
    "geo_loc_name", "lat_lon",
    "Environment_Broad_Scale", "Specific_Environment", "Broader Category"
]


def row_to_text(row):
    parts = []
    for col in COMMON_COLUMNS:
        val = row.get(col, "").strip()
        if val and val.lower() != "not applicable":
            parts.append(f"{col}: {val}")
    for col, val in row.items():
        if col not in COMMON_COLUMNS and val and val.strip() and val.strip().lower() != "not applicable":
            parts.append(f"{col}: {val.strip()}")
    return " ".join(parts)


def build_study_text(accession, title, csv_rows, analysis_text, paper_texts):
    parts = [f"Study accession: {accession}"]
    if title:
        parts.append(f"Study title: {title}")
    parts.append(f"Sequencing runs: {len(csv_rows)}")
    for field in ["organism_name", "instrument", "geo_loc_name", "Broader Category"]:
        vals = set()
        for row in csv_rows:
            v = row.get(field, "").strip()
            if v and v.lower() != "not applicable":
                vals.add(v)
        if vals:
            label = {"organism_name": "Organisms", "instrument": "Instruments", "geo_loc_name": "Locations", "Broader Category": "Categories"}[field]
            parts.append(f"{label}: {', '.join(vals)}")
    if analysis_text:
        parts.append(f"Analysis plan: {analysis_text[:2000]}")
    if paper_texts:
        parts.append(f"Papers: {' '.join(paper_texts)[:3000]}")
    return "\n".join(parts)


def build_index():
    os.makedirs(INDEX_DIR, exist_ok=True)

    studies = []
    runs = []
    papers = []

    dirs = [d for d in sorted(os.listdir(DATA_DIR)) if os.path.isdir(os.path.join(DATA_DIR, d))]

    for dirname in dirs:
        dirpath = os.path.join(DATA_DIR, dirname)
        accession = dirname

        csv_rows = []
        for cf in [f for f in os.listdir(dirpath) if f.endswith("_curated.csv")]:
            csv_rows.extend(read_csv_metadata(os.path.join(dirpath, cf)))

        study_title = csv_rows[0].get("study_title", "") if csv_rows else ""

        analysis_text = ""
        for df in [f for f in os.listdir(dirpath) if f.endswith(".docx")]:
            analysis_text += read_docx(os.path.join(dirpath, df)) + "\n"

        paper_texts = []
        for pf in [f for f in os.listdir(dirpath) if f.endswith(".pdf")]:
            txt = read_pdf(os.path.join(dirpath, pf))
            if txt:
                paper_texts.append(txt)
                papers.append({
                    "id": f"{accession}_{pf}",
                    "accession": accession,
                    "filename": pf,
                    "study_title": study_title or accession,
                    "text": txt[:5000]
                })

        study_text = build_study_text(accession, study_title, csv_rows, analysis_text, paper_texts)
        pdf_count = len([f for f in os.listdir(dirpath) if f.endswith(".pdf")])
        studies.append({
            "id": accession,
            "accession": accession,
            "study_title": study_title or accession,
            "n_runs": len(csv_rows),
            "n_papers": pdf_count,
            "has_analysis_plan": bool(analysis_text),
            "text": study_text
        })

        for i, row in enumerate(csv_rows):
            run_acc = row.get("run_accession", f"{accession}_run_{i}") or f"{accession}_run_{i}"
            run_text = row_to_text(row)
            if run_text:
                runs.append({
                    "id": run_acc,
                    "accession": accession,
                    "run_accession": run_acc,
                    "study_title": study_title or accession,
                    "organism": row.get("organism_name", ""),
                    "instrument": row.get("instrument", ""),
                    "location": row.get("geo_loc_name", ""),
                    "category": row.get("Broader Category", ""),
                    "layout": row.get("library_layout", ""),
                    "text": run_text
                })

        print(f"  {accession}: {len(csv_rows)} runs, {pdf_count} papers")

    collections = {
        "studies": studies,
        "runs": runs,
        "papers": papers
    }

    for name, items in collections.items():
        texts = [item["text"] for item in items]
        if not texts:
            continue
        vectorizer = TfidfVectorizer(max_features=10000, stop_words="english", ngram_range=(1, 2))
        tfidf_matrix = vectorizer.fit_transform(texts)
        with open(os.path.join(INDEX_DIR, f"{name}_vectorizer.pkl"), "wb") as f:
            pickle.dump(vectorizer, f)
        with open(os.path.join(INDEX_DIR, f"{name}_matrix.pkl"), "wb") as f:
            pickle.dump(tfidf_matrix, f)
        with open(os.path.join(INDEX_DIR, f"{name}_items.pkl"), "wb") as f:
            pickle.dump(items, f)
        print(f"  Indexed {name}: {len(items)} items, {tfidf_matrix.shape[1]} features")

    print(f"\nDone! Index saved to {INDEX_DIR}")


if __name__ == "__main__":
    build_index()
