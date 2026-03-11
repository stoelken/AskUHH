from typing import List

import httpx
from chromadb import EmbeddingFunction, Documents, Embeddings

from .config import OLLAMA_HOST, EMBED_MODEL

# Shared client – set once by main.lifespan(), used everywhere.
_client: httpx.Client | None = None


def init(client: httpx.Client) -> None:
    global _client
    _client = client


def _embed(texts: List[str]) -> List[List[float]]:
    """Call Ollama /api/embed and return a list of vectors."""
    resp = _client.post(
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