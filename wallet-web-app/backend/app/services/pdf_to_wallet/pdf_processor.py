"""
PDF processing utilities for text extraction and page rendering.
"""

import logging
from typing import List
import numpy as np

try:
    import fitz  # PyMuPDF
    import cv2
except ImportError as e:
    raise ImportError(f"Missing required dependency: {e}. Install with: pip install pymupdf opencv-python")

logger = logging.getLogger(__name__)


class PDFProcessor:
    """Handles PDF text extraction and page rendering"""
    
    @staticmethod
    def extract_text(pdf_path: str) -> str:
        """Extract raw text from PDF using PyMuPDF"""
        try:
            doc = fitz.open(pdf_path)
            text_parts = []
            page_count = len(doc)
            
            for page_num in range(page_count):
                page = doc[page_num]
                text = page.get_text()
                text_parts.append(text)
                
            doc.close()
            raw_text = "\n".join(text_parts)
            logger.info(f"Extracted {len(raw_text)} characters from {page_count} pages")
            return raw_text
            
        except Exception as e:
            logger.error(f"Failed to extract text from PDF: {e}")
            return ""

    @staticmethod
    def render_pages(pdf_path: str, dpi: int = 300) -> List[np.ndarray]:
        """Render PDF pages to images at specified DPI"""
        try:
            doc = fitz.open(pdf_path)
            images = []
            
            # Calculate matrix scale factor (dpi/72)
            scale_factor = dpi / 72.0
            
            for page_num in range(len(doc)):
                page = doc[page_num]
                mat = fitz.Matrix(scale_factor, scale_factor)
                pix = page.get_pixmap(matrix=mat)
                img_data = pix.tobytes("png")
                
                # Convert to OpenCV format
                nparr = np.frombuffer(img_data, np.uint8)
                img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
                images.append(img)
                
            doc.close()
            logger.info(f"Rendered {len(images)} pages to images at {dpi} DPI")
            return images
            
        except Exception as e:
            logger.error(f"Failed to render PDF pages: {e}")
            return []
