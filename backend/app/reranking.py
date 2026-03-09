import json
import logging
import re
from typing import List

import httpx

logger = logging.getLogger(__name__)


def rerank(
    question: str,
    candidates: List[dict],
    ollama_host: str,
    llm_model: str,
    top_k: int,
) -> List[dict]:
    """Listwise reranking via a single LLM call."""
    prompt = (
        "You are a document relevance ranking assistant.\n"
        "Given a question and numbered document passages, return ONLY a JSON array "
        "of ALL passage indices (0-based) ordered from most to least relevant.\n"
        "Respond with ONLY the JSON array, nothing else. Example: [2, 0, 4, 1, 3]\n\n"
        f"Question: {question}\n\n"
        "Passages:\n"
    )
    for i, c in enumerate(candidates):
        prompt += f"[{i}] {c['text'][:400]}\n\n"

    with httpx.Client(timeout=60) as client:
        resp = client.post(
            f"{ollama_host}/api/generate",
            json={
                "model":   llm_model,
                "prompt":  prompt,
                "stream":  False,
                "think":   False,
                "options": {"temperature": 0.0, "num_predict": 256},
            },
        )
        resp.raise_for_status()

    raw = resp.json()["response"].strip()
    logger.info(f"Reranking raw response: {raw!r}")

    match = re.search(r'\[[\d,\s]+\]', raw)
    if match:
        ranked_indices = json.loads(match.group())
        ranked_indices = [i for i in ranked_indices if 0 <= i < len(candidates)]
    else:
        logger.warning("Reranking: could not parse LLM response, using original order")
        ranked_indices = list(range(len(candidates)))

    for rank, idx in enumerate(ranked_indices):
        candidates[idx]["score"] = round(1.0 - rank / max(len(ranked_indices), 1), 4)

    return [candidates[i] for i in ranked_indices[:top_k]]
