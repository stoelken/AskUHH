import logging
import math
import re
from typing import List

import httpx

logger = logging.getLogger(__name__)


def sigmoid(x: float) -> float:
    """Normalize logit score to [0,1] range using sigmoid function."""
    try:
        return 1.0 / (1.0 + math.exp(-x))
    except OverflowError:
        return 0.0 if x < 0 else 1.0


def _score_one(
    question: str,
    doc_text: str,
    ollama_host: str,
    rerank_model: str,
    client: httpx.Client,
) -> float:
    """Score a single (question, document) pair using BGE-Reranker-v2-m3 via Ollama.
    """
    prompt = f"Query: {question}\nDocument: {doc_text}\nRelevance:"

    resp = client.post(
        f"{ollama_host}/api/generate",
        json={
            "model": rerank_model,
            "prompt": prompt,
            "stream": False,
            "options": {"temperature": 0.0, "num_predict": 20},
        },
        timeout=30.0,
    )
    resp.raise_for_status()

    response_text = resp.json().get("response", "").strip()
    logger.debug(f"BGE Response: {response_text!r}")

    # Parse numeric score from response
    try:
        match = re.search(r'[-]?\d+\.?\d*', response_text)
        if match:
            value = float(match.group())
            if 0.0 <= value <= 1.0:
                return value
            else:
                return sigmoid(max(-10.0, min(10.0, value)))
    except (ValueError, AttributeError):
        logger.warning(f"BGE: Could not parse score from response: {response_text!r}")

    return 0.5 



def rerank(
    question: str,
    candidates: List[dict],
    ollama_host: str,
    rerank_model: str,
    top_k: int,
    client: httpx.Client,
) -> List[dict]:
    """Score all candidates using BGE-Reranker and return top-k by reranker score (normalized with sigmoid).
    """
    scores = []

    for i, c in enumerate(candidates):
        try:
            score = _score_one(
                question, c["text"][:2000], ollama_host, rerank_model, client,
            )
            c["score"] = score
            scores.append(score)

            logger.info(
                f"Rerank: score={score:.4f} | "
                f"{c['file']} p{c['page']} | {c['text'][:60]!r}"
            )
        except Exception as e:
            logger.warning(f"Rerank failed for candidate {i}: {e}")
            c["score"] = 0.0
            scores.append(0.0)

    logger.info(
        f"Rerank summary: "
        f"min={min(scores):.4f}, max={max(scores):.4f}, avg={sum(scores)/len(scores):.4f} "
        f"out of {len(candidates)} candidates"
    )

    # Sort by reranker score, descending
    result = sorted(candidates, key=lambda x: x["score"], reverse=True)[:top_k]

    return result
