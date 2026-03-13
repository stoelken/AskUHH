import base64
import logging
from contextlib import asynccontextmanager
from pathlib import Path
from typing import List

import fitz
import httpx
from fastapi import FastAPI, HTTPException, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from langchain_text_splitters import RecursiveCharacterTextSplitter
from pydantic import BaseModel

from . import models, store, embeddings, reranking, image_describer
from .config import (
    CHUNK_OVERLAP, CHUNK_SIZE, IMAGES_DIR, OLLAMA_HOST,
    RERANK_CANDIDATES, TOP_K,
)
from .pdf_processor import extract_images_from_pdf

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s - %(message)s",
)
logger = logging.getLogger(__name__)

http_client: httpx.Client = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global http_client
    http_client = httpx.Client(
        timeout=httpx.Timeout(connect=10, read=180, write=30, pool=180),
        limits=httpx.Limits(
            max_connections=20,
            max_keepalive_connections=10,
            keepalive_expiry=120,
        ),
    )
    embeddings.init(http_client)
    reranking.init(http_client)
    image_describer.init(http_client)
    models.load()
    store.init()
    logger.info(f"Ollama host: {OLLAMA_HOST}")
    yield
    http_client.close()
    logger.info("Shutting down indexer.")


app = FastAPI(title="Multimodal Indexer", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


class ImageSearchRequest(BaseModel):
    query: str
    top_k: int = 2


class TextSearchRequest(BaseModel):
    query: str
    top_k: int = 4
    rerank_candidates: int = 15


@app.get("/health")
def health():
    return {
        "status": "ok",
        "models_loaded": models.is_loaded(),
        "text_count": store.text_count(),
        "image_count": store.image_count(),
    }


@app.get("/status")
def status():
    return {
        "text_count": store.text_count(),
        "image_count": store.image_count(),
    }


@app.post("/ingest")
def ingest(files: List[UploadFile] = File(...)):
    """Receive PDFs, extract text chunks + images, embed both, store in ChromaDB."""
    if not files:
        raise HTTPException(400, "No files uploaded")

    store.clear_text()
    store.clear_images()

    splitter = RecursiveCharacterTextSplitter(
        chunk_size=CHUNK_SIZE,
        chunk_overlap=CHUNK_OVERLAP,
        separators=["\n\n", "\n", ". ", "! ", "? ", "; ", " "],
        length_function=len,
    )

    # Accumulators for text
    text_ids: List[str] = []
    text_docs: List[str] = []
    text_metas: List[dict] = []

    # Accumulators for images
    img_ids: List[str] = []
    img_embeddings: List[List[float]] = []
    img_metas: List[dict] = []

    pdf_count = 0

    for upload in files:
        if not upload.filename.lower().endswith(".pdf"):
            logger.warning(f"Skipping non-PDF file: {upload.filename}")
            continue

        pdf_count += 1
        pdf_bytes = upload.file.read()
        logger.info(f"Processing {upload.filename} ({len(pdf_bytes)} bytes)")

        # ── Text extraction + chunking ────────────────────────────
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
        for page_num in range(len(doc)):
            text = doc[page_num].get_text().strip()
            if not text:
                continue
            page = page_num + 1
            for idx, chunk in enumerate(splitter.split_text(text)):
                chunk = chunk.strip()
                if len(chunk) < 40:
                    continue
                stem = Path(upload.filename).stem
                text_ids.append(f"{stem}__p{page:04d}__c{idx:03d}")
                text_docs.append(chunk)
                text_metas.append({"file_name": upload.filename, "page": page})
        doc.close()

        # ── Image extraction ──────────────────────────────────────
        image_entries = extract_images_from_pdf(pdf_bytes, upload.filename)
        if image_entries:
            pil_images = [e["pil_image"] for e in image_entries]
            BATCH = 32
            clip_embs = []
            for i in range(0, len(pil_images), BATCH):
                clip_embs.extend(models.embed_images(pil_images[i : i + BATCH]))

            for entry, emb in zip(image_entries, clip_embs):
                img_ids.append(entry["id"])
                img_embeddings.append(emb)
                img_metas.append({
                    "file_name": entry["file_name"],
                    "page": entry["page"],
                    "image_path": entry["image_path"],
                    "page_text": entry["page_text"][:2000],
                })

            # ── Generate AI descriptions for images ────────────────
            logger.info(f"Generating VLM descriptions for {len(image_entries)} images...")
            descriptions = image_describer.describe_images(image_entries)
            for entry, desc in zip(image_entries, descriptions):
                if not desc or len(desc.strip()) < 20:
                    continue
                desc_id = f"{entry['id']}__desc"
                text_ids.append(desc_id)
                text_docs.append(desc)
                text_metas.append({
                    "file_name": entry["file_name"],
                    "page": entry["page"],
                    "image_path": entry["image_path"],
                    "type": "image_description",
                })

    # ── Embed text via Ollama and store ───────────────────────────
    if text_docs:
        logger.info(f"Embedding {len(text_docs)} text chunks via Ollama...")
        BATCH = 64
        text_embeddings = []
        for i in range(0, len(text_docs), BATCH):
            text_embeddings.extend(embeddings.embed_texts(text_docs[i : i + BATCH]))
        store.upsert_text(text_ids, text_docs, text_embeddings, text_metas)

    # ── Store image embeddings ────────────────────────────────────
    if img_ids:
        store.upsert_images(img_ids, img_embeddings, img_metas)

    result = {
        "success": True,
        "pdf_count": pdf_count,
        "text_count": len(text_ids),
        "image_count": len(img_ids),
    }
    logger.info(f"Ingest complete: {result}")
    return result


@app.post("/search/text")
def search_text(req: TextSearchRequest):
    """Embed query via Ollama, search text collection, rerank, return top-k."""
    if store.text_count() == 0:
        return {"text_results": []}

    query_embedding = embeddings.embed_query(req.query)
    n = max(1, min(req.rerank_candidates, store.text_count()))
    results = store.search_text(query_embedding, n_results=n)

    candidates = [
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

    ranked = reranking.rerank(req.query, candidates, req.top_k)

    logger.info(
        f"Text search for {req.query!r}: "
        f"{len(ranked)} results after reranking from {len(candidates)} candidates"
    )
    return {"text_results": ranked}


@app.post("/search/images")
def search_images(req: ImageSearchRequest):
    """Hybrid image search: CLIP + text description matching."""
    logger.info(f"Image search request: query={req.query!r}, top_k={req.top_k}")
    if store.image_count() == 0:
        return {"image_results": []}

    # ── 1) CLIP visual search ─────────────────────────────────────
    n_candidates = max(req.top_k * 3, 10)
    query_embedding = models.embed_query(req.query)
    results = store.search_images(query_embedding, n_results=n_candidates)

    query_lower = req.query.lower()
    stop_words = {
        "der", "die", "das", "den", "dem", "des", "ein", "eine", "einer", "einem",
        "einen", "und", "oder", "aber", "für", "von", "mit", "bei", "nach", "aus",
        "auf", "ist", "sind", "was", "wie", "wer", "wann", "wo", "ich", "du", "er",
        "sie", "wir", "ihr", "sich", "nicht", "auch", "noch", "nur", "wenn", "als",
        "kann", "wird", "hat", "haben", "sein", "werden", "gibt", "welche", "welcher",
        "the", "is", "are", "was", "were", "for", "and", "with", "this", "that",
        "from", "what", "how", "who", "can", "has", "have", "not", "but",
    }
    query_terms = [t for t in query_lower.split() if len(t) >= 2 and t not in stop_words]

    # score CLIP candidates by image_path
    scored_by_path: dict[str, dict] = {}
    for meta, dist in zip(results["metadatas"][0], results["distances"][0]):
        clip_score = max(0.0, 1.0 - dist)
        page_text = meta.get("page_text", "").lower()

        if query_terms and page_text:
            matches = sum(1 for t in query_terms if t in page_text)
            text_boost = matches / len(query_terms)
        else:
            text_boost = 0.0

        hybrid_score = 0.4 * clip_score + 0.6 * text_boost
        img_path = meta.get("image_path", "")
        scored_by_path[img_path] = {
            "meta": meta,
            "score": round(hybrid_score, 4),
            "source": "clip",
        }

    # ── 2) Text description search ────────────────────────────────
    try:
        desc_embedding = embeddings.embed_query(req.query)
        desc_results = store.search_text_filtered(
            desc_embedding,
            n_results=req.top_k * 2,
            where={"type": "image_description"},
        )
        for meta, dist in zip(desc_results["metadatas"][0], desc_results["distances"][0]):
            desc_score = max(0.0, 1.0 - dist)
            img_path = meta.get("image_path", "")
            # Description match wins over CLIP if it scores higher
            existing = scored_by_path.get(img_path)
            if not existing or desc_score > existing["score"]:
                scored_by_path[img_path] = {
                    "meta": meta,
                    "score": round(desc_score, 4),
                    "source": "description",
                }
    except Exception:
        logger.exception("Description-based image search failed, using CLIP only")

    # ── 3) Merge, sort, return top-k ──────────────────────────────
    ranked = sorted(scored_by_path.values(), key=lambda x: x["score"], reverse=True)

    image_results = []
    for s in ranked[: req.top_k]:
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

    logger.info(
        f"Image search for {req.query!r}: {len(image_results)} images, "
        f"scores={[(r['score'], s['source']) for r, s in zip(image_results, ranked[:req.top_k])]}"
    )
    return {"image_results": image_results}
