import json
import logging
import math
import re
from contextlib import asynccontextmanager
from pathlib import Path
from typing import List

import httpx
from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, StreamingResponse, Response
from pydantic import BaseModel, Field
from langdetect import detect

from .config import DOCS_DIR, EMBED_MODEL, LLM_MODEL, OLLAMA_HOST, SYSTEM_PROMPT, TOP_K_IMAGES
from .indexer import service as indexer


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s - %(message)s",
)
logger = logging.getLogger(__name__)
http_client: httpx.Client = None


# App startup/shutdown hook: sets shared HTTP client and indexer, then cleans up.
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

    indexer.init(http_client)
    logger.info(f"Ollama host: {OLLAMA_HOST}")

    yield

    http_client.close()
    logger.info("Shutting down.")

app = FastAPI(title="AskUHH Backend", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

class QueryRequest(BaseModel):
    question: str
    history: List[str] = Field(default_factory=list)

class StatusResponse(BaseModel):
    pdf_count:   int
    chunk_count: int
    image_count: int = 0
    documents:   List[str]
    indexed_documents: List[str]
    needs_index: bool
    ollama_host: str
    llm_model:   str
    embed_model: str

class IngestResponse(BaseModel):
    success:     bool
    message:     str
    pdf_count:   int
    chunk_count: int

class UploadResponse(BaseModel):
    success: bool
    message: str
    uploaded_files: List[str]
    skipped_files: List[str]

class HighlightRequest(BaseModel):
    filename: str
    chunks: List[dict]

# Quick health check endpoint for containers and uptime checks.
@app.get("/health")
def health():
    return {"status": "ok"}


# Serves one PDF file directly from docs storage.
@app.get("/pdf/{filename}")
def serve_pdf(filename: str):
    pdf_path = Path(DOCS_DIR) / filename
    if not pdf_path.exists() or pdf_path.suffix.lower() != ".pdf":
        raise HTTPException(status_code=404, detail="PDF not found")
    return FileResponse(pdf_path, media_type="application/pdf")


# Creates a highlighted PDF based on matched chunk text locations.
@app.post("/pdf/highlight")
def highlight_pdf(req: HighlightRequest):
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


# Returns app/index status like files, chunk counts, and model settings.
@app.get("/status", response_model=StatusResponse)
def status():
    pdf_files = list(Path(DOCS_DIR).glob("**/*.pdf"))
    text_count = 0
    img_count = 0
    indexed_documents = []

    try:
        st = indexer.get_status() or {}
        text_count = int(st.get("text_count", 0) or 0)
        img_count = int(st.get("image_count", 0) or 0)

        indexed_from_status = st.get("indexed_documents", [])
        if isinstance(indexed_from_status, list):
            indexed_documents = sorted(
                {
                    str(name).strip()
                    for name in indexed_from_status
                    if str(name).strip()
                }
            )
    except Exception:
        logger.exception("Failed to read index status")

    current_documents = sorted(f.name for f in pdf_files)
    needs_index = bool(current_documents) and set(current_documents) != set(indexed_documents)

    return StatusResponse(
        pdf_count=len(pdf_files),
        chunk_count=text_count,
        image_count=img_count,
        documents=current_documents,
        indexed_documents=indexed_documents,
        needs_index=needs_index,
        ollama_host=OLLAMA_HOST,
        llm_model=LLM_MODEL,
        embed_model=EMBED_MODEL,
    )


# Deletes a PDF from docs folder after basic safety validation.
@app.delete("/documents/{filename}")
def delete_document(filename: str):
    safe_name = Path(filename).name
    if not safe_name or Path(safe_name).suffix.lower() != ".pdf":
        raise HTTPException(status_code=400, detail="Only PDF files can be deleted.")

    target = Path(DOCS_DIR) / safe_name
    if not target.exists():
        raise HTTPException(status_code=404, detail="Document not found.")

    try:
        target.unlink()
        return {"success": True, "message": f"Deleted {safe_name}."}
    except Exception as e:
        logger.error("Failed to delete %s: %s", safe_name, e, exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to delete document.")


# Runs ingest/indexing over all PDFs currently in the docs directory.
@app.post("/ingest", response_model=IngestResponse)
def ingest():
    pdf_files = list(Path(DOCS_DIR).glob("**/*.pdf"))

    if not pdf_files:
        raise HTTPException(status_code=400, detail=f"No PDF files found in {DOCS_DIR}.")

    try:
        result = indexer.ingest_pdfs(pdf_files)
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


# Upload endpoint that stores only valid PDF files in docs storage.
@app.post("/documents/upload", response_model=UploadResponse)
async def upload_documents(files: List[UploadFile] = File(...)):
    docs_path = Path(DOCS_DIR)
    docs_path.mkdir(parents=True, exist_ok=True)

    uploaded_files: List[str] = []
    skipped_files: List[str] = []

    for file in files:
        name = Path(file.filename or "").name
        if not name or Path(name).suffix.lower() != ".pdf":
            skipped_files.append(name or "unnamed")
            continue

        target = docs_path / name
        try:
            content = await file.read()
            target.write_bytes(content)
            uploaded_files.append(name)
        except Exception:
            logger.exception("Failed to store uploaded file: %s", name)
            skipped_files.append(name)
        finally:
            await file.close()

    if not uploaded_files:
        raise HTTPException(
            status_code=400,
            detail="No valid PDF files uploaded.",
        )

    msg = f"Uploaded {len(uploaded_files)} PDF file(s)."
    if skipped_files:
        msg += f" Skipped {len(skipped_files)} file(s)."

    return UploadResponse(
        success=True,
        message=msg,
        uploaded_files=uploaded_files,
        skipped_files=skipped_files,
    )


# Builds the final LLM prompt from question + retrieved chunks.
def _get_baseline_logprobs(question: str) -> dict:
    """
    Call LLM without context to get baseline token probabilities.
    Used to compute context_lift = how much the retrieved context
    changed the model's confidence for each token.

    context_lift > 0  context increased confidence (model is using the docs)
    context_lift ≈ 0  model ignoring context (prior knowledge)
    context_lift < 0  context confused the model (potential conflict)
    """
    baseline_prompt = (
        f"Answer the following question as best you can.\n"
        f"Question: {question}\n\n"
        f"Answer:"
    )
    try:
        resp = http_client.post(
            f"{OLLAMA_HOST}/api/generate",
            json={
                "model":        LLM_MODEL,
                "prompt":       baseline_prompt,
                "system":       SYSTEM_PROMPT,
                "stream":       False,
                "logprobs":     True,
                "top_logprobs": 20,
                "options":      {"temperature": 0.1, "num_predict": 1024},
            },
        )
        resp.raise_for_status()
        raw = resp.json()
        result = {}
        for token_data in raw.get("logprobs", []):
            top = token_data.get("top_logprobs", [])
            if top:
                token = top[0]["token"]
                result[token] = round(math.exp(top[0]["logprob"]) * 100, 1)
        logger.info(f"Baseline logprobs collected: {len(result)} tokens")
        return result
    except Exception as e:
        logger.warning(f"Baseline logprobs failed (context_lift will be null): {e}")
        return {}


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


# Adds recent user questions so follow-up queries keep conversation context.
def _compose_question_with_history(question: str, history: List[str]) -> str:
    clean_history = [h.strip() for h in history if isinstance(h, str) and h.strip()]
    if not clean_history:
        return question

    recent = clean_history[-8:]
    history_block = "\n".join(f"- {item}" for item in recent)
    return (
        "Previous user questions (conversation context):\n"
        f"{history_block}\n\n"
        "Current question:\n"
        f"{question}"
    )


# Converts token logprob data into readable probability values + alternatives.
def _extract_actual_token_probability(token_data: dict) -> tuple[str, float | None, list]:
    generated_token = token_data.get("token", "")
    top = token_data.get("top_logprobs", [])

    probability = None
    chosen_logprob = token_data.get("logprob")
    if isinstance(chosen_logprob, (int, float)):
        probability = round(math.exp(chosen_logprob) * 100, 1)
    else:
        for alt in top:
            if alt.get("token") == generated_token and isinstance(alt.get("logprob"), (int, float)):
                probability = round(math.exp(alt["logprob"]) * 100, 1)
                break

    alternatives = []
    for alt in top:
        alt_token = alt.get("token", "")
        alt_logprob = alt.get("logprob")
        if alt_token == generated_token:
            continue
        if not isinstance(alt_logprob, (int, float)):
            continue
        alternatives.append(
            {
                "token": alt_token,
                "probability": round(math.exp(alt_logprob) * 100, 1),
            }
        )

    return generated_token, probability, alternatives


# Removes hidden <think> parts from model output before streaming to UI.
def _strip_think_content(state: dict, token: str) -> str:
    state["buffer"] += token
    out = []

    while True:
        buf = state["buffer"]
        low = buf.lower()

        if state["in_think"]:
            end_idx = low.find("</think>")
            if end_idx == -1:
                keep = len("</think>") - 1
                if len(buf) > keep:
                    state["buffer"] = buf[-keep:]
                break
            state["buffer"] = buf[end_idx + len("</think>"):]
            state["in_think"] = False
            continue

        start_idx = low.find("<think>")
        if start_idx == -1:
            keep = len("<think>") - 1
            if len(buf) <= keep:
                break
            out.append(buf[:-keep])
            state["buffer"] = buf[-keep:]
            break

        if start_idx > 0:
            out.append(buf[:start_idx])
        state["buffer"] = buf[start_idx + len("<think>"):]
        state["in_think"] = True

    return "".join(out)


# Asks the model for 3 short follow-up question suggestions.
def _generate_followups(question: str, answer: str, chunks: list) -> list:
    try:
        lang = detect(question)
    except Exception:
        lang = "de"

    context_hints = "\n".join(
        f"- [{c['file']}, p.{c['page']}]: {c['text'][:300]}"
        for c in chunks[:4]
    )

    prompt = (
        "Based on the following question, answer, and document context, "
        "suggest exactly 3 short follow-up questions the user might want to ask next.\n\n"
        "Rules:\n"
        "- Each question must be answerable from the same document collection.\n"
        "- Keep each question under 12 words.\n"
        "- Questions should explore different aspects, go deeper, or clarify related topics.\n"
        "- Do NOT repeat the original question.\n"
        f"- Write all questions in the same language as the original question (detected: {lang}).\n\n"
        f"Original question: {question}\n\n"
        f"Answer summary: {answer[:600]}\n\n"
        f"Available context:\n{context_hints}\n\n"
        'Respond with this exact JSON structure:\n'
        '{"questions": ["question 1", "question 2", "question 3"]}'
    )

    resp = http_client.post(
        f"{OLLAMA_HOST}/api/generate",
        json={
            "model": LLM_MODEL,
            "prompt": prompt,
            "system": "You are a helpful assistant. Respond with valid JSON only.",
            "stream": False,
            "format": "json",
            "options": {"temperature": 0.6, "num_predict": 256},
        },
    )
    resp.raise_for_status()
    raw = resp.json().get("response", "").strip()
    logger.info(f"Followup response: {raw[:300]!r}")

    parsed = json.loads(raw)

    if isinstance(parsed, list):
        items = parsed
    elif isinstance(parsed, dict):
        items = parsed.get("questions") or parsed.get("follow_ups") or parsed.get("followups") or []
    else:
        return []

    return [
        q.strip() for q in items
        if isinstance(q, str) and q.strip()
    ][:3]


# Groups retrieved chunks into compact source objects for the frontend.
def _build_sources(chunks: list) -> list:
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
    return [
        {"filename": name, "chunks": sources_map[name]}
        for name in list(sources_map.keys())[:3]
    ]

# Detects query language and translates to English if needed for better retrieval results.
def _translate_if_needed(question: str) -> str:
    try:
        lang = detect(question)
    except Exception:
        lang = "unknown"

    if lang == "de" or lang == "en":
        return question

    logger.info(f"Query language '{lang}' — translating to English for retrieval")
    try:
        resp = http_client.post(
            f"{OLLAMA_HOST}/api/generate",
            json={
                "model": LLM_MODEL,
                "prompt": f"Translate this text to ENGLISH. Output ONLY the translation:\n\n{question}",
                "system": "You are a translator. Output only the translated text, no explanations.",
                "stream": False,
                "options": {"temperature": 0, "num_predict": 512},
            },
        )
        resp.raise_for_status()
        translated = resp.json().get("response", "").strip()
        translated = re.sub(r"<think>.*?</think>", "", translated, flags=re.DOTALL).strip()
        logger.info(f"Translated search query: {translated[:200]!r}")
        return translated if translated else question
    except Exception as e:
        logger.warning(f"Translation failed, using original query: {e}")
        return question

# Main streaming query endpoint: retrieve, call LLM, and stream SSE events.
@app.post("/query/stream")
def query_stream(req: QueryRequest):
    try:
        merged_question = _compose_question_with_history(req.question, req.history)
        search_query = _translate_if_needed(req.question)
        chunks = indexer.search_text(search_query)
        baseline_probs = _get_baseline_logprobs(req.question)
    except Exception as e:
        logger.error(f"Retrieval failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

    if not chunks:
        raise HTTPException(status_code=400, detail="No documents indexed yet. Call /ingest first.")

    prompt = _build_prompt(merged_question, chunks)
    sources_data = _build_sources(chunks)

    all_images = []
    try:
        image_results = indexer.search_images(search_query, TOP_K_IMAGES)
        all_images = [img["image_b64"] for img in image_results if isinstance(img, dict) and img.get("image_b64")]
        logger.info(
            "Image search: %s images, scores=%s",
            len(all_images),
            [img.get("score") for img in image_results if isinstance(img, dict)],
        )
    except Exception as e:
        logger.warning(f"Image retrieval from indexer failed: {e}")

    logger.info(f"Debug: image_count={len(all_images)}")

    # Generator that pushes sources, tokens, done payload, and follow-ups via SSE.
    def event_generator():
        yield f"event: sources\ndata: {json.dumps(sources_data)}\n\n"

        token_probs = []
        think_state = {"buffer": "", "in_think": False}
        answer_parts: list[str] = []
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

                    # Stream visible tokens to frontend
                    token = chunk_data.get("response", "")
                    if token:
                        visible = _strip_think_content(think_state, token)
                        if visible:
                            yield f"event: token\ndata: {json.dumps(visible)}\n\n"
                            answer_parts.append(visible)

                    # Collect logprobs with baseline/context_lift
                    for token_data in chunk_data.get("logprobs", []):
                        generated_token, probability, alternatives = _extract_actual_token_probability(token_data)
                        if not generated_token:
                            continue
                        baseline = baseline_probs.get(generated_token, None)
                        context_lift = (
                            round(probability - baseline, 1)
                            if probability is not None and baseline is not None else None
                        )
                        token_probs.append({
                            "token":        generated_token,
                            "probability":  probability,
                            "baseline":     baseline,
                            "context_lift": context_lift,
                            "alternatives": alternatives,
                        })

                    if chunk_data.get("done", False):
                        if not think_state["in_think"] and think_state["buffer"]:
                            tail = think_state["buffer"]
                            think_state["buffer"] = ""
                            yield f"event: token\ndata: {json.dumps(tail)}\n\n"
                            answer_parts.append(tail)
                            token_probs.append({
                                "token":        tail,
                                "probability":  None,
                                "baseline":     None,
                                "context_lift": None,
                                "alternatives": [],
                            })
                        break
        except Exception as e:
            logger.error(f"Streaming failed: {e}", exc_info=True)
            yield f"event: error\ndata: {json.dumps(str(e))}\n\n"

        numeric_probs = [t["probability"] for t in token_probs if isinstance(t.get("probability"), (int, float))]
        avg_probability = round(sum(numeric_probs) / len(numeric_probs), 1) if numeric_probs else None

        done_payload = {
            "logprobs": token_probs,
            "avg_probability": avg_probability,
            "token_count": len(token_probs),
            "debug_images": all_images,
        }
        yield f"event: done\ndata: {json.dumps(done_payload)}\n\n"

        full_answer = "".join(answer_parts)
        try:
            followups = _generate_followups(req.question, full_answer, chunks)
            if followups:
                yield f"event: followups\ndata: {json.dumps(followups)}\n\n"
        except Exception as e:
            logger.warning(f"Follow-up generation failed (non-critical): {e}")

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
