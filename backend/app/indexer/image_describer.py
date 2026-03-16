import base64
import logging
from io import BytesIO
from typing import List

import httpx
from PIL import Image

from ..config import OLLAMA_HOST, VLM_MODEL

logger = logging.getLogger(__name__)

_client: httpx.Client | None = None

_PROMPT = (
    "Describe this document image concisely. "
    "Only state the type (table, bar chart, line chart, flowchart, pie chart, diagram, etc.). "
    "List all visible data, numbers, labels, axes, and legends. "
    "State the topic and key takeaway."
)


# Stores shared HTTP client used for VLM calls.
def init(client: httpx.Client) -> None:
    global _client
    _client = client


# Converts a PIL image to base64 PNG for model input.
def _pil_to_base64(img: Image.Image) -> str:
    buf = BytesIO()
    img.save(buf, format="PNG")
    return base64.b64encode(buf.getvalue()).decode()


# Describes one image using the configured vision-language model.
def describe_image(img: Image.Image) -> str:
    b64 = _pil_to_base64(img)
    resp = _client.post(
        f"{OLLAMA_HOST}/api/generate",
        json={
            "model": VLM_MODEL,
            "prompt": _PROMPT,
            "images": [b64],
            "stream": False,
            "options": {
                "num_predict": 256,
                "temperature": 0.2,
            },
        },
    )
    resp.raise_for_status()
    return resp.json().get("response", "").strip()


# Describes many images and falls back to page text if one fails.
def describe_images(entries: List[dict]) -> List[str]:
    descriptions = []
    for i, entry in enumerate(entries):
        img_id = entry.get("id", f"image_{i}")
        try:
            desc = describe_image(entry["pil_image"])
            logger.info(f"Described {img_id}: {desc[:80]}...")
            descriptions.append(desc)
        except Exception:
            logger.exception(f"Failed to describe {img_id}, using page_text fallback")
            descriptions.append(entry.get("page_text", "")[:500])
    return descriptions
