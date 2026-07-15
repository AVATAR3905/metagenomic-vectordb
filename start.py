import os
import sys

DIR = os.path.dirname(os.path.abspath(__file__))


def main():
    print("=" * 50)
    print("  Metagenomic Vector DB Dashboard")
    print("=" * 50)

    db_path = os.path.join(DIR, "chroma_db")
    if not os.path.isdir(db_path) or not os.listdir(db_path):
        print("\nBuilding vector database (first run)...")
        sys.path.insert(0, DIR)
        from ingest import ingest
        ingest()
        print()

    os.chdir(DIR)
    from app import init, app
    init()

    port = int(os.environ.get("PORT", 5000))
    host = "0.0.0.0"
    print(f"\nServer running on http://{host}:{port}")
    print("-" * 50)

    from gunicorn.app.base import BaseApplication

    class StandaloneApplication(BaseApplication):
        def __init__(self, app, options=None):
            self.options = options or {}
            self.application = app
            super().__init__()
        def load_config(self):
            for k, v in self.options.items():
                if k in self.cfg.settings and v is not None:
                    self.cfg.set(k.lower(), v)
        def load(self):
            return self.application

    options = {
        "bind": f"{host}:{port}",
        "workers": 1,
        "timeout": 120,
    }
    StandaloneApplication(app, options).run()


if __name__ == "__main__":
    main()
