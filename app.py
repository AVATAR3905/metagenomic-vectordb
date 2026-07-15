import os
import pickle
import numpy as np
from flask import Flask, render_template, request, jsonify

app = Flask(__name__)

DIR = os.path.dirname(os.path.abspath(__file__))
INDEX_DIR = os.path.join(DIR, "search_index")

collections = {}
for name in ["studies", "runs", "papers"]:
    with open(os.path.join(INDEX_DIR, f"{name}_vectorizer.pkl"), "rb") as f:
        vectorizer = pickle.load(f)
    with open(os.path.join(INDEX_DIR, f"{name}_matrix.pkl"), "rb") as f:
        matrix = pickle.load(f)
    with open(os.path.join(INDEX_DIR, f"{name}_items.pkl"), "rb") as f:
        items = pickle.load(f)
    collections[name] = {"vectorizer": vectorizer, "matrix": matrix, "items": items}


def search(collection_name, query, n=10):
    col = collections[collection_name]
    query_vec = col["vectorizer"].transform([query])
    scores = cosine_similarity(query_vec, col["matrix"]).flatten()
    top_indices = scores.argsort()[::-1][:n]
    results = []
    for idx in top_indices:
        if scores[idx] > 0:
            item = dict(col["items"][idx])
            item.pop("text", None)
            results.append({"id": item["id"], "metadata": item, "score": round(float(scores[idx]), 4)})
    return results


def cosine_similarity(a, b):
    return (a * b.T).toarray() if hasattr(a, 'toarray') else np.dot(a, b.T)


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/stats")
def api_stats():
    return jsonify({
        "studies": len(collections["studies"]["items"]),
        "runs": len(collections["runs"]["items"]),
        "papers": len(collections["papers"]["items"])
    })


@app.route("/api/search", methods=["POST"])
def api_search():
    data = request.json
    query = data.get("query", "")
    collection = data.get("collection", "studies")
    n = data.get("n", 10)
    if not query:
        return jsonify({"error": "Empty query"}), 400
    if collection not in collections:
        return jsonify({"error": "Invalid collection"}), 400
    results = search(collection, query, n)
    return jsonify({"results": results, "total": len(results)})


@app.route("/api/study/<accession>")
def api_study(accession):
    study = None
    for item in collections["studies"]["items"]:
        if item["id"] == accession:
            study = item
            break
    if not study:
        return jsonify({"error": "Study not found"}), 404

    runs = [r for r in collections["runs"]["items"] if r["accession"] == accession]
    papers = [p for p in collections["papers"]["items"] if p["accession"] == accession]
    full_doc = study.get("text", "")
    return jsonify({
        "accession": accession,
        "document": full_doc,
        "metadata": {k: v for k, v in study.items() if k != "text"},
        "runs": [{k: v for k, v in r.items() if k != "text"} for r in runs],
        "papers": [{"id": p["id"], "filename": p["filename"]} for p in papers]
    })


@app.route("/api/all_studies")
def api_all_studies():
    return jsonify({
        "studies": [{"id": item["id"], "metadata": {k: v for k, v in item.items() if k != "text"}} for item in collections["studies"]["items"]]
    })


@app.route("/api/filters")
def api_filters():
    runs = collections["runs"]["items"]
    organisms, instruments, locations, categories = set(), set(), set(), set()
    for r in runs:
        if r.get("organism"): organisms.add(r["organism"])
        if r.get("instrument"): instruments.add(r["instrument"])
        if r.get("location"): locations.add(r["location"])
        if r.get("category"): categories.add(r["category"])
    return jsonify({"organisms": sorted(organisms), "instruments": sorted(instruments), "locations": sorted(locations), "categories": sorted(categories)})


@app.route("/api/filtered_runs", methods=["POST"])
def api_filtered_runs():
    data = request.json
    filtered = collections["runs"]["items"]
    for key in ["organism", "instrument", "location", "category"]:
        if data.get(key):
            filtered = [r for r in filtered if r.get(key) == data[key]]
    return jsonify({"runs": [{k: v for k, v in r.items() if k != "text"} for r in filtered], "total": len(filtered)})
