import subprocess
import sys
import os

DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(DIR, "data")
DB_DIR = os.path.join(DIR, "chroma_db")

REQUIRED = ["chromadb", "flask", "sentence_transformers", "docx", "PyPDF2"]
IMPORT_MAP = {
    "chromadb": "chromadb",
    "flask": "flask",
    "sentence_transformers": "sentence-transformers",
    "docx": "python-docx",
    "PyPDF2": "PyPDF2",
}


def install_missing():
    missing = []
    for mod in REQUIRED:
        try:
            __import__(mod)
        except ImportError:
            missing.append(IMPORT_MAP[mod])
    if missing:
        print(f"Installing missing packages: {', '.join(missing)}")
        subprocess.check_call(
            [sys.executable, "-m", "pip", "install", "--quiet"] + missing
        )
        print("Packages installed.\n")


def build_db():
    if os.path.isdir(DB_DIR) and os.listdir(DB_DIR):
        print("Database already exists, skipping ingestion.")
        return
    print("Building vector database (first run only)...")
    subprocess.check_call([sys.executable, os.path.join(DIR, "ingest.py")])
    print()


def main():
    print("=" * 50)
    print("  Metagenomic Vector DB Dashboard")
    print("=" * 50)

    print("\n[1/3] Checking dependencies...")
    install_missing()

    print("[2/3] Preparing database...")
    build_db()

    print("[3/3] Starting server...")
    print("-" * 50)

    os.chdir(DIR)
    from app import init, app
    init()

    port = int(os.environ.get("PORT", 5000))
    host = "0.0.0.0" if os.environ.get("RENDER") else "127.0.0.1"
    print(f"  Listening on {host}:{port}")
    print("-" * 50)

    app.run(debug=False, host=host, port=port)


if __name__ == "__main__":
    main()
