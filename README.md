# AskUHH - RAG Assistant for University Regulations <a name="Introduction"></a>

AskUHH is a document-based chat assistant for university regulation PDFs.
It lets you upload documents, index them, ask questions in a chat UI, and open the matching PDF sources.

In this project version, the pipeline includes:

- PDF upload and management
- text chunk retrieval with embeddings (ChromaDB)
- optional image extraction + image descriptions for visual content
- streamed LLM answers with source documents and follow-up question suggestions

The goal is to make regulation-heavy PDFs easier to understand by giving answers grounded in your own files.

# Data <a name="Data"></a>

## Data Overview <a name="DataOverview"></a>

| Source           | Description                                 | Location                     |
| ---------------- | ------------------------------------------- | ---------------------------- |
| PDF files        | University documents used as knowledge base | backend/data/docs/           |
| Text chunks      | Embedded text segments for retrieval        | Docker volume backend_chroma |
| Extracted images | Stored page images used for VLM retrieval   | Docker volume backend_images |

## Data Flow <a name="DataFlow"></a>

1. Add PDFs to the docs folder (or upload in UI)
2. Trigger indexing
3. Backend extracts text chunks (and images), then creates embeddings
4. Query retrieves relevant chunks/images
5. LLM streams an answer based only on retrieved context

# Installation <a name="Installation"></a>

## Prerequisites <a name="Prerequisites"></a>

Before you run this repository, make sure you have:

1. Docker Desktop (with Docker Compose)
2. Git
3. Optional GPU support (if you want to run Ollama locally with GPU)
4. A reachable Ollama endpoint (local container or external host)

## Installation Steps <a name="InstallationSteps"></a>

1. Clone repository

```bash
git clone https://git.informatik.uni-hamburg.de/3gorke/askuhh.git
cd askuhh
```

2. Create local env file

```bash
cp .env.example .env
```

3. Edit environment values in .env

Minimal example:

```dotenv
OLLAMA_HOST=http://134.100.39.14:11435

LLM_MODEL=qwen3-vl:8b-instruct
EMBED_MODEL=snowflake-arctic-embed2
TOP_K_IMAGES=3

FRONTEND_PORT=3123
BACKEND_PORT=8123
```

4. Start app stack

```bash
docker compose up --build
```

This starts:

- askuhh-backend
- askuhh-frontend

5. Optional: start local Ollama container profile

```bash
docker compose --profile ollama -f docker-compose.gpu.yml up -d ollama
```

Use this when you do not want to rely on an external Ollama host.

6. Open app

```text
http://localhost:3123
```

# User Guide <a name="UserGuide"></a>

## Quick Start in App <a name="QuickStartInApp"></a>

1. Upload one or more PDFs in the sidebar
2. Click Index / Re-index
3. Wait until chunk count is available
4. Ask your question in the chat
5. Open source PDFs from the answer cards

## Document Handling <a name="DocumentHandling"></a>

- Upload uses the sidebar dropzone or file picker
- Only PDF files are accepted
- You can delete individual documents in the loaded documents list
- After adding/deleting docs, run Index / Re-index to refresh retrieval data

## Chat Behavior <a name="ChatBehavior"></a>

- Answers are streamed token-by-token
- Sources are shown per assistant response
- Follow-up suggestions are generated after the answer
- If nothing is indexed yet, the app will block querying and show a hint banner

# API Overview <a name="ApiOverview"></a>

## Main Endpoints <a name="MainEndpoints"></a>

| Endpoint              | Method | Purpose                                      |
| --------------------- | ------ | -------------------------------------------- |
| /health               | GET    | service health check                         |
| /status               | GET    | frontend status cards and indexing state     |
| /documents/upload     | POST   | upload PDF files                             |
| /documents/{filename} | DELETE | delete PDF file                              |
| /ingest               | POST   | build/rebuild index                          |
| /query/stream         | POST   | SSE answer stream                            |
| /pdf/{filename}       | GET    | serve original PDF                           |
| /pdf/highlight        | POST   | create highlighted PDF from retrieved chunks |

# Developer Guide <a name="DeveloperGuide"></a>

## Project Structure <a name="ProjectStructure"></a>

- frontend/: React + Vite UI
- backend/: FastAPI app + indexing pipeline
- backend/app/indexer/: embeddings, vector store, PDF processing, image description
- backend/data/docs/: mounted document folder for PDFs
- docker-compose.yml: frontend + backend services
- docker-compose.gpu.yml: optional local Ollama GPU profile

## Typical Dev Workflow <a name="DevWorkflow"></a>

1. Start services with docker compose
2. Add test PDFs into backend/data/docs/
3. Trigger ingest from UI
4. Ask test questions and verify sources
5. Check backend logs for retrieval/LLM behavior

## Notes on Models <a name="ModelNotes"></a>

- LLM model is configured with LLM_MODEL
- Embedding model is configured with EMBED_MODEL
- Vision-language model is configured with VLM_MODEL (if used)
- Make sure models are available on your Ollama instance

# Troubleshooting <a name="Troubleshooting"></a>

## Backend not reachable

- check container status: docker compose ps
- verify BACKEND_PORT mapping
- test health endpoint directly: http://localhost:8123/health

## No answers or "No documents indexed"

- make sure PDFs exist in backend/data/docs/
- run Index / Re-index
- verify chunk count in sidebar status

## Ollama connection issues

- verify OLLAMA_HOST in .env
- if local ollama container is used, make sure it is running
- ensure selected models are pulled and available

# Next Steps <a name="NextSteps"></a>

- add stronger auth and role-based access if needed
- improve retrieval reranking for long regulation documents
- add ingestion history and per-document indexing status
- add test suite for API and retrieval quality checks
