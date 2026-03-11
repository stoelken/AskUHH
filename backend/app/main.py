import json
import logging
from contextlib import asynccontextmanager
from pathlib import Path
from typing import List

import chromadb
import httpx
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, StreamingResponse, Response
from langchain_community.document_loaders import PyMuPDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from pydantic import BaseModel
from langdetect import detect

from .config import (
    CHROMA_DIR, CHUNK_OVERLAP, CHUNK_SIZE, COLLECTION,
    DOCS_DIR, EMBED_MODEL, LLM_MODEL, OLLAMA_HOST, RERANK_CANDIDATES, RERANK_MODEL,
    RERANK_WORKERS, SYSTEM_PROMPT, TOP_K,
)
from .embeddings import OllamaEmbeddingFunction, embed_query
from .reranking import rerank

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s - %(message)s",
)
logger = logging.getLogger(__name__)
chroma_collection = None
http_client: httpx.Client = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global chroma_collection, http_client

    http_client = httpx.Client(
        timeout=httpx.Timeout(connect=10, read=180, write=30, pool=10),
        limits=httpx.Limits(
            max_connections=20,
            max_keepalive_connections=10,
            keepalive_expiry=120,
        ),
    )

    db = chromadb.PersistentClient(path=CHROMA_DIR)
    chroma_collection = db.get_or_create_collection(
        name=COLLECTION,
        embedding_function=OllamaEmbeddingFunction(),
        metadata={"hnsw:space": "cosine"},
    )
    logger.info(f"Embedding model: {EMBED_MODEL} via Ollama")
    logger.info(f"ChromaDB ready. Indexed chunks: {chroma_collection.count()}")
    logger.info(
        f"Reranking: pointwise via {RERANK_MODEL}, "
        f"candidates={RERANK_CANDIDATES}, workers={RERANK_WORKERS}"
    )

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
    documents:   List[str]
    ollama_host: str
    llm_model:   str
    embed_model: str

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
    return StatusResponse(
        pdf_count=len(pdf_files),
        chunk_count=chroma_collection.count(),
        documents=[f.name for f in pdf_files],
        ollama_host=OLLAMA_HOST,
        llm_model=LLM_MODEL,
        embed_model=EMBED_MODEL,
    )

@app.post("/ingest", response_model=IngestResponse)
def ingest():
    """Load all PDFs, split into chunks, embed, and store in ChromaDB."""
    pdf_files = list(Path(DOCS_DIR).glob("**/*.pdf"))

    if not pdf_files:
        raise HTTPException(status_code=400, detail=f"No PDF files found in {DOCS_DIR}.")

    # Clearing
    existing_ids = chroma_collection.get()["ids"]
    if existing_ids:
        chroma_collection.delete(ids=existing_ids)
        logger.info(f"Cleared {len(existing_ids)} existing chunks before re-indexing.")

    splitter = RecursiveCharacterTextSplitter(
        chunk_size=CHUNK_SIZE,
        chunk_overlap=CHUNK_OVERLAP,
        separators=["\n\n", "\n", ". ", "! ", "? ", "; ", " "],
        length_function=len,
    )

    all_ids:   List[str]  = []
    all_texts: List[str]  = []
    all_metas: List[dict] = []

    try:
        for pdf_path in pdf_files:
            logger.info(f"Extracting: {pdf_path.name}")
            for page_doc in PyMuPDFLoader(str(pdf_path)).load():
                text     = page_doc.page_content.strip()
                page_num = int(page_doc.metadata.get("page", 0)) + 1

                if not text:
                    continue

                for idx, chunk in enumerate(splitter.split_text(text)):
                    chunk = chunk.strip()
                    if len(chunk) < 40:
                        continue
                    all_ids.append(f"{pdf_path.stem}__p{page_num:04d}__c{idx:03d}")
                    all_texts.append(chunk)
                    all_metas.append({"file_name": pdf_path.name, "page": page_num})

        if not all_texts:
            raise HTTPException(status_code=400, detail="PDFs found but no text could be extracted.")

        logger.info(f"Storing {len(all_texts)} chunks in ChromaDB...")
        BATCH = 64
        for i in range(0, len(all_texts), BATCH):
            chroma_collection.upsert(
                ids=all_ids[i:i+BATCH],
                documents=all_texts[i:i+BATCH],
                metadatas=all_metas[i:i+BATCH],
            )
            logger.info(f"  {min(i+BATCH, len(all_texts))} / {len(all_texts)} chunks stored")

        return IngestResponse(
            success=True,
            message=f"Indexed {len(pdf_files)} PDF(s) into {len(all_ids)} chunks.",
            pdf_count=len(pdf_files),
            chunk_count=len(all_ids),
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Ingest failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


def _retrieve_chunks(question: str) -> list:
    """Shared retrieval + parallel reranking logic for all query endpoints."""
    results = chroma_collection.query(
        query_embeddings=[embed_query(question)],
        n_results=min(RERANK_CANDIDATES, chroma_collection.count()),
        include=["documents", "metadatas", "distances"],
    )
    candidates = [
        {
            "text":  doc,
            "file":  meta.get("file_name", "Unknown"),
            "page":  int(meta.get("page", 0)),
            "score": round(max(0.0, 1.0 - dist), 4),
        }
        for doc, meta, dist in zip(
            results["documents"][0],
            results["metadatas"][0],
            results["distances"][0],
        )
    ]
    return rerank(
        question, candidates, OLLAMA_HOST, RERANK_MODEL, TOP_K,
        client=http_client,
        max_workers=RERANK_WORKERS,
    )


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
    """SSE streaming endpoint: sends sources first, then LLM tokens, then [DONE]."""
    if chroma_collection.count() == 0:
        raise HTTPException(status_code=400, detail="No documents indexed yet. Call /ingest first.")

    try:
        chunks = _retrieve_chunks(req.question)
        prompt = _build_prompt(req.question, chunks)
    except Exception as e:
        logger.error(f"Retrieval failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

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

    def event_generator():
        # 1) Send enriched sources with chunk data as the first event
        yield f"event: sources\ndata: {json.dumps(sources_data)}\n\n"

        # 2) Stream LLM tokens from Ollama
        try:
            with http_client.stream(
                "POST",
                f"{OLLAMA_HOST}/api/generate",
                json={
                    "model":   LLM_MODEL,
                    "prompt":  prompt,
                    "system":  SYSTEM_PROMPT,
                    "stream":  True,
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
                    if chunk_data.get("done", False):
                        break
        except Exception as e:
            logger.error(f"Streaming failed: {e}", exc_info=True)
            yield f"event: error\ndata: {json.dumps(str(e))}\n\n"

        # 3) Signal completion
        yield "event: done\ndata: {}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )