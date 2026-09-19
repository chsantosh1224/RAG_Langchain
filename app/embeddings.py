"""Embeddings served by TEI (Text Embeddings Inference) running Qwen3-Embedding-0.6B.

Ingest and query both use this module, so documents and questions are always
embedded by the same model the same way.
"""
import os

import httpx
from langchain_core.embeddings import Embeddings

TEI_URL = os.getenv("TEI_URL", "http://127.0.0.1:8080")
EMBEDDING_DIM = 1024

# Qwen3 is instruction-aware: questions get a task prefix, documents do not.
QUERY_INSTRUCTION = "Given a question, retrieve passages from company policy documents that answer it"

# Small batches keep each CPU request short (TEI's own limit is 32 inputs).
BATCH_SIZE = 8


class TEIEmbeddings(Embeddings):
    def __init__(self, base_url: str = TEI_URL, timeout: float = 180.0):
        self._client = httpx.Client(base_url=base_url, timeout=timeout)

    def _embed(self, texts: list[str]) -> list[list[float]]:
        vectors = []
        for i in range(0, len(texts), BATCH_SIZE):
            resp = self._client.post("/embed", json={"inputs": texts[i:i + BATCH_SIZE]})
            resp.raise_for_status()
            vectors.extend(resp.json())
        return vectors

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return self._embed(texts)

    def embed_query(self, text: str) -> list[float]:
        return self._embed([f"Instruct: {QUERY_INSTRUCTION}\nQuery:{text}"])[0]
