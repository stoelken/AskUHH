from typing import List

import httpx
from chromadb import EmbeddingFunction, Documents, Embeddings

from .config import OLLAMA_HOST, EMBED_MODEL


def _embed(texts: List[str]) -> List[List[float]]:
    """Call Ollama /api/embed and return a list of vectors."""
    with httpx.Client(timeout=60) as client:
        resp = client.post(
            f"{OLLAMA_HOST}/api/embed",
            json={"model": EMBED_MODEL, "input": texts},
        )
        resp.raise_for_status()
    return resp.json()["embeddings"]


class OllamaEmbeddingFunction(EmbeddingFunction):
    """ChromaDB embedding function backed by Ollama."""

    def __call__(self, input: Documents) -> Embeddings:
        return _embed(list(input))


def embed_query(question: str) -> List[float]:
    """Embed a single query via Ollama."""
    return _embed([question])[0]