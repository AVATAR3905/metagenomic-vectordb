import os
import chromadb
from flask import Flask, render_template, request, jsonify
from sentence_transformers import SentenceTransformer

app = Flask(__name__)

DB_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "chroma_db")
model = None
client = None
studies_col = None
runs_col = None
papers_col = None


def init():
    global model, client, studies_col, runs_col, papers_col
    model = SentenceTransformer("all-MiniLM-L6-v2")
    client = chromadb.PersistentClient(path=DB_DIR)
    studies_col = client.get_collection("studies")
    runs_col = client.get_collection("runs")
    papers_col = client.get_collection("papers")


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/stats")
def api_stats():
    return jsonify({
        "studies": studies_col.count(),
        "runs": runs_col.count(),
        "papers": papers_col.count()
    })


@app.route("/api/search", methods=["POST"])
def api_search():
    data = request.json
    query = data.get("query", "")
    collection = data.get("collection", "studies")
    n = data.get("n", 10)

    if not query:
        return jsonify({"error": "Empty query"}), 400

    emb = model.encode([query]).tolist()
    col = {"studies": studies_col, "runs": runs_col, "papers": papers_col}.get(collection, studies_col)
    results = col.query(query_embeddings=emb, n_results=n)

    items = []
    for i in range(len(results["ids"][0])):
        meta = results["metadatas"][0][i] if results["metadatas"] else {}
        dist = results["distances"][0][i] if results["distances"] else 0
        score = round(1 - dist, 4)
        doc = results["documents"][0][i] if results["documents"] else ""
        items.append({
            "id": results["ids"][0][i],
            "metadata": meta,
            "score": score,
            "preview": doc[:500]
        })

    return jsonify({"results": items, "total": len(items)})


@app.route("/api/study/<accession>")
def api_study(accession):
    results = studies_col.get(ids=[accession], include=["documents", "metadatas"])
    if not results["ids"]:
        return jsonify({"error": "Study not found"}), 404

    doc = results["documents"][0] if results["documents"] else ""
    meta = results["metadatas"][0] if results["metadatas"] else {}

    run_results = runs_col.get(
        where={"accession": accession},
        include=["documents", "metadatas"]
    )
    runs = []
    for i in range(len(run_results["ids"])):
        runs.append({
            "id": run_results["ids"][i],
            "metadata": run_results["metadatas"][i] if run_results["metadatas"] else {}
        })

    paper_results = papers_col.get(
        where={"accession": accession},
        include=["documents", "metadatas"]
    )
    papers = []
    for i in range(len(paper_results["ids"])):
        papers.append({
            "id": paper_results["ids"][i],
            "filename": paper_results["metadatas"][i].get("filename", "") if paper_results["metadatas"] else ""
        })

    return jsonify({
        "accession": accession,
        "document": doc,
        "metadata": meta,
        "runs": runs,
        "papers": papers
    })


@app.route("/api/all_studies")
def api_all_studies():
    results = studies_col.get(include=["metadatas"])
    studies = []
    for i in range(len(results["ids"])):
        studies.append({
            "id": results["ids"][i],
            "metadata": results["metadatas"][i] if results["metadatas"] else {}
        })
    return jsonify({"studies": studies})


@app.route("/api/filters")
def api_filters():
    runs = runs_col.get(include=["metadatas"])
    organisms = set()
    instruments = set()
    locations = set()
    categories = set()
    for meta in runs["metadatas"]:
        if meta.get("organism"):
            organisms.add(meta["organism"])
        if meta.get("instrument"):
            instruments.add(meta["instrument"])
        if meta.get("location"):
            locations.add(meta["location"])
        if meta.get("category"):
            categories.add(meta["category"])
    return jsonify({
        "organisms": sorted(organisms),
        "instruments": sorted(instruments),
        "locations": sorted(locations),
        "categories": sorted(categories)
    })


@app.route("/api/filtered_runs", methods=["POST"])
def api_filtered_runs():
    data = request.json
    where_clauses = []
    if data.get("organism"):
        where_clauses.append({"organism": data["organism"]})
    if data.get("instrument"):
        where_clauses.append({"instrument": data["instrument"]})
    if data.get("location"):
        where_clauses.append({"location": data["location"]})
    if data.get("category"):
        where_clauses.append({"category": data["category"]})

    kwargs = {"include": ["metadatas"]}
    if len(where_clauses) == 1:
        kwargs["where"] = where_clauses[0]
    elif len(where_clauses) > 1:
        kwargs["where"] = {"$and": where_clauses}

    results = runs_col.get(**kwargs)
    items = []
    for i in range(len(results["ids"])):
        items.append({
            "id": results["ids"][i],
            "metadata": results["metadatas"][i] if results["metadatas"] else {}
        })
    return jsonify({"runs": items, "total": len(items)})


if __name__ == "__main__":
    init()
    print("Server starting...")
    print("Open http://localhost:5000 in your browser")
    app.run(debug=True, port=5000)
