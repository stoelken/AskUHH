import os

OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://localhost:11434")
LLM_MODEL   = os.getenv("LLM_MODEL",  "qwen3:8b")

DOCS_DIR   = os.getenv("DOCS_DIR",   "/data/docs")
CHROMA_DIR = os.getenv("CHROMA_DIR", "/data/chroma_db")
COLLECTION = "university_legal"

EMBED_MODEL  = os.getenv("EMBED_MODEL", "snowflake-arctic-embed2")
QUERY_PREFIX = "Represent this sentence for searching relevant passages: "

CHUNK_SIZE    = int(os.getenv("CHUNK_SIZE",    "512"))
CHUNK_OVERLAP = int(os.getenv("CHUNK_OVERLAP", "64"))

TOP_K              = int(os.getenv("TOP_K",              "5"))
RERANK_CANDIDATES  = int(os.getenv("RERANK_CANDIDATES",  "15"))
RERANK_MODEL       = os.getenv("RERANK_MODEL", "bona/bge-reranker-v2-m3")

SYSTEM_PROMPT = """You are a helpful assistant for university students.
You answer questions about study regulations, examination rules, and legal university documents.
Always be clear, accurate, and easy to understand.
Structure your answers with headings or bullet points where appropriate.
After each heading and the content of that heading, include a new empty line before the next heading or the next content. This makes it easier to read.
Do NOT include inline source citations (e.g. "(Source: ...)" or "(Quelle: ...)") — sources are displayed separately in the UI.
If the answer is not contained in the provided documents, say so clearly — do not guess."""