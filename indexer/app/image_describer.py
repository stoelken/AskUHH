import base64
import logging
from io import BytesIO
from typing import List

import httpx
from PIL import Image

from .config import OLLAMA_HOST, VLM_MODEL

logger = logging.getLogger(__name__)

_client: httpx.Client | None = None

_PROMPT = (
    "Beschreibe dieses Bild aus einem Dokument detailliert auf Deutsch. "
    "Nenne den Typ des Bildes (z.B. Tabelle, Balkendiagramm, Liniendiagramm, "
    "Flussdiagramm, Tortendiagramm, Screenshot, Foto, Schema, etc.). "
    "Beschreibe alle sichtbaren Daten, Zahlen, Beschriftungen, Achsen und Legenden. "
    "Erkläre das Thema und die Kernaussage des Bildes."
)


def init(client: httpx.Client) -> None:
    global _client
    _client = client


def _pil_to_base64(img: Image.Image) -> str:
    buf = BytesIO()
    img.save(buf, format="PNG")
    return base64.b64encode(buf.getvalue()).decode()


def describe_image(img: Image.Image) -> str:
    """Send a single image to the Ollama VLM and return a text description."""
    b64 = _pil_to_base64(img)
    resp = _client.post(
        f"{OLLAMA_HOST}/api/generate",
        json={
            "model": VLM_MODEL,
            "prompt": _PROMPT,
            "images": [b64],
            "stream": False,
        },
    )
    resp.raise_for_status()
    return resp.json().get("response", "").strip()


def describe_images(entries: List[dict]) -> List[str]:
    """Generate text descriptions for a list of image entries.

    Each entry must have a 'pil_image' key with a PIL Image.
    Returns a list of description strings (same order as entries).
    """
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
