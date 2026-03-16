import logging
from typing import List

import fitz

logger = logging.getLogger(__name__)


# Highlights matching chunk text in a PDF and returns the modified file bytes.
def highlight_chunks_in_pdf(pdf_path: str, chunks: List[dict]) -> bytes:
    doc = fitz.open(pdf_path)

    for chunk in chunks:
        page_num = chunk["page"]
        text = chunk["text"]

        if page_num < 1 or page_num > doc.page_count:
            logger.warning(f"Page {page_num} out of range for PDF {pdf_path}")
            continue

        page = doc[page_num - 1]
        rects = page.search_for(text)
        if rects:
            page.add_highlight_annot(start=rects[0].tl, stop=rects[-1].br)
            logger.debug(f"Highlighted text on page {page_num}: {text[:50]}...")
        else:
            logger.debug(f"Text not found on page {page_num}: {text[:50]}...")

    return doc.write()
