import logging
from pathlib import Path
from typing import List

import fitz
from PIL import Image
import io

from .config import IMAGES_DIR

logger = logging.getLogger(__name__)


def extract_images_from_pdf(
    pdf_bytes: bytes,
    filename: str,
) -> List[dict]:
    """Extract all images from a PDF, save to disk, return metadata + PIL images.

    Returns list of dicts:
      {id, file_name, page, image_path, pil_image}
    """
    stem = Path(filename).stem
    out_dir = Path(IMAGES_DIR) / stem
    out_dir.mkdir(parents=True, exist_ok=True)

    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    results = []

    for page_num in range(len(doc)):
        page = doc[page_num]
        seen_rects = []

        def is_duplicate(rect):
            for seen in seen_rects:
                if abs(rect.x0 - seen.x0) < 10 and abs(rect.y0 - seen.y0) < 10:
                    return True
            return False

        def collect(rect, source):
            if rect.is_empty or rect.get_area() < 500:
                return
            if is_duplicate(rect):
                return
            seen_rects.append(rect)

            pix = page.get_pixmap(dpi=150, clip=rect)
            png_bytes = pix.tobytes("png")

            img_idx = len([r for r in results if r["page"] == page_num + 1])
            rel_path = f"{stem}/p{page_num + 1:04d}_img{img_idx:03d}.png"
            abs_path = Path(IMAGES_DIR) / rel_path
            abs_path.write_bytes(png_bytes)

            pil_img = Image.open(io.BytesIO(png_bytes)).convert("RGB")

            results.append({
                "id": f"{stem}__p{page_num + 1:04d}__img{img_idx:03d}",
                "file_name": filename,
                "page": page_num + 1,
                "image_path": rel_path,
                "pil_image": pil_img,
            })
            logger.info(f"  [{source}] {rel_path}")

        # 1) embedded raster blocks
        for block in page.get_text("dict")["blocks"]:
            if block["type"] == 1:
                collect(fitz.Rect(block["bbox"]), "type1_block")

        # 2) xobject images
        for img_info in page.get_images(full=True):
            bbox = page.get_image_bbox(img_info)
            collect(bbox, "xobject")

        # 3) vector graphics / drawings
        for rect in page.cluster_drawings():
            collect(rect, "drawing_cluster")

    doc.close()
    logger.info(f"Extracted {len(results)} images from {filename}")
    return results
