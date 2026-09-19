"""Local ingest: load every file in ./documents into pgvector (rag.chunks).

Safe to re-run: each file's chunks are upserted by deterministic ID, then any
leftover chunks from an older, longer version of the file are deleted.
"""
import os

from dotenv import load_dotenv

load_dotenv()

from app.embeddings import TEIEmbeddings
from app.vectorstore import ensure_table, get_engine, get_vectorstore
from core.ingest_lib import chunk_ids, is_supported, load_file, split_documents

DATA_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "documents")


def ingest_file(store, path: str, source: str) -> int:
    chunks = split_documents(load_file(path, source))
    store.add_documents(chunks, ids=chunk_ids(chunks))
    # Prune chunks left over from a previous, longer version of this file.
    store.delete(filter={"$and": [{"source": source}, {"chunk_index": {"$gte": len(chunks)}}]})
    return len(chunks)


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
