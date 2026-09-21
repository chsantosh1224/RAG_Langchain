"""Local ingest: load every file in ./documents into pgvector (rag.chunks).

Safe to re-run: each file's chunks are upserted by deterministic ID, then any
leftover chunks from an older, longer version of the file are deleted.
"""
import os

from dotenv import load_dotenv

load_dotenv()

from app.embeddings import TEIEmbeddings
from app.ingest_service import ingest_file
from app.vectorstore import ensure_table, get_engine, get_vectorstore
from core.ingest_lib import is_supported

DATA_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "documents")


def main():
    engine = get_engine()
    ensure_table(engine)
    store = get_vectorstore(engine, TEIEmbeddings())

    files = sorted(f for f in os.listdir(DATA_PATH) if is_supported(f))
    if not files:
        print(f"No supported files in {DATA_PATH}")
        return

    for name in files:
        count = ingest_file(store, os.path.join(DATA_PATH, name), source=name)
        print(f"{name}: {count} chunks")


if __name__ == "__main__":
    main()
