import logging
from typing import List, Optional

import chromadb

from ..config import CHROMA_DIR, TEXT_COLLECTION

logger = logging.getLogger(__name__)

_client: Optional[chromadb.PersistentClient] = None
_text_collection: Optional[chromadb.Collection] = None

_HNSW_META = {"hnsw:space": "cosine", "hnsw:search_ef": 100}


def init() -> None:
    global _client, _text_collection
    _client = chromadb.PersistentClient(path=CHROMA_DIR)
    _text_collection = _client.get_or_create_collection(
        name=TEXT_COLLECTION,
        metadata=_HNSW_META,
    )
    logger.info(f"ChromaDB ready at {CHROMA_DIR} — text={_text_collection.count()}")


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
    n = max(1, min(n_results, count))
    try:
        return _text_collection.query(
            query_embeddings=[query_embedding],
            n_results=n,
            include=["documents", "metadatas", "distances"],
        )
    except RuntimeError:
        logger.warning(f"HNSW query failed for text (count={count}), using get() fallback")
        return _get_all_fallback(_text_collection, query_embedding, n, include_documents=True)


def search_text_filtered(
    query_embedding: List[float],
    n_results: int,
    where: dict,
) -> dict:
    count = _text_collection.count()
    if count == 0:
        return {"ids": [[]], "documents": [[]], "metadatas": [[]], "distances": [[]]}
    n = max(1, min(n_results, count))
    try:
        return _text_collection.query(
            query_embeddings=[query_embedding],
            n_results=n,
            where=where,
            include=["documents", "metadatas", "distances"],
        )
    except Exception:
        logger.warning(f"Filtered text search failed (where={where}), returning empty")
        return {"ids": [[]], "documents": [[]], "metadatas": [[]], "distances": [[]]}


def clear_text() -> None:
    existing = _text_collection.get()["ids"]
    if existing:
        _text_collection.delete(ids=existing)
        logger.info(f"Cleared {len(existing)} text chunks")


def text_count() -> int:
    return _text_collection.count()


def _get_all_fallback(
    collection: chromadb.Collection,
    query_embedding: List[float],
    n: int,
    include_documents: bool,
) -> dict:
    include = ["metadatas", "embeddings"]
    if include_documents:
        include.append("documents")
    data = collection.get(include=include)
    if not data["ids"]:
        empty = {"ids": [[]], "metadatas": [[]], "distances": [[]]}
        if include_documents:
            empty["documents"] = [[]]
        return empty

    import numpy as np
    q = np.array(query_embedding, dtype=np.float32)
    q = q / (np.linalg.norm(q) + 1e-10)
    scored = []
    for i, emb in enumerate(data["embeddings"]):
        v = np.array(emb, dtype=np.float32)
        v = v / (np.linalg.norm(v) + 1e-10)
        dist = 1.0 - float(np.dot(q, v))
        scored.append((i, dist))
    scored.sort(key=lambda x: x[1])
    top = scored[:n]

    result = {
        "ids": [[data["ids"][i] for i, _ in top]],
        "metadatas": [[data["metadatas"][i] for i, _ in top]],
        "distances": [[d for _, d in top]],
    }
    if include_documents:
        result["documents"] = [[data["documents"][i] for i, _ in top]]
    return result
