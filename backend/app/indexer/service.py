import base64
import logging
from pathlib import Path
from typing import List

import fitz
import httpx
from langchain_text_splitters import RecursiveCharacterTextSplitter

from . import embeddings, image_describer, store
from ..config import CHUNK_OVERLAP, CHUNK_SIZE, IMAGES_DIR

logger = logging.getLogger(__name__)


def init(http_client: httpx.Client) -> None:
    embeddings.init(http_client)
    image_describer.init(http_client)
    store.init()


def get_status() -> dict:
    return {"text_count": store.text_count()}


def ingest_pdfs(pdf_paths: List[Path]) -> dict:
    store.clear_text()

    splitter = RecursiveCharacterTextSplitter(
        chunk_size=CHUNK_SIZE,
        chunk_overlap=CHUNK_OVERLAP,
        separators=["\n\n", "\n", ". ", "! ", "? ", "; ", " "],
        length_function=len,
    )

    text_ids: List[str] = []
    text_docs: List[str] = []
    text_metas: List[dict] = []
    pdf_count = 0

    for pdf_path in pdf_paths:
        if pdf_path.suffix.lower() != ".pdf":
            logger.warning(f"Skipping non-PDF: {pdf_path}")
            continue

        pdf_count += 1
        pdf_bytes = pdf_path.read_bytes()
        filename = pdf_path.name
        logger.info(f"Processing {filename} ({len(pdf_bytes)} bytes)")

        # ── Text extraction + chunking ────────────────────────────
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
        for page_num in range(len(doc)):
            text = doc[page_num].get_text().strip()
            if not text:
                continue
            page = page_num + 1
            stem = pdf_path.stem
            for idx, chunk in enumerate(splitter.split_text(text)):
                chunk = chunk.strip()
                if len(chunk) < 40:
                    continue
                text_ids.append(f"{stem}__p{page:04d}__c{idx:03d}")
                text_docs.append(chunk)
                text_metas.append({"file_name": filename, "page": page})
        doc.close()

        # ── Image extraction + VLM descriptions ──────────────────
        from .pdf_processor import extract_images_from_pdf
        image_entries = extract_images_from_pdf(pdf_bytes, filename)
        if image_entries:
            logger.info(f"Generating VLM descriptions for {len(image_entries)} images...")
            descriptions = image_describer.describe_images(image_entries)
            for entry, desc in zip(image_entries, descriptions):
                if not desc or len(desc.strip()) < 20:
                    continue
                text_ids.append(f"{entry['id']}__desc")
                text_docs.append(desc)
                text_metas.append({
                    "file_name": entry["file_name"],
                    "page": entry["page"],
                    "image_path": entry["image_path"],
                    "type": "image_description",
                })

    # ── Embed all text via Ollama and store ───────────────────────
    if text_docs:
        logger.info(f"Embedding {len(text_docs)} text chunks via Ollama...")
        BATCH = 64
        text_embeddings: List[List[float]] = []
        for i in range(0, len(text_docs), BATCH):
            text_embeddings.extend(embeddings.embed_texts(text_docs[i : i + BATCH]))
        store.upsert_text(text_ids, text_docs, text_embeddings, text_metas)

    result = {
        "success": True,
        "pdf_count": pdf_count,
        "text_count": len(text_ids),
        "image_count": 0,
    }
    logger.info(f"Ingest complete: {result}")
    return result


def search_text(query: str, top_k: int = 4) -> List[dict]:
    if store.text_count() == 0:
        return []

    query_embedding = embeddings.embed_query(query)
    n = max(1, min(top_k, store.text_count()))
    results = store.search_text(query_embedding, n_results=n)

    return [
        {
            "text": doc,
            "file": meta.get("file_name", "Unknown"),
            "page": int(meta.get("page", 0)),
            "score": round(max(0.0, 1.0 - dist), 4),
        }
        for doc, meta, dist in zip(
            results["documents"][0],
            results["metadatas"][0],
            results["distances"][0],
        )
    ]


def search_images(query: str, top_k: int = 2) -> List[dict]:
    scored_by_path: dict[str, dict] = {}

    try:
        desc_embedding = embeddings.embed_query(query)
        desc_results = store.search_text_filtered(
            desc_embedding,
            n_results=top_k * 2,
            where={"type": "image_description"},
        )
        for meta, dist in zip(desc_results["metadatas"][0], desc_results["distances"][0]):
            desc_score = max(0.0, 1.0 - dist)
            img_path = meta.get("image_path", "")
            existing = scored_by_path.get(img_path)
            if not existing or desc_score > existing["score"]:
                scored_by_path[img_path] = {"meta": meta, "score": round(desc_score, 4)}
    except Exception:
        logger.exception("Description-based image search failed")

    ranked = sorted(scored_by_path.values(), key=lambda x: x["score"], reverse=True)

    image_results = []
    for s in ranked[:top_k]:
        image_path = Path(IMAGES_DIR) / s["meta"]["image_path"]
        if not image_path.exists():
            logger.warning(f"Image not found: {image_path}")
            continue
        b64 = base64.b64encode(image_path.read_bytes()).decode()
        image_results.append({
            "file_name": s["meta"]["file_name"],
            "page": s["meta"]["page"],
            "image_b64": b64,
            "score": s["score"],
        })

    logger.info(f"Image search for {query!r}: {len(image_results)} images")
    return image_results
