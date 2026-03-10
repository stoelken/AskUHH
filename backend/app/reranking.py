import logging
from typing import List

import httpx

logger = logging.getLogger(__name__)

_RERANK_SYSTEM = (
    "Judge whether the Document meets the requirements based on the Query and the "
    "Instruct provided. Note that the answer can only be \"yes\" or \"no\"."
)
_INSTRUCT = "Retrieve relevant passages that answer the question"


def _score(question: str, doc_text: str, ollama_host: str, rerank_model: str) -> float:
    """Score a single (question, document) pair using Qwen3-Reranker. Returns 1.0 for 'yes' and 0.0 for 'no'."""
    user_msg = (
        f"<Instruct>: {_INSTRUCT}\n"
        f"<Query>: {question}\n"
        f"<Document>: {doc_text}"
    )
    with httpx.Client(timeout=30) as client:
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


def rerank(
    question: str,
    candidates: List[dict],
    ollama_host: str,
    rerank_model: str,
    top_k: int,
) -> List[dict]:
    """Pointwise reranking: score each candidate independently, sort by score.

    Returns up to top_k candidates. 'yes' chunks are preferred; 'no' chunks
    are only included as fallback if not enough 'yes' chunks exist.
    """
    for c in candidates:
        c["_relevant"] = _score(question, c["text"][:2000], ollama_host, rerank_model) == 1.0
        logger.info(f"Rerank: {'YES' if c['_relevant'] else 'NO '} | {c['file']} p{c['page']} | {c['text'][:60]!r}")

    yes_chunks = sorted([c for c in candidates if c["_relevant"]],     key=lambda x: x["score"], reverse=True)
    no_chunks  = sorted([c for c in candidates if not c["_relevant"]], key=lambda x: x["score"], reverse=True)

    logger.info(f"Rerank summary: {len(yes_chunks)} yes, {len(no_chunks)} no out of {len(candidates)} candidates")

    result = yes_chunks[:top_k]
    if len(result) < top_k:
        result += no_chunks[:top_k - len(result)]

    for c in result:
        del c["_relevant"]

    return result
