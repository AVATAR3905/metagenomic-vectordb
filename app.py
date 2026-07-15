import os
import chromadb
from chromadb.utils import embedding_functions
from flask import Flask, render_template, request, jsonify

app = Flask(__name__)

DIR = os.path.dirname(os.path.abspath(__file__))
DB_DIR = os.path.join(DIR, "chroma_db")

ef = embedding_functions.DefaultEmbeddingFunction()
client = chromadb.PersistentClient(path=DB_DIR)
studies_col = client.get_collection("studies", embedding_function=ef)
runs_col = client.get_collection("runs", embedding_function=ef)
papers_col = client.get_collection("papers", embedding_function=ef)


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/stats")
def api_stats():
    return jsonify({"studies": studies_col.count(), "runs": runs_col.count(), "papers": papers_col.count()})


@app.route("/api/search", methods=["POST"])
def api_search():
    data = request.json
    query = data.get("query", "")
    collection = data.get("collection", "studies")
    n = data.get("n", 10)
    if not query:
        return jsonify({"error": "Empty query"}), 400
    col = {"studies": studies_col, "runs": runs_col, "papers": papers_col}.get(collection, studies_col)
    results = col.query(query_texts=[query], n_results=n)
    items = []
    for i in range(len(results["ids"][0])):
        meta = results["metadatas"][0][i] if results["metadatas"] else {}
        dist = results["distances"][0][i] if results["distances"] else 0
        score = round(1 - dist, 4)
        doc = results["documents"][0][i] if results["documents"] else ""
        items.append({"id": results["ids"][0][i], "metadata": meta, "score": score, "preview": doc[:500]})
    return jsonify({"results": items, "total": len(items)})


@app.route("/api/study/<accession>")
def api_study(accession):
    results = studies_col.get(ids=[accession], include=["documents", "metadatas"])
    if not results["ids"]:
        return jsonify({"error": "Study not found"}), 404
    doc = results["documents"][0] if results["documents"] else ""
    meta = results["metadatas"][0] if results["metadatas"] else {}
    run_results = runs_col.get(where={"accession": accession}, include=["metadatas"])
    runs = [{"id": run_results["ids"][i], "metadata": run_results["metadatas"][i]} for i in range(len(run_results["ids"]))]
    paper_results = papers_col.get(where={"accession": accession}, include=["metadatas"])
    papers = [{"id": paper_results["ids"][i], "filename": paper_results["metadatas"][i].get("filename", "")} for i in range(len(paper_results["ids"]))]
    return jsonify({"accession": accession, "document": doc, "metadata": meta, "runs": runs, "papers": papers})


@app.route("/api/all_studies")
def api_all_studies():
    results = studies_col.get(include=["metadatas"])
    studies = [{"id": results["ids"][i], "metadata": results["metadatas"][i]} for i in range(len(results["ids"]))]
    return jsonify({"studies": studies})


@app.route("/api/filters")
def api_filters():
    runs = runs_col.get(include=["metadatas"])
    organisms, instruments, locations, categories = set(), set(), set(), set()
    for meta in runs["metadatas"]:
        if meta.get("organism"): organisms.add(meta["organism"])
        if meta.get("instrument"): instruments.add(meta["instrument"])
        if meta.get("location"): locations.add(meta["location"])
        if meta.get("category"): categories.add(meta["category"])
    return jsonify({"organisms": sorted(organisms), "instruments": sorted(instruments), "locations": sorted(locations), "categories": sorted(categories)})


@app.route("/api/filtered_runs", methods=["POST"])
def api_filtered_runs():
    data = request.json
    where_clauses = []
    for key in ["organism", "instrument", "location", "category"]:
        if data.get(key):
            where_clauses.append({key: data[key]})
    kwargs = {"include": ["metadatas"]}
    if len(where_clauses) == 1:
        kwargs["where"] = where_clauses[0]
    elif len(where_clauses) > 1:
        kwargs["where"] = {"$and": where_clauses}
    results = runs_col.get(**kwargs)
    items = [{"id": results["ids"][i], "metadata": results["metadatas"][i]} for i in range(len(results["ids"]))]
    return jsonify({"runs": items, "total": len(items)})


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    host = "0.0.0.0"
    print(f"Server running on http://{host}:{port}")
    app.run(debug=False, host=host, port=port)
