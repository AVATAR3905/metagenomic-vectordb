import os
import csv
import chromadb
from chromadb.utils import embedding_functions
from docx import Document
from PyPDF2 import PdfReader

DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(DIR, "data")
DB_DIR = os.path.join(DIR, "chroma_db")

COMMON_COLUMNS = [
    "run_accession", "study_accession", "study_title",
    "experiment_accession", "experiment_title", "experiment_desc",
    "organism_name", "library_strategy", "library_layout",
    "sample_accession", "sample_title", "bioproject",
    "instrument", "run_total_bases", "host", "isolation_source",
    "geo_loc_name", "lat_lon",
    "Environment_Broad_Scale", "Specific_Environment", "Broader Category"
]


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
        for page in reader.pages[:20]:
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
            reader = csv.DictReader(f)
            for row in reader:
                rows.append(row)
    except Exception:
        pass
    return rows


def row_to_text(row):
    parts = []
    for col in COMMON_COLUMNS:
        val = row.get(col, "").strip()
        if val and val.lower() != "not applicable":
            parts.append(f"{col}: {val}")
    for col, val in row.items():
        if col not in COMMON_COLUMNS and val and val.strip() and val.strip().lower() != "not applicable":
            parts.append(f"{col}: {val.strip()}")
    return "; ".join(parts)


def build_study_text(study_accession, study_title, csv_rows, analysis_text, paper_texts):
    parts = []
    parts.append(f"Study accession: {study_accession}")
    if study_title:
        parts.append(f"Study title: {study_title}")
    parts.append(f"Number of sequencing runs: {len(csv_rows)}")
    organisms = set()
    instruments = set()
    locations = set()
    categories = set()
    for row in csv_rows:
        org = row.get("organism_name", "").strip()
        if org and org.lower() != "not applicable":
            organisms.add(org)
        inst = row.get("instrument", "").strip()
        if inst and inst.lower() != "not applicable":
            instruments.add(inst)
        loc = row.get("geo_loc_name", "").strip()
        if loc and loc.lower() != "not applicable":
            locations.add(loc)
        cat = row.get("Broader Category", "").strip()
        if cat:
            categories.add(cat)
    if organisms:
        parts.append(f"Organisms: {', '.join(organisms)}")
    if instruments:
        parts.append(f"Instruments: {', '.join(instruments)}")
    if locations:
        parts.append(f"Locations: {', '.join(locations)}")
    if categories:
        parts.append(f"Environment categories: {', '.join(categories)}")
    if analysis_text:
        parts.append(f"Analysis plan: {analysis_text[:2000]}")
    if paper_texts:
        combined = " ".join(paper_texts)[:3000]
        parts.append(f"Research papers: {combined}")
    return "\n".join(parts)


def ingest():
    ef = embedding_functions.DefaultEmbeddingFunction()
    client = chromadb.PersistentClient(path=DB_DIR)

    for name in ["studies", "runs", "papers"]:
        try:
            client.delete_collection(name)
        except Exception:
            pass

    studies_col = client.create_collection("studies", metadata={"hnsw:space": "cosine"}, embedding_function=ef)
    runs_col = client.create_collection("runs", metadata={"hnsw:space": "cosine"}, embedding_function=ef)
    papers_col = client.create_collection("papers", metadata={"hnsw:space": "cosine"}, embedding_function=ef)

    study_ids, study_docs, study_metas = [], [], []
    run_ids, run_docs, run_metas = [], [], []
    paper_ids, paper_docs, paper_metas = [], [], []

    dirs = [d for d in os.listdir(DATA_DIR) if os.path.isdir(os.path.join(DATA_DIR, d))]

    for dirname in sorted(dirs):
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
                paper_ids.append(f"{accession}_{pf}")
                paper_docs.append(txt[:5000])
                paper_metas.append({"accession": accession, "filename": pf, "study_title": study_title or accession})

        study_text = build_study_text(accession, study_title, csv_rows, analysis_text, paper_texts)
        study_ids.append(accession)
        study_docs.append(study_text)
        study_metas.append({
            "accession": accession,
            "study_title": study_title or accession,
            "n_runs": len(csv_rows),
            "n_papers": len([f for f in os.listdir(dirpath) if f.endswith(".pdf")]),
            "has_analysis_plan": bool(analysis_text)
        })

        for i, row in enumerate(csv_rows):
            run_acc = row.get("run_accession", f"{accession}_run_{i}") or f"{accession}_run_{i}"
            run_text = row_to_text(row)
            if run_text:
                run_ids.append(run_acc)
                run_docs.append(run_text)
                run_metas.append({
                    "accession": accession,
                    "run_accession": run_acc,
                    "study_title": study_title or accession,
                    "organism": row.get("organism_name", ""),
                    "instrument": row.get("instrument", ""),
                    "location": row.get("geo_loc_name", ""),
                    "category": row.get("Broader Category", ""),
                    "layout": row.get("library_layout", "")
                })

        print(f"  {accession}: {len(csv_rows)} runs, {len([f for f in os.listdir(dirpath) if f.endswith('.pdf')])} papers")

    print(f"\nEmbedding {len(study_ids)} studies...")
    studies_col.add(ids=study_ids, documents=study_docs, metadatas=study_metas)

    batch_size = 100
    if run_ids:
        print(f"Embedding {len(run_ids)} runs...")
        for i in range(0, len(run_ids), batch_size):
            end = min(i + batch_size, len(run_ids))
            runs_col.add(ids=run_ids[i:end], documents=run_docs[i:end], metadatas=run_metas[i:end])
            print(f"    Runs {i}-{end}")

    if paper_ids:
        print(f"Embedding {len(paper_ids)} papers...")
        for i in range(0, len(paper_ids), batch_size):
            end = min(i + batch_size, len(paper_ids))
            papers_col.add(ids=paper_ids[i:end], documents=paper_docs[i:end], metadatas=paper_metas[i:end])

    print(f"\nDone! Studies: {studies_col.count()}, Runs: {runs_col.count()}, Papers: {papers_col.count()}")


if __name__ == "__main__":
    ingest()
