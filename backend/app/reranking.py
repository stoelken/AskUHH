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
                "options": {"temperature": 0.0, "num_predict": 5},
            },
        )
        resp.raise_for_status()

    answer = resp.json()["message"]["content"].strip().lower()
    logger.debug(f"Rerank score for chunk: {answer!r}")
    return 1.0 if answer.startswith("yes") else 0.0


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

    yes_chunks = sorted([c for c in candidates if c["_relevant"]],     key=lambda x: x["score"], reverse=True)
    no_chunks  = sorted([c for c in candidates if not c["_relevant"]], key=lambda x: x["score"], reverse=True)

    result = yes_chunks[:top_k]
    if len(result) < top_k:
        result += no_chunks[:top_k - len(result)]

    for c in result:
        del c["_relevant"]

    return result
