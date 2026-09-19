"""Loading and chunking shared by the local ingest script and the ingest Lambda.

Pure functions: no database or network access, so both callers can reuse them.
"""
import os
import uuid

from langchain_community.document_loaders import Docx2txtLoader, PyPDFLoader, TextLoader
from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter

CHUNK_SIZE = 1000
CHUNK_OVERLAP = 200

# Fixed namespace so the same (source, index) always produces the same UUID.
CHUNK_NAMESPACE = uuid.UUID("6f1d3c2a-8b4e-4f0a-9c7d-2e5b1a9f3c10")

LOADERS = {
    ".pdf": PyPDFLoader,
    ".docx": Docx2txtLoader,
    ".txt": lambda path: TextLoader(path, encoding="utf-8"),
}


def is_supported(filename: str) -> bool:
    return os.path.splitext(filename)[1].lower() in LOADERS


def load_file(path: str, source: str) -> list[Document]:
    """Load one file. `source` is the stable name stored with each chunk
    (the S3 key in AWS, the relative path locally), not the temp path on disk."""
    ext = os.path.splitext(path)[1].lower()
    if ext not in LOADERS:
        raise ValueError(f"Unsupported file type: {ext}")

    docs = LOADERS[ext](path).load()
    for doc in docs:
        doc.metadata["source"] = source
    return docs


def split_documents(docs: list[Document]) -> list[Document]:
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=CHUNK_SIZE,
        chunk_overlap=CHUNK_OVERLAP,
    )
    chunks = splitter.split_documents(docs)
    for i, chunk in enumerate(chunks):
        chunk.metadata["chunk_index"] = i
    return chunks


def chunk_ids(chunks: list[Document]) -> list[str]:
    """Deterministic IDs: re-ingesting the same file yields the same IDs."""
    return [
        str(uuid.uuid5(CHUNK_NAMESPACE, f"{c.metadata['source']}#{c.metadata['chunk_index']}"))
        for c in chunks
    ]
