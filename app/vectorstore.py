"""pgvector store: table rag.chunks with an HNSW index, shared by ingest and query."""
import os

from langchain_core.embeddings import Embeddings
from langchain_postgres import Column, PGEngine, PGVectorStore
from langchain_postgres.v2.indexes import HNSWIndex
from sqlalchemy.exc import ProgrammingError

from app.embeddings import EMBEDDING_DIM

# 127.0.0.1, not localhost: Docker publishes on IPv4 only, and "localhost" tries IPv6 first and hangs.
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://postgres:postgres@127.0.0.1:5432/rag")
SCHEMA = "rag"
TABLE = "chunks"

# Real columns instead of JSON metadata, so we can filter and delete by source.
METADATA_COLUMNS = [
    Column("source", "TEXT", nullable=False),
    Column("page", "INTEGER"),
    Column("chunk_index", "INTEGER", nullable=False),
]


def _is_local(url: str) -> bool:
    return "@localhost" in url or "@127.0.0.1" in url


def get_engine() -> PGEngine:
    # PGEngine is async; asyncpg also works with Windows' default event loop.
    # asyncpg spells it "ssl", psycopg spells it "sslmode"; RDS requires TLS.
    url = DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://", 1).replace("sslmode=", "ssl=")
    if "ssl=" not in url and not _is_local(url):
        url += ("&" if "?" in url else "?") + "ssl=require"
    return PGEngine.from_connection_string(url)


def ensure_table(engine: PGEngine) -> None:
    """Create rag.chunks and its HNSW index if they don't exist yet."""
    try:
        engine.init_vectorstore_table(
            table_name=TABLE,
            schema_name=SCHEMA,
            vector_size=EMBEDDING_DIM,
            metadata_columns=METADATA_COLUMNS,
        )
    except ProgrammingError as e:
        if "already exists" in str(e):
            return
        raise

    # Only reached when the table was just created.
    store = get_vectorstore(engine, embeddings=None)
    store.apply_vector_index(HNSWIndex())


def get_vectorstore(engine: PGEngine, embeddings: Embeddings) -> PGVectorStore:
    return PGVectorStore.create_sync(
        engine=engine,
        embedding_service=embeddings,
        table_name=TABLE,
        schema_name=SCHEMA,
        metadata_columns=[c.name for c in METADATA_COLUMNS],
    )
