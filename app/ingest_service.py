"""Put one file's chunks into pgvector. Used by the local script and the Lambda."""
from langchain_postgres import PGVectorStore

from core.ingest_lib import chunk_ids, load_file, split_documents


def ingest_file(store: PGVectorStore, path: str, source: str) -> int:
    """Upsert every chunk of `path` under the name `source`, then drop leftovers
    from an older, longer version of the same file. Safe to run repeatedly."""
    chunks = split_documents(load_file(path, source))
    store.add_documents(chunks, ids=chunk_ids(chunks))
    store.delete(filter={"$and": [{"source": source}, {"chunk_index": {"$gte": len(chunks)}}]})
    return len(chunks)
