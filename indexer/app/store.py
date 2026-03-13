import logging
from typing import List, Optional

import chromadb

from .config import CHROMA_DIR, IMAGE_COLLECTION, TEXT_COLLECTION

logger = logging.getLogger(__name__)

_client: Optional[chromadb.PersistentClient] = None
_image_collection: Optional[chromadb.Collection] = None
_text_collection: Optional[chromadb.Collection] = None


def init() -> None:
    global _client, _image_collection, _text_collection
    _client = chromadb.PersistentClient(path=CHROMA_DIR)
    _image_collection = _client.get_or_create_collection(
        name=IMAGE_COLLECTION,
        metadata={"hnsw:space": "cosine"},
    )
    _text_collection = _client.get_or_create_collection(
        name=TEXT_COLLECTION,
        metadata={"hnsw:space": "cosine"},
    )
    logger.info(
        f"ChromaDB ready at {CHROMA_DIR} — "
        f"text={_text_collection.count()}, images={_image_collection.count()}"
    )


# ── Image collection ──────────────────────────────────────────────

def upsert_images(
    ids: List[str],
    embeddings: List[List[float]],
    metadatas: List[dict],
) -> None:
    BATCH = 64
    for i in range(0, len(ids), BATCH):
        _image_collection.upsert(
            ids=ids[i : i + BATCH],
            embeddings=embeddings[i : i + BATCH],
            metadatas=metadatas[i : i + BATCH],
        )
    logger.info(f"Upserted {len(ids)} image embeddings")


def search_images(query_embedding: List[float], n_results: int) -> dict:
    count = _image_collection.count()
    if count == 0:
        return {"ids": [[]], "metadatas": [[]], "distances": [[]]}
    n = min(n_results, count)
    return _image_collection.query(
        query_embeddings=[query_embedding],
        n_results=n,
        include=["metadatas", "distances"],
    )


def clear_images() -> None:
    existing = _image_collection.get()["ids"]
    if existing:
        _image_collection.delete(ids=existing)
        logger.info(f"Cleared {len(existing)} image embeddings")


def image_count() -> int:
    return _image_collection.count()


# ── Text collection ───────────────────────────────────────────────

def upsert_text(
    ids: List[str],
    documents: List[str],
    embeddings: List[List[float]],
    metadatas: List[dict],
) -> None:
    BATCH = 64
    for i in range(0, len(ids), BATCH):
        _text_collection.upsert(
            ids=ids[i : i + BATCH],
            documents=documents[i : i + BATCH],
            embeddings=embeddings[i : i + BATCH],
            metadatas=metadatas[i : i + BATCH],
        )
    logger.info(f"Upserted {len(ids)} text chunks")


def search_text(query_embedding: List[float], n_results: int) -> dict:
    count = _text_collection.count()
    if count == 0:
        return {"ids": [[]], "documents": [[]], "metadatas": [[]], "distances": [[]]}
    n = min(n_results, count)
    return _text_collection.query(
        query_embeddings=[query_embedding],
        n_results=n,
        include=["documents", "metadatas", "distances"],
    )


def clear_text() -> None:
    existing = _text_collection.get()["ids"]
    if existing:
        _text_collection.delete(ids=existing)
        logger.info(f"Cleared {len(existing)} text chunks")


def text_count() -> int:
    return _text_collection.count()
