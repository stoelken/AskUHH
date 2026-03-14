import logging
from typing import List

import httpx

from ..config import OLLAMA_HOST, EMBED_MODEL

logger = logging.getLogger(__name__)

_client: httpx.Client | None = None


def init(client: httpx.Client) -> None:
    global _client
    _client = client


def embed_texts(texts: List[str]) -> List[List[float]]:
    """Call Ollama /api/embed and return a list of vectors."""
    resp = _client.post(
        f"{OLLAMA_HOST}/api/embed",
        json={"model": EMBED_MODEL, "input": texts},
    )
    resp.raise_for_status()
    return resp.json()["embeddings"]


def embed_query(question: str) -> List[float]:
    """Embed a single query via Ollama."""
    return embed_texts([question])[0]
