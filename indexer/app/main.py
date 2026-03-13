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

from . import models, store, embeddings, reranking
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
    """Hybrid image search: CLIP visual similarity + page text match boost."""
    if store.image_count() == 0:
        return {"image_results": []}

    # Fetch more candidates than needed, then re-rank with text boost
    n_candidates = max(req.top_k * 3, 10)
    query_embedding = models.embed_query(req.query)
    results = store.search_images(query_embedding, n_results=n_candidates)

    query_lower = req.query.lower()
    query_terms = [t for t in query_lower.split() if len(t) >= 2]

    scored = []
    for meta, dist in zip(results["metadatas"][0], results["distances"][0]):
        clip_score = max(0.0, 1.0 - dist)
        page_text = meta.get("page_text", "").lower()

        # Boost: fraction of query terms found in the page text
        if query_terms and page_text:
            matches = sum(1 for t in query_terms if t in page_text)
            text_boost = matches / len(query_terms)
        else:
            text_boost = 0.0

        # Hybrid: 40% CLIP + 60% text match (text is more reliable for documents)
        hybrid_score = 0.4 * clip_score + 0.6 * text_boost

        scored.append({
            "meta": meta,
            "clip_score": round(clip_score, 4),
            "text_boost": round(text_boost, 4),
            "hybrid_score": round(hybrid_score, 4),
        })

    scored.sort(key=lambda x: x["hybrid_score"], reverse=True)

    image_results = []
    for s in scored[: req.top_k]:
        image_path = Path(IMAGES_DIR) / s["meta"]["image_path"]
        if not image_path.exists():
            logger.warning(f"Image not found: {image_path}")
            continue

        b64 = base64.b64encode(image_path.read_bytes()).decode()
        image_results.append({
            "file_name": s["meta"]["file_name"],
            "page": s["meta"]["page"],
            "image_b64": b64,
            "score": s["hybrid_score"],
        })

    logger.info(
        f"Image search for {req.query!r}: {len(image_results)} images, "
        f"hybrid_scores={[r['score'] for r in image_results]}, "
        f"details={[(s['clip_score'], s['text_boost']) for s in scored[:req.top_k]]}"
    )
    return {"image_results": image_results}
