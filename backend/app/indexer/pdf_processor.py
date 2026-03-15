import hashlib
import io
import logging
from pathlib import Path
from typing import List

import fitz
from PIL import Image

from ..config import IMAGES_DIR

logger = logging.getLogger(__name__)

MIN_AREA         = 10_000
MIN_AREA_DRAWING = 25_000
MIN_DIM          = 50
MIN_ASPECT       = 0.15
MAX_ASPECT       = 6.5


def _passes_size_filter(rect: fitz.Rect, min_area: int) -> bool:
    if rect.is_empty or rect.get_area() < min_area:
        return False
    if rect.width < MIN_DIM or rect.height < MIN_DIM:
        return False
    aspect = rect.width / rect.height
    return MIN_ASPECT <= aspect <= MAX_ASPECT


def _overlap_ratio(a: fitz.Rect, b: fitz.Rect) -> float:
    inter = a & b
    if inter.is_empty:
        return 0.0
    return inter.get_area() / min(a.get_area(), b.get_area())


def extract_images_from_pdf(
    pdf_bytes: bytes,
    filename: str,
) -> List[dict]:
    stem = Path(filename).stem
    out_dir = Path(IMAGES_DIR) / stem
    out_dir.mkdir(parents=True, exist_ok=True)

    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    results = []
    seen_hashes: set[str] = set()

    for page_num in range(len(doc)):
        page = doc[page_num]
        page_text = page.get_text().strip()
        accepted_rects: List[fitz.Rect] = []

        def _is_overlapping(rect: fitz.Rect) -> bool:
            return any(_overlap_ratio(rect, seen) > 0.5 for seen in accepted_rects)

        def collect(rect: fitz.Rect, min_area: int) -> None:
            if not _passes_size_filter(rect, min_area):
                return
            if _is_overlapping(rect):
                return

            pix = page.get_pixmap(dpi=150, clip=rect)
            png_bytes = pix.tobytes("png")

            content_hash = hashlib.md5(png_bytes).hexdigest()
            if content_hash in seen_hashes:
                return
            seen_hashes.add(content_hash)

            accepted_rects.append(rect)

            img_idx = len([r for r in results if r["page"] == page_num + 1])
            rel_path = f"{stem}/p{page_num + 1:04d}_img{img_idx:03d}.png"
            (Path(IMAGES_DIR) / rel_path).write_bytes(png_bytes)

            pil_img = Image.open(io.BytesIO(png_bytes)).convert("RGB")
            results.append({
                "id":         f"{stem}__p{page_num + 1:04d}__img{img_idx:03d}",
                "file_name":  filename,
                "page":       page_num + 1,
                "image_path": rel_path,
                "pil_image":  pil_img,
                "page_text":  page_text,
            })
            logger.info(f"  Kept {rel_path} ({rect.width:.0f}×{rect.height:.0f} pt)")

        for block in page.get_text("dict")["blocks"]:
            if block["type"] == 1:
                collect(fitz.Rect(block["bbox"]), MIN_AREA)

        for img_info in page.get_images(full=True):
            collect(page.get_image_bbox(img_info), MIN_AREA)

        for rect in page.cluster_drawings():
            collect(rect, MIN_AREA_DRAWING)

    doc.close()
    logger.info(f"Extracted {len(results)} images from {filename}")
    return results
