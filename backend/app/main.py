import logging
from contextlib import asynccontextmanager
from pathlib import Path
from collections import defaultdict
from itertools import zip_longest
from typing import List, Optional

import chromadb
import httpx
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from langchain_community.document_loaders import PyMuPDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from pydantic import BaseModel

from .config import (
    CHROMA_DIR, CHUNK_OVERLAP, CHUNK_SIZE, COLLECTION,
    DOCS_DIR, EMBED_MODEL, LLM_MODEL, OLLAMA_HOST, RERANK_CANDIDATES, RERANK_MODEL,
    SYSTEM_PROMPT, TOP_K,
)
from .embeddings import OllamaEmbeddingFunction, embed_query
from .reranking import rerank

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s - %(message)s",
)
logger = logging.getLogger(__name__)
chroma_collection = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global chroma_collection

    db = chromadb.PersistentClient(path=CHROMA_DIR)
    chroma_collection = db.get_or_create_collection(
        name=COLLECTION,
        embedding_function=OllamaEmbeddingFunction(),
        metadata={"hnsw:space": "cosine"},
    )
    logger.info(f"Embedding model: {EMBED_MODEL} via Ollama")
    logger.info(f"ChromaDB ready. Indexed chunks: {chroma_collection.count()}")
    logger.info(f"Reranking: pointwise via {RERANK_MODEL}, candidates={RERANK_CANDIDATES}")

    yield
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

class SourceNode(BaseModel):
    file:  str
    page:  int
    score: float
    text:  str

class QueryResponse(BaseModel):
    answer:  str
    sources: List[SourceNode]

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

@app.get("/health")
def health():
    return {"status": "ok"}


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
                    all_texts.append(f"[Document: {pdf_path.name}]\n{chunk}")
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


@app.post("/query", response_model=QueryResponse)
def query(req: QueryRequest):
    """Embed question, retrieve candidates, rerank via LLM, generate answer."""
    if chroma_collection.count() == 0:
        raise HTTPException(status_code=400, detail="No documents indexed yet. Call /ingest first.")

    try:
        results = chroma_collection.query(
            query_embeddings=[embed_query(req.question)],
            n_results=min(RERANK_CANDIDATES, chroma_collection.count()),
            include=["documents", "metadatas", "distances"],
        )

        candidates = [
            {
                "text":  doc,
                "file":  meta.get("file_name", "Unknown"),
                "page":  int(meta.get("page", 0)),
                "score": round(1.0 - dist, 4),
            }
            for doc, meta, dist in zip(
                results["documents"][0],
                results["metadatas"][0],
                results["distances"][0],
            )
        ]

        chunks = rerank(req.question, candidates, OLLAMA_HOST, RERANK_MODEL, TOP_K)

        context = "\n\n---\n\n".join(c['text'] for c in chunks)

        prompt = (
            "Answer the following question solely based on the provided document excerpts. "
            "Do NOT add any information that is not explicitly stated in the excerpts. "
            "Do not cite sources inline — they are shown separately to the user. "
            "Structure your answer clearly using bullet points or headings where it helps readability. "
            "If the answer is not in the documents, say so clearly.\n\n"
            f"Question: {req.question}\n\n"
            f"Context:\n{context}\n\n"
            "Answer:"
        )

        with httpx.Client(timeout=180) as client:
            resp = client.post(
                f"{OLLAMA_HOST}/api/generate",
                json={
                    "model":   LLM_MODEL,
                    "prompt":  prompt,
                    "system":  SYSTEM_PROMPT,
                    "stream":  False,
                    "options": {"temperature": 0.1, "num_predict": 1024},
                },
            )
            resp.raise_for_status()

        return QueryResponse(
            answer=resp.json()["response"].strip(),
            sources=[
                SourceNode(file=c["file"], page=c["page"], score=c["score"], text=c["text"])
                for c in chunks
            ],
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Query failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))