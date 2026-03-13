import json
import logging
import math
from contextlib import asynccontextmanager
from pathlib import Path
from typing import List

import httpx
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, StreamingResponse, Response
from pydantic import BaseModel
from langdetect import detect

from .config import DOCS_DIR, INDEXER_HOST, LLM_MODEL, OLLAMA_HOST, SYSTEM_PROMPT, TOP_K_IMAGES
from . import indexer_client

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
    indexer_client.init(http_client)

    logger.info(f"Ollama host: {OLLAMA_HOST}")
    logger.info(f"Indexer host: {INDEXER_HOST}")

    yield

    http_client.close()
    logger.info("Shutting down.")

app = FastAPI(title="University RAG API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

class QueryRequest(BaseModel):
    question: str

class StatusResponse(BaseModel):
    pdf_count:   int
    chunk_count: int
    image_count: int = 0
    documents:   List[str]
    ollama_host: str
    llm_model:   str

class IngestResponse(BaseModel):
    success:     bool
    message:     str
    pdf_count:   int
    chunk_count: int

class HighlightRequest(BaseModel):
    filename: str
    chunks: List[dict]

@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/pdf/{filename}")
def serve_pdf(filename: str):
    pdf_path = Path(DOCS_DIR) / filename
    if not pdf_path.exists() or pdf_path.suffix.lower() != ".pdf":
        raise HTTPException(status_code=404, detail="PDF not found")
    return FileResponse(pdf_path, media_type="application/pdf")


@app.post("/pdf/highlight")
def highlight_pdf(req: HighlightRequest):
    """Highlight specific chunks in a PDF and return modified PDF with annotations."""
    pdf_path = Path(DOCS_DIR) / req.filename
    if not pdf_path.exists() or pdf_path.suffix.lower() != ".pdf":
        raise HTTPException(status_code=404, detail="PDF not found")

    try:
        from .pdf_highlighter import highlight_chunks_in_pdf
        highlighted_bytes = highlight_chunks_in_pdf(str(pdf_path), req.chunks)
        return Response(content=highlighted_bytes, media_type="application/pdf")
    except Exception as e:
        logger.error(f"PDF highlighting failed for {req.filename}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/status", response_model=StatusResponse)
def status():
    pdf_files = list(Path(DOCS_DIR).glob("**/*.pdf"))
    text_count = 0
    img_count = 0
    try:
        st = indexer_client.get_status()
        text_count = st.get("text_count", 0)
        img_count = st.get("image_count", 0)
    except Exception:
        pass
    return StatusResponse(
        pdf_count=len(pdf_files),
        chunk_count=text_count,
        image_count=img_count,
        documents=[f.name for f in pdf_files],
        ollama_host=OLLAMA_HOST,
        llm_model=LLM_MODEL,
    )

@app.post("/ingest", response_model=IngestResponse)
def ingest():
    """Upload all local PDFs to the indexer for text + image indexing."""
    pdf_files = list(Path(DOCS_DIR).glob("**/*.pdf"))

    if not pdf_files:
        raise HTTPException(status_code=400, detail=f"No PDF files found in {DOCS_DIR}.")

    try:
        result = indexer_client.ingest_pdfs(pdf_files)
        text_count = result.get("text_count", 0)
        image_count = result.get("image_count", 0)

        return IngestResponse(
            success=True,
            message=f"Indexed {result['pdf_count']} PDF(s): {text_count} text chunks + {image_count} images.",
            pdf_count=result["pdf_count"],
            chunk_count=text_count,
        )
    except Exception as e:
        logger.error(f"Ingest failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


def _build_prompt(question: str, chunks: list) -> str:
    lang = detect(question)
    context = "\n\n---\n\n".join(
        f"[file_name: {c['file']}, page_num {c['page']}]\n{c['text']}"
        for c in chunks
    )
    logger.info(f"Chunks passed to LLM ({len(chunks)}):")
    for i, c in enumerate(chunks):
        logger.info(f"  [{i}] file={c['file']} page={c['page']} score={c['score']} text_preview={c['text'][:80]!r}")
    return (
        "Answer the following question solely based on the provided document excerpts. "
        "Do NOT add any information that is not explicitly stated in the excerpts. "
        "Do not cite sources inline — they are shown separately to the user. "
        "Structure your answer clearly using bold headings or bullet points where it helps readability.\n\n"
        "IMPORTANT: Format your response like this:\n"
        "**Section Title**\n"
        "Content goes directly here on the next line.\n\n"
        "**Next Section**\n"
        "More content here.\n\n"
        "- For section titles use markdown headings\n"
        "- NO blank line between the title and content\n"
        "- Add blank lines ONLY between the content of the previous section and the heading of the next section\n"
        "- NO blank line at the beginning\n\n"
        "If the answer is not in the documents, say so clearly.\n\n"
        f"Always respond in the same language as the question (detected: {lang}).\n"
        f"Question: {question}\n\n"
        f"Context:\n{context}\n\n"
        "Answer:"
    )


@app.post("/query/stream")
def query_stream(req: QueryRequest):
    """SSE streaming endpoint: sends sources first, then LLM tokens, then done with logprobs."""

    # ── Retrieve text chunks from indexer ──────────────────────────
    try:
        chunks = indexer_client.search_text(req.question)
    except Exception as e:
        logger.error(f"Text retrieval failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

    if not chunks:
        raise HTTPException(status_code=400, detail="No documents indexed yet. Call /ingest first.")

    prompt = _build_prompt(req.question, chunks)

    # Build sources data: group chunks by filename, keep top 3 per file
    sources_map = {}
    for c in chunks:
        if c["file"] not in sources_map:
            sources_map[c["file"]] = []
        if len(sources_map[c["file"]]) < 3:
            sources_map[c["file"]].append({
                "page": c["page"],
                "text": c["text"],
                "score": c["score"],
            })

    # Limit to top 3 files (preserving chunk order)
    pdf_names = list(sources_map.keys())[:3]
    sources_data = [
        {"filename": name, "chunks": sources_map[name]}
        for name in pdf_names
    ]

    # ── Get CLIP-ranked top images from indexer ────────────────────
    all_images = []
    try:
        image_results = indexer_client.search_images(req.question, TOP_K_IMAGES)
        all_images = [img["image_b64"] for img in image_results]
        logger.info(f"CLIP image search: {len(all_images)} images, scores={[img['score'] for img in image_results]}")
    except Exception as e:
        logger.warning(f"Image retrieval from indexer failed: {e}")

    logger.info(f"Debug: image_count={len(all_images)}")

    def event_generator():
        # 1) Send enriched sources with chunk data as the first event
        yield f"event: sources\ndata: {json.dumps(sources_data)}\n\n"

        # 2) Stream LLM tokens from Ollama, collecting logprobs
        token_probs = []
        try:
            with http_client.stream(
                "POST",
                f"{OLLAMA_HOST}/api/generate",
                json={
                    "model":        LLM_MODEL,
                    "prompt":       prompt,
                    "system":       SYSTEM_PROMPT,
                    "stream":       True,
                    "logprobs":     True,
                    "top_logprobs": 20,
                    "images":       all_images,
                    "options": {"temperature": 0.1, "num_predict": 1024},
                },
            ) as resp:
                resp.raise_for_status()
                for line in resp.iter_lines():
                    if not line:
                        continue
                    chunk_data = json.loads(line)
                    token = chunk_data.get("response", "")
                    if token:
                        yield f"event: token\ndata: {json.dumps(token)}\n\n"

                    for token_data in chunk_data.get("logprobs", []):
                        top = token_data.get("top_logprobs", [])
                        if not top:
                            continue
                        chosen = top[0]
                        prob = math.exp(chosen["logprob"])
                        token_probs.append({
                            "token":        chosen["token"],
                            "probability":  round(prob * 100, 1),
                            "alternatives": [
                                {
                                    "token":       alt["token"],
                                    "probability": round(math.exp(alt["logprob"]) * 100, 1),
                                }
                                for alt in top[1:]
                            ],
                        })

                    if chunk_data.get("done", False):
                        break
        except Exception as e:
            logger.error(f"Streaming failed: {e}", exc_info=True)
            yield f"event: error\ndata: {json.dumps(str(e))}\n\n"

        # 3) Signal completion with logprobs
        yield f"event: done\ndata: {json.dumps({'logprobs': token_probs, 'debug_images': all_images})}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
