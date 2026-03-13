import logging
from typing import List

import httpx

from .config import OLLAMA_HOST, RERANK_MODEL

logger = logging.getLogger(__name__)

_client: httpx.Client | None = None

_RERANK_SYSTEM = (
    "Judge whether the Document meets the requirements based on the Query and the "
    'Instruct provided. Note that the answer can only be "yes" or "no".'
)
_INSTRUCT = "Retrieve relevant passages that answer the question"


def init(client: httpx.Client) -> None:
    global _client
    _client = client


def _score_one(question: str, doc_text: str) -> bool:
    """Score a single (question, document) pair. Returns True for relevant."""
    user_msg = (
        f"<Instruct>: {_INSTRUCT}\n"
        f"<Query>: {question}\n"
        f"<Document>: {doc_text}"
    )
    resp = _client.post(
        f"{OLLAMA_HOST}/api/chat",
        json={
            "model": RERANK_MODEL,
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
    return "yes" in answer and "no" not in answer.split("yes")[0]


def rerank(question: str, candidates: List[dict], top_k: int) -> List[dict]:
    """Pointwise reranking – sequential loop.

    Scores each candidate one by one, then returns up to top_k results
    preferring 'yes' chunks sorted by embedding score.
    """
    for i, c in enumerate(candidates):
        try:
            relevant = _score_one(question, c["text"][:2000])
        except Exception as e:
            logger.warning(f"Rerank failed for candidate {i}: {e}")
            relevant = False

        c["_relevant"] = relevant
        logger.info(
            f"Rerank: {'YES' if relevant else 'NO '} | "
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
