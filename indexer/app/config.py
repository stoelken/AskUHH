import os

CLIP_MODEL = os.getenv("CLIP_MODEL", "openai/clip-vit-base-patch32")
CHROMA_DIR = os.getenv("CHROMA_DIR", "/data/chroma_db")
IMAGES_DIR = os.getenv("IMAGES_DIR", "/data/images")
IMAGE_COLLECTION = os.getenv("IMAGE_COLLECTION", "image_embeddings")
TEXT_COLLECTION = os.getenv("TEXT_COLLECTION", "text_chunks")
CHUNK_SIZE = int(os.getenv("CHUNK_SIZE", "512"))
CHUNK_OVERLAP = int(os.getenv("CHUNK_OVERLAP", "64"))
DEVICE = os.getenv("DEVICE", "cuda")

# Ollama (co-located on the same GPU server)
OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://askuhh-ollama:11434")
EMBED_MODEL = os.getenv("EMBED_MODEL", "snowflake-arctic-embed2")
RERANK_MODEL = os.getenv("RERANK_MODEL", "dengcao/Qwen3-Reranker-0.6B:Q8_0")
VLM_MODEL = os.getenv("VLM_MODEL", "qwen3-vl:8b-instruct")
RERANK_CANDIDATES = int(os.getenv("RERANK_CANDIDATES", "15"))
TOP_K = int(os.getenv("TOP_K", "4"))
