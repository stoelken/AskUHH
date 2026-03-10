import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List

import httpx

logger = logging.getLogger(__name__)

_RERANK_SYSTEM = (
    "Judge whether the Document meets the requirements based on the Query and the "
    'Instruct provided. Note that the answer can only be "yes" or "no".'
)
_INSTRUCT = "Retrieve relevant passages that answer the question"


def _score(
    question: str,
    doc_text: str,
    ollama_host: str,
    rerank_model: str,
    client: httpx.Client,
) -> float:
    """Score a single (question, document) pair using Qwen3-Reranker.

    Returns 1.0 for 'yes' and 0.0 for 'no'.
    Uses the *shared* httpx.Client for connection pooling.
    """
    user_msg = (
        f"<Instruct>: {_INSTRUCT}\n"
        f"<Query>: {question}\n"
        f"<Document>: {doc_text}"
    )
    resp = client.post(
        f"{ollama_host}/api/chat",
        json={
            "model": rerank_model,
            "messages": [
                {"role": "system",    "content": _RERANK_SYSTEM},
                {"role": "user",      "content": user_msg},
                {"role": "assistant", "content": "<think>\n\n</think>\n\n"},
            ],
            "stream": False,
            "options": {"temperature": 0.0, "num_predict": 32},
        },
    )
    resp.raise_for_status()

    answer = resp.json()["message"]["content"].strip().lower()
    relevant = "yes" in answer and "no" not in answer.split("yes")[0]
    return 1.0 if relevant else 0.0


def _score_candidate(
    idx: int,
    candidate: dict,
    question: str,
    ollama_host: str,
    rerank_model: str,
    client: httpx.Client,
) -> tuple:
    """Wrapper for parallel execution — scores one candidate, returns (index, is_relevant)."""
    try:
        score = _score(question, candidate["text"][:2000], ollama_host, rerank_model, client)
        return idx, score == 1.0
    except Exception as e:
        logger.warning(f"Rerank failed for candidate {idx}: {e}")
        return idx, False


def rerank(
    question: str,
    candidates: List[dict],
    ollama_host: str,
    rerank_model: str,
    top_k: int,
    client: httpx.Client,
    max_workers: int = 5,
) -> List[dict]:
    """Pointwise reranking with **parallel** scoring.

    Scores all candidates concurrently via a ThreadPoolExecutor,
    then sorts and returns up to top_k results.
    'yes' chunks are preferred; 'no' chunks serve as fallback.
    """
    with ThreadPoolExecutor(max_workers=max_workers) as pool:
        futures = {
            pool.submit(
                _score_candidate, i, c, question, ollama_host, rerank_model, client,
            ): i
            for i, c in enumerate(candidates)
        }

        for future in as_completed(futures):
            idx, relevant = future.result()
            candidates[idx]["_relevant"] = relevant

    for c in candidates:
        logger.info(
            f"Rerank: {'YES' if c['_relevant'] else 'NO '} | "
            f"{c['file']} p{c['page']} | {c['text'][:60]!r}"
        )

    yes_chunks = sorted(
        [c for c in candidates if c["_relevant"]],
        key=lambda x: x["score"], reverse=True,
    )
    no_chunks = sorted(
        [c for c in candidates if not c["_relevant"]],
        key=lambda x: x["score"], reverse=True,
    )

    logger.info(
        f"Rerank summary: {len(yes_chunks)} yes, {len(no_chunks)} no "
        f"out of {len(candidates)} candidates"
    )

    result = yes_chunks[:top_k]
    if len(result) < top_k:
        result += no_chunks[: top_k - len(result)]

    for c in result:
        del c["_relevant"]

    return result