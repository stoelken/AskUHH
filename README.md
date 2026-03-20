# AskUHH – RAG-Based Assistant for University Documents <a name="Introduction"></a>

AskUHH is a document-based chat assistant specifically designed for working with university PDF documents such as examination regulations, study guidelines, and other legal documents of the University of Hamburg.

The application allows users to upload PDF files, automatically index them, and then ask questions about the content in natural language. Answers are streamed in real time and are based exclusively on the uploaded documents. Source references with page numbers are displayed automatically, and the relevant passages in the original PDF are highlighted directly.

The current version of the pipeline includes:

- **PDF upload and management** via a web interface
- **Text chunk retrieval** with semantic embeddings (ChromaDB)
- **Image extraction and VLM descriptions** for visual content in PDFs
- **Streamed LLM answers** with source documents, confidence scores, and follow-up suggestions

The goal is to simplify working with regulation-heavy PDF documents by providing answers that are directly grounded in the user's own files.

---

# Architecture <a name="Architecture"></a>

## System Overview <a name="SystemOverview"></a>

AskUHH consists of three main components orchestrated via Docker Compose:

| Component | Technology | Description |
|-----------|------------|-------------|
| **Frontend** | React 18, Vite, Tailwind CSS, shadcn/ui | Chat interface with sidebar for document management and indexing |
| **Backend** | FastAPI, Python 3.11 | REST API for PDF processing, indexing, retrieval, and LLM streaming |
| **Ollama** | Ollama (Docker or external host) | Local LLM inference for embeddings, answer generation, and image descriptions |

## Data Flow <a name="DataFlow"></a>

1. PDF files are uploaded via the UI or placed directly into the docs folder
2. During indexing, the backend extracts text chunks and images from the PDFs
3. Text chunks are vectorized using the embedding model and stored in ChromaDB
4. Images are described by a vision-language model and indexed as well
5. When a user submits a query, the most relevant chunks and images are retrieved via similarity search
6. The LLM generates an answer based exclusively on the retrieved context
7. The answer is streamed token by token to the frontend, along with sources and follow-up suggestions

## Data Sources <a name="DataSources"></a>

| Source | Description | Location |
|--------|-------------|----------|
| PDF files | University documents serving as the knowledge base | `backend/data/docs/` |
| Text chunks | Embedded text segments for retrieval | Docker volume `backend_chroma` |
| Extracted images | Page images for VLM-based retrieval | Docker volume `backend_images` |

---

# Installation <a name="Installation"></a>

## Prerequisites <a name="Prerequisites"></a>

Before running the application, make sure the following tools are installed:

