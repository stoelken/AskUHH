import logging
from typing import List

import torch
from PIL import Image
from transformers import CLIPModel, CLIPProcessor

from .config import CLIP_MODEL, DEVICE

logger = logging.getLogger(__name__)

_model: CLIPModel | None = None
_processor: CLIPProcessor | None = None
_device: str = DEVICE


def load() -> None:
    global _model, _processor, _device
    if not torch.cuda.is_available() and _device == "cuda":
        logger.warning("CUDA not available, falling back to CPU")
        _device = "cpu"
    logger.info(f"Loading CLIP model {CLIP_MODEL} on {_device}...")
    _model = CLIPModel.from_pretrained(CLIP_MODEL).to(_device)
    _processor = CLIPProcessor.from_pretrained(CLIP_MODEL)
    _model.eval()
    logger.info("CLIP model loaded.")


def is_loaded() -> bool:
    return _model is not None


def embed_images(images: List[Image.Image]) -> List[List[float]]:
    """Encode a batch of PIL images with CLIP's image encoder (512-dim)."""
    inputs = _processor(images=images, return_tensors="pt").to(_device)
    with torch.no_grad():
        features = _model.get_image_features(**inputs)
    features = features / features.norm(dim=-1, keepdim=True)
    return features.cpu().tolist()


def embed_query(text: str) -> List[float]:
    """Encode a text query with CLIP's text encoder (512-dim)."""
    inputs = _processor(text=[text], return_tensors="pt", padding=True).to(_device)
    with torch.no_grad():
        features = _model.get_text_features(**inputs)
    features = features / features.norm(dim=-1, keepdim=True)
    return features[0].cpu().tolist()
