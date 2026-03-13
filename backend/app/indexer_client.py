import logging
from pathlib import Path
from typing import List

import httpx

from .config import INDEXER_HOST

logger = logging.getLogger(__name__)

_client: httpx.Client | None = None


def init(client: httpx.Client) -> None:
    global _client
    _client = client


def ingest_pdfs(pdf_paths: List[Path]) -> dict:
    """Upload PDFs to the indexer for text + image indexing."""
    files = []
    for p in pdf_paths:
        files.append(("files", (p.name, p.open("rb"), "application/pdf")))
    try:
        resp = _client.post(
            f"{INDEXER_HOST}/ingest",
            files=files,
            timeout=600.0,
        )
        resp.raise_for_status()
        return resp.json()
    finally:
        for _, (_, f, _) in files:
            f.close()


def search_text(query: str) -> List[dict]:
    """Search for reranked text chunks via the indexer."""
    resp = _client.post(
        f"{INDEXER_HOST}/search/text",
        json={"query": query},
    )
    resp.raise_for_status()
    return resp.json().get("text_results", [])


def search_images(query: str, top_k: int) -> List[dict]:
    """Search for CLIP-ranked images via the indexer."""
    resp = _client.post(
        f"{INDEXER_HOST}/search/images",
        json={"query": query, "top_k": top_k},
    )
    resp.raise_for_status()
    return resp.json().get("image_results", [])


def get_status() -> dict:
    """Get indexer status."""
    resp = _client.get(f"{INDEXER_HOST}/status")
    resp.raise_for_status()
    return resp.json()
