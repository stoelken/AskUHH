import os
import logging
from pathlib import Path
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from llama_index.core import (
    VectorStoreIndex,
    SimpleDirectoryReader,
    Settings,
    StorageContext,
)
from llama_index.core.node_parser import SentenceSplitter
from llama_index.embeddings.ollama import OllamaEmbedding
from llama_index.llms.ollama import Ollama
from llama_index.vector_stores.chroma import ChromaVectorStore
import chromadb

# ── Logging ───────────────────────────────────────────────────────────────────

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ── Config ────────────────────────────────────────────────────────────────────

OLLAMA_HOST   = os.getenv("OLLAMA_HOST", "http://localhost:11434")
DOCS_DIR      = os.getenv("DOCS_DIR", "/data/docs")
CHROMA_DIR    = os.getenv("CHROMA_DIR", "/data/chroma_db")
COLLECTION    = "university_legal"
LLM_MODEL     = os.getenv("LLM_MODEL", "qwen3:8b")
EMBED_MODEL   = os.getenv("EMBED_MODEL", "snowflake-arctic-embed2")
CHUNK_SIZE    = int(os.getenv("CHUNK_SIZE", "512"))
CHUNK_OVERLAP = int(os.getenv("CHUNK_OVERLAP", "64"))
TOP_K         = int(os.getenv("TOP_K", "4"))

SYSTEM_PROMPT = """You are a helpful assistant for university students.
You answer questions about university regulations, formal procedures, and legal documents.
Always be clear, accurate, and student-friendly.
Always cite which document your answer comes from.
If the answer is not contained in the provided documents, say so clearly — do not guess.
Keep answers concise and easy to understand."""

# ── State ─────────────────────────────────────────────────────────────────────

chroma_collection = None

# ── Startup ───────────────────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    global chroma_collection
    logger.info("Initializing LlamaIndex settings...")

    Settings.llm = Ollama(
        model=LLM_MODEL,
        base_url=OLLAMA_HOST,
        request_timeout=180,
        system_prompt=SYSTEM_PROMPT,
    )
    Settings.embed_model = OllamaEmbedding(
        model_name=EMBED_MODEL,
        base_url=OLLAMA_HOST,
    )
    Settings.text_splitter = SentenceSplitter(
        chunk_size=CHUNK_SIZE,
        chunk_overlap=CHUNK_OVERLAP,
    )

    db = chromadb.PersistentClient(path=CHROMA_DIR)
    chroma_collection = db.get_or_create_collection(COLLECTION)
    logger.info(f"ChromaDB ready. Chunks indexed: {chroma_collection.count()}")

    yield
    logger.info("Shutting down.")


# ── App ───────────────────────────────────────────────────────────────────────

app = FastAPI(title="University RAG API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Schemas ───────────────────────────────────────────────────────────────────

class QueryRequest(BaseModel):
    question: str

class SourceNode(BaseModel):
    file: str
    score: float
    text: str

class QueryResponse(BaseModel):
    answer: str
    sources: list[SourceNode]

class StatusResponse(BaseModel):
    pdf_count: int
    chunk_count: int
    documents: list[str]
    ollama_host: str
    llm_model: str
    embed_model: str

class IngestResponse(BaseModel):
    success: bool
    message: str
    pdf_count: int
    page_count: int

# ── Helpers ───────────────────────────────────────────────────────────────────

def get_index():
    vector_store = ChromaVectorStore(chroma_collection=chroma_collection)
    storage_context = StorageContext.from_defaults(vector_store=vector_store)
    return VectorStoreIndex.from_vector_store(vector_store, storage_context=storage_context)

# ── Routes ────────────────────────────────────────────────────────────────────

@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/status", response_model=StatusResponse)
def status():
    docs_path = Path(DOCS_DIR)
    pdf_files = list(docs_path.glob("**/*.pdf"))
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
    docs_path = Path(DOCS_DIR)
    pdf_files = list(docs_path.glob("**/*.pdf"))

    if not pdf_files:
        raise HTTPException(status_code=400, detail="No PDF files found in docs directory.")

    try:
        documents = SimpleDirectoryReader(DOCS_DIR, recursive=True).load_data()
        vector_store = ChromaVectorStore(chroma_collection=chroma_collection)
        storage_context = StorageContext.from_defaults(vector_store=vector_store)
        VectorStoreIndex.from_documents(documents, storage_context=storage_context, show_progress=False)
        logger.info(f"Indexed {len(pdf_files)} PDFs, {len(documents)} pages.")
        return IngestResponse(
            success=True,
            message=f"Successfully indexed {len(pdf_files)} document(s).",
            pdf_count=len(pdf_files),
            page_count=len(documents),
        )
    except Exception as e:
        logger.error(f"Ingest error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/query", response_model=QueryResponse)
def query(req: QueryRequest):
    if chroma_collection.count() == 0:
        raise HTTPException(status_code=400, detail="No documents indexed yet. Run /ingest first.")

    try:
        index = get_index()
        engine = index.as_query_engine(similarity_top_k=TOP_K)
        response = engine.query(req.question)
        sources = [
            SourceNode(
                file=node.metadata.get("file_name", "Unknown"),
                score=node.score or 0.0,
                text=node.text,
            )
            for node in response.source_nodes
        ]
        return QueryResponse(answer=str(response), sources=sources)
    except Exception as e:
        logger.error(f"Query error: {e}")
        raise HTTPException(status_code=500, detail=str(e))