1. **Docker Desktop** (with Docker Compose): Docker allows you to run the application in containers without installing local dependencies. Download at [docker.com](https://www.docker.com/products/docker-desktop/).

2. **Git**: For version control and cloning the repository. Download at [git-scm.com](https://git-scm.com/).

3. **Ollama endpoint**: Either a local Ollama container (optionally with GPU support) or an external Ollama host reachable over the network.

## Installation Steps <a name="InstallationSteps"></a>

1. **Clone the repository**:
   ```bash
   git clone https://git.informatik.uni-hamburg.de/3gorke/askuhh.git
   cd askuhh
   ```

2. **Configure environment variables**: Create a `.env` file in the root directory of the repository (or copy the template if available):
   ```bash
   cp .env.example .env
   ```

3. **Edit the `.env` file**: Open the `.env` file and adjust the values to match your environment. A minimal configuration looks like this:
   ```dotenv
   OLLAMA_HOST=http://134.100.39.14:11435

   LLM_MODEL=qwen3-vl:8b-instruct
   EMBED_MODEL=snowflake-arctic-embed2
   TOP_K_IMAGES=3

   FRONTEND_PORT=3123
   BACKEND_PORT=8123
   ```

   The most important variables are:

   | Variable | Description | Default |
   |----------|-------------|---------|
   | `OLLAMA_HOST` | URL of the Ollama endpoint | `http://localhost:11434` |
   | `LLM_MODEL` | LLM model for answer generation | `qwen3-vl:8b-instruct` |
   | `EMBED_MODEL` | Model for text embeddings | `snowflake-arctic-embed2` |
   | `VLM_MODEL` | Vision-language model for image descriptions | `qwen3-vl:8b-instruct` |
   | `TOP_K_IMAGES` | Number of images retrieved per query | `3` |
   | `FRONTEND_PORT` | Port for the frontend | `3000` |
   | `BACKEND_PORT` | Port for the backend | `8000` |

4. **Start the application**: Launch the full stack with Docker Compose:
   ```bash
   docker compose up --build
   ```

   This starts two containers:
   - `askuhh-backend` – FastAPI server on the configured backend port
   - `askuhh-frontend` – Nginx server with the React app on the configured frontend port

5. **Optional – Start a local Ollama container**: If no external Ollama host is available, you can start a local Ollama container with GPU support:
   ```bash
   docker compose -f docker-compose.gpu.yml up -d ollama
   ```

   Make sure the required models are loaded on the Ollama host:
   ```bash
   ollama pull qwen3-vl:8b-instruct
   ollama pull snowflake-arctic-embed2
   ```

6. **Open the application**: Open a web browser and navigate to:
   ```
   http://localhost:3123
   ```

   (Adjust the port according to your `FRONTEND_PORT` configuration.)

---

# User Guide <a name="UserGuide"></a>

## Quick Start <a name="QuickStart"></a>

1. Upload one or more PDF files via the sidebar
2. Click **Index / Re-index** to process the documents
3. Wait until the chunk count appears in the sidebar
4. Ask your question in the chat window
5. Open source documents directly from the answer cards

## Document Management <a name="DocumentHandling"></a>

- **Upload**: Use the dropzone or file dialog in the sidebar. Only PDF files are accepted.
- **Delete**: Individual documents can be removed via the document list in the sidebar.
- **Re-indexing**: After adding or removing documents, indexing must be re-run via **Index / Re-index** for changes to take effect in retrieval.

## Chat Features <a name="ChatFeatures"></a>

- **Streaming answers**: Responses are displayed token by token in real time.
- **Source references**: Each answer shows the relevant PDF sources with page numbers. Clicking a source opens the highlighted passage in the original PDF.
- **Follow-up suggestions**: After each answer, three follow-up questions are automatically generated and can be sent with a single click.
- **Multilingual support**: Questions can be asked in German and English. Answers are returned in the language of the question.
- **Confidence scores**: An average token probability is calculated for each answer, serving as an indicator of response reliability.
- **Chat history**: Recent messages are stored locally and restored on revisit. The history can be cleared at any time using the trash button.
- **Cancel**: Ongoing answers can be interrupted at any time using the stop button.

## Indexing Notice <a name="IndexingNote"></a>

If no documents have been indexed yet, the application displays a notice banner and blocks the chat window. In this case, PDFs must first be uploaded and indexed.

---

# API Overview <a name="ApiOverview"></a>

The backend provides a REST API that can also be used independently of the frontend.

## Endpoints <a name="Endpoints"></a>

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/health` | GET | Health check for containers and monitoring |
| `/status` | GET | Status data for the frontend sidebar (document list, chunk count, model configuration) |
| `/documents/upload` | POST | Upload PDF files |
| `/documents/{filename}` | DELETE | Delete a PDF file |
| `/ingest` | POST | Build or rebuild the index |
| `/query/stream` | POST | SSE stream with answer tokens, sources, logprobs, and follow-ups |
| `/pdf/{filename}` | GET | Serve the original PDF |
| `/pdf/highlight` | POST | Return a PDF with highlighted chunk locations |

## Example: Streaming Query <a name="QueryExample"></a>
```bash
curl -X POST http://localhost:8123/query/stream \
  -H "Content-Type: application/json" \
  -d '{"question": "What are the deadlines for exam registration?", "history": []}'
```

The response is streamed as Server-Sent Events (SSE) with the following event types:

| Event | Content |
|-------|---------|
| `sources` | List of relevant PDF chunks with filename, page, and text |
| `token` | Single answer token (streamed incrementally) |
| `done` | Logprobs, average probability, and debug data |
| `followups` | List of three suggested follow-up questions |
| `error` | Error message in case of problems |

---

# Developer Guide <a name="DeveloperGuide"></a>

## Project Structure <a name="ProjectStructure"></a>
```
askuhh/
├── frontend/                    # React + Vite frontend
│   ├── src/
│   │   ├── App.jsx              # Main chat component
│   │   ├── api/
│   │   │   └── client.js        # API client with SSE parsing
│   │   ├── components/ui/
│   │   │   ├── Sidebar.jsx      # Document management and status
│   │   │   ├── message-item.jsx # Message display with sources and logprobs
│   │   │   ├── PdfModal.jsx     # PDF viewer with highlighting
│   │   │   └── button.jsx       # Reusable button component
│   │   └── hooks/
│   │       └── useStatus.js     # Status polling hook
│   ├── Dockerfile               # Multi-stage build (Node → Nginx)
│   ├── nginx.conf               # Reverse proxy configuration to backend
│   ├── package.json             # Dependencies and scripts
│   └── vite.config.js           # Vite configuration
│
├── backend/                     # FastAPI backend
│   ├── app/
│   │   ├── main.py              # API endpoints, prompt construction, streaming logic
│   │   ├── config.py            # Environment variables and system configuration
│   │   ├── pdf_highlighter.py   # PDF highlighting for source view
│   │   └── indexer/
│   │       ├── service.py       # Indexing and search orchestration
│   │       ├── embeddings.py    # Ollama embedding client
│   │       ├── store.py         # ChromaDB vector store
│   │       ├── pdf_processor.py # PDF text and image extraction
│   │       └── image_describer.py # VLM-based image descriptions
│   ├── data/docs/               # Mounted folder for PDF files
│   ├── Dockerfile               # Python 3.11 container
│   └── requirements.txt         # Python dependencies
│
├── docker-compose.yml           # Frontend + backend services
├── docker-compose.gpu.yml       # Optional local Ollama container with GPU
└── README.md
```

## Technology Stack <a name="TechStack"></a>

| Area | Technology |
|------|------------|
| Frontend | React 18, Vite, Tailwind CSS, shadcn/ui, Lucide Icons, react-markdown |
| Backend | FastAPI, Uvicorn, Python 3.11 |
| Vector database | ChromaDB |
| PDF processing | PyMuPDF (fitz) |
| Text splitting | LangChain `RecursiveCharacterTextSplitter` |
| LLM inference | Ollama (local or remote) |
| Default models | `qwen3-vl:8b-instruct` (LLM + VLM), `snowflake-arctic-embed2` (embeddings) |
| Containerization | Docker, Docker Compose, Nginx |

## Typical Development Workflow <a name="DevWorkflow"></a>

1. Clone the repository and switch to the `main` branch:
   ```bash
   git checkout main
   ```

2. Create a new feature branch:
   ```bash
   git checkout -b feature/your_feature_name
   ```

3. Start services with Docker Compose:
   ```bash
   docker compose up --build
   ```

4. Place test PDFs in `backend/data/docs/` and index them via the UI

5. Ask test questions and verify the sources in the answers

6. Check backend logs for retrieval and LLM behavior:
   ```bash
   docker compose logs -f backend
   ```

7. Commit your changes and create a pull request

## Notes on Models <a name="ModelNotes"></a>

- The **LLM model** (`LLM_MODEL`) is used for answer generation, follow-up questions, and language translation.
- The **embedding model** (`EMBED_MODEL`) creates vector representations of text chunks for semantic retrieval.
- The **vision-language model** (`VLM_MODEL`) describes extracted images from PDFs so that visual content becomes searchable as well.
- All models must be available on the configured Ollama host. To load them:
   ```bash
   ollama pull qwen3-vl:8b-instruct
   ollama pull snowflake-arctic-embed2
   ```

---

# Troubleshooting <a name="Troubleshooting"></a>

## Backend not reachable

- Check container status: `docker compose ps`
- Verify `BACKEND_PORT` mapping in the `.env` file
- Test the health endpoint directly: `http://localhost:8123/health`

## No answers or "No documents indexed"

- Make sure PDFs exist in `backend/data/docs/`
- Run **Index / Re-index** in the sidebar
- Check chunk count in the sidebar status display

## Ollama connection issues

- Verify `OLLAMA_HOST` in the `.env` file
- If using the local Ollama container, make sure it is running: `docker compose -f docker-compose.gpu.yml ps`
- Check that the selected models are pulled and available: `ollama list`

## Frontend shows a blank page

- Check the browser console for error messages
- Make sure the backend is reachable (Nginx proxies `/api` requests to the backend)
- Rebuild containers: `docker compose up --build`

---

# Next Steps <a name="NextSteps"></a>

Since this project was developed within a limited timeframe, there are several avenues for future improvement:

## Retrieval and Answer Quality

- **Reranking**: Implement a reranking step after initial retrieval to improve chunk relevance
- **Hybrid search**: Combine semantic search with keyword-based search (BM25) for more robust results
- **Chunk strategy optimization**: Evaluate different chunk sizes and overlap values for various document types

## Document Management

- **Incremental indexing**: Only index newly added documents instead of rebuilding the entire index
- **Per-document status**: Display the indexing status for each individual document
- **Indexing history**: Log past indexing operations for traceability

## Security and Access Control

- **Authentication**: Integrate an authentication solution for application access
- **Role-based access**: Implement different permission levels for different user groups

## Quality Assurance

- **Test suite**: Automated tests for API endpoints and retrieval quality
- **Evaluation benchmark**: Systematic evaluation of answer quality on an annotated test dataset

## User Experience

- **Enhanced PDF viewer**: Improved in-app PDF view with page navigation and zoom
- **Export functionality**: Allow users to export chat histories as PDF or Markdown
- **Feedback mechanism**: Enable users to rate answers to continuously improve quality

---

# License

This project is licensed under the MIT License.

Copyright (c) 2026 Felix Gorke, Florian Eigendorf, Mustafa Qarizada, Maximilian Stölken

Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated documentation files (the "Software"), to deal in the Software without restriction, including without limitation the rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software, and to permit persons to whom the Software is furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.

---

# Acknowledgments

AskUHH was developed as part of the *Applications with Artificial Intelligence* course at the University of Hamburg (WiSe 2025/26).

---

# Contact Information

For questions or suggestions, please reach out via the [GitLab repository](https://git.informatik.uni-hamburg.de/3gorke/askuhh).
